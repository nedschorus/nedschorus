#!/usr/bin/env python3
"""Tests for nc-systems/general-tools/compiled-python-libraries-pinned-requirements-install-common.py.

The importer, the installer, pip and the clock are test doubles, so no
library is installed. The shell reader's own tests run the same code through
the reader's load_parser.

Run: python3 nc-systems/general-tools/tests/compiled-python-libraries-pinned-requirements-install-common-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]

_spec = importlib.util.spec_from_file_location(
    "compiled_python_libraries_pinned_requirements_install_common",
    REPOSITORY_ROOT / "nc-systems" / "general-tools"
    / "compiled-python-libraries-pinned-requirements-install-common.py")
install = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(install)

failures = 0


def check(name, condition, detail=None):
    global failures
    if condition:
        print(f"PASS  {name}")
    else:
        failures += 1
        print(f"FAIL  {name}: {detail!r}")


def libraries_after(installs_needed):
    """An importer that fails until the installer has run installs_needed times, and that installer."""
    state = {"installs": 0, "forgotten": 0}

    def importer():
        if state["installs"] < installs_needed:
            raise ImportError("No module named 'tree_sitter'")
        return "the libraries"

    def installer():
        state["installs"] += 1
        return "installed"

    def forget_loaded_copies():
        state["forgotten"] += 1
    return importer, installer, forget_loaded_copies, state


def failing_installer(state, error_class=install.CompiledPythonLibrariesUnavailable):
    def installer():
        state["installs"] += 1
        raise error_class("pip: network is unreachable")
    return installer


def install_then_import(state_directory, importer, installer, forget, now, fresh_process=False,
                        **error_classes):
    try:
        return install.compiled_python_libraries_install_then_import(
            importer, installer, lambda: now, lambda: fresh_process, state_directory, forget,
            **error_classes), None
    except install.CompiledPythonLibrariesUnavailable as error:
        return None, error


with tempfile.TemporaryDirectory() as scratch:
    state_directory = Path(scratch) / "state"
    record = state_directory / install.INSTALL_FAILURE_FILE_NAME

    importer, installer, forget, state = libraries_after(1)
    result, raised = install_then_import(state_directory, importer, installer, forget, 1000.0)
    check("a missing library is installed once, then imported",
          result == "the libraries" and raised is None and state["installs"] == 1, (result, state))
    check("this process's loaded copies are forgotten before each import under the lock",
          state["forgotten"] == 2, state)

    importer, installer, forget, state = libraries_after(0)
    result, raised = install_then_import(state_directory, importer, installer, forget, 1000.0)
    check("a library another caller installed meanwhile is imported without an install",
          result == "the libraries" and state["installs"] == 0, state)

    importer, _installer, forget, state = libraries_after(99)
    result, raised = install_then_import(state_directory, importer, failing_installer(state), forget,
                                         1000.0)
    check("a failed install raises CompiledPythonLibrariesUnavailable with what the install printed",
          raised is not None and "network is unreachable" in raised.install_output, raised)
    check("a failed install is recorded",
          record.is_file() and "network is unreachable" in record.read_text(encoding="utf-8"))
    os.utime(record, (1000.0, 1000.0))

    importer, _installer, forget, state = libraries_after(99)
    result, raised = install_then_import(state_directory, importer, failing_installer(state), forget,
                                         1000.0 + 60)
    check("within ten minutes of a failed install, no install runs and the recorded output is given",
          state["installs"] == 0 and raised is not None
          and "network is unreachable" in raised.install_output, (state, raised))

    importer, installer, forget, state = libraries_after(1)
    result, raised = install_then_import(state_directory, importer, installer, forget,
                                         1000.0 + install.INSTALL_RETRY_SECONDS + 1)
    check("after ten minutes the install runs again, and success clears the record",
          result == "the libraries" and state["installs"] == 1 and not record.exists(),
          (state, record.exists()))

    def importer_never():
        raise ImportError("No module named 'tree_sitter_bash'")
    result, raised = install_then_import(state_directory, importer_never, lambda: "installed",
                                         lambda: None, 5000.0, fresh_process=False)
    check("an install that leaves the import failing in every process raises "
          "CompiledPythonLibrariesUnavailable and is recorded",
          raised is not None and "importing still fails" in raised.install_output
          and not isinstance(raised, install.CompiledPythonLibrariesInstalledForANewProcess)
          and record.is_file(), raised)
    os.utime(record, (5000.0, 5000.0))

    result, raised = install_then_import(state_directory, importer_never, lambda: "installed",
                                         lambda: None, 5000.0 + install.INSTALL_RETRY_SECONDS + 1,
                                         fresh_process=True)
    check("an install that a new process can import raises "
          "CompiledPythonLibrariesInstalledForANewProcess and clears the older failure record",
          isinstance(raised, install.CompiledPythonLibrariesInstalledForANewProcess)
          and not record.exists(), raised)

    class CallerUnavailable(install.CompiledPythonLibrariesUnavailable):
        pass

    class CallerInstalledForANewProcess(CallerUnavailable):
        pass
    importer, _installer, forget, state = libraries_after(99)
    result, raised = install_then_import(
        state_directory, importer, failing_installer(state, CallerUnavailable), forget, 6000.0,
        unavailable_error=CallerUnavailable,
        installed_for_new_process_error=CallerInstalledForANewProcess)
    check("a caller's own error class is raised and recorded",
          type(raised) is CallerUnavailable and record.is_file(), raised)
    os.utime(record, (6000.0, 6000.0))
    result, raised = install_then_import(
        state_directory, importer_never, lambda: "installed", lambda: None, 6060.0,
        unavailable_error=CallerUnavailable,
        installed_for_new_process_error=CallerInstalledForANewProcess)
    check("a recorded failure is raised as the caller's own error class",
          type(raised) is CallerUnavailable and "network is unreachable" in raised.install_output,
          raised)
    record.unlink()
    result, raised = install_then_import(
        state_directory, importer_never, lambda: "installed", lambda: None, 6100.0,
        fresh_process=True, unavailable_error=CallerUnavailable,
        installed_for_new_process_error=CallerInstalledForANewProcess)
    check("the caller's own new-process error class is raised",
          type(raised) is CallerInstalledForANewProcess, raised)

    blocking_file = Path(scratch) / "a-file-not-a-directory"
    blocking_file.write_text("x")
    importer, installer, forget, state = libraries_after(1)
    result, raised = install_then_import(blocking_file / "state", importer, installer, forget, 9000.0)
    check("a state directory that cannot be made raises CompiledPythonLibrariesUnavailable saying so",
          raised is not None and "install lock" in raised.install_output and state["installs"] == 0,
          (raised, state))

    read_only = Path(scratch) / "read-only-state"
    read_only.mkdir()
    (read_only / install.INSTALL_LOCK_FILE_NAME).write_text("")
    read_only.chmod(0o555)
    importer, _installer, forget, state = libraries_after(99)
    try:
        result, raised = install_then_import(read_only, importer, failing_installer(state), forget,
                                             9000.0)
    except OSError as error:
        raised = error
    check("a failed install whose record cannot be written still raises "
          "CompiledPythonLibrariesUnavailable",
          isinstance(raised, install.CompiledPythonLibrariesUnavailable) and state["installs"] == 1,
          (raised, state))
    read_only.chmod(0o755)

    import fcntl
    import threading
    held = Path(scratch) / "held-state"
    held.mkdir()
    # The caller runs in a child with a timeout, so a caller that waits too long prints FAIL here
    # instead of hanging the suite. The child's deadline is argv[3] seconds; its importer succeeds,
    # as it does once another process's install has finished.
    held_lock_caller_code = (
        "import importlib.util, json, sys, time\n"
        "from pathlib import Path\n"
        "spec = importlib.util.spec_from_file_location('m', sys.argv[1])\n"
        "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
        "m.INSTALL_LOCK_WAIT_SECONDS = float(sys.argv[3])\n"
        "installs = []\n"
        "started = time.monotonic()\n"
        "try:\n"
        "    result = m.compiled_python_libraries_install_then_import(lambda: 'the libraries',\n"
        "        lambda: installs.append(1), lambda: 9000.0, lambda: False, Path(sys.argv[2]), lambda: None)\n"
        "    outcome = {'result': result, 'raised': None}\n"
        "except m.CompiledPythonLibrariesUnavailable as error:\n"
        "    outcome = {'raised': error.install_output, 'class': type(error).__name__}\n"
        "outcome.update(installs=len(installs), elapsed=time.monotonic() - started)\n"
        "print(json.dumps(outcome))\n")

    def caller_while_lock_held(wait_seconds, release_after=None):
        other_install = open(held / install.INSTALL_LOCK_FILE_NAME, "w")
        fcntl.flock(other_install, fcntl.LOCK_EX)
        if release_after is not None:
            threading.Timer(release_after, other_install.close).start()
        try:
            child = subprocess.run([sys.executable, "-c", held_lock_caller_code, _spec.origin, str(held),
                                    str(wait_seconds)], capture_output=True, text=True, timeout=20)
            return json.loads(child.stdout) if child.returncode == 0 else {"child": child.stderr[-500:]}
        except subprocess.TimeoutExpired:
            return {"child": "waited for the lock until the 20 s timeout"}
        finally:
            if release_after is None:
                other_install.close()

    outcome = caller_while_lock_held(1)
    check("when another process still holds the install lock at the deadline, the caller gives up: "
          "CompiledPythonLibrariesInstallAlreadyRunning, saying an install is still running, no install, "
          "no failure recorded",
          outcome.get("class") == "CompiledPythonLibrariesInstallAlreadyRunning"
          and "still running" in outcome.get("raised", "") and outcome.get("installs") == 0
          and 1 <= outcome.get("elapsed", 0) < 10
          and not (held / install.INSTALL_FAILURE_FILE_NAME).exists(), outcome)
    # The other install finishes 2 s after it starts; the child's own start-up uses part of that.
    outcome = caller_while_lock_held(15, release_after=2)
    check("when another process's install finishes within the deadline, the caller waits, then "
          "imports what that install put in place, without installing",
          outcome.get("result") == "the libraries" and outcome.get("installs") == 0
          and 0.5 <= outcome.get("elapsed", 0) < 10, outcome)
    check("the guards' deadline stays well under Claude Code's 30-second hook timeout",
          0 < install.INSTALL_LOCK_WAIT_SECONDS <= 20, install.INSTALL_LOCK_WAIT_SECONDS)


def runner_exiting(returncode, stdout="", stderr=""):
    def run(command, **kwargs):
        run.command, run.kwargs = command, kwargs
        return subprocess.CompletedProcess(command, returncode, stdout, stderr)
    return run


run = runner_exiting(0, "Successfully installed tree-sitter-0.25.2")
printed = install.pinned_requirements_pip_install(8, run)
check("the install runs pip per user, from the pinned requirements file, within the given timeout",
      run.command == [sys.executable, "-m", "pip", "install", "--user", "--break-system-packages",
                      "--disable-pip-version-check", "--quiet", "-r",
                      str(install.PINNED_REQUIREMENTS_FILE)]
      and run.kwargs["timeout"] == 8 and run.kwargs["stdin"] == subprocess.DEVNULL
      and "Successfully installed" in printed, (run.command, run.kwargs))
check("the pinned requirements file sits beside the module",
      install.PINNED_REQUIREMENTS_FILE.is_file()
      and install.PINNED_REQUIREMENTS_FILE.name == "compiled-python-libraries-pinned-requirements.txt")
try:
    install.pinned_requirements_pip_install(8, runner_exiting(1, "", "ERROR: No matching distribution"))
    raised = None
except install.CompiledPythonLibrariesUnavailable as error:
    raised = error
check("pip exiting nonzero raises CompiledPythonLibrariesUnavailable with its output",
      raised is not None and "No matching distribution" in raised.install_output
      and "exited 1" in raised.install_output, raised)
try:
    install.pinned_requirements_pip_install(8, runner_exiting(1))
    raised = None
except install.CompiledPythonLibrariesUnavailable as error:
    raised = error
check("pip exiting nonzero with no output says so",
      raised is not None and "(no output)" in raised.install_output, raised)


def runner_timing_out(command, **kwargs):
    raise subprocess.TimeoutExpired(command, kwargs["timeout"])


try:
    install.pinned_requirements_pip_install(8, runner_timing_out)
    raised = None
except install.CompiledPythonLibrariesUnavailable as error:
    raised = error
check("pip timing out raises CompiledPythonLibrariesUnavailable saying it did not finish",
      raised is not None and "did not finish" in raised.install_output, raised)

import shlex
where, command = install.pinned_requirements_by_hand_install_command(
    "ned-box", Path("/tmp/a dir/it's-requirements.txt"))
ssh_words = shlex.split(command)
check("the ssh form quotes the install so the remote shell reads the same words, a path with a "
      "space and a quote included",
      where == "in a Terminal on your Mac" and ssh_words[:2] == ["ssh", "nedlern@ned-box"]
      and len(ssh_words) == 3
      and shlex.split(ssh_words[2]) == [sys.executable, "-m", "pip", "install", "--user",
                                        "--break-system-packages", "-r", "/tmp/a dir/it's-requirements.txt"],
      (where, command))
where, command = install.pinned_requirements_by_hand_install_command(
    "Neds-MacBook-Pro", Path("/tmp/a dir/it's-requirements.txt"))
check("the local form is quoted for the user's shell",
      where == "on Neds-MacBook-Pro"
      and shlex.split(command)[-1] == "/tmp/a dir/it's-requirements.txt", (where, command))

print("all cases passed" if not failures else f"{failures} case(s) failed")
sys.exit(1 if failures else 0)
