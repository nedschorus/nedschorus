#!/usr/bin/env python3
"""Tests for git-gatekeeper.py, slices 1 to 3.

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
  plus the `unbuilt-option` boundary,
  B2's trailer round-trip, and B3d's version floors.
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

    # --- the slice boundary is a named refusal, never a crash --------------
    for label, arguments in (
        ("--no-wait", base_request(work, remote, base, ["README.md"]) + ["--no-wait"]),
        ("status", ["status", "deadbeef"]),
        ("cancel", ["cancel", "deadbeef"]),
    ):
        code, payload = run_gatekeeper(arguments, state_home)
        check(f"unbuilt {label} refuses by name",
              payload.get("error") == "unbuilt-option", payload)
        check(f"unbuilt {label} exits 1, not 2 — a boundary is not a defect", code == 1, code)
        check(f"unbuilt {label} names the slice that builds it",
              "slice" in payload.get("next_action", ""), payload)

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
