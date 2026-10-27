#!/usr/bin/env python3
"""Send this machine's queued events to agent-seat-database-service.py, oldest first.

Usage:
  nc-systems/agent-seat-database/agent-seat-database-local-events-file-sender.py
      [--local-events-file PATH] [--service-url URL] [--token-file PATH]

  --local-events-file  default ~/.local/state/nedschorus/agent-seat-events.sqlite
  --service-url        default http://ned-box.local:8765
  --token-file         default ~/.config/nedschorus/agent-seat-database-service.token

write_event_to_local_events_file_and_start_sender, in
agent-seat-database-local-events-file-common.py, starts this program after
each event it queues; the sending job will start it every 10 minutes. One sender runs per machine at a time: it runs only while it holds an
exclusive SQLite transaction on agent-seat-events-sender.sqlite, beside the local
events file, taken without waiting, and exits 0 at once when another sender
holds it. The operating system releases the transaction of a sender that is
killed.

The holder sends the oldest queued row, waits at most 2 seconds for the
answer, and sends the next only after the service has answered the one before,
so the service receives this machine's events in the order they were written.
When the queue is empty it ends the transaction with a rollback and looks at
the queue again; when a row is queued, it takes the transaction again, without
waiting, and exits if another sender took it meanwhile. So a row whose writer's
sender found the transaction taken is sent by this sender or by the one that
took it.

What each answer does to the row:
  2xx   fills `sent` and `sequence`, and deletes every sent row whose sequence is
        at or below the newest backup's highest sequence number, when that backup's
        generation ID is the file's. No row is deleted before the first backup.
        When the file no longer holds the answer's generation ID, because a
        reader's 412 handling changed it meanwhile, the answer is dropped and the
        row, queued again, is sent again under the new generation ID.
  412   in one transaction, and only while the file still holds the generation ID
        sent, clears `sent` and `sequence` on every sent row and saves the
        service's new generation ID; sending goes on from the oldest queued row.
  400, 422
        fills `rejected` with the answer and the time; sending goes on.
  401, 409, any other answer, an answer that is not the JSON expected, or none
        leaves the row queued and stops this sender, so no later row overtakes
        it.

Exit codes: 0 the queue is empty, or another sender holds the transaction;
1 stopped with rows still queued, the reason on standard error; 2 the token
file cannot be read.
"""

import argparse
import http.client
import importlib.util
import json
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path

PROGRAM = "agent-seat-database-local-events-file-sender"
ANSWER_TIMEOUT_SECONDS = 2
EXIT_QUEUE_SENT = 0
EXIT_STOPPED_WITH_ROWS_QUEUED = 1
EXIT_TOKEN_FILE_UNREADABLE = 2

_events_file_spec = importlib.util.spec_from_file_location(
    "agent_seat_database_local_events_file_common",
    Path(__file__).resolve().with_name("agent-seat-database-local-events-file-common.py"))
events_file = importlib.util.module_from_spec(_events_file_spec)
_events_file_spec.loader.exec_module(events_file)


def oldest_queued_row(connection):
    return connection.execute(
        "SELECT row_number, event_id, body FROM outbox_event "
        "WHERE sent IS NULL AND rejected IS NULL ORDER BY row_number LIMIT 1").fetchone()


def post_event(service_url, token, generation, body):
    """Return (status, answer text); status is None when no answer came."""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    if generation is not None:
        headers[events_file.GENERATION_HEADER] = generation
    request = urllib.request.Request(f"{service_url}/events", data=body.encode("utf-8"),
                                     headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=ANSWER_TIMEOUT_SECONDS) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", "replace")
    except (OSError, http.client.HTTPException) as error:
        return None, f"{error.__class__.__name__}: {error}"


def answer_object(text, keys):
    """The answer as a dict holding every key in keys, or None."""
    try:
        answer = json.loads(text)
    except ValueError:
        return None
    if not isinstance(answer, dict) or not all(key in answer for key in keys):
        return None
    return answer


def record_sent(connection, row_number, answer):
    connection.execute("BEGIN IMMEDIATE")
    try:
        generation = events_file.generation_seen(connection)
        if generation == answer["generation_id"]:
            connection.execute("UPDATE outbox_event SET sent = ?, sequence = ? "
                               "WHERE row_number = ?",
                               (events_file.utc_now(), answer["sequence"], row_number))
            backup = answer["newest_backup"]
            if backup is not None and backup.get("generation_id") == generation:
                connection.execute("DELETE FROM outbox_event WHERE sent IS NOT NULL "
                                   "AND sequence <= ?", (backup["highest_sequence"],))
        connection.execute("COMMIT")
    except BaseException:
        connection.execute("ROLLBACK")
        raise


def record_rejected(connection, row_number, status, text):
    connection.execute("UPDATE outbox_event SET rejected = ? WHERE row_number = ?",
                       (json.dumps({"status": status, "answer": text,
                                    "at": events_file.utc_now()}), row_number))


def send_queued_rows(connection, service_url, token):
    """Send until the queue is empty, and return None; or return why sending stopped."""
    while True:
        row = oldest_queued_row(connection)
        if row is None:
            return None
        row_number, event_id, body = row
        generation = events_file.generation_seen(connection)
        status, text = post_event(service_url, token, generation, body)
        if status is not None and 200 <= status < 300:
            answer = answer_object(text, ("sequence", "generation_id", "newest_backup"))
            if answer is not None:
                record_sent(connection, row_number, answer)
                continue
        elif status == 412:
            answer = answer_object(text, ("generation_id",))
            if answer is not None:
                events_file.requeue_sent_events_for_new_database_generation_id(
                    connection, generation, answer["generation_id"])
                continue
        elif status in (400, 422):
            record_rejected(connection, row_number, status, text)
            continue
        return (f"{PROGRAM}: stopped at queued row {row_number} (event {event_id}): "
                f"{'no answer' if status is None else f'answer {status}'} from "
                f"{service_url}: {text}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--local-events-file",
                        default=str(events_file.AGENT_SEAT_DATABASE_LOCAL_EVENTS_FILE_PATH))
    parser.add_argument("--service-url", default=events_file.AGENT_SEAT_DATABASE_SERVICE_URL)
    parser.add_argument("--token-file",
                        default=str(events_file.AGENT_SEAT_DATABASE_SERVICE_TOKEN_FILE_PATH))
    arguments = parser.parse_args(argv)
    try:
        token = Path(arguments.token_file).read_text(encoding="utf-8").strip()
    except OSError as error:
        print(f"{PROGRAM}: not run — the token file {arguments.token_file} cannot be read "
              f"({error.strerror}). Every request to the service carries this machine's token.\n"
              f"Create it as one line holding this machine's token, mode 600, and add the same "
              f"line to ~/.config/nedschorus/agent-seat-database-service-accepted-tokens on "
              f"ned-box.", file=sys.stderr)
        return EXIT_TOKEN_FILE_UNREADABLE
    connection = events_file.open_local_events_file(arguments.local_events_file)
    lock_path = events_file.local_events_file_sender_lock_file_path(arguments.local_events_file)
    lock = sqlite3.connect(str(lock_path), timeout=0, isolation_level=None)
    while True:
        try:
            lock.execute("BEGIN EXCLUSIVE")
        except sqlite3.OperationalError as error:
            if "locked" not in str(error):
                raise
            return EXIT_QUEUE_SENT
        try:
            stopped = send_queued_rows(connection, arguments.service_url, token)
        finally:
            lock.execute("ROLLBACK")
        if stopped is not None:
            print(stopped, file=sys.stderr)
            return EXIT_STOPPED_WITH_ROWS_QUEUED
        if oldest_queued_row(connection) is None:
            return EXIT_QUEUE_SENT


if __name__ == "__main__":
    sys.exit(main())
