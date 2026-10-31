#!/usr/bin/env python3
"""Tests for the local events file and its sender:
nc-systems/agent-seat-database/agent-seat-database-local-events-file-common.py and
nc-systems/agent-seat-database/agent-seat-database-local-events-file-sender.py.

The cases run the real service on a loopback port, and fake services that give
one fixed answer, and read the local events file back: an event queued and
sent by the sender it starts, the first 412 and a restore's 412, rejected rows,
the answers that stop the sender, an unreachable service, a second sender, a
sender lock file that cannot be opened, a missing token file, the deletion
of sent rows a backup holds, and the stop report a stopped sender leaves for
the next event's writer to print.

Run: python3 nc-systems/agent-seat-database/tests/agent-seat-database-local-events-file-sender-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import io
import json
import signal
import socket
import sys
import sqlite3
import tempfile
import threading
import time
import uuid
from contextlib import redirect_stderr
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DIRECTORY = Path(__file__).resolve().parents[1]


def load(name, file_name):
    spec = importlib.util.spec_from_file_location(name, DIRECTORY / file_name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


service = load("agent_seat_database_service", "agent-seat-database-service.py")
events_file = load("agent_seat_database_local_events_file_common",
                   "agent-seat-database-local-events-file-common.py")
sender = load("agent_seat_database_local_events_file_sender",
              "agent-seat-database-local-events-file-sender.py")

failures = 0


def check(name, condition, detail=None):
    global failures
    if condition:
        print(f"PASS  {name}")
    else:
        failures += 1
        print(f"FAIL  {name}: {detail!r}")


TOKEN = "mac-token"
SEAT_FIELDS = {"seat_name": "merge-lane-2", "seat_directory": "/d", "task_list_name": "t"}


def serve(server):
    server.RequestHandlerClass.log_message = lambda *arguments: None
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{server.server_address[1]}"


def fake_service(status, text):
    """A service that answers every request with one status and body, and counts them."""
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            calls.append(self.rfile.read(int(self.headers["Content-Length"])))
            encoded = text.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    return serve(ThreadingHTTPServer(("127.0.0.1", 0), Handler)), calls


def queue(path, operation="agent-seat-created", fields=None, seat_id=None):
    """Queue one event without starting a sender; return its event ID."""
    event_id = str(uuid.uuid4())
    body = {"event_id": event_id, "machine": "mac", "operation": operation,
            "occurred_at": "2026-10-26T10:00:00+00:00", "seat_id": seat_id or str(uuid.uuid4()),
            "fields": dict(SEAT_FIELDS, seat_name=event_id) if fields is None else fields}
    connection = events_file.open_local_events_file(path)
    connection.execute("INSERT INTO outbox_event (event_id, body, written_at) VALUES (?, ?, ?)",
                       (event_id, json.dumps(body), "now"))
    connection.close()
    return event_id


def local_events_file(name):
    """A local events file in a directory of its own, so each has its own sender lock file."""
    return SCRATCH / name / "agent-seat-events.sqlite"


def rows(path):
    connection = sqlite3.connect(str(path))
    found = connection.execute("SELECT event_id, sent IS NOT NULL, sequence, rejected "
                               "FROM outbox_event ORDER BY row_number").fetchall()
    connection.close()
    return found


def stop_report_text(path):
    report = events_file.local_events_file_sender_stop_report_path(path)
    return report.read_text(encoding="utf-8") if report.exists() else None


def generation_in(path):
    connection = sqlite3.connect(str(path))
    found = connection.execute("SELECT generation_id FROM database_generation_seen").fetchone()[0]
    connection.close()
    return found


class SenderRanTooLong(Exception):
    pass


def stop_a_sender_that_never_stops(signal_number, frame):
    raise SenderRanTooLong()


signal.signal(signal.SIGALRM, stop_a_sender_that_never_stops)


def run_sender(path, url, token_file):
    """Run the sender; a sender that sends the same row for ever fails the case, not the suite's clock."""
    errors = io.StringIO()
    signal.alarm(20)
    try:
        with redirect_stderr(errors):
            code = sender.main(["--local-events-file", str(path), "--service-url", url,
                                "--token-file", str(token_file)])
    except SenderRanTooLong:
        code = "ran for 20 seconds without stopping"
    finally:
        signal.alarm(0)
    return code, errors.getvalue()


with tempfile.TemporaryDirectory() as scratch:
    scratch = SCRATCH = Path(scratch)
    token_file = scratch / "token"
    token_file.write_text(TOKEN + "\n", encoding="utf-8")
    accepted = scratch / "accepted"
    accepted.write_text(TOKEN + "\n", encoding="utf-8")
    database = scratch / "service.sqlite3"
    url = serve(service.make_server(database, accepted, "127.0.0.1", 0))
    service_db = sqlite3.connect(str(database), isolation_level=None)

    def service_generation():
        return service_db.execute("SELECT generation_id FROM database_generation").fetchone()[0]

    check("this machine is named as the service names it",
          events_file.THIS_MACHINE == ("mac" if sys.platform == "darwin" else "ned-box"),
          events_file.THIS_MACHINE)

    # The local events file
    fresh = scratch / "made" / "here" / "events.sqlite"
    connection = events_file.open_local_events_file(fresh)
    check("a new local events file is made in WAL mode with its four tables, and the "
          "generation seen is null",
          connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
          and {row[0] for row in connection.execute(
              "SELECT name FROM sqlite_master WHERE type = 'table'")}
          == {"outbox_event", "agent_seat", "database_generation_seen", "page_shown"}
          and connection.execute("SELECT * FROM database_generation_seen").fetchall() == [(None,)])
    connection.close()
    events_file.open_local_events_file(fresh).close()
    check("opening the file again keeps one generation row",
          sqlite3.connect(str(fresh)).execute(
              "SELECT count(*) FROM database_generation_seen").fetchone()[0] == 1)
    check("the sender's lock file is the second file beside the local events file",
          events_file.local_events_file_sender_lock_file_path(fresh)
          == fresh.with_name("agent-seat-events-sender.sqlite"))

    # Queued, then sent by the sender the writer starts; the first answer is 412.
    outbox = local_events_file("outbox")
    seat = str(uuid.uuid4())
    event_id = events_file.write_event_to_local_events_file_and_start_sender(
        "agent-seat-created", seat, SEAT_FIELDS, local_events_file=outbox,
        sender_arguments=("--service-url", url, "--token-file", str(token_file)))
    stored = None
    for _ in range(100):
        stored = service_db.execute("SELECT body FROM event WHERE event_id = ?",
                                    (event_id,)).fetchone()
        if stored and rows(outbox)[0][1]:
            break
        time.sleep(0.1)
    body = json.loads(stored[0]) if stored else None
    check("the writer queues the event with this machine, the operation, the seat ID and the "
          "fields, and the sender it starts delivers it",
          body is not None and body["machine"] == events_file.THIS_MACHINE
          and body["operation"] == "agent-seat-created" and body["seat_id"] == seat
          and body["fields"] == SEAT_FIELDS, body)
    check("after the first answer, 412, the file holds the service's generation ID and the "
          "row its sequence number",
          generation_in(outbox) == service_generation() and rows(outbox) == [(event_id, 1, 1, None)],
          (generation_in(outbox), rows(outbox)))

    # Oldest first, in one pass
    later = [queue(outbox) for _ in range(3)]
    code, errors = run_sender(outbox, url, token_file)
    check("the sender sends every queued row, oldest first, and exits 0",
          code == 0 and [row[2] for row in rows(outbox)] == [1, 2, 3, 4], (code, errors, rows(outbox)))
    code, errors = run_sender(outbox, url, token_file)
    check("a sender with an empty queue exits 0 and sends nothing",
          code == 0 and service_db.execute("SELECT count(*) FROM event").fetchone()[0] == 4,
          (code, errors))

    # A restore: the service's generation ID changes
    service_db.execute("UPDATE database_generation SET generation_id = 'restored'")
    service_db.execute("DELETE FROM event WHERE sequence > 2")
    service_db.execute("DELETE FROM sqlite_sequence")
    service_db.execute("INSERT INTO sqlite_sequence VALUES ('event', 2)")
    newest = queue(outbox)
    code, errors = run_sender(outbox, url, token_file)
    check("after a restore the 412 queues every sent row again; rows the copy holds get their "
          "old numbers and rows it lacks new ones, in the order written",
          code == 0 and generation_in(outbox) == "restored"
          and [row[2] for row in rows(outbox)] == [1, 2, 3, 4, 5]
          and rows(outbox)[-1][0] == newest, (code, errors, rows(outbox)))

    # Deletion of sent rows the newest backup holds
    service_db.execute("INSERT INTO newest_backup VALUES ('zz-another-generation', 99)")
    queue(outbox)
    run_sender(outbox, url, token_file)
    check("no sent row is deleted while the newest backup's generation ID differs from the file's",
          len(rows(outbox)) == 6, rows(outbox))
    service_db.execute("UPDATE newest_backup SET generation_id = 'restored', highest_sequence = 4")
    queue(outbox)
    run_sender(outbox, url, token_file)
    check("sent rows at or below the newest backup's highest sequence number are deleted, the "
          "rest kept",
          [row[2] for row in rows(outbox)] == [5, 6, 7], rows(outbox))
    service_db.execute("DELETE FROM newest_backup")
    queue(outbox)
    run_sender(outbox, url, token_file)
    check("no sent row is deleted before the first backup", len(rows(outbox)) == 4, rows(outbox))

    # 400 and 422: rejected, and sending goes on
    rejected_file = local_events_file("rejected")
    unknown_seat = queue(rejected_file, "agent-seat-paused", {})
    good = queue(rejected_file)
    code, errors = run_sender(rejected_file, url, token_file)
    found = rows(rejected_file)
    rejection = json.loads(found[0][3]) if found[0][3] else {}
    check("a 422 fills the row's rejected column with the answer and the time, and the next "
          "row is sent",
          code == 0 and found[0][0] == unknown_seat and not found[0][1]
          and rejection.get("status") == 422 and "no agent-seat" in rejection.get("answer", "")
          and rejection.get("at") and found[1][0] == good and found[1][1], (code, errors, found))
    connection = events_file.open_local_events_file(rejected_file)
    connection.execute("INSERT INTO outbox_event (event_id, body, written_at) "
                       "VALUES ('raw', '[1]', 'now')")
    connection.close()
    code, errors = run_sender(rejected_file, url, token_file)
    check("a 400 rejects the row too", code == 0
          and json.loads(rows(rejected_file)[2][3])["status"] == 400, (code, rows(rejected_file)))

    # Answers that stop the sender
    for status, text, name in (
            (409, '{"error": "unknown operation"}', "409"),
            (401, '{"error": "no accepted token"}', "401"),
            (500, "boom", "500"),
            (200, "not json", "a 200 that is not JSON"),
            (200, '{"sequence": 1}', "a 200 without the generation ID and newest backup"),
            (412, "{}", "a 412 without a generation ID")):
        stopped_file = local_events_file(f"stopped-{uuid.uuid4()}")
        first, second = queue(stopped_file), queue(stopped_file)
        fake_url, calls = fake_service(status, text)
        code, errors = run_sender(stopped_file, fake_url, token_file)
        check(f"{name}: the sender stops with exit 1, the row stays queued and no later row is sent",
              code == 1 and len(calls) == 1 and json.loads(calls[0])["event_id"] == first
              and rows(stopped_file) == [(first, 0, None, None), (second, 0, None, None)]
              and f"answer {status}" in errors and text in errors, (code, errors, calls))
        check(f"{name}: the stop report beside the local events file holds the same reason",
              stop_report_text(stopped_file) == errors, (stop_report_text(stopped_file), errors))
    check("the 409 stop names the row and the service's answer", "queued row 1" in errors, errors)

    # The stop report reaches the next event's writer, and goes once the queue empties
    printed = io.StringIO()
    with redirect_stderr(printed):
        events_file.write_event_to_local_events_file_and_start_sender(
            "agent-seat-created", str(uuid.uuid4()), SEAT_FIELDS, local_events_file=stopped_file,
            sender_arguments=("--service-url", url, "--token-file", str(scratch / "no-token")))
    check("the next event's writer prints the stop report an automatically started sender left",
          "not reaching the agent-seat database service" in printed.getvalue()
          and "answer 412" in printed.getvalue(), printed.getvalue())
    # The sender the writer started finds no token and rewrites the report;
    # waiting for that keeps it from racing the sender run below.
    for _ in range(100):
        if "not run" in (stop_report_text(stopped_file) or ""):
            break
        time.sleep(0.1)
    check("the sender the writer starts writes its own stop to the report",
          "not run" in (stop_report_text(stopped_file) or ""), stop_report_text(stopped_file))
    code, errors = run_sender(stopped_file, url, token_file)
    check("a sender that empties the queue deletes the stop report",
          code == 0 and stop_report_text(stopped_file) is None, (code, errors))
    printed = io.StringIO()
    with redirect_stderr(printed):
        events_file.write_event_to_local_events_file_and_start_sender(
            "agent-seat-created", str(uuid.uuid4()), SEAT_FIELDS, local_events_file=stopped_file,
            sender_arguments=("--service-url", url, "--token-file", str(token_file)))
    check("(control) with no stop report the writer prints nothing", printed.getvalue() == "",
          printed.getvalue())

    # An unreachable service
    closed = socket.socket()
    closed.bind(("127.0.0.1", 0))
    closed_port = closed.getsockname()[1]
    closed.close()
    unreachable_file = local_events_file("unreachable")
    waiting = queue(unreachable_file)
    code, errors = run_sender(unreachable_file, f"http://127.0.0.1:{closed_port}", token_file)
    check("an unreachable service: exit 1, the row stays queued, and the reason says no answer",
          code == 1 and rows(unreachable_file) == [(waiting, 0, None, None)]
          and "no answer" in errors, (code, errors))

    # A service that does not answer within 2 seconds
    silent = socket.socket()
    silent.bind(("127.0.0.1", 0))
    silent.listen(1)
    started = time.monotonic()
    code, errors = run_sender(unreachable_file, f"http://127.0.0.1:{silent.getsockname()[1]}",
                              token_file)
    waited = time.monotonic() - started
    silent.close()
    check("a service that does not answer: the sender waits about 2 seconds, then stops with "
          "the row queued", code == 1 and 1.5 < waited < 10 and "no answer" in errors
          and rows(unreachable_file) == [(waiting, 0, None, None)], (code, waited, errors))

    # One sender at a time
    held_file = local_events_file("held")
    held_row = queue(held_file)
    holder = sqlite3.connect(str(events_file.local_events_file_sender_lock_file_path(held_file)),
                             timeout=0, isolation_level=None)
    holder.execute("BEGIN EXCLUSIVE")
    code, errors = run_sender(held_file, url, token_file)
    check("a sender that cannot take the transaction exits 0 at once and sends nothing",
          code == 0 and rows(held_file) == [(held_row, 0, None, None)] and errors == "",
          (code, errors))
    report = events_file.local_events_file_sender_stop_report_path(held_file)
    report.write_text("the holder's reason\n", encoding="utf-8")
    run_sender(held_file, url, token_file)
    check("a sender that cannot take the transaction leaves the holder's stop report alone",
          stop_report_text(held_file) == "the holder's reason\n", stop_report_text(held_file))
    holder.execute("ROLLBACK")
    code, errors = run_sender(held_file, url, token_file)
    check("once the transaction is free, the next sender sends the row",
          code == 0 and rows(held_file)[0][1] == 1, (code, errors))

    broken_lock_file = local_events_file("broken_lock")
    queue(broken_lock_file)
    events_file.local_events_file_sender_lock_file_path(broken_lock_file).mkdir()
    try:
        run_sender(broken_lock_file, url, token_file)
        raised = None
    except sqlite3.OperationalError as error:
        raised = str(error)
    check("a lock file SQLite cannot open is an error, not taken for another sender",
          raised is not None and "locked" not in raised, raised)
    check("an error that ends the sender is written to the stop report, traceback included",
          "Traceback" in (stop_report_text(broken_lock_file) or "")
          and raised in stop_report_text(broken_lock_file), stop_report_text(broken_lock_file))

    # The token file
    code, errors = run_sender(held_file, url, scratch / "no-token")
    check("a missing token file: exit 2, naming the file and the accepted-tokens file",
          code == 2 and "no-token" in errors and "accepted-tokens" in errors, (code, errors))
    check("a missing token file is written to the stop report",
          stop_report_text(held_file) == errors, (stop_report_text(held_file), errors))

    # The 412 step and the 2xx write when another program changed the generation meanwhile
    race_file = local_events_file("race")
    race_row = queue(race_file)
    connection = events_file.open_local_events_file(race_file)
    connection.execute("UPDATE database_generation_seen SET generation_id = 'new'")
    sender.record_sent(connection, 1, {"sequence": 9, "generation_id": "ancient",
                                       "newest_backup": None})
    check("an answer under a generation ID the file no longer holds is dropped, and the row "
          "stays queued", rows(race_file) == [(race_row, 0, None, None)], rows(race_file))
    sender.record_sent(connection, 1, {"sequence": 9, "generation_id": "new",
                                       "newest_backup": None})
    events_file.requeue_sent_events_for_new_database_generation_id(connection, "old", "newer")
    check("the 412 step changes nothing while the file no longer holds the old generation ID",
          rows(race_file) == [(race_row, 1, 9, None)] and generation_in(race_file) == "new",
          (rows(race_file), generation_in(race_file)))
    events_file.requeue_sent_events_for_new_database_generation_id(connection, "new", "newer")
    check("the 412 step clears sent and sequence and saves the new generation ID",
          rows(race_file) == [(race_row, 0, None, None)] and generation_in(race_file) == "newer",
          (rows(race_file), generation_in(race_file)))
    connection.execute("DROP TABLE outbox_event")
    for name, step in (
            ("the 412 step", lambda: events_file.requeue_sent_events_for_new_database_generation_id(
                connection, "newer", "newest")),
            ("the 2xx write", lambda: sender.record_sent(
                connection, 1, {"sequence": 1, "generation_id": "newer", "newest_backup": None}))):
        try:
            step()
            raised = None
        except sqlite3.OperationalError as error:
            raised = error
        check(f"{name} rolls back its transaction when a statement fails",
              raised is not None and not connection.in_transaction
              and generation_in(race_file) == "newer", raised)
    connection.close()

raise SystemExit(1 if failures else 0)
