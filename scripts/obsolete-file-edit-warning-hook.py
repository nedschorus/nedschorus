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

A WARNING IS NOT REPEATED WORD FOR WORD. The cache also holds, for each path
already warned about, the text of the last warning given. An edit whose
warning would be that same text again is silent; a warning whose text changed,
such as a detached HEAD's verdict going from "do not overlap" to "overlap",
is given. A warning that reports a git step failing is recorded like any other
but never held back. Because the record lives in the path-set cache, a commit here or
a fetch that moves main clears it, and the warning is given again. The record
belongs to the worktree, not to an agent-session: a second agent-session in
the same worktree is not warned about a file an earlier one was warned about
until HEAD or origin/main moves. A record that cannot be written leaves the
warning as it is and adds a line saying so, because the warning will then
repeat.

EVERY CLAUSE OF THE WARNING IS COMPUTED, never asserted: the commit count is
measured, and said to have failed if it cannot be, and the advice is chosen from the head's actual state, not
guessed. Note what the never-pushed advice does NOT say: that the Stop hook
will rebase the branch at turn end. It will not, in this very case — an
agent that just edited a file has a dirty tree, and
rebase_never_pushed_branch() skips a dirty tree by design.

NOTHING TO COMPARE AGAINST IS SILENCE, exit 0: a cwd in no repository, no
HEAD or no origin/main, a file outside the checkout.

A GIT STEP THAT FAILS after the file is known to be obsolete, such as the
commit count or the overlap check, is said in the warning itself, and that
warning is never held back as a repeat. Any other git failure, git missing or a
git call timing out included, is the hook failing.

A FAULT OF THE HOOK ITSELF, such as stdin that is not a JSON object,
checkout-freshness-catch-up.py failing to load, a git failure or any exception:
nothing on stdout, exit 1, and on stderr a first line naming the hook and the
fault, followed for a git failure by what to do next. Claude Code records a
PostToolUse exit 1 as a non-blocking error, shows its first stderr line and
keeps the edit; exit 0 would read as "this file is not obsolete".
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
# top can clear a conflict, so it is cleared by the hand-merge that
# the VERDICT: CONFLICT report of scripts/branch-conflict-check.py describes.
# Forbidding every merge here would send an agent with a conflict away from
# the one move that clears it.
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
OVERLAP_UNKNOWN_LINE = (
    "git could not tell whether main's changes to {path} overlap this checkout's copy "
    "({failure}): stop and tell the user before you make the branch or commit."
)
COMMIT_COUNT_FAILED_LINE = (
    "git could not count the commits on origin/main that changed the file ({failure})."
)
GIT_FAILURE_CAUSE_LINE = (
    "obsolete-file-edit-warning-hook: {failure}, so the edited file was not checked "
    "against origin/main; the edit itself succeeded."
)
GIT_FAILURE_NOTHING_TO_RERUN_LINE = (
    "Nothing needs rerunning: this check runs again at your next Edit or Write.")
RECORD_WRITE_FAILED_LINE = (
    "obsolete-file-edit-warning could not record that it gave this warning, so it "
    "will give it again at your next edit of this file ({record}: {reason}). Nothing "
    "needs doing about the record."
)
MERGE_FILE_TIMEOUT_SECONDS = 15
# git merge-file exits with the number of conflicts, capped at 127; above that is an error.
MERGE_FILE_HIGHEST_CONFLICT_COUNT = 127


def _load_checkout_freshness_module():
    """checkout-freshness-catch-up.py as a module; raises when it will not load.

    A script, not a package, so it is loaded the way this project loads one
    script from another (scripts/recover-crashed-seats.py loads
    handoff-supervisor.py the same way). Resolving this file's own directory
    explicitly rather than trusting sys.path[0]. A failed load reaches the
    top-level handler, which reports it.
    """
    specification = importlib.util.spec_from_file_location(
        "checkout_freshness_catch_up",
        Path(__file__).resolve().with_name("checkout-freshness-catch-up.py"))
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def git_step_failed(freshness, arguments, completed, directory: Path):
    """The GitCommandFailed for a run_git call that did not give an answer."""
    detail = (completed.stderr or "").strip().splitlines()
    if completed.returncode == freshness.GIT_DID_NOT_RUN:
        return freshness.git_output.GitCommandFailed(
            arguments, directory, None, detail[0] if detail else "git did not run")
    return freshness.git_output.GitCommandFailed(
        arguments, directory, completed.returncode, detail[0] if detail else "")


def checkout_facts(freshness, working_directory: Path):
    """(checkout root, git directory, HEAD sha, origin/main sha), or None when
    there is nothing to compare against: no repository, no HEAD or no
    origin/main. Raises GitCommandFailed when git cannot say.

    One `git rev-parse` for all four rather than the four calls
    checkout_root(), git_directory() and two rev-parses would cost: this is
    the whole of the cache-hit path, and it runs at every edit an agent
    makes. rev-parse answers in argument order, and exits 128 alike for a
    revision that does not exist and for a git that failed, so only a failed
    call pays for the questions that tell the two apart.
    """
    arguments = ["rev-parse", "--show-toplevel", "--absolute-git-dir", "HEAD", "origin/main"]
    resolved = freshness.run_git(arguments, working_directory,
                                 timeout=REV_PARSE_TIMEOUT_SECONDS)
    if resolved.returncode == freshness.GIT_DID_NOT_RUN:
        raise git_step_failed(freshness, arguments, resolved, working_directory)
    if resolved.returncode != 0:
        if freshness.git_output.git_stderr_says_outside_a_repository(resolved.stderr):
            return None
        for revision in ("HEAD", "origin/main"):
            verify_arguments = ["rev-parse", "--verify", "--quiet", revision]
            verified = freshness.run_git(verify_arguments, working_directory,
                                         timeout=REV_PARSE_TIMEOUT_SECONDS)
            # --verify --quiet exits 1, and only 1, for a revision that does not exist.
            if verified.returncode == 1:
                return None
            if verified.returncode != 0:
                raise git_step_failed(freshness, verify_arguments, verified, working_directory)
        raise git_step_failed(freshness, arguments, resolved, working_directory)
    lines = [line.strip() for line in resolved.stdout.splitlines() if line.strip()]
    if len(lines) != 4:
        raise freshness.git_output.GitCommandFailed(
            arguments, working_directory, 0,
            f"printed {len(lines)} lines where it answers with 4")
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
    """(the paths main has moved that this checkout has not, {path: the last
    warning given about it}), cached. Raises GitCommandFailed when git could not
    answer, which is NOT the same as nothing being obsolete. A recomputed set
    starts with no warnings given.

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
        warned = cached.get("warned")
        return set(cached["paths"]), (warned if isinstance(warned, dict) else {})

    # Without --exit-code, git diff has no nonzero answer: every nonzero is a
    # failure, GIT_DID_NOT_RUN for a missing or hung git included.
    arguments = ["diff", "-z", "--name-only", "--no-renames", "HEAD...origin/main"]
    listed = freshness.run_git(arguments, checkout, timeout=OBSOLETE_DIFF_TIMEOUT_SECONDS)
    if listed.returncode != 0:
        raise git_step_failed(freshness, arguments, listed, checkout)
    paths = set(freshness.git_output.nul_separated_fields(listed.stdout))
    freshness.write_stamp(cache_path, {"head": head_sha, "main_tip": main_sha,
                                       "paths": sorted(paths), "warned": {}})
    return paths, {}


def warning_record_write(git_directory: Path, head_sha: str, main_sha: str,
                         paths, warned: dict):
    """Write the path set with the warnings given; return None, or the reason
    the write failed. Not write_stamp(), which drops a failure: a record that
    was not written makes the warning repeat, and the agent is told why."""
    try:
        (git_directory / PATH_SET_CACHE_FILE_NAME).write_text(
            json.dumps({"head": head_sha, "main_tip": main_sha, "paths": sorted(paths),
                        "warned": warned}, indent=2) + "\n",
            encoding="utf-8")
    except OSError as error:
        return f"{type(error).__name__}: {error}"
    return None


def commits_on_main_touching(freshness, checkout: Path, repository_path: str):
    """How many commits origin/main has that this checkout lacks touched this
    file, or None when it counts none. Raises GitCommandFailed when git cannot
    count them.

    Two dots here, where the path set uses three: `HEAD..origin/main` is the
    COMMITS reachable from main and not from HEAD, which is what "how many
    commits changed it since your merge base" counts. The three-dot form is a
    diff of trees and has no commit list to count.
    """
    arguments = ["rev-list", "--count", "HEAD..origin/main", "--", repository_path]
    counted = freshness.run_git(arguments, checkout, timeout=COMMIT_COUNT_TIMEOUT_SECONDS)
    if counted.returncode != 0:
        raise git_step_failed(freshness, arguments, counted, checkout)
    try:
        count = int(counted.stdout.strip())
    except ValueError:
        raise freshness.git_output.GitCommandFailed(
            arguments, checkout, 0, f"printed {counted.stdout.strip()!r}, not a count") from None
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
    """(line, whether the line reports a git failure): whether main's changes to
    the file overlap this checkout's copy.

    The line is MAIN_HAS_NO_FILE_LINE when main's tree was read and lists no file at
    the path, MAIN_COPY_UNREADABLE_LINE with git's text when main's copy or tree
    cannot be read, OVERLAP_UNKNOWN_LINE when another git step (merge base, base
    copy, merge-file) fails, and "" when there is no merge base, the merge base has
    no file at the path, or the edited file is gone.

    A two-way diff against main cannot answer this, because the agent's own edit is
    part of it; a three-way merge of the file, with the merge base as the common
    ancestor, answers it directly. The verdict is textual: changes that do not
    overlap can still disagree.
    """
    def overlap_unknown(arguments, completed):
        failure = git_step_failed(freshness, arguments, completed, checkout)
        return OVERLAP_UNKNOWN_LINE.format(path=repository_path, failure=failure), True

    merge_base_arguments = ["merge-base", "HEAD", "origin/main"]
    merge_base = freshness.run_git(merge_base_arguments, checkout,
                                   timeout=REV_PARSE_TIMEOUT_SECONDS)
    # git merge-base exits 1 when the two have no common ancestor.
    if merge_base.returncode == 1:
        return "", False
    if merge_base.returncode != 0:
        return overlap_unknown(merge_base_arguments, merge_base)
    if not merge_base.stdout.strip():
        return "", False
    main_copy = freshness.run_git(["show", f"origin/main:{repository_path}"], checkout,
                                  timeout=REV_PARSE_TIMEOUT_SECONDS)
    if main_copy.returncode != 0:
        # git show exits 128 both for a path main lacks and for an object it cannot
        # read; only a tree that was read and lists nothing proves the file is gone.
        main_listing = freshness.run_git(
            ["ls-tree", "origin/main", "--", repository_path], checkout,
            timeout=REV_PARSE_TIMEOUT_SECONDS)
        if main_listing.returncode == 0 and not main_listing.stdout.strip():
            return MAIN_HAS_NO_FILE_LINE.format(path=repository_path), False
        text = ((main_copy.stderr or "").strip()
                or "git show exited %d" % main_copy.returncode)
        return MAIN_COPY_UNREADABLE_LINE.format(path=repository_path, text=text), True
    base_copy_arguments = ["show", f"{merge_base.stdout.strip()}:{repository_path}"]
    base_copy = freshness.run_git(base_copy_arguments, checkout,
                                  timeout=REV_PARSE_TIMEOUT_SECONDS)
    if base_copy.returncode != 0:
        base_listing = freshness.run_git(
            ["ls-tree", merge_base.stdout.strip(), "--", repository_path], checkout,
            timeout=REV_PARSE_TIMEOUT_SECONDS)
        if base_listing.returncode == 0 and not base_listing.stdout.strip():
            return "", False
        return overlap_unknown(base_copy_arguments, base_copy)
    working_copy = checkout / repository_path
    if not working_copy.is_file():
        return "", False
    with tempfile.TemporaryDirectory() as scratch:
        base_path = Path(scratch) / "merge-base-copy"
        main_path = Path(scratch) / "origin-main-copy"
        # run_git decodes with surrogateescape; writing the same way restores bytes that are not UTF-8.
        base_path.write_text(base_copy.stdout, encoding="utf-8", errors="surrogateescape")
        main_path.write_text(main_copy.stdout, encoding="utf-8", errors="surrogateescape")
        merge_file_arguments = ["merge-file", "-p", "-q", str(working_copy),
                                str(base_path), str(main_path)]
        merged = freshness.run_git(merge_file_arguments, checkout,
                                   timeout=MERGE_FILE_TIMEOUT_SECONDS)
    if merged.returncode == 0:
        return NO_OVERLAP_LINE.format(path=repository_path), False
    if 0 < merged.returncode <= MERGE_FILE_HIGHEST_CONFLICT_COUNT:
        return OVERLAP_LINE.format(path=repository_path), False
    return overlap_unknown(merge_file_arguments, merged)


def head_advice(freshness, checkout: Path, git_directory: Path, repository_path: str):
    """(text, on its own lines, whether the text reports a git failure) for what
    to do about the branch.

    On a branch the advice continues the warning's one line, as it always has. A
    detached HEAD and a branch state git could not report get lines of their own,
    since each is a different instruction.
    """
    branch_answer = freshness.run_git(["rev-parse", "--abbrev-ref", "HEAD"], checkout,
                                      timeout=REV_PARSE_TIMEOUT_SECONDS)
    if branch_answer.returncode != 0:
        text = (branch_answer.stderr or "").strip() or (
            "git rev-parse exited %d" % branch_answer.returncode)
        return BRANCH_STATE_UNKNOWN_LINE.format(text=text), True, True
    branch = branch_answer.stdout.strip()
    state_key, state_text = freshness.head_state(checkout, branch)
    if state_key == "unpushed":
        return NEVER_PUSHED_ADVICE, False, False
    if state_key == "pushed-history":
        return freshness.PUSHED_HISTORY_ADVICE, False, False
    if state_key in PUSHED_HEAD_STATE_KEYS:
        return PUSHED_ADVICE, False, False
    if state_key == "detached":
        marker = git_operation_in_progress(freshness, git_directory)
        if marker is not None:
            return GIT_OPERATION_IN_PROGRESS_LINE.format(marker=marker), True, False
        lines = [DETACHED_HEAD_LINE]
        verdict, verdict_reports_failure = overlap_line(freshness, checkout, repository_path)
        if verdict:
            lines.append(verdict)
        return "\n".join(lines), True, verdict_reports_failure
    return BRANCH_STATE_UNKNOWN_LINE.format(text=state_text), True, True


def obsolete_file_warning_line(repository_path: str, commit_count, advice: str,
                               advice_on_own_lines: bool = False,
                               count_failure=None) -> str:
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
    if count_failure is not None:
        line += " " + COMMIT_COUNT_FAILED_LINE.format(failure=count_failure)
    if not advice:
        return line
    return f"{line}\n{advice}" if advice_on_own_lines else f"{line} {advice}"


def main() -> int:
    payload = json.loads(sys.stdin.read())
    if not isinstance(payload, dict):
        raise ValueError("the input on the hook's stdin is JSON, but not an object")
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
    try:
        return warn_about_edited_file(freshness, working_directory, file_path)
    except freshness.git_output.GitCommandFailed as failure:
        print(GIT_FAILURE_CAUSE_LINE.format(failure=failure), file=sys.stderr)
        # The shared wording comes through checkout-freshness-catch-up's copy, so a
        # hook copied away from it fails in the one load the top-level handler reports.
        print(GIT_FAILURE_NOTHING_TO_RERUN_LINE, file=sys.stderr)
        print(freshness.next_step_lines.same_failure_again_line(
            "at your next Edit or Write", "obsolete-file-edit-warning-hook"), file=sys.stderr)
        return 1


def warn_about_edited_file(freshness, working_directory: Path, file_path: str) -> int:
    facts = checkout_facts(freshness, working_directory)
    if facts is None:
        return 0
    checkout, git_directory, head_sha, main_sha = facts

    repository_path = path_within_checkout(file_path, checkout)
    if repository_path is None:
        return 0

    obsolete, warned = obsolete_path_set(freshness, checkout, git_directory, head_sha, main_sha)
    if repository_path not in obsolete:
        return 0

    # Only from here on does anything cost more than a lookup: the count and
    # the head state are measured for the one file that actually warned.
    advice, advice_on_own_lines, advice_reports_failure = head_advice(
        freshness, checkout, git_directory, repository_path)
    try:
        commit_count, count_failure = (
            commits_on_main_touching(freshness, checkout, repository_path), None)
    except freshness.git_output.GitCommandFailed as failure:
        commit_count, count_failure = None, failure
    line = obsolete_file_warning_line(
        repository_path, commit_count, advice, advice_on_own_lines, count_failure)
    if (not advice_reports_failure and count_failure is None
            and warned.get(repository_path) == line):
        return 0
    warned[repository_path] = line
    write_failure = warning_record_write(git_directory, head_sha, main_sha, obsolete, warned)
    if write_failure is not None:
        line += "\n" + RECORD_WRITE_FAILED_LINE.format(
            record=git_directory / PATH_SET_CACHE_FILE_NAME, reason=write_failure)
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": line,
    }}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"obsolete-file-edit-warning-hook: the edited file was not checked against "
              f"origin/main, because the hook failed; the edit itself succeeded: "
              f"{type(error).__name__}: {error}", file=sys.stderr)
        sys.exit(1)
