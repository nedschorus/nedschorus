#!/usr/bin/env python3
"""Tests for checkout-freshness-catch-up.py.

Run: python3 scripts/checkout-freshness-catch-up-test.py
Prints one line per case and exits non-zero if any case fails. Every case
runs against throwaway repositories under a temporary directory; the layout
mirrors the fleet's: one clone parked on main (the reference copy) carrying
a linked worktree on its own branch (the seat).
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_PATH = Path(__file__).with_name("checkout-freshness-catch-up.py")

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


def run_catch_up(extra_arguments, path_prefix=None):
    environment = dict(os.environ)
    if path_prefix is not None:
        environment["PATH"] = f"{path_prefix}{os.pathsep}{environment['PATH']}"
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--interval-seconds", "0", *extra_arguments],
        capture_output=True, text=True, check=False, env=environment,
    )


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
    check("the agent is told it was rebased, and which files moved under it",
          "was rebased onto origin/main" in agent_text(result)
          and "scripts your tests run against (1): scripts/advance-one.py" in agent_text(result),
          agent_text(result))
    check("and told to rerun the suites for what it touched",
          "Rerun the test suites" in agent_text(result), agent_text(result))
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
          (seat / "advance-two.txt").exists() and "was rebased" in agent_text(cleaned),
          agent_text(cleaned))

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
          and "`git rebase --abort` puts everything back" in agent_text(result),
          agent_text(result))
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

    # -----------------------------------------------------------------------
    # MISBEHAVIOUR is the only thing the user hears. Ruled 2026-09-15: "If the
    # agents are doing the wrong thing, or not doing the right thing, that's
    # when I probably need to be told."
    # -----------------------------------------------------------------------
    # A merge from main on a working branch: the thing #324 removed. Note the
    # branch is 0 behind after it — a drift-first design would never look.
    merge_seat = tmp / "merge-only-worktree"
    git(["worktree", "add", "-q", "-b", "merge-only", str(merge_seat), "main~1"], reference)
    configure_identity(merge_seat)
    git(["fetch", "-q", "origin"], merge_seat)
    git(["-c", "core.editor=true", "merge", "--no-ff", "--no-edit", "origin/main"], merge_seat)
    result = run_catch_up(["--cwd", str(merge_seat)])
    check("a merge from main on a working branch is reported to the USER",
          "carries 1 merge commit(s) from main" in display_text(result)
          and "nedschorus#324" in display_text(result), result.stdout)
    check("and only once", display_text(run_catch_up(["--cwd", str(merge_seat)])) == "")
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
          "merge commit(s) from main" not in display_text(result), display_text(result))

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
    check("and told to leave it and start the next topic from main",
          "Do not rebase, merge or amend it" in agent_text(result)
          and "git checkout -b <name> origin/main" in agent_text(result), agent_text(result))
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
    result = run_catch_up(["--cwd", str(seat)])
    check("an amend after a push is reported to the USER as a rewritten head",
          "rewrote its pushed head" in display_text(result)
          and "no longer an ancestor" in display_text(result), result.stdout)
    check("and the state is recorded as diverged",
          stamp_of(seat).get("head_state") == "diverged-from-remote", str(stamp_of(seat)))
    check("reported once", display_text(run_catch_up(["--cwd", str(seat)])) == "")
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
          "Do not rebase, merge or amend it" in agent_text(pushed_now), agent_text(pushed_now))

    # Detached HEAD: its own advice, never moved.
    detached = tmp / "detached-worktree"
    git(["worktree", "add", "-q", "--detach", str(detached), "main~1"], reference)
    detached_head = git(["rev-parse", "HEAD"], detached).stdout.strip()
    result = run_catch_up(["--cwd", str(detached)])
    check("a detached HEAD is told to check out its branch, and not moved",
          "detached HEAD" in agent_text(result) and "check out your branch" in agent_text(result)
          and git(["rev-parse", "HEAD"], detached).stdout.strip() == detached_head,
          agent_text(result))

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
          and "was rebased" in agent_text(result), result.stdout)

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
    check("a successful pull clears the reference's reason key",
          "last_reference_blockers" not in stamp_of(reference), str(stamp_of(reference)))


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

    # Uncomputable is silent, never invented: the clause is dropped whole.
    not_a_repository = tmp / "not-a-repository"
    not_a_repository.mkdir()
    check("a directory that is not a checkout yields no listing at all",
          catch_up_module.obsolete_files_by_category(not_a_repository) == [],
          str(catch_up_module.obsolete_files_by_category(not_a_repository)))


print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
