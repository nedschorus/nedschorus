#!/usr/bin/env python3
"""Tests for open-mac-window-from-ned-box.py.

ssh is replaced by a stub (NEDSCHORUS_SSH_PROGRAM) that records its arguments
and answers as told, so no test connects to the Mac. The round-trip cases make
the stub play sshd: it runs the Mac's forced command with SSH_ORIGINAL_COMMAND
set to the request, and a stub opener records what window would open.

Run: python3 scripts/open-mac-window-from-ned-box-test.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CALLER_PATH = Path(__file__).with_name("open-mac-window-from-ned-box.py")
FORCED_COMMAND_PATH = Path(__file__).with_name("mac-window-opened-for-ned-box-forced-command.py")

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def run_caller(arguments, ssh_body=None, destination=None, play_sshd=False):
    scratch = Path(tempfile.mkdtemp(prefix="open-mac-window-test-"))
    record = scratch / "ssh-arguments.json"
    opened_record = scratch / "opener-arguments.json"
    stub = scratch / "ssh-stub"
    lines = ["#!/bin/sh", f"""python3 -c 'import json,sys; json.dump(sys.argv[1:], open("{record}","w"))' "$@" """]
    if play_sshd:
        opener = scratch / "opener-stub"
        opener.write_text(f"""python3 -c 'import json,sys; json.dump(sys.argv[1:], open("{opened_record}","w"))' "$@"\n""")
        lines.append('for last; do :; done')
        lines.append(f'SSH_ORIGINAL_COMMAND="$last" NEDSCHORUS_MAC_WINDOW_OPENER="{opener}" HOME="{scratch}" exec "{sys.executable}" "{FORCED_COMMAND_PATH}"')
    else:
        lines.append(ssh_body or "exit 0")
    stub.write_text("\n".join(lines) + "\n")
    stub.chmod(0o755)
    environment = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(scratch), "NEDSCHORUS_SSH_PROGRAM": str(stub)}
    if destination:
        environment["NEDSCHORUS_MAC_SSH_DESTINATION"] = destination
    result = subprocess.run([sys.executable, str(CALLER_PATH), *arguments], capture_output=True, text=True, env=environment)
    sent = json.loads(record.read_text()) if record.exists() else None
    opened = json.loads(opened_record.read_text()) if opened_record.exists() else None
    shutil.rmtree(scratch)
    return result, sent, opened


result, sent, _ = run_caller([])
check("no arguments is a usage error, and nothing is sent", result.returncode == 2 and "usage:" in result.stderr and sent is None, result.stderr)

result, sent, _ = run_caller(["tmux", "attach", "-t", "merge-lane-2"], ssh_body="echo opened; exit 0")
check("the request travels as one remote-command argument, after '--' and the destination",
      sent is not None and sent[-3:] == ["--", "el@10.0.1.23", "open-window tmux attach -t merge-lane-2"], sent)
check("ssh uses only the Mac-side-action key, never prompts, and gives up on a dead link",
      sent is not None and sent[0] == "-i" and sent[1].endswith("/.ssh/id_ed25519_mac_side_action")
      and "IdentitiesOnly=yes" in sent and "BatchMode=yes" in sent and "ConnectTimeout=10" in sent, sent)
check("a window the Mac opened exits 0 and passes the Mac's output on", result.returncode == 0 and "opened" in result.stdout, result)

result, sent, _ = run_caller(["tmux"], destination="el@10.0.1.99")
check("the destination can be overridden", sent is not None and "el@10.0.1.99" in sent, sent)

for words in (["tmux;", "rm"], ["echo", "$HOME"], ["it's"], [""], ["-oProxyCommand=/usr/bin/true"], ["a b"], ["tmux", "a\nb"]):
    result, sent, _ = run_caller(words)
    check(f"words the Mac would refuse are refused here, and nothing is sent: {words!r}",
          result.returncode == 2 and sent is None and "no request was sent, because" in result.stderr, (result.returncode, sent, result.stderr))

result, sent, _ = run_caller(["tmux"], ssh_body="echo 'el@10.0.1.23: Permission denied (publickey).' >&2; exit 255")
check("a refused key says the Mac does not admit it yet, and to tell the user",
      result.returncode == 1 and "does not admit this key yet" in result.stderr, result.stderr)

result, sent, _ = run_caller(["tmux"], ssh_body="echo 'Host key verification failed.' >&2; exit 255")
check("an unknown host key names the one-time ssh-keyscan step",
      result.returncode == 1 and "ssh-keyscan -t ed25519 10.0.1.23 >> ~/.ssh/known_hosts" in result.stderr, result.stderr)

result, sent, _ = run_caller(["tmux"], ssh_body="echo 'ssh: connect to host 10.0.1.23 port 22: Operation timed out' >&2; exit 255")
check("an unreachable Mac says so, with ssh's own error",
      result.returncode == 1 and "could not reach the Mac" in result.stderr and "Operation timed out" in result.stderr, result.stderr)

result, sent, _ = run_caller(["tmux"], ssh_body="echo 'refused for a reason' >&2; exit 2")
check("a refusal from the Mac exits 2 and passes the Mac's reason on", result.returncode == 2 and "refused for a reason" in result.stderr, result)

for words in (["tmux", "attach", "-t", "merge-lane-2"],
              ["git", "-C", "/home/nedlern/Projects/nedschorus", "log", "--oneline", "-5"],
              ["less", "/home/nedlern/nedschorus-logs/walk/x-minutes.md"]):
    result, sent, opened = run_caller(words, play_sshd=True)
    check(f"round trip: the Mac opens a window running exactly these words on ned-box: {words!r}",
          result.returncode == 0 and opened == ["ssh", "-t", "--", "nedlern@ned-box", *words], (result.returncode, opened, result.stderr))

print()
if failures:
    print(f"{len(failures)} case(s) failed")
    sys.exit(1)
print("all cases passed")
