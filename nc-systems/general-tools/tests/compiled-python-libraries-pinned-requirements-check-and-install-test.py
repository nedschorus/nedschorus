#!/usr/bin/env python3
"""Tests for nc-systems/general-tools/compiled-python-libraries-pinned-requirements-check-and-install.py.

The process that reads installed versions and the installer are test
doubles, except one case that reads this python3's real versions.

Run: python3 nc-systems/general-tools/tests/compiled-python-libraries-pinned-requirements-check-and-install-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import fcntl
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]

_spec = importlib.util.spec_from_file_location(
    "compiled_python_libraries_pinned_requirements_check_and_install",
    REPOSITORY_ROOT / "nc-systems" / "general-tools"
    / "compiled-python-libraries-pinned-requirements-check-and-install.py")
checker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(checker)
install = checker.pinned_libraries_install

failures = 0


def check(name, condition, detail=None):
    global failures
    if condition:
        print(f"PASS  {name}")
    else:
        failures += 1
        print(f"FAIL  {name}: {detail!r}")


LOCK_DIRECTORY = Path(tempfile.mkdtemp()) / "install-state"
real_check_and_install_before_lock = checker.check_and_install


def check_and_install_in_scratch(host, runner, installer):
    return real_check_and_install_before_lock(host, runner, installer, LOCK_DIRECTORY)


checker.check_and_install = check_and_install_in_scratch
PINS = checker.pinned_versions()
check("the pinned file's lines are read as name and version, and its comments skipped",
      PINS == {"tree-sitter": "0.25.2", "tree-sitter-bash": "0.25.1"}, PINS)

with tempfile.TemporaryDirectory() as scratch:
    bad = Path(scratch) / "requirements.txt"
    bad.write_text("# a comment\ntree-sitter>=0.25\n", encoding="utf-8")
    try:
        checker.pinned_versions(bad)
        raised = None
    except ValueError as error:
        raised = error
    check("a line that does not pin one version is refused, naming the line",
          raised is not None and "tree-sitter>=0.25" in str(raised), raised)


def version_reader(*answers):
    """A runner that answers each versions read with the next of answers."""
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        answer = answers[min(len(calls), len(answers)) - 1]
        if isinstance(answer, int):
            return subprocess.CompletedProcess(command, answer, "", "Traceback: boom")
        return subprocess.CompletedProcess(command, 0, json.dumps(answer), "")
    run.calls = calls
    return run


ALL_PINNED = dict(PINS)
ONE_MISSING = {"tree-sitter": "0.25.2", "tree-sitter-bash": None}


def installer_that(outcome):
    state = {"installs": 0, "lock_held": None}

    def installer():
        state["installs"] += 1
        # The lock is held when another opener cannot take it without waiting.
        with open(LOCK_DIRECTORY / install.INSTALL_LOCK_FILE_NAME, "w") as other:
            try:
                fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
                state["lock_held"] = False
            except BlockingIOError:
                state["lock_held"] = True
        if outcome is not None:
            raise install.CompiledPythonLibrariesUnavailable(outcome)
        return "Successfully installed tree-sitter-bash-0.25.1"
    installer.state = state
    return installer


installer = installer_that(None)
status, lines = checker.check_and_install("ned-box", version_reader(ALL_PINNED), installer)
check("when every library is at its pin, no install runs and one line says so",
      status == 0 and installer.state["installs"] == 0 and len(lines) == 1
      and "all 2 pinned" in lines[0], (status, lines))

installer = installer_that(None)
status, lines = checker.check_and_install("ned-box", version_reader(ONE_MISSING, ALL_PINNED), installer)
check("a missing library is installed, and the one line names what was installed",
      status == 0 and installer.state["installs"] == 1 and len(lines) == 1
      and "tree-sitter-bash: wanted 0.25.1, found none" in lines[0], (status, lines))
check("the install runs holding the install lock the Bash guards take",
      installer.state["lock_held"] is True, installer.state)

installer = installer_that(None)
status, lines = checker.check_and_install(
    "ned-box", version_reader({"tree-sitter": "0.24.0", "tree-sitter-bash": "0.25.1"}, ALL_PINNED),
    installer)
check("a library at another version counts as missing and is installed",
      status == 0 and installer.state["installs"] == 1 and "found 0.24.0" in lines[0], lines)

installer = installer_that("`pip ...` exited 1: no network")
status, lines = checker.check_and_install("ned-box", version_reader(ONE_MISSING), installer)
text = "\n".join(lines)
check("a failed install exits 1, naming the machine, what is missing and what the install printed",
      status == 1 and "ned-box:" in lines[0] and "tree-sitter-bash: wanted 0.25.1, found none" in text
      and "no network" in text, lines)
check("on ned-box the by-hand command is the ssh form the user runs from the Mac, naming this interpreter",
      lines[-1] == f"To install them by hand, run this command in a Terminal on your Mac: "
                   f"ssh nedlern@ned-box '{sys.executable} -m pip install --user "
                   f"--break-system-packages -r {install.PINNED_REQUIREMENTS_FILE}'", lines[-1])
status, lines = checker.check_and_install("Neds-MacBook-Pro", version_reader(ONE_MISSING),
                                          installer_that("no network"))
check("on another machine the by-hand command is run there as it is",
      lines[-1].startswith(f"To install them by hand, run this command on Neds-MacBook-Pro: "
                           f"{sys.executable} -m pip install --user"), lines[-1])

status, lines = checker.check_and_install("ned-box", version_reader(ONE_MISSING),
                                          installer_that(None))
check("an install that succeeds but leaves a library missing exits 1, quoting what the install printed",
      status == 1 and "What the install printed: Successfully installed tree-sitter-bash-0.25.1"
      in lines, lines)

try:
    checker.check_and_install("ned-box", version_reader(1), installer_that(None))
    raised = None
except RuntimeError as error:
    raised = error
check("a versions read that fails raises, quoting what it printed",
      raised is not None and "boom" in str(raised), raised)

versions = checker.installed_versions({"pip", "no-such-library-for-this-test"})
check("this python3's real installed versions are read, and an absent library reads as None",
      isinstance(versions.get("pip"), str) and versions["no-such-library-for-this-test"] is None,
      versions)

import threading
other_install = open(LOCK_DIRECTORY / install.INSTALL_LOCK_FILE_NAME, "w")
fcntl.flock(other_install, fcntl.LOCK_EX)
threading.Timer(0.5, other_install.close).start()
installer = installer_that(None)
status, lines = checker.check_and_install("ned-box", version_reader(ONE_MISSING, ALL_PINNED), installer)
check("the script waits for an install another process is running, then installs",
      status == 0 and installer.state["installs"] == 1, (status, lines))

blocking_file = Path(tempfile.mkdtemp()) / "a-file-not-a-directory"
blocking_file.write_text("x")
installer = installer_that(None)
status, lines = real_check_and_install_before_lock("ned-box", version_reader(ONE_MISSING), installer,
                                                   blocking_file / "state")
check("an install lock that cannot be opened is reported as the install's failure, not a traceback",
      status == 1 and installer.state["installs"] == 0
      and any("install lock" in line for line in lines), (status, lines))

import contextlib
import io
real_check_and_install = checker.check_and_install


def check_failing(host):
    raise OSError("python3 not found")


checker.check_and_install = check_failing
printed = io.StringIO()
with contextlib.redirect_stdout(printed):
    status = checker.main([])
checker.check_and_install = real_check_and_install
check("a check that cannot run exits 1 and says why, naming the machine",
      status == 1 and "could not be checked: python3 not found" in printed.getvalue(),
      (status, printed.getvalue()))

print("all cases passed" if not failures else f"{failures} case(s) failed")
sys.exit(1 if failures else 0)
