#!/usr/bin/env python3
"""Finds the executable file the running Python process runs, for suites that copy it under the name claude.

Not a test file, and not a program a seat runs: a suite that needs a process named `claude`, such
as one whose code looks for its nearest `claude` parent process, loads it and copies
interpreter_image_of_this_process() to a file named claude. Its name ends `-test-fixture.py`
rather than `-test.py` so scripts/run-all-test-suites.py, which finds suites with
`git ls-files -- '*-test.py'`, does not run it as a suite of its own.

A copy, not a symbolic link to sys.executable, because the process name the code under test reads
is the name of the executable file the process runs. On macOS a framework Python's
bin/python3.x is a launcher that re-executes Python.app's Python, so a link to it, or a copy of it,
runs under the name Python, not claude.
"""

import os
import subprocess
import sys
from pathlib import Path


def interpreter_image_of_this_process():
    """The executable file this process runs: /proc/self/exe on Linux, `ps -o comm=` elsewhere.

    Raises RuntimeError when ps reports a name that is not a full path, and
    subprocess.CalledProcessError when ps fails."""
    if sys.platform.startswith("linux"):
        return Path(os.readlink("/proc/self/exe"))
    ps = subprocess.run(["ps", "-o", "comm=", "-p", str(os.getpid())],
                        capture_output=True, text=True, check=True)
    image = Path(ps.stdout.strip())
    if not image.is_absolute():
        raise RuntimeError(f"ps reported {image!r} as this process's executable, not a full path")
    return image
