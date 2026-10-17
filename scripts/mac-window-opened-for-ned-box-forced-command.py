#!/usr/bin/env python3
"""Forward to scripts/mac-request-from-ned-box-forced-command.py, this program's new name.

The Mac's ~/.ssh/authorized_keys names this path in the command= option of the
line that admits ned-box's key, and the Mac pulls the rename before the user
edits that line. Delete this file once that line names the new path.
"""

import os
import sys
from pathlib import Path

NEW_PROGRAM_PATH = Path(__file__).resolve().with_name("mac-request-from-ned-box-forced-command.py")

os.execv(sys.executable, [sys.executable, str(NEW_PROGRAM_PATH), *sys.argv[1:]])
