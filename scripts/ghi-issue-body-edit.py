#!/usr/bin/env python3
"""Replace a GitHub issue's body, but only if the body has not changed since
the caller read it — otherwise refuse and write nothing.

User-ruled 2026-09-08: "GHI edits should check for conflicts." `gh issue
edit <n> --body-file <file>` replaces an issue's whole body with no
base-version check, so when two seats edit one issue the second silently
discards the first's change. That happened: the cold-read-research seat
overwrote another seat's edit to nedschorus#7 earlier the same day, and
nothing anywhere said so. The user then set the scope: "Rarely will two
agents modify a GHI simultaneously. If they do even more rarely they will
contradict each other. So the fix should be simple." So this program does
one thing and stops. It refuses on a conflict. There is no retry, no
merge, no three-way anything, no lock, and no state file — a refusal hands
the situation back to the agent that caused it, which is the whole fix.

THIS IS THE NARROW PIECE, NOT THE WRITE TOOL. The GHI write path proper —
reference checks, length checks, the soft-block-and-reconsider path, the
comment verb — is `scripts/ghi-issue-write.py`, designed in nedschorus#46
(docs/issues/46-ghi-info-agent-design.md § The GHI write path) and not yet
built. Only the conflict-checked body edit is built here, small enough to
be absorbed into that tool as one guard when it lands: one comparison, one
refusal, one `gh issue edit`. Nothing here anticipates the rest of #46.
The ghi-write skill still names the unbuilt tool; skill text lands only
through the user's own walk and cold read, so this build leaves it alone.

Usage:
  ghi-issue-body-edit.py <issue-number> --base-body-file PATH
                         --new-body-file PATH [--repo OWNER/NAME]

THE CALLER'S BASE RECORD IS A COPY OF THE BODY THEY READ, not a digest of
it. Both forms detect a conflict equally well; only the copy can SHOW one.
The refusal has to be actionable — it prints a unified diff of the body the
caller read against the body GitHub holds now, which is what tells the
caller that the other change was a paragraph they were about to delete
rather than a typo fix, and often whose change it was. A digest can say
only "it moved", leaving the caller to go fetch the body themselves to find
out what happened, which is the same work with an extra step. The copy also
costs the caller nothing: the body must be read to be edited, so keeping the
file that was read is free.

Produce the base record with exactly this command, the same read this
script makes internally:

  gh issue view <issue-number> --repo nedschorus/nedschorus --json body \
      --jq .body > <base-body-file>

Then edit a copy of that file into the new body and pass both paths.

Bodies are compared normalized: CRLF and bare CR to LF, and trailing
newlines stripped. Without the trailing-newline half, every edit would
refuse: `--jq .body` appends a newline of its own that is not part of the
body (measured on nedschorus#7, 2026-09-08 — the file ends in three
newlines where the body itself has two), so the caller's file and the
JSON-parsed body would never compare equal. The CRLF half is cheap
insurance for a body typed into GitHub's web editor, which stores CRLF; no
CR appeared in the four bodies sampled here (nedschorus#1, #7, #46, #142).
The diff is built from the normalized text too, so a refusal shows the
other seat's change and not line-ending noise.

Exit codes, the cold-read-record-ship.py set:
  0   the body was still what the caller read, and the edit was made
  1   a `gh` call failed (unreachable, no such issue, edit rejected);
      nothing was written
  2   REFUSED — the body changed since the caller read it; nothing was
      written, and stderr carries the diff
  64  bad invocation (no such file, an empty new body, a non-issue number,
      a mistyped flag), as the cell launchers do

Accepted residual, under the same "the fix should be simple" ruling: the
check is not atomic with the write. A third write landing in the moment
between the comparison and the `gh issue edit` is still lost, exactly as
today. Closing that needs a lock or a conditional write GitHub's issue API
does not offer, and the traffic this defends against is two cooperative
seats minutes apart, not a millisecond race.
"""

import argparse
import difflib
import json
import subprocess
import sys
from pathlib import Path

DEFAULT_REPO = "nedschorus/nedschorus"

EXIT_EDITED = 0
EXIT_FAILED = 1
EXIT_REFUSED = 2
EXIT_BAD_INVOCATION = 64

# A gh that never ran (missing binary, timeout) reports a code gh itself
# cannot return, so "no answer" is never read as "ran and failed" — the
# same convention as ghi-mirror-refresh.py's GH_DID_NOT_RUN.
GH_DID_NOT_RUN = -1

GH_TIMEOUT_SECONDS = 60


def run_gh(arguments, timeout=GH_TIMEOUT_SECONDS):
    try:
        return subprocess.run(["gh", *arguments], capture_output=True, text=True,
                              check=False, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as error:
        return subprocess.CompletedProcess(arguments, GH_DID_NOT_RUN, "",
                                           f"{type(error).__name__}: {error}")


class BadInvocationArgumentParser(argparse.ArgumentParser):
    """argparse's own command-line errors join EXIT_BAD_INVOCATION.

    argparse exits 2 on a missing or unknown option, and 2 here means
    REFUSED — the one answer a caller must never confuse with a mistyped
    flag, since a refusal says another seat's change is at stake and a
    mistyped flag says nothing of the kind. Usage text and message are
    argparse's, unchanged; only the exit code moves.
    """

    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(EXIT_BAD_INVOCATION, f"{self.prog}: error: {message}\n")


def normalized_body(text: str) -> str:
    """The comparable form of an issue body: LF line endings, no trailing
    newlines. See the module docstring for why both halves are needed."""
    return text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")


def read_issue_body(issue_number: int, repo: str):
    """The issue's body and last-updated stamp as GitHub holds them now.

    Returns ({"body": str, "updatedAt": str}, None) or (None, error). Both
    fields are in the field allowlist of the box's gh 2.46.0 as well as the
    Mac's 2.97.0 (verified 2026-09-08) — unlike `stateReason`, which
    ghi-mirror-refresh.py had to route around.
    """
    result = run_gh(["issue", "view", str(issue_number), "--repo", repo,
                     "--json", "body,updatedAt"])
    if result.returncode != 0:
        return None, (result.stderr or "gh issue view failed with no stderr").strip()
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        return None, f"gh returned unparseable JSON: {error}"
    if not isinstance(payload, dict) or "body" not in payload:
        return None, f"gh returned no body field: {result.stdout[:200]!r}"
    return payload, None


def conflict_report(issue_number: int, repo: str, updated_at: str,
                    base_body: str, current_body: str) -> str:
    """What the refusal prints: that it changed, when, and the difference."""
    diff = difflib.unified_diff(
        base_body.splitlines(), current_body.splitlines(),
        fromfile="the body you read", tofile=f"the body on GitHub now (updated {updated_at})",
        lineterm="",
    )
    return "\n".join([
        f"ghi-issue-body-edit: REFUSED — issue #{issue_number} in {repo} changed "
        f"since you read it (GitHub's copy was updated {updated_at}), so your edit "
        "was NOT written; it would have discarded the change below.",
        *diff,
        "",
        "Re-read the issue, fold that change into your new body, and run this "
        "again with a base record taken from the re-read.",
    ])


def main(argv=None) -> int:
    parser = BadInvocationArgumentParser(
        description="Replace a GitHub issue's body only if it has not changed "
                    "since you read it.",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__,
    )
    parser.add_argument("issue_number", type=int, help="the issue to edit")
    parser.add_argument("--base-body-file", required=True,
                        help="the body as you read it (see the usage note for the "
                             "one command that produces this file)")
    parser.add_argument("--new-body-file", required=True,
                        help="the body to write in its place")
    parser.add_argument("--repo", default=DEFAULT_REPO,
                        help=f"owner/name holding the issue (default {DEFAULT_REPO})")
    arguments = parser.parse_args(argv)

    if arguments.issue_number <= 0:
        print(f"ghi-issue-body-edit: {arguments.issue_number} is not an issue number",
              file=sys.stderr)
        return EXIT_BAD_INVOCATION

    new_body_path = Path(arguments.new_body_file)
    try:
        new_body_text = new_body_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        print(f"ghi-issue-body-edit: could not read the new body at "
              f"{new_body_path}: {error}", file=sys.stderr)
        return EXIT_BAD_INVOCATION
    if not new_body_text.strip():
        print(f"ghi-issue-body-edit: the new body at {new_body_path} is empty — "
              "writing it would erase the issue's text; compose the body first",
              file=sys.stderr)
        return EXIT_BAD_INVOCATION

    base_body_path = Path(arguments.base_body_file)
    try:
        # An EMPTY base record is legal and means what it says: the issue had
        # no body when the caller read it. Only an unreadable one is a bad
        # invocation.
        base_body_text = base_body_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        print(f"ghi-issue-body-edit: could not read the base record at "
              f"{base_body_path}: {error}", file=sys.stderr)
        return EXIT_BAD_INVOCATION

    issue, error = read_issue_body(arguments.issue_number, arguments.repo)
    if issue is None:
        print(f"ghi-issue-body-edit: could not read issue #{arguments.issue_number} "
              f"from {arguments.repo}, so nothing was written: {error}", file=sys.stderr)
        return EXIT_FAILED

    updated_at = issue.get("updatedAt") or "at an unreported time"
    current_body = normalized_body(issue.get("body") or "")
    base_body = normalized_body(base_body_text)
    if current_body != base_body:
        print(conflict_report(arguments.issue_number, arguments.repo, updated_at,
                              base_body, current_body), file=sys.stderr)
        return EXIT_REFUSED

    result = run_gh(["issue", "edit", str(arguments.issue_number),
                     "--repo", arguments.repo, "--body-file", str(new_body_path)])
    if result.returncode != 0:
        print(f"ghi-issue-body-edit: the edit failed and issue "
              f"#{arguments.issue_number} is unchanged: "
              f"{(result.stderr or 'gh issue edit failed with no stderr').strip()}",
              file=sys.stderr)
        return EXIT_FAILED

    print(f"ghi-issue-body-edit: issue #{arguments.issue_number} in "
          f"{arguments.repo} rewritten from {new_body_path} — the body you read "
          f"(GitHub's copy, updated {updated_at}) was still current, so no one "
          "else's change was discarded.")
    # gh issue edit prints the issue URL; pass it through rather than swallow it.
    if result.stdout.strip():
        print(result.stdout.strip())
    return EXIT_EDITED


if __name__ == "__main__":
    sys.exit(main())
