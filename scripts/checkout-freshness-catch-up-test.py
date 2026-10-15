#!/usr/bin/env python3
"""Tests for checkout-freshness-catch-up.py.

Run: python3 scripts/checkout-freshness-catch-up-test.py
Prints one line per case and exits non-zero if any case fails. Every case
runs against throwaway repositories under a temporary directory; the layout
mirrors the fleet's: one clone parked on main (the reference copy) carrying
a linked worktree on its own branch (the seat).
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Before anything runs git: a run started with GIT_DIR set, or with another
# variable that redirects git, must still build this suite's scratch
# repositories where the suite says, not in the repository the variable names.
_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().with_name(
        "git-redirecting-environment-removal-test-fixture.py"))
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

SCRIPT_PATH = Path(__file__).with_name("checkout-freshness-catch-up.py")

# Spelled out here, NOT imported from the script: a typo in the script's copy
# would propagate through an import and the pin would pass anyway. Ruled
# 2026-09-18, after agents relayed the hook's notes to the user: "you don't
# need to tell me what other agents are doing."
NOT_FOR_THE_USER_LINE = (
    "Do not report this to the user: he does not need to hear that main moved, or "
    "what other agents merged, unless it changes the work you are doing with him."
)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def git(arguments, cwd: Path):
    return subprocess.run(["git", *arguments], cwd=str(cwd),
                          capture_output=True, text=True, check=False)


def run_catch_up_once(extra_arguments, path_prefix=None, stdin_text=None):
    environment = dict(os.environ)
    if path_prefix is not None:
        environment["PATH"] = f"{path_prefix}{os.pathsep}{environment['PATH']}"
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--interval-seconds", "0", *extra_arguments],
        capture_output=True, text=True, check=False, env=environment,
        input=stdin_text,
    )


def run_catch_up(extra_arguments, path_prefix=None):
    """One Stop-hook run, then the next prompt's delivery, as the agent meets
    them: the user's lines from the Stop run and the agent's notes from the
    delivery, in one result. The operator-facing modes run once, as before."""
    stop = run_catch_up_once(extra_arguments, path_prefix)
    if "--cwd" not in extra_arguments or any(
            flag in extra_arguments for flag in ("--report", "--reference-pull",
                                                 "--deliver-pending-agent-notes")):
        return stop
    cwd = extra_arguments[extra_arguments.index("--cwd") + 1]
    delivery = run_catch_up_once(["--deliver-pending-agent-notes", "--cwd", cwd], path_prefix)
    combined = dict(emitted_object(stop) or {})
    delivered = (emitted_object(delivery) or {}).get("hookSpecificOutput", {}).get(
        "additionalContext", "")
    stop_context = combined.pop("hookSpecificOutput", {}).get("additionalContext", "")
    agent = "\n".join(text for text in (stop_context, delivered) if text)
    if agent:
        combined["hookSpecificOutput"] = {"hookEventName": "UserPromptSubmit",
                                          "additionalContext": agent}
    return subprocess.CompletedProcess(
        stop.args, stop.returncode,
        json.dumps(combined, ensure_ascii=False) if combined else "",
        stop.stderr + delivery.stderr)


def emitted_object(result):
    """The JSON object a run emitted, or None when it spoke plain text.

    The Stop hook emits ONE object carrying both audiences: `systemMessage` for
    the user's display, `hookSpecificOutput.additionalContext` for the agent's
    context. The operator-facing modes (--report, --reference-pull) still speak
    plain text, and their cases assert exactly that.
    """
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def display_text(result) -> str:
    """What the USER was shown by a hook run."""
    return (emitted_object(result) or {}).get("systemMessage", "")


def agent_text(result) -> str:
    """What the AGENT was told by a hook run — the channel that, until
    2026-09-15, this script never used and every agent therefore never read."""
    return ((emitted_object(result) or {})
            .get("hookSpecificOutput", {})
            .get("additionalContext", ""))


def never_blocks(result) -> bool:
    """No decision field: blocking costs the agent a turn, and the blocking
    channel went with the merge (ruled 2026-09-14). Emitting JSON is NOT
    blocking — the object is how both audiences are reached at all."""
    return "decision" not in (emitted_object(result) or {})


def configure_identity(repository: Path):
    git(["config", "user.email", "test@example.invalid"], repository)
    git(["config", "user.name", "freshness test"], repository)


def commit_file(repository: Path, name: str, content: str, message: str):
    # Parents created: the telling's categories are decided by PATH, so its
    # cases need real ones (scripts/, docs/, .claude/skills/), not flat files.
    (repository / name).parent.mkdir(parents=True, exist_ok=True)
    (repository / name).write_text(content, encoding="utf-8")
    git(["add", name], repository)
    git(["commit", "-q", "-m", message], repository)


def stamp_of(checkout: Path) -> dict:
    git_dir = Path(git(["rev-parse", "--absolute-git-dir"], checkout).stdout.strip())
    try:
        return json.loads((git_dir / "checkout-freshness-stamp.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


with tempfile.TemporaryDirectory() as temporary_directory:
    tmp = Path(temporary_directory)

    # The "remote": an ordinary repository reached by path.
    origin = tmp / "origin-repo"
    origin.mkdir()
    git(["init", "-q", "-b", "main"], origin)
    configure_identity(origin)
    commit_file(origin, "shared.txt", "first\n", "first commit")

    # The machine's clone, parked on main, and a seat worktree on its branch.
    reference = tmp / "reference-clone"
    git(["clone", "-q", str(origin), str(reference)], tmp)
    configure_identity(reference)
    seat = tmp / "seat-worktree"
    git(["worktree", "add", "-q", "-b", "seat", str(seat), "main"], reference)
    configure_identity(seat)
    seat_git_dir = Path(git(["rev-parse", "--absolute-git-dir"], seat).stdout.strip())

    def rebase_state_dirs_absent(checkout_git_dir: Path) -> bool:
        return not any((checkout_git_dir / marker).exists()
                       for marker in ("rebase-merge", "rebase-apply"))

    # -----------------------------------------------------------------------
    # A NEVER-PUSHED branch is rebased by the hook. Walked and ruled
    # 2026-09-15. Not the merge nedschorus#324 removed: that landed merge
    # commits on FROZEN heads; this moves only heads nobody else has and
    # creates no merge commit.
    # -----------------------------------------------------------------------
    commit_file(origin, "scripts/advance-one.py", "one\n", "advance one")
    head_before = git(["rev-parse", "HEAD"], seat).stdout.strip()
    result = run_catch_up(["--cwd", str(seat)])
    check("a never-pushed, clean seat behind main is REBASED at turn end",
          (seat / "scripts/advance-one.py").exists()
          and git(["rev-parse", "HEAD"], seat).stdout.strip() != head_before,
          result.stdout + result.stderr)
    check("the rebase leaves no merge commit",
          git(["rev-list", "--merges", "--count", "origin/main..HEAD"], seat).stdout.strip() == "0")
    check("a seat with no commits of its own, moved where main changed no standing "
          "instruction, is told nothing",
          agent_text(result) == "", agent_text(result))
    check("the USER hears nothing about routine drift",
          display_text(result) == "", display_text(result))
    check("never a block", never_blocks(result), result.stdout)
    check("the stamp records 0 behind and the rebase",
          stamp_of(seat).get("behind") == 0 and "rebased 1" in stamp_of(seat).get("last_action", ""),
          str(stamp_of(seat)))
    check("the reference clone fast-forwarded on the same pass, silently",
          (reference / "scripts/advance-one.py").exists() and display_text(result) == "",
          result.stdout)

    again = run_catch_up(["--cwd", str(seat)])
    check("level with main, the next turn end says nothing to anyone",
          again.stdout.strip() == "", again.stdout)

    # Throttle: with a fresh stamp and a long interval, no fetch happens, so a
    # new remote commit stays unseen and the run is silent.
    commit_file(origin, "advance-two.txt", "two\n", "advance two")
    quiet = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--interval-seconds", "3600", "--cwd", str(seat)],
        capture_output=True, text=True, check=False,
    )
    check("a fresh stamp suppresses the fetch (throttle)", quiet.stdout.strip() == "",
          quiet.stdout)
    check("the throttled run still says 0 behind", stamp_of(seat).get("behind") == 0)

    # A DIRTY tree is skipped, told once, and attempted again every turn end.
    (seat / "shared.txt").write_text("local edit in progress\n", encoding="utf-8")
    result = run_catch_up(["--cwd", str(seat)])
    check("a dirty tree is not rebased",
          not (seat / "advance-two.txt").exists()
          and (seat / "shared.txt").read_text(encoding="utf-8") == "local edit in progress\n",
          result.stdout)
    check("the agent is told why it was not updated, and what to do",
          "Not updated: 1 uncommitted tracked change(s)" in agent_text(result)
          and "commit or set aside any uncommitted work" in agent_text(result),
          agent_text(result))
    check("the skipped note ends by saying it is not for the user, byte for byte",
          agent_text(result).endswith("\n" + NOT_FOR_THE_USER_LINE), agent_text(result))
    check("the user hears nothing about a dirty seat", display_text(result) == "",
          display_text(result))
    dirty_again = run_catch_up(["--cwd", str(seat)])
    check("the dirty tree is not told again while nothing changed",
          agent_text(dirty_again) == "", agent_text(dirty_again))
    # rebase.autoStash=true would stash a dirty tree and rebase it anyway. The
    # dirty-tree blocker fires before the rebase is reached, so this case pins
    # the BEHAVIOUR; the script's --no-autostash is the second line of defence
    # behind it, and a mutation dropping the flag alone does not fail here.
    git(["config", "rebase.autoStash", "true"], seat)
    with_autostash = run_catch_up(["--cwd", str(seat)])
    check("rebase.autoStash=true does not make a dirty tree get rebased (blocker first)",
          not (seat / "advance-two.txt").exists()
          and (seat / "shared.txt").read_text(encoding="utf-8") == "local edit in progress\n",
          with_autostash.stdout)
    git(["config", "--unset", "rebase.autoStash"], seat)
    git(["checkout", "--", "shared.txt"], seat)
    cleaned = run_catch_up(["--cwd", str(seat)])
    check("the moment the tree is clean, the rebase goes (attempted every turn end)",
          (seat / "advance-two.txt").exists(), cleaned.stdout)
    check("and, with no commits of its own and no standing instruction changed, "
          "nothing is told", agent_text(cleaned) == "", agent_text(cleaned))

    # A CONFLICT is attempted, aborted cleanly, and named.
    commit_file(seat, "shared.txt", "seat version\n", "seat edits shared")
    commit_file(origin, "shared.txt", "origin version\n", "origin edits shared")
    head_before = git(["rev-parse", "HEAD"], seat).stdout.strip()
    result = run_catch_up(["--cwd", str(seat)])
    check("a conflicting rebase is aborted: HEAD unchanged, tree clean",
          git(["rev-parse", "HEAD"], seat).stdout.strip() == head_before
          and git(["status", "--porcelain"], seat).stdout.strip() == "",
          result.stdout)
    check("no rebase state is left behind", rebase_state_dirs_absent(seat_git_dir)
          and not (seat_git_dir / "MERGE_HEAD").exists())
    check("the agent is told the conflicting file and how to proceed",
          "conflicts on shared.txt" in agent_text(result)
          and "run `git rebase --abort`, which puts everything back" in agent_text(result),
          agent_text(result))
    check("the conflict note says when to resolve now and when to finish first",
          "resolve the conflict and run `git rebase --continue`" in agent_text(result)
          and "finish what you are doing first" in agent_text(result), agent_text(result))
    check("the conflict note no longer says staying behind costs nothing",
          "costs nothing" not in agent_text(result), agent_text(result))
    check("the conflict note names the pre-push check and the selective test run",
          "refused by the pre-push check" in agent_text(result)
          and "--only-suites-whose-recorded-inputs-changed-since origin/main" in agent_text(result),
          agent_text(result))
    check("the conflict note ends by saying it is not for the user, byte for byte",
          agent_text(result).endswith("\n" + NOT_FOR_THE_USER_LINE), agent_text(result))
    check("the user hears nothing about a conflict either", display_text(result) == "",
          display_text(result))
    check("the conflict is not told again while nothing changed",
          agent_text(run_catch_up(["--cwd", str(seat)])) == "")
    check("the stamp says why", "rebase conflict" in stamp_of(seat).get("last_action", ""),
          str(stamp_of(seat)))
    # Put the seat level with main, with one commit of its own, for the cases
    # below. (A by-hand rebase here would hit the same conflict.)
    git(["reset", "-q", "--hard", "origin/main"], seat)
    commit_file(seat, "seat-own.txt", "mine\n", "the seat's own work")
    check("(fixture) the seat is level with main and carries one own commit",
          git(["rev-list", "--count", "HEAD..origin/main"], seat).stdout.strip() == "0"
          and git(["rev-parse", "--abbrev-ref", "HEAD"], seat).stdout.strip() == "seat")

    # A rebase git REFUSES before starting (PR #388 review, reproduced by the
    # lane): an untracked file at the exact path main just added. rc=1 "could
    # not detach HEAD", no rebase state, and `git rebase --abort` would exit
    # 128. That is a refusal, not a failed abort — told to the agent once,
    # NEVER a user line.
    commit_file(origin, "scripts/lands-on-main.py", "main's\n", "main adds a script")
    (seat / "scripts").mkdir(exist_ok=True)
    (seat / "scripts/lands-on-main.py").write_text("untracked local\n", encoding="utf-8")
    head_before = git(["rev-parse", "HEAD"], seat).stdout.strip()
    result = run_catch_up(["--cwd", str(seat)])
    check("a rebase git refuses before starting leaves HEAD and the tree untouched",
          git(["rev-parse", "HEAD"], seat).stdout.strip() == head_before
          and rebase_state_dirs_absent(seat_git_dir)
          and (seat / "scripts/lands-on-main.py").read_text(encoding="utf-8") == "untracked local\n",
          result.stdout)
    check("and is NOT a user line — git never entered the tree",
          display_text(result) == "", display_text(result))
    check("the agent is told git refused, and what to do",
          "Not updated: git refused" in agent_text(result)
          and "commit or set aside any uncommitted work" in agent_text(result),
          agent_text(result))
    check("the stamp says refused", stamp_of(seat).get("last_action", "").startswith("rebase refused"),
          str(stamp_of(seat)))
    refused_again = run_catch_up(["--cwd", str(seat)])
    check("a refusal is told once: the next turn end is silent on both channels",
          refused_again.stdout.strip() == "", refused_again.stdout)
    (seat / "scripts/lands-on-main.py").unlink()
    cleared = run_catch_up(["--cwd", str(seat)])
    check("with the file gone, the next turn end rebases (attempted every turn end)",
          "was rebased" in agent_text(cleared)
          and (seat / "scripts/lands-on-main.py").read_text(encoding="utf-8") == "main's\n",
          agent_text(cleared))

    # -----------------------------------------------------------------------
    # MISBEHAVIOUR is told to the agent, with what to do about it, and never
    # put on the user's display.
    # -----------------------------------------------------------------------
    # A merge from main on a working branch. Note the branch is 0 behind after
    # it — a drift-first design would never look.
    merge_seat = tmp / "merge-only-worktree"
    git(["worktree", "add", "-q", "-b", "merge-only", str(merge_seat), "main~1"], reference)
    configure_identity(merge_seat)
    git(["fetch", "-q", "origin"], merge_seat)
    git(["-c", "core.editor=true", "merge", "--no-ff", "--no-edit", "origin/main"], merge_seat)
    result = run_catch_up(["--cwd", str(merge_seat)])
    merge_sha = git(["rev-parse", "--short=12", "HEAD"], merge_seat).stdout.strip()
    merge_note = agent_text(result)
    check("a merge from main on a working branch is told to the AGENT, with its merge commit",
          f"checkout-freshness: merge-only carries 1 merge commit(s) from main ({merge_sha})."
          in merge_note, result.stdout)
    for instruction_line in (
            "This project brings a branch up to date by rebasing it onto main, not by "
            "merging main into it.",
            "If the branch was never pushed, rebase it onto origin/main.",
            "If it was pushed, leave its history and tell the agent-seat merge-lane-2, with "
            "SendMessage, which merge commits it carries."):
        check(f"the merge note says: {instruction_line}",
              instruction_line in merge_note, merge_note)
    check("the merge note is not put on the user's display (systemMessage)",
          display_text(result) == "", result.stdout)
    check("the merge note ends with the agent's not-for-the-user sentence",
          merge_note.endswith("\n" + NOT_FOR_THE_USER_LINE), merge_note)
    check("and only once",
          "merge commit(s) from main" not in agent_text(run_catch_up(["--cwd", str(merge_seat)])))
    # A merge of another topic branch is not the banned thing.
    topic_seat = tmp / "topic-merge-worktree"
    git(["worktree", "add", "-q", "-b", "topic-a", str(topic_seat), "main"], reference)
    configure_identity(topic_seat)
    commit_file(topic_seat, "topic-a.txt", "a\n", "topic a work")
    git(["branch", "-q", "topic-b", "main"], reference)
    other = tmp / "topic-b-worktree"
    git(["worktree", "add", "-q", str(other), "topic-b"], reference)
    configure_identity(other)
    commit_file(other, "topic-b.txt", "b\n", "topic b work")
    git(["-c", "core.editor=true", "merge", "--no-ff", "--no-edit", "topic-b"], topic_seat)
    result = run_catch_up(["--cwd", str(topic_seat)])
    check("a merge of another topic branch is NOT reported as a merge from main",
          "merge commit(s) from main" not in agent_text(result), agent_text(result))

    # -----------------------------------------------------------------------
    # A PUSHED branch is never moved. The agent is told once per update of
    # main, and told to leave it.
    # -----------------------------------------------------------------------
    commit_file(origin, "scripts/advance-three.py", "three\n", "advance three")
    git(["push", "-q", "origin", "seat"], seat)
    head_before = git(["rev-parse", "HEAD"], seat).stdout.strip()
    result = run_catch_up(["--cwd", str(seat)])
    check("a pushed seat behind main is NOT moved",
          git(["rev-parse", "HEAD"], seat).stdout.strip() == head_before
          and not (seat / "scripts/advance-three.py").exists(), result.stdout)
    check("the agent is told the drift, the frozen state, and the named files",
          "seat is 1 behind origin/main" in agent_text(result)
          and "head pushed and equal to origin/seat (frozen" in agent_text(result)
          and "scripts/advance-three.py" in agent_text(result), agent_text(result))
    # The heading over the listing, byte for byte, with the line under it.
    # User-ruled 2026-09-18: it read "Older here than on main", which is false
    # of a file main ADDED — this checkout has no copy at all — and with
    # --no-renames the list also holds the old path of a rename, which main
    # deleted. The ruled words are true of changed, added and deleted paths
    # alike.
    check("the listing sits under the heading the user ruled, byte for byte",
          "\nChanged on main since your merge base:\n"
          "  scripts your tests run against (1): scripts/advance-three.py\n"
          in agent_text(result), agent_text(result))
    check("and told to leave it and start the next topic from main",
          "Do not rebase or amend it" in agent_text(result)
          and "git checkout -b <name> origin/main" in agent_text(result), agent_text(result))
    # A conflict with main is the one case a commit on top cannot clear; the
    # pushed-branch advice sends it to the hand-merge (CLAUDE.md, "How a change
    # reaches main", worded 2026-09-30).
    check("a pushed branch is told how to clear a conflict with main, byte for byte",
          "If it conflicts with main, clear the conflict with the hand-merge that "
          "scripts/branch-conflict-check.py describes." in agent_text(result),
          agent_text(result))
    check("the pushed head's status says how a conflict is cleared, byte for byte",
          "(frozen: a fix is a new commit on top, never an amend; a conflict with "
          "main is cleared by a hand-merge)" in agent_text(result), agent_text(result))
    check("the pushed-branch note ends by saying it is not for the user, byte for byte",
          agent_text(result).endswith("\n" + NOT_FOR_THE_USER_LINE), agent_text(result))
    check("the user hears nothing", display_text(result) == "", display_text(result))
    check("the stamp records the head state", stamp_of(seat).get("head_state") == "pushed")
    check("main standing still: nothing more is said",
          run_catch_up(["--cwd", str(seat)]).stdout.strip() == "")
    commit_file(origin, "scripts/advance-four.py", "four\n", "advance four")
    moved = run_catch_up(["--cwd", str(seat)])
    check("main moving tells the agent again, with the new file named",
          "seat is 2 behind" in agent_text(moved) and "scripts/advance-four.py" in agent_text(moved),
          agent_text(moved))
    check("the telling key is branch, main's tip, and pushed-or-not",
          set(stamp_of(seat).get("last_told", {})) == {"branch", "main_tip", "pushed"}
          and stamp_of(seat)["last_told"]["pushed"] is True, str(stamp_of(seat).get("last_told")))
    # The seat's own movements are not updates of main.
    commit_file(seat, "more.txt", "more\n", "a commit on top of the pushed head")
    own = run_catch_up(["--cwd", str(seat)])
    check("a commit on top of the pushed head does not re-tell", agent_text(own) == "",
          agent_text(own))
    check("nor is it moved", not (seat / "scripts/advance-four.py").exists())
    git(["push", "-q", "origin", "seat"], seat)
    check("pushing that commit does not re-tell (still pushed)",
          agent_text(run_catch_up(["--cwd", str(seat)])) == "")

    # HEAD a strict ancestor of its remote branch: a fix pushed from elsewhere.
    git(["reset", "-q", "--hard", "HEAD~1"], seat)
    result = run_catch_up(["--cwd", str(seat)])
    check("a head behind its own remote is recorded as such and not moved",
          stamp_of(seat).get("head_state") == "behind-remote"
          and not (seat / "scripts/advance-four.py").exists(), str(stamp_of(seat)))
    check("and is not a user line, nor a re-tell (still pushed; the key is unchanged)",
          display_text(result) == "" and agent_text(result) == "", result.stdout)
    commit_file(origin, "advance-four-b.txt", "4b\n", "advance four b")
    result = run_catch_up(["--cwd", str(seat)])
    check("at the next update of main the behind-remote state reaches the agent",
          "head behind origin/seat by 1 commit(s) pushed from elsewhere" in agent_text(result)
          and "fast-forward to it before working here" in agent_text(result), agent_text(result))
    git(["reset", "-q", "--hard", "origin/seat"], seat)

    # A REWRITTEN pushed head: amend after push. The second misbehaviour.
    git(["commit", "-q", "--amend", "--no-edit", "-m", "amended after push"], seat)
    amended_head = git(["rev-parse", "--short=12", "HEAD"], seat).stdout.strip()
    pushed_head = git(["rev-parse", "--short=12", "origin/seat"], seat).stdout.strip()
    result = run_catch_up(["--cwd", str(seat)])
    rewritten_note = agent_text(result)
    check("an amend after a push is told to the AGENT as a rewritten head",
          f"checkout-freshness: seat's HEAD ({amended_head}) no longer contains its pushed "
          f"head origin/seat ({pushed_head}): an amend or a rebase rewrote pushed commits, "
          f"which moves the code under its reviewer." in rewritten_note, result.stdout)
    for instruction_line in (
            "Do not push this HEAD.",
            "Put your change back as one commit on top of origin/seat, then push."):
        check(f"the rewritten-head note says: {instruction_line}",
              instruction_line in rewritten_note, rewritten_note)
    check("the rewritten-head note is not put on the user's display (systemMessage)",
          display_text(result) == "", result.stdout)
    check("and the state is recorded as diverged",
          stamp_of(seat).get("head_state") == "diverged-from-remote", str(stamp_of(seat)))
    check("reported once",
          "no longer contains its pushed head" not in agent_text(run_catch_up(["--cwd", str(seat)])))
    git(["reset", "-q", "--hard", "origin/seat"], seat)

    # never-pushed -> pushed flips the advice, so the push re-tells once.
    flip = tmp / "flip-worktree"
    git(["worktree", "add", "-q", "-b", "flip", str(flip), "main~2"], reference)
    configure_identity(flip)
    (flip / "shared.txt").write_text("dirty\n", encoding="utf-8")
    first = run_catch_up(["--cwd", str(flip)])
    check("(fixture) a dirty never-pushed branch gets the rebase advice",
          "run `git rebase origin/main`" in agent_text(first), agent_text(first))
    git(["checkout", "--", "shared.txt"], flip)
    commit_file(flip, "flip.txt", "flip\n", "flip's own work")
    git(["push", "-q", "origin", "flip"], flip)
    pushed_now = run_catch_up(["--cwd", str(flip)])
    check("pushing a never-pushed branch re-tells once, with the advice flipped",
          "Do not rebase or amend it" in agent_text(pushed_now), agent_text(pushed_now))

    # PUSHED HISTORY UNDER A NEW NAME (GHI "The checkout-freshness hook treats a
    # new branch cut at a pull request's pushed head as never pushed, and
    # rebases it"). A fix-round agent cannot check out a pull request's own
    # branch in a second worktree, so it cuts a NEW branch at the pushed head.
    # No origin/<that name> exists, yet its commits are the pull request's,
    # under review: the hook must not rebase it. Before the fix, every case
    # below failed: the hook called the branch "unpushed" and rebased it.
    fix_round = tmp / "fix-round-worktree"
    pushed_head = git(["rev-parse", "origin/flip"], reference).stdout.strip()
    git(["worktree", "add", "-q", "-b", "flip-fix-round", str(fix_round), "origin/flip"],
        reference)
    configure_identity(fix_round)
    commit_file(origin, "scripts/advance-five-a.py", "5a\n", "advance five a")
    result = run_catch_up(["--cwd", str(fix_round)])
    check("a new branch cut at a pushed head, behind main, is NOT rebased",
          git(["rev-parse", "HEAD"], fix_round).stdout.strip() == pushed_head
          and not (fix_round / "scripts/advance-five-a.py").exists(), result.stdout)
    check("its head state is pushed-history, not unpushed",
          stamp_of(fix_round).get("head_state") == "pushed-history", str(stamp_of(fix_round)))
    check("the agent is told where the commits already are",
          "no branch of this name on origin, but its commits are already on origin/flip"
          in agent_text(result), agent_text(result))
    check("and told why it is not rebased and what to do, byte for byte",
          "This branch's commits are already on GitHub under another branch name, so the "
          "branch is treated as pushed and is not rebased: a pushed head may be under "
          "review, and a rebase would rewrite it. Do not rebase or amend those commits. A "
          "fix is a new commit on top. If it conflicts with main, clear the conflict with "
          "the hand-merge that scripts/branch-conflict-check.py describes."
          in agent_text(result), agent_text(result))
    check("the pushed-history note never tells the agent to rebase",
          "git rebase origin/main" not in agent_text(result), agent_text(result))
    check("the pushed-history note ends by saying it is not for the user, byte for byte",
          agent_text(result).endswith("\n" + NOT_FOR_THE_USER_LINE), agent_text(result))
    check("the user hears nothing about a pushed-history branch", display_text(result) == "",
          display_text(result))

    # The agent's fix commit on top is on no remote branch; the commits beneath
    # it are. The check has to look past HEAD, and the branch stays unrebased.
    commit_file(fix_round, "fix.txt", "the fix\n", "the fix-round's commit on top")
    fix_head = git(["rev-parse", "HEAD"], fix_round).stdout.strip()
    commit_file(origin, "scripts/advance-five-b.py", "5b\n", "advance five b")
    result = run_catch_up(["--cwd", str(fix_round)])
    check("with an unpushed fix commit on top, the branch is still NOT rebased",
          git(["rev-parse", "HEAD"], fix_round).stdout.strip() == fix_head
          and git(["rev-parse", "HEAD~1"], fix_round).stdout.strip() == pushed_head
          and not (fix_round / "scripts/advance-five-b.py").exists(), result.stdout)
    check("and its head state is still pushed-history",
          stamp_of(fix_round).get("head_state") == "pushed-history", str(stamp_of(fix_round)))

    # The other side of the line: a genuinely new branch, whose own commit is on
    # no remote branch, is still rebased exactly as before.
    fresh = tmp / "fresh-topic-worktree"
    git(["worktree", "add", "-q", "-b", "fresh-topic", str(fresh), "origin/main~1"], reference)
    configure_identity(fresh)
    commit_file(fresh, "fresh.txt", "new work\n", "a new topic's own commit, never pushed")
    result = run_catch_up(["--cwd", str(fresh)])
    check("a new branch whose own commit is on no remote branch is still rebased",
          (fresh / "scripts/advance-five-b.py").exists() and (fresh / "fresh.txt").exists()
          and "was rebased" in agent_text(result), agent_text(result) + result.stderr)

    # Detached HEAD: an agent-seat's own checkout, moved forward when it holds
    # nothing of its own, and otherwise told why not and what to do. The texts
    # are spelled out here, not imported, so a typo in the script fails a case.
    detached_not_moved_second_line = (
        "CLAUDE.md, the skills and the hooks load from this checkout, so until it moves, the "
        "files listed above stay older here than on main.")
    detached_work_line = (
        "It holds work of its own: run `git switch -c <branch name>` to put that work on a "
        "branch, and commit any uncommitted changes there; from then on the hook's rules for a "
        "branch apply.")
    detached_bisect_line = (
        "A bisect is in progress: finish it or abort it; the next turn's end moves the "
        "checkout forward.")
    detached_refused_condition_lines = (
        "If git names an untracked file that main would overwrite, move that file out of the "
        "way; the next turn's end moves the checkout forward.\n"
        "If git names anything else, leave the checkout as it is: the refusal has been "
        "reported to the user.")

    def detached_worktree_behind_main(name):
        git(["fetch", "-q"], reference)
        path = tmp / name
        git(["worktree", "add", "-q", "--detach", str(path), "origin/main~1"], reference)
        configure_identity(path)
        return path

    def head_of(checkout):
        return git(["rev-parse", "HEAD"], checkout).stdout.strip()

    def main_tip():
        return git(["rev-parse", "main"], origin).stdout.strip()

    commit_file(origin, "scripts/detached-advance.py", "advance\n", "advance for the detached cases")
    detached = detached_worktree_behind_main("detached-worktree")
    (detached / "seat-scratch-note.md").write_text("untracked\n", encoding="utf-8")
    result = run_catch_up(["--cwd", str(detached)])
    check("a detached HEAD with nothing of its own and an untracked file is moved forward",
          head_of(detached) == main_tip() and (detached / "seat-scratch-note.md").exists()
          and (detached / "scripts/detached-advance.py").exists(), agent_text(result))
    check("and, main having changed no standing instruction, the agent is told nothing",
          agent_text(result) == "", agent_text(result))
    check("and the user is told nothing", display_text(result) == "", display_text(result))
    result = run_catch_up(["--cwd", str(detached)])
    check("a detached HEAD already at origin/main prints nothing",
          result.stdout.strip() == "", result.stdout)

    tracked = detached_worktree_behind_main("detached-tracked-change-worktree")
    tracked_head = head_of(tracked)
    (tracked / "shared.txt").write_text("edited here\n", encoding="utf-8")
    result = run_catch_up(["--cwd", str(tracked)])
    check("a detached HEAD with an uncommitted tracked change is not moved",
          head_of(tracked) == tracked_head, agent_text(result))
    check("and message B names the change and gives the work-of-its-own line alone",
          "This checkout's detached HEAD was not moved forward: 1 uncommitted tracked "
          f"change(s).\n{detached_not_moved_second_line}\n{detached_work_line}\n"
          f"{NOT_FOR_THE_USER_LINE}" in agent_text(result), agent_text(result))
    result = run_catch_up(["--cwd", str(tracked)])
    check("message B is not repeated while main has not moved",
          agent_text(result) == "", agent_text(result))
    git(["checkout", "--", "shared.txt"], tracked)
    result = run_catch_up(["--cwd", str(tracked)])
    check("once the change is gone, the next turn's end moves it forward",
          head_of(tracked) == main_tip(), agent_text(result))
    check("and the move drops the queued not-moved note instead of repeating it",
          "was not moved forward" not in agent_text(result), agent_text(result))

    own = detached_worktree_behind_main("detached-own-commit-worktree")
    commit_file(own, "own-work.txt", "own\n", "a commit on a detached HEAD")
    own_head = head_of(own)
    result = run_catch_up(["--cwd", str(own)])
    check("a detached HEAD with a commit of its own is not moved, and is told so",
          head_of(own) == own_head
          and "not moved forward: 1 commit(s) of its own.\n" in agent_text(result)
          and f"{detached_not_moved_second_line}\n{detached_work_line}\n"
          f"{NOT_FOR_THE_USER_LINE}" in agent_text(result), agent_text(result))

    both = detached_worktree_behind_main("detached-own-commit-and-change-worktree")
    commit_file(both, "own-work.txt", "own\n", "a commit on a detached HEAD")
    (both / "shared.txt").write_text("edited here\n", encoding="utf-8")
    result = run_catch_up(["--cwd", str(both)])
    check("with a commit and a change, message B names both and gives the work line once",
          "not moved forward: 1 commit(s) of its own; 1 uncommitted tracked change(s).\n"
          in agent_text(result) and agent_text(result).count(detached_work_line) == 1,
          agent_text(result))

    bisecting = detached_worktree_behind_main("detached-bisect-worktree")
    bisecting_head = head_of(bisecting)
    bisect_git_dir = Path(git(["rev-parse", "--absolute-git-dir"], bisecting).stdout.strip())
    (bisect_git_dir / "BISECT_LOG").write_text("git bisect start\n", encoding="utf-8")
    result = run_catch_up(["--cwd", str(bisecting)])
    check("a detached HEAD mid-bisect is not moved, and gets the in-progress line alone",
          head_of(bisecting) == bisecting_head
          and "not moved forward: a bisect in progress.\n" in agent_text(result)
          and f"{detached_not_moved_second_line}\n{detached_bisect_line}\n"
          f"{NOT_FOR_THE_USER_LINE}" in agent_text(result)
          and detached_work_line not in agent_text(result), agent_text(result))

    rebasing = detached_worktree_behind_main("detached-rebase-with-own-commit-worktree")
    commit_file(rebasing, "own-work.txt", "own\n", "a commit on a detached HEAD")
    rebasing_git_dir = Path(git(["rev-parse", "--absolute-git-dir"], rebasing).stdout.strip())
    (rebasing_git_dir / "rebase-merge").mkdir()
    result = run_catch_up(["--cwd", str(rebasing)])
    check("mid-rebase with a commit of its own, message B names both but gives only the "
          "in-progress line",
          "not moved forward: a rebase in progress; 1 commit(s) of its own.\n"
          in agent_text(result)
          and f"{detached_not_moved_second_line}\n" + detached_bisect_line.replace(
              "A bisect", "A rebase") + f"\n{NOT_FOR_THE_USER_LINE}" in agent_text(result)
          and detached_work_line not in agent_text(result), agent_text(result))
    (rebasing_git_dir / "rebase-merge").rmdir()

    commit_file(origin, "scripts/detached-collision.py", "main's copy\n",
                "main adds a file a detached checkout holds untracked")
    colliding = detached_worktree_behind_main("detached-untracked-collision-worktree")
    (colliding / "scripts").mkdir(exist_ok=True)
    (colliding / "scripts/detached-collision.py").write_text("my copy\n", encoding="utf-8")
    colliding_head = head_of(colliding)
    result = run_catch_up(["--cwd", str(colliding)])
    check("a fast-forward git refuses over an untracked file leaves the checkout and the file",
          head_of(colliding) == colliding_head
          and (colliding / "scripts/detached-collision.py").read_text(encoding="utf-8")
          == "my copy\n", agent_text(result))
    check("and message B gives git's error, naming the file, and the refused lines",
          "not moved forward: git refused the fast-forward.\n" in agent_text(result)
          and any(line.startswith("Git refused the fast-forward: ")
                  and "scripts/detached-collision.py" in line
                  for line in agent_text(result).splitlines())
          and f"\n{detached_refused_condition_lines}\n{NOT_FOR_THE_USER_LINE}"
          in agent_text(result), agent_text(result))
    check("and a refusal over an untracked file is not sent to the user",
          display_text(result) == "", display_text(result))

    locked = detached_worktree_behind_main("detached-index-locked-worktree")
    locked_head = head_of(locked)
    locked_git_dir = Path(git(["rev-parse", "--absolute-git-dir"], locked).stdout.strip())
    (locked_git_dir / "index.lock").write_text("", encoding="utf-8")
    result = run_catch_up(["--cwd", str(locked)])
    check("a refusal for any other reason leaves the checkout where it was",
          head_of(locked) == locked_head, agent_text(result))
    check("and the user is sent one line naming the checkout and git's error",
          f"catch-up: {locked.resolve()} is 1 behind origin/main and could not fast-forward: "
          in display_text(result) and "index.lock" in display_text(result),
          display_text(result))
    check("and the agent is told the refusal was reported",
          "Git refused the fast-forward: " in agent_text(result)
          and detached_refused_condition_lines in agent_text(result), agent_text(result))
    result = run_catch_up(["--cwd", str(locked)])
    check("the same refusal is not sent to the user twice",
          display_text(result) == "", display_text(result))
    (locked_git_dir / "index.lock").unlink()
    result = run_catch_up(["--cwd", str(locked)])
    check("once the lock is gone, the next turn's end moves it forward",
          head_of(locked) == main_tip() and "Git refused" not in agent_text(result),
          agent_text(result))
    commit_file(origin, "scripts/detached-relock-advance.py", "advance\n",
                "advance after a detached checkout was moved")
    (locked_git_dir / "index.lock").write_text("", encoding="utf-8")
    result = run_catch_up(["--cwd", str(locked)])
    check("after a move, the same refusal again is sent to the user again",
          "could not fast-forward: " in display_text(result)
          and "index.lock" in display_text(result), display_text(result))
    (locked_git_dir / "index.lock").unlink()

    unreadable = detached_worktree_behind_main("detached-unreadable-status-worktree")
    unreadable_head = head_of(unreadable)
    unreadable_index = Path(git(["rev-parse", "--absolute-git-dir"],
                                unreadable).stdout.strip()) / "index"
    saved_index = unreadable_index.read_bytes()
    unreadable_index.write_bytes(b"not an index")
    result = run_catch_up(["--cwd", str(unreadable)])
    check("a detached HEAD whose git status cannot be read is not moved, and git is not asked",
          head_of(unreadable) == unreadable_head
          and "not moved forward: git status unreadable.\n" in agent_text(result)
          and "Git refused the fast-forward" not in agent_text(result), agent_text(result))
    unreadable_index.write_bytes(saved_index)

    sequencing = detached_worktree_behind_main("detached-paused-sequence-worktree")
    sequencing_head = head_of(sequencing)
    sequence_base = head_of(sequencing)
    commit_file(sequencing, "shared.txt", "sequence one\n", "sequence commit one")
    commit_file(sequencing, "sequence-two.txt", "two\n", "sequence commit two")
    picked = git(["rev-list", "--reverse", f"{sequence_base}..HEAD"], sequencing).stdout.split()
    git(["checkout", "-q", "--detach", sequence_base], sequencing)
    (sequencing / "shared.txt").write_text("a different line\n", encoding="utf-8")
    git(["commit", "-qam", "a conflicting base"], sequencing)
    sequencing_head = head_of(sequencing)
    git(["cherry-pick", "--no-commit", *picked], sequencing)
    git(["checkout", "--ours", "shared.txt"], sequencing)
    git(["add", "shared.txt"], sequencing)
    sequencing_git_dir = Path(git(["rev-parse", "--absolute-git-dir"], sequencing).stdout.strip())
    check("the fixture is a paused sequence with a clean index and no CHERRY_PICK_HEAD",
          (sequencing_git_dir / "sequencer").is_dir()
          and not (sequencing_git_dir / "CHERRY_PICK_HEAD").exists()
          and git(["status", "--porcelain", "--untracked-files=no"],
                  sequencing).stdout.strip() == "",
          git(["status"], sequencing).stdout)
    result = run_catch_up(["--cwd", str(sequencing)])
    check("a detached HEAD with a paused cherry-pick sequence is not moved, and is told so",
          head_of(sequencing) == sequencing_head
          and "not moved forward: a cherry-pick in progress" in agent_text(result)
          and detached_bisect_line.replace("A bisect", "A cherry-pick") in agent_text(result),
          agent_text(result))
    git(["cherry-pick", "--abort"], sequencing)

    # The ghi-info shape (nedschorus#334): no commits of its own, far behind,
    # never pushed — so it is simply brought level, the same fast-forward the
    # box's ghi-info-ask now does for itself (#375).
    ghi = tmp / "ghi-info-worktree"
    first_commit = git(["rev-list", "--max-parents=0", "main"], reference).stdout.strip()
    git(["worktree", "add", "-q", "-b", "ghi-info", str(ghi), first_commit], reference)
    configure_identity(ghi)
    result = run_catch_up(["--cwd", str(ghi)])
    check("a never-pushed branch with no own commits, far behind, is brought level",
          never_blocks(result) and (ghi / "scripts/advance-four.py").exists()
          and agent_text(result) == "", result.stdout)

    # A foreign merge in progress blocks the rebase and survives untouched.
    foreign_git_dir = Path(git(["rev-parse", "--absolute-git-dir"], ghi).stdout.strip())
    (foreign_git_dir / "MERGE_HEAD").write_text("0" * 40 + "\n", encoding="utf-8")
    commit_file(origin, "advance-five.txt", "five\n", "advance five")
    result = run_catch_up(["--cwd", str(ghi)])
    check("a foreign merge in progress survives untouched, and the agent is told why",
          (foreign_git_dir / "MERGE_HEAD").exists() and not (ghi / "advance-five.txt").exists()
          and "a git operation in progress (MERGE_HEAD)" in agent_text(result),
          agent_text(result))
    (foreign_git_dir / "MERGE_HEAD").unlink()

    # The reference copy with a local commit is left alone — and THAT is a
    # user line: someone left work where none belongs.
    commit_file(reference, "local-on-main.txt", "local\n", "a commit main does not have")
    commit_file(origin, "advance-six.txt", "six\n", "advance six")
    result = run_catch_up(["--cwd", str(reference)])
    check("a reference with local commits is left alone, and the USER is told",
          "left alone" in display_text(result) and "local commit" in display_text(result),
          result.stdout)
    check("the diverged reference was not moved", not (reference / "advance-six.txt").exists())
    # Once per REASON, not per turn. This line runs at every turn end off local
    # refs, and before PR #388 it went to plain stdout nobody read, so nobody
    # noticed it repeated. As the user's systemMessage a repeat is the noise the
    # 2026-09-15 ruling removed.
    check("the same reason at the next turn end is not reported to the user again",
          display_text(run_catch_up(["--cwd", str(reference)])) == "")
    commit_file(origin, "advance-seven.txt", "seven\n", "advance seven")
    check("main moving does not re-report while the reason is unchanged",
          display_text(run_catch_up(["--cwd", str(reference)])) == "")
    (reference / "shared.txt").write_text("also dirty\n", encoding="utf-8")
    changed = run_catch_up(["--cwd", str(reference)])
    check("a changed reason is reported once more",
          "uncommitted tracked change" in display_text(changed)
          and "local commit" in display_text(changed), display_text(changed))
    check("and then not again",
          display_text(run_catch_up(["--cwd", str(reference)])) == "")
    check("the reason is what the stamp keys on",
          stamp_of(reference).get("last_reference_blockers") and
          any("uncommitted" in reason for reason in stamp_of(reference)["last_reference_blockers"]),
          str(stamp_of(reference).get("last_reference_blockers")))
    # The operator-facing mode is a launch log: it says so every time.
    operator = run_catch_up(["--reference-pull", "--repo", str(reference)])
    operator_again = run_catch_up(["--reference-pull", "--repo", str(reference)])
    check("--reference-pull reports the same blocked reference every time",
          "left alone" in operator.stdout and "left alone" in operator_again.stdout,
          operator.stdout + operator_again.stdout)
    git(["checkout", "--", "shared.txt"], reference)

    # A session seated outside any repository does nothing, silently.
    nowhere = tmp / "not-a-repo"
    nowhere.mkdir()
    result = run_catch_up(["--cwd", str(nowhere)])
    check("a non-repository cwd exits silently", result.returncode == 0 and result.stdout.strip() == "",
          f"rc={result.returncode} {result.stdout}")

    # A failed fetch is named in the telling (ruled 2026-09-15, item 7).
    broken = tmp / "broken-fetch-worktree"
    git(["worktree", "add", "-q", "-b", "broken", str(broken), "main~1"], reference)
    configure_identity(broken)
    git(["push", "-q", "origin", "broken"], broken)      # pushed, so it is told, not rebased
    git(["remote", "set-url", "origin", str(tmp / "no-such-remote")], reference)
    result = run_catch_up(["--cwd", str(broken)])
    git(["remote", "set-url", "origin", str(origin)], reference)
    check("a failed fetch is named, so a stale list says it is stale",
          "fetch failed at" in agent_text(result) and "this list may be stale" in agent_text(result),
          agent_text(result) + result.stderr)

    # --cwd means "no stdin". stdin is held OPEN: a closed pipe reads as EOF
    # and would pass whether or not the run waited on it.
    held = subprocess.Popen(
        [sys.executable, str(SCRIPT_PATH), "--interval-seconds", "0", "--cwd", str(seat)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        held.wait(timeout=30)
        hung = False
    except subprocess.TimeoutExpired:
        hung = True
        held.kill()
    held.stdin.close(); held.stdout.close(); held.stderr.close()
    check("--cwd never waits on stdin (a terminal would hang)", not hung,
          "the run was still waiting after 30s")

    # While the agent answers a Stop hook, the hook does nothing at all: with a
    # zero interval it would otherwise fetch and rewrite the stamp.
    stamp_path = Path(git(["rev-parse", "--absolute-git-dir"], seat).stdout.strip()) / "checkout-freshness-stamp.json"
    stamp_before = stamp_path.read_bytes() if stamp_path.exists() else None
    answering = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--interval-seconds", "0"],
        input=json.dumps({"cwd": str(seat), "stop_hook_active": True}),
        capture_output=True, text=True, check=False)
    stamp_after = stamp_path.read_bytes() if stamp_path.exists() else None
    check("stop_hook_active: silent, and no fetch or stamp write while the agent answers a Stop hook",
          answering.returncode == 0 and answering.stdout == "" and answering.stderr == ""
          and stamp_after == stamp_before,
          f"rc={answering.returncode} {answering.stdout} {answering.stderr} stamp changed: {stamp_after != stamp_before}")

    # The real wiring reads cwd from the stdin payload.
    payload = json.dumps({"cwd": str(seat)})
    from_stdin = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--interval-seconds", "0"],
        input=payload, capture_output=True, text=True, check=False)
    check("the stdin payload drives cwd, as the hook calls it",
          from_stdin.returncode == 0 and never_blocks(from_stdin),
          from_stdin.stdout + from_stdin.stderr)

    # The report mode states behind/ahead and the fetch age.
    result = run_catch_up(["--report", "--repo", str(seat)])
    check("the report names behind, ahead, and fetch age",
          "behind" in result.stdout and "ahead" in result.stdout and "fetched" in result.stdout,
          result.stdout)

# The module, imported for the cases below that call into it directly.
import importlib.util
specification = importlib.util.spec_from_file_location("catch_up_module", SCRIPT_PATH)
catch_up_module = importlib.util.module_from_spec(specification)
specification.loader.exec_module(catch_up_module)
import contextlib, io

# ---------------------------------------------------------------------------
# PR #87's review: git's prose must be read in a stable locale
# ---------------------------------------------------------------------------
# The merge path decides whether it owns a conflict by looking for the word
# "CONFLICT" in git's output. git translates that word — a German-locale host
# prints "KONFLIKT" — so on such a host the match fails, the cleanup that
# should abort the merge is skipped, and the seat's tree is left parked
# mid-merge. A stub git reports the locale it was handed.
import os as _os
import shutil as _shutil
import tempfile as _tempfile

with _tempfile.TemporaryDirectory() as locale_scratch:
    locale_scratch = Path(locale_scratch)
    stub_directory = locale_scratch / "stub"
    stub_directory.mkdir()
    stub_git = stub_directory / "git"
    stub_git.write_text(
        "#!/bin/sh\n"
        f'printf "%s" "${{LC_ALL-UNSET}}" > {locale_scratch / "seen-locale"}\n'
        "exit 128\n",
        encoding="utf-8")
    stub_git.chmod(0o755)
    environment = dict(_os.environ)
    environment["PATH"] = f"{stub_directory}{_os.pathsep}{environment.get('PATH', '')}"
    environment["LC_ALL"] = "de_DE.UTF-8"
    subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--interval-seconds", "0",
         "--report", "--repo", str(locale_scratch)],
        capture_output=True, text=True, check=False, env=environment,
    )
    seen_locale = (locale_scratch / "seen-locale")
    check("git is run in the C locale, so its prose is stable to match on",
          seen_locale.exists() and seen_locale.read_text(encoding="utf-8") == "C",
          seen_locale.read_text(encoding="utf-8") if seen_locale.exists() else "stub never ran")

# ---------------------------------------------------------------------------
# PR #87's review: an unknowable count must not leave the old number standing
# ---------------------------------------------------------------------------
# The seat's own path already nulls behind/ahead when the comparison cannot be
# made, because a preserved stale count renders as knowledge. The reference
# path and the report path kept the previous numbers.
with tempfile.TemporaryDirectory() as unknowable_scratch:
    unknowable_scratch = Path(unknowable_scratch)
    lone = unknowable_scratch / "lone-checkout"
    lone.mkdir()
    git(["init", "-q", "-b", "main"], lone)
    configure_identity(lone)
    commit_file(lone, "a.txt", "one\n", "first")

    def seed_stale_counts(checkout: Path):
        """Put numbers in the stamp that a later run must not leave standing."""
        git_dir = Path(git(["rev-parse", "--absolute-git-dir"], checkout).stdout.strip())
        stamp_file = git_dir / "checkout-freshness-stamp.json"
        stamp = {}
        try:
            stamp = json.loads(stamp_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
        stamp["behind"], stamp["ahead"] = 7, 3
        stamp_file.write_text(json.dumps(stamp), encoding="utf-8")

    # There is no origin/main here at all, so the comparison is unknowable.
    seed_stale_counts(lone)
    run_catch_up(["--reference-pull", "--repo", str(lone)])
    stamp = stamp_of(lone)
    check("an unknowable count nulls the reference checkout's recorded behind",
          stamp.get("behind") is None, json.dumps(stamp))
    check("an unknowable count nulls the reference checkout's recorded ahead",
          stamp.get("ahead") is None, json.dumps(stamp))

    seed_stale_counts(lone)
    result = run_catch_up(["--report", "--repo", str(lone)])
    stamp = stamp_of(lone)
    check("the report says the comparison could not be made",
          "no origin/main" in result.stdout, result.stdout)
    check("an unknowable count nulls the behind the report leaves behind",
          stamp.get("behind") is None, json.dumps(stamp))
    check("an unknowable count nulls the ahead the report leaves behind",
          stamp.get("ahead") is None, json.dumps(stamp))

# ---------------------------------------------------------------------------
# A git that never ran must not be readable as a real answer
# ---------------------------------------------------------------------------
# run_git synthesizes a CompletedProcess when git cannot be launched at all.
# It used to synthesize returncode 1 — which git uses as a genuine answer
# elsewhere in this project ("HEAD does not exist"), so a launch failure and a
# real "no" were the same value. That collision was a live defect in the
# session-location guard (PR #103); it is only latent here, because every
# caller in this file tests `!= 0`. Pinned so the two files keep one meaning.
with tempfile.TemporaryDirectory() as no_git_scratch:
    no_git_scratch = Path(no_git_scratch)
    empty_path_directory = no_git_scratch / "no-git-here"
    empty_path_directory.mkdir()
    saved_path = os.environ.get("PATH", "")
    try:
        os.environ["PATH"] = str(empty_path_directory)
        unlaunchable = catch_up_module.run_git(["status"], no_git_scratch, timeout=5)
    finally:
        os.environ["PATH"] = saved_path
    check("a git that cannot be launched reports GIT_DID_NOT_RUN",
          unlaunchable.returncode == catch_up_module.GIT_DID_NOT_RUN,
          str(unlaunchable.returncode))
    check("a git that cannot be launched does not report 1, which git uses as an answer",
          unlaunchable.returncode != 1, str(unlaunchable.returncode))
    check("callers still see it as a failure",
          unlaunchable.returncode != 0, str(unlaunchable.returncode))
    # A git that did not run must never read as "unpushed" — the one answer
    # that authorises a rebase (PR #388 review).
    saved_path = os.environ["PATH"]
    try:
        os.environ["PATH"] = str(empty_path_directory)
        unknown_state, unknown_text = catch_up_module.head_state(no_git_scratch, "seat")
    finally:
        os.environ["PATH"] = saved_path
    check("head_state with git unlaunchable is 'unknown', never 'unpushed'",
          unknown_state == "unknown" and "git did not run" in unknown_text,
          (unknown_state, unknown_text))

# ---------------------------------------------------------------------------
# The pushed-history check failing is "unknown", never "unpushed"
# ---------------------------------------------------------------------------
# git answers that no origin/<branch> exists, and then the check of whether
# the branch's commits are on a remote branch fails. That failure must not
# fall through to "unpushed", the one answer that authorises a rebase. A shim
# fails every rev-list and hands every other call to the real git.
with tempfile.TemporaryDirectory() as shim_scratch:
    shim_scratch = Path(shim_scratch)
    shim_origin = shim_scratch / "origin"
    shim_origin.mkdir()
    git(["init", "-q", "-b", "main"], shim_origin)
    configure_identity(shim_origin)
    commit_file(shim_origin, "a.txt", "a\n", "first")
    shim_clone = shim_scratch / "clone"
    git(["clone", "-q", str(shim_origin), str(shim_clone)], shim_scratch)
    configure_identity(shim_clone)
    git(["checkout", "-q", "-b", "a-branch-never-pushed"], shim_clone)
    commit_file(shim_clone, "b.txt", "b\n", "own work")
    rev_list_failing = shim_scratch / "rev-list-failing-git"
    rev_list_failing.mkdir()
    (rev_list_failing / "git").write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "rev-list" ]; then\n'
        '  printf "shimmed: rev-list fails\\n" >&2\n'
        "  exit 3\n"
        "fi\n"
        f'exec "{shutil.which("git")}" "$@"\n', encoding="utf-8")
    (rev_list_failing / "git").chmod(0o755)
    saved_path = os.environ["PATH"]
    try:
        os.environ["PATH"] = f"{rev_list_failing}{os.pathsep}{saved_path}"
        failed_check_state, failed_check_text = catch_up_module.head_state(
            shim_clone, "a-branch-never-pushed")
    finally:
        os.environ["PATH"] = saved_path
    check("a pushed-history check that fails is 'unknown', never 'unpushed'",
          failed_check_state == "unknown"
          and "could not check whether this branch's commits are on a remote branch"
          in failed_check_text, (failed_check_state, failed_check_text))
    check("(control) with git answering, the same branch is 'unpushed'",
          catch_up_module.head_state(shim_clone, "a-branch-never-pushed")[0] == "unpushed",
          str(catch_up_module.head_state(shim_clone, "a-branch-never-pushed")))

# ---------------------------------------------------------------------------
# --reference-pull must still speak. Its only other case exercises the
# unknowable-count path, which queues nothing, so the flush there was never
# reached: deleting it silenced the mode with the suite green (review finding,
# 2026-08-31). Both launchers call this mode at every launch.
# ---------------------------------------------------------------------------

with tempfile.TemporaryDirectory() as reference_pull_scratch:
    tmp = Path(reference_pull_scratch)
    origin = tmp / "origin-repo"
    origin.mkdir()
    git(["init", "-q", "-b", "main"], origin)
    configure_identity(origin)
    commit_file(origin, "shared.txt", "first\n", "first commit")
    reference = tmp / "reference-clone"
    git(["clone", "-q", str(origin), str(reference)], tmp)
    configure_identity(reference)
    commit_file(origin, "advance.txt", "one\n", "advance")

    pulled = run_catch_up(["--reference-pull", "--repo", str(reference)])
    check("--reference-pull reports the fast-forward it performed",
          "reference checkout" in pulled.stdout and "fast-forwarded" in pulled.stdout,
          pulled.stdout + pulled.stderr)
    check("--reference-pull actually advanced the checkout",
          (reference / "advance.txt").exists())
    check("--reference-pull still speaks PLAIN TEXT — launchers read it on a terminal",
          emitted_object(pulled) is None, pulled.stdout)
    check("and the operator's terminal line does not carry the agent's not-for-the-user sentence",
          NOT_FOR_THE_USER_LINE not in pulled.stdout, pulled.stdout)
    check("a successful pull clears the reference's reason key",
          "last_reference_blockers" not in stamp_of(reference), str(stamp_of(reference)))


# ---------------------------------------------------------------------------
# A reference whose fetch failed must not read as up to date. It computed
# "0 behind" off refs the failed fetch never updated, and returned without a
# word (user-approved fix, 2026-09-17, backlog-recheck walk item 1, fix 11).
# ---------------------------------------------------------------------------

with tempfile.TemporaryDirectory() as reference_fetch_scratch:
    tmp = Path(reference_fetch_scratch)
    origin = tmp / "origin-repo"
    origin.mkdir()
    git(["init", "-q", "-b", "main"], origin)
    configure_identity(origin)
    commit_file(origin, "shared.txt", "first\n", "first commit")
    reference = tmp / "reference-clone"
    git(["clone", "-q", str(origin), str(reference)], tmp)
    configure_identity(reference)
    seat = tmp / "seat-worktree"
    git(["worktree", "add", "-q", "-b", "seat", str(seat), "main"], reference)

    # origin moves on, and then cannot be reached: local refs still say 0 behind.
    commit_file(origin, "unseen.txt", "unseen\n", "a commit the failed fetch never saw")
    git(["remote", "set-url", "origin", str(tmp / "no-such-remote")], reference)

    unreachable_hook = run_catch_up(["--cwd", str(seat)])
    check("a reference whose fetch failed tells the user its 0 behind may be stale",
          "reference checkout" in display_text(unreachable_hook)
          and "fetch failed at" in display_text(unreachable_hook),
          unreachable_hook.stdout + unreachable_hook.stderr)
    check("and says it once, not at every turn end while the fetch keeps failing",
          display_text(run_catch_up(["--cwd", str(seat)])) == "")
    unreachable_operator = run_catch_up(["--reference-pull", "--repo", str(reference)])
    unreachable_operator_again = run_catch_up(["--reference-pull", "--repo", str(reference)])
    check("--reference-pull reports the failed fetch every time",
          "fetch failed at" in unreachable_operator.stdout
          and "fetch failed at" in unreachable_operator_again.stdout,
          unreachable_operator.stdout + unreachable_operator_again.stdout)

    git(["remote", "set-url", "origin", str(origin)], reference)
    reachable_hook = run_catch_up(["--cwd", str(seat)])
    check("once the fetch works again the reference catches up and the failure is not repeated",
          (reference / "unseen.txt").exists() and "fetch failed" not in display_text(reachable_hook),
          reachable_hook.stdout)
    check("and the failure's reason key is cleared",
          "last_reference_blockers" not in stamp_of(reference), str(stamp_of(reference)))


# ---------------------------------------------------------------------------
# A blocked reference whose fetch starts or stops failing is reported again.
# The skip line's once-per-reason key was the blocker list alone, so while
# the same blocker stayed, the fetch note it carries never reached the user
# (PR 666's review, merge-lane-2, item 1).
# ---------------------------------------------------------------------------

with tempfile.TemporaryDirectory() as blocked_reference_fetch_scratch:
    tmp = Path(blocked_reference_fetch_scratch)
    origin = tmp / "origin-repo"
    origin.mkdir()
    git(["init", "-q", "-b", "main"], origin)
    configure_identity(origin)
    commit_file(origin, "shared.txt", "first\n", "first commit")
    reference = tmp / "reference-clone"
    git(["clone", "-q", str(origin), str(reference)], tmp)
    configure_identity(reference)
    commit_file(origin, "advance.txt", "one\n", "advance")
    (reference / "shared.txt").write_text("dirty\n", encoding="utf-8")

    blocked = run_catch_up(["--cwd", str(reference)])
    check("a blocked reference off a good fetch is reported once, with no fetch note",
          "left alone" in display_text(blocked)
          and "uncommitted tracked change" in display_text(blocked)
          and "fetch failed" not in display_text(blocked), display_text(blocked))
    check("the same blocker off a good fetch is not reported again",
          display_text(run_catch_up(["--cwd", str(reference)])) == "")

    git(["remote", "set-url", "origin", str(tmp / "no-such-remote")], reference)
    failing = run_catch_up(["--cwd", str(reference)])
    check("the same blocker is reported again when its fetch starts failing, naming the failed fetch",
          "left alone" in display_text(failing)
          and "uncommitted tracked change" in display_text(failing)
          and "fetch failed at" in display_text(failing),
          failing.stdout + failing.stderr)
    check("and not again while the fetch keeps failing",
          display_text(run_catch_up(["--cwd", str(reference)])) == "")

    git(["remote", "set-url", "origin", str(origin)], reference)
    recovered = run_catch_up(["--cwd", str(reference)])
    check("the same blocker is reported again when the fetch works again, without the note",
          "left alone" in display_text(recovered)
          and "uncommitted tracked change" in display_text(recovered)
          and "fetch failed" not in display_text(recovered),
          recovered.stdout + recovered.stderr)
    check("the reference was never moved while it was blocked",
          not (reference / "advance.txt").exists())


# ---------------------------------------------------------------------------
# changed_here_versus_main: the line names what MOVED, never a fixed list of
# categories. The first draft asserted "your tests, hooks, skills and documents
# here are older than main" at every printing; on the seat that built it, ten
# scripts and four documents had moved and zero hooks and zero skills had, so
# two thirds of the sentence was false every time. The user caught it — "are
# you sure they are older than main, or are you just saying that?" — and these
# are the cases that keep it honest.
# ---------------------------------------------------------------------------

with tempfile.TemporaryDirectory() as naming_scratch:
    tmp = Path(naming_scratch)
    origin = tmp / "origin-repo"
    origin.mkdir()
    git(["init", "-q", "-b", "main"], origin)
    configure_identity(origin)
    commit_file(origin, "shared.txt", "first\n", "first commit")
    seat = tmp / "seat"
    git(["clone", "-q", str(origin), str(seat)], tmp)
    configure_identity(seat)
    git(["checkout", "-q", "-b", "seat"], seat)

    def named(*commits):
        """Land the given (path, message) pairs on main and ask what moved."""
        for path, message in commits:
            commit_file(origin, path, f"{path}\n", message)
        git(["fetch", "--quiet", "origin"], seat)
        return catch_up_module.format_obsolete_files(
            catch_up_module.obsolete_files_by_category(seat))

    check("a changed script is NAMED, with the reason its category matters",
          named(("scripts/one.py", "a script"))
          == "  scripts your tests run against (1): scripts/one.py")
    listing = named(("docs/a.md", "a doc"), (".claude/skills/s/SKILL.md", "a skill"))
    check("categories come in the order an agent should care about them",
          listing.index("skills you run under") < listing.index("scripts your tests"),
          listing)
    check("each category names its own files and counts them",
          "skills you run under (1): .claude/skills/s/SKILL.md" in listing
          and "documents you may cite (1): docs/a.md" in listing, listing)
    check("instructions are their own category",
          "your standing instructions (1): CLAUDE.md" in named(("CLAUDE.md", "rules")),
          named())
    check("hooks and their wiring share one category, having one reason",
          "hooks and wiring that run on your work (2)"
          in named((".claude/hooks/a-guard.py", "a hook"),
                   (".claude/settings.json", "wiring")), named())
    check("an uncategorised path is still surfaced rather than hidden",
          "other files (1): Makefile" in named(("Makefile", "a makefile")), named())

    # nc-systems/ holds a system kept whole — its code, its tests and its
    # design of record in one directory — so a change there is named as what
    # it is. Until 2026-09-22 the directory matched no category and fell to
    # the catch-all: observed live that day, when
    # nc-systems/handoff/handoff-design.md moved on main and this hook
    # reported it as "other files". The pair is a design AND a program, so the
    # case proves the category is decided by the path's prefix, not by the
    # extension; the catch-all still holds this scratch repository's Makefile
    # from the case above, so what is asserted is that nc-systems/ is not on
    # that line.
    systems_listing = named(("nc-systems/handoff/handoff-design.md", "a design of record"),
                            ("nc-systems/handoff/handoff-supervisor.py", "the system's code"))
    check("a system kept whole is named as one, its design of record and its code together",
          "systems you build on, code and design of record (2): "
          "nc-systems/handoff/handoff-design.md, nc-systems/handoff/handoff-supervisor.py"
          in systems_listing, systems_listing)
    catch_all_line = next((line for line in systems_listing.splitlines()
                           if line.lstrip().startswith("other files")), "")
    check("and never under the catch-all, the least informative label available",
          "nc-systems/" not in catch_all_line, catch_all_line or systems_listing)

    # A wide gap is capped, or the agent reads a wall and skims it. Its own
    # repository, so the count is exactly what this case put there.
    wide_origin = tmp / "wide-origin"
    wide_origin.mkdir()
    git(["init", "-q", "-b", "main"], wide_origin)
    configure_identity(wide_origin)
    commit_file(wide_origin, "shared.txt", "first\n", "first commit")
    wide_seat = tmp / "wide-seat"
    git(["clone", "-q", str(wide_origin), str(wide_seat)], tmp)
    configure_identity(wide_seat)
    git(["checkout", "-q", "-b", "wide"], wide_seat)
    for index in range(10):
        commit_file(wide_origin, f"scripts/wide-{index}.py", "x\n", f"wide {index}")
    git(["fetch", "--quiet", "origin"], wide_seat)
    wide = catch_up_module.format_obsolete_files(
        catch_up_module.obsolete_files_by_category(wide_seat))
    named_count = wide.count("scripts/wide-")
    check("a wide category names only the first few files",
          named_count == catch_up_module.DRIFT_FILES_NAMED_PER_CATEGORY,
          f"{named_count} named: {wide}")
    check("and counts the rest rather than listing them",
          "and 6 more" in wide and "scripts your tests run against (10)" in wide, wide)

    # THE REGRESSION THE USER CAUGHT: a gap containing no skills and no hooks
    # must not mention skills or hooks.
    origin2 = tmp / "origin-two"
    origin2.mkdir()
    git(["init", "-q", "-b", "main"], origin2)
    configure_identity(origin2)
    commit_file(origin2, "shared.txt", "first\n", "first commit")
    seat2 = tmp / "seat-two"
    git(["clone", "-q", str(origin2), str(seat2)], tmp)
    configure_identity(seat2)
    git(["checkout", "-q", "-b", "seat"], seat2)
    commit_file(origin2, "scripts/only.py", "only\n", "only a script moved")
    git(["fetch", "--quiet", "origin"], seat2)
    scripts_only = catch_up_module.format_obsolete_files(
        catch_up_module.obsolete_files_by_category(seat2))
    check("a gap with no skills and no hooks mentions neither",
          "skill" not in scripts_only and "hooks" not in scripts_only
          and "scripts/only.py" in scripts_only, scripts_only)

    # THREE DOTS, NOT TWO. Two-dot diff compares the trees outright and would
    # report this branch's OWN work as something main changed — the branch that
    # built this feature would have claimed its own new files as missing.
    commit_file(seat2, ".claude/skills/mine/SKILL.md", "mine\n", "the SEAT writes a skill")
    own_work = catch_up_module.format_obsolete_files(
        catch_up_module.obsolete_files_by_category(seat2))
    check("the branch's own new skill is NOT reported as something main changed",
          "skill" not in own_work, own_work)
    check("and what main really changed is still named",
          "scripts/only.py" in own_work, own_work)

    # A FILE MAIN RENAMED AWAY from the path this branch still holds it at.
    # Rename detection is on by default and `git diff --name-only` prints only
    # a rename's DESTINATION, so without --no-renames the old path goes
    # unlisted — the one file guaranteed to conflict, since main deleted it.
    # The edit-warning hook's obsolete_path_set() had the same defect and got
    # the same fix. Its own repositories, so no rename leaks into the counts
    # the cases above pin.
    #
    # The two checks after the fixture checks FAIL against this script as it
    # was before --no-renames. That was checked by running this file against
    # that revision, not assumed: a test that passes on both sides of a fix
    # pins nothing.
    rename_origin = tmp / "rename-origin"
    rename_origin.mkdir()
    git(["init", "-q", "-b", "main"], rename_origin)
    configure_identity(rename_origin)
    commit_file(rename_origin, "scripts/main-will-rename-this.py", "held at the old path\n",
                "a file main will later rename away from this path")
    rename_seat = tmp / "rename-seat"
    git(["clone", "-q", str(rename_origin), str(rename_seat)], tmp)
    configure_identity(rename_seat)
    git(["checkout", "-q", "-b", "seat"], rename_seat)
    git(["mv", "scripts/main-will-rename-this.py", "scripts/main-renamed-it-to-this.py"],
        rename_origin)
    git(["commit", "-q", "-m", "rename a file out from under the branch"], rename_origin)
    git(["fetch", "--quiet", "origin"], rename_seat)
    check("(fixture) the branch still holds the renamed file at the old path",
          (rename_seat / "scripts/main-will-rename-this.py").is_file())
    check("(fixture) and origin/main no longer has that path at all",
          git(["cat-file", "-e", "origin/main:scripts/main-will-rename-this.py"],
              rename_seat).returncode != 0)
    renamed_listing = catch_up_module.format_obsolete_files(
        catch_up_module.obsolete_files_by_category(rename_seat))
    check("a file main renamed away is listed at the OLD path, the one this branch holds",
          "scripts/main-will-rename-this.py" in renamed_listing, renamed_listing)
    check("and the rename is listed as both its paths, the one main deleted and the one it added",
          renamed_listing == ("  scripts your tests run against (2): "
                              "scripts/main-renamed-it-to-this.py, "
                              "scripts/main-will-rename-this.py"),
          renamed_listing)

    # Uncomputable is silent, never invented: the clause is dropped whole.
    not_a_repository = tmp / "not-a-repository"
    not_a_repository.mkdir()
    check("a directory that is not a checkout yields no listing at all",
          catch_up_module.obsolete_files_by_category(not_a_repository) == [],
          str(catch_up_module.obsolete_files_by_category(not_a_repository)))


# ---------------------------------------------------------------------------
# The two `git rebase --abort` shapes healthy git cannot produce
# (nedschorus#389). PR #388's blocking fix decides abort-failed by whether
# rebase state REMAINS on disk, never by the abort's exit code, and carries
# the abort's own stderr. Reverting that to the pre-fix `returncode != 0` form
# left every case green: the suite had no abort that exits non-zero, because
# a real git never does. So a regression of the exact defect #388 removed
# would have been silent. Each shape is produced by a `git` shim first on
# PATH that intercepts only `rebase --abort` and hands every other call to
# the real binary.
# ---------------------------------------------------------------------------

with tempfile.TemporaryDirectory() as abort_scratch:
    tmp = Path(abort_scratch)
    real_git = shutil.which("git")

    def shim(name: str, abort_body: str) -> Path:
        directory = tmp / name
        directory.mkdir()
        script = directory / "git"
        script.write_text(
            "#!/bin/sh\n"
            'if [ "$1" = "rebase" ] && [ "$2" = "--abort" ]; then\n'
            f"{abort_body}\n"
            "fi\n"
            f'exec "{real_git}" "$@"\n',
            encoding="utf-8")
        script.chmod(0o755)
        return directory

    # Shape 1: the abort DOES its job, then exits 128 anyway.
    abort_done_bad_exit = shim(
        "abort-done-bad-exit",
        f'  "{real_git}" rebase --abort\n'
        '  printf "shimmed: abort done, exit 128 regardless\\n" >&2\n'
        "  exit 128")
    # Shape 2: the abort refuses and leaves the rebase state where it was.
    abort_refuses = shim(
        "abort-refuses",
        '  printf "shimmed abort failure: refusing to touch the tree\\n" >&2\n'
        "  exit 1")

    def conflicting_seat(name: str):
        """A never-pushed seat whose next rebase onto main must conflict."""
        origin = tmp / f"{name}-origin"
        origin.mkdir()
        git(["init", "-q", "-b", "main"], origin)
        configure_identity(origin)
        commit_file(origin, "shared.txt", "first\n", "first commit")
        reference = tmp / f"{name}-reference"
        git(["clone", "-q", str(origin), str(reference)], tmp)
        configure_identity(reference)
        seat = tmp / f"{name}-seat"
        git(["worktree", "add", "-q", "-b", "seat", str(seat), "main"], reference)
        configure_identity(seat)
        commit_file(seat, "shared.txt", "seat version\n", "seat edits shared")
        commit_file(origin, "shared.txt", "origin version\n", "origin edits shared")
        git_dir = Path(git(["rev-parse", "--absolute-git-dir"], seat).stdout.strip())
        return seat, git_dir

    def rebase_state_present(git_dir: Path) -> bool:
        return any((git_dir / marker).exists() for marker in ("rebase-merge", "rebase-apply"))

    # --- shape 1: abort succeeded, exit code lied ---------------------------
    seat, git_dir = conflicting_seat("shape-one")
    head_before = git(["rev-parse", "HEAD"], seat).stdout.strip()
    result = run_catch_up(["--cwd", str(seat)], path_prefix=str(abort_done_bad_exit))
    check("an abort that succeeds but exits non-zero is a CONFLICT, decided from the disk",
          "conflicts on shared.txt" in agent_text(result), agent_text(result) + result.stderr)
    check("and is NOT a user line", display_text(result) == "", display_text(result))
    check("the tree is exactly as it was: HEAD unchanged, no rebase state",
          git(["rev-parse", "HEAD"], seat).stdout.strip() == head_before
          and not rebase_state_present(git_dir)
          and git(["status", "--porcelain"], seat).stdout.strip() == "",
          git(["status"], seat).stdout)
    check("the stamp says conflict, not abort-failed",
          stamp_of(seat).get("last_action", "").startswith("rebase conflict"),
          str(stamp_of(seat).get("last_action")))

    # --- shape 2: abort refused, state left behind --------------------------
    seat, git_dir = conflicting_seat("shape-two")
    head_before = git(["rev-parse", "HEAD"], seat).stdout.strip()
    result = run_catch_up(["--cwd", str(seat)], path_prefix=str(abort_refuses))
    check("an abort that leaves rebase state behind is ABORT-FAILED",
          stamp_of(seat).get("last_action") == "rebase failed AND could not abort"
          and rebase_state_present(git_dir), str(stamp_of(seat).get("last_action")))
    check("and IS a user line, carrying the ABORT's own stderr",
          "was left mid-rebase" in display_text(result)
          and "shimmed abort failure: refusing to touch the tree" in display_text(result),
          display_text(result))
    check("the agent is told to inspect before doing anything else",
          "could not be aborted cleanly" in agent_text(result)
          and "Inspect `git status`" in agent_text(result), agent_text(result))
    # Both channels speak on this one run: the sentence must end the agent's
    # note and be absent from the user's line, side by side.
    check("the abort-failed note ends by saying it is not for the user; the user line does not",
          agent_text(result).endswith("\n" + NOT_FOR_THE_USER_LINE)
          and NOT_FOR_THE_USER_LINE not in display_text(result),
          result.stdout)
    # The structural claim merge-lane set out to test: a true abort-failed
    # cannot repeat. It holds, and for a reason one step earlier than the
    # in-progress blocker: a tree parked mid-rebase has a DETACHED HEAD sitting
    # at origin/main's tip, so it reads as 0 behind and nothing is said on
    # either channel. The agent was told once, at the failure, to inspect
    # `git status` before doing anything else; that is the whole telling.
    following = run_catch_up(["--cwd", str(seat)])
    check("the next turn end repeats NOTHING: no user line, no telling, nothing attempted",
          following.stdout.strip() == "" and rebase_state_present(git_dir),
          following.stdout)
    check("and the turn after that is silent too",
          run_catch_up(["--cwd", str(seat)]).stdout.strip() == "")
    git(["rebase", "--abort"], seat)
    check("(fixture) a real abort restores the seat",
          not rebase_state_present(git_dir)
          and git(["rev-parse", "HEAD"], seat).stdout.strip() == head_before)

    # The shims pass every other call through: a seat whose rebase is clean
    # rebases normally under a shim, because no abort is ever reached.
    git(["reset", "-q", "--hard", "origin/main"], seat)
    commit_file(seat, "seat-only.txt", "mine\n", "the seat's own, non-conflicting work")
    commit_file(tmp / "shape-two-origin", "advance.txt", "more\n", "main moves on")
    result = run_catch_up(["--cwd", str(seat)], path_prefix=str(abort_refuses))
    check("a shim intercepts only the abort: a clean rebase still goes through it",
          "was rebased onto origin/main" in agent_text(result), agent_text(result) + result.stderr)


# ---------------------------------------------------------------------------
# The conflict exception (user-ruled 2026-09-21, fix approved 2026-09-22)
# ---------------------------------------------------------------------------
# A merge from main whose parents CONFLICT is the hand merge the user allowed —
# the author had no choice — and is NOT reported. One whose parents merge
# cleanly is the catch-up nedschorus#324 banned and still is. The rename case
# below is the head of PR "A conflict is the one case a commit on top cannot
# clear" (600) in miniature: git's default rename detection re-merges it
# CLEAN, so without `-X no-renames` the hook would keep reporting the pull
# request that created the exception. Both not-reported cases FAIL
# against this script without the fix, and the rename one fails again if the
# flag alone is dropped — checked by running this file against each, not
# assumed.
# ---------------------------------------------------------------------------

with tempfile.TemporaryDirectory() as exception_scratch:
    exception_tmp = Path(exception_scratch)
    real_git = shutil.which("git")

    def seat_on_main(name: str):
        """A fresh origin, reference clone and seat worktree cut from main."""
        exception_origin = exception_tmp / f"{name}-origin"
        exception_origin.mkdir()
        git(["init", "-q", "-b", "main"], exception_origin)
        configure_identity(exception_origin)
        commit_file(exception_origin, "shared.txt", "first\n", "first commit")
        commit_file(exception_origin, "scripts/main-will-move-this.py", "held here\n",
                    "a script main will later move")
        exception_reference = exception_tmp / f"{name}-reference"
        git(["clone", "-q", str(exception_origin), str(exception_reference)], exception_tmp)
        configure_identity(exception_reference)
        exception_seat = exception_tmp / f"{name}-seat"
        git(["worktree", "add", "-q", "-b", "seat", str(exception_seat), "main"],
            exception_reference)
        configure_identity(exception_seat)
        return exception_origin, exception_seat

    def merge_main_into(seat_path: Path):
        """Merge origin/main by hand, as the 2026-09-21 procedure has an author
        do it; returns git's exit status so a conflict can be resolved."""
        git(["fetch", "-q", "origin"], seat_path)
        return git(["-c", "core.editor=true", "merge", "--no-ff", "--no-edit", "origin/main"],
                   seat_path).returncode

    def merge_tree_status(seat_path: Path, extra_arguments):
        """What git says about re-merging the seat's merge commit's two parents."""
        return git(["merge-tree", "--write-tree", *extra_arguments, "HEAD^1", "HEAD^2"],
                   seat_path).returncode

    # --- a clean catch-up merge is STILL reported ---------------------------
    clean_origin, clean_seat = seat_on_main("clean-catch-up")
    commit_file(clean_seat, "seat-own.txt", "mine\n", "the seat's own work")
    commit_file(clean_origin, "scripts/unrelated.py", "main's\n", "main advances elsewhere")
    check("(fixture) a catch-up merge of main lands without a conflict",
          merge_main_into(clean_seat) == 0)
    check("(fixture) and its parents re-merge cleanly",
          merge_tree_status(clean_seat, ["-X", "no-renames"]) == 0)
    clean_result = run_catch_up(["--cwd", str(clean_seat)])
    check("a catch-up merge whose parents merge cleanly is still told to the agent",
          "carries 1 merge commit(s) from main" in agent_text(clean_result),
          clean_result.stdout)

    # --- two catch-up merges are counted and named, newest first -------------
    twice_origin, twice_seat = seat_on_main("two-catch-up-merges")
    commit_file(twice_seat, "seat-own.txt", "mine\n", "the seat's own work")
    commit_file(twice_origin, "scripts/unrelated-one.py", "main's\n", "main advances once")
    check("(fixture) the first catch-up merge lands without a conflict",
          merge_main_into(twice_seat) == 0)
    older_merge = git(["rev-parse", "--short=12", "HEAD"], twice_seat).stdout.strip()
    commit_file(twice_origin, "scripts/unrelated-two.py", "main's\n", "main advances twice")
    check("(fixture) the second catch-up merge lands without a conflict",
          merge_main_into(twice_seat) == 0)
    newer_merge = git(["rev-parse", "--short=12", "HEAD"], twice_seat).stdout.strip()
    twice_result = run_catch_up(["--cwd", str(twice_seat)])
    check("a branch with two catch-up merges is told both, counted and named",
          f"seat carries 2 merge commit(s) from main ({newer_merge}, {older_merge})."
          in agent_text(twice_result), twice_result.stdout)

    # --- a merge that RESOLVED a conflict is not reported --------------------
    def hand_resolved_seat(name: str):
        """A seat that merged main by hand and resolved a real conflict — the
        2026-09-21 procedure, end to end."""
        its_origin, its_seat = seat_on_main(name)
        commit_file(its_seat, "shared.txt", "the seat's line\n", "the seat edits shared")
        commit_file(its_origin, "shared.txt", "main's line\n", "main edits shared")
        conflicted = merge_main_into(its_seat) != 0
        (its_seat / "shared.txt").write_text("resolved by hand\n", encoding="utf-8")
        git(["add", "shared.txt"], its_seat)
        git(["-c", "core.editor=true", "commit", "-q", "--no-edit"], its_seat)
        return its_seat, conflicted

    conflict_seat, conflicted = hand_resolved_seat("hand-resolved")
    check("(fixture) merging main by hand conflicts, as it did on the two hand "
          "merges of 2026-09-22", conflicted)
    check("(fixture) the resolution is a merge commit whose second parent is on main",
          git(["rev-list", "--merges", "--count", "origin/main..HEAD"],
              conflict_seat).stdout.strip() == "1")
    conflict_result = run_catch_up(["--cwd", str(conflict_seat)])
    check("a merge that resolved a real conflict is NOT reported: the author had no choice",
          "merge commit(s) from main" not in agent_text(conflict_result),
          conflict_result.stdout)

    # --- the shape of that pull request's head: a file main RENAMED out ----
    # Rename detection merges this silently, so the author's own git reported no
    # conflict while GitHub reported CONFLICTING and refused the merge. The
    # conflict that forced the hand merge is the one seen WITHOUT rename
    # detection, which is why the flag is load-bearing.
    rename_origin, rename_seat = seat_on_main("renamed-under-the-branch")
    commit_file(rename_seat, "scripts/main-will-move-this.py", "the seat's edit\n",
                "the seat edits the script at its old path")
    (rename_origin / "nc-systems").mkdir()
    git(["mv", "scripts/main-will-move-this.py", "nc-systems/main-moved-it-here.py"],
        rename_origin)
    git(["commit", "-q", "-m", "main moves the script out of scripts/"], rename_origin)
    merge_main_into(rename_seat)
    check("(fixture) the parents re-merge CLEAN under git's default rename detection",
          merge_tree_status(rename_seat, []) == 0)
    check("(fixture) and CONFLICT with rename detection off — the conflict GitHub saw",
          merge_tree_status(rename_seat, ["-X", "no-renames"]) == 1)
    rename_result = run_catch_up(["--cwd", str(rename_seat)])
    check("the hand merge of a file main renamed away is NOT reported — the shape "
          "of the head of the pull request that added the exception",
          "merge commit(s) from main" not in agent_text(rename_result),
          rename_result.stdout)

    # --- an error from merge-tree is not an answer: the merge is reported ----
    # merge-tree exits 1 for a conflict AND for an argument it cannot resolve,
    # and a git too old for --write-tree or for -X exits 129 on usage. Neither
    # may read as "conflict", or a misbehaviour disappears silently. Each shape
    # is produced by a `git` shim first on PATH that intercepts only merge-tree.
    def merge_tree_shim(name: str, body: str) -> Path:
        directory = exception_tmp / name
        directory.mkdir()
        script = directory / "git"
        script.write_text(
            "#!/bin/sh\n"
            'if [ "$1" = "merge-tree" ]; then\n'
            f"{body}\n"
            "fi\n"
            f'exec "{real_git}" "$@"\n',
            encoding="utf-8")
        script.chmod(0o755)
        return directory

    unresolvable = merge_tree_shim(
        "merge-tree-exits-one-with-nothing",
        '  printf "shimmed: not something we can merge\\n" >&2\n'
        "  exit 1")
    old_git = merge_tree_shim(
        "merge-tree-unsupported",
        '  printf "shimmed: unknown option --write-tree\\n" >&2\n'
        "  exit 129")

    # A seat each, because a finding is reported once per stamp: the second run
    # on one seat would be silent for that reason, not for the shim's.
    old_git_seat, _ = hand_resolved_seat("merge-tree-unsupported-seat")
    old_git_result = run_catch_up(["--cwd", str(old_git_seat)], path_prefix=str(old_git))
    check("a git too old for the re-merge reports the merge, as the hook did before the exception",
          "carries 1 merge commit(s) from main" in agent_text(old_git_result),
          old_git_result.stdout + old_git_result.stderr)
    unresolvable_seat, _ = hand_resolved_seat("merge-tree-exits-one-seat")
    unresolvable_result = run_catch_up(["--cwd", str(unresolvable_seat)],
                                       path_prefix=str(unresolvable))
    check("merge-tree exiting 1 with no answer is an error, not a conflict: still reported",
          "carries 1 merge commit(s) from main" in agent_text(unresolvable_result),
          unresolvable_result.stdout + unresolvable_result.stderr)
    check("and the hook still exits 0 under both, blocking no turn",
          old_git_result.returncode == 0 and unresolvable_result.returncode == 0
          and never_blocks(old_git_result) and never_blocks(unresolvable_result),
          f"{old_git_result.returncode} {unresolvable_result.returncode}")

    # --- a hand-merge the conflict check called for is not reported ----------
    # CLAUDE.md, "How a change reaches main": a pushed branch that
    # scripts/branch-conflict-check.py reports as `VERDICT: CONFLICT` is cleared
    # by a hand-merge. That program asks git with rename detection ON, as
    # `git merge` and the pre-push hook do; this hook once re-merged the two
    # parents with rename detection OFF only. A file added under a directory the
    # other side moved conflicts only WITH detection (CONFLICT (file location)).
    # So the conflict check ordered the hand-merge, git's own merge stopped and
    # was resolved by hand, and this hook then told the user that the branch did
    # what was ruled out 2026-09-14. The first shape is the merge commit "Merge
    # main to relocate #342's two drafts, and revert two commit-pinned paths"
    # (6bd0aa5850ce) in miniature, the one such merge in main's history
    # (merges_from_main's docstring); the second is the same conflict with the
    # two sides swapped. Both not-reported checks FAIL against the script as it
    # was when it re-merged without rename detection only, each printing the
    # merge-from-main line — checked by running this file against that
    # revision, not assumed.
    conflict_check_path = SCRIPT_PATH.with_name("branch-conflict-check.py")

    def conflict_check_exit_and_verdict_line(seat_path: Path):
        """(exit status, first line) of the real conflict check, run as the
        pre-push hook runs it: git's answer alone, GitHub never asked."""
        ran = subprocess.run([sys.executable, str(conflict_check_path), "--head", "HEAD"],
                             cwd=str(seat_path), capture_output=True, text=True, check=False)
        return ran.returncode, (ran.stdout.splitlines() or [""])[0]

    def move_drafts_directory(repository: Path):
        git(["mv", "docs/drafts", "docs/queue"], repository)
        git(["commit", "-q", "-m", "move docs/drafts to docs/queue"], repository)

    def add_third_draft(repository: Path):
        commit_file(repository, "docs/drafts/third-draft.md", "the third draft\n",
                    "add a third draft under docs/drafts")

    for shape_name, seat_change, main_change, case_name in (
            ("seat-moved-the-directory", move_drafts_directory, add_third_draft,
             "the hand-merge that relocates a file main added under a directory the "
             "branch moved is NOT reported — the conflict check called for it"),
            ("main-moved-the-directory", add_third_draft, move_drafts_directory,
             "the hand-merge that relocates a file the branch added under a directory "
             "main moved is NOT reported — the conflict check called for it")):
        shape_origin, shape_seat = seat_on_main(shape_name)
        # A directory both sides start with, holding two drafts.
        commit_file(shape_origin, "docs/drafts/first-draft.md", "the first draft\n",
                    "main adds a first draft")
        commit_file(shape_origin, "docs/drafts/second-draft.md", "the second draft\n",
                    "main adds a second draft")
        git(["fetch", "-q", "origin"], shape_seat)
        git(["merge", "-q", "--ff-only", "origin/main"], shape_seat)
        seat_change(shape_seat)
        # Pushed, because the rule is about a pushed branch: its head is frozen,
        # so a commit on top is the only other move, and that cannot clear a
        # conflict.
        git(["push", "-q", "origin", "seat"], shape_seat)
        main_change(shape_origin)
        git(["fetch", "-q", "origin"], shape_seat)

        verdict_exit, verdict_line = conflict_check_exit_and_verdict_line(shape_seat)
        check(f"(fixture, {shape_name}) the conflict check reports VERDICT: CONFLICT "
              "and exits 1, on git's answer alone",
              verdict_exit == 1 and verdict_line.startswith("VERDICT: CONFLICT -- "),
              f"exit {verdict_exit}: {verdict_line}")
        check(f"(fixture, {shape_name}) merging main by hand stops on a conflict",
              merge_main_into(shape_seat) != 0)
        # The resolution git itself suggests: the added file goes where the
        # directory went. The merge's message names the resolved file, as
        # CLAUDE.md has a hand-merge do.
        git(["add", "-A"], shape_seat)
        git(["commit", "-q", "-m",
             "Merge origin/main into seat by hand\n\n"
             "Resolved: docs/queue/third-draft.md, moved from docs/drafts/ to "
             "follow the directory."], shape_seat)
        check(f"(fixture, {shape_name}) the resolution is one merge commit whose second "
              "parent is on main, with the added file relocated",
              git(["rev-list", "--merges", "--count", "origin/main..HEAD"],
                  shape_seat).stdout.strip() == "1"
              and git(["merge-base", "--is-ancestor", "HEAD^2", "origin/main"],
                      shape_seat).returncode == 0
              and git(["ls-files", "docs"], shape_seat).stdout.split()
              == ["docs/queue/first-draft.md", "docs/queue/second-draft.md",
                  "docs/queue/third-draft.md"],
              git(["ls-files", "docs"], shape_seat).stdout)
        check(f"(fixture, {shape_name}) the parents CONFLICT under git's default rename "
              "detection, which is what the conflict check asked",
              merge_tree_status(shape_seat, []) == 1)
        check(f"(fixture, {shape_name}) and re-merge CLEAN with rename detection off, "
              "which is all this hook once asked",
              merge_tree_status(shape_seat, ["-X", "no-renames"]) == 0)
        shape_result = run_catch_up(["--cwd", str(shape_seat)])
        check(case_name, "merge commit(s) from main" not in agent_text(shape_result),
              agent_text(shape_result))

    # --- one re-merge errors: the other one's answer decides -----------------
    # The hook re-merges twice, without rename detection and with it. An error
    # from one is not an answer, so it is never a conflict: the merge is
    # skipped only when the OTHER re-merge positively shows a conflict, and is
    # reported when the other is clean. The two shim cases above make both
    # re-merges error; these four make exactly one error, by a `git` shim that
    # intercepts merge-tree only when rename detection is off, or only when it
    # is on. A git with --write-tree but without -X for merge-tree is the real
    # version of the first.
    def merge_tree_shim_for_one_strategy(name: str, without_rename_detection: bool,
                                         body: str) -> Path:
        directory = exception_tmp / name
        directory.mkdir()
        script = directory / "git"
        script.write_text(
            "#!/bin/sh\n"
            'if [ "$1" = "merge-tree" ]; then\n'
            '  case " $* " in\n'
            '    *" no-renames "*) without_rename_detection=yes ;;\n'
            "    *) without_rename_detection=no ;;\n"
            "  esac\n"
            f'  if [ "$without_rename_detection" = "{"yes" if without_rename_detection else "no"}" ]; then\n'
            f"{body}\n"
            "  fi\n"
            "fi\n"
            f'exec "{real_git}" "$@"\n',
            encoding="utf-8")
        script.chmod(0o755)
        return directory

    no_renames_errors = merge_tree_shim_for_one_strategy(
        "merge-tree-errors-without-rename-detection", True,
        '    printf "shimmed: unknown option -X\\n" >&2\n'
        "    exit 129")
    default_errors = merge_tree_shim_for_one_strategy(
        "merge-tree-errors-with-rename-detection", False,
        '    printf "shimmed: fatal\\n" >&2\n'
        "    exit 128")

    def shimmed_merge_tree_statuses(shim_directory: Path, seat_path: Path):
        """(exit without rename detection, exit with it) of re-merging the
        seat's merge commit's parents through a shim, as the hook would."""
        environment = dict(os.environ)
        environment["PATH"] = f"{shim_directory}{os.pathsep}{environment['PATH']}"
        return tuple(
            subprocess.run(["git", "merge-tree", "--write-tree", *strategy_arguments,
                            "HEAD^1", "HEAD^2"], cwd=str(seat_path), env=environment,
                           capture_output=True, text=True, check=False).returncode
            for strategy_arguments in (["-X", "no-renames"], []))

    def clean_catch_up_seat(name: str):
        """A seat that merged main with nothing to resolve: the banned catch-up."""
        its_origin, its_seat = seat_on_main(name)
        commit_file(its_seat, "seat-own.txt", "mine\n", "the seat's own work")
        commit_file(its_origin, "scripts/unrelated.py", "main's\n", "main advances elsewhere")
        merge_main_into(its_seat)
        return its_seat

    # A seat each, for the reason given above: a finding is reported once per stamp.
    for (combination_name, shim_directory, build_seat, expected_statuses,
         expected_reported, case_name) in (
            ("no-renames-errors-default-conflicts", no_renames_errors,
             lambda name: hand_resolved_seat(name)[0], (129, 1), False,
             "an error without rename detection and a conflict with it: NOT reported, "
             "the conflict is an answer"),
            ("no-renames-conflicts-default-errors", default_errors,
             lambda name: hand_resolved_seat(name)[0], (1, 128), False,
             "a conflict without rename detection and an error with it: NOT reported, "
             "the conflict is an answer"),
            ("no-renames-errors-default-clean", no_renames_errors,
             clean_catch_up_seat, (129, 0), True,
             "an error without rename detection and a clean merge with it: still "
             "reported, the error is not a conflict"),
            ("no-renames-clean-default-errors", default_errors,
             clean_catch_up_seat, (0, 128), True,
             "a clean merge without rename detection and an error with it: still "
             "reported, the error is not a conflict")):
        combination_seat = build_seat(combination_name)
        statuses = shimmed_merge_tree_statuses(shim_directory, combination_seat)
        check(f"(fixture, {combination_name}) the shim makes exactly one re-merge error",
              statuses == expected_statuses, str(statuses))
        combination_result = run_catch_up(["--cwd", str(combination_seat)],
                                          path_prefix=str(shim_directory))
        reported = "carries 1 merge commit(s) from main" in agent_text(combination_result)
        check(case_name, reported is expected_reported,
              combination_result.stdout + combination_result.stderr)
        check(f"and the hook exits 0 and blocks no turn ({combination_name})",
              combination_result.returncode == 0 and never_blocks(combination_result),
              str(combination_result.returncode))


# ---------------------------------------------------------------------------
# git output read in its -z form: real paths, never C-quoted or split
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as z_scratch:
    # git reports a worktree's resolved path; macOS's temporary directory sits
    # under the /var -> /private/var link, so compare against the resolved one.
    z_scratch = Path(z_scratch).resolve()
    z_origin = z_scratch / "origin-repo"
    z_origin.mkdir()
    git(["init", "-q", "-b", "main"], z_origin)
    configure_identity(z_origin)
    commit_file(z_origin, "my notes.md", "first\n", "first commit")
    # A main worktree whose path holds a newline: one porcelain record, not two lines.
    z_reference = z_scratch / "reference\nclone"
    git(["clone", "-q", str(z_origin), str(z_reference)], z_scratch)
    configure_identity(z_reference)
    z_seat = z_scratch / "z-seat"
    git(["worktree", "add", "-q", "-b", "z-seat", str(z_seat), "main"], z_reference)
    check("the reference checkout of a worktree is the main worktree, a newline in its path kept",
          catch_up_module.reference_checkout_of(z_seat) == z_reference,
          repr(catch_up_module.reference_checkout_of(z_seat)))

    commit_file(z_origin, "docs/café.md", "main's\n", "main adds a non-ASCII path")
    commit_file(z_origin, "my notes.md", "main's line\n", "main changes a path with a space")
    git(["fetch", "--quiet", "origin"], z_seat)
    z_listing = catch_up_module.obsolete_files_by_category(z_seat)
    check("files main moved are listed by their real names, not C-quoted",
          z_listing == [("documents you may cite", ["docs/café.md"]),
                        ("other files", ["my notes.md"])], str(z_listing))

    commit_file(z_seat, "my notes.md", "the branch's line\n", "the branch changes it too")
    z_git_dir = Path(git(["rev-parse", "--absolute-git-dir"], z_seat).stdout.strip())
    z_outcome = catch_up_module.rebase_never_pushed_branch(z_seat, z_git_dir)
    check("a rebase conflict on a path with a space names the path whole",
          z_outcome == ("conflict", "my notes.md"), str(z_outcome))

    git(["mv", "my notes.md", "renamed notes.md"], z_seat)
    check("a staged rename is one uncommitted tracked change",
          catch_up_module.uncommitted_tracked_change_count(z_seat) == 1,
          str(catch_up_module.uncommitted_tracked_change_count(z_seat)))
    git(["reset", "-q", "--hard"], z_seat)

# ---------------------------------------------------------------------------
# Notes reach the agent with its next prompt, not at Stop; a checkout with no
# commits of its own hears only of standing instructions main changed
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as notes_scratch:
    tmp = Path(notes_scratch).resolve()
    real_git = shutil.which("git")
    fixture_count = [0]

    def notes_fixture(first_files=None):
        """(origin, seat): a remote holding first_files, and a never-pushed
        seat branch level with it, with no commits of its own."""
        fixture_count[0] += 1
        root = tmp / f"fixture-{fixture_count[0]}"
        origin_repo = root / "origin"
        origin_repo.mkdir(parents=True)
        git(["init", "-q", "-b", "main"], origin_repo)
        configure_identity(origin_repo)
        for name, content in (first_files or {"shared.txt": "first\n"}).items():
            commit_file(origin_repo, name, content, f"add {name}")
        clone = root / "clone"
        git(["clone", "-q", str(origin_repo), str(clone)], root)
        configure_identity(clone)
        seat_path = root / "seat"
        git(["worktree", "add", "-q", "-b", "seat", str(seat_path), "main"], clone)
        configure_identity(seat_path)
        return origin_repo, seat_path

    def stop_only(checkout, path_prefix=None):
        return run_catch_up_once(["--cwd", str(checkout)], path_prefix)

    def deliver(checkout):
        return run_catch_up_once(["--deliver-pending-agent-notes", "--cwd", str(checkout)])

    def delivered_text(result):
        return ((emitted_object(result) or {}).get("hookSpecificOutput", {})
                .get("additionalContext", ""))

    def stamp_path_of(checkout):
        return Path(git(["rev-parse", "--absolute-git-dir"], checkout).stdout.strip()) \
            / "checkout-freshness-stamp.json"

    claude_md_lines = "".join(f"- rule {number}\n" for number in range(1, 6))
    origin_repo, notes_seat = notes_fixture({"CLAUDE.md": claude_md_lines})
    commit_file(origin_repo, "CLAUDE.md", claude_md_lines.replace("- rule 3\n", "- rule three\n"),
                "main changes a rule")
    stop = stop_only(notes_seat)
    check("a Stop run gives the agent no context, so it costs no turn",
          "hookSpecificOutput" not in (emitted_object(stop) or {}), stop.stdout)
    check("and queues the note in the stamp",
          len(stamp_of(notes_seat).get("pending_agent_notes", [])) == 1, str(stamp_of(notes_seat)))
    first = deliver(notes_seat)
    check("the next prompt's delivery is a UserPromptSubmit context",
          (emitted_object(first) or {}).get("hookSpecificOutput", {}).get("hookEventName")
          == "UserPromptSubmit", first.stdout)
    check("a changed CLAUDE.md is told with its changed lines, old and new",
          "checkout-freshness: main changed CLAUDE.md, which this agent-session read at its start."
          in delivered_text(first)
          and "\n-- rule 3\n" in delivered_text(first) and "\n+- rule three" in delivered_text(first)
          and "rule 4" not in delivered_text(first), delivered_text(first))
    check("the CLAUDE.md note ends by saying it is not for the user, byte for byte",
          delivered_text(first).endswith("\n" + NOT_FOR_THE_USER_LINE), delivered_text(first))
    check("a delivery clears the queue, so the next prompt hears nothing",
          deliver(notes_seat).stdout.strip() == "" and "pending_agent_notes" not in stamp_of(notes_seat),
          str(stamp_of(notes_seat)))

    origin_repo, notes_seat = notes_fixture()
    commit_file(origin_repo, ".claude/skills/walk-me-through/SKILL.md", "steps\n", "a skill changes")
    commit_file(origin_repo, "docs/agents/pr-reviewer-instructions.md", "rules\n", "instructions change")
    commit_file(origin_repo, "nc-systems/cold-read/cold-read-fast-clarify-prompt.md", "p\n", "a prompt")
    commit_file(origin_repo, ".claude/skills/walk-me-through/reference.md", "r\n", "not a SKILL.md")
    commit_file(origin_repo, "scripts/tool.py", "t\n", "a script")
    stop_only(notes_seat)
    told = delivered_text(deliver(notes_seat))
    check("a changed SKILL.md tells the agent to invoke the skill again",
          "checkout-freshness: main changed .claude/skills/walk-me-through/SKILL.md. If you are "
          "following the walk-me-through skill, invoke it again before its next step, so that "
          "its new text loads." in told, told)
    check("a changed -instructions.md and -prompt.md are told as standing instructions",
          "main changed docs/agents/pr-reviewer-instructions.md, a file of standing instructions."
          in told and "main changed nc-systems/cold-read/cold-read-fast-clarify-prompt.md, a file"
          in told, told)
    check("a skill's other files and scripts are not told",
          "reference.md" not in told and "scripts/tool.py" not in told, told)

    origin_repo, notes_seat = notes_fixture({"CLAUDE.md": "- one rule\n"})
    commit_file(origin_repo, "CLAUDE.md", "".join(f"- new rule {n:04d} {'x' * 60}\n"
                                                  for n in range(120)), "a long rewrite")
    stop_only(notes_seat)
    told = delivered_text(deliver(notes_seat))
    check("a CLAUDE.md change too long to show is named by its changed lines",
          "checkout-freshness: main changed CLAUDE.md, which this agent-session read at its start, "
          "at lines 1-120. Read CLAUDE.md again before your next action." in told
          and "new rule 0050" not in told, told[:400])

    origin_repo, notes_seat = notes_fixture({"CLAUDE.md": "- a\n"})
    commit_file(origin_repo, "CLAUDE.md", "- b\n", "first change")
    stop_only(notes_seat)
    commit_file(origin_repo, "CLAUDE.md", "- c\n", "second change")
    stop_only(notes_seat)
    told = delivered_text(deliver(notes_seat))
    check("two moves before one prompt are both told",
          "+- b" in told and "+- c" in told and told.count("main changed CLAUDE.md") == 2, told)

    origin_repo, notes_seat = notes_fixture()
    commit_file(origin_repo, "CLAUDE.md", "- rule\n", "main adds CLAUDE.md")
    diff_fails = tmp / "diff-fails-shim"
    diff_fails.mkdir()
    (diff_fails / "git").write_text(
        "#!/bin/sh\n"
        'for argument in "$@"; do\n'
        '  if [ "$argument" = "--name-only" ]; then\n'
        '    echo "fatal: shimmed diff failure" >&2; exit 128\n'
        "  fi\n"
        "done\n"
        f'exec "{real_git}" "$@"\n', encoding="utf-8")
    (diff_fails / "git").chmod(0o755)
    stop_only(notes_seat, path_prefix=str(diff_fails))
    told = delivered_text(deliver(notes_seat))
    check("a diff git cannot make is told as such, never read as nothing changed",
          (notes_seat / "CLAUDE.md").exists()
          and "checkout-freshness: this checkout was moved forward to origin/main, but git could "
          "not list what main changed (fatal: shimmed diff failure)." in told
          and "Read CLAUDE.md again before your next action." in told, told)

    origin_repo, notes_seat = notes_fixture()
    (notes_seat / "shared.txt").write_text("dirty\n", encoding="utf-8")
    commit_file(origin_repo, "a.txt", "a\n", "advance a")
    stop_only(notes_seat)
    commit_file(origin_repo, "b.txt", "b\n", "advance b")
    stop_only(notes_seat)
    told = delivered_text(deliver(notes_seat))
    check("a newer not-updated note replaces the older one",
          told.count("Not updated: 1 uncommitted tracked change(s)") == 1 and "b.txt" in told, told)
    stop_only(notes_seat)
    commit_file(origin_repo, "c.txt", "c\n", "advance c")
    stop_only(notes_seat)
    git(["checkout", "--", "shared.txt"], notes_seat)
    stop_only(notes_seat)
    told = delivered_text(deliver(notes_seat))
    check("a note that a move was blocked is dropped once the move is made",
          "Not updated" not in told and (notes_seat / "c.txt").exists(), told)

    # The write is made to fail by putting a directory where the stamp goes:
    # a read-only git directory would also stop git itself, and the checkout
    # could not move.
    origin_repo, notes_seat = notes_fixture()
    stop_only(notes_seat)
    stamp_file = stamp_path_of(notes_seat)
    commit_file(origin_repo, "CLAUDE.md", "- rule\n", "main adds CLAUDE.md")
    stamp_file.unlink()
    stamp_file.mkdir()
    try:
        stop = stop_only(notes_seat)
    finally:
        stamp_file.rmdir()
    stop_context = ((emitted_object(stop) or {}).get("hookSpecificOutput", {})
                    .get("additionalContext", ""))
    check("notes that cannot be queued go out at Stop instead, saying why",
          "main changed CLAUDE.md" in stop_context
          and "checkout-freshness: these notes come now, not with your next prompt, because they "
          "could not be saved to" in stop_context, stop.stdout)

    origin_repo, notes_seat = notes_fixture()
    commit_file(origin_repo, "CLAUDE.md", "- rule\n", "main adds CLAUDE.md")
    stop_only(notes_seat)
    stamp_file = stamp_path_of(notes_seat)
    stamp_file.chmod(0o444)
    try:
        delivered = delivered_text(deliver(notes_seat))
    finally:
        stamp_file.chmod(0o644)
    check("a delivery that cannot clear the queue says the notes may come again",
          "main changed CLAUDE.md" in delivered
          and "checkout-freshness: these notes could not be cleared from" in delivered, delivered)

    stamp_file.write_text("{not json", encoding="utf-8")
    delivered = delivered_text(deliver(notes_seat))
    check("a queue that cannot be read is told, not taken for an empty one",
          "checkout-freshness: notes queued for you could not be read from" in delivered, delivered)

    long_notes = [{"kind": "moved", "text": "long " + "y" * 4000, "short": "short one"},
                  {"kind": "moved", "text": "long " + "z" * 6000, "short": "short two"}]
    check("a delivery too long for one context is cut to the notes' short forms",
          catch_up_module.delivery_text(long_notes) == "short one\n\nshort two",
          catch_up_module.delivery_text(long_notes)[:200])
    many = [{"kind": "moved", "text": "n" * 3000} for _ in range(5)]
    cut = catch_up_module.delivery_text(many)
    check("and when even those are too long, the newest that fit are kept, the rest counted",
          len(cut) <= catch_up_module.DELIVERY_CHARACTER_LIMIT
          and cut.startswith("checkout-freshness: 3 older note(s) did not fit"), cut[:120])


    def queued_notes(checkout):
        notes = stamp_of(checkout).get("pending_agent_notes", [])
        return notes if isinstance(notes, list) else []

    origin_repo, notes_seat = notes_fixture()
    detached = notes_seat.parent / "detached"
    git(["worktree", "add", "-q", "--detach", str(detached), "main"], notes_seat.parent / "clone")
    configure_identity(detached)
    (detached / "shared.txt").write_text("dirty\n", encoding="utf-8")
    commit_file(origin_repo, "a.txt", "a\n", "advance a")
    stop_only(detached)
    check("a detached HEAD that is not moved queues its note as a blocked note",
          [note.get("kind") for note in queued_notes(detached)] == ["blocked"]
          and "was not moved forward" in queued_notes(detached)[0]["text"],
          str(queued_notes(detached)))
    git(["checkout", "--", "shared.txt"], detached)
    stop_only(detached)
    check("once the detached HEAD is moved, its queued not-moved note is dropped from the queue",
          (detached / "a.txt").exists()
          and not any("was not moved forward" in note["text"] for note in queued_notes(detached)),
          str(queued_notes(detached)))

    origin_repo, notes_seat = notes_fixture()
    (notes_seat / "shared.txt").write_text("dirty\n", encoding="utf-8")
    commit_file(origin_repo, "a.txt", "a\n", "advance a")
    stop_only(notes_seat)
    git(["checkout", "--", "shared.txt"], notes_seat)
    git(["rebase", "-q", "origin/main"], notes_seat)
    stop_only(notes_seat)
    check("a queued blocked note is dropped once the checkout is level with main by other means",
          (notes_seat / "a.txt").exists() and queued_notes(notes_seat) == [],
          str(queued_notes(notes_seat)))

    origin_repo, notes_seat = notes_fixture()
    (notes_seat / "shared.txt").write_text("dirty\n", encoding="utf-8")
    commit_file(origin_repo, "a.txt", "a\n", "advance a")
    stop_only(notes_seat)
    count_fails = tmp / "count-fails-shim"
    count_fails.mkdir()
    (count_fails / "git").write_text(
        "#!/bin/sh\n"
        'for argument in "$@"; do\n'
        '  if [ "$argument" = "--count" ]; then\n'
        '    echo "fatal: shimmed count failure" >&2; exit 128\n'
        "  fi\n"
        "done\n"
        f'exec "{real_git}" "$@"\n', encoding="utf-8")
    (count_fails / "git").chmod(0o755)
    first_count_failure = stop_only(notes_seat, path_prefix=str(count_fails))
    check("a count git cannot make keeps the queued notes, since nothing shows the checkout caught up",
          [note.get("kind") for note in queued_notes(notes_seat)] == ["blocked", "count-failed"],
          str(queued_notes(notes_seat)))
    count_failed_text = next((note["text"] for note in queued_notes(notes_seat)
                              if note.get("kind") == "count-failed"), "")
    check("a count git cannot make is told to the agent, with git's message, byte for byte",
          count_failed_text.startswith(
              "checkout-freshness: git could not count how far seat is behind origin/main "
              "(git rev-list exited 128: fatal: shimmed count failure), so this checkout was not "
              "compared with main and may be older than main.\n"
              "Run `git fetch origin` and then `git rev-list --count HEAD..origin/main` to see "
              "the count, or git's message.\n"
              "If git cannot make the count either, tell the user what git said: a checkout that "
              "cannot be compared with main changes the work you are doing with him.")
          and count_failed_text.endswith("changes the work you are doing with him."),
          count_failed_text)
    check("the count-failed note, which tells the agent to tell the user, does not end with "
          "the line saying it is not for the user",
          NOT_FOR_THE_USER_LINE not in count_failed_text, count_failed_text)
    deliver(notes_seat)
    again = stop_only(notes_seat, path_prefix=str(count_fails))
    check("the same count failure is told once, not at every turn's end",
          queued_notes(notes_seat) == [], str(queued_notes(notes_seat)))
    reference_count_line = ("was not compared with origin/main, because git could not count how "
                            "far behind it is: git rev-list exited 128: fatal: shimmed count failure")
    check("a reference checkout git cannot count is told to the user, with git's message",
          f"catch-up: reference checkout {(notes_seat.parent / 'clone').resolve()} "
          f"{reference_count_line}" in display_text(first_count_failure),
          display_text(first_count_failure))
    check("and only once", reference_count_line not in display_text(again), display_text(again))
    report_result = run_catch_up_once(["--report", "--repo", str(notes_seat)],
                                      path_prefix=str(count_fails))
    check("--report says the comparison could not be made, and git's message",
          report_result.stdout.strip() == f"freshness: {notes_seat.resolve()} could not be "
          f"compared with origin/main: git rev-list exited 128: fatal: shimmed count failure",
          report_result.stdout)
    stop_only(notes_seat, path_prefix=str(count_fails))
    check("(fixture) the queue is empty before the count-failed note is queued again",
          queued_notes(notes_seat) == [], str(queued_notes(notes_seat)))
    stamp_file = stamp_path_of(notes_seat)
    stamp_now = json.loads(stamp_file.read_text(encoding="utf-8"))
    stamp_now.pop("last_count_error", None)
    stamp_file.write_text(json.dumps(stamp_now) + "\n", encoding="utf-8")
    stop_only(notes_seat, path_prefix=str(count_fails))
    check("(fixture) a count-failed note is queued",
          "count-failed" in [note.get("kind") for note in queued_notes(notes_seat)],
          str(queued_notes(notes_seat)))
    stop_only(notes_seat)
    check("a queued count-failed note is dropped once a count succeeds",
          "count-failed" not in [note.get("kind") for note in queued_notes(notes_seat)]
          and "last_count_error" not in stamp_of(notes_seat), str(queued_notes(notes_seat)))

    def git_shim(name, cases):
        """A git that answers the given argument shapes itself and passes
        every other call to the real git. cases: (shell test, shell action)."""
        directory = tmp / name
        directory.mkdir()
        lines = ["#!/bin/sh", 'all=" $* "']
        for test, action in cases:
            lines.append(f"if {test}; then {action}; fi")
        lines.append(f'exec "{real_git}" "$@"')
        (directory / "git").write_text("\n".join(lines) + "\n", encoding="utf-8")
        (directory / "git").chmod(0o755)
        return str(directory)

    def count_failed_texts(checkout):
        return [note["text"] for note in queued_notes(checkout)
                if note.get("kind") == "count-failed"]

    origin_repo, notes_seat = notes_fixture()
    commit_file(origin_repo, "a.txt", "a\n", "advance a")
    main_ref_fails = git_shim("main-ref-fails-shim", [(
        'case "$all" in *" --verify "*" origin/main "*) true;; *) false;; esac',
        'echo "fatal: shimmed ref failure" >&2; exit 128')])
    stop_only(notes_seat, path_prefix=main_ref_fails)
    told = count_failed_texts(notes_seat)
    check("a failure to look up origin/main is told with git's own reason, not as a missing origin/main",
          len(told) == 1 and "(git rev-parse exited 128: fatal: shimmed ref failure)" in told[0]
          and "there is no origin/main" not in told[0], str(told))
    deliver(notes_seat)
    other_ref_failure = git_shim("other-ref-failure-shim", [(
        'case "$all" in *" --verify "*" origin/main "*) true;; *) false;; esac',
        'echo "fatal: a different ref failure" >&2; exit 128')])
    stop_only(notes_seat, path_prefix=other_ref_failure)
    told = count_failed_texts(notes_seat)
    check("a later failure at the same step with a different reason is told again",
          len(told) == 1 and "fatal: a different ref failure" in told[0], str(told))
    deliver(notes_seat)
    count_not_a_number = git_shim("count-not-a-number-shim", [(
        'case "$all" in *" --count "*) true;; *) false;; esac', 'echo "many"; exit 0')])
    stop_only(notes_seat, path_prefix=count_not_a_number)
    told = count_failed_texts(notes_seat)
    check("a count git prints that is not a number is told as a failed count, not as level with main",
          len(told) == 1 and "(git rev-list printed 'many' and 'many', not counts)" in told[0]
          and stamp_of(notes_seat).get("behind") is None, str(told))

    origin_repo, notes_seat = notes_fixture()
    git(["push", "-q", "-u", "origin", "seat"], notes_seat)
    commit_file(origin_repo, "a.txt", "a\n", "advance a")
    stop_only(notes_seat)
    commit_file(origin_repo, "b.txt", "b\n", "advance b")
    stop_only(notes_seat)
    check("a newer note on a pushed branch replaces the older one in the queue",
          [note.get("kind") for note in queued_notes(notes_seat)] == ["pushed"]
          and "2 behind" in queued_notes(notes_seat)[0]["text"],
          str(queued_notes(notes_seat)))

    six_thousand_to_nine = "".join(f"- line {n:03d} {'w' * 55}\n" for n in range(100))
    origin_repo, notes_seat = notes_fixture({"CLAUDE.md": "- one rule\n"})
    commit_file(origin_repo, "CLAUDE.md", six_thousand_to_nine, "a rewrite of about 7,000 characters")
    stop_only(notes_seat)
    told = delivered_text(deliver(notes_seat))
    check("a CLAUDE.md diff over 6,000 characters is named by its lines even when the "
          "delivery would fit it",
          len(six_thousand_to_nine) < catch_up_module.DELIVERY_CHARACTER_LIMIT - 1000
          and "Read CLAUDE.md again before your next action." in told
          and "line 050" not in told, told[:400])

    origin_repo, notes_seat = notes_fixture({".claude/skills/gone/SKILL.md": "steps\n",
                                             "shared.txt": "first\n"})
    git(["rm", "-q", ".claude/skills/gone/SKILL.md"], origin_repo)
    git(["commit", "-q", "-m", "main deletes a skill"], origin_repo)
    stop_only(notes_seat)
    told = delivered_text(deliver(notes_seat))
    check("a skill main deleted is told as deleted, not as one to invoke again",
          "checkout-freshness: main deleted .claude/skills/gone/SKILL.md." in told
          and "invoke it again" not in told, told)

    skill_reload_lines = (
        "If you are following a skill, invoke it again before its next step.\n"
        "If that skill's .claude/skills/<name>/SKILL.md is no longer in this checkout, main "
        "deleted the skill: stop following it.")
    for note_name, rendered in (
            ("the did-not-fit line", catch_up_module.delivery_text(many)),
            ("the could-not-be-read line", catch_up_module.NOTES_UNREADABLE_LINE.format(
                path="stamp.json", error="unreadable")),
            ("the moved-without-a-list note", catch_up_module.MOVED_WITHOUT_LIST_NOTE.format(
                error="no list"))):
        check(f"{note_name} says to invoke the skill again, and to stop following a skill "
              f"main deleted, byte for byte", skill_reload_lines in rendered, rendered[:600])

    origin_repo, notes_seat = notes_fixture()
    commit_file(notes_seat, "own.txt", "mine\n", "the seat's own work")
    commit_file(origin_repo, "a.txt", "a\n", "advance a")
    stop_only(notes_seat)
    told = delivered_text(deliver(notes_seat))
    check("a rebase under the branch's own commits ends with the test-run instruction, byte for byte",
          "was rebased onto origin/main" in told
          and told.endswith("\nRun `python3 scripts/run-all-test-suites.py "
                            "--only-suites-whose-recorded-inputs-changed-since origin/main`: "
                            "your work now sits on newer code.\n" + NOT_FOR_THE_USER_LINE), told)

    git(["push", "-q", "-u", "origin", "seat"], notes_seat)
    git(["commit", "-q", "--amend", "-m", "amended once"], notes_seat)
    stop_only(notes_seat)
    git(["commit", "-q", "--amend", "-m", "amended twice"], notes_seat)
    second_amend = git(["rev-parse", "--short=12", "HEAD"], notes_seat).stdout.strip()
    stop_only(notes_seat)
    told = delivered_text(deliver(notes_seat))
    check("a newer rewritten-head note replaces an older one not yet delivered",
          told.count("no longer contains its pushed head") == 1
          and f"seat's HEAD ({second_amend})" in told, told)
    git(["commit", "-q", "--amend", "-m", "amended a third time"], notes_seat)
    third_amend = git(["rev-parse", "--short=12", "HEAD"], notes_seat).stdout.strip()
    stop_only(notes_seat)
    head_state_unknown = git_shim("head-state-unknown-shim", [
        ('case "$all" in *" --verify "*" origin/seat "*) true;; *) false;; esac', "exit 1"),
        ('case "$all" in *" --remotes "*) true;; *) false;; esac',
         'echo "fatal: shimmed remotes failure" >&2; exit 128')])
    stop_only(notes_seat, path_prefix=head_state_unknown)
    rewritten = [note["text"] for note in queued_notes(notes_seat)
                 if note.get("kind") == "rewritten-head"]
    check("a queued rewritten-head note stays, unchanged, when git cannot tell where the head stands",
          len(rewritten) == 1 and f"seat's HEAD ({third_amend})" in rewritten[0], str(rewritten))
    deliver(notes_seat)
    stop_only(notes_seat, path_prefix=head_state_unknown)
    stop_only(notes_seat)
    check("and once delivered, the same rewritten head is not told again after a check git could not make",
          "rewritten-head" not in [note.get("kind") for note in queued_notes(notes_seat)],
          str(queued_notes(notes_seat)))
    git(["reset", "-q", "--hard", "origin/seat"], notes_seat)
    stop_only(notes_seat)
    check("a queued rewritten-head note is dropped once the head contains its pushed head again",
          "rewritten-head" not in [note.get("kind") for note in queued_notes(notes_seat)],
          str(queued_notes(notes_seat)))

    origin_repo, notes_seat = notes_fixture()
    commit_file(notes_seat, "own.txt", "mine\n", "the seat's own work")
    before_merge = git(["rev-parse", "HEAD"], notes_seat).stdout.strip()
    commit_file(origin_repo, "a.txt", "a\n", "advance a")
    git(["fetch", "-q", "origin"], notes_seat)
    git(["merge", "-q", "--no-edit", "origin/main"], notes_seat)
    stop_only(notes_seat)
    stop_only(notes_seat)
    check("a merge from main is queued as a merges-from-main note, kept at later turn ends "
          "while the branch is level with main",
          [note.get("kind") for note in queued_notes(notes_seat)] == ["merges-from-main"],
          str(queued_notes(notes_seat)))
    commit_file(origin_repo, "b.txt", "b\n", "advance b")
    git(["fetch", "-q", "origin"], notes_seat)
    git(["merge", "-q", "--no-edit", "origin/main"], notes_seat)
    stop_only(notes_seat)
    told = delivered_text(deliver(notes_seat))
    check("a newer merges-from-main note replaces an older one not yet delivered",
          told.count("merge commit(s) from main") == 1
          and "seat carries 2 merge commit(s) from main" in told, told)
    commit_file(origin_repo, "c.txt", "c\n", "advance c")
    git(["fetch", "-q", "origin"], notes_seat)
    git(["merge", "-q", "--no-edit", "origin/main"], notes_seat)
    stop_only(notes_seat)
    queued_before = queued_notes(notes_seat)
    merges_unlisted = git_shim("merges-unlisted-shim", [(
        'case "$all" in *" --merges "*) true;; *) false;; esac',
        'echo "fatal: shimmed merges failure" >&2; exit 128')])
    stop_only(notes_seat, path_prefix=merges_unlisted)
    check("a queued merges-from-main note stays, unchanged, when git cannot list the branch's merges",
          [note for note in queued_notes(notes_seat) if note.get("kind") == "merges-from-main"]
          == [note for note in queued_before if note.get("kind") == "merges-from-main"]
          and len(queued_before) >= 1, str(queued_notes(notes_seat)))
    deliver(notes_seat)
    stop_only(notes_seat, path_prefix=merges_unlisted)
    stop_only(notes_seat)
    check("and once delivered, the same merges are not told again after a check git could not make",
          "merges-from-main" not in [note.get("kind") for note in queued_notes(notes_seat)],
          str(queued_notes(notes_seat)))
    git(["reset", "-q", "--hard", before_merge], notes_seat)
    stop_only(notes_seat)
    check("a queued merges-from-main note is dropped once the branch no longer carries the merges",
          "merges-from-main" not in [note.get("kind") for note in queued_notes(notes_seat)]
          and (notes_seat / "c.txt").exists(), str(queued_notes(notes_seat)))

    no_main_repo = tmp / "no-origin-main"
    no_main_repo.mkdir()
    git(["init", "-q", "-b", "seat"], no_main_repo)
    configure_identity(no_main_repo)
    commit_file(no_main_repo, "own.txt", "mine\n", "the seat's own work")
    no_main_run = stop_only(no_main_repo)
    check("a checkout with no origin/main and no stamp yet runs to the end without a crash, "
          "and queues the could-not-count note",
          no_main_run.returncode == 0 and "Traceback" not in no_main_run.stderr
          and "git could not count how far seat is behind origin/main"
          in " ".join(note["text"] for note in queued_notes(no_main_repo)),
          no_main_run.stderr + str(queued_notes(no_main_repo)))

    origin_repo, notes_seat = notes_fixture()
    commit_file(notes_seat, "own.txt", "mine\n", "the seat's own work")
    commit_file(origin_repo, "a.txt", "a\n", "advance a")
    git(["fetch", "-q", "origin"], notes_seat)
    git(["merge", "-q", "--no-edit", "origin/main"], notes_seat)
    git(["push", "-q", "-u", "origin", "seat"], notes_seat)
    stop_only(notes_seat)
    deliver(notes_seat)
    git(["commit", "-q", "--amend", "-m", "the merge, amended"], notes_seat)
    carried_run = stop_only(notes_seat, path_prefix=merges_unlisted)
    carried_kinds = sorted(note.get("kind") for note in queued_notes(notes_seat))
    check("when git cannot list the merges and the head is rewritten, only the rewritten "
          "head is told: the merges note already delivered is not queued again, and nothing crashes",
          carried_run.returncode == 0 and "Traceback" not in carried_run.stderr
          and carried_kinds == ["rewritten-head"],
          carried_run.stderr + str(queued_notes(notes_seat)))

    origin_repo, notes_seat = notes_fixture()
    commit_file(notes_seat, "own.txt", "mine\n", "the seat's own work")
    commit_file(origin_repo, "a.txt", "a\n", "advance a")
    git(["fetch", "-q", "origin"], notes_seat)
    git(["merge", "-q", "--no-edit", "origin/main"], notes_seat)
    git(["push", "-q", "-u", "origin", "seat"], notes_seat)
    git(["commit", "-q", "--amend", "-m", "the merge, amended"], notes_seat)
    stop_only(notes_seat)
    both_told = delivered_text(deliver(notes_seat))
    git(["reset", "-q", "--hard", "HEAD~1"], origin_repo)
    git(["fetch", "-q", "origin"], notes_seat)
    unmerged_run = stop_only(notes_seat)
    unmerged_kinds = [note.get("kind") for note in queued_notes(notes_seat)]
    check("when the merges finding changes while the head stays rewritten, the rewritten-head "
          "note already delivered is not queued again",
          "merge commit(s) from main" in both_told and "no longer contains its pushed head" in both_told
          and unmerged_run.returncode == 0 and "rewritten-head" not in unmerged_kinds,
          both_told + unmerged_run.stderr + str(queued_notes(notes_seat)))

    def write_stamp_notes(path, notes):
        path.write_text(json.dumps({"pending_agent_notes": notes}) + "\n", encoding="utf-8")

    reread_dir = tmp / "reread-stamp"
    reread_dir.mkdir()
    reread_stamp = reread_dir / "stamp.json"
    stale_note = {"kind": "moved", "text": "already delivered"}
    write_stamp_notes(reread_stamp, [])
    catch_up_module.AGENT_NOTES.append({"kind": "moved", "text": "new"})
    catch_up_module.save_stamp_with_queued_notes(reread_stamp,
                                                 {"pending_agent_notes": [stale_note]})
    check("the queue is re-read just before the write, so a delivery made meanwhile is not undone",
          [note["text"] for note in json.loads(reread_stamp.read_text())["pending_agent_notes"]]
          == ["new"], reread_stamp.read_text())


print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
