#!/usr/bin/env python3
"""Check that every pinned compiled Python library is installed at its pinned version; install what is not.

Reads compiled-python-libraries-pinned-requirements.txt beside this file. A
library is missing when the python3 running this script has no copy of it,
or has a copy at another version. When one is missing, the script installs
the whole pinned file per user, as the shell reader does, and checks again.

It prints one line and exits 0 when nothing is left missing, naming what it
installed. Otherwise it prints what is still missing, what the install
printed, and the command that installs the libraries by hand, and exits 1.

Run: python3 nc-systems/general-tools/compiled-python-libraries-pinned-requirements-check-and-install.py
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import socket
import subprocess
import sys
from pathlib import Path

_pinned_libraries_install_spec = importlib.util.spec_from_file_location(
    "compiled_python_libraries_pinned_requirements_install_common",
    Path(__file__).resolve().with_name("compiled-python-libraries-pinned-requirements-install-common.py"))
pinned_libraries_install = importlib.util.module_from_spec(_pinned_libraries_install_spec)
_pinned_libraries_install_spec.loader.exec_module(pinned_libraries_install)

# Run by hand or once a day, not inside a hook, so a slow download may finish.
INSTALL_TIMEOUT_SECONDS = 600
CHECK_TIMEOUT_SECONDS = 60
# A new process reads the installed versions, so a copy installed by this run is seen.
INSTALLED_VERSIONS_PROGRAM = (
    "import importlib.metadata, json, sys\n"
    "versions = {}\n"
    "for name in json.loads(sys.argv[1]):\n"
    "    try:\n"
    "        versions[name] = importlib.metadata.version(name)\n"
    "    except importlib.metadata.PackageNotFoundError:\n"
    "        versions[name] = None\n"
    "print(json.dumps(versions))\n")


def pinned_versions(requirements_file=pinned_libraries_install.PINNED_REQUIREMENTS_FILE):
    """Return {name: version} for each `name==version` line of the requirements file."""
    pins = {}
    for line in requirements_file.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        name, separator, version = line.partition("==")
        if not separator or not name.strip() or not version.strip():
            raise ValueError(f"{requirements_file}: not a `name==version` line: {line!r}")
        pins[name.strip()] = version.strip()
    return pins


def installed_versions(names, runner=subprocess.run):
    """Return {name: installed version or None}, read by a new process of this python3."""
    completed = runner([sys.executable, "-c", INSTALLED_VERSIONS_PROGRAM, json.dumps(sorted(names))],
                       capture_output=True, text=True, timeout=CHECK_TIMEOUT_SECONDS,
                       stdin=subprocess.DEVNULL)
    if completed.returncode != 0:
        raise RuntimeError(f"reading the installed versions exited {completed.returncode}: "
                           f"{(completed.stdout + completed.stderr).strip() or '(no output)'}")
    return json.loads(completed.stdout)


def missing_libraries(pins, versions):
    """Return the lines `name: wanted pin, found …` for each library not at its pinned version."""
    return [f"{name}: wanted {pins[name]}, found {versions.get(name) or 'none'}"
            for name in sorted(pins) if versions.get(name) != pins[name]]


def check_and_install(host, runner=subprocess.run, installer=None):
    """Return (exit status, report lines)."""
    if installer is None:
        def installer():
            return pinned_libraries_install.pinned_requirements_pip_install(INSTALL_TIMEOUT_SECONDS, runner)
    pins = pinned_versions()
    missing = missing_libraries(pins, installed_versions(pins, runner))
    if not missing:
        return 0, [f"{host}: all {len(pins)} pinned compiled Python libraries are installed "
                   f"at their pinned versions."]
    try:
        install_output = installer()
    except pinned_libraries_install.CompiledPythonLibrariesUnavailable as error:
        install_output = error.install_output
    still_missing = missing_libraries(pins, installed_versions(pins, runner))
    if not still_missing:
        return 0, [f"{host}: installed {'; '.join(missing)}; all {len(pins)} pinned compiled "
                   f"Python libraries are now at their pinned versions."]
    return 1, [f"{host}: these pinned compiled Python libraries are still missing after an install:",
               *(f"  {line}" for line in still_missing),
               f"What the install printed: {install_output or '(nothing)'}",
               "To install them by hand, run this command {}: {}".format(
                   *pinned_libraries_install.pinned_requirements_by_hand_install_command(host))]


def main(arguments=None):
    argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                            epilog="Exits 0 when nothing is left missing, 1 otherwise.").parse_args(arguments)
    host = socket.gethostname().split(".")[0]
    try:
        status, lines = check_and_install(host)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"{host}: the pinned compiled Python libraries could not be checked: {error}")
        return 1
    print("\n".join(lines))
    return status


if __name__ == "__main__":
    sys.exit(main())
