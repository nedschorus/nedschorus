#!/usr/bin/env python3
"""Open a file from ned-box in Typora on the user's Mac.

Usage, on ned-box: scripts/open-file-in-typora-on-mac-from-ned-box.py <path>

for example `scripts/open-file-in-typora-on-mac-from-ned-box.py docs/nedschorus-wiki/nedschorus-glossary.md`.
The path may be relative to the current directory. It must name a file under
/home/nedlern, because the Mac sees ned-box's home through its mount
/Volumes/nedhome and nothing else on ned-box.

The path is resolved here, symlinks included, and the request
`open-in-typora <absolute path>` goes over ssh with the key
~/.ssh/id_ed25519_mac_side_action to the Mac's forced command,
scripts/mac-window-opened-for-ned-box-forced-command.py. That program checks
the path again, maps it onto the mount, and runs `open -a Typora` on it. This
program checks the request with the forced command's own function first, so a
request the Mac would refuse for its text is refused here, before any
connection is made.

The environment overrides open-mac-window-from-ned-box.py reads apply here too,
and NEDSCHORUS_NED_BOX_HOME overrides ned-box's home: the seams the test suite
uses.
"""

import importlib.util
import os
import sys
from pathlib import Path

PROGRAM = "open-file-in-typora-on-mac-from-ned-box"
WINDOW_SENDER_PATH = Path(__file__).with_name("open-mac-window-from-ned-box.py")


def load_window_sender_module():
    specification = importlib.util.spec_from_file_location("open_mac_window_from_ned_box", WINDOW_SENDER_PATH)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def main(arguments):
    window_sender = load_window_sender_module()
    forced_command = window_sender.load_forced_command_module()
    if len(arguments) != 1:
        print(f"usage: {PROGRAM} <path>", file=sys.stderr)
        print("Opens one file from ned-box in Typora on the user's Mac.", file=sys.stderr)
        return window_sender.EXIT_USAGE_OR_REFUSED
    ned_box_home = os.environ.get("NEDSCHORUS_NED_BOX_HOME") or forced_command.NED_BOX_HOME
    resolved = os.path.realpath(arguments[0])
    if not os.path.isfile(resolved):
        print(f"{PROGRAM}: no request was sent, because {resolved} is not a file on ned-box.", file=sys.stderr)
        print("Give the path of an existing file.", file=sys.stderr)
        return window_sender.EXIT_USAGE_OR_REFUSED
    # Checked before the shared function, which would read a space as a second path.
    if not forced_command.SAFE_WORD_PATTERN.fullmatch(resolved):
        print(f"{PROGRAM}: no request was sent, because {resolved} holds a character outside letters, digits and _ . / : = @ % + , -, such as a space.", file=sys.stderr)
        print(f"Copy the file to a name under {ned_box_home}/ made only of those characters, and open the copy.", file=sys.stderr)
        return window_sender.EXIT_USAGE_OR_REFUSED
    request = f"{forced_command.TYPORA_VERB} {resolved}"
    try:
        forced_command.typora_path_on_ned_box(request, ned_box_home)
    except forced_command.RequestRefused as refusal:
        print(f"{PROGRAM}: no request was sent, because {refusal}.", file=sys.stderr)
        print(f"The Mac sees only files under {ned_box_home}/: copy the file there and open the copy.", file=sys.stderr)
        return window_sender.EXIT_USAGE_OR_REFUSED
    return window_sender.send_request_to_mac(
        request, forced_command, program=PROGRAM,
        not_done="Typora was not opened",
        fallback=f"the file you wanted shown, {resolved}, so he can open it himself",
        may_not_have_happened="Typora may not have opened the file",
        timeout_fallback=f"the file you wanted shown, {resolved}")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
