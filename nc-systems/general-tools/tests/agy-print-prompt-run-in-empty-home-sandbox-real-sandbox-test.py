#!/usr/bin/env python3
"""The cases of agy-print-prompt-run-in-empty-home-sandbox-test.py that need
the real bwrap: the home holds nothing but .gemini, and agy starts in an empty
working directory.

The real bwrap cannot start inside the nc-test-sandbox, so this suite is
listed in scripts/run-all-test-suites.py's SUITES_RUN_WITHOUT_ANY_SANDBOX and
waits for that list's machine-wide lock. It runs
nc-systems/general-tools/tests/agy-print-prompt-run-in-empty-home-sandbox-test.py
with --real-sandbox-cases-only, which runs those cases alone; the other cases
of that suite run inside the nc-test-sandbox with a stand-in for bwrap. Its
exit code and output are that run's.

Run: python3 nc-systems/general-tools/tests/agy-print-prompt-run-in-empty-home-sandbox-real-sandbox-test.py
"""

import subprocess
import sys
from pathlib import Path

SUITE = Path(__file__).resolve().parent / "agy-print-prompt-run-in-empty-home-sandbox-test.py"

sys.exit(subprocess.run([sys.executable, str(SUITE), "--real-sandbox-cases-only"],
                        check=False).returncode)
