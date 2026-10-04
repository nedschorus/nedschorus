#!/usr/bin/env python3
"""Watch open pull requests and emit flushed OPENED and NEW-HEAD events.

The first successful poll establishes a silent baseline unless --from-start
is set. Failed polls preserve state and announce blindness; activity that
opens and closes between successful polls cannot be recovered.

Polling needs no public webhook endpoint. GraphQL selects only needed fields
and avoids gh versions’ differing --json field lists."""

import argparse
import json
import os
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
        return None, f"a pull request came back as {type(node).__name__}, not an object"
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


def fetch_open_pull_requests(repo, token):
    """Return (all_open_pull_requests, None) or (None, reason); never return partial results."""
    owner, _, name = repo.partition("/")
    pull_requests = []
    cursor = None
    for _ in range(MAX_PAGES):
        arguments = ["api", "graphql",
                     "-f", f"query={OPEN_PULL_REQUESTS_QUERY}",
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
            pull_request, reason = pull_request_from_node(node)
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
    return parser.parse_args(argv)


def main(argv=None):
    arguments = parse_arguments(argv)
    if arguments.poll_seconds <= 0:
        warn("watch-open-pull-requests: --poll-seconds must be > 0")
        return 2
    owner, slash, name = arguments.repo.partition("/")
    if not (owner and slash and name) or "/" in name:
        warn(f"watch-open-pull-requests: --repo must be OWNER/NAME, "
             f"not {arguments.repo!r}")
        return 2
    token, reason = read_token(Path(arguments.token_file).expanduser())
    if reason is not None:
        warn(f"watch-open-pull-requests: {reason}")
        return 2
    SECRETS_TO_REDACT.append(token)

    # Author-supplied titles must not kill the watch on an unencodable character.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")

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

        for line in events_for_poll(known_head_shas, pull_requests):
            emit(line)
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
