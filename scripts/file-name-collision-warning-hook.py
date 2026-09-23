#!/usr/bin/env python3
"""file-name-collision-warning-hook — two tracked files must not share a name.

Fires after an agent's Edit or Write and tells it, on the spot, when the file
it just wrote carries a name that already belongs to another tracked file. It
warns; it never refuses.

WHY (user-ruled 2026-09-22, walk cite-files-by-name-not-path-2026-09-21,
items 2 and 3, on the paired design of GHI nedschorus#610):

  A move is checked by searching for the file's NAME, not its old path
  (item 1, approved the same walk). That check is only sound while a name
  means one file. On 2026-09-22 the repository held 294 tracked files and
  285 distinct names, the only repeats being the three exempted below, so
  the premise holds today and this hook is what keeps it holding.

  Measured before the ruling and told to the user: no accidental collision
  has ever happened here. Every repeat in the whole history was deliberate
  and identified by its folder -- the three names below, and the ~20
  per-record files of the old review-record folders, which are gitignored
  now and live in the log-store. So this guards the move check that was
  just adopted, not past damage, and it was put to him that way.

  It is a hook and not only a suite test because nothing runs the suites
  automatically: there is no CI in this repository and nothing invokes
  scripts/run-all-test-suites.py. Hooks already fire on every Edit and
  Write. The suite test beside this file
  (scripts/file-name-collision-warning-hook-test.py, its last case) covers
  what a hook cannot see: a file created by git mv, by a shell copy, or by
  a program that writes its own files.

  The third line of the warning points at CLAUDE.md's naming rule rather
  than restating it -- user-ruled 2026-09-22 in the same item: "if we have
  a file naming convention, why don't we simply say to use it". A
  restatement is a second hand copy of a rule that already has a home, the
  defect that PR nedschorus#599 had just fixed elsewhere.

WHAT IT CANNOT SEE, stated so nobody reads more into a silent run:
  - A file written by anything other than the Edit and Write tools.
  - Which write CREATED the file. A PostToolUse payload carries no such
    flag, so the warning says "you wrote", and an agent that keeps editing
    an unresolved collision is told again each time. The collision is still
    true, so repeating it is not a false report.
  - A tracked path written back in different letter case where the
    filesystem folds case -- the Mac's does, ned-box's does not. There the
    write lands on the tracked file and there is one file, not two, so
    there is no collision to report and this hook is silent. It said the
    opposite until 2026-09-23, naming the file just written as the one to
    delete; is_the_same_file_on_this_filesystem() below is the fix, and it
    asks the filesystem rather than the platform.

Input: the PostToolUse payload on stdin.
Output: one hookSpecificOutput.additionalContext line, or nothing.
Exit codes: always 0. A warning that fails an agent's turn would be worse
than the collision it reports.
"""

import json
import subprocess
import sys
from pathlib import Path, PurePath

# The three names whose meaning comes from their folder, not from themselves.
# SKILL.md and README.md are fixed by the tools that read them; .gitkeep is
# fixed by git. A name a future tool requires shows up here as a failing
# suite case, which is the point: it is added deliberately, not by drift.
EXEMPT_FILE_NAMES = frozenset({"skill.md", "readme.md", ".gitkeep"})

# This runs at every Edit and every Write, so no call here may hang a turn --
# the standard scripts/obsolete-file-edit-warning-hook.py sets for the hook
# beside this one in the same PostToolUse block. Three git calls at most, all
# of them local reads that measure at about 50 ms together, and the harness
# kills the hook at the 30 seconds .claude/settings.json registers. A hung git
# therefore costs a bounded wait and one silent run.
GIT_CALL_TIMEOUT_SECONDS = 10


def git_output(arguments, cwd: Path):
    """stdout of a git call, or None if git could not answer. None is git
    failing, not git answering "nothing" -- every caller treats it as
    silence rather than as an empty result. A timeout is git failing too:
    subprocess.TimeoutExpired is a SubprocessError, not an OSError, so it is
    named here rather than covered by it."""
    try:
        finished = subprocess.run(["git", *arguments], cwd=str(cwd),
                                  capture_output=True, text=True, check=False,
                                  timeout=GIT_CALL_TIMEOUT_SECONDS)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None
    if finished.returncode != 0:
        return None
    return finished.stdout


def checkout_of(working_directory: Path):
    """The checkout the session works in, or None."""
    top_level = git_output(["rev-parse", "--show-toplevel"], working_directory)
    if top_level is None or not top_level.strip():
        return None
    return Path(top_level.strip()).resolve()


def path_within_checkout(file_path: str, checkout: Path):
    """The written file as a repository-relative path, or None when it is
    outside the checkout -- a scratchpad file, a log, anything under /tmp."""
    try:
        resolved = Path(file_path).resolve()
    except (OSError, ValueError):
        return None
    try:
        return resolved.relative_to(checkout)
    except ValueError:
        return None


def is_ignored(relative_path: PurePath, checkout: Path) -> bool:
    """git's own answer, never a copy of .gitignore. The directories that
    hold repeated names on purpose -- docs/walk/, cold-read-records/,
    sanity-check-records/, ghi-mirror/ -- are ignored, so this is what keeps
    every walk file and every review record out of the comparison."""
    try:
        finished = subprocess.run(
            ["git", "check-ignore", "-q", "--", str(relative_path)],
            cwd=str(checkout), capture_output=True, text=True, check=False,
            timeout=GIT_CALL_TIMEOUT_SECONDS)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return False
    return finished.returncode == 0


def is_the_same_file_on_this_filesystem(tracked: str, written: PurePath,
                                        checkout: Path) -> bool:
    """True when two repository-relative paths name ONE file here.

    The filesystem is asked, not the platform: samefile compares device and
    inode, which is the question itself. A tracked path written back in
    different letter case is ONE file where case is folded, because the
    write lands on the tracked file, and TWO files where it is not -- and
    the same hook runs on both machines.

    A path that cannot be stat'ed -- a tracked file absent from the working
    tree -- counts as a second file, which is what it is wherever case is
    not folded, and what this hook reported before it asked at all.
    """
    if tracked == str(written):
        return True
    try:
        return (checkout / tracked).samefile(checkout / written)
    except (OSError, ValueError):
        return False


def tracked_paths_sharing_name(relative_path: PurePath, checkout: Path):
    """Every OTHER tracked file whose name matches, letter case ignored.

    Case is ignored on both sides because the move check this guards
    searches for a name, and a name is searched for the way it is read, not
    the way it is spelled. The name comparison comes first so the filesystem
    is asked about the handful of paths that match rather than about all of
    them. None when git could not answer.
    """
    listing = git_output(["ls-files", "-z"], checkout)
    if listing is None:
        return None
    wanted = relative_path.name.lower()
    return sorted(
        tracked for tracked in listing.split("\0")
        if tracked and PurePath(tracked).name.lower() == wanted
        and not is_the_same_file_on_this_filesystem(
            tracked, relative_path, checkout))


def collision_warning_line(relative_path: PurePath, others) -> str:
    """The three lines the agent reads: what happened, and the only two
    situations that produce it. Nothing else -- no rationale, no citation,
    no advice to think about it (CLAUDE.md, the rule for text an agent reads
    at the moment it acts)."""
    already = ", ".join(others)
    moved_from = others[0] if len(others) == 1 else "the file you moved from"
    return (
        f"file-name-collision-warning: you wrote {relative_path}; "
        f"the name {relative_path.name} is already {already}.\n"
        f"If you are moving the file, delete {moved_from} in this change.\n"
        f"If both files are meant to exist, rename the one you just wrote by "
        f"CLAUDE.md's naming rule, and update what you have already written "
        f"to point at the new name.")


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, ValueError, OSError):
        return 0
    if not isinstance(payload, dict):
        return 0

    tool_input = payload.get("tool_input")
    file_path = tool_input.get("file_path") if isinstance(tool_input, dict) else None
    if not file_path or not isinstance(file_path, str):
        return 0

    # The session's OWN view of where it works. Never $CLAUDE_PROJECT_DIR:
    # that variable lies in forked sessions, naming the main checkout while
    # settings load from the worktree -- the same reason
    # scripts/obsolete-file-edit-warning-hook.py and
    # .claude/hooks/instruction-file-guard.py both read cwd from the payload.
    working_directory = payload.get("cwd")
    if not working_directory or not isinstance(working_directory, str):
        return 0
    working_directory = Path(working_directory)
    if not working_directory.is_dir():
        return 0

    checkout = checkout_of(working_directory)
    if checkout is None:
        return 0

    relative_path = path_within_checkout(file_path, checkout)
    if relative_path is None:
        return 0
    if relative_path.name.lower() in EXEMPT_FILE_NAMES:
        return 0
    if is_ignored(relative_path, checkout):
        return 0

    others = tracked_paths_sharing_name(relative_path, checkout)
    if not others:
        return 0

    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": collision_warning_line(relative_path, others),
    }}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
