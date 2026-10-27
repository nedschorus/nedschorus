"""Write an event into this machine's local events file, and start the sender.

A program never sends an event to agent-seat-database-service.py itself: it
calls write_event_to_local_events_file_and_start_sender, which commits the
event as a row of the local events file, an outbox, and then starts
agent-seat-database-local-events-file-sender.py without waiting for it. The row waits there until the service has stored it,
so an agent-seat keeps working while ned-box cannot be reached.

Load it by path, under the snake_case form of its file name:

    spec = importlib.util.spec_from_file_location(
        "agent_seat_database_local_events_file_common", <path>)

It runs on both machines, the Mac's Apple Python 3.9 included.

THE LOCAL EVENTS FILE, AGENT_SEAT_DATABASE_LOCAL_EVENTS_FILE_PATH, holds three
tables:
  outbox_event   one row per event, in the order programs wrote them: the event
                 as sent (body), when it was written, and `sent` with `sequence`
                 once the service stored it, or `rejected` once the service
                 answered 400 or 422. A row with neither `sent` nor `rejected`
                 is queued.
  agent_seat     one row per agent-seat of this machine: its ID, its name, and
                 whether it is retired.
  database_generation_seen
                 one row: the service's generation ID this file last saw, null
                 until the first answer.
"""

import json
import sqlite3
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

AGENT_SEAT_DATABASE_LOCAL_EVENTS_FILE_PATH = (Path.home() / ".local" / "state" / "nedschorus"
                                              / "agent-seat-events.sqlite")
SENDER_LOCK_FILE_NAME = "agent-seat-events-sender.sqlite"
AGENT_SEAT_DATABASE_SERVICE_URL = "http://ned-box.local:8765"
AGENT_SEAT_DATABASE_SERVICE_TOKEN_FILE_PATH = (Path.home() / ".config" / "nedschorus"
                                               / "agent-seat-database-service.token")
GENERATION_HEADER = "Agent-Seat-Database-Generation-Id"
SENDER_PATH = Path(__file__).resolve().with_name("agent-seat-database-local-events-file-sender.py")
THIS_MACHINE = "mac" if sys.platform == "darwin" else "ned-box"
BUSY_TIMEOUT_SECONDS = 10

SCHEMA = (
    "CREATE TABLE IF NOT EXISTS outbox_event ("
    " row_number INTEGER PRIMARY KEY,"
    " event_id TEXT NOT NULL UNIQUE,"
    " body TEXT NOT NULL,"
    " written_at TEXT NOT NULL,"
    " sent TEXT,"
    " sequence INTEGER,"
    " rejected TEXT)",
    "CREATE TABLE IF NOT EXISTS agent_seat ("
    " seat_id TEXT PRIMARY KEY,"
    " seat_name TEXT NOT NULL,"
    " retired INTEGER NOT NULL DEFAULT 0)",
    "CREATE TABLE IF NOT EXISTS database_generation_seen (generation_id TEXT)",
    "INSERT INTO database_generation_seen SELECT NULL"
    " WHERE NOT EXISTS (SELECT 1 FROM database_generation_seen)",
)


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def local_events_file_sender_lock_file_path(local_events_file):
    return Path(local_events_file).with_name(SENDER_LOCK_FILE_NAME)


def open_local_events_file(local_events_file=AGENT_SEAT_DATABASE_LOCAL_EVENTS_FILE_PATH):
    """Open the file, making it and its tables when absent; transactions are explicit."""
    Path(local_events_file).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(local_events_file), timeout=BUSY_TIMEOUT_SECONDS,
                                 isolation_level=None)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("BEGIN IMMEDIATE")
    for statement in SCHEMA:
        connection.execute(statement)
    connection.execute("COMMIT")
    return connection


def generation_seen(connection):
    return connection.execute("SELECT generation_id FROM database_generation_seen").fetchone()[0]


def requeue_sent_events_for_new_database_generation_id(connection, old_generation, new_generation):
    """Mark every sent row queued again under the service's new generation ID.

    Only while the file still holds old_generation, so a second program that got
    the same 412 does not clear rows already resent under the new one.
    """
    connection.execute("BEGIN IMMEDIATE")
    try:
        if generation_seen(connection) == old_generation:
            connection.execute("UPDATE outbox_event SET sent = NULL, sequence = NULL "
                               "WHERE sent IS NOT NULL")
            connection.execute("UPDATE database_generation_seen SET generation_id = ?",
                               (new_generation,))
        connection.execute("COMMIT")
    except BaseException:
        connection.execute("ROLLBACK")
        raise


def start_sender(local_events_file=AGENT_SEAT_DATABASE_LOCAL_EVENTS_FILE_PATH,
                 sender_arguments=()):
    """Start the sender in its own session, and do not wait for it."""
    subprocess.Popen(
        [sys.executable, str(SENDER_PATH), "--local-events-file", str(local_events_file),
         *sender_arguments],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True)


def write_event_to_local_events_file_and_start_sender(
        operation, seat_id, fields, local_events_file=AGENT_SEAT_DATABASE_LOCAL_EVENTS_FILE_PATH,
        sender_arguments=()):
    """Queue one event for the service, start the sender, and return the event's ID.

    seat_id is None for an operation that names no agent-seat, such as
    machine-booted. The fields are the operation's, as the service's
    OPERATION_FIELDS lists them.
    """
    event_id = str(uuid.uuid4())
    body = {"event_id": event_id, "machine": THIS_MACHINE, "operation": operation,
            "occurred_at": utc_now(), "seat_id": seat_id, "fields": fields}
    connection = open_local_events_file(local_events_file)
    try:
        connection.execute("INSERT INTO outbox_event (event_id, body, written_at) "
                           "VALUES (?, ?, ?)", (event_id, json.dumps(body), utc_now()))
    finally:
        connection.close()
    start_sender(local_events_file, sender_arguments)
    return event_id
