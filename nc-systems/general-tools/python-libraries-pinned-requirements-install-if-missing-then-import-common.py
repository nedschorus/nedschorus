#!/usr/bin/env python3
"""Install the Python libraries pinned in python-libraries-pinned-requirements.txt.

A program that needs one of these libraries imports it; when the import
fails, python_libraries_pinned_requirements_install_if_missing_then_import installs the whole pinned
file per user, with pip's --user --break-system-packages, and imports again.
The user hears only when the install fails: the caller gets
PythonLibrariesPinnedRequirementsInstallOrImportFailed, whose install_output says what the install
printed, and says so in its own message.

Callers that run in parallel, such as the Bash guards on one command, take
turns on a lock file, so only the first installs. A failed install is
recorded, and for ten minutes later callers get the recorded output instead of
waiting for an install that fails again.

Before each import under the lock, the caller's packages are dropped from
sys.modules, submodules included: an import that failed partway, such as a
newer markdown-it-py whose dependency is missing, leaves its submodules loaded,
and the next import would mix them with the installed version.

A compiled module cannot be replaced inside a running process. When the
install succeeds but this process still holds a copy it could not use, and a
new Python process can import the libraries, the caller gets
PythonLibrariesPinnedRequirementsInstalledButImportableOnlyInANewProcessError, and does its work in a new
process.

Python 3.11 is the project's minimum for the pinned libraries. Below it nothing
is installed, and no by-hand install command is offered, since pip would run
under the same interpreter; the words instead say how to put a newer Python
first on the PATH.

Load it by path, under the snake_case form of its file name:

    spec = importlib.util.spec_from_file_location(
        "python_libraries_pinned_requirements_install_if_missing_then_import_common", <path>)
"""

# Deferred annotations let the module load on the Mac's system Python 3.9.
from __future__ import annotations

import importlib
import shlex
import site
import subprocess
import sys
from pathlib import Path

PINNED_REQUIREMENTS_FILE = Path(__file__).resolve().with_name(
    "python-libraries-pinned-requirements.txt")
INSTALL_RETRY_SECONDS = 600
INSTALL_LOCK_FILE_NAME = "install.lock"
INSTALL_FAILURE_FILE_NAME = "last-install-failure.txt"
MINIMUM_PYTHON_VERSION = (3, 11)


class PythonLibrariesPinnedRequirementsInstallOrImportFailed(Exception):
    """A pinned library could not be imported, and installing it failed.

    install_output holds what the install printed, or why it did not run.
    """

    def __init__(self, install_output):
        super().__init__(install_output)
        self.install_output = install_output


class PythonLibrariesPinnedRequirementsInstalledButImportableOnlyInANewProcessError(PythonLibrariesPinnedRequirementsInstallOrImportFailed):
    """The install succeeded, but this process still holds the unusable copy it loaded first."""


def pinned_requirements_pip_install_command(requirements_file=PINNED_REQUIREMENTS_FILE, *quiet_options):
    """Return the pip command that installs the pinned file per user for this process's interpreter."""
    return [sys.executable, "-m", "pip", "install", "--user", "--break-system-packages",
            *quiet_options, "-r", str(requirements_file)]


def _dotted(version):
    return ".".join(map(str, version))


def _python_version(python_version):
    return tuple(python_version or sys.version_info[:3])


def pinned_requirements_by_hand_install_command(host, requirements_file=PINNED_REQUIREMENTS_FILE,
                                                python_version=None):
    """Return (where, command): where the user runs the pinned file's install by hand, and the command.

    The command names this process's own interpreter, which is the one the libraries must be
    installed for; a bare `python3` on the user's PATH may be another one.
    Below MINIMUM_PYTHON_VERSION no command can work, so command is None; give the user
    python_below_minimum_version_instruction instead.
    """
    if _python_version(python_version)[:2] < MINIMUM_PYTHON_VERSION:
        return f"on {host}", None
    install = shlex.join(pinned_requirements_pip_install_command(requirements_file))
    # The user sits at the Mac, and reaches ned-box over ssh.
    if host == "ned-box":
        return "in a Terminal on your Mac", f"ssh nedlern@ned-box {shlex.quote(install)}"
    return f"on {host}", install


def python_below_minimum_version_instruction(host, python_version=None):
    """Return what the user does on host when this process's Python is below the minimum, else None."""
    version = _python_version(python_version)
    if version[:2] >= MINIMUM_PYTHON_VERSION:
        return None
    minimum = _dotted(MINIMUM_PYTHON_VERSION)
    return (f"No install command can work for {sys.executable}, which is Python {_dotted(version)}: "
            f"the project's minimum is Python {minimum}. Install Python {minimum} or later on {host}, "
            f"and put its directory ahead of {Path(sys.executable).parent} on the PATH; on the Mac, "
            f"that means Homebrew's Python ahead of Apple's. The next run then installs the pinned "
            f"libraries itself.")


def pinned_requirements_pip_install(timeout_seconds, runner=subprocess.run,
                                    requirements_file=PINNED_REQUIREMENTS_FILE,
                                    unavailable_error=PythonLibrariesPinnedRequirementsInstallOrImportFailed,
                                    python_version=None):
    """Install the pinned requirements per user; return what pip printed, or raise unavailable_error."""
    python_version = _python_version(python_version)
    if python_version[:2] < MINIMUM_PYTHON_VERSION:
        raise unavailable_error(
            f"nothing was installed: {sys.executable} is Python {_dotted(python_version)}, below "
            f"Python {_dotted(MINIMUM_PYTHON_VERSION)}, the project's minimum for the pinned libraries.")
    command = pinned_requirements_pip_install_command(requirements_file, "--disable-pip-version-check",
                                                      "--quiet")
    try:
        completed = runner(command, capture_output=True, text=True, timeout=timeout_seconds,
                           stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError) as error:
        raise unavailable_error(f"`{' '.join(command)}` did not finish: {error}") from error
    printed = (completed.stdout + completed.stderr).strip()
    if completed.returncode != 0:
        raise unavailable_error(
            f"`{' '.join(command)}` exited {completed.returncode}: {printed or '(no output)'}")
    return printed


def python_libraries_pinned_requirements_install_if_missing_then_import(
        importer, installer, clock, fresh_process_check, state_directory, loaded_package_names,
        unavailable_error=PythonLibrariesPinnedRequirementsInstallOrImportFailed,
        installed_for_new_process_error=PythonLibrariesPinnedRequirementsInstalledButImportableOnlyInANewProcessError):
    """Install with installer(), unless another caller already has, and return importer()'s result.

    Call it after importer() has failed once.

    importer raises ImportError while a library is missing or unusable.
    installer raises unavailable_error when the install fails.
    fresh_process_check returns whether a new Python process can import the libraries.
    loaded_package_names are the top-level packages importer() loads; they and their submodules
    are dropped from sys.modules before each import, so the import loads the copy on disk.
    The lock and the failure record live in state_directory.
    """
    try:
        state_directory.mkdir(parents=True, exist_ok=True)
        lock = open(state_directory / INSTALL_LOCK_FILE_NAME, "w")
    except OSError as error:
        raise unavailable_error(f"could not open the install lock in {state_directory}: {error}") \
            from error
    with lock:
        try:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX)
        except (ImportError, OSError):
            pass  # Without the lock, two installs may run; each installs the same pinned files.
        # Another caller may have installed into a user site this process did not have at start-up.
        _refresh_import_paths()
        _forget_loaded_packages(loaded_package_names)
        try:
            return importer()
        except ImportError:
            pass
        failure_record = state_directory / INSTALL_FAILURE_FILE_NAME
        try:
            if clock() - failure_record.stat().st_mtime < INSTALL_RETRY_SECONDS:
                # Each caller would otherwise wait for its own failing install.
                raise unavailable_error(failure_record.read_text(encoding="utf-8"))
        except OSError:
            pass
        try:
            installer()
            _refresh_import_paths()
            _forget_loaded_packages(loaded_package_names)
            try:
                modules = importer()
            except ImportError as error:
                if fresh_process_check():
                    raise installed_for_new_process_error(
                        f"the install finished; this process still holds the copy it could not "
                        f"use: {error}") from error
                raise unavailable_error(
                    f"the install finished but importing still fails: {error}") from error
        except installed_for_new_process_error:
            _forget_failure(failure_record)
            raise
        except unavailable_error as error:
            try:
                failure_record.write_text(error.install_output, encoding="utf-8")
            except OSError:
                pass
            raise
        _forget_failure(failure_record)
        return modules


def _forget_loaded_packages(package_names):
    for name in [name for name in sys.modules if name.split(".")[0] in package_names]:
        del sys.modules[name]


def _forget_failure(failure_record):
    try:
        failure_record.unlink()
    except OSError:
        pass


def _refresh_import_paths():
    # A user site that did not exist at start-up is not on sys.path yet.
    site.addsitedir(site.getusersitepackages())
    importlib.invalidate_caches()
