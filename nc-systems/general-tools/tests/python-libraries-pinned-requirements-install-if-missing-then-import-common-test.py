#!/usr/bin/env python3
"""Tests for nc-systems/general-tools/python-libraries-pinned-requirements-install-if-missing-then-import-common.py.

The importer, the installer, pip and the clock are test doubles, so no
library is installed. The shell reader's own tests run the same code through
the reader's load_parser.

Run: python3 nc-systems/general-tools/tests/python-libraries-pinned-requirements-install-if-missing-then-import-common-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import ast
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import types
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]

_spec = importlib.util.spec_from_file_location(
    "python_libraries_pinned_requirements_install_if_missing_then_import_common",
    REPOSITORY_ROOT / "nc-systems" / "general-tools"
    / "python-libraries-pinned-requirements-install-if-missing-then-import-common.py")
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


HALF_IMPORTED_PACKAGE = "nedschorus_install_test_half_imported_package"
# Shares the package name as a prefix, so a drop that matched by prefix would remove it too.
UNRELATED_MODULE = HALF_IMPORTED_PACKAGE + "_x"


def libraries_after(installs_needed):
    """An importer that fails until the installer has run installs_needed times, that installer,
    and the package names to pass.

    Each failed import leaves a submodule of the package loaded, as a real import that fails
    partway does; the importer counts the imports that find one still loaded.
    """
    state = {"installs": 0, "imports": 0, "stale_submodule_seen": 0}

    def leave_submodule_loaded():
        sys.modules[HALF_IMPORTED_PACKAGE + ".submodule"] = types.ModuleType(
            HALF_IMPORTED_PACKAGE + ".submodule")

    def importer():
        state["imports"] += 1
        if HALF_IMPORTED_PACKAGE + ".submodule" in sys.modules:
            state["stale_submodule_seen"] += 1
        if state["installs"] < installs_needed:
            leave_submodule_loaded()
            raise ImportError("No module named 'tree_sitter'")
        return "the libraries"

    def installer():
        state["installs"] += 1
        return "installed"

    leave_submodule_loaded()
    sys.modules[UNRELATED_MODULE] = types.ModuleType(UNRELATED_MODULE)
    return importer, installer, (HALF_IMPORTED_PACKAGE,), state


def failing_installer(state, error_class=install.PythonLibrariesPinnedRequirementsInstallOrImportFailed):
    def installer():
        state["installs"] += 1
        raise error_class("pip: network is unreachable")
    return installer


def install_then_import(state_directory, importer, installer, package_names, now, fresh_process=False,
                        **error_classes):
    try:
        return install.python_libraries_pinned_requirements_install_if_missing_then_import(
            importer, installer, lambda: now, lambda: fresh_process, state_directory, package_names,
            **error_classes), None
    except install.PythonLibrariesPinnedRequirementsInstallOrImportFailed as error:
        return None, error


with tempfile.TemporaryDirectory() as scratch:
    state_directory = Path(scratch) / "state"
    record = state_directory / install.INSTALL_FAILURE_FILE_NAME

    importer, installer, package_names, state = libraries_after(1)
    result, raised = install_then_import(state_directory, importer, installer, package_names, 1000.0)
    check("a missing library is installed once, then imported",
          result == "the libraries" and raised is None and state["installs"] == 1, (result, state))
    check("a half-imported package's submodules are dropped before each import under the lock",
          state["imports"] == 2 and state["stale_submodule_seen"] == 0, state)
    check("modules outside the named packages stay loaded, one whose name starts with a named package's name included", UNRELATED_MODULE in sys.modules)

    importer, installer, package_names, state = libraries_after(0)
    result, raised = install_then_import(state_directory, importer, installer, package_names, 1000.0)
    check("a library another caller installed meanwhile is imported without an install",
          result == "the libraries" and state["installs"] == 0, state)

    importer, _installer, package_names, state = libraries_after(99)
    result, raised = install_then_import(state_directory, importer, failing_installer(state), package_names,
                                         1000.0)
    check("a failed install raises PythonLibrariesPinnedRequirementsInstallOrImportFailed with what the install printed",
          raised is not None and "network is unreachable" in raised.install_output, raised)
    check("a failed install is recorded",
          record.is_file() and "network is unreachable" in record.read_text(encoding="utf-8"))
    os.utime(record, (1000.0, 1000.0))

    importer, _installer, package_names, state = libraries_after(99)
    result, raised = install_then_import(state_directory, importer, failing_installer(state), package_names,
                                         1000.0 + 60)
    check("within ten minutes of a failed install, no install runs and the recorded output is given",
          state["installs"] == 0 and raised is not None
          and "network is unreachable" in raised.install_output, (state, raised))

    importer, installer, package_names, state = libraries_after(1)
    result, raised = install_then_import(state_directory, importer, installer, package_names,
                                         1000.0 + install.INSTALL_RETRY_SECONDS + 1)
    check("after ten minutes the install runs again, and success clears the record",
          result == "the libraries" and state["installs"] == 1 and not record.exists(),
          (state, record.exists()))

    def importer_never():
        raise ImportError("No module named 'tree_sitter_bash'")
    result, raised = install_then_import(state_directory, importer_never, lambda: "installed",
                                         (), 5000.0, fresh_process=False)
    check("an install that leaves the import failing in every process raises "
          "PythonLibrariesPinnedRequirementsInstallOrImportFailed and is recorded",
          raised is not None and "importing still fails" in raised.install_output
          and not isinstance(raised, install.PythonLibrariesPinnedRequirementsInstalledButImportableOnlyInANewProcessError)
          and record.is_file(), raised)
    os.utime(record, (5000.0, 5000.0))

    result, raised = install_then_import(state_directory, importer_never, lambda: "installed",
                                         (), 5000.0 + install.INSTALL_RETRY_SECONDS + 1,
                                         fresh_process=True)
    check("an install that a new process can import raises "
          "PythonLibrariesPinnedRequirementsInstalledButImportableOnlyInANewProcessError and clears the older failure record",
          isinstance(raised, install.PythonLibrariesPinnedRequirementsInstalledButImportableOnlyInANewProcessError)
          and not record.exists(), raised)

    class CallerUnavailable(install.PythonLibrariesPinnedRequirementsInstallOrImportFailed):
        pass

    class CallerInstalledForANewProcess(CallerUnavailable):
        pass
    importer, _installer, package_names, state = libraries_after(99)
    result, raised = install_then_import(
        state_directory, importer, failing_installer(state, CallerUnavailable), package_names, 6000.0,
        unavailable_error=CallerUnavailable,
        installed_for_new_process_error=CallerInstalledForANewProcess)
    check("a caller's own error class is raised and recorded",
          type(raised) is CallerUnavailable and record.is_file(), raised)
    os.utime(record, (6000.0, 6000.0))
    result, raised = install_then_import(
        state_directory, importer_never, lambda: "installed", (), 6060.0,
        unavailable_error=CallerUnavailable,
        installed_for_new_process_error=CallerInstalledForANewProcess)
    check("a recorded failure is raised as the caller's own error class",
          type(raised) is CallerUnavailable and "network is unreachable" in raised.install_output,
          raised)
    record.unlink()
    result, raised = install_then_import(
        state_directory, importer_never, lambda: "installed", (), 6100.0,
        fresh_process=True, unavailable_error=CallerUnavailable,
        installed_for_new_process_error=CallerInstalledForANewProcess)
    check("the caller's own new-process error class is raised",
          type(raised) is CallerInstalledForANewProcess, raised)

    blocking_file = Path(scratch) / "a-file-not-a-directory"
    blocking_file.write_text("x")
    importer, installer, package_names, state = libraries_after(1)
    result, raised = install_then_import(blocking_file / "state", importer, installer, package_names, 9000.0)
    check("a state directory that cannot be made raises PythonLibrariesPinnedRequirementsInstallOrImportFailed saying so",
          raised is not None and "install lock" in raised.install_output and state["installs"] == 0,
          (raised, state))

    read_only = Path(scratch) / "read-only-state"
    read_only.mkdir()
    (read_only / install.INSTALL_LOCK_FILE_NAME).write_text("")
    read_only.chmod(0o555)
    importer, _installer, package_names, state = libraries_after(99)
    try:
        result, raised = install_then_import(read_only, importer, failing_installer(state), package_names,
                                             9000.0)
    except OSError as error:
        raised = error
    check("a failed install whose record cannot be written still raises "
          "PythonLibrariesPinnedRequirementsInstallOrImportFailed",
          isinstance(raised, install.PythonLibrariesPinnedRequirementsInstallOrImportFailed) and state["installs"] == 1,
          (raised, state))
    read_only.chmod(0o755)

    # Parallel callers, such as the Bash guards on one command, take turns on the install lock,
    # so only the first installs. Two child processes start together; each one's installer takes a
    # second and then writes the marker its importer looks for. Each child has a timeout, so a
    # caller that never gets the lock prints FAIL instead of hanging the suite.
    parallel_state = Path(scratch) / "parallel-state"
    installed_marker = Path(scratch) / "parallel-installed"
    installs_log = Path(scratch) / "parallel-installs.log"
    parallel_caller_code = (
        "import importlib.util, sys, time\n"
        "from pathlib import Path\n"
        "spec = importlib.util.spec_from_file_location('m', sys.argv[1])\n"
        "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
        "marker, log = Path(sys.argv[3]), Path(sys.argv[4])\n"
        "def importer():\n"
        "    if not marker.exists():\n"
        "        raise ImportError('No module named tree_sitter')\n"
        "    return 'the libraries'\n"
        "def installer():\n"
        "    with open(log, 'a') as handle:\n"
        "        handle.write('install\\n')\n"
        "    time.sleep(1)\n"
        "    marker.write_text('')\n"
        "print(m.python_libraries_pinned_requirements_install_if_missing_then_import(\n"
        "    importer, installer, time.time, lambda: False, Path(sys.argv[2]), ()))\n")
    callers = [subprocess.Popen([sys.executable, "-c", parallel_caller_code, _spec.origin, str(parallel_state),
                                 str(installed_marker), str(installs_log)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
               for _ in range(2)]
    outcomes = []
    for caller in callers:
        try:
            stdout, stderr = caller.communicate(timeout=30)
            outcomes.append((caller.returncode, stdout.strip(), stderr[-300:]))
        except subprocess.TimeoutExpired:
            caller.kill()
            outcomes.append(("timed out", "", ""))
    installs = installs_log.read_text().count("install") if installs_log.exists() else 0
    check("two callers starting together take turns on the install lock: one installs, both import",
          installs == 1 and all(outcome[:2] == (0, "the libraries") for outcome in outcomes),
          (installs, outcomes))


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
      and install.PINNED_REQUIREMENTS_FILE.name == "python-libraries-pinned-requirements.txt")
try:
    install.pinned_requirements_pip_install(8, runner_exiting(1, "", "ERROR: No matching distribution"))
    raised = None
except install.PythonLibrariesPinnedRequirementsInstallOrImportFailed as error:
    raised = error
check("pip exiting nonzero raises PythonLibrariesPinnedRequirementsInstallOrImportFailed with its output",
      raised is not None and "No matching distribution" in raised.install_output
      and "exited 1" in raised.install_output, raised)
try:
    install.pinned_requirements_pip_install(8, runner_exiting(1))
    raised = None
except install.PythonLibrariesPinnedRequirementsInstallOrImportFailed as error:
    raised = error
check("pip exiting nonzero with no output says so",
      raised is not None and "(no output)" in raised.install_output, raised)


def runner_timing_out(command, **kwargs):
    raise subprocess.TimeoutExpired(command, kwargs["timeout"])


try:
    install.pinned_requirements_pip_install(8, runner_timing_out)
    raised = None
except install.PythonLibrariesPinnedRequirementsInstallOrImportFailed as error:
    raised = error
check("pip timing out raises PythonLibrariesPinnedRequirementsInstallOrImportFailed saying it did not finish",
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

old_python_run = runner_exiting(0)
try:
    install.pinned_requirements_pip_install(8, old_python_run, python_version=(3, 9, 6))
    raised = None
except install.PythonLibrariesPinnedRequirementsInstallOrImportFailed as error:
    raised = error
check("below Python 3.11 pip does not run, and the failure names the interpreter, its version "
      "and the minimum",
      raised is not None and not hasattr(old_python_run, "command")
      and sys.executable in raised.install_output and "Python 3.9.6" in raised.install_output
      and "Python 3.11" in raised.install_output,
      raised)
for host in ("Neds-MacBook-Pro", "ned-box"):
    where, command = install.pinned_requirements_by_hand_install_command(
        host, python_version=(3, 9, 6))
    check(f"below Python 3.11 no by-hand install command is offered, on {host}",
          command is None and where == f"on {host}", (where, command))
instruction = install.python_below_minimum_version_instruction("Neds-MacBook-Pro", (3, 10, 14))
check("below Python 3.11 the instruction names the interpreter, its version, the minimum, the PATH "
      "fix and the rerun, and no pip command",
      instruction is not None and sys.executable in instruction and "Python 3.10.14" in instruction
      and "Python 3.11 or later on Neds-MacBook-Pro" in instruction and "Homebrew" in instruction
      and str(Path(sys.executable).parent) in instruction and "next run" in instruction
      and "pip" not in instruction, instruction)
check("at Python 3.11 there is no below-minimum instruction, and the by-hand command is offered",
      install.python_below_minimum_version_instruction("h", (3, 11, 0)) is None
      and install.pinned_requirements_by_hand_install_command("h", python_version=(3, 11, 0))[1]
      is not None)
run = runner_exiting(0)
install.pinned_requirements_pip_install(8, run, python_version=(3, 11, 0))
check("at Python 3.11 pip runs", hasattr(run, "command"))

source = Path(_spec.origin).read_text(encoding="utf-8")
try:
    ast.parse(source, feature_version=(3, 9))
    parse_error = None
except SyntaxError as error:
    parse_error = error
check("the module parses as Python 3.9, so an older Python reaches the version check",
      parse_error is None, parse_error)

# A hook may wait on the install lock through another run's install, then run its own;
# both must finish inside the hook's registered timeout, or Claude Code kills the hook
# before it reports the failure or records it.
settings = json.loads((REPOSITORY_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
reader_source = (REPOSITORY_ROOT / "nc-systems" / "general-tools"
                 / "shell-command-tree-sitter-bash-reader-common.py").read_text(encoding="utf-8")
timeout_pattern = re.compile(r"^INSTALL_TIMEOUT_SECONDS = (\d+)$", re.MULTILINE)
installing_hooks = []
for groups in settings["hooks"].values():
    for group in groups:
        for registered in group["hooks"]:
            script = re.search(r'"\$CLAUDE_PROJECT_DIR"/(\S+\.py)', registered.get("command", ""))
            if not script or not (REPOSITORY_ROOT / script.group(1)).is_file():
                continue
            script_source = (REPOSITORY_ROOT / script.group(1)).read_text(encoding="utf-8")
            if "python-libraries-pinned-requirements-install-if-missing-then-import-common.py" in script_source:
                timeout_source, loads = script_source, "the shared module"
            elif "shell-command-tree-sitter-bash-reader-common.py" in script_source:
                timeout_source, loads = reader_source, "the shell reader"
            else:
                continue
            install_timeout = int(timeout_pattern.search(timeout_source).group(1))
            installing_hooks.append((script.group(1), install_timeout, registered.get("timeout"), loads))
too_short = [entry for entry in installing_hooks
             if entry[2] is None or 2 * entry[1] >= entry[2]]
check("every registered hook that may install the pinned libraries has a timeout longer than "
      "two installs",
      not too_short, (too_short, installing_hooks))
# Each way a hook reaches the install must be found, or the case above checks nothing for it.
check("the timeout case finds the hard-wrap reminder and a Bash guard that loads the shell reader",
      ("scripts/markdown-edit-hard-wrapped-paragraph-reminder-hook.py", "the shared module")
      in [(entry[0], entry[3]) for entry in installing_hooks]
      and any(entry[3] == "the shell reader" for entry in installing_hooks), installing_hooks)

print("all cases passed" if not failures else f"{failures} case(s) failed")
sys.exit(1 if failures else 0)
