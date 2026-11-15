#!/usr/bin/env python3
"""Tests for nc-systems/nc-shared-database/nc-shared-database-service-call-common.py.

The cases call a fake service on a loopback port that answers each request with
the status the case sets, a listening socket that never answers, and a port
nothing listens on: success, the 400, 401 and 422 refusals, a 422 whose answer
is cut short or still being read at the time limit, a 404, a 500 and a 200 cut
short counted as no answer, no answer within the time limit to a read and to an
event, a name lookup that ends after the limit or fails, a refused connection,
an unreadable token file, and the handoff-supervisor's variant, which calls
again with the same event ID, logs once when its wait starts and once when it
stops, and does not call again after a refusal or an unreadable token file. One
case records an event in the real service, nc-shared-database-service.py, to show the event the module
builds is one the service stores.

Run: python3 nc-systems/nc-shared-database/tests/nc-shared-database-service-call-common-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import json
import socket
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DIRECTORY = Path(__file__).resolve().parents[1]


def load(name, file_name):
    spec = importlib.util.spec_from_file_location(name, DIRECTORY / file_name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


caller = load("nc_shared_database_service_call_common", "nc-shared-database-service-call-common.py")
service = load("nc_shared_database_service", "nc-shared-database-service.py")

failures = 0


def check(name, condition, detail=None):
    global failures
    if condition:
        print(f"PASS  {name}")
    else:
        failures += 1
        print(f"FAIL  {name}: {detail!r}")


class FakeService:
    """Answers each request with the first of self.statuses, which it then drops unless it
    is the last, and keeps every request it got."""

    def __init__(self):
        self.statuses = [200]
        self.requests = []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *arguments):
                pass

            def answer(self, body):
                fake.requests.append({"method": self.command, "path": self.path,
                                      "authorization": self.headers.get("Authorization"),
                                      "body": json.loads(body) if body else None})
                status = fake.statuses.pop(0) if len(fake.statuses) > 1 else fake.statuses[0]
                encoded = json.dumps({"sequence": 7} if status == 200
                                     else {"error": f"answer {status}"}).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def do_GET(self):
                self.answer(None)

            def do_POST(self):
                self.answer(self.rfile.read(int(self.headers.get("Content-Length") or 0)))

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"


def failure_of(call):
    try:
        call()
    except caller.NcSharedDatabaseServiceCallFailed as failure:
        return failure
    return None


with tempfile.TemporaryDirectory() as scratch:
    scratch = Path(scratch)
    token_file = scratch / "nc-shared-database-service.token"
    token_file.write_text("mac-token\n", encoding="utf-8")
    fake = FakeService()
    options = {"service_url": fake.url, "token_file": token_file}

    answer = caller.nc_shared_database_event_send_single_attempt(
        "agent-seat-paused", "seat-1", {}, **options)
    sent = fake.requests[-1]
    check("a success returns the service's answer", answer == {"sequence": 7}, answer)
    check("an event is a POST to /events with this machine's token as a Bearer token",
          sent["method"] == "POST" and sent["path"] == "/events"
          and sent["authorization"] == "Bearer mac-token", sent)
    check("the event carries a new event ID, this machine, the operation, its own time, the "
          "seat ID and the fields",
          set(sent["body"]) == service.EVENT_KEYS and sent["body"]["event_id"]
          and sent["body"]["machine"] == caller.THIS_MACHINE
          and sent["body"]["operation"] == "agent-seat-paused"
          and sent["body"]["seat_id"] == "seat-1" and sent["body"]["fields"] == {}, sent)
    answer = caller.nc_shared_database_service_http_request_single_attempt("/agent-seats", **options)
    check("a read is a GET of the path given", fake.requests[-1]["method"] == "GET"
          and fake.requests[-1]["path"] == "/agent-seats" and answer == {"sequence": 7},
          fake.requests[-1])

    for status in (400, 422):
        fake.statuses = [status]
        failure = failure_of(lambda: caller.nc_shared_database_event_send_single_attempt(
            "agent-seat-paused", "seat-1", {}, **options))
        check(f"{status} raises a FAILED line with the service's answer, as a refusal",
              failure is not None and failure.service_answered
              and str(failure).startswith(f"FAILED: the nc-shared-database service on ned-box "
                                          f"refused POST {fake.url}/events the event ")
              and f"with {status}, and stored nothing" in str(failure)
              and f"answer {status}" in str(failure) and "correct the program that sent" in str(failure)
              and '"operation": "agent-seat-paused"' in str(failure),
              failure and str(failure))

    fake.statuses = [401]
    failure = failure_of(lambda: caller.nc_shared_database_event_send_single_attempt(
        "agent-seat-paused", "seat-1", {}, **options))
    check("401 names this machine's token file and ned-box's accepted-tokens file, and says the "
          "token must be one line of it",
          failure is not None and failure.service_answered and str(token_file) in str(failure)
          and caller.NC_SHARED_DATABASE_SERVICE_ACCEPTED_TOKENS_FILE_ON_NED_BOX in str(failure)
          and "one line of its accepted-tokens file" in str(failure)
          and caller.NC_SHARED_DATABASE_SERVICE_ON_NED_BOX_AND_JOBS_ON_BOTH_MACHINES_INSTALL_FROM_THE_MAC_COMMAND in str(failure),
          failure and str(failure))

    for status in (404, 500):
        fake.statuses = [status]
        failure = failure_of(lambda: caller.nc_shared_database_event_send_single_attempt(
            "agent-seat-paused", "seat-1", {}, **options))
        check(f"{status} counts as no answer: ned-box cannot be reached",
              failure is not None and not failure.service_answered
              and str(failure).startswith("FAILED: the nc-shared-database service on ned-box cannot be reached")
              and f"was answered {status}" in str(failure)
              and "Do not record or read the agent-seat records another way" in str(failure),
              failure and str(failure))

    silent = socket.socket()
    silent.bind(("127.0.0.1", 0))
    silent.listen(1)
    failure = failure_of(lambda: caller.nc_shared_database_service_http_request_single_attempt(
        "/agent-seats", service_url=f"http://127.0.0.1:{silent.getsockname()[1]}",
        token_file=token_file, timeout_seconds=0.2))
    check("no answer within the time limit: ned-box cannot be reached",
          failure is not None and not failure.service_answered
          and "got no answer within 0.2 seconds" in str(failure)
          and "so nothing was recorded or read" in str(failure), failure and str(failure))
    failure = failure_of(lambda: caller.nc_shared_database_event_send_single_attempt(
        "agent-seat-paused", "seat-1", {}, service_url=f"http://127.0.0.1:{silent.getsockname()[1]}",
        token_file=token_file, timeout_seconds=0.2))
    silent.close()
    check("an event sent with no answer within the time limit may still be stored, and the "
          "FAILED line says so, with its event ID",
          failure is not None and not failure.service_answered
          and "got no answer within 0.2 seconds" in str(failure)
          and "after the event was sent, so the service may still store it: event ID "
          in str(failure) and "nothing was recorded" not in str(failure)
          and "was sent and may have been recorded" in str(failure), failure and str(failure))

    closed = socket.socket()
    closed.bind(("127.0.0.1", 0))
    closed_port = closed.getsockname()[1]
    closed.close()
    failure = failure_of(lambda: caller.nc_shared_database_service_http_request_single_attempt(
        "/agent-seats", service_url=f"http://127.0.0.1:{closed_port}", token_file=token_file))
    check("a refused connection: ned-box cannot be reached",
          failure is not None and not failure.service_answered
          and str(failure).startswith("FAILED: the nc-shared-database service on ned-box cannot be reached")
          and caller.NC_SHARED_DATABASE_SERVICE_STATUS_COMMAND_ON_NED_BOX in str(failure),
          failure and str(failure))

    requests_before = len(fake.requests)
    failure = failure_of(lambda: caller.nc_shared_database_service_http_request_single_attempt(
        "/agent-seats", service_url=fake.url, token_file=scratch / "no-such.token"))
    check("an unreadable token file sends nothing and raises a FAILED line naming the file",
          failure is not None and failure.service_answered
          and len(fake.requests) == requests_before
          and str(scratch / "no-such.token") in str(failure)
          and str(failure).startswith("FAILED: GET"), failure and str(failure))

    def answers_once(raw_answer, then_wait_seconds=0):
        """A service URL whose one connection gets raw_answer, which may end short of its
        Content-Length, and is closed then_wait_seconds later."""
        listening = socket.socket()
        listening.bind(("127.0.0.1", 0))
        listening.listen(1)

        def answer():
            connection, _ = listening.accept()
            connection.recv(65536)
            connection.sendall(raw_answer)
            time.sleep(then_wait_seconds)
            connection.close()
            listening.close()

        threading.Thread(target=answer, daemon=True).start()
        return f"http://127.0.0.1:{listening.getsockname()[1]}"

    failure = failure_of(lambda: caller.nc_shared_database_event_send_single_attempt(
        "agent-seat-paused", "seat-1", {}, token_file=token_file, service_url=answers_once(
            b"HTTP/1.1 422 Unprocessable Entity\r\nContent-Length: 100\r\n\r\nshort")))
    check("a 422 whose answer is cut short raises the refusal's FAILED line, saying the answer "
          "could not be read",
          failure is not None and failure.service_answered and "with 422" in str(failure)
          and "its answer could not be read: " in str(failure),
          failure and str(failure))

    failure = failure_of(lambda: caller.nc_shared_database_event_send_single_attempt(
        "agent-seat-paused", "seat-1", {}, token_file=token_file, timeout_seconds=0.2,
        service_url=answers_once(b"HTTP/1.1 422 Unprocessable Entity\r\nContent-Length: 100"
                                 b"\r\n\r\nshort", then_wait_seconds=1)))
    check("a 422 whose answer is still being read at the time limit raises the refusal's FAILED "
          "line, so the retrying variant does not send the event again",
          failure is not None and failure.service_answered and "with 422" in str(failure)
          and "its answer could not be read: " in str(failure),
          failure and str(failure))

    failure = failure_of(lambda: caller.nc_shared_database_event_send_single_attempt(
        "agent-seat-paused", "seat-1", {}, token_file=token_file,
        service_url=answers_once(b"HTTP/1.1 200 OK\r\nContent-Length: 100\r\n\r\nshort")))
    check("a 200 whose answer is cut short counts as no answer, and says the event may be stored",
          failure is not None and not failure.service_answered
          and "was answered 200, but its answer could not be read: " in str(failure)
          and "the service may still store it" in str(failure), failure and str(failure))

    real_getaddrinfo = socket.getaddrinfo
    looked_up = []

    def name_lookup_that_stalls_then_finds_the_fake(host, port, *arguments, **keywords):
        looked_up.append(host)
        if host == "stalled-name-lookup.invalid":
            time.sleep(0.5)
            return real_getaddrinfo("127.0.0.1", fake.server.server_address[1], *arguments,
                                    **keywords)
        if host == "unknown-name.invalid":
            raise socket.gaierror(socket.EAI_NONAME, "Name or service not known")
        if host == "stalled-twice.invalid":
            time.sleep(0.6)
            raise socket.gaierror(socket.EAI_NONAME, "Name or service not known")
        if host == "ipv6-first.invalid":
            found = real_getaddrinfo("127.0.0.1", fake.server.server_address[1], *arguments,
                                     **keywords)
            return [(socket.AF_INET6, socket.SOCK_STREAM, 6, "",
                     ("::1", fake.server.server_address[1], 0, 0))] + found
        return real_getaddrinfo(host, port, *arguments, **keywords)

    socket.getaddrinfo = name_lookup_that_stalls_then_finds_the_fake
    try:
        requests_before = len(fake.requests)
        started = time.monotonic()
        failure = failure_of(lambda: caller.nc_shared_database_event_send_single_attempt(
            "agent-seat-paused", "seat-1", {}, service_url="http://stalled-name-lookup.invalid:8765",
            token_file=token_file, timeout_seconds=0.2))
        took = time.monotonic() - started
        time.sleep(1)
        check("a name lookup that ends after the time limit ends the call at the limit, and the "
              "event is never sent: ned-box cannot be reached, nothing was recorded",
              failure is not None and not failure.service_answered and took < 0.5
              and len(fake.requests) == requests_before
              and "got no answer within 0.2 seconds: the name lookup of "
                  "stalled-name-lookup.invalid did not finish" in str(failure)
              and "so nothing was recorded or read" in str(failure),
              (took, fake.requests[requests_before:], failure and str(failure)))

        looked_up.clear()
        fake.statuses = [200]
        answer = caller.nc_shared_database_service_http_request_single_attempt(
            "/agent-seats", service_url=fake.url.replace("127.0.0.1", "localhost"),
            token_file=token_file)
        check("a call looks its host name up once, within the time limit",
              answer == {"sequence": 7} and looked_up == ["localhost"], (answer, looked_up))

        failure = failure_of(lambda: caller.nc_shared_database_service_http_request_single_attempt(
            "/agent-seats", service_url="http://unknown-name.invalid:8765", token_file=token_file))
        check("a failed name lookup: ned-box cannot be reached",
              failure is not None and not failure.service_answered
              and "failed the name lookup of unknown-name.invalid (gaierror: " in str(failure),
              failure and str(failure))

        looked_up.clear()
        first = failure_of(lambda: caller.nc_shared_database_service_http_request_single_attempt(
            "/agent-seats", service_url="http://stalled-twice.invalid:8765", token_file=token_file,
            timeout_seconds=0.2))
        second = failure_of(lambda: caller.nc_shared_database_service_http_request_single_attempt(
            "/agent-seats", service_url="http://stalled-twice.invalid:8765", token_file=token_file,
            timeout_seconds=0.2))
        check("while an earlier call's name lookup is still stalled, a call starts no other "
              "lookup and says why",
              first is not None and second is not None and not second.service_answered
              and looked_up == ["stalled-twice.invalid"]
              and "did not look up stalled-twice.invalid: its name lookup started by an earlier "
                  "call has still not finished" in str(second),
              (looked_up, second and str(second)))
        time.sleep(1)
        looked_up.clear()
        third = failure_of(lambda: caller.nc_shared_database_service_http_request_single_attempt(
            "/agent-seats", service_url="http://stalled-twice.invalid:8765", token_file=token_file,
            timeout_seconds=0.2))
        check("once the stalled lookup has finished, the next call looks the name up again",
              looked_up == ["stalled-twice.invalid"] and third is not None
              and "did not look up" not in str(third), (looked_up, third and str(third)))
        time.sleep(1)

        real_socket = socket.socket

        def socket_that_cannot_open_ipv6(family=socket.AF_INET, *arguments, **keywords):
            if family == socket.AF_INET6:
                raise OSError(97, "Address family not supported by protocol")
            return real_socket(family, *arguments, **keywords)

        socket.socket = socket_that_cannot_open_ipv6
        try:
            fake.statuses = [200]
            answer = caller.nc_shared_database_service_http_request_single_attempt(
                "/agent-seats", service_url="http://ipv6-first.invalid:8765", token_file=token_file)
        except caller.NcSharedDatabaseServiceCallFailed as failure:
            answer = str(failure)
        except OSError as error:
            answer = f"raw {type(error).__name__}: {error}"
        finally:
            socket.socket = real_socket
        check("an address whose family this machine cannot open is skipped, and the next address "
              "is tried", answer == {"sequence": 7}, answer)
    finally:
        socket.getaddrinfo = real_getaddrinfo

    # The handoff-supervisor's variant
    logged, slept = [], []
    fake.statuses = [500, 500, 200]
    requests_before = len(fake.requests)
    answer = caller.nc_shared_database_event_send_retrying_every_30_seconds_until_service_answers(
        "handoff-supervisor-ended", "seat-1", {"run_id": "run-1"}, logged.append,
        sleep=slept.append, **options)
    calls = fake.requests[requests_before:]
    check("while ned-box cannot be reached, the variant calls again after 30 seconds with the "
          "same event ID until the service answers",
          answer == {"sequence": 7} and len(calls) == 3 and slept == [30, 30]
          and len({call["body"]["event_id"] for call in calls}) == 1, (answer, calls, slept))
    check("the variant logs once when its wait starts and once when it stops",
          len(logged) == 2 and logged[0].startswith("waiting for ned-box to record "
                                                    "handoff-supervisor-ended event")
          and logged[1].startswith("ned-box answered again"), logged)

    logged, slept = [], []
    fake.statuses = [200]
    caller.nc_shared_database_event_send_retrying_every_30_seconds_until_service_answers(
        "handoff-supervisor-ended", "seat-1", {"run_id": "run-1"}, logged.append,
        sleep=slept.append, **options)
    check("an event answered at once logs nothing and waits for nothing",
          logged == [] and slept == [], (logged, slept))

    logged, slept = [], []
    fake.statuses = [422]
    requests_before = len(fake.requests)
    answer = caller.nc_shared_database_event_send_retrying_every_30_seconds_until_service_answers(
        "handoff-supervisor-ended", "seat-1", {"run_id": "run-1"}, logged.append,
        sleep=slept.append, **options)
    check("a refusal is logged as its FAILED line, returns None and is not sent again",
          answer is None and len(fake.requests) == requests_before + 1 and slept == []
          and len(logged) == 1 and logged[0].startswith("FAILED: the nc-shared-database "
                                                        "service on ned-box refused"),
          (answer, logged))

    logged, slept = [], []
    fake.statuses = [500, 400]
    answer = caller.nc_shared_database_event_send_retrying_every_30_seconds_until_service_answers(
        "handoff-supervisor-ended", "seat-1", {"run_id": "run-1"}, logged.append,
        sleep=slept.append, **options)
    check("a refusal after a wait logs the wait's start, its end and the FAILED line",
          answer is None and slept == [30] and len(logged) == 3
          and logged[0].startswith("waiting for ned-box") and logged[1].startswith("ned-box "
                                                                                   "answered again")
          and logged[2].startswith("FAILED"), logged)

    logged, slept = [], []
    requests_before = len(fake.requests)
    answer = caller.nc_shared_database_event_send_retrying_every_30_seconds_until_service_answers(
        "handoff-supervisor-ended", "seat-1", {"run_id": "run-1"}, logged.append,
        sleep=slept.append, service_url=fake.url, token_file=scratch / "no-such.token")
    check("an unreadable token file is logged as its FAILED line, returns None and sends nothing",
          answer is None and len(fake.requests) == requests_before and slept == []
          and len(logged) == 1 and logged[0].startswith("FAILED: POST"), (answer, logged))

    database = scratch / "nc-shared-database.sqlite3"
    tokens = scratch / "accepted-tokens"
    tokens.write_text("mac-token\n", encoding="utf-8")
    real = service.make_nc_shared_database_service_http_server(database, tokens, "127.0.0.1", 0)
    real.RequestHandlerClass.log_message = lambda *arguments: None
    threading.Thread(target=real.serve_forever, daemon=True).start()
    real_options = {"service_url": f"http://127.0.0.1:{real.server_address[1]}",
                    "token_file": token_file}
    answer = caller.nc_shared_database_event_send_single_attempt(
        "agent-seat-created", "seat-1", {"seat_name": "merge-lane-2",
                                         "seat_directory": "/home/nedlern/agents/merge-lane-2",
                                         "task_list_name": "nedschorus-merge-lane-2-tasks"},
        **real_options)
    listed = caller.nc_shared_database_service_http_request_single_attempt("/agent-seats",
                                                                            **real_options)
    check("the real service stores an event the module builds, and lists its agent-seat",
          answer == {"sequence": 1}
          and [seat["seat_name"] for seat in listed["agent_seats"]] == ["merge-lane-2"],
          (answer, listed))

raise SystemExit(1 if failures else 0)
