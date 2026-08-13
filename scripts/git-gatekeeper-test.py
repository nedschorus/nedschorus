#!/usr/bin/env python3
"""Tests for git-gatekeeper.py, slices 1 to 5.

Run: python3 scripts/git-gatekeeper-test.py

Every pushing case targets a throwaway local BARE repository, fresh per case
(build binding B3a). Atomic ref update and non-fast-forward rejection are
git-generic, so the fixture is faithful and the real nedschorus repository is
untouchable by this suite. Nothing here authenticates, and nothing here reads
the legacy tree.

Coverage, against the specification's acceptance-test index:
  T1  every form refusal names its error and leaves no side effect
  T2  the happy path's four success guarantees, trailer asserted exactly
  T3  the digest: identical resubmit deduplicates; changed content digests
      fresh; metadata-only changes do not move the digest
  T9  the advisory: undeclared worktree changes are noted, never blocking
  T11 every import defect refuses as import-invalid, facts naming the defect
  T4  concurrent check-ins: the winner is unaware, the loser integrates
  T5  a real conflict refuses, naming the paths, the commits and the fix
  T6  sustained head movement ends at the retry cap, never a spin
  T7  the worker lifecycle: --no-wait accepted, every status outcome
      (checked-in / in-progress / abandoned / unknown / the B4d record)
  T8  cancel: all four branches, group-kill-and-wait for a live worker
  B3c the branch-protection audit: all three outcomes (ok and wrong via
      the --protection-file seam; audit-failed with gh off the PATH)
  plus the 4.1 live-twin in-progress answer, the expiry sweep, the repo
  git-config pins, B2's trailer round-trip, and B3d's version floors.
  (T10 retired 2026-08-10 with the `imports` subcommand; the trailer's
  exactness stays covered by the import happy path and B2's round-trip.
  The base is computed by the program since the same ruling, so no --base
  form cases exist.)

The import cases read a stand-in LEGACY repository fixture (B3b), never the
real nedlern tree — which does not exist on this box in any case.

Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPT_PATH = Path(__file__).with_name("git-gatekeeper.py")

_spec = importlib.util.spec_from_file_location("git_gatekeeper", SCRIPT_PATH)
gatekeeper = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gatekeeper)

failures = []
cases_run = 0


def check(case_name, condition, detail=""):
    global cases_run
    cases_run += 1
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def wait_for(predicate, seconds=60, interval=0.02):
    """Wait on a condition, not on a duration (ruled 2026-08-12).

    The cases that hold a worker open used to bet that their own work — a
    status call, a whole second check-in, a rival's git work — finished inside
    a fixed sleep. On a loaded host the sleep won and the assertion inverted
    quietly into the opposite outcome. Every such wait now watches the phase
    files the worker writes, under a timeout generous enough that expiry means
    a real defect rather than a slow machine.
    """
    deadline = time.time() + seconds
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return bool(predicate())


def git(arguments, cwd, check_result=True):
    """Fails its own case rather than unwinding the run (ruled 2026-08-12).

    This helper used to raise on a non-zero exit, and nothing caught it, so one
    broken fixture ended the suite where it stood. That surfaced as a traceback
    rather than a false green — but the cases that never ran left no trace, and
    a traceback after a hundred passes reads as an environment hiccup rather
    than as a third of the suite not executing.
    """
    completed = subprocess.run(
        ["git", *arguments], cwd=str(cwd), capture_output=True, text=True, check=False
    )
    if check_result and completed.returncode != 0:
        check(f"git {' '.join(arguments)} succeeds in {Path(cwd).name}",
              False, completed.stderr.strip() or completed.stdout.strip())
    return completed


def load_payload(text):
    """A reply that is not JSON is a failed case, never a dead run."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"outcome": "UNPARSEABLE", "stdout": text}


def run_gatekeeper(arguments, state_home):
    """Invoke the program as an agent would: a subprocess, JSON on stdout."""
    environment = {**os.environ, "XDG_STATE_HOME": str(state_home)}
    environment.pop("CLAUDE_CODE_SESSION_ID", None)
    completed = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *arguments],
        capture_output=True, text=True, check=False, env=environment,
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = {"outcome": "UNPARSEABLE", "stdout": completed.stdout,
                   "stderr": completed.stderr}
    return completed.returncode, payload


def make_fixture(root: Path, name: str):
    """A bare 'remote' with a seeded main, plus a working clone of it."""
    remote = root / f"{name}-remote.git"
    git(["init", "--quiet", "--bare", "--initial-branch=main", str(remote)], root)

    work = root / name
    git(["clone", "--quiet", str(remote), str(work)], root)
    git(["config", "user.name", "fixture"], work)
    git(["config", "user.email", "fixture@nedschorus.invalid"], work)

    (work / "README.md").write_text("seed\n", encoding="utf-8")
    (work / "keep.txt").write_text("untouched\n", encoding="utf-8")
    git(["add", "-A"], work)
    git(["commit", "--quiet", "-m", "seed the fixture history"], work)
    git(["push", "--quiet", "origin", "main"], work)
    base = git(["rev-parse", "HEAD"], work).stdout.strip()
    return remote, work, base


def make_legacy_fixture(root: Path, name: str):
    """A stand-in for the legacy repository: B3b. Never the real nedlern tree."""
    legacy = root / f"{name}-legacy"
    git(["init", "--quiet", "--initial-branch=main", str(legacy)], root)
    git(["config", "user.name", "legacy"], legacy)
    git(["config", "user.email", "legacy@nedschorus.invalid"], legacy)
    (legacy / "old-tool.py").write_text("print('the legacy version')\n", encoding="utf-8")
    git(["add", "-A"], legacy)
    git(["commit", "--quiet", "-m", "the legacy state being imported from"], legacy)
    legacy_commit = git(["rev-parse", "HEAD"], legacy).stdout.strip()

    # A later legacy commit, so a test can prove the import takes the content
    # as it stood at the DECLARED commit and not merely the newest.
    (legacy / "old-tool.py").write_text("print('changed after the import')\n", encoding="utf-8")
    git(["add", "-A"], legacy)
    git(["commit", "--quiet", "-m", "legacy moved on after the import"], legacy)
    return legacy, legacy_commit


def base_request(work, remote, base, files, message="fixture change", issue="none",
                 overrides=None):
    """A complete, well-formed argv, with any flag overridable by exact name.

    Built whole rather than sliced: a test that malforms the command line by
    accident measures argparse, not the gatekeeper.
    """
    fields = {
        "--message": message, "--import": "none", "--issue": issue,
        "--agent": "claude-code/opus-5", "--repo": str(work), "--remote": str(remote),
    }
    fields.update(overrides or {})
    arguments = ["check-in", "--files", *files]
    for name, value in fields.items():
        arguments += [name, value]
    return arguments


with tempfile.TemporaryDirectory() as workspace_name:
    workspace = Path(workspace_name)
    state_home = workspace / "state"

    # --- B3d: version floors ------------------------------------------------
    check("python floor is met", sys.version_info >= (3, 12), sys.version)
    # The version is matched rather than positional: Apple's git reports
    # "git version 2.39.5 (Apple Git-154)", whose last token is "Git-154)" —
    # taking it crashed the whole suite on macOS before the floor could report
    # (fixed 2026-08-12; the fleet runs macOS and Ubuntu, so a floor miss must
    # fail as a case, not as a traceback).
    git_version_output = subprocess.run(
        ["git", "--version"], capture_output=True, text=True, check=False
    ).stdout
    git_version_match = re.search(r"(\d+)\.(\d+)(?:\.\d+)?", git_version_output)
    check("git floor is met (>= 2.40)",
          git_version_match is not None
          and (int(git_version_match[1]), int(git_version_match[2])) >= (2, 40),
          git_version_output.strip())

    # --- T2: the happy path, and its four success guarantees ---------------
    remote, work, base = make_fixture(workspace, "happy")
    (work / "README.md").write_text("seed\nsecond line\n", encoding="utf-8")
    code, payload = run_gatekeeper(
        base_request(work, remote, base, ["README.md"], "add a second line", "3"), state_home
    )
    check("T2 happy path exits 0", code == 0, f"{code} {payload}")
    check("T2 happy path answers checked-in", payload.get("outcome") == "checked-in", payload)
    commit = payload.get("commit", "")
    check("T2 the reply carries the commit id", len(commit) == 40, payload)

    remote_log = git(["log", "main", "--format=%H"], remote).stdout.split()
    check("T2 guarantee 1: the change is on main", commit in remote_log, remote_log)

    pushed_content = git(["show", f"{commit}:README.md"], remote).stdout
    check("T2 guarantee 2: main holds exactly the declared content",
          pushed_content == "seed\nsecond line\n", repr(pushed_content))

    body = git(["show", "--no-patch", "--format=%B", commit], remote).stdout
    expected_trailers = [
        "Gatekeeper-origin: none",
        "Gatekeeper-agent: claude-code/opus-5",
        f"Gatekeeper-digest: {payload['digest']}",
        "Gatekeeper-import: none",
        "Gatekeeper-issue: #3",
    ]
    check("T2 guarantee 3: the trailer block is exact",
          body.strip().endswith("\n".join(expected_trailers)), repr(body))
    check("T2 the message body is the caller's", body.startswith("add a second line"), repr(body))
    check("T2 an undeclared path is untouched at main",
          git(["show", f"{commit}:keep.txt"], remote).stdout == "untouched\n")
    check("T2 the workspace is swept on success",
          not (state_home / "nedschorus-gatekeeper" / payload["digest"]).exists())

    # --- T3: the digest -----------------------------------------------------
    code, repeat = run_gatekeeper(
        base_request(work, remote, base, ["README.md"], "add a second line", "3"), state_home
    )
    check("T3 an identical resubmit deduplicates",
          repeat.get("outcome") == "already-checked-in", repeat)
    check("T3 the deduplicated reply names the original commit",
          repeat.get("commit") == commit, repeat)
    check("T3 a deduplicated resubmit exits 0", code == 0, code)

    code, metadata_only = run_gatekeeper(
        base_request(work, remote, base, ["README.md"], "a completely different message", "99"),
        state_home,
    )
    check("T3 metadata-only changes do not move the digest",
          metadata_only.get("outcome") == "already-checked-in", metadata_only)

    (work / "README.md").write_text("seed\nthird line\n", encoding="utf-8")
    fresh_digest = gatekeeper.compute_digest(
        base, {"README.md": b"seed\nthird line\n"}, "none"
    )
    check("T3 changed content digests fresh", fresh_digest != payload["digest"])

    # Framing regression (2026-08-12): a crafted single file whose bytes
    # embed the tag sequence must not collide with the two-file request it
    # imitates — the length prefixes keep them apart.
    crafted_one = {"a": b"x\x00path\x00b\x00content\x00y"}
    plain_two = {"a": b"x", "b": b"y"}
    check("T3 crafted content cannot collide two different requests",
          gatekeeper.compute_digest(base, crafted_one, "none")
          != gatekeeper.compute_digest(base, plain_two, "none"))

    # --- T9: the advisory ---------------------------------------------------
    remote, work, base = make_fixture(workspace, "advisory")
    (work / "README.md").write_text("seed\ndeclared\n", encoding="utf-8")
    (work / "keep.txt").write_text("undeclared work in progress\n", encoding="utf-8")
    code, payload = run_gatekeeper(
        base_request(work, remote, base, ["README.md"]), state_home
    )
    check("T9 the advisory never blocks", payload.get("outcome") == "checked-in", payload)
    check("T9 the advisory names the undeclared path",
          "keep.txt" in payload.get("advisory", ""), payload)
    check("T9 the undeclared path did not reach main",
          git(["show", "main:keep.txt"], remote).stdout == "untouched\n")

    git(["checkout", "--quiet", "--", "."], work)  # drop the advisory props
    git(["pull", "--quiet"], work)  # refresh past the first check-in
    (work / "brand-new.txt").write_text("forgotten new file\n", encoding="utf-8")
    (work / "README.md").write_text("seed\ndeclared\nagain\n", encoding="utf-8")
    code, payload = run_gatekeeper(
        base_request(work, remote, base, ["README.md"], "declare again"), state_home
    )
    check("T9 the advisory names an untracked (new) file",
          "brand-new.txt" in payload.get("advisory", ""), payload)

    # --- T4: the loser integrates over the newer commits --------------------
    # A request whose base is behind main exercises the identical code path as
    # a lost race: "being behind is just main moved before we started."
    remote, work, base = make_fixture(workspace, "integrate")
    ahead = workspace / "integrate-ahead"
    git(["clone", "--quiet", str(remote), str(ahead)], workspace)
    git(["config", "user.name", "ahead"], ahead)
    git(["config", "user.email", "ahead@nedschorus.invalid"], ahead)
    (ahead / "elsewhere.txt").write_text("a different path entirely\n", encoding="utf-8")
    git(["add", "-A"], ahead)
    git(["commit", "--quiet", "-m", "touch a path the pending request does not"], ahead)
    git(["push", "--quiet", "origin", "main"], ahead)

    (work / "README.md").write_text("seed\nintegrated\n", encoding="utf-8")
    code, payload = run_gatekeeper(base_request(work, remote, base, ["README.md"]), state_home)
    check("T4 a request behind main still checks in",
          payload.get("outcome") == "checked-in", payload)
    check("T4 the reply says how many commits it integrated over",
          payload.get("integrated_over") == 1, payload)
    check("T4 the newer commit survived the integration",
          git(["show", "main:elsewhere.txt"], remote).stdout == "a different path entirely\n")
    check("T4 the integrated change is on main",
          git(["show", "main:README.md"], remote).stdout == "seed\nintegrated\n")

    # T4, the genuine race: two gatekeepers started at the same moment on
    # different paths. Whoever loses must integrate and succeed anyway, so the
    # assertion holds no matter which one wins.
    remote, work, base = make_fixture(workspace, "race")
    second = workspace / "race-second"
    git(["clone", "--quiet", str(remote), str(second)], workspace)
    (work / "README.md").write_text("seed\nracer one\n", encoding="utf-8")
    (second / "keep.txt").write_text("racer two\n", encoding="utf-8")

    environment = {**os.environ, "XDG_STATE_HOME": str(state_home)}
    environment.pop("CLAUDE_CODE_SESSION_ID", None)
    racers = [
        subprocess.Popen(
            [sys.executable, str(SCRIPT_PATH),
             *base_request(one, remote, base, [path], f"racer on {path}")],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=environment,
        )
        for one, path in ((work, "README.md"), (second, "keep.txt"))
    ]
    outcomes = []
    for racer in racers:
        stdout, _ = racer.communicate(timeout=120)
        try:
            outcomes.append(json.loads(stdout))
        except json.JSONDecodeError:
            outcomes.append({"outcome": "UNPARSEABLE", "stdout": stdout})

    check("T4 both racers checked in",
          all(one.get("outcome") == "checked-in" for one in outcomes), outcomes)
    check("T4 exactly one racer had to integrate",
          sum(1 for one in outcomes if one.get("integrated_over")) == 1, outcomes)
    check("T4 both changes are on main after the race",
          git(["show", "main:README.md"], remote).stdout == "seed\nracer one\n"
          and git(["show", "main:keep.txt"], remote).stdout == "racer two\n")

    # --- T5: a real conflict refuses rather than guessing -------------------
    remote, work, base = make_fixture(workspace, "conflict")
    rival = workspace / "conflict-rival"
    git(["clone", "--quiet", str(remote), str(rival)], workspace)
    git(["config", "user.name", "rival"], rival)
    git(["config", "user.email", "rival@nedschorus.invalid"], rival)
    (rival / "README.md").write_text("seed\nthe rival's version\n", encoding="utf-8")
    git(["add", "-A"], rival)
    git(["commit", "--quiet", "-m", "change the very path the pending request changes"], rival)
    git(["push", "--quiet", "origin", "main"], rival)
    rival_tip = git(["rev-parse", "main"], remote).stdout.strip()

    (work / "README.md").write_text("seed\nour version\n", encoding="utf-8")
    code, payload = run_gatekeeper(base_request(work, remote, base, ["README.md"]), state_home)
    check("T5 a real conflict refuses", payload.get("error") == "conflict", payload)
    check("T5 conflict exits 1", code == 1, code)
    check("T5 conflict names the colliding path", "README.md" in payload.get("facts", ""), payload)
    check("T5 conflict names the intervening commit",
          "change the very path" in payload.get("facts", ""), payload)
    check("T5 conflict teaches the next action",
          "resubmit" in payload.get("next_action", "")
          and "main" in payload.get("next_action", ""), payload)
    check("T5 the rival's version is still what main holds",
          git(["show", "main:README.md"], remote).stdout == "seed\nthe rival's version\n")
    check("T5 conflict did not move main",
          git(["rev-parse", "main"], remote).stdout.strip() == rival_tip)

    # --- T6: the retry cap ends the loop rather than spinning ---------------
    # Sustained head movement is simulated at the seam rather than by racing a
    # background pusher: a timing-dependent test of a bound is a test that
    # sometimes does not test the bound.
    remote, work, base = make_fixture(workspace, "cap")
    (work / "README.md").write_text("seed\nnever lands\n", encoding="utf-8")

    original_attempt_push = gatekeeper.attempt_push
    original_fetch_main_tip = gatekeeper.fetch_main_tip
    original_paths_changed = gatekeeper.paths_changed_between
    original_build_candidate = gatekeeper.build_candidate
    rounds = {"count": 0}

    def always_rejected(clone):
        rounds["count"] += 1
        return False, "! [rejected] main -> main (non-fast-forward)"

    def always_moving(clone):
        return f"{rounds['count']:040x}"

    gatekeeper.attempt_push = always_rejected
    gatekeeper.fetch_main_tip = always_moving
    gatekeeper.paths_changed_between = lambda clone, older, newer: set()  # never a conflict
    gatekeeper.build_candidate = lambda clone, request, worktree, digest, target=None: "c" * 40
    try:
        capped = None
        try:
            gatekeeper.integrate_and_push(
                work, {"base": base, "paths": ["README.md"], "message": "m", "issue": "none",
                       "agent": "a", "origin": "none", "import": None},
                {"README.md": b"seed\nnever lands\n"}, "0" * 64,
            )
        except gatekeeper.Refusal as refusal:
            capped = refusal
        check("T6 sustained head movement ends in main-moving-too-fast",
              capped is not None and capped.error == "main-moving-too-fast", capped)
        check("T6 the loop is bounded at exactly the stated cap",
              rounds["count"] == gatekeeper.MAX_INTEGRATION_ROUNDS, rounds)
        check("T6 the cap refusal teaches a next action",
              bool(capped and capped.next_action), capped)
    finally:
        gatekeeper.attempt_push = original_attempt_push
        gatekeeper.fetch_main_tip = original_fetch_main_tip
        gatekeeper.paths_changed_between = original_paths_changed
        gatekeeper.build_candidate = original_build_candidate

    # --- retired by slice 3: main-moved is no longer an ending --------------
    # Slice 1 refused when main had moved at all. Slice 3 splits that: moved
    # with no overlap integrates (T4 above), moved with overlap conflicts (T5
    # above). The retired ending must not resurface as a surprise.
    remote, work, base = make_fixture(workspace, "moved")
    other = workspace / "moved-other"
    git(["clone", "--quiet", str(remote), str(other)], workspace)
    git(["config", "user.name", "other"], other)
    git(["config", "user.email", "other@nedschorus.invalid"], other)
    (other / "elsewhere.txt").write_text("someone else got there first\n", encoding="utf-8")
    git(["add", "-A"], other)
    git(["commit", "--quiet", "-m", "move main ahead of the declared base"], other)
    git(["push", "--quiet", "origin", "main"], other)

    (work / "README.md").write_text("seed\nlate\n", encoding="utf-8")
    code, payload = run_gatekeeper(base_request(work, remote, base, ["README.md"]), state_home)
    check("a moved main no longer refuses with main-moved",
          payload.get("error") != "main-moved", payload)
    check("a moved main integrates instead", payload.get("outcome") == "checked-in", payload)
    check("main now holds both the newer commit and the integrated change",
          git(["show", "main:elsewhere.txt"], remote).stdout == "someone else got there first\n"
          and git(["show", "main:README.md"], remote).stdout == "seed\nlate\n")

    # --- T1: every form refusal, and its lack of side effects --------------
    remote, work, base = make_fixture(workspace, "form")
    (work / "README.md").write_text("seed\nchanged\n", encoding="utf-8")
    main_before = git(["rev-parse", "main"], remote).stdout.strip()

    form_cases = [
        ("malformed-field", base_request(work, remote, base, ["README.md"], "   ")),
        ("malformed-field", base_request(work, remote, base, ["README.md"], issue="zero")),
        ("malformed-field",
         base_request(work, remote, base, ["README.md"], overrides={"--agent": "  "})),
        ("unknown-path", base_request(work, remote, base, ["no-such-path.txt"])),
        ("unchanged-path", base_request(work, remote, base, ["keep.txt"])),
        ("malformed-field", base_request(work, remote, base, ["a path with spaces.txt"])),
        ("malformed-field", base_request(work, remote, base, ["/etc/passwd"])),
        ("malformed-field", base_request(work, remote, base, ["../escape.txt"])),
        ("malformed-field", base_request(work, remote, base, [".git/config"])),
        ("malformed-field", base_request(work, remote, base, ["README.md", "README.md"])),
    ]
    for expected_error, arguments in form_cases:
        code, payload = run_gatekeeper(arguments, state_home)
        label = f"T1 {expected_error}: {' '.join(arguments[2:4])}"
        check(f"{label} refuses with its named error",
              payload.get("error") == expected_error, payload)
        check(f"{label} exits 1", code == 1, code)
        check(f"{label} states the facts", bool(payload.get("facts")), payload)
        check(f"{label} teaches the next action", bool(payload.get("next_action")), payload)

    check("T1 no form refusal moved main",
          git(["rev-parse", "main"], remote).stdout.strip() == main_before)
    check("T1 no form refusal left a workspace behind",
          not (state_home / "nedschorus-gatekeeper").exists()
          or not any((state_home / "nedschorus-gatekeeper").iterdir()))

    # --- slice 4: the worker lifecycle (T7, T8) -----------------------------
    remote, work, base = make_fixture(workspace, "nowait")
    (work / "README.md").write_text("seed\nasync change\n", encoding="utf-8")
    code, payload = run_gatekeeper(
        base_request(work, remote, base, ["README.md"], "async change") + ["--no-wait"],
        state_home,
    )
    check("T7 --no-wait answers accepted with the digest",
          payload.get("outcome") == "accepted"
          and len(payload.get("digest", "")) == 64, payload)
    nowait_digest = payload.get("digest", "")
    status_payload = {}
    deadline = time.time() + 60
    while time.time() < deadline:
        code, status_payload = run_gatekeeper(
            ["status", nowait_digest, "--repo", str(work)], state_home)
        if status_payload.get("outcome") == "checked-in":
            break
        time.sleep(0.3)
    check("T7 status reaches checked-in after a no-wait submission",
          status_payload.get("outcome") == "checked-in", status_payload)
    check("T7 the async change is on main",
          git(["show", "main:README.md"], remote).stdout == "seed\nasync change\n")
    check("T7 the worker swept its workspace on success",
          not (state_home / "nedschorus-gatekeeper" / nowait_digest).exists())
    code, payload = run_gatekeeper(["cancel", nowait_digest, "--repo", str(work)],
                                   state_home)
    check("T8 cancel after the push answers too-late",
          payload.get("outcome") == "too-late" and payload.get("commit"), payload)
    code, payload = run_gatekeeper(["cancel", "0" * 64, "--repo", str(work)], state_home)
    check("T8 cancelling an unknown digest answers unknown-request",
          payload.get("outcome") == "unknown-request", payload)
    code, payload = run_gatekeeper(["status", "0" * 64, "--repo", str(work)], state_home)
    check("T7 status on an unknown digest answers unknown",
          payload.get("outcome") == "unknown", payload)

    # B4d + liveness: a paused worker holds WORKING open; a rival then makes
    # its eventual push a real conflict, retained as the refusal record.
    remote, work, base = make_fixture(workspace, "b4d")
    rival = workspace / "b4d-rival"
    git(["clone", "--quiet", str(remote), str(rival)], workspace)
    git(["config", "user.name", "rival"], rival)
    git(["config", "user.email", "rival@nedschorus.invalid"], rival)
    (work / "README.md").write_text("seed\nours\n", encoding="utf-8")
    paused_environment = {**os.environ, "XDG_STATE_HOME": str(state_home),
                          "GATEKEEPER_TEST_WORKER_PAUSE_AT": "before-git"}
    paused_environment.pop("CLAUDE_CODE_SESSION_ID", None)
    completed = subprocess.run(
        [sys.executable, str(SCRIPT_PATH),
         *base_request(work, remote, base, ["README.md"], "will conflict"),
         "--no-wait"],
        capture_output=True, text=True, check=False, env=paused_environment)
    accepted = load_payload(completed.stdout)
    b4d_digest = accepted.get("digest", "")

    # One writer for worker.pid (ruled 2026-08-12, applied 2026-08-13). check_in
    # stamped "<pid> 0" immediately after Popen and then raced the worker for the
    # file; a worker dying before its own stamp left that placeholder forever,
    # and worker_state skips the start-time comparison on a placeholder, so the
    # workspace's pid-reuse guard was off for good. Probed the instant the
    # spawner returns, because that is when the placeholder existed and the
    # detached worker had not yet booted far enough to overwrite it.
    b4d_workspace = state_home / "nedschorus-gatekeeper" / b4d_digest
    try:
        spawn_tokens = (b4d_workspace / "worker.pid").read_text(
            encoding="utf-8").split()
    except OSError:
        spawn_tokens = []
    check("check_in writes no worker.pid placeholder in --no-wait mode",
          len(spawn_tokens) < 2 or spawn_tokens[1] != "0", spawn_tokens)
    stamp_deadline = time.time() + 10
    stamped: list[str] = []
    while time.time() < stamp_deadline and len(stamped) < 2:
        try:
            stamped = (b4d_workspace / "worker.pid").read_text(
                encoding="utf-8").split()
        except OSError:
            stamped = []
        if len(stamped) < 2:
            time.sleep(0.05)
    check("the detached worker stamps its own identity as its first act",
          len(stamped) == 2 and stamped[1] not in ("", "0"), stamped)

    check("B4d the paused submission was accepted",
          accepted.get("outcome") == "accepted", accepted)
    check("the worker announces the phase it is held at",
          wait_for(lambda: (b4d_workspace / ".reached-before-git").exists()),
          sorted(p.name for p in b4d_workspace.iterdir()))
    code, payload = run_gatekeeper(["status", b4d_digest, "--repo", str(work)],
                                   state_home)
    check("T7 status reports in-progress while the worker lives",
          payload.get("outcome") == "in-progress", payload)
    code, payload = run_gatekeeper(
        base_request(work, remote, base, ["README.md"], "will conflict"), state_home)
    check("a live twin submission answers in-progress, never swept (4.1)",
          payload.get("outcome") == "in-progress", payload)
    (rival / "README.md").write_text("seed\ntheirs\n", encoding="utf-8")
    git(["add", "-A"], rival)
    git(["commit", "--quiet", "-m", "rival changes the very same path"], rival)
    git(["push", "--quiet", "origin", "main"], rival)
    # Released only now that the rival's conflicting commit is on main, so the
    # worker's push is guaranteed to lose. The old form raced the rival's git
    # work against a three-second sleep.
    (b4d_workspace / ".release-before-git").write_text("", encoding="utf-8")
    deadline = time.time() + 60
    while time.time() < deadline:
        code, payload = run_gatekeeper(["status", b4d_digest, "--repo", str(work)],
                                       state_home)
        if payload.get("outcome") != "in-progress":
            break
        time.sleep(0.3)
    check("B4d status returns the retained conflict refusal",
          payload.get("error") == "conflict", payload)
    check("B4d the retained refusal exits 1", code == 1, code)
    code, payload = run_gatekeeper(["status", b4d_digest, "--repo", str(work)],
                                   state_home)
    check("B4d the record is returned once, then swept (second status: unknown)",
          payload.get("outcome") == "unknown", payload)

    # T8: cancelling a live worker — group kill, wait, history arbitrates.
    remote, work, base = make_fixture(workspace, "cancelrun")
    (work / "README.md").write_text("seed\nnever lands\n", encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(SCRIPT_PATH),
         *base_request(work, remote, base, ["README.md"], "to be cancelled"),
         "--no-wait"],
        capture_output=True, text=True, check=False, env=paused_environment)
    cancel_digest = load_payload(completed.stdout).get("digest", "")
    cancel_workspace = state_home / "nedschorus-gatekeeper" / cancel_digest
    wait_for(lambda: (cancel_workspace / ".reached-before-git").exists())
    code, payload = run_gatekeeper(["cancel", cancel_digest, "--repo", str(work)],
                                   state_home)
    check("T8 cancelling a live worker answers cancelled",
          payload.get("outcome") == "cancelled", payload)
    check("T8 the cancelled work never reached main",
          git(["show", "main:README.md"], remote).stdout == "seed\n")
    check("T8 the cancelled workspace is swept",
          not (state_home / "nedschorus-gatekeeper" / cancel_digest).exists())

    # Cancel truthfulness, first half (ruled 2026-08-12): a push that lands
    # inside cancel's wait must be reported. The history re-check used to run
    # only on the live-worker branch and only before the wait, so a worker that
    # pushed inside it was answered "cancelled — nothing reached main" while
    # status reported the commit a second later. The worker is held at
    # before-push and ignores SIGTERM, standing in for the two real ways a
    # worker outlives its cancellation; it is released while cancel waits.
    remote, work, base = make_fixture(workspace, "cancel-race")
    (work / "README.md").write_text("seed\nwins the race\n", encoding="utf-8")
    racing_environment = {**paused_environment,
                          "GATEKEEPER_TEST_WORKER_PAUSE_AT": "before-push",
                          "GATEKEEPER_TEST_WORKER_IGNORES_TERM": "1"}
    completed = subprocess.run(
        [sys.executable, str(SCRIPT_PATH),
         *base_request(work, remote, base, ["README.md"], "pushes inside the wait"),
         "--no-wait"],
        capture_output=True, text=True, check=False, env=racing_environment)
    race_digest = load_payload(completed.stdout).get("digest", "")
    race_workspace = state_home / "nedschorus-gatekeeper" / race_digest
    check("the worker reaches the pre-push phase",
          wait_for(lambda: (race_workspace / ".reached-before-push").exists()),
          race_digest)
    race_environment = {**os.environ, "XDG_STATE_HOME": str(state_home)}
    race_environment.pop("CLAUDE_CODE_SESSION_ID", None)
    canceller = subprocess.Popen(
        [sys.executable, str(SCRIPT_PATH), "cancel", race_digest, "--repo", str(work)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        env=race_environment)
    try:
        # Cancel's SIGTERM wait is ten seconds; releasing after one leaves nine
        # of margin, and overshooting cannot pass wrongly — SIGKILL would end
        # the worker with nothing pushed and the case would fail, not invert.
        time.sleep(1)
        (race_workspace / ".release-before-push").write_text("", encoding="utf-8")
        race_stdout, _ = canceller.communicate(timeout=120)
    finally:
        if canceller.poll() is None:
            canceller.kill()
            canceller.communicate()
    race_payload = load_payload(race_stdout)
    check("cancel answers too-late when the push lands inside its wait",
          race_payload.get("outcome") == "too-late"
          and race_payload.get("commit"), race_payload)
    check("the push that won the race is on main",
          git(["show", "main:README.md"], remote).stdout == "seed\nwins the race\n")

    # Cancel truthfulness, second half (ruled 2026-08-12): a worker cancel
    # cannot stop yields cancel-failed, the fifth outcome, and keeps its
    # workspace. Nothing confirmed the kill before that ruling — both killpg
    # calls swallow every error and worker_state reads permission-denied as
    # alive — so a worker this user cannot signal produced a false "cancelled"
    # after fifteen seconds of trying. Reproduced with pid 1, which is alive,
    # foreign, and unsignalable; the case is skipped where it is signalable
    # (running as root), because there cancel would really signal that group.
    try:
        os.kill(1, 0)
        init_is_unsignalable = False
    except PermissionError:
        init_is_unsignalable = True
    except OSError:
        init_is_unsignalable = False
    if init_is_unsignalable and os.geteuid() != 0:
        unstoppable_digest = "8" * 64
        unstoppable = state_home / "nedschorus-gatekeeper" / unstoppable_digest
        unstoppable.mkdir(parents=True)
        (unstoppable / "request.json").write_text("{}", encoding="utf-8")
        (unstoppable / "worker.pid").write_text(
            f"1 {gatekeeper.process_start_time(1)}", encoding="utf-8")
        code, payload = run_gatekeeper(
            ["cancel", unstoppable_digest, "--repo", str(work)], state_home)
        check("cancel answers cancel-failed when it cannot stop the worker",
              payload.get("outcome") == "cancel-failed", payload)
        check("cancel-failed exits 1", code == 1, code)
        check("cancel-failed names the worker it could not stop",
              "1" in payload.get("facts", ""), payload)
        check("cancel-failed leaves the workspace in place, never swept",
              unstoppable.is_dir(), payload)
    else:
        print("SKIP  cancel-failed: pid 1 is signalable from this account")

    # T7: the abandoned state, and cancel's fourth branch.
    fake_digest = "f" * 64
    fake_workspace = state_home / "nedschorus-gatekeeper" / fake_digest
    fake_workspace.mkdir(parents=True)
    (fake_workspace / "request.json").write_text("{}", encoding="utf-8")
    (fake_workspace / "worker.pid").write_text("999999 0", encoding="utf-8")
    code, payload = run_gatekeeper(["status", fake_digest, "--repo", str(work)],
                                   state_home)
    check("T7 a dead-worker workspace reports abandoned",
          payload.get("outcome") == "abandoned", payload)
    code, payload = run_gatekeeper(["cancel", fake_digest, "--repo", str(work)],
                                   state_home)
    check("T8 cancelling an abandoned workspace answers cancelled",
          payload.get("outcome") == "cancelled", payload)
    check("T8 the abandoned workspace is swept", not fake_workspace.exists())

    # A failed fetch is never read as absence (ruled 2026-08-12): status and
    # cancel used to grep a stale origin/main and assert 'unknown' or
    # 'cancelled — nothing reached main' for work that had reached it. The
    # catalog already carries network-down, documented as safely resubmittable.
    remote, work, base = make_fixture(workspace, "unreachable-remote")
    git(["remote", "set-url", "origin", str(workspace / "no-such-remote.git")], work)
    for subcommand in ("status", "cancel"):
        code, payload = run_gatekeeper(
            [subcommand, "1" * 64, "--repo", str(work)], state_home
        )
        check(f"{subcommand} answers network-down rather than asserting absence",
              payload.get("error") == "network-down", payload)
        check(f"{subcommand} exits 1 on network-down", code == 1, code)

    # The advisory names real files (ruled 2026-08-12). Plain --porcelain
    # collapses a wholly-new directory to one entry, so a declared new file
    # inside one was reported as an undeclared change — the advisory named the
    # caller's own work — while a genuinely forgotten file in a new directory
    # was never named either. Untracked names are arbitrary, so quoting made the
    # advisory report strings that were not paths.
    remote, work, base = make_fixture(workspace, "advisory-shapes")
    (work / "newdir").mkdir()
    (work / "newdir" / "declared.txt").write_text("declared\n", encoding="utf-8")
    (work / "forgotten-dir").mkdir()
    (work / "forgotten-dir" / "forgotten.txt").write_text("forgotten\n",
                                                          encoding="utf-8")
    (work / "spaced name.txt").write_text("spaced\n", encoding="utf-8")
    code, payload = run_gatekeeper(
        base_request(work, remote, base, ["newdir/declared.txt"], "declare in a new dir"),
        state_home,
    )
    advisory = payload.get("advisory", "")
    check("the advisory does not name the caller's own declared new file",
          "newdir" not in advisory, payload)
    check("the advisory names a forgotten file inside a new directory",
          "forgotten-dir/forgotten.txt" in advisory, payload)
    check("the advisory reports an awkward name as a real path",
          "spaced name.txt" in advisory and '\\"' not in advisory, payload)

    # The worker-identity guard works on this platform (ruled 2026-08-12): it
    # read /proc alone, so it returned "" for every process on macOS and the
    # comparison was skipped — dead code on half a fleet that runs macOS and
    # Ubuntu, with nothing announcing which behaviour a host had.
    check("a real start time is captured on this platform",
          gatekeeper.process_start_time(os.getpid()) not in ("", "0"),
          gatekeeper.process_start_time(os.getpid()))
    check("a start time carries no whitespace",
          len(gatekeeper.process_start_time(os.getpid()).split()) == 1,
          gatekeeper.process_start_time(os.getpid()))
    recycled_digest = "9" * 64
    recycled_workspace = state_home / "nedschorus-gatekeeper" / recycled_digest
    recycled_workspace.mkdir(parents=True)
    (recycled_workspace / "request.json").write_text("{}", encoding="utf-8")
    # A live pid (this test's own) recorded against a start time that is not its
    # own: the pid was recycled, so the worker it named is gone.
    (recycled_workspace / "worker.pid").write_text(
        f"{os.getpid()} not-the-start-time", encoding="utf-8"
    )
    code, payload = run_gatekeeper(["status", recycled_digest, "--repo", str(work)],
                                   state_home)
    check("a recycled pid does not masquerade as a live worker",
          payload.get("outcome") == "abandoned", payload)

    # The symlink boundary, both directions (ruled 2026-08-12, widening
    # WALK-1). The shipped check tested only a declared path's final component,
    # so a symlinked ANCESTOR read bytes from outside the repository; and the
    # write side had no check at all, so a symlink carried in MAIN's tree was
    # recreated in the candidate clone and the write followed it out. Both were
    # demonstrated during the PR #49 review. The outside file's bytes are the
    # load-bearing assertion: the reply alone looked like an ordinary io error.
    remote, work, base = make_fixture(workspace, "symlink-boundary")
    outside = workspace / "outside-every-repository"
    outside.mkdir()
    secret = outside / "secret.txt"
    secret.write_text("OUTSIDE CONTENT\n", encoding="utf-8")

    (work / "esc").symlink_to(outside, target_is_directory=True)
    code, payload = run_gatekeeper(
        base_request(work, remote, base, ["esc/secret.txt"], "read through a link"),
        state_home,
    )
    check("a symlinked ancestor refuses on the read side",
          payload.get("error") == "malformed-field"
          and "symlink" in payload.get("facts", ""), payload)
    (work / "esc").unlink()

    # main carries the link; the caller's copy is an ordinary file, so no check
    # on the caller's worktree can see the problem.
    seeded = workspace / "symlink-boundary-seed"
    git(["clone", "--quiet", str(remote), str(seeded)], workspace)
    git(["config", "user.name", "fixture"], seeded)
    git(["config", "user.email", "fixture@nedschorus.invalid"], seeded)
    (seeded / "docs").mkdir()
    os.symlink(str(secret), str(seeded / "docs" / "link.txt"))
    git(["add", "-A"], seeded)
    git(["commit", "--quiet", "-m", "main carries a symlink"], seeded)
    git(["push", "--quiet", "origin", "main"], seeded)
    git(["pull", "--quiet"], work)
    link_in_work = work / "docs" / "link.txt"
    if link_in_work.is_symlink():
        link_in_work.unlink()
    link_in_work.write_text("DECLARED BY THE CALLER\n", encoding="utf-8")
    code, payload = run_gatekeeper(
        base_request(work, remote, None, ["docs/link.txt"], "write through main's link"),
        state_home,
    )
    check("a symlink in main's tree refuses with its own named error",
          payload.get("error") == "base-tree-symlink", payload)
    check("the file outside every repository is untouched",
          secret.read_text(encoding="utf-8") == "OUTSIDE CONTENT\n", payload)

    # Death requires positive evidence (ruled 2026-08-12). An unreadable or
    # absent worker.pid used to read as "dead", the strongest conclusion from
    # the weakest evidence: status called a running request abandoned, and a
    # twin submission deleted the live worker's clone and spawned a rival.
    for torn_label, torn_bytes in (("an empty", ""), ("a garbage", "not-a-pid")):
        torn_digest = ("a" if torn_label == "an empty" else "b") * 64
        torn_workspace = state_home / "nedschorus-gatekeeper" / torn_digest
        torn_workspace.mkdir(parents=True)
        (torn_workspace / "request.json").write_text("{}", encoding="utf-8")
        (torn_workspace / "worker.pid").write_text(torn_bytes, encoding="utf-8")
        code, payload = run_gatekeeper(["status", torn_digest, "--repo", str(work)],
                                       state_home)
        check(f"{torn_label} worker.pid is not evidence of death",
              payload.get("outcome") == "in-progress", payload)
        check(f"{torn_label} worker.pid leaves the workspace intact",
              torn_workspace.is_dir(), payload)

    # The retained refusal record survives a status that lands mid-write, and is
    # delivered once (ruled 2026-08-12): the record was written in place after
    # its siblings were unlinked, so a status arriving in either window either
    # reported "abandoned" for a refused request or replaced the reason with a
    # generic io error and then swept it.
    unreadable_digest = "c" * 64
    unreadable_workspace = state_home / "nedschorus-gatekeeper" / unreadable_digest
    unreadable_workspace.mkdir(parents=True)
    (unreadable_workspace / "refusal.json").write_text("{half-written",
                                                       encoding="utf-8")
    code, payload = run_gatekeeper(["status", unreadable_digest, "--repo", str(work)],
                                   state_home)
    check("an unreadable refusal record is reported, not invented",
          payload.get("error") == "workspace-io-error", payload)
    check("an unreadable refusal record is retained, not swept",
          unreadable_workspace.is_dir(), payload)

    # Kill scope (ruled 2026-08-12): a recorded pid that does not lead its own
    # process group is signalled alone. worker.pid is written above the
    # --no-wait branch, so a waiting check-in records its own pid, whose group
    # belongs to the invoking shell or harness — and cancel's group kill reached
    # every process in it. Demonstrated during the PR #49 review by killing a
    # launcher and an unrelated sibling alongside the check-in.
    scope_digest = "d" * 64
    scope_workspace = state_home / "nedschorus-gatekeeper" / scope_digest
    scope_workspace.mkdir(parents=True)
    (scope_workspace / "request.json").write_text("{}", encoding="utf-8")
    # The launcher stands in for the caller's harness: its own session, holding
    # a child whose pid is recorded as the worker. A group kill takes the
    # launcher down with the child; a correctly scoped kill does not.
    launcher = subprocess.Popen(
        # The launcher reaps its child (child.wait()) before sleeping on, which
        # is the production shape: a detached worker's parent exits at once, so
        # the worker reparents to init and is reaped the moment it dies. Without
        # the reap the killed child lingers as a zombie, and os.kill(pid, 0)
        # succeeds on zombies — liveness would read "alive" forever.
        [sys.executable, "-c",
         "import subprocess, sys, time;"
         "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']);"
         "print(child.pid, flush=True);"
         "child.wait();"
         "time.sleep(60)"],
        stdout=subprocess.PIPE, text=True, start_new_session=True,
    )
    try:
        recorded_pid = int(launcher.stdout.readline().strip())
        (scope_workspace / "worker.pid").write_text(f"{recorded_pid} 0",
                                                    encoding="utf-8")
        code, payload = run_gatekeeper(
            ["cancel", scope_digest, "--repo", str(work)], state_home
        )
        check("cancel does not group-kill a pid that leads no group",
              launcher.poll() is None, payload)
        recorded_gone = False
        for _ in range(50):
            try:
                os.kill(recorded_pid, 0)
            except (ProcessLookupError, PermissionError):
                recorded_gone = True
                break
            time.sleep(0.1)
        check("cancel still signals the recorded process itself", recorded_gone,
              payload)
    finally:
        launcher.kill()
        launcher.wait(timeout=10)

    # Path safety (ruled 2026-08-12): a caller-supplied digest never becomes a
    # path. Joining an absolute argument discards the workspace root and '..'
    # climbs out of it, so before the enumeration lookup `cancel` deleted the
    # named directory and answered `cancelled`, and `status` read a foreign
    # refusal record and then deleted it. The surviving-directory assertion is
    # the load-bearing half: the reply alone looked correct in the absolute case
    # only because the deletion had already happened.
    for label, argument_builder in (
        ("an absolute path", lambda victim: str(victim)),
        ("a climbing path", lambda victim: f"../../{victim.name}"),
    ):
        for subcommand in ("status", "cancel"):
            victim = workspace / f"victim-{subcommand}-{label.split()[1]}"
            (victim / "nested").mkdir(parents=True)
            (victim / "keep.txt").write_text("PRECIOUS\n", encoding="utf-8")
            # A refusal record makes the status path reach its sweep, and the
            # climbing form needs the root to exist for '..' to resolve.
            (victim / "refusal.json").write_text('{"outcome": "planted"}',
                                                 encoding="utf-8")
            (state_home / "nedschorus-gatekeeper").mkdir(parents=True, exist_ok=True)
            code, payload = run_gatekeeper(
                [subcommand, argument_builder(victim), "--repo", str(work)], state_home
            )
            check(f"{subcommand} with {label} finds nothing",
                  payload.get("outcome") in ("unknown", "unknown-request"), payload)
            check(f"{subcommand} with {label} destroys nothing",
                  victim.exists() and (victim / "keep.txt").is_file(), payload)
            check(f"{subcommand} with {label} returns no foreign record",
                  payload.get("error") != "planted"
                  and payload.get("outcome") != "planted", payload)

    # The opportunistic expiry sweep (ruled 2026-08-10).
    old_stamp = time.time() - 31 * 24 * 3600
    aged_record = state_home / "nedschorus-gatekeeper" / ("e" * 64)
    aged_record.mkdir(parents=True)
    (aged_record / "refusal.json").write_text("{}", encoding="utf-8")
    os.utime(aged_record, (old_stamp, old_stamp))
    aged_scratch = state_home / "nedschorus-gatekeeper" / "screening-stale"
    aged_scratch.mkdir()
    os.utime(aged_scratch, (old_stamp, old_stamp))
    run_gatekeeper(["status", "0" * 64, "--repo", str(work)], state_home)
    check("the sweep clears a 31-day-old refusal record", not aged_record.exists())
    check("the sweep clears stale screening scratch", not aged_scratch.exists())

    # --- slice 5: the branch-protection audit (B3c's three outcomes) --------
    designed = {
        "restrictions": {"users": [{"login": "NedLern"}], "teams": [], "apps": []},
        "enforce_admins": {"enabled": True},
        "allow_force_pushes": {"enabled": False},
        "allow_deletions": {"enabled": False},
    }
    protection_file = workspace / "protection.json"
    protection_file.write_text(json.dumps(designed), encoding="utf-8")
    code, payload = run_gatekeeper(
        ["audit", "--protection-file", str(protection_file)], state_home)
    check("B3c audit answers protection-ok on the designed settings",
          payload.get("outcome") == "protection-ok" and code == 0, payload)

    # GitHub stores the canonical login lowercase and account names are
    # case-insensitive for identity, so the spelling difference alone is not
    # drift. Pinned because the audit read it as drift until 2026-08-13 and
    # answered protection-wrong against correctly configured protection.
    cased = {**designed, "restrictions": {**designed["restrictions"],
                                          "users": [{"login": "nedlern"}]}}
    protection_file.write_text(json.dumps(cased), encoding="utf-8")
    code, payload = run_gatekeeper(
        ["audit", "--protection-file", str(protection_file)], state_home)
    check("B3c audit answers protection-ok when the login differs only in case",
          payload.get("outcome") == "protection-ok" and code == 0, payload)

    drifted = {
        "restrictions": {"users": [{"login": "NedLern"}, {"login": "intruder"}],
                         "teams": [], "apps": []},
        "enforce_admins": {"enabled": False},
        "allow_force_pushes": {"enabled": True},
        "allow_deletions": {"enabled": False},
    }
    protection_file.write_text(json.dumps(drifted), encoding="utf-8")
    code, payload = run_gatekeeper(
        ["audit", "--protection-file", str(protection_file)], state_home)
    check("B3c audit answers protection-wrong on drifted settings",
          payload.get("outcome") == "protection-wrong" and code == 1, payload)
    audit_facts = payload.get("facts", "")
    check("B3c protection-wrong names every differing setting",
          "intruder" in audit_facts and "enforce-admins" in audit_facts
          and "force-push" in audit_facts, audit_facts)

    no_gh_environment = {**os.environ, "XDG_STATE_HOME": str(state_home),
                         "PATH": str(workspace / "empty-path")}
    no_gh_environment.pop("CLAUDE_CODE_SESSION_ID", None)
    completed = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "audit",
         "--repo-slug", "nedschorus/nedschorus"],
        capture_output=True, text=True, check=False, env=no_gh_environment,
    )
    audit_payload = load_payload(completed.stdout)
    check("B3c audit without gh answers audit-failed, never a silent skip",
          audit_payload.get("outcome") == "audit-failed"
          and completed.returncode == 1, audit_payload)

    # --- slice 5: the repo git-config pins ----------------------------------
    enclosing = SCRIPT_PATH.parent.parent
    for key in ("user.name", "user.email"):
        pinned = git(["config", key], enclosing, check_result=False).stdout.strip()
        check(f"slice 5 pins {key} in the enclosing repository", bool(pinned), key)
    use_config_only = git(["config", "user.useConfigOnly"], enclosing,
                          check_result=False).stdout.strip()
    check("slice 5 pins user.useConfigOnly=true", use_config_only == "true",
          use_config_only or "(unset)")

    # --import takes 'none' or nothing; any other value is a malformed field,
    # not a slice boundary, now that the entry checkpoint is built.
    code, payload = run_gatekeeper(
        base_request(work, remote, base, ["README.md"], overrides={"--import": "somecommit"}),
        state_home,
    )
    check("an unrecognised --import value is a malformed field",
          payload.get("error") == "malformed-field", payload)
    check("an unrecognised --import value exits 1", code == 1, code)

    # A declared symlink refuses (ruled 2026-08-12): the gate reads
    # regular-file bytes and does not follow links.
    (work / "linked.txt").symlink_to(work / "README.md")
    code, payload = run_gatekeeper(base_request(work, remote, base, ["linked.txt"]),
                                   state_home)
    check("a declared symlink refuses as malformed-field",
          payload.get("error") == "malformed-field"
          and "symlink" in payload.get("facts", ""), payload)
    check("a declared symlink exits 1", code == 1, code)

    # Command-line-form errors join the JSON contract (ruled 2026-08-11):
    # argparse-level mistakes refuse like any malformed field, exit 1 —
    # never usage text with the defect code.
    for cli_label, cli_arguments in (
        ("an unknown flag", base_request(work, remote, base, ["README.md"]) + ["--bogus"]),
        ("a missing required field", ["check-in", "--files", "README.md"]),
        ("no subcommand at all", []),
    ):
        code, payload = run_gatekeeper(cli_arguments, state_home)
        check(f"{cli_label} refuses as malformed-field JSON",
              payload.get("error") == "malformed-field", payload)
        check(f"{cli_label} exits 1, not the defect code", code == 1, code)

    # --- deletions and additions, since the happy path only modified -------
    remote, work, base = make_fixture(workspace, "addremove")
    (work / "added.txt").write_text("new content\n", encoding="utf-8")
    (work / "keep.txt").unlink()
    code, payload = run_gatekeeper(
        base_request(work, remote, base, ["added.txt", "keep.txt"], "add one path, delete another"),
        state_home,
    )
    check("an addition and a deletion check in together",
          payload.get("outcome") == "checked-in", payload)
    if payload.get("commit"):
        listed = git(["ls-tree", "--name-only", payload["commit"]], remote).stdout.split()
        check("the added path is on main", "added.txt" in listed, listed)
        check("the deleted path is gone from main", "keep.txt" not in listed, listed)

    # --- slice 2: the entry checkpoint --------------------------------------
    remote, work, base = make_fixture(workspace, "import")
    legacy, legacy_commit = make_legacy_fixture(workspace, "import")

    def import_request(files, dest, source="old-tool.py", commit=None, message="import a tool",
                       drop=(), extra=None):
        arguments = ["check-in", "--files", *files, "--message", message,
                     "--issue", "none", "--agent", "claude-code/opus-5",
                     "--repo", str(work), "--remote", str(remote), "--legacy-repo", str(legacy)]
        triple = {"--import-commit": commit or legacy_commit,
                  "--import-source": source, "--import-dest": dest}
        for name, value in triple.items():
            if name not in drop:
                arguments += [name, value]
        return arguments + list(extra or [])

    code, payload = run_gatekeeper(
        import_request(["tools/imported-tool.py"], "tools/imported-tool.py"), state_home
    )
    check("a declared import checks in", payload.get("outcome") == "checked-in", payload)
    imported_commit = payload.get("commit", "")
    if imported_commit:
        content = git(["show", f"{imported_commit}:tools/imported-tool.py"], remote).stdout
        check("the import copies the bytes as they stood at the declared commit",
              content == "print('the legacy version')\n", repr(content))

        body = git(["show", "--no-patch", "--format=%B", imported_commit], remote).stdout
        expected = f"Gatekeeper-import: {legacy_commit} old-tool.py -> tools/imported-tool.py"
        check("the import trailer records the whole triple", expected in body, body)

        # B2: the trailer must survive git's own trailer parser, not just a
        # substring match — the record is only as good as what can read it.
        interpreted = subprocess.run(
            ["git", "interpret-trailers", "--parse"], input=body,
            capture_output=True, text=True, check=False, cwd=str(remote),
        ).stdout
        check("B2 the trailer round-trips through git interpret-trailers",
              expected in interpreted, interpreted)

        # T10 retired 2026-08-10: the `imports` subcommand was deleted. The
        # trailer is the record; the view is one documented git command, and
        # the deleted command must stay deleted rather than resurface.
        listed = git(["log", "main", "--grep", "Gatekeeper-import: " + legacy_commit],
                     remote).stdout
        check("the documented git-log view finds the import trailer",
              imported_commit[:7] in listed or imported_commit in listed, listed)
        code, payload = run_gatekeeper(["imports"], state_home)
        check("the deleted imports subcommand refuses as a malformed command line",
              payload.get("error") == "malformed-field" and code == 1, payload)

    # --- T11: every import error class -------------------------------------
    # Every import defect refuses as the one code import-invalid (four codes
    # merged 2026-08-10); the facts distinguish the defects, so each case also
    # asserts its distinguishing fact fragment.
    import_error_cases = [
        ("import-invalid", "missing",
         import_request(["tools/x.py"], "tools/x.py", drop=("--import-source",))),
        ("import-invalid", "missing",
         import_request(["tools/x.py"], "tools/x.py",
                        drop=("--import-commit", "--import-source"))),
        ("import-invalid", "no import was declared",
         import_request(["tools/x.py"], "tools/x.py",
                        drop=("--import-commit", "--import-source", "--import-dest"))),
        ("import-invalid", "--import none was given alongside",
         import_request(["tools/x.py"], "tools/x.py", extra=["--import", "none"])),
        ("import-invalid", "not in --files",
         import_request(["README.md"], "tools/undeclared.py")),
        ("import-invalid", "does not exist in the legacy repository",
         import_request(["tools/x.py"], "tools/x.py", source="no-such-legacy-path.py")),
        ("import-invalid", "no commit",
         import_request(["tools/x.py"], "tools/x.py", commit="0" * 40)),
        ("malformed-field", "not a full 40-character commit id",
         import_request(["tools/x.py"], "tools/x.py", commit="abc123")),
        ("malformed-field", "whitespace",
         import_request(["tools/x.py"], "tools/x.py", source="a legacy path.py")),
    ]
    main_before_imports = git(["rev-parse", "main"], remote).stdout.strip()
    for expected_error, fact_fragment, arguments in import_error_cases:
        code, payload = run_gatekeeper(arguments, state_home)
        label = f"T11 {expected_error} ({fact_fragment[:24]})"
        check(f"{label} refuses by name", payload.get("error") == expected_error, payload)
        check(f"{label} exits 1", code == 1, code)
        check(f"{label} facts name the defect",
              fact_fragment in payload.get("facts", ""), payload)
        check(f"{label} teaches the next action", bool(payload.get("next_action")), payload)

    code, payload = run_gatekeeper(
        import_request(["tools/x.py"], "tools/x.py",
                       extra=["--legacy-repo", str(workspace / "not-a-repository")]),
        state_home,
    )
    check("T11 an unreadable legacy checkout refuses import-invalid",
          payload.get("error") == "import-invalid"
          and "not a readable git repository" in payload.get("facts", ""), payload)

    check("T11 no import refusal moved main",
          git(["rev-parse", "main"], remote).stdout.strip() == main_before_imports)

    # --- the origin trailer records the submitting session -----------------
    remote, work, base = make_fixture(workspace, "origin")
    (work / "README.md").write_text("seed\nwith a session\n", encoding="utf-8")
    environment = {**os.environ, "XDG_STATE_HOME": str(state_home),
                   "CLAUDE_CODE_SESSION_ID": "session-under-test"}
    completed = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *base_request(work, remote, base, ["README.md"])],
        capture_output=True, text=True, check=False, env=environment,
    )
    origin_payload = load_payload(completed.stdout)
    origin_body = git(
        ["show", "--no-patch", "--format=%B", origin_payload["commit"]], remote
    ).stdout
    check("the origin trailer records the submitting session",
          "Gatekeeper-origin: session-under-test" in origin_body, origin_body)

    shutil.rmtree(state_home, ignore_errors=True)

print()
# The count is printed so a short run is visible on sight (ruled 2026-08-12): a
# run that ends early leaves the cases it never reached with no trace at all,
# and a traceback arriving after a hundred passes reads as an environment
# hiccup rather than as a third of the suite not executing.
print(f"{cases_run} cases run")
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
