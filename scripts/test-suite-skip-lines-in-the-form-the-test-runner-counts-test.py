#!/usr/bin/env python3
"""Fail when a tracked test suite reports a skipped test case in a form
scripts/run-all-test-suites.py does not count.

The test runner counts a skipped test case only as a printed line matching
`^SKIP\\s`. A suite that prints `SKIP:` or `SKIPPED`, or skips through
unittest's own skip machinery, still exits 0, so its skips vanish from every
report and the suite reads as a full pass.

Usage: test-suite-skip-lines-in-the-form-the-test-runner-counts-test.py [--checkout DIR]
  --checkout  scan this checkout's test suites only, without the self-check
              cases; default, the checkout this file is in, with them
"""
import importlib.util
import re
import subprocess
import sys
import tempfile
from pathlib import Path

_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().with_name(
        "git-redirecting-environment-removal-test-fixture.py"))
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

REPOSITORY = Path(__file__).resolve().parent.parent
SCAN_ONLY = sys.argv[1:2] == ["--checkout"]
if SCAN_ONLY:
    REPOSITORY = Path(sys.argv[2])

# A print or echo inside a string literal is a fixture another suite feeds to
# the test runner, so a quote just before it exempts the line.
UNCOUNTED_SKIP_PRINT = re.compile(
    r"""(?<!["'])\b(?:print\(\s*f?|echo\s+|printf\s+)["']?SKIP(?![ \t])""")
UNITTEST_SKIP = re.compile(
    r"""(?:(?<!["'])\.skipTest\(|(?<!["'@\w])@?unittest\.skip(?:If|Unless)?\()""")

PRINT_INSTEAD = ("print one line per skipped test case that opens SKIP and a space, "
                 "such as `SKIP  <test case>: <why it was skipped>`")


def uncounted_skip_forms(path, text):
    """Each line of one suite that skips in a form the test runner does not count."""
    found = []
    for number, line in enumerate(text.splitlines(), start=1):
        if UNCOUNTED_SKIP_PRINT.search(line):
            found.append(f"{path}:{number}: {line.strip()}\n"
                         f"  The test runner counts only a line matching ^SKIP\\s; "
                         f"{PRINT_INSTEAD}.")
        elif UNITTEST_SKIP.search(line):
            found.append(f"{path}:{number}: {line.strip()}\n"
                         f"  unittest's own skips print no SKIP line, so the test runner "
                         f"never counts them; skip the case in plain code and "
                         f"{PRINT_INSTEAD}.")
    return found


failures = []


def check(name, condition, detail=""):
    if condition:
        print(f"ok   {name}")
    else:
        print(f"FAIL {name}" + (f"\n{detail}" if detail else ""))
        failures.append(name)


if not SCAN_ONLY:
    CASES = [
        ("a SKIP line with a colon is refused", 'print("SKIP: a case: no tmux")', True),
        ("an f-string SKIP line with a colon is refused", "print(f'SKIP: {name}')", True),
        ("a SKIPPED line is refused", 'print("SKIPPED a case")', True),
        ("a shell SKIP line with a colon is refused", 'echo "SKIP: a case"', True),
        ("a printf SKIP line with no space is refused", "printf 'SKIP-%s\\n' case", True),
        # Built in two parts, or this file's own scan would refuse the line.
        ("unittest's skipTest is refused", "        self." + "skipTest('no tmux')", True),
        ("unittest's skip decorator is refused", "@unittest.skip('no tmux')", True),
        ("unittest's skipIf decorator is refused", "@unittest.skipIf(True, 'no tmux')", True),
        ("unittest's skipUnless decorator is refused", "@unittest.skipUnless(False, 'x')", True),
        ("a SKIP line with two spaces is accepted", 'print("SKIP  a case: no tmux")', False),
        ("a SKIP line with one space is accepted", "print(f\"SKIP {name}: {reason}\")", False),
        ("a shell SKIP line with a space is accepted", 'echo "SKIP  a case"', False),
        ("a fixture string holding a SKIPPED print is accepted",
         "             \"print('SKIPPED is not SKIP followed by a space')\\n\"", False),
        ("a name containing SKIP is accepted", 'SKIPPED = []', False),
        ("an environment variable containing SKIP is accepted",
         'environment["HANDOFF_SKIP_PROTECTION_AUDIT"] = "1"', False),
    ]
    for name, line, refused in CASES:
        check(name, bool(uncounted_skip_forms("x-test.py", line)) == refused,
              f"  line: {line}")

    named = uncounted_skip_forms("a/b-test.py", "x = 1\n" "print('SKIP: c')")
    check("the offending file, line number and line are named",
          len(named) == 1 and named[0].startswith("a/b-test.py:2: ") and "'SKIP: c'" in named[0],
          repr(named))



    def run_on_scratch_checkout(suite_text):
        with tempfile.TemporaryDirectory() as scratch:
            subprocess.run(["git", "init", "-q", scratch], check=True)
            (Path(scratch) / "a-test.py").write_text(suite_text)
            subprocess.run(["git", "-C", scratch, "add", "a-test.py"], check=True)
            return subprocess.run([sys.executable, __file__, "--checkout", scratch],
                                  capture_output=True, text=True)


    refused = run_on_scratch_checkout("x = 1\n" "print('SKIP: a case')\n")
    check("a checkout holding an uncounted skip line exits 1 and names the file and line",
          refused.returncode == 1 and "a-test.py:2: " in refused.stdout, refused.stdout + refused.stderr)
    accepted = run_on_scratch_checkout("print('SKIP  a case: no tmux')\n")
    check("a checkout whose skip lines are all counted exits 0",
          accepted.returncode == 0, accepted.stdout + accepted.stderr)

listed = subprocess.run(["git", "-C", str(REPOSITORY), "ls-files", "--", "*-test.py", "*-test.sh"],
                        capture_output=True, text=True)
check("git lists the test suites", listed.returncode == 0 and listed.stdout.strip(),
      listed.stderr)
offences = []
for relative in listed.stdout.splitlines():
    offences += uncounted_skip_forms(
        relative, (REPOSITORY / relative).read_text(encoding="utf-8", errors="replace"))
check("every tracked test suite prints skips in the form the test runner counts",
      not offences, "\n".join(offences))

if failures:
    print(f"{len(failures)} of the checks above failed.")
    sys.exit(1)
print("all cases passed")
