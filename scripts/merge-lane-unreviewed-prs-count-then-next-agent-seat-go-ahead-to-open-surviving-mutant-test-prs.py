#!/usr/bin/env python3
"""Release the next agent-seat holding mutant-test tasks when merge-lane-2's review queue is quiet. Exits 0 if it released an agent-seat, 1 if none was due, 2 if it could not tell or the message was not sent.

Usage:
  scripts/merge-lane-unreviewed-prs-count-then-next-agent-seat-go-ahead-to-open-surviving-mutant-test-prs.py
      [--state-directory DIR]

The program counts the open pull requests, not drafts, that have no review
from merge-lane-2 on their newest commit: no GitHub review by the account
ned-review-merge, in any state, whose commit is the pull request's head
commit. When that count is 10 or fewer and the agent-seats file names an
agent-seat not yet recorded as released, the program sends the first such
agent-seat, in the file's order, the release message with the idle sweep's own
send code and prompt, unchanged, from
scripts/agent-seat-idle-sweep-headless-judge-wake-messages-send-and-user-alerts-write.py.
It records the agent-seat as released only when the idle sweep's check of that
send passes and every text sent to the agent-seat is the release message, and
then prints `RELEASED <agent-seat>`; otherwise it prints what failed and
records nothing, so the next run, at the next merge or by hand, tries again.
When no agent-seat is due, it prints the count.

A mutant-test pull request only adds tests for surviving mutants. Such pull
requests stay unopened until the agent-seat holding them is told that the
review queue is quiet; the message says the agent-seat may then open them one
per source file, with at most 5 open at a time.

--state-directory, by default
/home/nedlern/nedsnodes-logs/seats/merge-lane-2/surviving-mutant-test-prs-go-ahead,
holds two files and the sender's empty working directory:
  agent-seats-holding-surviving-mutant-test-tasks-in-go-ahead-order.txt: one
    agent-seat per line, in the order they are released; blank lines are
    ignored. The program only reads it.
  agent-seats-given-surviving-mutant-test-prs-go-ahead.jsonl: one JSON object
    per agent-seat recorded as released, with the keys agent_seat and
    released_at. The program appends to it, and makes it when it is missing.

scripts/merge-lane-pull-request-merge-through-merge-gate-with-stacked-pull-request-retarget.py
runs this program after each merge. gh runs with the environment the program
is given, so with the GH_TOKEN its caller sets.
"""

import argparse
import datetime
import json
import importlib.util
import subprocess
import sys
from pathlib import Path

_sweep_spec = importlib.util.spec_from_file_location(
    "agent_seat_idle_sweep_headless_judge_wake_messages_send_and_user_alerts_write",
    Path(__file__).with_name(
        "agent-seat-idle-sweep-headless-judge-wake-messages-send-and-user-alerts-write.py"))
idle_sweep = importlib.util.module_from_spec(_sweep_spec)
_sweep_spec.loader.exec_module(idle_sweep)

REPOSITORY_OWNER, REPOSITORY_NAME = "nedsnodes", "nedsnodes"
MERGE_LANE_ACCOUNT = "ned-review-merge"
QUIET_REVIEW_QUEUE_MOST_UNREVIEWED_PULL_REQUESTS = 10
MUTANT_TEST_PULL_REQUESTS_OPEN_AT_ONCE_AT_MOST = 5
DEFAULT_STATE_DIRECTORY = Path(
    "/home/nedlern/nedsnodes-logs/seats/merge-lane-2/surviving-mutant-test-prs-go-ahead")
AGENT_SEATS_FILE_NAME = "agent-seats-holding-surviving-mutant-test-tasks-in-go-ahead-order.txt"
RELEASED_FILE_NAME = "agent-seats-given-surviving-mutant-test-prs-go-ahead.jsonl"
RELEASED_LINE_PREFIX = "RELEASED "
# The working directory names the sender the receiving agent-seat sees.
SENDER_WORKING_DIRECTORY_NAME = "merge-lane-2-mutant-test-release"

EXIT_RELEASED = 0
EXIT_NONE_DUE = 1
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
    path = state_directory / RELEASED_FILE_NAME
    record = {"agent_seat": agent_seat,
              "released_at": datetime.datetime.now(datetime.timezone.utc).strftime(
                  "%Y-%m-%dT%H:%M:%SZ")}
    try:
        with path.open("a", encoding="utf-8") as released:
            released.write(json.dumps(record) + "\n")
    except OSError as error:
        raise CouldNotTell(f"{agent_seat} was sent the release message, but it could not be "
                           f"recorded as released in {path}: {error}\n"
                           f"Until it is recorded, each merge sends {agent_seat} the message "
                           f"again.\n"
                           f"Append this line to {path} by hand, once the cause is fixed: "
                           f"{json.dumps(record)}\n"
                           f"If you cannot, tell the user: \"{agent_seat} has been told it may "
                           f"open its mutant-test pull requests, but {path} on ned-box cannot be "
                           f"written to record that: {error}\"\n"
                           f"{SUBAGENT_LINE}")


def release_message_send_problems(state_directory, agent_seat, text):
    """Send text to agent_seat as the idle sweep sends its wake messages; return what failed,
    by the idle sweep's own check and by a comparison of each text sent with the release
    message, or [] when the send passed both."""
    text = f"{text}\n\n{idle_sweep.DO_NOT_REPLY_SENTENCE}"
    prompt = idle_sweep.SENDER_PROMPT.format(
        seat=agent_seat, text=text,
        find_the_entry=idle_sweep.FIND_THE_ENTRY.format(seat=agent_seat),
        keep_the_last_sentence=idle_sweep.KEEP_THE_LAST_SENTENCE)
    outcome = idle_sweep.run_headless(prompt, idle_sweep.SEND_ANSWER_SCHEMA,
                                      idle_sweep.SENDING_TOOLS,
                                      state_directory / SENDER_WORKING_DIRECTORY_NAME,
                                      idle_sweep.HEADLESS_TIMEOUT_SECONDS)
    if outcome.error:
        return [f"the headless agent-session that sends the message failed: {outcome.error}"]
    return idle_sweep.send_problems(outcome, [agent_seat]) + [
        f"sent {seat} a text other than the release message: {sent_text!r}"
        for seat, sent_text in idle_sweep.sent_texts_other_than_code_wrote(
            outcome, [agent_seat], text)]


def release_message(count):
    return (f"merge-lane-2's review queue is quiet: {count} open pull requests, not drafts, "
            f"wait for a review from merge-lane-2. You may now open your pull requests that only "
            f"add tests for surviving mutants: one per source file, with at most "
            f"{MUTANT_TEST_PULL_REQUESTS_OPEN_AT_ONCE_AT_MOST} open at a time.")


def release_named_and_sent(state_directory):
    count = unreviewed_open_pull_requests_count()
    counted = (f"{count} open pull requests, not drafts, have no review from {MERGE_LANE_ACCOUNT} "
               f"on their head commit")
    if count > QUIET_REVIEW_QUEUE_MOST_UNREVIEWED_PULL_REQUESTS:
        print(f"{counted}; the review queue is quiet at "
              f"{QUIET_REVIEW_QUEUE_MOST_UNREVIEWED_PULL_REQUESTS} or fewer, so no agent-seat "
              f"holding mutant-test tasks is released.")
        return EXIT_NONE_DUE
    released = released_agent_seats(state_directory)
    waiting = [seat for seat in agent_seats_in_release_order(state_directory)
               if seat not in released]
    if not waiting:
        print(f"{counted}, but every agent-seat in {state_directory / AGENT_SEATS_FILE_NAME} is "
              f"already recorded as released in {state_directory / RELEASED_FILE_NAME}.")
        return EXIT_NONE_DUE
    seat = waiting[0]
    problems = release_message_send_problems(state_directory, seat, release_message(count))
    if problems:
        print(f"{counted}, so {seat} is due for release, but the release message was not sent: "
              f"{'; '.join(problems)}.\n"
              f"Nothing was recorded, so the next merge tries again. To try now, run: "
              f"{PROGRAM_COMMAND}\n"
              f"If it fails the same way, and the failure says claude is logged out on ned-box, "
              f"tell the user so; otherwise tell the user: \"The release message to {seat} "
              f"cannot be sent from ned-box: {'; '.join(problems)}\"\n"
              f"{SUBAGENT_LINE}")
        return EXIT_COULD_NOT_TELL
    release_recorded(state_directory, seat)
    print(f"{RELEASED_LINE_PREFIX}{seat}\n"
          f"{counted}. {seat} was sent this message, and is recorded as released in "
          f"{state_directory / RELEASED_FILE_NAME}:\n"
          f"{release_message(count)}")
    return EXIT_RELEASED


def main(argv=None):
    arguments = parse_arguments(argv)
    try:
        return release_named_and_sent(arguments.state_directory)
    except CouldNotTell as error:
        print(f"could not tell whether to release an agent-seat holding mutant-test tasks: "
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
