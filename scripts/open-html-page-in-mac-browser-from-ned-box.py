#!/usr/bin/env python3
"""Open an HTML page from ned-box's log-store in the browser on the user's Mac.

Usage, on ned-box: scripts/open-html-page-in-mac-browser-from-ned-box.py <path>

for example `scripts/open-html-page-in-mac-browser-from-ned-box.py
/home/nedlern/nedschorus-logs/handoff-agent-seat-died-without-session-handoff-restart-watcher/notices/x.html`.
The path may be relative to the current directory. It must name a .html file
under /home/nedlern/nedschorus-logs, the log-store, which the Mac reads
through its mount /Volumes/nedhome.

The path is resolved here, symlinks included, and the request
`open-in-browser <absolute path>` goes over ssh with the key
~/.ssh/id_ed25519_mac_side_action to the Mac's forced command,
scripts/mac-window-opened-for-ned-box-forced-command.py. That program checks
the path again, maps it onto the mount, and runs `open` on it, which shows it
in the Mac's default browser. This program checks the request with the forced
command's own function first, so a request the Mac would refuse for its text
is refused here, before any connection is made.

Exit status: 0 opened; 1 not opened, or may not have opened (the Mac could not
be reached, ssh timed out, or `open` failed on the Mac); 2 refused, here or by
the Mac, or a usage error.

The environment overrides open-mac-window-from-ned-box.py reads apply here too,
and NEDSCHORUS_NED_BOX_HOME overrides ned-box's home: the seams the test suite
uses.
"""

import importlib.util
import os
import sys
from pathlib import Path

PROGRAM = "open-html-page-in-mac-browser-from-ned-box"
WINDOW_SENDER_PATH = Path(__file__).with_name("open-mac-window-from-ned-box.py")


def load_window_sender_module():
    specification = importlib.util.spec_from_file_location("open_mac_window_from_ned_box", WINDOW_SENDER_PATH)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def main(arguments):
    if arguments in (["--help"], ["-h"]):
        print(__doc__)
        return 0
    window_sender = load_window_sender_module()
    forced_command = window_sender.load_forced_command_module()
    ned_box_home = os.environ.get("NEDSCHORUS_NED_BOX_HOME") or forced_command.NED_BOX_HOME
    pages_directory = f"{ned_box_home.rstrip('/')}/{forced_command.BROWSER_PAGES_DIRECTORY_NAME}"
    if len(arguments) != 1:
        print(f"usage: {PROGRAM} <path>", file=sys.stderr)
        print(f"Opens one .html file under {pages_directory}/ in the browser on the user's Mac.", file=sys.stderr)
        return window_sender.EXIT_USAGE_OR_REFUSED
    resolved = os.path.realpath(arguments[0])
    if not os.path.isfile(resolved):
        print(f"{PROGRAM}: no request was sent, because {resolved} is not a file on ned-box.", file=sys.stderr)
        print("Give the path of an existing page.", file=sys.stderr)
        return window_sender.EXIT_USAGE_OR_REFUSED
    # Checked before the shared function, which would read a space as a second path.
    if not forced_command.SAFE_WORD_PATTERN.fullmatch(resolved):
        print(f"{PROGRAM}: no request was sent, because {resolved} holds a character outside letters, digits and _ . / : = @ % + , -, such as a space.", file=sys.stderr)
        print(f"Write the page under {pages_directory}/ with a name made only of those characters.", file=sys.stderr)
        return window_sender.EXIT_USAGE_OR_REFUSED
    request = f"{forced_command.BROWSER_VERB} {resolved}"
    try:
        forced_command.browser_page_path_on_ned_box(request, ned_box_home)
    except forced_command.RequestRefused as refusal:
        print(f"{PROGRAM}: no request was sent, because {refusal}.", file=sys.stderr)
        print(f"The Mac opens only .html files under {pages_directory}/: write the page there.", file=sys.stderr)
        return window_sender.EXIT_USAGE_OR_REFUSED
    # The user opens the page on the Mac, so he is given the Mac's path to it.
    mac_path = os.path.join(forced_command.MAC_MOUNT_OF_NED_BOX_HOME, resolved[len(ned_box_home.rstrip("/")) + 1:])
    return window_sender.send_request_to_mac(
        request, forced_command, program=PROGRAM,
        not_done="the page was not opened",
        fallback=f"the page you wanted shown, which is {mac_path} on the Mac, so he can open it himself",
        may_not_have_happened="the page may not have opened",
        timeout_fallback=f"what this says, and the page you wanted shown, which is {mac_path} on the Mac, so he can check whether it opened")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
