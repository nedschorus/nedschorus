#!/usr/bin/env python3
"""Open an iTerm window on the user's Mac that runs a command on ned-box.

Usage, on ned-box: scripts/open-mac-window-from-ned-box.py <word> [<word> ...]

for example `scripts/open-mac-window-from-ned-box.py tmux attach -t merge-lane-2`.
The Mac opens a window running `ssh -t -- nedlern@ned-box <word> ...`, so the
user sees the command's output on his own screen.

The request goes over ssh with the key ~/.ssh/id_ed25519_mac_side_action. The
Mac admits that key for one forced command only,
scripts/mac-window-opened-for-ned-box-forced-command.py, which checks the
request word by word before anything runs. This program checks the words with
that same function first, so a request the Mac would refuse is refused here,
with the same reason, before any connection is made.

NEDSCHORUS_MAC_SSH_DESTINATION overrides the Mac's address; NEDSCHORUS_SSH_PROGRAM
overrides the ssh program, the seam the test suite uses.
"""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

PROGRAM = "open-mac-window-from-ned-box"
DEFAULT_MAC_SSH_DESTINATION = "el@10.0.1.23"
MAC_SIDE_ACTION_KEY = Path.home() / ".ssh" / "id_ed25519_mac_side_action"
SSH_EXIT_CONNECTION_FAILED = 255
FORCED_COMMAND_PATH = Path(__file__).with_name("mac-window-opened-for-ned-box-forced-command.py")

EXIT_OPENED = 0
EXIT_USAGE_OR_REFUSED = 2
EXIT_NOT_OPENED = 1


def load_forced_command_module():
    specification = importlib.util.spec_from_file_location("mac_window_opened_for_ned_box_forced_command", FORCED_COMMAND_PATH)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def request_for(words, forced_command):
    """The one remote-command string the Mac receives as SSH_ORIGINAL_COMMAND."""
    request = " ".join([forced_command.REQUEST_VERB, *words])
    received = forced_command.window_command_words(request)
    if received != list(words):
        raise forced_command.RequestRefused(
            "a word holds a space, so the Mac would split it into other words than the ones given")
    return request


def ssh_command(request, destination, ssh_program="ssh"):
    return [ssh_program, "-i", str(MAC_SIDE_ACTION_KEY), "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=10", "--", destination, request]


def explain_connection_failure(stderr, destination):
    if "Permission denied" in stderr:
        return [f"{PROGRAM}: the Mac refused the key {MAC_SIDE_ACTION_KEY}, so no window was opened.",
                "The Mac's ~/.ssh/authorized_keys does not admit this key yet: tell the user, who adds the line the helper's pull request gives."]
    if "Host key verification failed" in stderr:
        return [f"{PROGRAM}: this machine does not know the Mac's host key, so ssh stopped before connecting and no window was opened.",
                f"Tell the user; the one-time fix, run on ned-box, is: ssh-keyscan -t ed25519 {destination.split('@')[-1]} >> ~/.ssh/known_hosts"]
    return [f"{PROGRAM}: could not reach the Mac at {destination}, so no window was opened: {stderr.strip() or 'ssh exited 255'}.",
            "Tell the user what this says, and the command you wanted shown, so he can run it himself."]


def main(arguments):
    if not arguments:
        print(f"usage: {PROGRAM} <word> [<word> ...]", file=sys.stderr)
        print("Opens a window on the user's Mac running ssh -t -- nedlern@ned-box <word> ...", file=sys.stderr)
        return EXIT_USAGE_OR_REFUSED
    forced_command = load_forced_command_module()
    try:
        request = request_for(arguments, forced_command)
    except forced_command.RequestRefused as refusal:
        print(f"{PROGRAM}: no request was sent, because {refusal}.", file=sys.stderr)
        print("Each word must be made of letters, digits and _ . / : = @ % + , - and the first may not start with '-'.", file=sys.stderr)
        print("If the command needs shell syntax or quoted words, put it in a script on ned-box and pass that script's path.", file=sys.stderr)
        return EXIT_USAGE_OR_REFUSED
    destination = os.environ.get("NEDSCHORUS_MAC_SSH_DESTINATION") or DEFAULT_MAC_SSH_DESTINATION
    ssh_program = os.environ.get("NEDSCHORUS_SSH_PROGRAM") or "ssh"
    try:
        result = subprocess.run(ssh_command(request, destination, ssh_program), capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        print(f"{PROGRAM}: ssh to the Mac at {destination} did not finish within 60 seconds, so the window may not have opened.", file=sys.stderr)
        print("Tell the user the command you wanted shown.", file=sys.stderr)
        return EXIT_NOT_OPENED
    if result.returncode == SSH_EXIT_CONNECTION_FAILED:
        for line in explain_connection_failure(result.stderr, destination):
            print(line, file=sys.stderr)
        return EXIT_NOT_OPENED
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    if result.returncode == forced_command.EXIT_REFUSED:
        return EXIT_USAGE_OR_REFUSED
    return EXIT_OPENED if result.returncode == 0 else EXIT_NOT_OPENED


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
