#!/usr/bin/env python3
"""Fail when a Python file in the checkout breaks one of the Ruff rules in RULES.

Runs Ruff's rules in RULES, with Ruff's own settings for them, over every `.py`
file git tracks or would add, so a hit fails the author's own test run. Ruff's
S110 flags a bare `except`, `except Exception` and `except BaseException` whose
body is only `pass`; an `except` that names a narrower exception is left alone.
The F rules find unused imports and variables, an unused name defined again,
an f-string with no placeholders, and an undefined name, which fails only when
the line runs. A false F821 hit is marked `# noqa: F821` with its reason.

Ruff is pinned in
nn-systems/general-tools/python-libraries-pinned-requirements.txt.
When the python3 running this suite cannot run Ruff, the suite installs the
pinned file per user, as the hooks do. When that install fails, the suite
prints what the install printed and the command that installs it by hand,
and fails.

Run: python3 scripts/python-files-pass-selected-ruff-rules-test.py
"""

import importlib.util
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().with_name("git-redirecting-environment-removal-test-fixture.py"))
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

REPOSITORY = Path(__file__).resolve().parent.parent

_pinned_libraries_install_spec = importlib.util.spec_from_file_location(
    "python_libraries_pinned_requirements_install_if_missing_then_import_common",
    REPOSITORY / "nn-systems" / "general-tools"
    / "python-libraries-pinned-requirements-install-if-missing-then-import-common.py")
pinned_libraries_install = importlib.util.module_from_spec(_pinned_libraries_install_spec)
_pinned_libraries_install_spec.loader.exec_module(pinned_libraries_install)

# The suite runs by hand or from the suite runner, not inside a hook, so a slow download may finish.
INSTALL_TIMEOUT_SECONDS = 600
RUFF_TIMEOUT_SECONDS = 300
RUFF = [sys.executable, "-m", "ruff"]

# Each rule's fix, printed after the hits when that rule has one.
FIX_INSTRUCTIONS = {
    "S110": (
        "Each S110 `except` above swallows a failure: its body is only `pass`, so nobody sees the "
        "failure.\n"
        "Where the failure matters to whoever acts on the program's output, report it: print what "
        "failed and exit nonzero, or raise it to a caller that does.\n"
        "Where the failure is expected and harmless, narrow the `except` to the exception you "
        "expect, with a comment giving the reason."),
    "F401": ("Remove each F401 import above that nothing uses; first grep for a program that "
             "loads the file by path and reads the name from it."),
    "F811": "Remove each F811 import or definition above that repeats an earlier, unused one.",
    "F841": ("Remove each F841 variable above that is never read; keep the call that assigns it "
             "when the call has an effect."),
    "F541": "Drop the `f` prefix from each F541 string above, which has no placeholder.",
    "F821": (
        "Define each F821 name above before the line that uses it, or quote an annotation that "
        "names a class defined later in the file.\n"
        "Where you have read the code and the name is always bound when the line runs, such as a "
        "lambda called inside the `except` that binds its name, end the line with "
        "`# noqa: F821` and the reason."),
}
RULES = tuple(FIX_INSTRUCTIONS)

failures = []


def check(name, condition, detail=""):
    print(("PASS " if condition else "FAIL ") + name)
    if not condition:
        print(f"    {detail}")
        failures.append(name)


def ruff_runs(runner):
    """Return (whether Ruff runs under this python3, what the attempt printed)."""
    try:
        completed = runner([*RUFF, "--version"], capture_output=True, text=True,
                           timeout=RUFF_TIMEOUT_SECONDS, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError) as error:
        return False, str(error)
    return completed.returncode == 0, (completed.stdout + completed.stderr).strip()


def ruff_ready_or_failure(runner, installer, host):
    """Return None when Ruff runs, installing the pinned file first if needed; else what failed."""
    if ruff_runs(runner)[0]:
        return None
    try:
        install_output = installer()
    except pinned_libraries_install.PythonLibrariesPinnedRequirementsInstallOrImportFailed as error:
        install_output = error.install_output
    runs, printed = ruff_runs(runner)
    if runs:
        return None
    where, command = pinned_libraries_install.pinned_requirements_by_hand_install_command(host)
    return (f"Ruff does not run under {sys.executable} after installing the pinned requirements "
            f"file, so no file was checked for the rules {', '.join(RULES)}.\n"
            f"What the install printed: {install_output or '(nothing)'}\n"
            f"What `{' '.join(RUFF)} --version` printed: {printed or '(nothing)'}\n"
            f"To install Ruff by hand, run this command {where}: {command}")


def python_files(checkout, runner):
    """Return the `.py` files git tracks or would add in checkout, as paths relative to it."""
    completed = runner(["git", "-C", str(checkout), "ls-files", "-z", "--cached", "--others",
                        "--exclude-standard", "--", "*.py"],
                       capture_output=True, text=True, check=True, stdin=subprocess.DEVNULL)
    # --cached also lists a tracked file deleted from the working tree, which Ruff cannot read.
    return sorted({name for name in completed.stdout.split("\0")
                   if name and (checkout / name).is_file()})


def ruff_report(checkout, files, runner):
    """Return (exit code, output) of Ruff's check of RULES on files; 0 none found, 1 found, else an error."""
    if not files:
        return 0, ""
    # --isolated reads no Ruff settings file, so only RULES run, with Ruff's own settings for them.
    # --no-cache keeps Ruff from writing a cache directory into the checkout.
    completed = runner([*RUFF, "check", "--isolated", "--no-cache", "--select", ",".join(RULES),
                        "--output-format", "concise", "--", *files],
                       cwd=checkout, capture_output=True, text=True,
                       timeout=RUFF_TIMEOUT_SECONDS, stdin=subprocess.DEVNULL)
    return completed.returncode, (completed.stdout + completed.stderr).strip()


def run_failure_cases():
    """The suite must fail, not pass, when Ruff cannot be installed or Ruff itself fails."""

    def ruff_never_runs(command, **_options):
        return subprocess.CompletedProcess(command, 1, "", "No module named ruff")

    def failing_installer():
        raise pinned_libraries_install.PythonLibrariesPinnedRequirementsInstallOrImportFailed(
            "ERROR: No matching distribution found for ruff==0.17.0")

    failure = ruff_ready_or_failure(ruff_never_runs, failing_installer, "ned-box")
    check("a failed install of Ruff is reported, with what the install printed and the by-hand "
          "command",
          failure is not None and "No matching distribution" in failure
          and "No module named ruff" in failure and "ssh nedlern@ned-box" in failure, repr(failure))

    calls = []

    def ruff_runs_after_install(command, **_options):
        return subprocess.CompletedProcess(command, 0 if calls else 1, "ruff 0.17.0", "")

    failure = ruff_ready_or_failure(ruff_runs_after_install, lambda: calls.append("install") or "",
                                    "ned-box")
    check("Ruff missing at first is installed, and then counts as ready",
          failure is None and calls == ["install"], repr((failure, calls)))

    def ruff_errors(command, **_options):
        return subprocess.CompletedProcess(command, 2, "", "error: Failed to parse")

    status, output = ruff_report(REPOSITORY, ["a.py"], ruff_errors)
    check("an error exit from Ruff is passed on, not taken as no hits",
          status == 2 and "Failed to parse" in output, repr((status, output)))

    verdict = repository_verdict(status, output, 1)
    check("an error exit from Ruff on the checkout fails the suite, naming the exit status",
          verdict[1] is False and "Ruff exited 2: error: Failed to parse" in verdict[2],
          repr(verdict))
    verdict = repository_verdict(1, "a.py:3:1: S110 `try`-`except`-`pass` detected", 1)
    check("an S110 hit in the checkout fails the suite, with how to fix it and no other rule's fix",
          verdict[1] is False and "a.py:3:1: S110" in verdict[2]
          and FIX_INSTRUCTIONS["S110"].split("\n")[0] in verdict[2]
          and FIX_INSTRUCTIONS["F401"] not in verdict[2],
          repr(verdict))


# Each fixture file, and the one hit Ruff, as this suite runs it, must report in it; None for none.
FIXTURES = {
    "swallowed.py": ("try:\n    import json  # noqa: F401\nexcept Exception:\n    pass\n",
                     "swallowed.py:3:1: S110"),
    "reported.py": ("import sys\ntry:\n    import json  # noqa: F401\nexcept Exception as error:\n"
                    "    print(error, file=sys.stderr)\n", None),
    "narrowed.py": ("try:\n    import json  # noqa: F401\nexcept ImportError:\n"
                    "    pass  # json is optional\n", None),
    "unused_import.py": ("import os\n", "unused_import.py:1:8: F401"),
    "defined_again.py": ("import json\nimport json\nprint(json)\n", "defined_again.py:2:8: F811"),
    "unused_variable.py": ("def f():\n    value = 1\n", "unused_variable.py:2:5: F841"),
    "placeholderless.py": ('print(f"text")\n', "placeholderless.py:1:7: F541"),
    "undefined.py": ("print(missing)\n", "undefined.py:1:7: F821"),
    "undefined_marked.py": ("print(missing)  # noqa: F821 bound by the program that runs it\n", None),
}


def run_fixture_cases():
    """Ruff, as this suite runs it, flags each rule's hit, and passes a reported or narrowed `except` and a noqa line."""
    with tempfile.TemporaryDirectory(
            prefix="python-files-pass-selected-ruff-rules-test-") as directory:
        fixture = Path(directory)
        for name, (text, _hit) in FIXTURES.items():
            (fixture / name).write_text(text, encoding="utf-8")
        status, output = ruff_report(fixture, list(FIXTURES), subprocess.run)
        for name, (_text, hit) in FIXTURES.items():
            hits = [line for line in output.splitlines() if line.startswith(f"{name}:")]
            if hit is None:
                check(f"{name} has no hit", status == 1 and not hits, repr((status, output)))
            else:
                check(f"{name} has the hit {hit.split(': ')[1]}, and only it",
                      status == 1 and len(hits) == 1 and hits[0].startswith(hit),
                      repr((status, output)))


def repository_verdict(status, output, file_count):
    """Return (case name, passed, detail) for Ruff's exit status and output on the checkout."""
    rules = ", ".join(RULES)
    if status == 0:
        return f"the checkout's {file_count} Python files pass Ruff's rules {rules}", True, ""
    if status == 1:
        fixes = "\n".join(fix for rule, fix in FIX_INSTRUCTIONS.items() if f": {rule} " in output)
        return (f"the checkout's Python files pass Ruff's rules {rules}", False,
                f"{output}\n{fixes}".replace("\n", "\n    "))
    return ("Ruff checks the checkout's Python files", False,
            f"Ruff exited {status}: {output or '(no output)'}".replace("\n", "\n    "))


def run_repository_check():
    files = python_files(REPOSITORY, subprocess.run)
    check("the checkout has Python files to check", len(files) > 0, repr(files))
    check(*repository_verdict(*ruff_report(REPOSITORY, files, subprocess.run), len(files)))


def main():
    run_failure_cases()

    def installer():
        return pinned_libraries_install.pinned_requirements_pip_install(INSTALL_TIMEOUT_SECONDS)

    failure = ruff_ready_or_failure(subprocess.run, installer, socket.gethostname().split(".")[0])
    check("Ruff runs under this python3", failure is None,
          (failure or "").replace("\n", "\n    "))
    if failure is None:
        run_fixture_cases()
        run_repository_check()
    if failures:
        print(f"{len(failures)} case(s) failed.")
        return 1
    print("all cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
