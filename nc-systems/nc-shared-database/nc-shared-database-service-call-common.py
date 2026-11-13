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
event or this machine's token file cannot be read.

Which answer counts as what:
  200            success
  400, 401, 422  the service answered and refused the request: a FAILED line
                 with the service's answer; calling again is refused again until
                 the cause is corrected
  anything else  no answer within 2 seconds, name lookup of ned-box.local
                 included, a refused connection, or any other status, such as a
                 500: ned-box cannot be reached

A call whose name lookup has not finished within the 2 seconds sends nothing. An
event sent whose answer did not come within them may still be stored, and the
FAILED line says so; the service stores an event ID once, so sending the same
event ID again is safe.
"""

import http.client
import json
import socket
import sys
import threading
import time
import urllib.parse
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
_name_lookups_not_finished = {}


class NcSharedDatabaseServiceCallFailed(Exception):
    """The call read nothing, and stored nothing unless its text says the event was sent
    and may still be stored. service_answered is True when calling again
    would not help: the service refused the request (400, 401 or 422), or this
    machine's token file cannot be read, so nothing was sent. It is False when
    ned-box could not be reached."""

    def __init__(self, message, service_answered):
        super().__init__(message)
        self.service_answered = service_answered


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# Messages follow docs/nedschorus-wiki/nedschorus-how-to-write-a-tool-message-to-agent-such-as-a-hook-refusal-or-script-error.md.
SUBAGENT_PASSES_IT_TO_DISPATCHING_AGENT_LINE = (
    "If you are a subagent, on either machine, and a line above says to tell the user, send "
    "the words that line quotes to the agent that dispatched you instead.")
NC_SHARED_DATABASE_SERVICE_ON_NED_BOX_AND_JOBS_ON_BOTH_MACHINES_INSTALL_FROM_THE_MAC_COMMAND = (
    "python3 ~/Projects/nedschorus/nc-systems/nc-shared-database/"
    "nc-shared-database-service-on-ned-box-and-jobs-on-both-machines-install-from-the-mac.py")
NC_SHARED_DATABASE_SERVICE_STATUS_COMMAND_ON_NED_BOX = (
    "systemctl --user status nc-shared-database-service")


def _not_reached(method, url, what_happened, sent_event=None):
    """sent_event is the event when it was sent and no answer came, so the service may
    have stored it."""
    if sent_event is None:
        outcome, outcome_for_user = "so nothing was recorded or read", "nothing was recorded"
    else:
        outcome = (f"after the event was sent, so the service may still store it: event ID "
                   f"{sent_event.get('event_id')}. The service stores an event ID once, but a "
                   f"program run again sends its event under a new event ID, so before running "
                   f"the step again, check whether the service holds the event")
        outcome_for_user = (f"the {sent_event.get('operation')} event, ID "
                            f"{sent_event.get('event_id')}, was sent and may have been recorded")
    return NcSharedDatabaseServiceCallFailed(
        f"FAILED: the nc-shared-database service on ned-box cannot be reached: "
        f"{method} {url}, a call to the service, "
        f"{what_happened}, {outcome}. The service holds the only record of "
        f"the agent-seats, so a program that needs it stops until ned-box answers.\n"
        f"Check the service: on ned-box run `{NC_SHARED_DATABASE_SERVICE_STATUS_COMMAND_ON_NED_BOX}`; "
        f"on the Mac run `ssh nedlern@ned-box '{NC_SHARED_DATABASE_SERVICE_STATUS_COMMAND_ON_NED_BOX}'`.\n"
        f"Then tell the user: \"The nc-shared-database service on ned-box did not answer "
        f"{method} {url} ({what_happened}); {outcome_for_user}. The check of the service "
        f"printed: <the first lines the check printed, or ssh's error>.\" Do not record or read "
        f"the agent-seat records another way, such as from files, and do not call again in a "
        f"loop: leave the step that needs the service until ned-box answers, and go on with work "
        f"that does not need ned-box.\n"
        f"{SUBAGENT_PASSES_IT_TO_DISPATCHING_AGENT_LINE}",
        service_answered=False)


def _refused(method, url, status, answer, token_file, body):
    if status == 401:
        return NcSharedDatabaseServiceCallFailed(
            f"FAILED: the nc-shared-database service on ned-box refused {method} {url} with "
            f"401, and recorded and read nothing: {answer}. The service answers only a request "
            f"whose token is one line of its accepted-tokens file, "
            f"{NC_SHARED_DATABASE_SERVICE_ACCEPTED_TOKENS_FILE_ON_NED_BOX} on ned-box, and this "
            f"machine sent the token in {token_file}.\n"
            f"If you are on the Mac: run `{NC_SHARED_DATABASE_SERVICE_ON_NED_BOX_AND_JOBS_ON_BOTH_MACHINES_INSTALL_FROM_THE_MAC_COMMAND}` "
            f"once, which writes both machines' tokens into that file. If it stops with an error, "
            f"follow what it prints and run it again; once it finishes without an error, run "
            f"again the step whose call to the service failed.\n"
            f"If you are on ned-box: tell the user: \"The nc-shared-database service on ned-box "
            f"refuses ned-box's token in {token_file}. Running "
            f"`{NC_SHARED_DATABASE_SERVICE_ON_NED_BOX_AND_JOBS_ON_BOTH_MACHINES_INSTALL_FROM_THE_MAC_COMMAND}` in a Terminal on the Mac "
            f"puts it into the service's accepted-tokens file.\" Then leave the step that needs "
            f"the service until he has run the installer, and go on with work that does not "
            f"need the service.\n"
            f"{SUBAGENT_PASSES_IT_TO_DISPATCHING_AGENT_LINE}",
            service_answered=True)
    sent = f" the event {json.dumps(body)}" if body is not None else ""
    return NcSharedDatabaseServiceCallFailed(
        f"FAILED: the nc-shared-database service on ned-box refused {method} {url}{sent}, sent by "
        f"{sys.argv[0] or 'python3 -c'}, with {status}, and stored nothing. The service's answer: "
        f"{answer}. A 400 or 422 means the service could not read the request or found a value "
        f"it does not accept, such as an unknown machine or a seat_id it holds no agent-seat "
        f"for; the same request sent again is refused again until that cause is corrected.\n"
        f"Find the cause from the service's answer, and correct the program that sent the "
        f"request. The docstring of nc-systems/nc-shared-database/nc-shared-database-service.py "
        f"says what each answer means and which keys and fields each operation takes; an event "
        f"about an agent-seat needs that agent-seat's agent-seat-created or agent-seat-seen "
        f"event stored first.",
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
            f"If you are on the Mac: run `{NC_SHARED_DATABASE_SERVICE_ON_NED_BOX_AND_JOBS_ON_BOTH_MACHINES_INSTALL_FROM_THE_MAC_COMMAND}` "
            f"once, which writes the token file. If it stops with an error, follow what it "
            f"prints and run it again; once it finishes without an error, run again the step "
            f"whose call to the service failed.\n"
            f"If you are on ned-box: tell the user: \"The nc-shared-database service cannot be "
            f"called from ned-box: its token file {token_file} cannot be read ({error}). Running "
            f"`{NC_SHARED_DATABASE_SERVICE_ON_NED_BOX_AND_JOBS_ON_BOTH_MACHINES_INSTALL_FROM_THE_MAC_COMMAND}` in a Terminal on the Mac "
            f"writes it.\" Then leave the step that needs the service until he has run the "
            f"installer, and go on with work that does not need the service.\n"
            f"{SUBAGENT_PASSES_IT_TO_DISPATCHING_AGENT_LINE}", service_answered=True)
    address = urllib.parse.urlsplit(url)
    deadline = time.monotonic() + timeout_seconds
    no_answer = f"got no answer within {timeout_seconds} seconds"
    lookup = {}

    def look_up():
        try:
            lookup["addresses"] = socket.getaddrinfo(address.hostname, address.port or 80,
                                                     type=socket.SOCK_STREAM)
        except OSError as error:
            lookup["error"] = error

    # getaddrinfo takes no timeout, so only the name lookup of ned-box.local runs in a
    # thread, abandoned at the limit; the request is sent from this thread, so an
    # abandoned lookup can never send it. A lookup still stalled from an earlier call
    # is not started again, so a caller calling every 30 seconds leaves one thread, not one
    # per call.
    earlier = _name_lookups_not_finished.get(address.hostname)
    if earlier is not None and earlier.is_alive():
        raise _not_reached(method, url, f"did not look up {address.hostname}: its name lookup "
                                        f"started by an earlier call has still not finished")
    looking_up = threading.Thread(target=look_up, daemon=True)
    looking_up.start()
    looking_up.join(timeout_seconds)
    if looking_up.is_alive():
        _name_lookups_not_finished[address.hostname] = looking_up
        raise _not_reached(method, url, f"{no_answer}: the name lookup of {address.hostname} "
                                        f"did not finish")
    if "error" in lookup:
        error = lookup["error"]
        raise _not_reached(method, url, f"failed the name lookup of {address.hostname} "
                                        f"({type(error).__name__}: {error})")
    connection = http.client.HTTPConnection(address.hostname, address.port)
    errors = []
    for family, kind, protocol, _, socket_address in lookup["addresses"]:
        candidate = None
        try:
            candidate = socket.socket(family, kind, protocol)
            candidate.settimeout(max(deadline - time.monotonic(), 0.001))
            candidate.connect(socket_address)
        except OSError as error:
            if candidate is not None:
                candidate.close()
            errors.append(f"{type(error).__name__}: {error}")
            continue
        connection.sock = sock = candidate
        break
    if connection.sock is None:
        raise _not_reached(method, url, f"could not connect ({'; '.join(errors)})")
    selector = (address.path or "/") + (f"?{address.query}" if address.query else "")
    sent_event = None
    try:
        try:
            sock.settimeout(max(deadline - time.monotonic(), 0.001))
            connection.request(
                method, selector, body=None if body is None else json.dumps(body).encode("utf-8"),
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
            # A request cut short is not stored: the service reads the whole body first.
            sent_event = body
            sock.settimeout(max(deadline - time.monotonic(), 0.001))
            response = connection.getresponse()
        except (OSError, http.client.HTTPException) as error:
            # A timeout is an OSError.
            raise _not_reached(method, url, f"{no_answer} ({type(error).__name__}: {error})",
                               sent_event) from None
        try:
            sock.settimeout(max(deadline - time.monotonic(), 0.001))
            answer = response.read()
        except (OSError, http.client.HTTPException) as error:
            answer = None
            unreadable = f"its answer could not be read: {type(error).__name__}: {error}"
    finally:
        connection.close()
    status = response.status
    if 200 <= status < 300:
        if answer is None:
            raise _not_reached(method, url, f"was answered {status}, but {unreadable}",
                               sent_event)
        return json.loads(answer)
    answer = f"<{unreadable}>" if answer is None else answer.decode("utf-8", "replace").strip()
    if status in STATUSES_THE_SERVICE_REFUSES_WITH:
        raise _refused(method, url, status, answer, token_file, body)
    raise _not_reached(method, url, f"was answered {status}: {answer}")


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
    stops, and with the FAILED line when the service refuses the event or this
    machine's token file cannot be read. Returns the service's answer, or None
    after such a FAILED line; never raises
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
