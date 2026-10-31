#!/usr/bin/env python3
"""Tests for nc-systems/agent-seat-database/agent-seat-database-service.py.

Each case starts the service on a loopback port with a database and an
accepted-tokens file under a temporary directory, sends real HTTP requests,
and reads the database back: tokens and 401, the generation ID and 412, the
400, 422 and 409 answers, values of the wrong type, an event sent twice, the
state each operation leaves, the newest backup's mark in every answer, and the
500 answer to an error no check foresaw.

Run: python3 nc-systems/agent-seat-database/tests/agent-seat-database-service-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import json
import sqlite3
import tempfile
import threading
import urllib.error
import urllib.request
import uuid
from pathlib import Path

SERVICE_PATH = Path(__file__).resolve().parents[1] / "agent-seat-database-service.py"
_spec = importlib.util.spec_from_file_location("agent_seat_database_service", SERVICE_PATH)
service = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(service)

failures = 0


def check(name, condition, detail=None):
    global failures
    if condition:
        print(f"PASS  {name}")
    else:
        failures += 1
        print(f"FAIL  {name}: {detail!r}")


TOKEN = "mac-token"
SEAT = str(uuid.uuid4())


def event(operation, fields, seat_id=SEAT, machine="mac", event_id=None, **extra):
    body = {"event_id": str(uuid.uuid4()) if event_id is None else event_id, "machine": machine,
            "operation": operation, "occurred_at": extra.pop("at", "2026-10-26T10:00:00+00:00"),
            "seat_id": seat_id, "fields": fields}
    body.update(extra)
    return body


SEAT_FIELDS = {"seat_name": "merge-lane-2", "seat_directory": "/home/nedlern/agents/merge-lane-2",
               "task_list_name": "nedschorus-merge-lane-2-tasks"}

with tempfile.TemporaryDirectory() as scratch:
    scratch = Path(scratch)
    database = scratch / "state" / "agent-seat-database.sqlite3"
    tokens = scratch / "accepted-tokens"
    tokens.write_text(f"{TOKEN}\n\n  ned-box-token  \n", encoding="utf-8")
    server = service.make_server(database, tokens, "127.0.0.1", 0)
    server.RequestHandlerClass.log_message = lambda *arguments: None
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    db = sqlite3.connect(str(database), isolation_level=None)
    generation = db.execute("SELECT generation_id FROM database_generation").fetchone()[0]

    def request(path, body=None, token=TOKEN, generation_id="current", raw=None):
        headers = {}
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        if generation_id is not None:
            headers[service.GENERATION_HEADER] = (
                generation if generation_id == "current" else generation_id)
        data = raw if raw is not None else (
            json.dumps(body).encode("utf-8") if body is not None else None)
        call = urllib.request.Request(base + path, data=data, headers=headers,
                                      method="POST" if data is not None else "GET")
        try:
            with urllib.request.urlopen(call, timeout=10) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())

    def events_stored():
        return db.execute("SELECT count(*) FROM event").fetchone()[0]

    check("a new database is made with WAL and a generation ID that is a UUID",
          db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
          and str(uuid.UUID(generation)) == generation)
    beside = scratch / "beside.sqlite3"
    service.create_database_if_absent(beside)
    check("a database is made in a directory that already exists", beside.exists())
    service.create_database_if_absent(database)
    check("an existing database keeps its generation ID",
          db.execute("SELECT generation_id FROM database_generation").fetchall() == [(generation,)])

    # 401
    for name, token in (("no token", None), ("an unknown token", "nobody"),
                        ("a token with another scheme", None)):
        status, answer = request("/agent-seats", token=token)
        check(f"401: {name} is refused", status == 401 and "accepted-tokens" in answer["error"],
              (status, answer))
    call = urllib.request.Request(base + "/agent-seats",
                                  headers={"Authorization": f"Basic {TOKEN}",
                                           service.GENERATION_HEADER: generation})
    try:
        urllib.request.urlopen(call, timeout=10)
        basic = None
    except urllib.error.HTTPError as error:
        basic = error.code
    check("401: a token sent under another scheme than Bearer is refused", basic == 401, basic)
    status, _ = request("/agent-seats", token="ned-box-token")
    check("a token on a line with surrounding blanks is accepted", status == 200, status)
    call = urllib.request.Request(base + "/agent-seats",
                                  headers={"Authorization": f"Token {TOKEN}",
                                           service.GENERATION_HEADER: generation})
    try:
        urllib.request.urlopen(call, timeout=10)
        other_scheme = None
    except urllib.error.HTTPError as error:
        other_scheme = error.code
    check("401: a token sent under the scheme Token is refused too", other_scheme == 401,
          other_scheme)
    tokens.rename(scratch / "moved")
    status, _ = request("/agent-seats")
    check("401: every request is refused while the accepted-tokens file cannot be read",
          status == 401, status)
    (scratch / "moved").rename(tokens)

    # 412
    before = events_stored()
    for name, sent_generation in (("no generation ID", None), ("another generation ID", "old")):
        status, answer = request("/events", event("agent-seat-created", SEAT_FIELDS),
                                 generation_id=sent_generation)
        check(f"412: {name} stores nothing and is answered with the current generation ID",
              status == 412 and answer == {"generation_id": generation}
              and events_stored() == before, (status, answer))
    status, answer = request("/agent-seats", generation_id="old")
    check("412: a list request with another generation ID is answered 412 too",
          status == 412 and answer == {"generation_id": generation}, (status, answer))

    # 400
    for name, raw in (("a body that is not JSON", b"{not json"),
                      ("a body that is a JSON list", b"[1]"),
                      ("an event with no event_id", json.dumps(
                          {k: v for k, v in event("agent-seat-paused", {}).items()
                           if k != "event_id"}).encode()),
                      ("an empty event_id", json.dumps(
                          event("agent-seat-paused", {}, event_id="")).encode())):
        status, answer = request("/events", raw=raw)
        check(f"400: {name}", status == 400 and events_stored() == before, (status, answer))
    status, answer = request("/events", raw=b"")
    check("400: an empty body", status == 400, (status, answer))

    # 422
    status, answer = request("/events", event("agent-seat-created", SEAT_FIELDS, machine="pc"))
    check("422: an unknown machine", status == 422 and "machine" in answer["error"],
          (status, answer))
    status, answer = request("/events", event("agent-seat-paused", {}, seat_id="no-such-seat"))
    check("422: a seat ID with no agent-seat row", status == 422
          and "no-such-seat" in answer["error"] and events_stored() == before, (status, answer))
    for name, body, named in (
            ("a field that is a list", event("agent-seat-created",
                                             dict(SEAT_FIELDS, seat_name=["x"])), "fields.seat_name"),
            ("a field that is an object", event("agent-seat-created",
                                                dict(SEAT_FIELDS, seat_directory={"a": 1})),
             "fields.seat_directory"),
            ("a number too large for SQLite", event("agent-seat-created",
                                                    dict(SEAT_FIELDS, task_list_name=2 ** 63)),
             "fields.task_list_name"),
            ("a seat ID that is an object", event("agent-seat-paused", {}, seat_id={"a": 1}),
             "seat_id"),
            ("an occurred_at that is a list", event("agent-seat-paused", {}, at=[1]),
             "occurred_at")):
        status, answer = request("/events", body)
        check(f"422: {name} names the value and stores nothing", status == 422
              and f"type it cannot store: {named}." in answer["error"]
              and body["event_id"] in answer["error"]
              and events_stored() == before,
              (status, answer))
    status, answer = request("/events", event("agent-seat-created",
                                              dict(SEAT_FIELDS, task_list_name=2 ** 63 - 1)))
    check("the largest number SQLite stores is accepted as a field",
          status == 200 and events_stored() == before + 1, (status, answer))
    db.execute("DELETE FROM agent_seat")
    db.execute("DELETE FROM event")
    db.execute("DELETE FROM sqlite_sequence")

    # 409
    for name, body in (
            ("an unknown operation", event("agent-seat-teleported", {})),
            ("a field the operation does not know", event("agent-seat-paused", {"why": "x"})),
            ("a field the operation needs, missing",
             event("agent-seat-created", {"seat_name": "x"})),
            ("an event without its own time",
             {k: v for k, v in event("agent-seat-paused", {}).items() if k != "occurred_at"}),
            ("an event key the service does not know",
             event("agent-seat-created", SEAT_FIELDS, priority=1)),
            ("fields that are not an object", event("agent-seat-paused", [])),
            ("a seat ID on machine-booted", event(
                "machine-booted", {"boot_id": "b", "booted_at": None, "previous_boot": None,
                                   "stop_estimated_at": None, "stop_estimate_method": None})),
            ("no seat ID on an operation about an agent-seat",
             event("agent-seat-created", SEAT_FIELDS, seat_id=None))):
        status, answer = request("/events", body)
        check(f"409: {name} stores nothing", status == 409 and events_stored() == before,
              (status, answer))

    # 200, and an event sent twice
    created = event("agent-seat-created", SEAT_FIELDS, at="2026-10-26T09:00:00+00:00")
    status, first = request("/events", created)
    check("200: an event is stored and answered with its sequence number, the generation ID "
          "and no backup yet",
          status == 200 and first["sequence"] == 1 and first["generation_id"] == generation
          and first["newest_backup"] is None, (status, first))
    status, again = request("/events", created)
    check("an event ID already held is stored once and answered with its first sequence number",
          status == 200 and again["sequence"] == 1 and events_stored() == 1, (status, again))
    row = db.execute("SELECT event_id, machine, operation, occurred_at, body FROM event").fetchone()
    check("the event row holds the machine, operation, the event's own time and its body",
          row[:4] == (created["event_id"], "mac", "agent-seat-created", created["occurred_at"])
          and json.loads(row[4]) == created, row)

    status, answer = request("/events", event(
        "agent-seat-created", dict(SEAT_FIELDS, seat_directory="/elsewhere"),
        seat_id=str(uuid.uuid4())))
    check("422: a name another agent-seat not retired holds is refused, and nothing is stored",
          status == 422 and "merge-lane-2" in answer["error"] and events_stored() == 1,
          (status, answer))

    def seat_state():
        return db.execute("SELECT paused_at, parked_at, retired_at FROM agent_seat "
                          "WHERE seat_id = ?", (SEAT,)).fetchone()

    def send(operation, fields, at, seat_id=SEAT):
        status, answer = request("/events", event(operation, fields, seat_id=seat_id, at=at))
        assert status == 200, (operation, status, answer)
        return answer

    began = {"run_id": "run-1", "boot_id": "boot-1", "process_id": 41,
             "process_started_at": "t", "generation": 3, "restart_attempt_id": "attempt-1"}
    send("agent-seat-parked", {}, "p1")
    send("agent-seat-paused", {}, "p2")
    check("paused ends a park and clears parked_at", seat_state() == ("p2", None, None),
          seat_state())
    send("agent-seat-parked", {}, "p3")
    send("handoff-supervisor-began", began, "p4")
    check("handoff-supervisor-began ends a pause and a park and clears both",
          seat_state() == (None, None, None), seat_state())
    send("agent-seat-parked", {}, "p5")
    send("agent-seat-paused", {}, "p6")
    send("agent-seat-parked", {}, "p7")
    send("agent-seat-retired", {}, "p8")
    check("retired ends a pause and a park", seat_state() == (None, None, "p8"), seat_state())

    reborn = str(uuid.uuid4())
    send("agent-seat-created", SEAT_FIELDS, "p9", seat_id=reborn)
    check("a retired agent-seat's name may be taken by a new agent-seat",
          db.execute("SELECT count(*) FROM agent_seat WHERE seat_name = 'merge-lane-2'")
          .fetchone()[0] == 2)
    send("agent-seat-seen", dict(SEAT_FIELDS, task_list_name="renamed"), "p10", seat_id=reborn)
    check("agent-seat-seen updates an agent-seat it already holds and keeps created_at",
          db.execute("SELECT task_list_name, created_at FROM agent_seat WHERE seat_id = ?",
                     (reborn,)).fetchone() == ("renamed", "p9"))
    seen_only = str(uuid.uuid4())
    send("agent-seat-seen", dict(SEAT_FIELDS, seat_name="ned-box-seat"), "p11", seat_id=seen_only)
    check("agent-seat-seen makes a row with no created_at for an agent-seat it does not hold",
          db.execute("SELECT machine, created_at FROM agent_seat WHERE seat_id = ?",
                     (seen_only,)).fetchone() == ("mac", None))

    send("handoff-supervisor-ended", {"run_id": "run-1"}, "e1", seat_id=reborn)
    send("handoff-supervisor-ended", {"run_id": "run-2"}, "e2", seat_id=reborn)
    send("handoff-supervisor-began", dict(began, run_id="run-2"), "b2", seat_id=reborn)
    check("handoff-supervisor-ended fills ended_at, also for a run whose began is not held "
          "yet, and a later began keeps it",
          db.execute("SELECT run_id, seat_id, boot_id, process_id, generation, began_at, ended_at, "
                     "restart_attempt_id FROM supervisor_run ORDER BY run_id").fetchall()
          == [("run-1", SEAT, "boot-1", 41, 3, "p4", "e1", "attempt-1"),
              ("run-2", reborn, "boot-1", 41, 3, "b2", "e2", "attempt-1")],
          db.execute("SELECT * FROM supervisor_run").fetchall())

    send("agent-session-launched", {"session_id": "s1", "run_id": "run-2",
                                    "transcript_path": None, "predecessor_session": None},
         "l1", seat_id=reborn)
    send("agent-session-ended", {"session_id": "s1", "run_id": "run-2", "exit_code": 1}, "x1",
         seat_id=reborn)
    send("agent-session-ended", {"session_id": "s2", "run_id": "run-2", "exit_code": 0}, "x2",
         seat_id=reborn)
    send("agent-session-launched", {"session_id": "s2", "run_id": "run-2",
                                    "transcript_path": "/t/s2.jsonl", "predecessor_session": "s1"},
         "l2", seat_id=reborn)
    check("a launch with no transcript, then its end, is one agent_session row; an end that "
          "arrives first keeps its exit code when the launch follows",
          db.execute("SELECT machine, session_id, run_id, seat_id, transcript_path, "
                     "predecessor_session, launched_at, ended_at, exit_code FROM agent_session "
                     "ORDER BY session_id").fetchall()
          == [("mac", "s1", "run-2", reborn, None, None, "l1", "x1", 1),
              ("mac", "s2", "run-2", reborn, "/t/s2.jsonl", "s1", "l2", "x2", 0)],
          db.execute("SELECT * FROM agent_session").fetchall())

    written = event("session-handoff-written", {"restart_counter": 7, "writer_session": "s2",
                                                "next_step_text": "go", "dont_restart_reason": None},
                    seat_id=reborn, at="w1")
    request("/events", written)
    send("session-handoff-consumed", {"written_event_id": written["event_id"], "run_id": "run-3"},
         "c1", seat_id=reborn)
    send("session-handoff-consumed", {"written_event_id": "unseen-write", "run_id": "run-3"},
         "c2", seat_id=reborn)
    late = event("session-handoff-written", {"restart_counter": 8, "writer_session": "s3",
                                             "next_step_text": "later", "dont_restart_reason": "ask"},
                 seat_id=reborn, at="w2", event_id="unseen-write")
    request("/events", late)
    check("session-handoff-written is keyed by its event ID, and consumed fills the row of the "
          "written event it names, whichever arrives first",
          db.execute("SELECT * FROM handoff_event ORDER BY written_at").fetchall()
          == [(written["event_id"], reborn, 7, "s2", "w1", "go", None, "run-3", "c1"),
              ("unseen-write", reborn, 8, "s3", "w2", "later", "ask", "run-3", "c2")],
          db.execute("SELECT * FROM handoff_event").fetchall())

    send("restart-attempted", {"attempt_id": "attempt-1", "boot_id": "boot-1", "why_picked": "live",
                               "action": "restart", "began_at": "r1", "ended_at": "r2",
                               "result": "started"}, "r2", seat_id=reborn)
    check("restart-attempted stores the attempt with the machine of the event",
          db.execute("SELECT * FROM restart_attempt").fetchall()
          == [("attempt-1", "mac", "boot-1", reborn, "live", "restart", "r1", "r2", "started")])
    booted = {"boot_id": "boot-9", "booted_at": "t0", "previous_boot": "boot-1",
              "stop_estimated_at": "t-1", "stop_estimate_method": "newest heartbeat"}
    status, answer = request("/events", event("machine-booted", booted, seat_id=None,
                                              machine="ned-box"))
    check("machine-booted names no agent-seat and stores the boot",
          status == 200 and db.execute("SELECT * FROM machine_boot").fetchall()
          == [("ned-box", "boot-9", "t0", "boot-1", "t-1", "newest heartbeat")], (status, answer))

    status, listed = request("/agent-seats")
    check("list agent-seats gives every agent-seat, with the generation ID",
          status == 200 and len(listed["agent_seats"]) == 3
          and listed["generation_id"] == generation, (status, listed))
    status, listed = request("/agent-seats?machine=ned-box")
    check("list agent-seats by machine gives only that machine's", status == 200
          and listed["agent_seats"] == [], (status, listed))
    status, one = request(f"/agent-seats/{reborn}")
    check("get one agent-seat gives its row, runs, agent-sessions, session-handoffs and "
          "restart attempts",
          status == 200 and one["agent_seat"]["seat_id"] == reborn
          and [run["run_id"] for run in one["supervisor_runs"]] == ["run-2"]
          and len(one["agent_sessions"]) == 2 and len(one["session_handoffs"]) == 2
          and len(one["restart_attempts"]) == 1 and one["generation_id"] == generation,
          (status, one))
    status, answer = request("/agent-seats/no-such-seat")
    check("get one agent-seat answers 404 for a seat ID it does not hold", status == 404,
          (status, answer))
    status, answer = request("/nowhere")
    check("an unknown path is answered 404", status == 404, (status, answer))
    status, answer = request("/agent-seats", body={})
    check("a POST to a path that takes GET is answered 404", status == 404, (status, answer))
    status, answer = request(f"/agent-seats/{reborn}", body={})
    check("a POST to one agent-seat's path is answered 404", status == 404, (status, answer))

    db.execute("INSERT INTO newest_backup VALUES ('gen-of-backup', 12)")
    status, answer = request("/events", event("agent-seat-paused", {}, seat_id=reborn))
    check("every answer gives the newest backup's generation ID and highest sequence number",
          status == 200 and answer["newest_backup"]
          == {"generation_id": "gen-of-backup", "highest_sequence": 12}, (status, answer))
    status, answer = request("/agent-seats")
    check("a list answer gives the newest backup too",
          answer["newest_backup"]["highest_sequence"] == 12, answer)

    sequences = [row[0] for row in db.execute("SELECT sequence FROM event ORDER BY sequence")]
    check("sequence numbers rise by one per stored event, in the order stored",
          sequences == list(range(1, len(sequences) + 1)), sequences)

    # 500: an error no check foresaw is answered, and its transaction rolled back
    def fail_to_apply(connection, applied):
        raise RuntimeError("the state tables could not be updated")

    applying, service.apply_event = service.apply_event, fail_to_apply
    before = events_stored()
    status, answer = request("/events", event("agent-seat-paused", {}))
    service.apply_event = applying
    check("500: an unforeseen error is answered with its type and message, and nothing is stored",
          status == 500 and answer == {"error": "RuntimeError: the state tables could not be "
                                                "updated"} and events_stored() == before,
          (status, answer))
    server.shutdown()

    try:
        service.main(["--port", "eighty"])
        refused = None
    except SystemExit as stop:
        refused = stop.code
    check("main exits 2 on a bad invocation", refused == 2, refused)

raise SystemExit(1 if failures else 0)
