#!/usr/bin/env python3
"""The cases of cold-read-agy-cell-test.py that need the real sandbox
program: that no credential file can be read from inside the agy cell,
under the real bwrap on Linux or sandbox-exec on macOS.

The real bwrap cannot start inside the nc-test-sandbox, so this suite is
listed in scripts/run-all-test-suites.py's SUITES_RUN_WITHOUT_ANY_SANDBOX and
waits for that list's machine-wide lock. It runs
nc-systems/cold-read/tests/cold-read-agy-cell-test.py with
--real-sandbox-cases-only, which runs those cases alone and puts no stand-in
for the sandbox program on PATH; the other cases of that suite run inside the
nc-test-sandbox with a stand-in. Its exit code and output are that run's.

Run: python3 nc-systems/cold-read/tests/cold-read-agy-cell-real-sandbox-test.py
"""

import subprocess
import sys
from pathlib import Path

SUITE = Path(__file__).resolve().parent / "cold-read-agy-cell-test.py"

sys.exit(subprocess.run([sys.executable, str(SUITE), "--real-sandbox-cases-only"],
                        check=False).returncode)
