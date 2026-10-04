#!/usr/bin/env python3
"""Warn the agent when it edits a file origin/main has already moved.

The Stop hook (scripts/checkout-freshness-catch-up.py) tells a seat how far
behind its whole checkout is, at the end of a turn — orientation, not the
file in the agent's hands at the moment its hands are on it. Without this
hook an agent can keep editing a function that a merged pull request already
changed, and nothing tells it. This hook is the other half: it fires only
when an agent actually touches a file main has changed, and it names THAT
file, then.

Wired as a `PostToolUse` hook matching `Edit|Write`. `Read` is deliberately
NOT matched: an agent reads far more files than it writes, and a warning
that fires on every read is a warning that gets skimmed. Which tools reach
this script is the matcher's business, not this file's — it warns about
whatever `tool_input.file_path` it is handed.

THE CHANNEL. One JSON object on stdout carrying
`hookSpecificOutput.additionalContext`, which IS added to the agent's
context. Plain stdout on a PostToolUse hook that exits 0 goes to the debug
log and reaches nobody — the hooks reference names `UserPromptSubmit`,
`UserPromptExpansion`, `SessionStart` and `PostModelSwitch` as the only
events where plain stdout becomes context, and PostToolUse is not among
them (code.claude.com/docs/en/hooks). Check a channel's reach against that
reference rather than assume it: a report on the wrong channel is read by
nobody. No `decision` field, ever: this must never block a tool call or cost
the agent a turn.

THE SET. `git diff --name-only --no-renames HEAD...origin/main`. The three
dots, and why two would be wrong, are explained once, in
checkout-freshness-catch-up.py's obsolete_files_by_category() docstring; read
it there rather than here.

--no-renames, because rename detection is on by default and prints only a
rename's DESTINATION. Without the flag, a file main renamed away from the
path this branch still holds it at is absent from the set, so editing it
draws no warning — the one case guaranteed to conflict, since main has
deleted that path. With the flag a rename lists both paths, which is what a merge-base diff
means by "changed": the old path lost its file and the new path gained one.
The commit count below still measures for the old path, because `rev-list`
with a pathspec counts the commit that deleted it.

This hook runs that one diff itself, for the reason obsolete_path_set() gives —
it needs to see the return code, which that function does not expose — and
imports the rest of what it needs from that script: run_git(), read_stamp(),
write_stamp() and head_state(). Its module level is imports and constants
only, its main() behind `if __name__ == "__main__"`, so importing runs
nothing.

NEVER FETCHES. The Stop hook fetches on its own throttle; this one runs at
every edit and must be fast. It reads whatever origin/main the last fetch
left — the same REF the Stop hook's telling rests on, and the same set:
checkout-freshness-catch-up.py's obsolete_files_by_category() passes
--no-renames too, so both run the same diff.

CACHED, because the diff is the only expensive call here and the answer
changes rarely. The path set is cached in the checkout's own git directory,
beside the Stop hook's stamp, keyed on BOTH origin/main's tip AND this
checkout's HEAD — either moving changes the answer, so either moving
invalidates. A cache hit costs one `git rev-parse` and a set lookup. Only a
real answer is ever cached: a diff that failed is not an empty set, and
writing one as though it were would silence this hook until the next commit
or fetch.

EVERY CLAUSE OF THE WARNING IS COMPUTED, never asserted: the commit count is
measured and dropped if it cannot be, and the advice is chosen from the head's actual state, not
guessed. Note what the never-pushed advice does NOT say: that the Stop hook
will rebase the branch at turn end. It will not, in this very case — an
agent that just edited a file has a dirty tree, and
rebase_never_pushed_branch() skips a dirty tree by design.

EVERYTHING HERE EXITS 0 AND PRINTS NOTHING ON ANY FAULT: not a repository,
git missing, no origin/main, an unreadable payload, a timeout, a failed
import. A staleness warning must never be the reason an edit fails.
"""

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

# The path set lives beside checkout-freshness-catch-up.py's
# checkout-freshness-stamp.json, in the checkout's own git directory — which
# for a linked worktree is that worktree's own .git/worktrees/<name>, so two
# seats sharing a repository never read each other's answer.
PATH_SET_CACHE_FILE_NAME = "obsolete-file-edit-warning-path-set-cache.json"

# Timeouts: this runs at every edit, so nothing here may hang a turn. The
# rev-parse is the only call on the cache-hit path.
REV_PARSE_TIMEOUT_SECONDS = 15
OBSOLETE_DIFF_TIMEOUT_SECONDS = 30
COMMIT_COUNT_TIMEOUT_SECONDS = 15

# Which head states mean "somebody else may have this branch". These are the
# four of head_state()'s keys that imply a push of this branch happened; the
# frozen-head rule in CLAUDE.md applies to every one of them.
# Its others — unpushed, pushed-history, detached, unknown — are handled
# separately in head_advice(). pushed-history is frozen too, but its commits
# were pushed under another branch name, so "This branch is pushed" would be
# false of it; it gets checkout-freshness-catch-up.py's PUSHED_HISTORY_ADVICE,
# which says what was found.
PUSHED_HEAD_STATE_KEYS = ("pushed", "pushed-with-local-commits",
                          "behind-remote", "diverged-from-remote")

NEVER_PUSHED_ADVICE = (
    "This branch has never been pushed, so nobody else has it: commit or set aside "
    "your work and run `git rebase origin/main` — the Stop hook rebases a never-pushed "
    "branch only when the tree is clean — then run `python3 scripts/run-all-test-suites.py "
    "--only-suites-whose-recorded-inputs-changed-since origin/main`."
)
# A pushed branch that conflicts with main is the one exception: no commit on
# top can clear a conflict, so it is cleared by a hand-merge (CLAUDE.md, "How a
# change reaches main"). Forbidding every merge here would send an agent with
# a conflict away from the one move that clears it.
PUSHED_ADVICE = (
    "This branch is pushed, so its review may be running: do not rebase or amend "
    "it. A fix for this topic is a new commit on top. If it conflicts with main, "
    "clear the conflict with the hand-merge that scripts/branch-conflict-check.py "
    "describes. Your next topic starts with `git checkout -b <name> origin/main`."
)


GIT_OPERATION_IN_PROGRESS_LINE = (
    "A git operation is in progress ({marker}): finish it before anything else."
)
DETACHED_HEAD_LINE = (
    "This checkout is on a detached HEAD: make a branch (git switch -c "
    "<a-branch-name>) before you commit, because a commit on a detached HEAD is on "
    "no branch."
)
NO_OVERLAP_LINE = (
    "main's changes to {path} do not overlap this checkout's copy; a rebase merges "
    "them cleanly."
)
OVERLAP_LINE = (
    "main's changes to {path} overlap this checkout's copy: after you make the branch "
    "and commit your edit, run git rebase origin/main, which will stop on this file, "
    "and resolve the conflict there."
)
MAIN_HAS_NO_FILE_LINE = (
    "main no longer has a file at {path}: find out whether main moved or deleted it "
    "(git log origin/main -- {path}) before you commit."
)
MAIN_COPY_UNREADABLE_LINE = (
    "git could not read {path} on origin/main ({text}), so this warning cannot say "
    "whether main's changes overlap your edit: stop and tell the user before you "
    "make the branch or commit."
)
BRANCH_STATE_UNKNOWN_LINE = (
    "git could not report this checkout's branch state ({text}): stop and tell the "
    "user before you commit."
)
MERGE_FILE_TIMEOUT_SECONDS = 15
# git merge-file exits with the number of conflicts, capped at 127; above that is an error.
MERGE_FILE_HIGHEST_CONFLICT_COUNT = 127


def _load_checkout_freshness_module():
    """checkout-freshness-catch-up.py as a module, or None.

    A script, not a package, so it is loaded the way this project loads one
    script from another (scripts/recover-crashed-seats.py loads
    handoff-supervisor.py the same way). Resolving this file's own directory
    explicitly rather than trusting sys.path[0]: a hook that fails to import
    is a hook that does not run, and here a failed import must be silence,
    not a traceback on the agent's tool call.
    """
    try:
        specification = importlib.util.spec_from_file_location(
            "checkout_freshness_catch_up",
            Path(__file__).resolve().with_name("checkout-freshness-catch-up.py"))
        module = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(module)
        return module
    except Exception:
        return None


def checkout_facts(freshness, working_directory: Path):
    """(checkout root, git directory, HEAD sha, origin/main sha), or None.

    One `git rev-parse` for all four rather than the four calls
    checkout_root(), git_directory() and two rev-parses would cost: this is
    the whole of the cache-hit path, and it runs at every edit an agent
    makes. rev-parse answers in argument order, and exits non-zero when any
    of them has no answer — no origin/main, no HEAD, no repository — which
    is the one check needed for all four.
    """
    resolved = freshness.run_git(
        ["rev-parse", "--show-toplevel", "--absolute-git-dir", "HEAD", "origin/main"],
        working_directory, timeout=REV_PARSE_TIMEOUT_SECONDS)
    if resolved.returncode != 0:
        return None
    lines = [line.strip() for line in resolved.stdout.splitlines() if line.strip()]
    if len(lines) != 4:
        return None
    return Path(lines[0]), Path(lines[1]), lines[2], lines[3]


def path_within_checkout(file_path: str, checkout: Path):
    """The edited file as git names it — relative, forward slashes — or None
    when it is not inside this checkout at all.

    Both sides are resolved first. On macOS the session's cwd and a tool's
    file_path arrive through /tmp and /var, while `git rev-parse
    --show-toplevel` answers with the realpath under /private; comparing them
    unresolved reads every such file as living outside the checkout.

    Outside is silence by design: an edit in another worktree or a scratch
    directory has no meaningful comparison against THIS checkout's merge base.
    """
    try:
        return Path(file_path).resolve().relative_to(checkout.resolve()).as_posix()
    except (ValueError, OSError, RuntimeError):
        return None


def obsolete_path_set(freshness, checkout: Path, git_directory: Path,
                      head_sha: str, main_sha: str):
    """The paths main has moved that this checkout has not, cached; or None
    when git could not answer, which is NOT the same as nothing being obsolete.

    The cache is valid only while BOTH origin/main's tip and this checkout's
    HEAD are what they were when it was written: a fetch that moves main
    changes the answer, and so does a commit here. A missing, torn or
    stale-keyed cache is simply recomputed — read_stamp() returns {} for
    anything it cannot parse.

    WHY THE DIFF IS RUN HERE and not through
    checkout-freshness-catch-up.py's obsolete_files_by_category(), which
    computes the same thing and is where the three dots are explained:
    that function answers [] both for "nothing is obsolete" and for "git
    could not say". For the Stop hook that is right — the clause is dropped
    either way, once, and the next turn end asks again. Here the answer is
    CACHED, so one failed diff would read as "nothing obsolete" for every
    edit until HEAD or origin/main next moved. Seeing the return code is the
    whole point of making this one call directly, and
    a failure caches nothing, so the very next edit asks git again.
    """
    cache_path = git_directory / PATH_SET_CACHE_FILE_NAME
    cached = freshness.read_stamp(cache_path)
    if (cached.get("head") == head_sha and cached.get("main_tip") == main_sha
            and isinstance(cached.get("paths"), list)):
        return set(cached["paths"])

    # run_git returns its own GIT_DID_NOT_RUN code rather than raising when
    # git is missing or the timeout expires, so one non-zero test covers a
    # failed diff, an absent binary and a hung one alike.
    listed = freshness.run_git(
        ["diff", "--name-only", "--no-renames", "HEAD...origin/main"],
        checkout, timeout=OBSOLETE_DIFF_TIMEOUT_SECONDS)
    if listed.returncode != 0:
        return None
    paths = set(line.strip() for line in listed.stdout.splitlines() if line.strip())
    freshness.write_stamp(cache_path, {"head": head_sha, "main_tip": main_sha,
                                       "paths": sorted(paths)})
    return paths


def commits_on_main_touching(freshness, checkout: Path, repository_path: str):
    """How many commits origin/main has that this checkout lacks touched this
    file, or None when git cannot say.

    Two dots here, where the path set uses three: `HEAD..origin/main` is the
    COMMITS reachable from main and not from HEAD, which is what "how many
    commits changed it since your merge base" counts. The three-dot form is a
    diff of trees and has no commit list to count.
    """
    counted = freshness.run_git(
        ["rev-list", "--count", "HEAD..origin/main", "--", repository_path],
        checkout, timeout=COMMIT_COUNT_TIMEOUT_SECONDS)
    if counted.returncode != 0:
        return None
    try:
        count = int(counted.stdout.strip())
    except ValueError:
        return None
    return count if count > 0 else None


def git_operation_in_progress(freshness, git_directory: Path):
    """The marker of a rebase, merge, cherry-pick or revert under way, or None.

    A bisect is not one of them: the agent is meant to test and edit at the commit
    under test, so the ordinary detached-HEAD facts apply.
    """
    for marker in freshness.GIT_IN_PROGRESS_MARKERS:
        if marker != "BISECT_LOG" and (git_directory / marker).exists():
            return marker
    return None


def overlap_line(freshness, checkout: Path, repository_path: str):
    """Whether main's changes to the file overlap this checkout's copy.

    Returns MAIN_HAS_NO_FILE_LINE when main's tree was read and lists no file at the
    path, MAIN_COPY_UNREADABLE_LINE with git's text when main's copy or tree cannot
    be read, and "" when another git step (merge base, base copy, merge-file) fails.

    A two-way diff against main cannot answer this, because the agent's own edit is
    part of it; a three-way merge of the file, with the merge base as the common
    ancestor, answers it directly. The verdict is textual: changes that do not
    overlap can still disagree.
    """
    merge_base = freshness.run_git(["merge-base", "HEAD", "origin/main"], checkout,
                                   timeout=REV_PARSE_TIMEOUT_SECONDS)
    if merge_base.returncode != 0 or not merge_base.stdout.strip():
        return ""
    main_copy = freshness.run_git(["show", f"origin/main:{repository_path}"], checkout,
                                  timeout=REV_PARSE_TIMEOUT_SECONDS)
    if main_copy.returncode != 0:
        # git show exits 128 both for a path main lacks and for an object it cannot
        # read; only a tree that was read and lists nothing proves the file is gone.
        main_listing = freshness.run_git(
            ["ls-tree", "origin/main", "--", repository_path], checkout,
            timeout=REV_PARSE_TIMEOUT_SECONDS)
        if main_listing.returncode == 0 and not main_listing.stdout.strip():
            return MAIN_HAS_NO_FILE_LINE.format(path=repository_path)
        text = ((main_copy.stderr or "").strip()
                or "git show exited %d" % main_copy.returncode)
        return MAIN_COPY_UNREADABLE_LINE.format(path=repository_path, text=text)
    base_copy = freshness.run_git(
        ["show", f"{merge_base.stdout.strip()}:{repository_path}"], checkout,
        timeout=REV_PARSE_TIMEOUT_SECONDS)
    if base_copy.returncode != 0:
        return ""
    working_copy = checkout / repository_path
    if not working_copy.is_file():
        return ""
    with tempfile.TemporaryDirectory() as scratch:
        base_path = Path(scratch) / "merge-base-copy"
        main_path = Path(scratch) / "origin-main-copy"
        base_path.write_text(base_copy.stdout, encoding="utf-8")
        main_path.write_text(main_copy.stdout, encoding="utf-8")
        merged = freshness.run_git(
            ["merge-file", "-p", "-q", str(working_copy), str(base_path), str(main_path)],
            checkout, timeout=MERGE_FILE_TIMEOUT_SECONDS)
    if merged.returncode == 0:
        return NO_OVERLAP_LINE.format(path=repository_path)
    if 0 < merged.returncode <= MERGE_FILE_HIGHEST_CONFLICT_COUNT:
        return OVERLAP_LINE.format(path=repository_path)
    return ""


def head_advice(freshness, checkout: Path, git_directory: Path, repository_path: str):
    """(text, on its own lines) for what to do about the branch.

    On a branch the advice continues the warning's one line, as it always has. A
    detached HEAD and a branch state git could not report get lines of their own,
    since each is a different instruction.
    """
    branch_answer = freshness.run_git(["rev-parse", "--abbrev-ref", "HEAD"], checkout,
                                      timeout=REV_PARSE_TIMEOUT_SECONDS)
    if branch_answer.returncode != 0:
        text = (branch_answer.stderr or "").strip() or (
            "git rev-parse exited %d" % branch_answer.returncode)
        return BRANCH_STATE_UNKNOWN_LINE.format(text=text), True
    branch = branch_answer.stdout.strip()
    state_key, state_text = freshness.head_state(checkout, branch)
    if state_key == "unpushed":
        return NEVER_PUSHED_ADVICE, False
    if state_key == "pushed-history":
        return freshness.PUSHED_HISTORY_ADVICE, False
    if state_key in PUSHED_HEAD_STATE_KEYS:
        return PUSHED_ADVICE, False
    if state_key == "detached":
        marker = git_operation_in_progress(freshness, git_directory)
        if marker is not None:
            return GIT_OPERATION_IN_PROGRESS_LINE.format(marker=marker), True
        lines = [DETACHED_HEAD_LINE]
        verdict = overlap_line(freshness, checkout, repository_path)
        if verdict:
            lines.append(verdict)
        return "\n".join(lines), True
    return BRANCH_STATE_UNKNOWN_LINE.format(text=state_text), True


def obsolete_file_warning_line(repository_path: str, commit_count, advice: str,
                               advice_on_own_lines: bool = False) -> str:
    """What the agent reads. Every clause of it measured."""
    if commit_count is None:
        moved = ("which origin/main has changed since this checkout's merge base "
                 "with origin/main")
    else:
        moved = (f"which {commit_count} commit(s) on origin/main have changed "
                 f"since this checkout's merge base with origin/main")
    line = (f"obsolete-file-edit-warning: you just changed {repository_path}, "
            f"{moved} and this checkout does not have, so your edit is built on an "
            f"old copy of the file.")
    if not advice:
        return line
    return f"{line}\n{advice}" if advice_on_own_lines else f"{line} {advice}"


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
    # settings load from the worktree — the same reason
    # checkout-freshness-catch-up.py and .claude/hooks/instruction-file-guard.py
    # both read cwd from the payload.
    working_directory = payload.get("cwd")
    if not working_directory or not isinstance(working_directory, str):
        return 0
    working_directory = Path(working_directory)
    if not working_directory.is_dir():
        return 0

    freshness = _load_checkout_freshness_module()
    if freshness is None:
        return 0

    facts = checkout_facts(freshness, working_directory)
    if facts is None:
        return 0
    checkout, git_directory, head_sha, main_sha = facts

    repository_path = path_within_checkout(file_path, checkout)
    if repository_path is None:
        return 0

    obsolete = obsolete_path_set(freshness, checkout, git_directory, head_sha, main_sha)
    # None is git failing to answer, not an empty answer: both are silence
    # here, but only the empty answer was cached.
    if obsolete is None or repository_path not in obsolete:
        return 0

    # Only from here on does anything cost more than a lookup: the count and
    # the head state are measured for the one file that actually warned.
    advice, advice_on_own_lines = head_advice(freshness, checkout, git_directory,
                                              repository_path)
    line = obsolete_file_warning_line(
        repository_path,
        commits_on_main_touching(freshness, checkout, repository_path),
        advice, advice_on_own_lines)
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": line,
    }}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        # A warning is never worth a failed tool call. Nothing above is
        # expected to raise — every git call goes through run_git, which does
        # not — but "expected" is not "guaranteed", and the cost of being
        # wrong here is an agent's edit reported as failed.
        sys.exit(0)
