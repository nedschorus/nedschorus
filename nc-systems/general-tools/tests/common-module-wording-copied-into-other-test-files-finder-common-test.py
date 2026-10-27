#!/usr/bin/env python3
"""Tests for nc-systems/general-tools/common-module-wording-copied-into-other-test-files-finder-common.py.

Each case builds a scratch git checkout holding a stand-in shared module and
test files that do or do not copy its wording, and asks the finder what it
names.

Run: python3 nc-systems/general-tools/tests/common-module-wording-copied-into-other-test-files-finder-common-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import atexit
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
# Before anything runs git: a run started with GIT_DIR set must still build its scratch checkouts where it says.
_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    REPOSITORY_ROOT / "scripts" / "git-redirecting-environment-removal-test-fixture.py")
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

_spec = importlib.util.spec_from_file_location(
    "common_module_wording_copied_into_other_test_files_finder_common",
    REPOSITORY_ROOT / "nc-systems" / "general-tools"
    / "common-module-wording-copied-into-other-test-files-finder-common.py")
finder = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(finder)

failures = 0
SCRATCH = Path(tempfile.mkdtemp(prefix="wording-copies-finder-test-"))
atexit.register(shutil.rmtree, SCRATCH, ignore_errors=True)


def check(name, condition, detail=None):
    global failures
    if condition:
        print(f"PASS  {name}")
    else:
        failures += 1
        print(f"FAIL  {name}: {detail!r}")


# Each piece below has the floor's seven words or more, except SHORT_LINE's six.
STAND_IN_MODULE = '''"""A stand-in shared module: this docstring has many more than seven words in it."""

STOP_LINE = "stop now and tell the user what both runs printed"
SHORT_LINE = "six words is under the floor"
SPLIT_LINE = ("the first half of this line and\\n"
              "the second  half of this line")


def rerun_line(command):
    """Return the rerun line; this docstring also has more than seven words."""
    if not command:
        raise TypeError("pass the command the agent ran, such as the program's own name")
    return f"run exactly {command} once more, and only once more, before you stop"
'''

def scratch_checkout(files, untracked=None):
    """A git checkout holding the stand-in module and files, each added to the index; untracked ones are not."""
    root = Path(tempfile.mkdtemp(dir=SCRATCH))
    subprocess.run(["git", "init", "--quiet", str(root)], check=True)
    for relative, text in {"tools/stand-in-wording-common.py": STAND_IN_MODULE, **files}.items():
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        (root / relative).write_text(text, encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    for relative, text in (untracked or {}).items():
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        (root / relative).write_text(text, encoding="utf-8")
    return root


def copies_in(files, untracked=None):
    root = scratch_checkout(files, untracked)
    return finder.common_module_wording_copies_in_other_test_files(root / "tools" / "stand-in-wording-common.py", root)


root = scratch_checkout({})
pieces = finder.common_module_wording_pieces(root / "tools" / "stand-in-wording-common.py")
check("the module's wording is its constants and its functions' literal pieces of seven words or more, "
      "whitespace made single, without docstrings or raise messages",
      pieces == {
          "stop now and tell the user what both runs printed": ["STOP_LINE"],
          "the first half of this line and the second half of this line": ["SPLIT_LINE"],
          "once more, and only once more, before you stop": ["rerun_line"],
      }, pieces)

found = copies_in({"tools/tests/caller-test.py": (
    'EXPECTED = "Then stop now and tell the user what both runs printed."\n')})
check("a test file holding a constant's wording is named with its path, line and the constant",
      found == [("tools/tests/caller-test.py", 1, "stop now and tell the user what both runs printed",
                 ["STOP_LINE"])], found)

found = copies_in({"scripts/caller-test.py": (
    'import sys\n\n'
    'def expected(command):\n'
    '    return (f"run exactly {command} once more, and only once more, "\n'
    '            "before you stop")\n')})
check("a test f-string holding a function's literal piece, its field outside the piece, is named "
      "at the literal's first line, with the function",
      found == [("scripts/caller-test.py", 4, "once more, and only once more, before you stop", ["rerun_line"])],
      found)

found = copies_in({"scripts/caller-test.py": (
    'EXPECTED = ("the first half of this line and  "\n'
    '            "the second\\n half of this line")\n')})
check("a copy split over implicitly joined literals, with other runs of whitespace, is still a copy",
      [copy[:2] for copy in found] == [("scripts/caller-test.py", 1)], found)

found = copies_in({"scripts/caller-test.py": (
    'def expected(empty):\n'
    '    return f"the first half of this line and {empty}the second half of this line"\n')})
check("a test f-string whose field falls inside the piece is not counted, even where the field "
      "could be empty",
      found == [], found)

found = copies_in({
    "tools/tests/stand-in-wording-common-test.py": 'PINNED = "stop now and tell the user what both runs printed"\n',
    "tools/caller.py": 'LINE = "stop now and tell the user what both runs printed"\n',
    "scripts/caller-test.py": ('"""Prose: stop now and tell the user what both runs printed."""\n'
                               'SHORT = "six words is under the floor"\n'),
})
check("the module's own test, a file that is not a test, a test's docstring and a piece under seven "
      "words are not counted", found == [], found)

found = copies_in({}, untracked={"scripts/caller-test.py": 'X = "stop now and tell the user what both runs printed"\n'})
check("a test file git does not track is not searched", found == [], found)

found = copies_in({"tools/tests/fixture.py": 'X = "stop now and tell the user what both runs printed"\n'})
check("a file in a tests directory counts as a test file whatever its name",
      [copy[0] for copy in found] == ["tools/tests/fixture.py"], found)

other_checkout = scratch_checkout({})
root = scratch_checkout({"scripts/caller-test.py": 'X = "stop now and tell the user what both runs printed"\n'})
os.environ["GIT_DIR"] = str(other_checkout / ".git")
try:
    found = finder.common_module_wording_copies_in_other_test_files(root / "tools" / "stand-in-wording-common.py", root)
finally:
    del os.environ["GIT_DIR"]
check("with GIT_DIR naming another checkout, the checkout given is still the one searched",
      [copy[0] for copy in found] == ["scripts/caller-test.py"], found)

line = finder.copied_wording_report_line(
    ("scripts/caller-test.py", 12, "stop now and tell the user what both runs printed", ["STOP_LINE"]))
check("the report line names the file and line, the wording, and the constant to call",
      line == ('scripts/caller-test.py:12 keeps its own copy of wording that STOP_LINE holds: '
               '"stop now and tell the user what both runs printed". '
               'Get it by calling STOP_LINE from the module instead.'), line)

not_a_checkout = Path(tempfile.mkdtemp(dir=SCRATCH))
(not_a_checkout / "stand-in-wording-common.py").write_text(STAND_IN_MODULE, encoding="utf-8")
try:
    outcome = finder.common_module_wording_copies_in_other_test_files(
        not_a_checkout / "stand-in-wording-common.py", not_a_checkout)
except subprocess.CalledProcessError as error:
    outcome = f"raised CalledProcessError, exit {error.returncode}"
check("a failing git ls-files raises to the caller instead of returning no copies",
      isinstance(outcome, str) and outcome.startswith("raised CalledProcessError"), outcome)

try:
    outcome = copies_in({"scripts/broken-test.py": "def broken(:\n"})
except SyntaxError as error:
    outcome = f"raised SyntaxError naming {Path(error.filename).name}"
check("a test file that does not parse raises to the caller, naming the file",
      outcome == "raised SyntaxError naming broken-test.py", outcome)

print(f"{failures} failure(s)" if failures else "all cases pass")
sys.exit(1 if failures else 0)
