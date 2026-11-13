#!/usr/bin/env python3
"""Tests for nc-systems/nc-shared-database/nc-shared-database-service-call-common.py.

The cases call a fake service on a loopback port that answers each request with
the status the case sets, a listening socket that never answers, and a port
nothing listens on: success, the 400, 401 and 422 refusals, a 422 whose answer
is cut short, a 409 and a 500 counted as no answer, no answer within the time
limit, a name lookup that stalls past it, a refused connection, an unreadable
token file, and the handoff-supervisor's variant, which calls again with the
same event ID, logs once when its wait starts and once when it stops, and does
not call again after a refusal or an unreadable token file. One case records an event in
the real service, nc-shared-database-service.py, to show the event the module
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

    for status in (409, 500):
        fake.statuses = [status]
        failure = failure_of(lambda: caller.nc_shared_database_event_send_single_attempt(
            "agent-seat-paused", "seat-1", {}, **options))
        check(f"{status} counts as no answer: ned-box cannot be reached",
              failure is not None and not failure.service_answered
              and str(failure).startswith("FAILED: ned-box cannot be reached")
              and f"was answered {status}" in str(failure)
              and "Do not record or read the agent-seat records another way" in str(failure),
              failure and str(failure))

    silent = socket.socket()
    silent.bind(("127.0.0.1", 0))
    silent.listen(1)
    failure = failure_of(lambda: caller.nc_shared_database_service_http_request_single_attempt(
        "/agent-seats", service_url=f"http://127.0.0.1:{silent.getsockname()[1]}",
        token_file=token_file, timeout_seconds=0.2))
    silent.close()
    check("no answer within the time limit: ned-box cannot be reached",
          failure is not None and not failure.service_answered
          and "got no answer within 0.2 seconds" in str(failure), failure and str(failure))

    closed = socket.socket()
    closed.bind(("127.0.0.1", 0))
    closed_port = closed.getsockname()[1]
    closed.close()
    failure = failure_of(lambda: caller.nc_shared_database_service_http_request_single_attempt(
        "/agent-seats", service_url=f"http://127.0.0.1:{closed_port}", token_file=token_file))
    check("a refused connection: ned-box cannot be reached",
          failure is not None and not failure.service_answered
          and str(failure).startswith("FAILED: ned-box cannot be reached")
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

    cut_short = socket.socket()
    cut_short.bind(("127.0.0.1", 0))
    cut_short.listen(1)

    def answer_422_and_close_before_the_answer_ends():
        connection, _ = cut_short.accept()
        connection.recv(65536)
        connection.sendall(b"HTTP/1.1 422 Unprocessable Entity\r\nContent-Length: 100\r\n\r\nshort")
        connection.close()

    threading.Thread(target=answer_422_and_close_before_the_answer_ends, daemon=True).start()
    failure = failure_of(lambda: caller.nc_shared_database_event_send_single_attempt(
        "agent-seat-paused", "seat-1", {}, service_url=f"http://127.0.0.1:{cut_short.getsockname()[1]}",
        token_file=token_file))
    cut_short.close()
    check("a 422 whose answer is cut short raises the refusal's FAILED line, saying the answer "
          "could not be read",
          failure is not None and failure.service_answered and "with 422" in str(failure)
          and "its answer could not be read: " in str(failure),
          failure and str(failure))

    real_getaddrinfo = socket.getaddrinfo

    def name_lookup_that_stalls(host, *arguments, **keywords):
        if host == "stalled-name-lookup.invalid":
            time.sleep(3)
        return real_getaddrinfo(host, *arguments, **keywords)

    socket.getaddrinfo = name_lookup_that_stalls
    started = time.monotonic()
    failure = failure_of(lambda: caller.nc_shared_database_service_http_request_single_attempt(
        "/agent-seats", service_url="http://stalled-name-lookup.invalid:8765",
        token_file=token_file, timeout_seconds=0.2))
    took = time.monotonic() - started
    socket.getaddrinfo = real_getaddrinfo
    check("a stalled name lookup ends the call at the time limit: ned-box cannot be reached",
          failure is not None and not failure.service_answered and took < 1
          and "got no answer within 0.2 seconds" in str(failure), (took, failure and str(failure)))

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
