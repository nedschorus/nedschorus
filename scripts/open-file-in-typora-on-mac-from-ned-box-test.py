#!/usr/bin/env python3
"""Tests for open-file-in-typora-on-mac-from-ned-box.py.

ssh is replaced by a stub (NEDSCHORUS_SSH_PROGRAM) that records its arguments
and answers as told, so no test connects to the Mac. ned-box's home is a
scratch directory (NEDSCHORUS_NED_BOX_HOME). The round-trip cases make the stub
play sshd: it runs the Mac's forced command with SSH_ORIGINAL_COMMAND set to
the request, ned-box's home and the Mac's mount both set to one real mount
point, and a stub `open` that records what it was asked to open.

Run: python3 scripts/open-file-in-typora-on-mac-from-ned-box-test.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CALLER_PATH = Path(__file__).with_name("open-file-in-typora-on-mac-from-ned-box.py")
FORCED_COMMAND_PATH = Path(__file__).with_name("mac-window-opened-for-ned-box-forced-command.py")

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def run_caller(arguments, home, ssh_body=None, play_sshd_with_mount=None, timeout_seconds=None, cwd=None):
    scratch = Path(tempfile.mkdtemp(prefix="open-typora-test-"))
    record = scratch / "ssh-arguments.json"
    open_record = scratch / "open-arguments.json"
    stub = scratch / "ssh-stub"
    lines = ["#!/bin/sh", f"""python3 -c 'import json,sys; json.dump(sys.argv[1:], open("{record}","w"))' "$@" """]
    if play_sshd_with_mount:
        open_stub = scratch / "open-stub"
        open_stub.write_text(f"""#!/bin/sh\npython3 -c 'import json,sys; json.dump(sys.argv[1:], open("{open_record}","w"))' "$@"\n""")
        open_stub.chmod(0o755)
        lines.append('for last; do :; done')
        lines.append(f'SSH_ORIGINAL_COMMAND="$last" NEDSCHORUS_MAC_OPEN_PROGRAM="{open_stub}" NEDSCHORUS_NED_BOX_HOME="{play_sshd_with_mount}" '
                     f'NEDSCHORUS_MAC_NED_BOX_HOME_MOUNT="{play_sshd_with_mount}" HOME="{scratch}" exec "{sys.executable}" "{FORCED_COMMAND_PATH}"')
    else:
        lines.append(ssh_body or "exit 0")
    stub.write_text("\n".join(lines) + "\n")
    stub.chmod(0o755)
    environment = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(scratch), "NEDSCHORUS_SSH_PROGRAM": str(stub),
                   "NEDSCHORUS_NED_BOX_HOME": str(home)}
    if timeout_seconds:
        environment["NEDSCHORUS_MAC_SSH_TIMEOUT_SECONDS"] = str(timeout_seconds)
    result = subprocess.run([sys.executable, str(CALLER_PATH), *arguments], capture_output=True, text=True, env=environment,
                            cwd=cwd)
    sent = json.loads(record.read_text()) if record.exists() else None
    opened = json.loads(open_record.read_text()) if open_record.exists() else None
    shutil.rmtree(scratch)
    return result, sent, opened


home = Path(os.path.realpath(tempfile.mkdtemp(prefix="open-typora-home-")))
document = home / "docs" / "notes.md"
document.parent.mkdir()
document.write_text("# notes\n")
outside = Path(os.path.realpath(tempfile.mkdtemp(prefix="open-typora-outside-")))
(outside / "secret.md").write_text("outside\n")
(home / "link-out.md").symlink_to(outside / "secret.md")
(home / "a b.md").write_text("spaced\n")

for arguments, case_name in (([], "no path"), ([str(document), str(document)], "two paths")):
    result, sent, _ = run_caller(arguments, home)
    check(f"{case_name} is a usage error, and nothing is sent", result.returncode == 2 and "usage:" in result.stderr and sent is None,
          (result.returncode, result.stderr))

result, sent, _ = run_caller([str(document)], home, ssh_body="echo 'opened it'; exit 0")
check("the request travels as one remote-command argument: the verb and the absolute path",
      sent is not None and sent[-1] == f"open-in-typora {document}" and sent[-2] == "el@10.0.1.23" and sent[-3] == "--", sent)
check("ssh uses only the Mac-side-action key, never prompts, and gives up on a dead link",
      sent is not None and sent[1].endswith("/.ssh/id_ed25519_mac_side_action")
      and "IdentitiesOnly=yes" in sent and "BatchMode=yes" in sent and "ConnectTimeout=10" in sent, sent)
check("a file the Mac opened exits 0 and passes the Mac's output on", result.returncode == 0 and "opened it" in result.stdout, result)

result, sent, _ = run_caller(["notes.md"], home, cwd=str(document.parent))
check("a relative path is sent as its absolute path", sent is not None and sent[-1] == f"open-in-typora {document}", sent)

for arguments, case_name, expected in (
        ([str(home / "absent.md")], "a missing file", "is not a file on ned-box"),
        ([str(document.parent)], "a folder", "is not a file on ned-box"),
        ([str(outside / "secret.md")], "a file outside the home", "copy the file there"),
        ([str(home / "link-out.md")], "a link inside the home that leads outside it", "copy the file there"),
        ([str(home / "a b.md")], "a name with a space", "such as a space"),
):
    result, sent, _ = run_caller(arguments, home)
    check(f"{case_name} is refused here, and nothing is sent",
          result.returncode == 2 and sent is None and "no request was sent, because" in result.stderr and expected in result.stderr,
          (result.returncode, sent, result.stderr))

result, sent, _ = run_caller([str(document)], home, ssh_body="echo 'el@10.0.1.23: Permission denied (publickey).' >&2; exit 255")
check("a refused key says Typora was not opened, and that the Mac does not admit the key",
      result.returncode == 1 and "so Typora was not opened" in result.stderr and "does not admit this key yet" in result.stderr, result.stderr)

result, sent, _ = run_caller([str(document)], home, ssh_body="echo 'ssh: connect to host 10.0.1.23 port 22: Operation timed out' >&2; exit 255")
check("an unreachable Mac says so, with ssh's own error and the file to tell the user about",
      result.returncode == 1 and "could not reach the Mac" in result.stderr and "Operation timed out" in result.stderr
      and str(document) in result.stderr, result.stderr)

result, sent, _ = run_caller([str(document)], home, ssh_body="echo 'refused for a reason' >&2; exit 2")
check("a refusal from the Mac exits 2 and passes the Mac's reason on", result.returncode == 2 and "refused for a reason" in result.stderr, result)

result, sent, _ = run_caller([str(document)], home, ssh_body="echo 'open failed' >&2; exit 1")
check("a Mac-side failure exits 1 and passes the Mac's error on", result.returncode == 1 and "open failed" in result.stderr, result)

result, sent, _ = run_caller([str(document)], home, ssh_body="sleep 5", timeout_seconds=0.5)
check("an ssh that does not finish in time exits 1 and says Typora may not have opened the file",
      result.returncode == 1 and "so Typora may not have opened the file" in result.stderr, (result.returncode, result.stderr))

mount = None
for candidate, writable_inside in (("/dev/shm", "/dev/shm"), ("/System/Volumes/Data", "/System/Volumes/Data/private/tmp")):
    if os.path.ismount(candidate) and os.access(writable_inside, os.W_OK):
        mount = candidate
        break
if mount is None:
    print("SKIP  round-trip cases: no writable mount point (/dev/shm or /System/Volumes/Data) on this machine")
else:
    files = Path(tempfile.mkdtemp(prefix="open-typora-round-trip-", dir=writable_inside))
    round_trip_document = files / "walk-minutes.md"
    round_trip_document.write_text("# minutes\n")
    result, sent, opened = run_caller([str(round_trip_document)], Path(mount), play_sshd_with_mount=mount)
    check("round trip: the Mac's forced command runs open -a Typora on exactly this file",
          result.returncode == 0 and opened == ["-a", "Typora", str(round_trip_document)], (result.returncode, opened, result.stderr))
    check("round trip: the Mac's confirmation reaches the caller",
          f"opened {round_trip_document} in Typora on the Mac" in result.stdout, result.stdout)
    shutil.rmtree(files)

shutil.rmtree(home)
shutil.rmtree(outside)

print()
if failures:
    print(f"{len(failures)} case(s) failed")
    sys.exit(1)
print("all cases passed")
