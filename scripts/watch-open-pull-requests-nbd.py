#!/usr/bin/env python3
"""Watch open pull requests and emit flushed OPENED and NEW-HEAD events.

The first successful poll establishes a silent baseline unless --from-start
is set. Failed polls preserve state and announce blindness; activity that
opens and closes between successful polls cannot be recovered.

Polling needs no public webhook endpoint. GraphQL selects only needed fields
and avoids gh versions’ differing --json field lists.

With --track-who-each-open-pull-request-waits-on it prints no OPENED or
NEW-HEAD lines. Instead it keeps, in a JSON state file in the log-store, one
entry per open pull request: who it waits on and since when. Who it waits on:
- a line "- PR <number> waits on <who>: <reason>" in merge-lane-2's
  merge-holds.md names the user, merge-lane-2 or another agent-seat, and wins;
  the time the hold was first seen is its "since";
- otherwise a draft, or a branch GitHub reports CONFLICTING, waits on its
  author, by GitHub account, since first seen;
- otherwise the latest APPROVED or CHANGES_REQUESTED review from
  --reviewer-login decides, or, on a pull request that account opened, from
  any other account: changes requested on the head commit wait on the author
  since that review; approval of the head commit waits on merge-lane-2 to
  merge; any other head commit waits on merge-lane-2 to review it, since the
  latest of the pull request's opening, the head commit's commit time and that
  review.
It prints one line, naming the pull request, its title, who it waits on, since
when and why, when a pull request opens, gets a new head commit, a review or a
comment, or closes; when one waits on merge-lane-2 and five minutes pass
after it began waiting or after its last such line; and when one waits on an
author or agent-seat and has been quiet for 30 minutes, and every 30 quiet
minutes after. A wait on the user is never reminded. The first invocation
without a state file lists every open pull request. A restart compares with
the saved state, so changes while it was stopped are reported then.

It does not handle: a merge-holds.md line in another form, which it reports
once and ignores; a reply to an inline review thread that GitHub does not
count as a new review; two invocations sharing one state file, which repeat
or lose each other's reminders; which agent-seat works for a GitHub account,
which only merge-holds.md can say. A query failure prints a BLIND line, again
every ten minutes it lasts, and a line on recovery. A state file it cannot
read or parse is reported and treated as missing; one it cannot write is
reported once, and the next invocation repeats what this one reported. It
reads GitHub and merge-holds.md and writes only its state file."""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_REPO = "nedschorus/nedschorus"
DEFAULT_POLL_SECONDS = 60.0
DEFAULT_TOKEN_FILE = "~/.config/nedschorus/ned-review-merge.token"

# GitHub caps GraphQL pages at 100; bound page count to prevent an endless pagination loop.
PAGE_SIZE = 100
MAX_PAGES = 10

# Bound hung queries so the watcher can announce blindness.
GH_QUERY_TIMEOUT_SECONDS = 30.0

# Use an exit code gh cannot return to distinguish failure to run from a completed query.
GH_DID_NOT_RUN = -1

HEAD_SHA_PREFIX_CHARS = 8
TITLE_SNIPPET_CHARS = 120
FAILURE_REASON_SNIPPET_CHARS = 300

# A short redaction pattern would corrupt ordinary output; reject invalid credentials at startup.
MINIMUM_PLAUSIBLE_TOKEN_CHARS = 8

OPEN_PULL_REQUESTS_QUERY = """
query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequests(states: OPEN, first: %d, after: $cursor,
                 orderBy: {field: CREATED_AT, direction: ASC}) {
      nodes {
        number
        title
        isDraft
        headRefOid
        author { login }
      }
      pageInfo { hasNextPage endCursor }
    }
  }
}
""" % PAGE_SIZE

# Redact every output path, including quoted gh stderr.
SECRETS_TO_REDACT = []


def redact_secrets(text):
    for secret in SECRETS_TO_REDACT:
        text = text.replace(secret, "[REDACTED]")
    return text


def emit(line):
    # Flush immediately so a buffered event cannot look like an inactive watch.
    print(redact_secrets(line), flush=True)


def warn(line):
    print(redact_secrets(line), file=sys.stderr, flush=True)


def one_line_snippet(text, limit):
    """Return a redacted, single-line snippet bounded by limit."""
    # Redact before truncation: a partial token no longer matches the whole-token redactor.
    return " ¶ ".join(redact_secrets(str(text)).strip().splitlines())[:limit]


def read_token(token_file: Path):
    """Return (token, None) or (None, reason), never including file contents in errors."""
    try:
        token = token_file.read_text(encoding="utf-8", errors="replace").strip()
    except OSError as error:
        return None, (f"cannot read the token file {token_file}: "
                      f"{error.strerror or type(error).__name__}")
    if len(token) < MINIMUM_PLAUSIBLE_TOKEN_CHARS:
        return None, (f"the token file {token_file} holds {len(token)} "
                      f"characters after stripping whitespace, which is not "
                      f"a GitHub token")
    return token, None


def run_gh(arguments, token, timeout=GH_QUERY_TIMEOUT_SECONDS):
    """Run gh with the credential in the environment and return its own exit status and output."""
    # Keep the token out of argv, which process listings and command errors can expose.
    environment = dict(os.environ)
    environment["GH_TOKEN"] = token
    try:
        return subprocess.run(["gh", *arguments], capture_output=True, text=True,
                              check=False, timeout=timeout, env=environment)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            arguments, GH_DID_NOT_RUN, "",
            f"gh did not answer within {timeout:g}s")
    except (OSError, subprocess.SubprocessError) as error:
        return subprocess.CompletedProcess(
            arguments, GH_DID_NOT_RUN, "", f"{type(error).__name__}: {error}")


def pull_request_from_node(node):
    """Return (pull_request, None) or (None, reason) for an invalid node."""
    # Dropping a malformed node would falsely report the pull request as newly opened at the next poll.
    if not isinstance(node, dict):
        return None, "a pull request came back as JSON that is not an object"
    number = node.get("number")
    head_sha = node.get("headRefOid")
    if not isinstance(number, int):
        return None, "a pull request came back with no usable number"
    if not isinstance(head_sha, str) or not head_sha:
        return None, f"pull request #{number} came back with no head commit sha"
    author = node.get("author")
    return {
        "number": number,
        "head_sha": head_sha,
        "title": node.get("title") or "",
        "is_draft": bool(node.get("isDraft")),
        # GitHub returns null authors for deleted accounts.
        "author": (author or {}).get("login") or "(unknown)",
    }, None


def fetch_open_pull_requests(repo, token, query=OPEN_PULL_REQUESTS_QUERY,
                             node_reader=None):
    """Return (all_open_pull_requests, None) or (None, reason); never return partial results.

    node_reader turns one GraphQL node into (pull_request, None) or (None, reason);
    the default is pull_request_from_node."""
    node_reader = node_reader or pull_request_from_node
    owner, _, name = repo.partition("/")
    pull_requests = []
    cursor = None
    for _ in range(MAX_PAGES):
        arguments = ["api", "graphql",
                     "-f", f"query={query}",
                     "-f", f"owner={owner}", "-f", f"name={name}"]
        if cursor:
            arguments += ["-f", f"cursor={cursor}"]
        result = run_gh(arguments, token)
        if result.returncode != 0:
            reason = (result.stderr or result.stdout or "").strip()
            return None, reason or f"gh exited {result.returncode} with no message"
        try:
            payload = json.loads(result.stdout)
        except (json.JSONDecodeError, ValueError) as error:
            return None, f"gh returned unparseable JSON: {error}"
        if not isinstance(payload, dict):
            return None, "gh returned JSON that is not an object"
        # GraphQL can return HTTP 200 with errors and partial data; reject the whole poll.
        if payload.get("errors"):
            return None, f"GraphQL error: {payload['errors']}"
        try:
            connection = payload["data"]["repository"]["pullRequests"]
            nodes = connection["nodes"]
            page_info = connection["pageInfo"]
        except (KeyError, TypeError) as error:
            return None, f"unexpected response shape: {type(error).__name__} {error}"
        if not isinstance(nodes, list) or not isinstance(page_info, dict):
            return None, "unexpected response shape: nodes or pageInfo missing"
        for node in nodes:
            pull_request, reason = node_reader(node)
            if reason is not None:
                return None, reason
            pull_requests.append(pull_request)
        if not page_info.get("hasNextPage"):
            return pull_requests, None
        cursor = page_info.get("endCursor")
        if not cursor:
            return None, "another page was reported but no cursor came with it"
    return None, (f"gave up after {MAX_PAGES} pages ({len(pull_requests)} pull "
                  f"requests) — pagination did not end")


def event_line(pull_request, event_name):
    draft_marker = " [draft]" if pull_request["is_draft"] else ""
    return (f"PR #{pull_request['number']} {event_name} "
            f"{pull_request['head_sha'][:HEAD_SHA_PREFIX_CHARS]} "
            f"{pull_request['author']}{draft_marker}: "
            f"{one_line_snippet(pull_request['title'], TITLE_SNIPPET_CHARS)}")


def events_for_poll(known_head_shas, pull_requests):
    """Return events from changes to (number, head_sha) since the last successful poll."""
    lines = []
    for pull_request in pull_requests:
        seen_head_sha = known_head_shas.get(pull_request["number"])
        if seen_head_sha is None:
            lines.append(event_line(pull_request, "OPENED"))
        elif seen_head_sha != pull_request["head_sha"]:
            lines.append(event_line(pull_request, "NEW-HEAD"))
    return lines


def head_shas_by_number(pull_requests):
    return {pull_request["number"]: pull_request["head_sha"]
            for pull_request in pull_requests}


def baseline_line(repo, poll_seconds, pull_requests, from_start):
    numbers = " ".join(f"#{pull_request['number']}"
                       for pull_request in pull_requests)
    what_happens_next = ("each reported below as OPENED" if from_start
                         else "not events; --from-start reports them")
    return (f"WATCH: watching {repo} every {poll_seconds:g}s; "
            f"{len(pull_requests)} open at baseline"
            f"{': ' + numbers if numbers else ''} "
            f"({what_happens_next})")


# ---------------------------------------------------------------------------
# --track-who-each-open-pull-request-waits-on, and its reminders.
# ---------------------------------------------------------------------------

MERGE_AGENT_SEAT = "merge-lane-2"
DEFAULT_REVIEWER_LOGIN = "ned-review-merge"
MERGE_AGENT_SEAT_LOG_STORE_DIRECTORY = Path(
    "/home/nedlern/nedschorus-logs/seats/merge-lane-2")
DEFAULT_WAITS_ON_STATE_FILE = (MERGE_AGENT_SEAT_LOG_STORE_DIRECTORY
                               / "who-each-open-pull-request-waits-on.json")
DEFAULT_MERGE_HOLDS_FILE = MERGE_AGENT_SEAT_LOG_STORE_DIRECTORY / "merge-holds.md"
QUEUE_STATE_VERSION = 1

MERGE_AGENT_SEAT_REMINDER_SECONDS = 5 * 60
AUTHOR_OR_AGENT_SEAT_QUIET_SECONDS = 30 * 60
# Shorter than the Monitor tool's 30-minute expiry, so a long outage is
# re-reported within each invocation, not only at its start.
BLIND_REMINDER_SECONDS = 10 * 60

# Who a pull request waits on; the kind decides which reminder applies.
WAITS_ON_MERGE_AGENT_SEAT = "merge-agent-seat"
WAITS_ON_AUTHOR = "author"
WAITS_ON_AGENT_SEAT = "agent-seat"
WAITS_ON_USER = "user"

# Enough to hold the latest decisive review on any pull request this project
# has had; an older one beyond it only changes the wording of the reason.
REVIEWS_SCANNED = 50

QUEUE_QUERY = """
query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequests(states: OPEN, first: %d, after: $cursor,
                 orderBy: {field: CREATED_AT, direction: ASC}) {
      nodes {
        number
        title
        isDraft
        headRefOid
        createdAt
        mergeable
        author { login }
        comments { totalCount }
        reviews(last: %d) {
          totalCount
          nodes { state submittedAt author { login } commit { oid } }
        }
        commits(last: 1) { nodes { commit { committedDate } } }
      }
      pageInfo { hasNextPage endCursor }
    }
  }
}
""" % (PAGE_SIZE, REVIEWS_SCANNED)

# Only list items opening "- PR " are holds; the rest of merge-holds.md is prose for its reader.
HOLD_LIST_ITEM_OPENING = "- PR "
HOLD_LINE_PATTERN = re.compile(r"^- PR (\d+) waits on ([a-z0-9][a-z0-9-]*): (\S.*)$")

QUEUE_ENTRY_FIELD_TYPES = {
    "title": str, "head_sha": str, "review_count": int, "comment_count": int,
    "kind": str, "party": str, "reason": str, "since": (int, float),
    "last_activity": (int, float), "reminded_wait": str,
    "last_reminded": (int, float),
}


def queue_pull_request_from_node(node):
    """Return (pull_request, None) or (None, reason), with the fields --queue-monitor needs."""
    pull_request, reason = pull_request_from_node(node)
    if reason is not None:
        return None, reason
    number = pull_request["number"]
    try:
        comment_count = node["comments"]["totalCount"]
        review_count = node["reviews"]["totalCount"]
        review_nodes = node["reviews"]["nodes"]
        commit_nodes = node["commits"]["nodes"]
    except (KeyError, TypeError):
        return None, (f"pull request #{number} came back without its comment "
                      f"count, reviews or commits")
    if not (isinstance(comment_count, int) and isinstance(review_count, int)
            and isinstance(review_nodes, list) and isinstance(commit_nodes, list)):
        return None, (f"pull request #{number} came back with comment count, "
                      f"reviews or commits of the wrong JSON type")
    reviews = []
    for review in review_nodes:
        if not isinstance(review, dict):
            return None, f"pull request #{number} has a review that is not a JSON object"
        # A pending review is unsubmitted and decides nothing.
        if review.get("state") == "PENDING":
            continue
        reviews.append({
            "login": (review.get("author") or {}).get("login") or "(unknown)",
            "state": review.get("state") or "",
            "submitted_at": review.get("submittedAt") or "",
            "commit": (review.get("commit") or {}).get("oid") or ""})
    head_committed_at = ""
    if commit_nodes and isinstance(commit_nodes[-1], dict):
        head_committed_at = (commit_nodes[-1].get("commit") or {}).get(
            "committedDate") or ""
    pull_request.update({
        "created_at": node.get("createdAt") or "",
        "mergeable": node.get("mergeable") or "UNKNOWN",
        "comment_count": comment_count,
        "review_count": review_count,
        "reviews": reviews,
        "head_committed_at": head_committed_at,
    })
    return pull_request, None


def github_time_seconds(text):
    """Return the epoch seconds of a GitHub timestamp, or None when there is none."""
    if not text:
        return None
    try:
        return datetime.datetime.fromisoformat(
            text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def utc_minute_text(seconds):
    return datetime.datetime.fromtimestamp(
        seconds, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def duration_text(seconds):
    minutes = max(0, int(seconds // 60))
    days, minutes = divmod(minutes, 24 * 60)
    hours, minutes = divmod(minutes, 60)
    if days:
        return f"{days}d{hours}h"
    if hours:
        return f"{hours}h{minutes}m"
    return f"{minutes}m"


def read_holds(hold_file):
    """Return ({number: (waits_on, reason)}, [problem, ...]); a missing file holds nothing."""
    try:
        text = hold_file.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return {}, []
    except OSError as error:
        return {}, [f"cannot read the merge holds file {hold_file}: "
                    f"{error.strerror or type(error).__name__}, so no hold in it applies"]
    holds = {}
    problems = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped.startswith(HOLD_LIST_ITEM_OPENING):
            continue
        match = HOLD_LINE_PATTERN.match(stripped)
        if match is None:
            problems.append(
                f"{hold_file} line {line_number} is not "
                f"'- PR <number> waits on <user, or an agent-seat's name>: <reason>', "
                f"so it holds nothing: {one_line_snippet(stripped, TITLE_SNIPPET_CHARS)}")
            continue
        number = int(match.group(1))
        if number in holds:
            problems.append(f"{hold_file} line {line_number} holds #{number} a "
                            f"second time and is ignored; the first line for "
                            f"#{number} applies")
            continue
        holds[number] = (match.group(2), match.group(3).strip())
    return holds, problems


def waiting_state(pull_request, hold, reviewer_login):
    """Return (kind, party, reason, since) for one pull request.

    since is a GitHub timestamp when GitHub shows when the wait began, else ""."""
    author = pull_request["author"]
    head_sha = pull_request["head_sha"]
    short_head = head_sha[:HEAD_SHA_PREFIX_CHARS]
    if hold is not None:
        waits_on, reason = hold
        if waits_on == "user":
            return WAITS_ON_USER, "the user", f"held: {reason}", ""
        if waits_on == MERGE_AGENT_SEAT:
            return WAITS_ON_MERGE_AGENT_SEAT, MERGE_AGENT_SEAT, f"held: {reason}", ""
        return WAITS_ON_AGENT_SEAT, f"agent-seat {waits_on}", f"held: {reason}", ""
    author_party = f"the author, GitHub account {author}"
    if pull_request["is_draft"]:
        return WAITS_ON_AUTHOR, author_party, "the pull request is a draft", ""
    if pull_request["mergeable"] == "CONFLICTING":
        return WAITS_ON_AUTHOR, author_party, "its branch conflicts with main", ""
    # The reviewer account cannot approve its own pull request; another account's review decides those.
    deciders = ((lambda login: login != reviewer_login) if author == reviewer_login
                else (lambda login: login == reviewer_login))
    decisive = [review for review in pull_request["reviews"]
                if deciders(review["login"])
                and review["state"] in ("APPROVED", "CHANGES_REQUESTED")]
    latest = decisive[-1] if decisive else None
    if latest is not None and latest["commit"] == head_sha:
        if latest["state"] == "CHANGES_REQUESTED":
            return (WAITS_ON_AUTHOR, author_party,
                    f"{latest['login']} requested changes on head commit {short_head}",
                    latest["submitted_at"])
        return (WAITS_ON_MERGE_AGENT_SEAT, MERGE_AGENT_SEAT,
                f"{latest['login']} approved head commit {short_head}: merge it",
                latest["submitted_at"])
    candidates = [pull_request["created_at"], pull_request["head_committed_at"]]
    if latest is not None:
        candidates.append(latest["submitted_at"])
    since = max(candidates, key=lambda text: github_time_seconds(text) or 0)
    if latest is not None and latest["state"] == "CHANGES_REQUESTED":
        return (WAITS_ON_MERGE_AGENT_SEAT, MERGE_AGENT_SEAT,
                f"head commit {short_head} came after {latest['login']} requested "
                f"changes: review the fix-round", since)
    return (WAITS_ON_MERGE_AGENT_SEAT, MERGE_AGENT_SEAT,
            f"head commit {short_head} has no approving or changes-requested "
            f"review: review it", since)


def queue_line(number, what, title, entry, now):
    return (f"PR #{number} {what}: \"{one_line_snippet(title, TITLE_SNIPPET_CHARS)}\"; "
            f"waits on {entry['party']} since {utc_minute_text(entry['since'])} "
            f"({duration_text(now - entry['since'])}): {entry['reason']}")


def what_changed(old, pull_request):
    """Return the words for what changed on a known pull request, or [] when nothing did."""
    changes = []
    if old["head_sha"] != pull_request["head_sha"]:
        changes.append(f"PUSHED {pull_request['head_sha'][:HEAD_SHA_PREFIX_CHARS]}")
    if pull_request["review_count"] > old["review_count"]:
        newest = pull_request["reviews"][-1] if pull_request["reviews"] else None
        changes.append("REVIEWED" + (f" by {newest['login']} ({newest['state']})"
                                     if newest else ""))
    if pull_request["comment_count"] > old["comment_count"]:
        changes.append("COMMENTED")
    return changes


def queue_poll(old_entries, pull_requests, holds, now, reviewer_login,
               list_every_pull_request):
    """Return (lines, entries, hold_problems) for one successful poll.

    old_entries and entries map the pull request number, as a string, to its saved line.
    With list_every_pull_request, every open pull request is printed as IN-QUEUE
    and counts as reminded, which is how a first invocation reports the queue."""
    lines = []
    entries = {}
    open_numbers = set()
    for pull_request in sorted(pull_requests, key=lambda item: item["number"]):
        number = pull_request["number"]
        open_numbers.add(number)
        old = old_entries.get(str(number))
        kind, party, reason, since_text = waiting_state(
            pull_request, holds.get(number), reviewer_login)
        wait = f"{kind}|{party}|{reason}"
        since = github_time_seconds(since_text)
        if since is None:
            same_wait = old is not None and (
                f"{old['kind']}|{old['party']}|{old['reason']}" == wait)
            since = old["since"] if same_wait else now
        if list_every_pull_request:
            changes = []
        elif old is None:
            changes = ["OPENED"]
        else:
            changes = what_changed(old, pull_request)
        entry = {
            "title": pull_request["title"],
            "head_sha": pull_request["head_sha"],
            "review_count": pull_request["review_count"],
            "comment_count": pull_request["comment_count"],
            "kind": kind, "party": party, "reason": reason, "since": since,
            "last_activity": now if (changes or old is None) else old["last_activity"],
            "reminded_wait": old["reminded_wait"] if old else "",
            "last_reminded": old["last_reminded"] if old else 0,
        }
        if list_every_pull_request:
            lines.append(queue_line(number, "IN-QUEUE", pull_request["title"], entry, now))
            entry["reminded_wait"] = wait
            entry["last_reminded"] = now
        elif changes:
            lines.append(queue_line(number, " ".join(changes), pull_request["title"],
                                    entry, now))
        elif (kind == WAITS_ON_MERGE_AGENT_SEAT
              # A commit's time can precede its push; the event line woke merge-lane-2 then.
              and now - max(since, entry["last_activity"]) >= MERGE_AGENT_SEAT_REMINDER_SECONDS
              and entry["reminded_wait"] != wait):
            lines.append(queue_line(
                number, f"STALE, waiting on {MERGE_AGENT_SEAT} for "
                        f"{duration_text(now - since)}",
                pull_request["title"], entry, now))
            entry["reminded_wait"] = wait
            entry["last_reminded"] = now
        elif kind in (WAITS_ON_AUTHOR, WAITS_ON_AGENT_SEAT):
            quiet_since = max(since, entry["last_activity"], entry["last_reminded"])
            if now - quiet_since >= AUTHOR_OR_AGENT_SEAT_QUIET_SECONDS:
                quiet_for = now - max(since, entry["last_activity"])
                lines.append(queue_line(
                    number, f"QUIET for {duration_text(quiet_for)}, remind {party}",
                    pull_request["title"], entry, now))
                entry["last_reminded"] = now
        entries[str(number)] = entry
    for key, old in sorted(old_entries.items(), key=lambda item: int(item[0])):
        if key not in entries:
            lines.append(f"PR #{key} CLOSED: \"{one_line_snippet(old['title'], TITLE_SNIPPET_CHARS)}\" "
                         f"is no longer open (merged or closed); it waited on "
                         f"{old['party']}: {old['reason']}")
    hold_problems = [f"#{number} is held, but is not an open pull request; "
                     f"remove its line"
                     for number in sorted(holds) if number not in open_numbers]
    return lines, entries, hold_problems


def load_queue_state(state_file):
    """Return (state, None), (None, None) when there is no state file, or (None, problem)."""
    try:
        text = state_file.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None, None
    except (OSError, UnicodeDecodeError) as error:
        return None, (f"cannot read the state file {state_file}: "
                      f"{getattr(error, 'strerror', None) or type(error).__name__}")
    try:
        state = json.loads(text)
    except ValueError as error:
        return None, f"the state file {state_file} is not JSON: {error}"
    entries = state.get("pull_requests") if isinstance(state, dict) else None
    if (not isinstance(state, dict) or state.get("version") != QUEUE_STATE_VERSION
            or not isinstance(entries, dict)
            or not isinstance(state.get("hold_problems"), list)
            or not all(key.isdigit() and isinstance(entry, dict)
                       and all(isinstance(entry.get(field), kinds)
                               for field, kinds in QUEUE_ENTRY_FIELD_TYPES.items())
                       for key, entry in entries.items())):
        return None, (f"the state file {state_file} is not version "
                      f"{QUEUE_STATE_VERSION} queue state")
    return state, None


def save_queue_state(state_file, state):
    """Write the state whole or not at all; return None or the problem."""
    temporary = state_file.with_name(state_file.name + ".partial")
    try:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(json.dumps(state, indent=1, sort_keys=True),
                             encoding="utf-8")
        temporary.replace(state_file)
    except OSError as error:
        return (f"cannot write the state file {state_file}: "
                f"{error.strerror or type(error).__name__}")
    return None


def queue_summary(entries):
    counts = {}
    for entry in entries.values():
        counts[entry["party"]] = counts.get(entry["party"], 0) + 1
    return "; ".join(f"{count} wait on {party}"
                     for party, count in sorted(counts.items(),
                                                key=lambda item: (-item[1], item[0])))


def run_queue_monitor(arguments, token):
    state_file = Path(arguments.who_each_open_pull_request_waits_on_state_file).expanduser()
    hold_file = Path(arguments.merge_holds_pull_request_list_file).expanduser()
    state, state_problem = load_queue_state(state_file)
    if state_problem is not None:
        emit(f"WAITS-ON: {state_problem}; so every open pull request is "
             f"listed below as on a first invocation")
    list_every_pull_request = state is None or arguments.print_who_each_open_pull_request_waits_on_and_exit
    old_entries = state["pull_requests"] if state else {}
    reported_hold_problems = state["hold_problems"] if state else []
    reported_state_write_problem = None
    blind_since = None
    last_blind_report = None
    failed_polls = 0

    while True:
        pull_requests, reason = fetch_open_pull_requests(
            arguments.repo, token, QUEUE_QUERY, queue_pull_request_from_node)
        now = time.time()
        if reason is not None:
            if arguments.print_who_each_open_pull_request_waits_on_and_exit:
                emit("WAITS-ON: GitHub query failed, so no queue is printed: "
                     + one_line_snippet(reason, FAILURE_REASON_SNIPPET_CHARS))
                return 1
            failed_polls += 1
            if blind_since is None:
                blind_since = last_blind_report = now
                emit("WAITS-ON: GitHub query failed, so this monitor is BLIND "
                     "until it recovers; what changed meanwhile is reported then: "
                     + one_line_snippet(reason, FAILURE_REASON_SNIPPET_CHARS))
            elif now - last_blind_report >= BLIND_REMINDER_SECONDS:
                last_blind_report = now
                emit(f"WAITS-ON: still BLIND after {failed_polls} failed "
                     f"polls over {duration_text(now - blind_since)}; latest failure: "
                     + one_line_snippet(reason, FAILURE_REASON_SNIPPET_CHARS))
            time.sleep(arguments.poll_seconds)
            continue
        if blind_since is not None:
            emit(f"WAITS-ON: GitHub query recovered after {failed_polls} "
                 f"failed polls over {duration_text(now - blind_since)}")
            blind_since = None
            failed_polls = 0

        holds, hold_problems = read_holds(hold_file)
        lines, entries, unopened_hold_problems = queue_poll(
            old_entries, pull_requests, holds, now, arguments.reviewer_login,
            list_every_pull_request)
        hold_problems += unopened_hold_problems
        if list_every_pull_request:
            emit(f"WAITS-ON: {len(entries)} open pull requests in "
                 f"{arguments.repo}" + (f": {queue_summary(entries)}" if entries else ""))
        for line in lines:
            emit(line)
        if hold_problems != reported_hold_problems or (
                list_every_pull_request and hold_problems):
            for problem in hold_problems:
                emit(f"WAITS-ON: merge holds file: {problem}")
            if not hold_problems:
                emit(f"WAITS-ON: merge holds file: every line in {hold_file} is "
                     f"well-formed again")
        if arguments.print_who_each_open_pull_request_waits_on_and_exit:
            return 0
        reported_hold_problems = hold_problems
        old_entries = entries
        list_every_pull_request = False

        write_problem = save_queue_state(state_file, {
            "version": QUEUE_STATE_VERSION, "pull_requests": entries,
            "hold_problems": hold_problems})
        if write_problem != reported_state_write_problem:
            emit(f"WAITS-ON: {write_problem}; the next invocation will "
                 f"report again what this one reported" if write_problem else
                 f"WAITS-ON: the state file {state_file} is written again")
            reported_state_write_problem = write_problem
        time.sleep(arguments.poll_seconds)


def parse_arguments(argv):
    parser = argparse.ArgumentParser(
        description="Watch a repository's open pull requests; print one "
                    "line per newly opened pull request and per new head "
                    "commit on an open one.")
    parser.add_argument("--repo", default=DEFAULT_REPO,
                        help=f"OWNER/NAME to watch (default: {DEFAULT_REPO})")
    parser.add_argument("--poll-seconds", type=float, default=DEFAULT_POLL_SECONDS,
                        help=f"seconds between queries (default: "
                             f"{DEFAULT_POLL_SECONDS:g}; one request each, "
                             f"against an authenticated 5,000/hour limit)")
    parser.add_argument("--token-file", default=DEFAULT_TOKEN_FILE,
                        help=f"file holding the GitHub token, passed to gh as "
                             f"GH_TOKEN and never printed (default: "
                             f"{DEFAULT_TOKEN_FILE})")
    parser.add_argument("--from-start", action="store_true",
                        help="report every pull request already open at the "
                             "first poll as OPENED, instead of taking them "
                             "as the silent baseline")
    parser.add_argument("--exit-after-first-poll-with-events", action="store_true",
                        help="exit 0 after the first poll that prints an "
                             "OPENED or NEW-HEAD line, once every event of "
                             "that poll is printed")
    parser.add_argument("--track-who-each-open-pull-request-waits-on",
                        action="store_true",
                        help="instead of OPENED and NEW-HEAD lines, keep a line of "
                             "state per open pull request saying who it waits on "
                             "and since when, and print a line when one opens, is "
                             "pushed to, is reviewed or commented on, closes, or "
                             "goes stale; the top of this file says when")
    parser.add_argument("--who-each-open-pull-request-waits-on-state-file",
                        default=str(DEFAULT_WAITS_ON_STATE_FILE),
                        help=f"where that mode keeps its state between "
                             f"invocations (default: {DEFAULT_WAITS_ON_STATE_FILE})")
    parser.add_argument("--merge-holds-pull-request-list-file",
                        default=str(DEFAULT_MERGE_HOLDS_FILE),
                        help=f"the merge agent-seat's list of held pull requests; "
                             f"a line '- PR <number> waits on <user, or an "
                             f"agent-seat's name>: <reason>' sets who that pull "
                             f"request waits on (default: {DEFAULT_MERGE_HOLDS_FILE})")
    parser.add_argument("--print-who-each-open-pull-request-waits-on-and-exit",
                        action="store_true",
                        help="with --track-who-each-open-pull-request-waits-on: "
                             "print one line per open pull request, change no "
                             "state, and exit 0, or 1 when GitHub cannot be asked")
    parser.add_argument("--reviewer-login", default=DEFAULT_REVIEWER_LOGIN,
                        help=f"the GitHub account whose approving or "
                             f"changes-requested review decides who a pull "
                             f"request waits on (default: {DEFAULT_REVIEWER_LOGIN})")
    return parser.parse_args(argv)


def main(argv=None):
    arguments = parse_arguments(argv)
    if arguments.poll_seconds <= 0:
        warn("watch-open-pull-requests-nbd: --poll-seconds must be > 0")
        return 2
    owner, slash, name = arguments.repo.partition("/")
    if not (owner and slash and name) or "/" in name:
        warn(f"watch-open-pull-requests-nbd: --repo must be OWNER/NAME, "
             f"not {arguments.repo!r}")
        return 2
    token, reason = read_token(Path(arguments.token_file).expanduser())
    if reason is not None:
        warn(f"watch-open-pull-requests-nbd: {reason}")
        return 2
    SECRETS_TO_REDACT.append(token)

    # Author-supplied titles must not kill the watch on an unencodable character.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")

    if arguments.track_who_each_open_pull_request_waits_on:
        return run_queue_monitor(arguments, token)
    if arguments.print_who_each_open_pull_request_waits_on_and_exit:
        warn("watch-open-pull-requests-nbd: "
             "--print-who-each-open-pull-request-waits-on-and-exit needs "
             "--track-who-each-open-pull-request-waits-on")
        return 2

    known_head_shas = None
    blind_since = None
    failed_polls = 0

    while True:
        pull_requests, reason = fetch_open_pull_requests(arguments.repo, token)
        if reason is not None:
            failed_polls += 1
            if blind_since is None:
                blind_since = time.monotonic()
                emit("WATCH: query failed, so this watch is BLIND until it "
                     "recovers (nothing is being seen; the recovery line "
                     "below flags anything the blindness cost): "
                     + one_line_snippet(reason, FAILURE_REASON_SNIPPET_CHARS))
            time.sleep(arguments.poll_seconds)
            continue

        if blind_since is not None:
            # Before the first baseline, outage openings cannot be distinguished from already-open pull requests.
            # --from-start reports all of them, so no loss warning applies.
            lost_openings_silently = (known_head_shas is None
                                      and not arguments.from_start)
            emit(f"WATCH: query recovered after {failed_polls} failed poll(s), "
                 f"about {time.monotonic() - blind_since:.0f}s blind"
                 + (" — and this watch had NO BASELINE yet, so anything that "
                    "opened during that blindness is absorbed into the "
                    "baseline below and gets no OPENED line (re-run with "
                    "--from-start to have the baseline reported as events)"
                    if lost_openings_silently else ""))
            blind_since = None
            failed_polls = 0

        if known_head_shas is None:
            emit(baseline_line(arguments.repo, arguments.poll_seconds,
                               pull_requests, arguments.from_start))
            known_head_shas = ({} if arguments.from_start
                               else head_shas_by_number(pull_requests))

        event_lines = events_for_poll(known_head_shas, pull_requests)
        for line in event_lines:
            emit(line)
        if event_lines and arguments.exit_after_first_poll_with_events:
            return 0
        # Drop closed pull requests so reopening produces another OPENED event.
        known_head_shas = head_shas_by_number(pull_requests)
        time.sleep(arguments.poll_seconds)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except BrokenPipeError:
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(0)
