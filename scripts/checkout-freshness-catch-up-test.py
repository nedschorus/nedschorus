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
    """The decision object a run emitted, or None when it spoke plain text."""
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def configure_identity(repository: Path):
    git(["config", "user.email", "test@example.invalid"], repository)
    git(["config", "user.name", "freshness test"], repository)


def commit_file(repository: Path, name: str, content: str, message: str):
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

    # Advance the remote past both checkouts.
    commit_file(origin, "advance-one.txt", "one\n", "advance one")

    result = run_catch_up(["--cwd", str(seat)])
    # A LANDED merge is an attention state (user-ruled 2026-08-31), so this run
    # speaks one channel: a single decision:block object carrying every line the
    # run produced, the reference checkout's included.
    #
    # Parsing the WHOLE of stdout is the assertion that matters, and it is the
    # regression test for the mixing this design exists to prevent: a merge lands
    # only when origin/main advanced, which is exactly when the reference
    # checkout also has something to say. A JSON object with a plain line
    # appended is neither valid JSON nor plain text — Claude Code reports it as a
    # hook error and the block is lost. Substring checks against raw stdout would
    # pass either way, since the same text sits inside the JSON.
    try:
        emitted_merge = json.loads(result.stdout)
    except json.JSONDecodeError:
        emitted_merge = None
    check("a landed merge emits exactly one JSON object on stdout",
          isinstance(emitted_merge, dict), result.stdout + result.stderr)
    merge_reason = (emitted_merge or {}).get("reason", "")
    check("a landed merge blocks, so the agent hears it rather than the display",
          (emitted_merge or {}).get("decision") == "block", result.stdout)
    check("a clean behind seat is merged",
          "merged origin/main into seat" in merge_reason, merge_reason)
    check("the merge names the files it changed",
          "advance-one.txt" in merge_reason, merge_reason)
    check("the merge warns against amending onto it",
          "--amend" in merge_reason and "git show --stat" in merge_reason,
          merge_reason)
    check("the seat now has the remote commit", (seat / "advance-one.txt").exists())
    check("the reference clone fast-forwarded on the same pass, reported inside "
          "the same object",
          "reference checkout" in merge_reason and (reference / "advance-one.txt").exists(),
          merge_reason)
    check("the stamp records zero behind after the merge", stamp_of(seat).get("behind") == 0,
          str(stamp_of(seat)))

    # Throttle: with a fresh stamp and a long interval, no fetch happens, so a
    # new remote commit stays unseen and the run is silent.
    commit_file(origin, "advance-two.txt", "two\n", "advance two")
    quiet = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--interval-seconds", "3600", "--cwd", str(seat)],
        capture_output=True, text=True, check=False,
    )
    check("a fresh stamp suppresses the fetch (throttle)", quiet.stdout.strip() == "",
          quiet.stdout)
    check("the throttled run merged nothing", not (seat / "advance-two.txt").exists())

    result = run_catch_up(["--cwd", str(seat)])
    check("interval zero fetches and merges the new commit",
          (seat / "advance-two.txt").exists(), result.stdout + result.stderr)

    # A dirty tracked file blocks the merge with its reason.
    commit_file(origin, "advance-three.txt", "three\n", "advance three")
    (seat / "shared.txt").write_text("local edit in progress\n", encoding="utf-8")
    result = run_catch_up(["--cwd", str(seat)])
    check("uncommitted tracked changes block the merge",
          "not merged" in result.stdout and "uncommitted tracked change" in result.stdout,
          result.stdout)
    check("the blocked merge changed nothing", not (seat / "advance-three.txt").exists())
    git(["checkout", "--", "shared.txt"], seat)

    # Untracked-only dirt does not block.
    (seat / "scratch-note.txt").write_text("scratch\n", encoding="utf-8")
    result = run_catch_up(["--cwd", str(seat)])
    check("untracked-only dirt does not block the merge",
          (seat / "advance-three.txt").exists(), result.stdout + result.stderr)
    (seat / "scratch-note.txt").unlink()

    # A conflicting advance: attempted, aborted, tree left exactly as it was.
    commit_file(seat, "shared.txt", "seat version\n", "seat edits shared")
    commit_file(origin, "shared.txt", "origin version\n", "origin edits shared")
    before = git(["rev-parse", "HEAD"], seat).stdout.strip()
    result = run_catch_up(["--cwd", str(seat)])
    check("a conflicting merge reports instead of landing",
          "would conflict" in result.stdout, result.stdout + result.stderr)
    check("the conflict abort restored HEAD", git(["rev-parse", "HEAD"], seat).stdout.strip() == before)
    check("no merge state is left behind", not (Path(git(["rev-parse", "--absolute-git-dir"], seat).stdout.strip()) / "MERGE_HEAD").exists())
    check("the tree is clean after the abort", git(["status", "--porcelain"], seat).stdout.strip() == "",
          git(["status", "--porcelain"], seat).stdout)

    # Resolve the conflict so later cases start clean: take origin's version.
    git(["merge", "--no-edit", "-X", "theirs", "origin/main"], seat)
    git(["checkout", "--theirs", "shared.txt"], seat)
    git(["add", "shared.txt"], seat)
    git(["commit", "-q", "--no-edit", "--allow-empty", "-m", "resolve for tests"], seat)

    # An in-progress git operation blocks the merge.
    commit_file(origin, "advance-four.txt", "four\n", "advance four")
    seat_git_dir = Path(git(["rev-parse", "--absolute-git-dir"], seat).stdout.strip())
    (seat_git_dir / "BISECT_LOG").write_text("simulated\n", encoding="utf-8")
    result = run_catch_up(["--cwd", str(seat)])
    check("an in-progress operation blocks the merge",
          "in progress" in result.stdout, result.stdout)
    (seat_git_dir / "BISECT_LOG").unlink()

    # Detached HEAD blocks with its reason. Advance the remote first so the
    # detached checkout is genuinely behind — a current one exercises nothing.
    commit_file(origin, "advance-detached.txt", "detached\n", "advance for detached case")
    detached = tmp / "detached-worktree"
    git(["worktree", "add", "-q", "--detach", str(detached), "main"], reference)
    result = run_catch_up(["--cwd", str(detached)])
    check("detached HEAD is named as the blocker", "detached HEAD" in result.stdout,
          result.stdout)

    # Foreign merge state is never aborted: with MERGE_HEAD present the hook
    # must leave the repository exactly as found (blocking review finding).
    commit_file(origin, "advance-foreign.txt", "foreign\n", "advance foreign")
    (seat_git_dir / "MERGE_HEAD").write_text("simulated foreign merge\n", encoding="utf-8")
    result = run_catch_up(["--cwd", str(seat)])
    check("a foreign merge in progress blocks the catch-up",
          "in progress" in result.stdout, result.stdout)
    check("the foreign merge state survives untouched",
          (seat_git_dir / "MERGE_HEAD").exists())
    (seat_git_dir / "MERGE_HEAD").unlink()
    result = run_catch_up(["--cwd", str(seat)])
    check("the catch-up resumes once the foreign merge is gone",
          (seat / "advance-foreign.txt").exists(), result.stdout)

    # A standing conflict is reported, not retried: ORIG_HEAD must not be
    # clobbered turn after turn for a known answer.
    commit_file(seat, "shared.txt", "seat again\n", "seat edits shared again")
    commit_file(origin, "shared.txt", "origin again\n", "origin edits shared again")
    result = run_catch_up(["--cwd", str(seat)])
    check("the fresh conflict is attempted and aborted", "would conflict" in result.stdout,
          result.stdout)
    orig_head_after_abort = (seat_git_dir / "ORIG_HEAD").read_text(encoding="utf-8") \
        if (seat_git_dir / "ORIG_HEAD").exists() else "absent"
    result = run_catch_up(["--cwd", str(seat)])
    check("the standing conflict is not retried", "not retried" in result.stdout,
          result.stdout)
    orig_head_after_repeat = (seat_git_dir / "ORIG_HEAD").read_text(encoding="utf-8") \
        if (seat_git_dir / "ORIG_HEAD").exists() else "absent"
    check("ORIG_HEAD survives the repeat unclobbered",
          orig_head_after_abort == orig_head_after_repeat)
    git(["merge", "--no-edit", "-X", "theirs", "origin/main"], seat)
    git(["checkout", "--theirs", "shared.txt"], seat)
    git(["add", "shared.txt"], seat)
    git(["commit", "-q", "--no-edit", "--allow-empty", "-m", "resolve second conflict"], seat)

    # The reference copy with a local commit is left alone, loudly.
    commit_file(reference, "local-on-main.txt", "local\n", "a commit main does not have")
    commit_file(origin, "advance-five.txt", "five\n", "advance five")
    result = run_catch_up(["--cwd", str(reference)])
    check("a reference with local commits is left alone",
          "left alone" in result.stdout and "local commit" in result.stdout,
          result.stdout)
    check("the diverged reference was not moved", not (reference / "advance-five.txt").exists())

    # A session seated outside any repository does nothing, silently.
    nowhere = tmp / "not-a-repo"
    nowhere.mkdir()
    result = run_catch_up(["--cwd", str(nowhere)])
    check("a non-repository cwd exits silently", result.returncode == 0 and result.stdout.strip() == "",
          f"rc={result.returncode} {result.stdout}")

    # The report mode states behind/ahead and the fetch age.
    result = run_catch_up(["--report", "--repo", str(seat)])
    check("the report names behind, ahead, and fetch age",
          "behind" in result.stdout and "ahead" in result.stdout and "fetched" in result.stdout,
          result.stdout)

# The attention emitter must produce Stop-hook JSON that forces a turn —
# plain text there would reach nobody (the routine lines are plain on
# purpose; only the attention state pays for delivery).
import importlib.util
specification = importlib.util.spec_from_file_location("catch_up_module", SCRIPT_PATH)
catch_up_module = importlib.util.module_from_spec(specification)
specification.loader.exec_module(catch_up_module)
import contextlib, io
captured = io.StringIO()
with contextlib.redirect_stdout(captured):
    catch_up_module.emit_attention("tree needs attention")
emitted = json.loads(captured.getvalue())
check("the attention emitter speaks Stop-hook JSON",
      emitted.get("decision") == "block" and "attention" in emitted.get("reason", ""),
      captured.getvalue())

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
# Channel classification. The landed-merge case pins its own channel; without
# these, no other path is pinned to one. A substring assertion against raw
# stdout matches identically whether the text is plain or wrapped in a
# decision:block object, so a path reclassified in either direction passes
# unnoticed — verified by sabotage, review finding 2026-08-31.
# ---------------------------------------------------------------------------

with tempfile.TemporaryDirectory() as channel_scratch:
    tmp = Path(channel_scratch)
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
    configure_identity(seat)

    # ROUTINE stays on the display: a dirty tree blocks the merge, and that is
    # the agent's own doing — it does not need a forced turn to learn it.
    commit_file(origin, "advance.txt", "one\n", "advance")
    (seat / "shared.txt").write_text("local edit in progress\n", encoding="utf-8")
    blocked = run_catch_up(["--cwd", str(seat)])
    check("a blocked merge reports on the display, not to the agent",
          emitted_object(blocked) is None and "not merged" in blocked.stdout,
          blocked.stdout)
    git(["checkout", "--", "shared.txt"], seat)

    # ATTENTION reaches the agent: a conflicted merge whose abort FAILED leaves
    # the tree mid-merge. This is the state emit_attention was built for, and
    # nothing exercised the PATH to it — only the emitter in isolation. The
    # abort is made to fail by a git shim that forwards everything else.
    real_git = shutil.which("git")
    shim_directory = tmp / "git-shim"
    shim_directory.mkdir()
    shim = shim_directory / "git"
    shim.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = merge ]; then\n'
        '  for argument in "$@"; do\n'
        '    case "$argument" in (--abort) echo "shim: abort refused" >&2; exit 1;; esac\n'
        "  done\n"
        "fi\n"
        f'exec {real_git} "$@"\n', encoding="utf-8")
    shim.chmod(0o755)
    commit_file(seat, "shared.txt", "seat version\n", "seat edits the shared file")
    commit_file(origin, "shared.txt", "origin version\n", "origin edits the same file")

    # ROUTINE again, and a DIFFERENT routine path from the dirty tree above: a
    # merge that would conflict is attempted, aborted cleanly, and reported to
    # the display. The tree is exactly as the agent left it, so there is nothing
    # it must act on before its next turn.
    conflicted = run_catch_up(["--cwd", str(seat)])
    check("a would-conflict merge reports on the display, not to the agent",
          emitted_object(conflicted) is None and "would conflict" in conflicted.stdout,
          conflicted.stdout)

    # A fresh conflict pair, so the standing-conflict throttle does not skip the
    # retry the failed-abort case needs.
    commit_file(origin, "shared.txt", "origin version two\n", "origin edits it again")
    stuck = run_catch_up(["--cwd", str(seat)], path_prefix=str(shim_directory))
    stuck_object = emitted_object(stuck)
    check("a failed abort reaches the agent as one JSON object",
          isinstance(stuck_object, dict) and stuck_object.get("decision") == "block",
          stuck.stdout + stuck.stderr)
    check("the failed abort says the tree needs attention",
          "needs attention" in (stuck_object or {}).get("reason", ""),
          (stuck_object or {}).get("reason", ""))
    git(["merge", "--abort"], seat)

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
    check("--reference-pull speaks plain text, never a block",
          emitted_object(pulled) is None, pulled.stdout)


print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
