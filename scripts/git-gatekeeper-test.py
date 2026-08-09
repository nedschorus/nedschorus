#!/usr/bin/env python3
"""Tests for git-gatekeeper.py, slice 1.

Run: python3 scripts/git-gatekeeper-test.py

Every pushing case targets a throwaway local BARE repository, fresh per case
(build binding B3a). Atomic ref update and non-fast-forward rejection are
git-generic, so the fixture is faithful and the real nedschorus repository is
untouchable by this suite. Nothing here authenticates, and nothing here reads
the legacy tree.

Coverage, against the specification's build-slice test list:
  T1  every form refusal names its error and leaves no side effect
  T2  the happy path's four success guarantees, trailer asserted exactly
  T3  the digest: identical resubmit deduplicates; changed content digests
      fresh; metadata-only changes do not move the digest
  T9  the advisory: undeclared worktree changes are noted, never blocking
  plus slice 1's own `main-moved` refusal, the `unbuilt-option` boundary,
  and B3d's version-floor smoke assertion.

Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_PATH = Path(__file__).with_name("git-gatekeeper.py")

_spec = importlib.util.spec_from_file_location("git_gatekeeper", SCRIPT_PATH)
gatekeeper = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gatekeeper)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def git(arguments, cwd, check_result=True):
    completed = subprocess.run(
        ["git", *arguments], cwd=str(cwd), capture_output=True, text=True, check=False
    )
    if check_result and completed.returncode != 0:
        raise AssertionError(f"git {' '.join(arguments)} failed: {completed.stderr}")
    return completed


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


def base_request(work, remote, base, files, message="fixture change", issue="none",
                 overrides=None):
    """A complete, well-formed argv, with any flag overridable by exact name.

    Built whole rather than sliced: a test that malforms the command line by
    accident measures argparse, not the gatekeeper.
    """
    fields = {
        "--message": message, "--base": base, "--import": "none", "--issue": issue,
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
    git_version = subprocess.run(
        ["git", "--version"], capture_output=True, text=True, check=False
    ).stdout.split()[-1]
    check("git floor is met (>= 2.40)",
          tuple(int(part) for part in git_version.split(".")[:2]) >= (2, 40), git_version)

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

    # --- slice 1's main-moved refusal --------------------------------------
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
    check("main-moved refuses rather than guessing",
          payload.get("error") == "main-moved", payload)
    check("main-moved exits 1, the refusal code", code == 1, code)
    check("main-moved names the intervening commit",
          "move main ahead" in payload.get("facts", ""), payload)
    check("main-moved teaches the next action",
          "--base" in payload.get("next_action", ""), payload)
    check("main-moved left main untouched",
          len(git(["log", "main", "--format=%H"], remote).stdout.split()) == 2)

    # --- T1: every form refusal, and its lack of side effects --------------
    remote, work, base = make_fixture(workspace, "form")
    (work / "README.md").write_text("seed\nchanged\n", encoding="utf-8")
    main_before = git(["rev-parse", "main"], remote).stdout.strip()

    form_cases = [
        ("missing-message", base_request(work, remote, base, ["README.md"], "   ")),
        ("malformed-field",
         base_request(work, remote, base, ["README.md"], overrides={"--base": "abc123"})),
        ("unknown-base",
         base_request(work, remote, base, ["README.md"], overrides={"--base": "0" * 40})),
        ("malformed-field", base_request(work, remote, base, ["README.md"], issue="zero")),
        ("malformed-field",
         base_request(work, remote, base, ["README.md"], overrides={"--agent": "  "})),
        ("unknown-path", base_request(work, remote, base, ["no-such-path.txt"])),
        ("unchanged-path", base_request(work, remote, base, ["keep.txt"])),
        ("unsafe-path", base_request(work, remote, base, ["a path with spaces.txt"])),
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

    # --- the slice boundary is a named refusal, never a crash --------------
    for arguments, expected in (
        (base_request(work, remote, base, ["README.md"]) + ["--no-wait"], "unbuilt-option"),
        (base_request(work, remote, base, ["README.md"],
                      overrides={"--import": "somecommit"}), "unbuilt-option"),
        (["status", "deadbeef"], "unbuilt-option"),
        (["cancel", "deadbeef"], "unbuilt-option"),
        (["imports"], "unbuilt-option"),
    ):
        code, payload = run_gatekeeper(arguments, state_home)
        check(f"unbuilt {arguments[0]} {arguments[1] if len(arguments) > 1 else ''} "
              f"refuses by name", payload.get("error") == expected, payload)
        check(f"unbuilt {arguments[0]} exits 1, not 2 — a boundary is not a defect",
              code == 1, code)
        check(f"unbuilt {arguments[0]} names the slice that builds it",
              "slice" in payload.get("next_action", ""), payload)

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

    # --- the origin trailer records the submitting session -----------------
    remote, work, base = make_fixture(workspace, "origin")
    (work / "README.md").write_text("seed\nwith a session\n", encoding="utf-8")
    environment = {**os.environ, "XDG_STATE_HOME": str(state_home),
                   "CLAUDE_CODE_SESSION_ID": "session-under-test"}
    completed = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *base_request(work, remote, base, ["README.md"])],
        capture_output=True, text=True, check=False, env=environment,
    )
    origin_payload = json.loads(completed.stdout)
    origin_body = git(
        ["show", "--no-patch", "--format=%B", origin_payload["commit"]], remote
    ).stdout
    check("the origin trailer records the submitting session",
          "Gatekeeper-origin: session-under-test" in origin_body, origin_body)

    shutil.rmtree(state_home, ignore_errors=True)

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
