#!/usr/bin/env python3
"""Warn the agent when it edits a file origin/main has already moved.

User-ruled 2026-09-17, on the proposal deferred 2026-09-15 in
docs/issues/324-checkout-freshness-catch-up-reports-instead-of-merging.md
("Next, proposed and not built: warn on the obsolete FILE, not the branch"):
"the fact that its rare doesn't mean its not important when it happens."

THE CASE IT EXISTS FOR, 2026-09-17: an agent spent twenty minutes editing
assess_seat in scripts/recover-crashed-seats.py while a pull request that
changed that very function merged. It caught this only because it checked
before committing. Nothing told it. The Stop hook
(scripts/checkout-freshness-catch-up.py) tells a seat how far behind its
whole checkout is, at the end of a turn — orientation, not the file in the
agent's hands at the moment its hands are on it. This hook is the other
half: it fires only when an agent actually touches a file main has changed,
and it names THAT file, then.

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
them. Checked against the reference (code.claude.com/docs/en/hooks) rather
than assumed: assuming a channel's reach is the mistake nedschorus#324 is a
record of, and before 2026-09-15 every report the Stop hook made was read by
nobody for exactly that reason. No `decision` field, ever: this must never
block a tool call or cost the agent a turn.

THE SET. `git diff --name-only --no-renames HEAD...origin/main`. The three
dots, and why two would be wrong, are explained once, in
checkout-freshness-catch-up.py's obsolete_files_by_category() docstring; read
it there rather than here.

--no-renames, because rename detection is on by default and prints only a
rename's DESTINATION. Without the flag, a file main renamed away from the
path this branch still holds it at is absent from the set, so editing it
draws no warning — the one case guaranteed to conflict, since main has
deleted that path. Found in review of PR #463, the pull request that added
this hook, and measured there against 76 renames in main's last 200 commits.
With the flag a rename lists both paths, which is what a merge-base diff
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
or fetch (user-ruled 2026-09-17).

EVERY CLAUSE OF THE WARNING IS COMPUTED, never asserted. The same
obsolete_files_by_category() docstring records the user rejecting a line with
false clauses — "are you sure they are older than main — or are you just
saying that?" (2026-09-15). So: the commit count is measured and dropped if
it cannot be, and the advice is chosen from the head's actual state, not
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
# four of head_state()'s keys that imply a push happened; the frozen-head rule
# (CLAUDE.md, ruled 2026-09-08) applies to every one of them. Its other three
# — unpushed, detached, unknown — are handled separately below.
PUSHED_HEAD_STATE_KEYS = ("pushed", "pushed-with-local-commits",
                          "behind-remote", "diverged-from-remote")

NEVER_PUSHED_ADVICE = (
    "This branch has never been pushed, so nobody else has it: commit or set aside "
    "your work and run `git rebase origin/main` — the Stop hook rebases a never-pushed "
    "branch only when the tree is clean — then rerun the tests for what you touched."
)
# The conflict clause is the user's ruling of 2026-09-21; the rationale is in
# checkout-freshness-catch-up.py beside LEAVE_IT_ADVICE, whose wording this
# tracks. A commit on top cannot clear a conflict, so advice offering only
# that move dead-ends an agent that hits one.
PUSHED_ADVICE = (
    "This branch is pushed, so its review may be running: do not rebase or "
    "amend it. A fix for this topic is a new commit on top; a conflict with "
    "main is cleared by one hand-made merge of origin/main, announced. Your "
    "next topic starts with `git checkout -b <name> origin/main`."
)


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
    whole point of making this one call directly (user-ruled 2026-09-17), and
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


def head_advice(freshness, checkout: Path):
    """What to do about the branch, or "" when the head's state is unclear.

    Dropped rather than guessed when head_state() answers "detached" or
    "unknown": the advice flips entirely on whether anyone else has this
    branch, and a wrong half of the line teaches the agent to discount the
    whole of it.
    """
    branch = freshness.run_git(["rev-parse", "--abbrev-ref", "HEAD"], checkout,
                               timeout=REV_PARSE_TIMEOUT_SECONDS).stdout.strip()
    state_key, _text = freshness.head_state(checkout, branch)
    if state_key == "unpushed":
        return NEVER_PUSHED_ADVICE
    if state_key in PUSHED_HEAD_STATE_KEYS:
        return PUSHED_ADVICE
    return ""


def obsolete_file_warning_line(repository_path: str, commit_count, advice: str) -> str:
    """The one line the agent reads. Every clause of it measured."""
    if commit_count is None:
        moved = "which origin/main has changed since this branch's merge base"
    else:
        moved = (f"which {commit_count} commit(s) on origin/main have changed "
                 f"since this branch's merge base")
    line = (f"obsolete-file-edit-warning: you just changed {repository_path}, "
            f"{moved} and this checkout does not have.")
    return f"{line} {advice}" if advice else line


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
    line = obsolete_file_warning_line(
        repository_path,
        commits_on_main_touching(freshness, checkout, repository_path),
        head_advice(freshness, checkout))
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
