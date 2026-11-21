#!/usr/bin/env python3
"""Name the next agent-seat holding mutant-test tasks to release when merge-lane-2's review queue is quiet, or record one as released. Exits 0 if it named or recorded an agent-seat, 1 if it named none, 2 if it could not tell.

Usage:
  scripts/merge-lane-unreviewed-prs-count-then-next-agent-seat-go-ahead-to-open-surviving-mutant-test-prs.py
      [--state-directory DIR] [--record-released AGENT_SEAT]

Without --record-released, the program counts the open pull requests, not
drafts, that have no review from merge-lane-2 on their newest commit: no GitHub
review by the account ned-review-merge, in any state, whose commit is the pull
request's head commit. When that count is 10 or fewer and the agent-seats file
names an agent-seat not yet recorded as released, the program prints `RELEASE
<agent-seat>` for the first such agent-seat in the file's order, the message to
send it, and the --record-released command to run once the message is sent;
otherwise it prints the count. It writes nothing, so a release whose message
was not sent, such as one in output a caller cut off, is named again on the
next run.

With --record-released AGENT_SEAT, the program records that agent-seat as
released, so later runs name the next one. It refuses an agent-seat the
agent-seats file does not name, and records an agent-seat already recorded
only once.

A mutant-test pull request only adds tests for surviving mutants. Such pull
requests stay unopened until merge-lane-2 tells the agent-seat holding them
that the review queue is quiet; the message says the agent-seat may then open
them one per source file, with at most 5 open at a time.

--state-directory, by default
/home/nedlern/nedsnodes-logs/seats/merge-lane-2/surviving-mutant-test-prs-go-ahead,
holds two files:
  agent-seats-holding-surviving-mutant-test-tasks-in-go-ahead-order.txt: one
    agent-seat per line, in the order they are released; blank lines are
    ignored. The program only reads it.
  agent-seats-given-surviving-mutant-test-prs-go-ahead.jsonl: one JSON object
    per agent-seat recorded as released, with the keys agent_seat and
    released_at. --record-released appends to it, and makes it when it is
    missing.

scripts/merge-lane-pull-request-merge-through-merge-gate-with-stacked-pull-request-retarget.py
runs this program, without --record-released, after each merge. gh runs with
the environment the program is given, so with the GH_TOKEN its caller sets.
"""

import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path

REPOSITORY_OWNER, REPOSITORY_NAME = "nedsnodes", "nedsnodes"
MERGE_LANE_ACCOUNT = "ned-review-merge"
QUIET_REVIEW_QUEUE_MOST_UNREVIEWED_PULL_REQUESTS = 10
MUTANT_TEST_PULL_REQUESTS_OPEN_AT_ONCE_AT_MOST = 5
DEFAULT_STATE_DIRECTORY = Path(
    "/home/nedlern/nedsnodes-logs/seats/merge-lane-2/surviving-mutant-test-prs-go-ahead")
AGENT_SEATS_FILE_NAME = "agent-seats-holding-surviving-mutant-test-tasks-in-go-ahead-order.txt"
RELEASED_FILE_NAME = "agent-seats-given-surviving-mutant-test-prs-go-ahead.jsonl"
RELEASE_LINE_PREFIX = "RELEASE "

EXIT_NAMED_OR_RECORDED = 0
EXIT_NAMED_NONE = 1
EXIT_COULD_NOT_TELL = 2

# reviews(last: 100): a pull request's reviews on its head commit are its newest.
OPEN_PULL_REQUESTS_QUERY = """
query($owner: String!, $name: String!, $endCursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequests(states: OPEN, first: 100, after: $endCursor) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number isDraft headRefOid
        reviews(author: "%s", last: 100) { nodes { commit { oid } } }
      }
    }
  }
}
""" % MERGE_LANE_ACCOUNT


PROGRAM_COMMAND = f"python3 scripts/{Path(__file__).name}"
SUBAGENT_LINE = "If you are a subagent, tell the agent that dispatched you instead of the user."
NOTHING_WAITS = ("Nothing else waits on this: no agent-seat holding mutant-test tasks is named "
                 "for release, and the next merge runs this program again.")


class CouldNotTell(Exception):
    """What failed and what to do, printed as the reason the program could not tell."""


def parse_arguments(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--state-directory", type=Path, default=DEFAULT_STATE_DIRECTORY,
                        help=f"holds {AGENT_SEATS_FILE_NAME} and {RELEASED_FILE_NAME} "
                             f"(default: {DEFAULT_STATE_DIRECTORY})")
    parser.add_argument("--record-released", metavar="AGENT_SEAT",
                        help="record AGENT_SEAT as released, once its message is sent")
    return parser.parse_args(argv)


def unreviewed_open_pull_requests_count():
    gh = subprocess.run(
        ["gh", "api", "graphql", "--paginate", "--slurp",
         "-F", f"owner={REPOSITORY_OWNER}", "-F", f"name={REPOSITORY_NAME}",
         "-f", f"query={OPEN_PULL_REQUESTS_QUERY}"],
        capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if gh.returncode != 0:
        error = gh.stderr.strip() or "gh printed no error"
        raise CouldNotTell(f"gh api graphql, reading the open pull requests and their reviews, "
                           f"exited {gh.returncode}: {error}\n"
                           f"{NOTHING_WAITS}\n"
                           f"Run it again once: {PROGRAM_COMMAND}\n"
                           f"If it fails the same way, tell the user: \"No agent-seat holding "
                           f"mutant-test tasks can be released, because gh cannot read the open "
                           f"pull requests on ned-box: {error}\"\n"
                           f"{SUBAGENT_LINE}")
    try:
        pull_requests = [node for page in json.loads(gh.stdout)
                         for node in page["data"]["repository"]["pullRequests"]["nodes"]]
        return sum(1 for node in pull_requests if not node["isDraft"] and not any(
            (review["commit"] or {}).get("oid") == node["headRefOid"]
            for review in node["reviews"]["nodes"]))
    except (ValueError, KeyError, TypeError) as error:
        raise CouldNotTell(f"gh api graphql exited 0 but printed output not in the shape this "
                           f"program reads ({type(error).__name__}: {error}); its first 300 "
                           f"characters: {gh.stdout[:300]!r}\n"
                           f"{NOTHING_WAITS}\n"
                           f"Tell the user: \"The program that releases agent-seats holding "
                           f"mutant-test tasks cannot read gh's answer about the open pull "
                           f"requests, so none is released until it is fixed: {error}\"\n"
                           f"{SUBAGENT_LINE}")


def agent_seats_in_release_order(state_directory):
    path = state_directory / AGENT_SEATS_FILE_NAME
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise CouldNotTell(f"could not read the agent-seats file {path}, which lists the "
                           f"agent-seats holding mutant-test tasks in the order they are "
                           f"released: {error}\n"
                           f"{NOTHING_WAITS}\n"
                           f"If the error names a cause you can fix, fix it and run: "
                           f"{PROGRAM_COMMAND}\n"
                           f"If the file is gone, ask the user which agent-seats hold mutant-test "
                           f"tasks and in what order, write them into {path}, one agent-seat per "
                           f"line, and run: {PROGRAM_COMMAND}\n"
                           f"{SUBAGENT_LINE}")
    return [line.strip() for line in text.splitlines() if line.strip()]


def released_agent_seats(state_directory):
    path = state_directory / RELEASED_FILE_NAME
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return set()
    except (OSError, UnicodeDecodeError) as error:
        raise CouldNotTell(f"could not read the released records {path}, which say which "
                           f"agent-seats were already told they may open their mutant-test pull "
                           f"requests: {error}\n"
                           f"{NOTHING_WAITS}\n"
                           f"If the error names a cause you can fix, fix it and run: "
                           f"{PROGRAM_COMMAND}\n"
                           f"Otherwise tell the user: \"No agent-seat holding mutant-test tasks "
                           f"can be released, because {path} on ned-box cannot be read: "
                           f"{error}\"\n"
                           f"{SUBAGENT_LINE}")
    released = set()
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            released.add(json.loads(line)["agent_seat"])
        except (ValueError, KeyError, TypeError) as error:
            raise CouldNotTell(f"line {number} of the released records {path} is not a JSON "
                               f"object with the key agent_seat ({type(error).__name__}: "
                               f"{error}): {line!r}\n"
                               f"{NOTHING_WAITS}\n"
                               f"Rewrite that line as a JSON object with the key agent_seat, "
                               f"naming the agent-seat it records as released, or delete it when "
                               f"no agent-seat can be read from it; then run: "
                               f"{PROGRAM_COMMAND}")
    return released


def release_recorded(state_directory, agent_seat):
    """Append agent_seat's record unless it is already recorded; return what was done."""
    path = state_directory / RELEASED_FILE_NAME
    seats = agent_seats_in_release_order(state_directory)
    if agent_seat not in seats:
        raise CouldNotTell(f"{agent_seat!r} is not named in "
                           f"{state_directory / AGENT_SEATS_FILE_NAME}, so it is not recorded as "
                           f"released; the file names: {', '.join(seats) or 'no agent-seat'}.\n"
                           f"Run the command with the agent-seat named on the RELEASE line: "
                           f"{PROGRAM_COMMAND} --record-released <agent-seat>")
    if agent_seat in released_agent_seats(state_directory):
        return f"{agent_seat} was already recorded as released in {path}; nothing was written."
    record = {"agent_seat": agent_seat,
              "released_at": datetime.datetime.now(datetime.timezone.utc).strftime(
                  "%Y-%m-%dT%H:%M:%SZ")}
    try:
        with path.open("a", encoding="utf-8") as released:
            released.write(json.dumps(record) + "\n")
    except OSError as error:
        raise CouldNotTell(f"could not record {agent_seat} as released in {path}: {error}\n"
                           f"Until it is recorded, each merge names {agent_seat} for release "
                           f"again, and it may be sent the message twice.\n"
                           f"If the error names a cause you can fix, fix it and run: "
                           f"{PROGRAM_COMMAND} --record-released {agent_seat}\n"
                           f"Otherwise tell the user: \"{agent_seat} has been told it may open "
                           f"its mutant-test pull requests, but {path} on ned-box cannot be "
                           f"written to record that: {error}\"\n"
                           f"{SUBAGENT_LINE}")
    return f"recorded {agent_seat} as released in {path}"


def release_message(count):
    return (f"merge-lane-2's review queue is quiet: {count} open pull requests, not drafts, "
            f"wait for a review from merge-lane-2. You may now open your pull requests that only "
            f"add tests for surviving mutants: one per source file, with at most "
            f"{MUTANT_TEST_PULL_REQUESTS_OPEN_AT_ONCE_AT_MOST} open at a time.")


def release_named_and_printed(state_directory):
    count = unreviewed_open_pull_requests_count()
    counted = (f"{count} open pull requests, not drafts, have no review from {MERGE_LANE_ACCOUNT} "
               f"on their head commit")
    if count > QUIET_REVIEW_QUEUE_MOST_UNREVIEWED_PULL_REQUESTS:
        print(f"{counted}; the review queue is quiet at "
              f"{QUIET_REVIEW_QUEUE_MOST_UNREVIEWED_PULL_REQUESTS} or fewer, so no agent-seat "
              f"holding mutant-test tasks is released.")
        return EXIT_NAMED_NONE
    released = released_agent_seats(state_directory)
    waiting = [seat for seat in agent_seats_in_release_order(state_directory)
               if seat not in released]
    if not waiting:
        print(f"{counted}, but every agent-seat in {state_directory / AGENT_SEATS_FILE_NAME} is "
              f"already recorded as released in {state_directory / RELEASED_FILE_NAME}.")
        return EXIT_NAMED_NONE
    seat = waiting[0]
    record_command = f"{PROGRAM_COMMAND} --record-released {seat}"
    if state_directory != DEFAULT_STATE_DIRECTORY:
        record_command += f" --state-directory {state_directory}"
    print(f"{RELEASE_LINE_PREFIX}{seat}\n"
          f"{counted}. Send {seat} this message with SendMessage, addressed to {seat}:\n"
          f"{release_message(count)}\n"
          f"Once the message is sent, record the release, so the next merge names the next "
          f"agent-seat instead of {seat}: {record_command}")
    return EXIT_NAMED_OR_RECORDED


def main(argv=None):
    arguments = parse_arguments(argv)
    try:
        if arguments.record_released is not None:
            print(release_recorded(arguments.state_directory, arguments.record_released))
            return EXIT_NAMED_OR_RECORDED
        return release_named_and_printed(arguments.state_directory)
    except CouldNotTell as error:
        print(f"could not record {arguments.record_released} as released: {error}"
              if arguments.record_released is not None else
              f"could not tell whether to release an agent-seat holding mutant-test tasks: "
              f"{error}")
    except Exception as error:  # noqa: BLE001 - a crash must exit 2, not Python's 1
        print(f"could not tell whether to release an agent-seat holding mutant-test tasks: "
              f"the program crashed: {type(error).__name__}: {error}\n"
              f"{NOTHING_WAITS}\n"
              f"Run it again once: {PROGRAM_COMMAND}\n"
              f"If it crashes the same way, tell the user: \"The program that releases "
              f"agent-seats holding mutant-test tasks crashes on ned-box, so none is released "
              f"until it is fixed: {type(error).__name__}: {error}\"\n"
              f"{SUBAGENT_LINE}")
    return EXIT_COULD_NOT_TELL


if __name__ == "__main__":
    sys.exit(main())
