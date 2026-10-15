#!/usr/bin/env python3
"""Tests for nc-systems/general-tools/python-libraries-pinned-requirements-check-and-install.py.

The process that reads installed versions and the installer are test
doubles, except one case that reads this python3's real versions.

Run: python3 nc-systems/general-tools/tests/python-libraries-pinned-requirements-check-and-install-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]

_spec = importlib.util.spec_from_file_location(
    "python_libraries_pinned_requirements_check_and_install",
    REPOSITORY_ROOT / "nc-systems" / "general-tools"
    / "python-libraries-pinned-requirements-check-and-install.py")
checker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(checker)
install = checker.python_libraries_pinned_requirements_install_if_missing_then_import_common

failures = 0


def check(name, condition, detail=None):
    global failures
    if condition:
        print(f"PASS  {name}")
    else:
        failures += 1
        print(f"FAIL  {name}: {detail!r}")


# The cases below read a fixture list of their own, so a library added to the real pinned list
# changes none of them.
FIXTURE_DIRECTORY = tempfile.TemporaryDirectory()
FIXTURE = Path(FIXTURE_DIRECTORY.name) / "pinned-requirements.txt"
FIXTURE.write_text("# a comment line\ntree-sitter==0.25.2\n\ntree-sitter-bash==0.25.1  # a trailing comment\n",
                   encoding="utf-8")
PINS = checker.pinned_versions(FIXTURE)
check("the pinned file's lines are read as name and version, and its comments skipped",
      PINS == {"tree-sitter": "0.25.2", "tree-sitter-bash": "0.25.1"}, PINS)

def check_and_install_with_fixture(host, runner, installer):
    return checker.check_and_install(host, runner, installer, requirements_file=FIXTURE)


real_pins = checker.pinned_versions()
check("the real pinned file parses and pins tree-sitter and tree-sitter-bash, which the shell reader needs",
      {"tree-sitter", "tree-sitter-bash"} <= set(real_pins), real_pins)
check("the real pinned file pins markdown-it-py and its dependency mdurl, which the hard-wrap reminder needs",
      {"markdown-it-py", "mdurl"} <= set(real_pins), real_pins)
pinned_lines = [line for line in install.PINNED_REQUIREMENTS_FILE.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.lstrip().startswith("#")]
check("every pinned line records the library's license beside it",
      pinned_lines and all("  # " in line and line.split("  # ", 1)[1].strip() for line in pinned_lines),
      pinned_lines)

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
    state = {"installs": 0}

    def installer():
        state["installs"] += 1
        if outcome is not None:
            raise install.PythonLibrariesPinnedRequirementsInstallOrImportFailed(outcome)
        return "Successfully installed tree-sitter-bash-0.25.1"
    installer.state = state
    return installer


installer = installer_that(None)
status, lines = check_and_install_with_fixture("ned-box", version_reader(ALL_PINNED), installer)
check("when every library is at its pin, no install runs and one line says so",
      status == 0 and installer.state["installs"] == 0 and len(lines) == 1
      and "all 2 pinned" in lines[0], (status, lines))

installer = installer_that(None)
status, lines = check_and_install_with_fixture("ned-box", version_reader(ONE_MISSING, ALL_PINNED), installer)
check("a missing library is installed, and the one line names what was installed",
      status == 0 and installer.state["installs"] == 1 and len(lines) == 1
      and "tree-sitter-bash: wanted 0.25.1, found none" in lines[0], (status, lines))

installer = installer_that(None)
status, lines = check_and_install_with_fixture(
    "ned-box", version_reader({"tree-sitter": "0.24.0", "tree-sitter-bash": "0.25.1"}, ALL_PINNED),
    installer)
check("a library at another version counts as missing and is installed",
      status == 0 and installer.state["installs"] == 1 and "found 0.24.0" in lines[0], lines)

installer = installer_that("`pip ...` exited 1: no network")
status, lines = check_and_install_with_fixture("ned-box", version_reader(ONE_MISSING), installer)
text = "\n".join(lines)
check("a failed install exits 1, naming the machine, what is missing and what the install printed",
      status == 1 and "ned-box:" in lines[0] and "tree-sitter-bash: wanted 0.25.1, found none" in text
      and "no network" in text, lines)
check("on ned-box the by-hand command is the ssh form the user runs from the Mac, naming this interpreter "
      "and the list that was checked",
      lines[-1] == f"To install them by hand, run this command in a Terminal on your Mac: "
                   f"ssh nedlern@ned-box '{sys.executable} -m pip install --user "
                   f"--break-system-packages -r {FIXTURE}'", lines[-1])
status, lines = check_and_install_with_fixture("Neds-MacBook-Pro", version_reader(ONE_MISSING),
                                          installer_that("no network"))
check("on another machine the by-hand command is run there as it is",
      lines[-1].startswith(f"To install them by hand, run this command on Neds-MacBook-Pro: "
                           f"{sys.executable} -m pip install --user"), lines[-1])

status, lines = checker.check_and_install("ned-box", version_reader(ONE_MISSING),
                                         installer_that("nothing was installed"),
                                         requirements_file=FIXTURE, python_version=(3, 9, 6))
check("below Python 3.11 the last line gives no pip command, and says how to put a newer Python "
      "first on the PATH",
      status == 1 and "pip" not in lines[-1] and "Python 3.9.6" in lines[-1]
      and "on ned-box" in lines[-1] and "Homebrew" in lines[-1], lines[-1])

status, lines = check_and_install_with_fixture("ned-box", version_reader(ONE_MISSING),
                                          installer_that(None))
check("an install that succeeds but leaves a library missing exits 1, quoting what the install printed",
      status == 1 and "What the install printed: Successfully installed tree-sitter-bash-0.25.1"
      in lines, lines)

try:
    check_and_install_with_fixture("ned-box", version_reader(1), installer_that(None))
    raised = None
except RuntimeError as error:
    raised = error
check("a versions read that fails raises, quoting what it printed",
      raised is not None and "boom" in str(raised), raised)

def reader_and_pip(*answers):
    """A runner that answers versions reads with the next of answers, and any pip install with success."""
    reads = version_reader(*answers)
    installs = []

    def run(command, **kwargs):
        if "pip" in command:
            installs.append(command)
            return subprocess.CompletedProcess(command, 0, "Successfully installed", "")
        return reads(command, **kwargs)
    run.installs = installs
    return run


runner = reader_and_pip(ONE_MISSING, ALL_PINNED)
status, lines = checker.check_and_install("ned-box", runner, requirements_file=FIXTURE)
check("the default installer installs the list that was checked, not the real list",
      status == 0 and len(runner.installs) == 1 and runner.installs[0][-2:] == ["-r", str(FIXTURE)],
      (status, runner.installs))

status, lines = checker.check_and_install("ned-box", version_reader(dict(real_pins)), installer_that(None))
check("with no requirements_file, the real pinned list is the one checked",
      status == 0 and f"all {len(real_pins)} pinned" in lines[0], (status, lines))

versions = checker.installed_versions({"pip", "no-such-library-for-this-test"})
check("this python3's real installed versions are read, and an absent library reads as None",
      isinstance(versions.get("pip"), str) and versions["no-such-library-for-this-test"] is None,
      versions)

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
