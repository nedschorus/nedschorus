"""Call the nc-shared-database service on ned-box: record an event, or read.

Every program on either machine that records an event in the nc-shared-database
or reads from it calls the service through this module. ned-box is required:
nothing is kept on this machine for a later send.

Load it by path, under the snake_case form of its file name:

    spec = importlib.util.spec_from_file_location(
        "nc_shared_database_service_call_common", <path>)

It runs on both machines, the Mac's Apple Python 3.9 included.

A one-shot program calls nc_shared_database_service_http_request_single_attempt
or nc_shared_database_event_send_single_attempt, which make one call with a
2-second limit and return the service's JSON answer, or raise
NcSharedDatabaseServiceCallFailed; the program prints the exception's text on
standard error and exits 1.

A handoff-supervisor calls
nc_shared_database_event_send_retrying_every_30_seconds_until_service_answers,
which sends the same event ID every 30 seconds until the service answers, and
returns None, after logging the FAILED line, when the service refuses the
event.

Which answer counts as what:
  200            success
  400, 401, 422  the service answered and refused the request: a FAILED line
                 with the service's answer; calling again would be refused again
  anything else  no answer in 2 seconds, a refused connection, or any other
                 status, such as a 500: ned-box cannot be reached
"""

import http.client
import json
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

NC_SHARED_DATABASE_SERVICE_URL = "http://ned-box.local:8765"
NC_SHARED_DATABASE_SERVICE_TOKEN_FILE_PATH = (Path.home() / ".config" / "nedschorus"
                                               / "nc-shared-database-service.token")
NC_SHARED_DATABASE_SERVICE_ACCEPTED_TOKENS_FILE_ON_NED_BOX = (
    "~/.config/nedschorus/nc-shared-database-service-accepted-tokens")
NC_SHARED_DATABASE_SERVICE_CALL_TIMEOUT_SECONDS = 2
NC_SHARED_DATABASE_SERVICE_CALL_AGAIN_AFTER_SECONDS = 30
THIS_MACHINE = "mac" if sys.platform == "darwin" else "ned-box"
STATUSES_THE_SERVICE_REFUSES_WITH = (400, 401, 422)


class NcSharedDatabaseServiceCallFailed(Exception):
    """The call stored or read nothing. service_answered is True when the service
    refused the request (400, 401 or 422), so calling again would not help, and
    False when ned-box could not be reached."""

    def __init__(self, message, service_answered):
        super().__init__(message)
        self.service_answered = service_answered


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# Messages follow docs/nedschorus-wiki/nedschorus-how-to-write-a-tool-message-to-agent-such-as-a-hook-refusal-or-script-error.md.
SUBAGENT_PASSES_IT_TO_DISPATCHING_AGENT_LINE = (
    "If you are a subagent, pass the same fact to the agent that dispatched you instead of "
    "telling the user.")
NC_SHARED_DATABASE_SERVICE_INSTALL_COMMAND_ON_THE_MAC = (
    "python3 ~/Projects/nedschorus/nc-systems/nc-shared-database/"
    "nc-shared-database-service-on-ned-box-and-jobs-on-both-machines-install-from-the-mac.py")
NC_SHARED_DATABASE_SERVICE_STATUS_COMMAND_ON_NED_BOX = (
    "systemctl --user status nc-shared-database-service")


def _not_reached(method, url, what_happened):
    return NcSharedDatabaseServiceCallFailed(
        f"FAILED: ned-box cannot be reached: {method} {url}, a call to the nc-shared-database "
        f"service on ned-box, {what_happened}, so nothing was recorded or read. The service "
        f"holds the only record of the agent-seats, so a program that needs it stops until "
        f"ned-box answers.\n"
        f"Check the service: on ned-box run `{NC_SHARED_DATABASE_SERVICE_STATUS_COMMAND_ON_NED_BOX}`; "
        f"on the Mac run `ssh nedlern@ned-box '{NC_SHARED_DATABASE_SERVICE_STATUS_COMMAND_ON_NED_BOX}'`.\n"
        f"Then tell the user: \"The nc-shared-database service on ned-box did not answer "
        f"{method} {url} ({what_happened}); nothing was recorded. The check of the service "
        f"printed: <the first lines the check printed, or ssh's error>.\" Do not record or read "
        f"the agent-seat records another way, such as from files: the step waits until ned-box "
        f"answers.\n"
        f"{SUBAGENT_PASSES_IT_TO_DISPATCHING_AGENT_LINE}",
        service_answered=False)


def _refused(method, url, status, answer, token_file):
    if status == 401:
        return NcSharedDatabaseServiceCallFailed(
            f"FAILED: the nc-shared-database service on ned-box refused {method} {url} with "
            f"401, and recorded and read nothing: {answer}. The service answers only a request "
            f"whose token is one line of its accepted-tokens file, "
            f"{NC_SHARED_DATABASE_SERVICE_ACCEPTED_TOKENS_FILE_ON_NED_BOX} on ned-box, and this "
            f"machine sent the token in {token_file}.\n"
            f"If you are on the Mac: run `{NC_SHARED_DATABASE_SERVICE_INSTALL_COMMAND_ON_THE_MAC}` "
            f"once, which writes both machines' tokens into that file, and follow what it prints "
            f"if it stops.\n"
            f"If you are on ned-box: tell the user: \"The nc-shared-database service on ned-box "
            f"refuses ned-box's token in {token_file}. Running "
            f"`{NC_SHARED_DATABASE_SERVICE_INSTALL_COMMAND_ON_THE_MAC}` in a Terminal on the Mac "
            f"puts it into the service's accepted-tokens file.\"\n"
            f"{SUBAGENT_PASSES_IT_TO_DISPATCHING_AGENT_LINE}",
            service_answered=True)
    return NcSharedDatabaseServiceCallFailed(
        f"FAILED: the nc-shared-database service on ned-box refused {method} {url} with "
        f"{status}, and stored nothing: {answer}. The service refuses a request it cannot parse "
        f"or place, so the same request sent again is refused again.\n"
        f"Correct the program that built the request, using the service's answer above; the "
        f"operations and the fields each takes are OPERATION_FIELDS in "
        f"nc-systems/nc-shared-database/nc-shared-database-service.py.",
        service_answered=True)


def nc_shared_database_service_http_request_single_attempt(
        path, body=None, service_url=NC_SHARED_DATABASE_SERVICE_URL,
        token_file=NC_SHARED_DATABASE_SERVICE_TOKEN_FILE_PATH,
        timeout_seconds=NC_SHARED_DATABASE_SERVICE_CALL_TIMEOUT_SECONDS):
    """One call: a POST of body as JSON when body is given, otherwise a GET.

    Returns the service's JSON answer to a success; raises
    NcSharedDatabaseServiceCallFailed otherwise.
    """
    method = "GET" if body is None else "POST"
    url = service_url + path
    try:
        token = Path(token_file).read_text(encoding="utf-8").strip()
    except OSError as error:
        raise NcSharedDatabaseServiceCallFailed(
            f"FAILED: {method} {url} was not sent, so nothing was recorded or read: this "
            f"machine's token file for the nc-shared-database service, {token_file}, cannot be "
            f"read ({error}). Every call to the service carries this machine's token from that "
            f"file.\n"
            f"If you are on the Mac: run `{NC_SHARED_DATABASE_SERVICE_INSTALL_COMMAND_ON_THE_MAC}` "
            f"once, which writes the token file, and follow what it prints if it stops.\n"
            f"If you are on ned-box: tell the user: \"The nc-shared-database service cannot be "
            f"called from ned-box: its token file {token_file} cannot be read ({error}). Running "
            f"`{NC_SHARED_DATABASE_SERVICE_INSTALL_COMMAND_ON_THE_MAC}` in a Terminal on the Mac "
            f"writes it.\"\n"
            f"{SUBAGENT_PASSES_IT_TO_DISPATCHING_AGENT_LINE}", service_answered=True)
    request = urllib.request.Request(
        url, method=method,
        data=None if body is None else json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        answer = error.read().decode("utf-8", "replace").strip()
        if error.code in STATUSES_THE_SERVICE_REFUSES_WITH:
            raise _refused(method, url, error.code, answer, token_file)
        raise _not_reached(method, url, f"was answered {error.code}: {answer}")
    except (OSError, http.client.HTTPException) as error:
        # urllib.error.URLError, a timeout and a refused connection are all OSError.
        raise _not_reached(method, url, f"got no answer within {timeout_seconds} seconds "
                                        f"({type(error).__name__}: {error})")


def nc_shared_database_event_body(operation, seat_id, fields, event_id=None):
    """The event as POST /events takes it; seat_id is None for an operation that names
    no agent-seat, such as machine-booted, and fields are the operation's, as the
    service's OPERATION_FIELDS lists them."""
    return {"event_id": event_id or str(uuid.uuid4()), "machine": THIS_MACHINE,
            "operation": operation, "occurred_at": utc_now(), "seat_id": seat_id,
            "fields": fields}


def nc_shared_database_event_send_single_attempt(operation, seat_id, fields, **call_options):
    """Record one event by one call; returns the service's answer, such as
    {"sequence": 7}, or raises NcSharedDatabaseServiceCallFailed."""
    return nc_shared_database_service_http_request_single_attempt(
        "/events", nc_shared_database_event_body(operation, seat_id, fields), **call_options)


def nc_shared_database_event_send_retrying_every_30_seconds_until_service_answers(
        operation, seat_id, fields, log, sleep=time.sleep, **call_options):
    """Record one event, calling again with the same event ID every 30 seconds while
    ned-box cannot be reached.

    log takes one line of text. It is called once when the wait starts, once when it
    stops, and with the FAILED line when the service refuses the event. Returns the
    service's answer, or None when the service refused the event; never raises
    NcSharedDatabaseServiceCallFailed.
    """
    body = nc_shared_database_event_body(operation, seat_id, fields)
    waiting_since = None
    while True:
        try:
            answer = nc_shared_database_service_http_request_single_attempt(
                "/events", body, **call_options)
        except NcSharedDatabaseServiceCallFailed as failure:
            if failure.service_answered:
                if waiting_since is not None:
                    log(f"ned-box answered again; waited since {waiting_since} to record "
                        f"{operation} event {body['event_id']}")
                log(str(failure))
                return None
            if waiting_since is None:
                waiting_since = utc_now()
                log(f"waiting for ned-box to record {operation} event {body['event_id']}, "
                    f"calling again every {NC_SHARED_DATABASE_SERVICE_CALL_AGAIN_AFTER_SECONDS} "
                    f"seconds: {failure}")
            sleep(NC_SHARED_DATABASE_SERVICE_CALL_AGAIN_AFTER_SECONDS)
            continue
        if waiting_since is not None:
            log(f"ned-box answered again; waited since {waiting_since} to record {operation} "
                f"event {body['event_id']}")
        return answer
