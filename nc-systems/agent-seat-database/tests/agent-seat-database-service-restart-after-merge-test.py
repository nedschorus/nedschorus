#!/usr/bin/env python3
"""Tests for nc-systems/agent-seat-database/agent-seat-database-service-restart-after-merge.py
and scripts/git-client-side-hooks/post-merge, which runs it.

Each case fast-forwards a temporary repository and runs the program in it, with
a fake `systemctl` on PATH that records its arguments and succeeds or fails on
request: a merge that changes the service restarts the unit, one that does not
leaves it, a failed restart prints systemctl's error and exits 1, a checkout
that is not the reference-checkout is left alone, and git failing to list the
merge's changes is reported. A last case merges through the real post-merge
hook in a checkout that is not ned-box's reference-checkout.

Run: python3 nc-systems/agent-seat-database/tests/agent-seat-database-service-restart-after-merge-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import io
import os
import subprocess
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PROGRAM_PATH = (REPOSITORY_ROOT / "nc-systems" / "agent-seat-database"
                / "agent-seat-database-service-restart-after-merge.py")
HOOKS_DIRECTORY = REPOSITORY_ROOT / "scripts" / "git-client-side-hooks"
_spec = importlib.util.spec_from_file_location("agent_seat_database_service_restart_after_merge",
                                               PROGRAM_PATH)
restarter = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(restarter)

_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    REPOSITORY_ROOT / "scripts" / "git-redirecting-environment-removal-test-fixture.py")
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

failures = 0


def check(name, condition, detail=None):
    global failures
    if condition:
        print(f"PASS  {name}")
    else:
        failures += 1
        print(f"FAIL  {name}: {detail!r}")


FAKE_SYSTEMCTL = """#!/bin/sh
if [ -z "$XDG_RUNTIME_DIR" ]; then
  echo "Failed to connect to user scope bus via local transport: No such file or directory" >&2
  exit 1
fi
echo "$@" >> "$FAKE_SYSTEMCTL_LOG"
echo "$XDG_RUNTIME_DIR" >> "$FAKE_SYSTEMCTL_LOG.runtime"
if [ -n "$FAKE_SYSTEMCTL_FAIL" ]; then
  echo "Failed to restart agent-seat-database-service.service: Unit agent-seat-database-service.service not found." >&2
  exit 5
fi
"""

with tempfile.TemporaryDirectory() as scratch:
    scratch = Path(scratch)
    bin_directory = scratch / "bin"
    bin_directory.mkdir()
    (bin_directory / "systemctl").write_text(FAKE_SYSTEMCTL, encoding="utf-8")
    (bin_directory / "systemctl").chmod(0o755)
    systemctl_log = scratch / "systemctl.log"
    os.environ.update(PATH=f"{bin_directory}:{os.environ['PATH']}",
                      FAKE_SYSTEMCTL_LOG=str(systemctl_log), GIT_AUTHOR_NAME="test",
                      GIT_AUTHOR_EMAIL="test@test.invalid", GIT_COMMITTER_NAME="test",
                      GIT_COMMITTER_EMAIL="test@test.invalid", GIT_CONFIG_GLOBAL="/dev/null",
                      GIT_CONFIG_NOSYSTEM="1")
    repository = scratch / "clone"

    def git(*arguments, hooks="/dev/null"):
        return subprocess.run(["git", "-c", f"core.hooksPath={hooks}", *arguments],
                              cwd=repository, capture_output=True, text=True, check=False)

    def commit_on_branch(branch, path, text):
        git("checkout", "-q", "-B", branch, "main")
        target = repository / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        git("add", path)
        git("commit", "-q", "-m", f"change {path}")
        git("checkout", "-q", "main")

    def run(reference=None, fail=False):
        if systemctl_log.exists():
            systemctl_log.unlink()
        os.environ["FAKE_SYSTEMCTL_FAIL"] = "1" if fail else ""
        printed, errors = io.StringIO(), io.StringIO()
        before = os.getcwd()
        os.chdir(repository)
        try:
            with redirect_stdout(printed), redirect_stderr(errors):
                code = restarter.main(["--reference-checkout", str(reference or repository)])
        finally:
            os.chdir(before)
        calls = systemctl_log.read_text().splitlines() if systemctl_log.exists() else []
        return code, calls, printed.getvalue(), errors.getvalue()

    subprocess.run(["git", "init", "-q", "-b", "main", str(repository)], check=True)
    git("commit", "-q", "--allow-empty", "-m", "start")

    code, calls, printed, errors = run()
    check("git failing to list the merge's changes (no ORIG_HEAD): exit 1, naming the command, "
          "and nothing restarted",
          code == 1 and calls == [] and "git diff --name-only ORIG_HEAD HEAD" in errors
          and "Run `XDG_RUNTIME_DIR=/run/user/$(id -u) systemctl --user restart "
              "agent-seat-database-service.service` on ned-box." in errors
          and "If the merge changed" not in errors
          and "service was not restarted: fatal:" in errors,
          (code, errors))

    commit_on_branch("docs", "README.md", "words")
    git("merge", "-q", "--ff-only", "docs")
    code, calls, printed, errors = run()
    check("a merge that does not change the service restarts nothing",
          code == 0 and calls == [] and errors == "", (code, calls, errors))

    commit_on_branch("service", restarter.SERVICE_FILES[0], "print('new')")
    git("merge", "-q", "--ff-only", "service")
    code, calls, printed, errors = run(reference=scratch / "elsewhere")
    check("in a checkout that is not the reference-checkout nothing is restarted",
          code == 0 and calls == [] and printed == "", (code, calls))
    code, calls, printed, errors = run()
    check("a fast-forward that changes the service restarts the unit",
          code == 0 and calls == ["--user restart agent-seat-database-service.service"]
          and "restarted" in printed, (code, calls, errors))
    saved_runtime_directory = os.environ.pop("XDG_RUNTIME_DIR", None)
    runtime_log = Path(f"{systemctl_log}.runtime")
    try:
        code, calls, printed, errors = run()
    finally:
        if saved_runtime_directory is not None:
            os.environ["XDG_RUNTIME_DIR"] = saved_runtime_directory
    check("a caller without XDG_RUNTIME_DIR, as an agent's Stop hook can be, still restarts "
          "the unit, with systemctl given /run/user/<uid>",
          code == 0 and calls == ["--user restart agent-seat-database-service.service"]
          and runtime_log.read_text().splitlines()[-1] == f"/run/user/{os.getuid()}",
          (code, calls, errors))
    os.environ["XDG_RUNTIME_DIR"] = str(scratch / "runtime")
    try:
        code, calls, printed, errors = run()
    finally:
        if saved_runtime_directory is None:
            os.environ.pop("XDG_RUNTIME_DIR")
        else:
            os.environ["XDG_RUNTIME_DIR"] = saved_runtime_directory
    check("a caller's own XDG_RUNTIME_DIR is passed to systemctl unchanged",
          code == 0 and runtime_log.read_text().splitlines()[-1] == str(scratch / "runtime"),
          (code, errors))
    code, calls, printed, errors = run(fail=True)
    check("a failed restart prints systemctl's error and exits 1",
          code == 1 and "systemctl said: Failed to restart agent-seat-database-service."
          "service: Unit agent-seat-database-service.service not found" in errors
          and "exited 5" in errors, (code, errors))

    outside = scratch / "not-a-repository"
    outside.mkdir()
    before = os.getcwd()
    os.chdir(outside)
    try:
        code = restarter.main(["--reference-checkout", str(outside)])
    finally:
        os.chdir(before)
    check("outside any git checkout nothing is done", code == 0, code)

    check("the reference-checkout by default is ned-box's",
          restarter.NED_BOX_REFERENCE_CHECKOUT == "/home/nedlern/Projects/nedschorus")

    commit_on_branch("service-again", restarter.SERVICE_FILES[0], "print('newer')")
    if systemctl_log.exists():
        systemctl_log.unlink()
    merged = git("merge", "--ff-only", "service-again", hooks=str(HOOKS_DIRECTORY))
    check("through the real post-merge hook, a merge in a checkout that is not ned-box's "
          "reference-checkout succeeds and restarts nothing",
          merged.returncode == 0 and not systemctl_log.exists()
          and git("rev-parse", "HEAD").stdout == git("rev-parse", "service-again").stdout,
          (merged.returncode, merged.stdout, merged.stderr))

raise SystemExit(1 if failures else 0)
