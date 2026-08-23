#!/usr/bin/env python3
"""The GHI write tool (nedschorus#46, design doc
docs/issues/46-ghi-info-agent-design.md § The GHI write path).

Every body-bearing issue write in this project lands through here. Authors
still write with `gh` as trained — the PreToolUse hook
(.claude/hooks/ghi-issue-write-redirect.py) rewrites their `gh issue
create`/`edit` into a call on this tool — so the mechanical checks run
whether or not the author remembered them, and the `ghi-write` skill stays
the layer that carries the judgment none of this machinery can.

What each body-bearing write costs, in order (design's own sequence):

  1. REFERENCE CHECK. In-repo paths the body cites must resolve on main.
     The check is reactive to what the body cites: no issue is required to
     cite an MD, but one that does must cite something a reader can open.
     A failure refuses with both ways forward — land the MD first, or write
     now without the reference and add it by edit once the MD lands.
  2. SIMILARITY ADJUDICATION. ghi-info is shown the draft and answers with
     one verdict line. `too-similar` refuses with a merge instruction;
     `related` lets the write through and names what to read; `unrelated`
     is a plain pass. FAIL-OPEN: ghi-info unreachable, slow, or answering
     in any shape that is not a verdict means the write proceeds
     unadjudicated — the mechanical checks still run. Infrastructure
     failure never produces a refusal.
  3. THE WRITE, through `gh`. This tool relays gh's own output verbatim and
     appends its own lines after it, so the author sees what gh said plus
     what this tool concluded.
  4. LENGTH MEASUREMENT. No author counts words. Over BODY_WORD_LIMIT, the
     reply instructs the split: keep a good summary in the body, merge the
     substance into the linked pair MD.

COMMENTS are the taught exception. Plain `gh issue comment` is denied at the
hook, because a comment cannot be mechanically rewritten into the body edit
this project's revision convention wants — where the content lands, and what
it supersedes, only the author knows. What this tool accepts instead is a
comment naming one of two catalog events: an instance outcome (one run of a
recurring process the issue tracks, while the issue stays open) or a
challenge to a ruling the issue records. The catalog grows only by explicit
ruling. "Completion" is deliberately not in it (user-ruled 2026-08-12): a
completion is the body edit recording the outcome, then a close with reason.

SOFT BLOCK, RECONSIDER-TO-PASS (user-ruled 2026-08-11). A refusal's one job
is a deliberate second look — GHI-filing mistakes are not worth the user's
attention, and a smart agent told to reconsider, and reconsidering, is good
enough. Every deny path ends with the same closing line: still convinced,
write the reasoning into .ghi-issue-write-reconsidered at the repository
root and resubmit. The marker passes exactly one write and is consumed by
it, riding the same lane as the instruction-file guard's .walk-approved —
agent reasoning in place of user approval, visible in the transcript.

ACCEPTED RESIDUALS, from the design, not defects to re-file:
  - an issue can change between the verdict and the write;
  - the enumeration holes stay open (`gh api`, MCP tools, creative quoting)
    under the cooperative posture: enforcement targets mistakes, not
    evasion. Bypassed writes still appear in the mirror delta, where the
    sweep finds their symptoms.

Usage:
  ghi-issue-write.py create --title T (--body B | --body-file F) [--repo R]
  ghi-issue-write.py edit <number> (--body B | --body-file F) [--title T]
  ghi-issue-write.py comment <number> --event-kind KIND
                     (--body B | --body-file F)
  ghi-issue-write.py delete <number>          (always refused)

Exit 0 when the write landed, 1 when it was refused or failed.
"""

import argparse
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
REPOSITORY_ROOT = SCRIPT_DIRECTORY.parent

_ask_spec = importlib.util.spec_from_file_location(
    "ghi_info_ask", SCRIPT_DIRECTORY / "ghi-info-ask.py")
ghi_info_ask = importlib.util.module_from_spec(_ask_spec)
_ask_spec.loader.exec_module(ghi_info_ask)

# The marker lane lives with the write guards so there is one copy of the
# contract (extracted 2026-08-19 by PR #91's review). This tool keeps its
# OWN marker filename, per that module's rule: approvals of different things
# must never be able to consume each other.
_marker_spec = importlib.util.spec_from_file_location(
    "guard_approval_marker",
    REPOSITORY_ROOT / ".claude" / "hooks" / "guard_approval_marker.py")
guard_approval_marker = importlib.util.module_from_spec(_marker_spec)
_marker_spec.loader.exec_module(guard_approval_marker)

DEFAULT_REPO = "nedschorus/nedschorus"
RECONSIDERED_MARKER_NAME = ".ghi-issue-write-reconsidered"
# The sweep imports this in a later PR; it is the one place the limit lives.
# Raised from 500 on 2026-08-20 (recorded in the ghi-write skill): at 500 a
# body of nothing but rulings did not fit, and the remedy routes decision
# text into a pull request, the most expensive way this project moves prose.
BODY_WORD_LIMIT = 1000

COMMENT_EVENT_KINDS = ("instance-outcome", "ruling-challenge")

RECONSIDER_LINE = (
    "\n\nIf you believe this refusal is wrong, reconsider once against its stated "
    "reason. Still convinced, write your reasoning into "
    f"{RECONSIDERED_MARKER_NAME} at the repository root and resubmit — the marker "
    "passes exactly one write and is consumed by it."
)

# Paths this project actually cites. Anchoring on the real top-level
# directories keeps prose out of the check: "the docs/ tree" is a citation,
# "roughly 3/4 of them" is not, and neither is a bare word with a dot in it.
IN_REPO_PATH_PATTERN = re.compile(
    r"(?<![\w/.-])((?:docs|scripts|bridge|md-review-records|\.claude)/[\w./-]*[\w/])")


def run_git(arguments, timeout=30):
    try:
        return subprocess.run(["git", "-C", str(REPOSITORY_ROOT), *arguments],
                              capture_output=True, text=True, check=False,
                              timeout=timeout)
    except (OSError, subprocess.SubprocessError) as error:
        return subprocess.CompletedProcess(arguments, 1, "", str(error))


def cited_in_repo_paths(body: str):
    """In-repo paths the body cites, in first-appearance order.

    Deliberately blind to anything inside a URL: full URLs are how this
    project cites what lives outside the repository, and a github.com link
    containing `docs/foo.md` is not a claim that the path resolves in this
    checkout. Markdown link targets and backticked paths both survive,
    because both are stripped of their surrounding punctuation by the
    pattern's own boundaries.
    """
    without_urls = re.sub(r"https?://\S+", " ", body or "")
    seen, paths = set(), []
    for match in IN_REPO_PATH_PATTERN.finditer(without_urls):
        path = match.group(1).rstrip(".,;:)")
        if path not in seen:
            seen.add(path)
            paths.append(path)
    return paths


def paths_missing_on_main(paths):
    """Which of these do not resolve on origin/main.

    origin/main, not the working tree: the design's rule is that a reader
    coming to the issue can open what it cites, and only what has landed is
    open to them. A path that exists locally but is uncommitted is exactly
    the case the refusal's "land the MD first" branch is written for.
    """
    missing = []
    for path in paths:
        if run_git(["cat-file", "-e", f"origin/main:{path}"]).returncode != 0:
            missing.append(path)
    return missing


def word_count(body: str) -> int:
    return len((body or "").split())


def consume_reconsidered_marker() -> bool:
    return guard_approval_marker.consume_approval_marker(
        REPOSITORY_ROOT / RECONSIDERED_MARKER_NAME)


def refuse(message: str) -> int:
    print(message + RECONSIDER_LINE, file=sys.stderr)
    return 1


def run_gh(arguments, timeout=120):
    try:
        return subprocess.run(["gh", *arguments], capture_output=True, text=True,
                              check=False, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as error:
        return subprocess.CompletedProcess(arguments, 1, "", str(error))


def relay(completed) -> None:
    """gh's own output, verbatim, before anything this tool has to add."""
    if completed.stdout:
        sys.stdout.write(completed.stdout)
    if completed.stderr:
        sys.stderr.write(completed.stderr)


def adjudicate_draft(title, body, editing_issue_number, seat_dir, repo):
    """The verdict, or None when adjudication is unavailable (fail-open).

    Every failure shape collapses to None on purpose: unreachable box, a
    timeout, ghi-info answering in prose, an escalate:, an out-of-scope. The
    design's rule is that infrastructure failure never refuses a write, and
    an unparseable answer is indistinguishable from an absent one here.
    """
    verdict, error = ghi_info_ask.adjudicate(title, body, editing_issue_number,
                                             seat_dir, repo)
    if verdict is None:
        print(f"ghi-issue-write: proceeding without adjudication ({error})",
              file=sys.stderr)
    return verdict


def check_and_adjudicate(title, body, editing_issue_number, seat_dir, repo,
                         marker_spent):
    """The two checks that can refuse. Returns (refusal_message, verdict)."""
    missing = paths_missing_on_main(cited_in_repo_paths(body))
    if missing and not marker_spent:
        named = ", ".join(missing)
        return (
            f"Refused: the body cites {named}, which does not resolve on main. "
            "Two ways forward: land the MD first, then rerun this write; or "
            "write now without the reference and add it by edit once the MD "
            "lands."
        ), None

    verdict = adjudicate_draft(title, body, editing_issue_number, seat_dir, repo)
    if verdict and verdict["kind"] == "too-similar" and not marker_spent:
        number = verdict["issues"][0]
        message = (
            f"Refused: #{number} already covers this ground. Read #{number}, then "
            "merge this content into it by editing it — not as a new issue or a "
            "parallel edit."
        )
        if editing_issue_number is not None:
            message += (
                f"\n\n#{editing_issue_number}, the issue you were editing, keeps its "
                f"current body; if #{number} now carries its ground, mark it "
                f"Superseded-by: #{number} and close it with a reason."
            )
        return message, verdict
    return None, verdict


def append_tool_lines(verdict, body) -> None:
    """This tool's own lines, after gh's relayed output."""
    if verdict and verdict["kind"] == "related":
        named = ", ".join(f"#{number}" for number in verdict["issues"])
        print(f"\nRelated issues worth knowing: {named}.")
    count = word_count(body)
    if count > BODY_WORD_LIMIT:
        print(f"\nThis body is {count} words; the limit is {BODY_WORD_LIMIT}. Keep a "
              "good summary in the body; merge the substance into the linked pair "
              "MD, creating or updating it. Ask ghi-info what to link.")


def resolve_body(arguments) -> str:
    if arguments.body_file:
        return Path(arguments.body_file).read_text(encoding="utf-8")
    return arguments.body or ""


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="The checked path for GitHub-issue writes in this project.",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__,
    )
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--seat-dir", default=None,
                        help="ghi-info's seat, passed through to the adjudication "
                             "consult (testing; an operator running box-side)")
    verbs = parser.add_subparsers(dest="verb", required=True)

    create = verbs.add_parser("create")
    create.add_argument("--title", required=True)
    create.add_argument("--body")
    create.add_argument("--body-file")
    create.add_argument("--label", action="append", default=[])

    edit = verbs.add_parser("edit")
    edit.add_argument("number", type=int)
    edit.add_argument("--title")
    edit.add_argument("--body")
    edit.add_argument("--body-file")

    comment = verbs.add_parser("comment")
    comment.add_argument("number", type=int)
    comment.add_argument("--event-kind", required=True, choices=COMMENT_EVENT_KINDS)
    comment.add_argument("--body")
    comment.add_argument("--body-file")

    delete = verbs.add_parser("delete")
    delete.add_argument("number", type=int)

    arguments = parser.parse_args(argv)
    seat_dir = (Path(arguments.seat_dir).expanduser() if arguments.seat_dir
                else ghi_info_ask.DEFAULT_SEAT_DIR)

    if arguments.verb == "delete":
        return refuse(
            "Refused: issues are never deleted — the record is append-forward. "
            "Close it instead, with a reason: completed or not planned.")

    body = resolve_body(arguments)

    if arguments.verb == "comment":
        # The catalog is the whole gate here: a comment naming one of the two
        # events is a genuine event, and the reference and length checks do
        # not apply — a comment is not the body, and the revision convention
        # keeps the body current, not the thread.
        completed = run_gh(["issue", "comment", str(arguments.number),
                            "--repo", arguments.repo, "--body", body])
        relay(completed)
        if completed.returncode != 0:
            return 1
        print(f"\nRecorded as a {arguments.event_kind} comment. The issue body still "
              "governs: if this event changes what the issue asks for, edit the body "
              "too.")
        return 0

    marker_spent = consume_reconsidered_marker()
    editing = arguments.number if arguments.verb == "edit" else None
    title = arguments.title if arguments.verb == "create" else (arguments.title or "")

    refusal, verdict = check_and_adjudicate(title, body, editing, seat_dir,
                                            arguments.repo, marker_spent)
    if refusal:
        return refuse(refusal)

    if arguments.verb == "create":
        gh_arguments = ["issue", "create", "--repo", arguments.repo,
                        "--title", arguments.title, "--body", body]
        for label in arguments.label:
            gh_arguments += ["--label", label]
    else:
        gh_arguments = ["issue", "edit", str(arguments.number),
                        "--repo", arguments.repo, "--body", body]
        if arguments.title:
            gh_arguments += ["--title", arguments.title]

    completed = run_gh(gh_arguments)
    relay(completed)
    if completed.returncode != 0:
        return 1
    append_tool_lines(verdict, body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
