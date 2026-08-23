#!/usr/bin/env python3
"""Watch a repository's open pull requests, one stdout line per event.

The merge-lane seat — the Mac-side agent that reviews and merges every pull
request into main until the git-gatekeeper activates — needs to know when a
pull request opens and when one gets new commits, because both restart the
clock it holds a pull request against (see "Why faster detection would not
help" below). Until this script it watched by hand: a shell polling loop
retyped at the start of every session from the previous session's
transcript. That loop was never reviewed, never tested, and died with the
session that typed it; each retyping was a fresh chance to get it wrong,
and the commonest way to get it wrong is silent (see "Announcing
blindness"). Where that account comes from, since it matters for judging
it: the merge seat's own record of its practice, which lives in
machine-local session transcripts a reader of main cannot open — this
paragraph is the durable statement of it, not a summary of one.
This is the same move as scripts/watch-agent-dialogs.py made
for seat transcripts — one durable watcher replacing per-session
improvisation — for a different channel.

Output contract — one stdout line per event, flushed immediately:

  PR #151 OPENED 78754c8a nedlern: <title>       a pull request that was not
                                                 open at the previous poll
  PR #151 NEW-HEAD 0fba6486 nedlern: <title>     an open pull request whose
                                                 head commit changed
  PR #152 OPENED 4b2c1de9 nedlern [draft]: ...   drafts are marked, not filtered
  WATCH: ...                                     the watcher's own state

The event key is the pair (pull request number, head commit sha) and
nothing else: a title edit, a new review, a label, a base-branch change,
a comment — none of them are events here. NEW-HEAD is named for what is
actually measured, a head sha that differs from the one seen last: an
ordinary push produces it, and so does a force-push or a rebase, which
move the head to a commit that may contain no new work at all. Both matter
to the merge seat for the same reason — its hold clock restarts from the
most recent push, whatever the push did.

Titles are folded to one line (newlines become " ¶ ") and truncated; the
sha is the head commit's first 8 characters. The author login is the pull
request's author, which for this project is usually the account that
opened it rather than the seat that wrote the work.

Deliberately not emitted: a pull request closing or merging, review and
comment activity, check runs. They are all watchable the same way and none
of them is what the hand-written loop was for; adding them is a later
change with its own argument, not a freebie.

Baseline. The first successful poll establishes what "already open" means
and emits no events for it, exactly as watch-agent-dialogs.py begins a
transcript at end-of-file; --from-start instead reports every already-open
pull request as OPENED. Either way one WATCH line is printed at that first
poll, so a quiet watch is provably a started watch rather than a dead one.
A pull request that closes is dropped from the compared state, so a
reopened pull request reports OPENED again — a re-announcement of
something the seat must look at again is the useful error to make here.

Announcing blindness. If the query fails — gh missing, network down,
credential rejected, GitHub erroring, an answer that is not the JSON this
program expects — the program prints one WATCH line saying the watch is
blind, and another when the query next succeeds. Silence is never how a
failure is reported here: a watcher that goes quiet on error is
indistinguishable from a quiet repository, and the seat relying on it
believes it has coverage it does not have. The compared state is NOT
touched by a failed poll, so blindness delays events rather than losing
them: a pull request that opens while the watch is blind is reported as
OPENED on the first poll that succeeds. The blind line is printed once per
episode rather than once per failed poll (a per-poll line would bury the
events either side of it); the recovery line carries how many polls failed
and roughly how long the blindness lasted.

The query's exit status is the query's own. `gh` is run through
subprocess.run with no shell and nothing piped into or out of it, and its
returncode is checked before its output is looked at. The shape being
avoided is `gh ... | jq ...`, whose exit status is jq's: a failed query
whose empty output jq parses happily becomes a successful poll that sees
zero open pull requests — which here would mean every open pull request
reported as OPENED again the moment the query recovers, and no blind line
at all. That shape has produced repeated defects in this project, and it
is the reason the blindness announcement above would otherwise never fire.
Three further failure layers are checked for the same reason: a timeout
(a hung query is silence too, so it is bounded and counted as a failure),
unparseable JSON, and a GraphQL response carrying an `errors` key — the
last of which arrives with HTTP 200 and a partial `data`, which is exactly
the kind of half-answer that must never be merged into the compared state.

The credential. The token is read from a file (--token-file, default
~/.config/nedschorus/ned-review-merge.token) and handed to `gh` only in the
environment, as GH_TOKEN. It is never in argv, so it cannot appear in a
process listing, a traceback, or an error message that quotes the command;
and every line this program prints, on stdout and stderr alike, goes
through a redaction that replaces the token's text with [REDACTED], so a
message quoted from gh's own stderr cannot carry it out either. The token
path being an option is what makes the tests possible: they run this
program against a fixture token file and a fake `gh`, never the real
credential and never GitHub.

Why this polls rather than being pushed to. GitHub offers no streaming
feed of repository activity — no WebSocket, no server-sent events; its push
mechanism is the webhook, which delivers to a publicly reachable HTTPS
endpoint, and this machine is a laptop behind NAT with no such endpoint. A
tunnel would manufacture one and would buy a worse failure than polling
has: a dead tunnel looks exactly like a quiet repository, which is the
failure mode this program's blind line exists to prevent. GitHub's REST
Events API is not a push channel either — it is polling with an ETag, and
its own documentation says "This API is not built to serve real-time use
cases. Depending on the time of day, event latency can be anywhere from 30s
to 6h" (docs.github.com/en/rest/activity/events, read 2026-08-23). Asking
for the open pull requests directly is both fresher and authoritative.

What the poll costs. One `gh api graphql` request per poll: at the default
60-second interval that is 60 requests an hour against an authenticated
limit of 5,000 an hour — 1.2% of the budget. Measured 2026-08-23 against
this repository: the query reports `rateLimit { cost }` of 1 point, the
GraphQL budget is 5,000 points an hour, and the whole response for 4 open
pull requests is 1,023 bytes. (The same query as a REST `GET
/repos/{owner}/{repo}/pulls` call was 87,784 bytes for those same 4 pull
requests — 85× more, for two fields per pull request. That is why the
query is GraphQL, following scripts/ghi-mirror-refresh.py's practice of
raw `gh api graphql` rather than `gh`'s own --json field allowlist, which
differs between the gh versions the fleet runs.) Provenance worth stating:
those byte and point figures were measured with this Mac's default `gh`
login, while the credential this program is meant to run with is the
`ned-review-merge` fine-grained token — which was proven separately, by
running this program against this repository once with that token: it
answered, and reported the four pull requests then open. Both credentials
are rated at 5,000 requests an hour and neither is near it. Were a
credential unable to run this query, the first poll would fail loudly
rather than quietly — see "Announcing blindness".

Why faster detection would not help. The merge seat holds every pull
request about three minutes from its most recent push, so an automated
reviewer that publishes no status check has time to post its findings
(the merge seat's CLAUDE.local.md, "Do not merge a pull request less than
about three minutes old", written after two merges that beat the reviewer
by 62 and 240 seconds — that file is machine-local to one seat and is not
in this repository, so the rule is restated here rather than only cited).
A 60-second poll therefore detects a pull request well
inside a window that is already being waited out on purpose; spending
requests to detect it in 5 seconds would move nothing that happens
afterward. The interval is an option for the cases the default is wrong
for, not because the default is a compromise.

Usage:
  scripts/watch-open-pull-requests.py [--repo OWNER/NAME]
      [--poll-seconds N] [--token-file PATH] [--from-start]

Exit codes: 0 clean exit (the consumer closed the pipe), 2 bad invocation
(including an unreadable token file), 130 interrupted.
"""

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

# Pull requests per page; GitHub's GraphQL connections cap at 100. Ten
# pages is a thousand simultaneously open pull requests — a bound that
# exists so a pagination loop can never spin forever, not one this
# repository will approach.
PAGE_SIZE = 100
MAX_PAGES = 10

# A hung query is silence, and silence is the failure this program exists
# to prevent, so the query is bounded well under the default poll interval
# and a timeout is counted as a failed poll like any other.
GH_QUERY_TIMEOUT_SECONDS = 30.0

# A gh that never ran (missing binary, timeout) reports a code gh itself
# cannot return, so "no answer" is never read as "ran and said nothing" —
# same convention, and the same name, as ghi-mirror-refresh.py's.
GH_DID_NOT_RUN = -1

HEAD_SHA_PREFIX_CHARS = 8
TITLE_SNIPPET_CHARS = 120
FAILURE_REASON_SNIPPET_CHARS = 300

# A token shorter than this is not a GitHub token, and treating one as a
# redaction pattern would corrupt every line printed (a one-character
# "token" would blank that character everywhere). An unreadable credential
# is refused at startup instead.
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

# Filled at startup with the credential's text. Every line printed by this
# program passes through redact_secrets first, so a message quoted from
# gh's stderr cannot carry the token to stdout, stderr, or a log.
SECRETS_TO_REDACT = []


def redact_secrets(text):
    for secret in SECRETS_TO_REDACT:
        text = text.replace(secret, "[REDACTED]")
    return text


def emit(line):
    """One event, one line, flushed now — a monitor reads this as it
    arrives, and a buffered line is a silent death."""
    print(redact_secrets(line), flush=True)


def warn(line):
    print(redact_secrets(line), file=sys.stderr, flush=True)


def one_line_snippet(text, limit):
    """Newlines folded to " ¶ " first, then the first `limit` characters —
    fold-then-truncate, so the emitted length is bounded by `limit`."""
    return " ¶ ".join(str(text).strip().splitlines())[:limit]


def read_token(token_file: Path):
    """(token, None) or (None, reason). The reason names the path — which
    is not secret — and never any of the file's content."""
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
    """`gh` with the credential in the environment and nothing piped.

    capture_output keeps stdout and stderr as data to be inspected, and no
    shell is involved, so the returncode this returns is gh's own. The
    token goes in the environment and never into argv: a process listing,
    a traceback, or an error message quoting the command therefore cannot
    expose it.
    """
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
    """(pull request, None) or (None, reason). A node that is not the shape
    the query asked for fails the whole poll rather than being dropped:
    silently dropping one would report it as OPENED again at the next
    poll, and would hide a real answer change behind a routine-looking
    event."""
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
        # author is null for a deleted account; "(unknown)" keeps the line
        # shape rather than printing None.
        "author": (author or {}).get("login") or "(unknown)",
    }, None


def fetch_open_pull_requests(repo, token):
    """Every open pull request, paginated. Returns (pull requests, None) or
    (None, reason) — and returns a partial answer never, since a short list
    is indistinguishable from pull requests having closed."""
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
        # Layer 1: gh's own exit status, checked before its output is read.
        if result.returncode != 0:
            reason = (result.stderr or result.stdout or "").strip()
            return None, reason or f"gh exited {result.returncode} with no message"
        # Layer 2: the answer parses as JSON.
        try:
            payload = json.loads(result.stdout)
        except (json.JSONDecodeError, ValueError) as error:
            return None, f"gh returned unparseable JSON: {error}"
        if not isinstance(payload, dict):
            return None, "gh returned JSON that is not an object"
        # Layer 3: GraphQL reports its own errors with HTTP 200 and a
        # partial `data`; that half-answer must never reach the state.
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
    """The lines one successful poll produces, comparing (number, head sha)
    against what the last successful poll saw."""
    lines = []
    for pull_request in pull_requests:
        seen_head_sha = known_head_shas.get(pull_request["number"])
        if seen_head_sha is None:
            lines.append(event_line(pull_request, "OPENED"))
        elif seen_head_sha != pull_request["head_sha"]:
            lines.append(event_line(pull_request, "NEW-HEAD"))
        # Same number, same head sha: whatever else changed is not an event.
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

    # Titles carry whatever an author typed; never let one unencodable
    # character kill the watch.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")

    known_head_shas = None   # None until the first successful poll
    blind_since = None       # monotonic start of the current blind episode
    failed_polls = 0

    while True:
        pull_requests, reason = fetch_open_pull_requests(arguments.repo, token)
        if reason is not None:
            failed_polls += 1
            if blind_since is None:
                blind_since = time.monotonic()
                emit("WATCH: query failed, so this watch is BLIND until it "
                     "recovers (nothing is being seen; what happens while "
                     "blind is reported when it recovers): "
                     + one_line_snippet(reason, FAILURE_REASON_SNIPPET_CHARS))
            time.sleep(arguments.poll_seconds)
            continue

        if blind_since is not None:
            emit(f"WATCH: query recovered after {failed_polls} failed poll(s), "
                 f"about {time.monotonic() - blind_since:.0f}s blind")
            blind_since = None
            failed_polls = 0

        if known_head_shas is None:
            emit(baseline_line(arguments.repo, arguments.poll_seconds,
                               pull_requests, arguments.from_start))
            known_head_shas = ({} if arguments.from_start
                               else head_shas_by_number(pull_requests))

        for line in events_for_poll(known_head_shas, pull_requests):
            emit(line)
        # Closed pull requests leave the compared state here, so a reopened
        # one reports OPENED again.
        known_head_shas = head_shas_by_number(pull_requests)
        time.sleep(arguments.poll_seconds)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except BrokenPipeError:
        # The consumer closed the pipe; die quietly, not with a traceback.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(0)
