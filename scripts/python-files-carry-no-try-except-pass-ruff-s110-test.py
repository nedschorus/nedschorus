#!/usr/bin/env python3
"""Fail when a Python file in the checkout has an `except` whose body is only `pass`.

Runs Ruff's rule S110 (try-except-pass), with Ruff's own settings for the rule,
over every `.py` file git tracks or would add, so a swallowed exception fails
the author's own test run. Ruff's S110 flags a bare `except`, `except
Exception` and `except BaseException`; an `except` that names a narrower
exception is left alone.

Ruff is pinned in
nc-systems/general-tools/python-libraries-pinned-requirements.txt.
When the python3 running this suite cannot run Ruff, the suite installs the
pinned file per user, as the hooks do. When that install fails, the suite
prints what the install printed and the command that installs it by hand,
and fails.

Run: python3 scripts/python-files-carry-no-try-except-pass-ruff-s110-test.py
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
    REPOSITORY / "nc-systems" / "general-tools"
    / "python-libraries-pinned-requirements-install-if-missing-then-import-common.py")
pinned_libraries_install = importlib.util.module_from_spec(_pinned_libraries_install_spec)
_pinned_libraries_install_spec.loader.exec_module(pinned_libraries_install)

# The suite runs by hand or from the suite runner, not inside a hook, so a slow download may finish.
INSTALL_TIMEOUT_SECONDS = 600
RUFF_TIMEOUT_SECONDS = 300
RUFF = [sys.executable, "-m", "ruff"]

FIX_INSTRUCTIONS = (
    "Each `except` above swallows a failure: its body is only `pass`, so nobody sees the failure.\n"
    "Where the failure matters to whoever acts on the program's output, report it: print what "
    "failed and exit nonzero, or raise it to a caller that does.\n"
    "Where the failure is expected and harmless, narrow the `except` to the exception you expect, "
    "with a comment giving the reason.")

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
            f"file, so no file was checked for S110.\n"
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


def s110_report(checkout, files, runner):
    """Return (exit code, output) of Ruff's S110 check on files; 0 none found, 1 found, else an error."""
    if not files:
        return 0, ""
    # --isolated reads no Ruff settings file, so only S110 runs, with Ruff's own settings for it.
    # --no-cache keeps Ruff from writing a cache directory into the checkout.
    completed = runner([*RUFF, "check", "--isolated", "--no-cache", "--select", "S110",
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

    status, output = s110_report(REPOSITORY, ["a.py"], ruff_errors)
    check("an error exit from Ruff is passed on, not taken as no hits",
          status == 2 and "Failed to parse" in output, repr((status, output)))

    verdict = repository_verdict(status, output, 1)
    check("an error exit from Ruff on the checkout fails the suite, naming the exit status",
          verdict[1] is False and "Ruff exited 2: error: Failed to parse" in verdict[2],
          repr(verdict))
    verdict = repository_verdict(1, "a.py:3:1: S110", 1)
    check("an S110 hit in the checkout fails the suite, with how to fix it",
          verdict[1] is False and "a.py:3:1: S110" in verdict[2]
          and FIX_INSTRUCTIONS.split("\n")[0] in verdict[2],
          repr(verdict))


def run_fixture_cases():
    """Ruff, as this suite runs it, flags a swallowed exception and passes a reported or narrowed one."""
    with tempfile.TemporaryDirectory(
            prefix="python-files-carry-no-try-except-pass-ruff-s110-test-") as directory:
        fixture = Path(directory)
        (fixture / "swallowed.py").write_text(
            "try:\n    import json\nexcept Exception:\n    pass\n", encoding="utf-8")
        (fixture / "reported.py").write_text(
            "import sys\ntry:\n    import json\nexcept Exception as error:\n"
            "    print(error, file=sys.stderr)\n", encoding="utf-8")
        (fixture / "narrowed.py").write_text(
            "try:\n    import json\nexcept ImportError:\n    pass  # json is optional\n",
            encoding="utf-8")
        status, output = s110_report(fixture, ["swallowed.py", "reported.py", "narrowed.py"],
                                     subprocess.run)
        check("an `except Exception` whose body is only `pass` is flagged, and only it",
              status == 1 and "swallowed.py:3:1: S110" in output
              and "reported.py" not in output and "narrowed.py" not in output,
              repr((status, output)))


def repository_verdict(status, output, file_count):
    """Return (case name, passed, detail) for Ruff's exit status and output on the checkout."""
    if status == 0:
        return f"no `except` swallows a failure in the checkout's {file_count} Python files", True, ""
    if status == 1:
        return ("no `except` swallows a failure in the checkout's Python files", False,
                f"{output}\n{FIX_INSTRUCTIONS}".replace("\n", "\n    "))
    return ("Ruff checks the checkout's Python files", False,
            f"Ruff exited {status}: {output or '(no output)'}".replace("\n", "\n    "))


def run_repository_check():
    files = python_files(REPOSITORY, subprocess.run)
    check("the checkout has Python files to check", len(files) > 0, repr(files))
    check(*repository_verdict(*s110_report(REPOSITORY, files, subprocess.run), len(files)))


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
