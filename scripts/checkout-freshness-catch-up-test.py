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
    # Ruled 2026-09-14 (nedschorus#324): the hook never merges into the
    # working branch. A behind seat is REPORTED — plain text on the display,
    # never a decision:block — and its tree and HEAD are left exactly as
    # they were. Parsing the whole of stdout as JSON is the channel
    # assertion: a block object would parse, plain text does not.
    head_before = git(["rev-parse", "HEAD"], seat).stdout.strip()
    check("a behind seat is reported on the display, never as a block",
          emitted_object(result) is None and "catch-up: seat is 1 behind origin/main" in result.stdout,
          result.stdout + result.stderr)
    check("the report says it did not merge, and why new work starts from origin/main",
          "Not merged (ruled 2026-09-14)" in result.stdout
          and "new work starts from origin/main" in result.stdout, result.stdout)
    check("the seat's tree did not gain the remote commit", not (seat / "advance-one.txt").exists())
    check("the seat's HEAD did not move",
          git(["rev-parse", "HEAD"], seat).stdout.strip() == head_before)
    check("a fresh branch reports zero own commits and an unpushed head",
          "0 own commit(s), 0 ahead counting merges; head unpushed" in result.stdout,
          result.stdout)
    check("the reference clone fast-forwarded on the same pass, reported in the same output",
          (reference / "advance-one.txt").exists() and "reference checkout" in result.stdout
          and "fast-forwarded" in result.stdout, result.stdout)
    check("the stamp records the behind count, the own count, and the head state",
          stamp_of(seat).get("behind") == 1 and stamp_of(seat).get("own") == 0
          and stamp_of(seat).get("head_state") == "unpushed"
          and "not merged" in stamp_of(seat).get("last_action", ""),
          str(stamp_of(seat)))

    # Reported on change only: the same facts at the next turn end are
    # silent, so a seat behind for the life of a review is not nagged; the
    # stamp still carries the numbers for the status line.
    again = run_catch_up(["--cwd", str(seat)])
    check("the same facts at the next run are not reported again",
          again.stdout.strip() == "", again.stdout)
    check("and the stamp still carries the count", stamp_of(seat).get("behind") == 1,
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
    check("the throttled run still recorded 1 behind", stamp_of(seat).get("behind") == 1)

    result = run_catch_up(["--cwd", str(seat)])
    check("interval zero fetches, and the changed count is reported once",
          "seat is 2 behind origin/main" in result.stdout, result.stdout + result.stderr)
    check("and still nothing was merged", not (seat / "advance-two.txt").exists())

    # A dirty tree changes nothing: there is no merge for it to block.
    (seat / "shared.txt").write_text("local edit in progress\n", encoding="utf-8")
    result = run_catch_up(["--cwd", str(seat)])
    check("a dirty tree is neither reported nor touched (nothing to block)",
          result.stdout.strip() == ""
          and (seat / "shared.txt").read_text(encoding="utf-8") == "local edit in progress\n",
          result.stdout)
    git(["checkout", "--", "shared.txt"], seat)

    # A branch that would conflict with main is not attempted: no merge
    # state appears, HEAD and the tree stay as they were.
    commit_file(seat, "shared.txt", "seat version\n", "seat edits shared")
    commit_file(origin, "shared.txt", "origin version\n", "origin edits shared")
    head_before = git(["rev-parse", "HEAD"], seat).stdout.strip()
    seat_git_dir = Path(git(["rev-parse", "--absolute-git-dir"], seat).stdout.strip())
    result = run_catch_up(["--cwd", str(seat)])
    check("a branch that would conflict is reported with its own commit counted, not attempted",
          "seat is 3 behind origin/main" in result.stdout
          and "1 own commit(s), 1 ahead counting merges" in result.stdout,
          result.stdout)
    check("no merge state appears", not (seat_git_dir / "MERGE_HEAD").exists())
    check("HEAD is unchanged and the tree is clean",
          git(["rev-parse", "HEAD"], seat).stdout.strip() == head_before
          and git(["status", "--porcelain"], seat).stdout.strip() == "")
    check("a seat-path run never emits a block, whatever the branch's shape",
          emitted_object(result) is None, result.stdout)

    # Own commits exclude merges: a branch carrying one catch-up merge and
    # nothing else reads "0 own, 1 ahead" — the shape the ruling measured on
    # supervisor-assumed-alive-says-only-what-is-kept (3 ahead, 0 own).
    # Cut behind main on purpose: the reference has fast-forwarded by now, so
    # a branch cut at its tip has nothing to merge.
    merge_seat = tmp / "merge-only-worktree"
    git(["worktree", "add", "-q", "-b", "merge-only", str(merge_seat), "main~1"], reference)
    configure_identity(merge_seat)
    git(["fetch", "-q", "origin"], merge_seat)
    git(["-c", "core.editor=true", "merge", "--no-ff", "--no-edit", "origin/main"], merge_seat)
    commit_file(origin, "advance-four.txt", "four\n", "advance four")
    result = run_catch_up(["--cwd", str(merge_seat)])
    check("own commits exclude merge commits: a merge-only branch reads 0 own, 1 ahead",
          "0 own commit(s), 1 ahead counting merges" in result.stdout, result.stdout)

    # The three head states, from git alone: pushed and equal to
    # origin/<branch> is the frozen one.
    git(["push", "-q", "origin", "seat"], seat)
    result = run_catch_up(["--cwd", str(seat)])
    check("a pushed head equal to its remote branch is reported frozen",
          "head pushed and equal to origin/seat (frozen" in result.stdout, result.stdout)
    check("the stamp records the head state", stamp_of(seat).get("head_state") == "pushed",
          str(stamp_of(seat)))
    commit_file(seat, "more.txt", "more\n", "a commit on top of the pushed head")
    result = run_catch_up(["--cwd", str(seat)])
    check("a pushed head with local commits on top says how many",
          "head pushed, with 1 local commit(s) not on origin/seat" in result.stdout,
          result.stdout)
    # Pushing that commit changes the head state alone — behind and own stay
    # as they were — and that alone is a changed fact worth one line.
    git(["push", "-q", "origin", "seat"], seat)
    result = run_catch_up(["--cwd", str(seat)])
    check("a changed head state alone is a changed fact, reported although behind and own did not change",
          "head pushed and equal to origin/seat" in result.stdout and "seat is 4 behind" in result.stdout,
          result.stdout)

    # Detached HEAD is named, not compared against origin/HEAD.
    detached = tmp / "detached-worktree"
    git(["worktree", "add", "-q", "--detach", str(detached), "main~1"], reference)
    result = run_catch_up(["--cwd", str(detached)])
    check("a detached HEAD is reported as such, and not merged",
          "detached HEAD" in result.stdout and "Not merged" in result.stdout, result.stdout)

    # The ghi-info shape (nedschorus#334): a branch with no commits of its
    # own, far behind, reported and not moved — and never a block, which is
    # the half of #334 this ruling removes.
    ghi = tmp / "ghi-info-worktree"
    first_commit = git(["rev-list", "--max-parents=0", "main"], reference).stdout.strip()
    git(["worktree", "add", "-q", "-b", "ghi-info", str(ghi), first_commit], reference)
    result = run_catch_up(["--cwd", str(ghi)])
    check("a branch with no own commits, far behind, is reported and left where it is",
          emitted_object(result) is None and "ghi-info is 4 behind origin/main" in result.stdout
          and "0 own commit(s)" in result.stdout and not (ghi / "advance-four.txt").exists(),
          result.stdout)

    # A foreign merge in progress is left exactly as found; the report still
    # comes.
    foreign_git_dir = Path(git(["rev-parse", "--absolute-git-dir"], ghi).stdout.strip())
    (foreign_git_dir / "MERGE_HEAD").write_text("0" * 40 + "\n", encoding="utf-8")
    commit_file(origin, "advance-five.txt", "five\n", "advance five")
    result = run_catch_up(["--cwd", str(ghi)])
    check("a foreign merge in progress survives untouched and the count is still reported",
          (foreign_git_dir / "MERGE_HEAD").exists() and "ghi-info is 5 behind" in result.stdout,
          result.stdout)
    (foreign_git_dir / "MERGE_HEAD").unlink()

    # The reference copy with a local commit is left alone, loudly.
    commit_file(reference, "local-on-main.txt", "local\n", "a commit main does not have")
    commit_file(origin, "advance-six.txt", "six\n", "advance six")
    result = run_catch_up(["--cwd", str(reference)])
    check("a reference with local commits is left alone",
          "left alone" in result.stdout and "local commit" in result.stdout,
          result.stdout)
    check("the diverged reference was not moved", not (reference / "advance-six.txt").exists())

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
    check("--reference-pull speaks plain text, never a block",
          emitted_object(pulled) is None, pulled.stdout)


print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
