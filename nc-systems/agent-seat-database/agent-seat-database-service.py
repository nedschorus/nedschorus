#!/usr/bin/env python3
"""Keep one record of every agent-seat on both machines, behind a narrow JSON API over HTTP.

Usage:
  nc-systems/agent-seat-database/agent-seat-database-service.py
      [--database PATH] [--accepted-tokens-file PATH] [--host HOST] [--port N]

  --database              default ~/.local/state/nedschorus/agent-seat-database.sqlite3,
                          made with its schema and a new generation ID when absent
  --accepted-tokens-file  default ~/.config/nedschorus/agent-seat-database-service-accepted-tokens,
                          one token per line, read at every request
  --host, --port          default every address, port 8765

On ned-box the systemd user unit agent-seat-database-service.service, beside
this file, runs it. Callers never see the tables: they send named operations.

EVERY REQUEST carries `Authorization: Bearer <token>` and the header
Agent-Seat-Database-Generation-Id, the generation ID the caller's local events
file holds. A token that is no line of the accepted-tokens file is answered 401.
A generation ID that differs from the database's, or none, is answered 412 with
{"generation_id": <the database's>}, and nothing is stored.

  POST /events             store one event; the body is a JSON object with
                           exactly the keys event_id, machine, operation,
                           occurred_at, seat_id (null for machine-booted) and
                           fields, an object with exactly the operation's fields
                           in OPERATION_FIELDS
  GET /agent-seats         list agent-seats; ?machine=mac or ?machine=ned-box
                           lists one machine's
  GET /agent-seats/<id>    one agent-seat, with its handoff-supervisor runs,
                           agent-sessions, session-handoffs and restart attempts

POST /events answers:
  200  {"sequence": N, ...}: stored now, or, for an event ID already held, the
       sequence number it was stored under
  400  the body is not a JSON object, or has no event ID
  422  an unknown machine; an occurred_at or seat_id that is not a string or
       null, or a field that is not a string, a number SQLite can store, true,
       false or null; a seat ID with no agent-seat row; or an agent-seat name
       another agent-seat not retired holds
  409  an unknown operation, or keys or fields other than the operation's; the
       caller leaves the event queued until the service knows the operation
  500  any other error, as {"error": "<its type>: <its message>"}; nothing is
       stored
Every 200 answer also carries "generation_id" and "newest_backup", which is
{"generation_id", "highest_sequence"} of the newest backup that passed its
integrity check, or null before the first.

An agent-seat's state is its events applied in sequence-number order, as each
is stored. An agent-seat stops being parked at its next handoff-supervisor-began,
paused or retired event, and stops being paused at its next
handoff-supervisor-began or retired event; the end clears the column.

Exit codes: 2 a bad invocation; otherwise the program runs until stopped.
"""

import argparse
import json
import os
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

DATABASE_PATH = Path.home() / ".local" / "state" / "nedschorus" / "agent-seat-database.sqlite3"
ACCEPTED_TOKENS_FILE_PATH = (Path.home() / ".config" / "nedschorus"
                             / "agent-seat-database-service-accepted-tokens")
PORT = 8765
GENERATION_HEADER = "Agent-Seat-Database-Generation-Id"
MACHINES = ("mac", "ned-box")
BUSY_TIMEOUT_SECONDS = 5

EVENT_KEYS = {"event_id", "machine", "operation", "occurred_at", "seat_id", "fields"}
OPERATION_FIELDS = {
    "agent-seat-created": {"seat_name", "seat_directory", "task_list_name"},
    "agent-seat-seen": {"seat_name", "seat_directory", "task_list_name"},
    "agent-seat-paused": set(),
    "agent-seat-parked": set(),
    "agent-seat-retired": set(),
    "machine-booted": {"boot_id", "booted_at", "previous_boot", "stop_estimated_at",
                       "stop_estimate_method"},
    "handoff-supervisor-began": {"run_id", "boot_id", "process_id", "process_started_at",
                                 "generation", "restart_attempt_id"},
    "handoff-supervisor-ended": {"run_id"},
    "agent-session-launched": {"session_id", "run_id", "transcript_path", "predecessor_session"},
    "agent-session-ended": {"session_id", "run_id", "exit_code"},
    "session-handoff-written": {"restart_counter", "writer_session", "next_step_text",
                                "dont_restart_reason"},
    "session-handoff-consumed": {"written_event_id", "run_id"},
    "restart-attempted": {"attempt_id", "boot_id", "why_picked", "action", "began_at",
                          "ended_at", "result"},
}
OPERATIONS_THAT_NAME_NO_AGENT_SEAT = {"machine-booted"}
OPERATIONS_THAT_MAY_NAME_A_NEW_AGENT_SEAT = {"agent-seat-created", "agent-seat-seen"}

SCHEMA = """
CREATE TABLE database_generation (generation_id TEXT NOT NULL);
CREATE TABLE newest_backup (generation_id TEXT NOT NULL, highest_sequence INTEGER);
CREATE TABLE event (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    machine TEXT NOT NULL,
    operation TEXT NOT NULL,
    occurred_at TEXT,
    received_at TEXT NOT NULL,
    body TEXT NOT NULL);
CREATE TABLE agent_seat (
    seat_id TEXT PRIMARY KEY,
    machine TEXT NOT NULL,
    seat_name TEXT NOT NULL,
    seat_directory TEXT,
    task_list_name TEXT,
    created_at TEXT,
    paused_at TEXT,
    parked_at TEXT,
    retired_at TEXT);
CREATE UNIQUE INDEX agent_seat_name_among_not_retired ON agent_seat (seat_name)
    WHERE retired_at IS NULL;
CREATE TABLE supervisor_run (
    run_id TEXT PRIMARY KEY,
    seat_id TEXT NOT NULL,
    boot_id TEXT,
    process_id INTEGER,
    process_started_at TEXT,
    generation INTEGER,
    began_at TEXT,
    ended_at TEXT,
    restart_attempt_id TEXT);
CREATE TABLE agent_session (
    machine TEXT NOT NULL,
    session_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    seat_id TEXT NOT NULL,
    transcript_path TEXT,
    predecessor_session TEXT,
    launched_at TEXT,
    ended_at TEXT,
    exit_code INTEGER,
    PRIMARY KEY (machine, session_id, run_id));
CREATE TABLE handoff_event (
    event_id TEXT PRIMARY KEY,
    seat_id TEXT NOT NULL,
    restart_counter INTEGER,
    writer_session TEXT,
    written_at TEXT,
    next_step_text TEXT,
    dont_restart_reason TEXT,
    consumed_by_run TEXT,
    consumed_at TEXT);
CREATE TABLE machine_boot (
    machine TEXT NOT NULL,
    boot_id TEXT NOT NULL,
    booted_at TEXT,
    previous_boot TEXT,
    stop_estimated_at TEXT,
    stop_estimate_method TEXT,
    PRIMARY KEY (machine, boot_id));
CREATE TABLE restart_attempt (
    attempt_id TEXT PRIMARY KEY,
    machine TEXT NOT NULL,
    boot_id TEXT,
    seat_id TEXT NOT NULL,
    why_picked TEXT,
    action TEXT,
    began_at TEXT,
    ended_at TEXT,
    result TEXT);
"""


class Answer(Exception):
    def __init__(self, status, body):
        super().__init__(status)
        self.status = status
        self.body = body


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(database_path):
    connection = sqlite3.connect(str(database_path), timeout=BUSY_TIMEOUT_SECONDS,
                                 isolation_level=None)
    connection.row_factory = sqlite3.Row
    return connection


def create_database_if_absent(database_path):
    database_path = Path(database_path)
    if database_path.exists():
        return
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = connect(database_path)
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("BEGIN IMMEDIATE")
        for statement in SCHEMA.split(";"):
            if statement.strip():
                connection.execute(statement)
        connection.execute("INSERT INTO database_generation VALUES (?)", (str(uuid.uuid4()),))
        connection.execute("COMMIT")
    finally:
        connection.close()


def accepted_tokens(accepted_tokens_path):
    try:
        lines = Path(accepted_tokens_path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return set()
    return {line.strip() for line in lines if line.strip()}


def database_generation(connection):
    return connection.execute("SELECT generation_id FROM database_generation").fetchone()[0]


def answer_footer(connection):
    backup = connection.execute(
        "SELECT generation_id, highest_sequence FROM newest_backup").fetchone()
    return {"generation_id": database_generation(connection),
            "newest_backup": dict(backup) if backup else None}


def parse_event(raw_body):
    try:
        event = json.loads(raw_body)
    except ValueError:
        raise Answer(400, {"error": "the body is not JSON"})
    if not isinstance(event, dict):
        raise Answer(400, {"error": "the body is not a JSON object"})
    if not isinstance(event.get("event_id"), str) or not event["event_id"]:
        raise Answer(400, {"error": "the event has no event_id"})
    return event


def sqlite_can_store(value):
    if isinstance(value, int) and not isinstance(value, bool):
        return -2 ** 63 <= value < 2 ** 63
    return value is None or isinstance(value, (str, float, bool))


def check_event_fits_its_operation(connection, event):
    if event.get("machine") not in MACHINES:
        raise Answer(422, {"error": f"unknown machine {event.get('machine')!r}"})
    operation = event.get("operation")
    if operation not in OPERATION_FIELDS:
        raise Answer(409, {"error": f"unknown operation {operation!r}"})
    fields = event.get("fields")
    if set(event) != EVENT_KEYS or not isinstance(fields, dict) \
            or set(fields) != OPERATION_FIELDS[operation]:
        raise Answer(409, {"error": f"the keys or fields differ from {operation}'s: event keys "
                                    f"{sorted(EVENT_KEYS)}, fields "
                                    f"{sorted(OPERATION_FIELDS[operation])}"})
    wrong = [key for key in ("occurred_at", "seat_id")
             if not (event[key] is None or isinstance(event[key], str))]
    wrong += [f"fields.{name}" for name, value in sorted(fields.items())
              if not sqlite_can_store(value)]
    if wrong:
        raise Answer(422, {"error": f"agent-seat-database-service.py did not store event "
                                    f"{event['event_id']} ({operation}, from {event['machine']}): "
                                    f"the value under each of these keys has a JSON type it "
                                    f"cannot store: {', '.join(wrong)}. occurred_at and seat_id "
                                    f"are each a string or null. Each value in the fields object "
                                    f"is a string, an integer from -2**63 to 2**63-1, a number "
                                    f"with a decimal point, true, false or null, never a list or "
                                    f"an object. agent-seat-database-local-events-file-sender.py "
                                    f"keeps this answer in the event's rejected column of the "
                                    f"outbox_event table in that machine's local events file, "
                                    f"and does not send the event again. Correct the program "
                                    f"that wrote it; a {operation} event written afterwards is "
                                    f"sent as usual."})
    names_no_seat = operation in OPERATIONS_THAT_NAME_NO_AGENT_SEAT
    if names_no_seat != (event["seat_id"] is None):
        raise Answer(409, {"error": f"{operation} takes "
                                    f"{'no' if names_no_seat else 'a'} seat_id"})
    if not names_no_seat and operation not in OPERATIONS_THAT_MAY_NAME_A_NEW_AGENT_SEAT \
            and connection.execute("SELECT 1 FROM agent_seat WHERE seat_id = ?",
                                   (event["seat_id"],)).fetchone() is None:
        raise Answer(422, {"error": f"no agent-seat has seat_id {event['seat_id']!r}"})


def apply_event(connection, event):
    """Bring the state tables up to date with one event, in the caller's transaction."""
    operation, seat_id, fields = event["operation"], event["seat_id"], event["fields"]
    at, machine = event["occurred_at"], event["machine"]
    execute = connection.execute
    if operation in ("agent-seat-created", "agent-seat-seen"):
        execute("INSERT INTO agent_seat (seat_id, machine, seat_name, seat_directory, "
                "task_list_name, created_at) VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (seat_id) DO UPDATE SET machine = excluded.machine, "
                "seat_name = excluded.seat_name, seat_directory = excluded.seat_directory, "
                "task_list_name = excluded.task_list_name, "
                "created_at = coalesce(excluded.created_at, created_at)",
                (seat_id, machine, fields["seat_name"], fields["seat_directory"],
                 fields["task_list_name"], at if operation == "agent-seat-created" else None))
    elif operation == "agent-seat-paused":
        execute("UPDATE agent_seat SET paused_at = ?, parked_at = NULL WHERE seat_id = ?",
                (at, seat_id))
    elif operation == "agent-seat-parked":
        execute("UPDATE agent_seat SET parked_at = ? WHERE seat_id = ?", (at, seat_id))
    elif operation == "agent-seat-retired":
        execute("UPDATE agent_seat SET retired_at = ?, paused_at = NULL, parked_at = NULL "
                "WHERE seat_id = ?", (at, seat_id))
    elif operation == "machine-booted":
        execute("INSERT OR REPLACE INTO machine_boot VALUES (?, ?, ?, ?, ?, ?)",
                (machine, fields["boot_id"], fields["booted_at"], fields["previous_boot"],
                 fields["stop_estimated_at"], fields["stop_estimate_method"]))
    elif operation == "handoff-supervisor-began":
        execute("INSERT INTO supervisor_run (run_id, seat_id, boot_id, process_id, "
                "process_started_at, generation, began_at, restart_attempt_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT (run_id) DO UPDATE SET "
                "boot_id = excluded.boot_id, process_id = excluded.process_id, "
                "process_started_at = excluded.process_started_at, "
                "generation = excluded.generation, began_at = excluded.began_at, "
                "restart_attempt_id = excluded.restart_attempt_id",
                (fields["run_id"], seat_id, fields["boot_id"], fields["process_id"],
                 fields["process_started_at"], fields["generation"], at,
                 fields["restart_attempt_id"]))
        execute("UPDATE agent_seat SET paused_at = NULL, parked_at = NULL WHERE seat_id = ?",
                (seat_id,))
    elif operation == "handoff-supervisor-ended":
        execute("INSERT INTO supervisor_run (run_id, seat_id, ended_at) VALUES (?, ?, ?) "
                "ON CONFLICT (run_id) DO UPDATE SET ended_at = excluded.ended_at",
                (fields["run_id"], seat_id, at))
    elif operation == "agent-session-launched":
        execute("INSERT INTO agent_session (machine, session_id, run_id, seat_id, "
                "transcript_path, predecessor_session, launched_at) VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (machine, session_id, run_id) DO UPDATE SET "
                "transcript_path = excluded.transcript_path, "
                "predecessor_session = excluded.predecessor_session, "
                "launched_at = excluded.launched_at",
                (machine, fields["session_id"], fields["run_id"], seat_id,
                 fields["transcript_path"], fields["predecessor_session"], at))
    elif operation == "agent-session-ended":
        execute("INSERT INTO agent_session (machine, session_id, run_id, seat_id, ended_at, "
                "exit_code) VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (machine, session_id, run_id) DO UPDATE SET "
                "ended_at = excluded.ended_at, exit_code = excluded.exit_code",
                (machine, fields["session_id"], fields["run_id"], seat_id, at,
                 fields["exit_code"]))
    elif operation == "session-handoff-written":
        execute("INSERT INTO handoff_event (event_id, seat_id, restart_counter, writer_session, "
                "written_at, next_step_text, dont_restart_reason) VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (event_id) DO UPDATE SET "
                "restart_counter = excluded.restart_counter, "
                "writer_session = excluded.writer_session, written_at = excluded.written_at, "
                "next_step_text = excluded.next_step_text, "
                "dont_restart_reason = excluded.dont_restart_reason",
                (event["event_id"], seat_id, fields["restart_counter"], fields["writer_session"],
                 at, fields["next_step_text"], fields["dont_restart_reason"]))
    elif operation == "session-handoff-consumed":
        execute("INSERT INTO handoff_event (event_id, seat_id, consumed_by_run, consumed_at) "
                "VALUES (?, ?, ?, ?) ON CONFLICT (event_id) DO UPDATE SET "
                "consumed_by_run = excluded.consumed_by_run, consumed_at = excluded.consumed_at",
                (fields["written_event_id"], seat_id, fields["run_id"], at))
    elif operation == "restart-attempted":
        execute("INSERT OR REPLACE INTO restart_attempt VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (fields["attempt_id"], machine, fields["boot_id"], seat_id, fields["why_picked"],
                 fields["action"], fields["began_at"], fields["ended_at"], fields["result"]))


def store_event(connection, raw_body):
    """Store one event; an answer raised here leaves the transaction open, and the
    request's connection, closed by its caller, rolls it back."""
    event = parse_event(raw_body)
    connection.execute("BEGIN IMMEDIATE")
    held = connection.execute("SELECT sequence FROM event WHERE event_id = ?",
                              (event["event_id"],)).fetchone()
    if held is not None:
        connection.execute("ROLLBACK")
        return {"sequence": held[0], **answer_footer(connection)}
    check_event_fits_its_operation(connection, event)
    sequence = connection.execute(
        "INSERT INTO event (event_id, machine, operation, occurred_at, received_at, body) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (event["event_id"], event["machine"], event["operation"], event["occurred_at"],
         utc_now(), json.dumps(event, sort_keys=True))).lastrowid
    try:
        apply_event(connection, event)
    except sqlite3.IntegrityError:
        raise Answer(422, {"error": "another agent-seat not retired holds the name "
                                    f"{event['fields'].get('seat_name')!r}"})
    connection.execute("COMMIT")
    return {"sequence": sequence, **answer_footer(connection)}


def rows(connection, query, parameters):
    return [dict(row) for row in connection.execute(query, parameters)]


def list_agent_seats(connection, query_string):
    machines = parse_qs(query_string).get("machine")
    if machines:
        seats = rows(connection, "SELECT * FROM agent_seat WHERE machine = ? ORDER BY seat_name",
                     (machines[0],))
    else:
        seats = rows(connection, "SELECT * FROM agent_seat ORDER BY seat_name", ())
    return {"agent_seats": seats, **answer_footer(connection)}


def get_agent_seat(connection, seat_id):
    seat = rows(connection, "SELECT * FROM agent_seat WHERE seat_id = ?", (seat_id,))
    if not seat:
        raise Answer(404, {"error": f"no agent-seat has seat_id {seat_id!r}"})
    return {
        "agent_seat": seat[0],
        "supervisor_runs": rows(connection, "SELECT * FROM supervisor_run WHERE seat_id = ? "
                                            "ORDER BY began_at", (seat_id,)),
        "agent_sessions": rows(connection, "SELECT * FROM agent_session WHERE seat_id = ? "
                                           "ORDER BY launched_at", (seat_id,)),
        "session_handoffs": rows(connection, "SELECT * FROM handoff_event WHERE seat_id = ? "
                                             "ORDER BY written_at", (seat_id,)),
        "restart_attempts": rows(connection, "SELECT * FROM restart_attempt WHERE seat_id = ? "
                                             "ORDER BY began_at", (seat_id,)),
        **answer_footer(connection)}


def make_request_handler(database_path, accepted_tokens_path):
    class RequestHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.answer_request(None)

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            self.answer_request(self.rfile.read(length))

        def answer_request(self, raw_body):
            connection = connect(database_path)
            try:
                status, body = 200, self.route(connection, raw_body)
            except Answer as answer:
                status, body = answer.status, answer.body
            except Exception as error:
                status, body = 500, {"error": f"{type(error).__name__}: {error}"}
            finally:
                connection.close()
            encoded = json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def route(self, connection, raw_body):
            scheme, _, token = (self.headers.get("Authorization") or "").partition(" ")
            if scheme != "Bearer" or token.strip() not in accepted_tokens(accepted_tokens_path):
                raise Answer(401, {"error": "no accepted token: send `Authorization: Bearer "
                                            "<token>` with a line of the service's "
                                            "accepted-tokens file"})
            generation = database_generation(connection)
            if self.headers.get(GENERATION_HEADER) != generation:
                raise Answer(412, {"generation_id": generation})
            path = urlsplit(self.path)
            if raw_body is not None and path.path == "/events":
                return store_event(connection, raw_body)
            if raw_body is None and path.path == "/agent-seats":
                return list_agent_seats(connection, path.query)
            if raw_body is None and path.path.startswith("/agent-seats/"):
                return get_agent_seat(connection, path.path[len("/agent-seats/"):])
            raise Answer(404, {"error": f"no operation at {self.command} {path.path}"})

    return RequestHandler


def make_server(database_path, accepted_tokens_path, host, port):
    create_database_if_absent(database_path)
    return ThreadingHTTPServer((host, port),
                               make_request_handler(database_path, accepted_tokens_path))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--database", default=str(DATABASE_PATH))
    parser.add_argument("--accepted-tokens-file", default=str(ACCEPTED_TOKENS_FILE_PATH))
    parser.add_argument("--host", default="")
    parser.add_argument("--port", type=int, default=PORT)
    arguments = parser.parse_args(argv)
    # Only nedlern may read or write the database, its WAL files included.
    os.umask(0o077)
    server = make_server(arguments.database, arguments.accepted_tokens_file,
                         arguments.host, arguments.port)
    server.serve_forever()


if __name__ == "__main__":
    sys.exit(main())
