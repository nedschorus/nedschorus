#!/usr/bin/env python3
"""Tests for open-html-page-in-mac-browser-from-ned-box.py.

ssh is replaced by a stub (NEDSCHORUS_SSH_PROGRAM) that records its arguments
and answers as told, so no test connects to the Mac. ned-box's home is a
scratch directory (NEDSCHORUS_NED_BOX_HOME). The round-trip case makes the stub
play sshd: it runs the Mac's forced command with SSH_ORIGINAL_COMMAND set to
the request, ned-box's home and the Mac's mount both set to one real mount
point, and a stub `open` that records what it was asked to open.

Run: python3 scripts/open-html-page-in-mac-browser-from-ned-box-test.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CALLER_PATH = Path(__file__).with_name("open-html-page-in-mac-browser-from-ned-box.py")
FORCED_COMMAND_PATH = Path(__file__).with_name("mac-window-opened-for-ned-box-forced-command.py")

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def run_caller(arguments, home, ssh_body=None, play_sshd_with_mount=None, timeout_seconds=None, cwd=None):
    scratch = Path(tempfile.mkdtemp(prefix="open-browser-test-"))
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


home = Path(os.path.realpath(tempfile.mkdtemp(prefix="open-browser-home-")))
pages = home / "nedschorus-logs" / "notices"
pages.mkdir(parents=True)
page = pages / "notice.html"
page.write_text("<!doctype html>\n")
(pages / "notes.md").write_text("# notes\n")
(home / "outside-the-log-store.html").write_text("<!doctype html>\n")
(pages / "link-out.html").symlink_to(home / "outside-the-log-store.html")
(pages / "a b.html").write_text("<!doctype html>\n")

for arguments, case_name in (([], "no path"), ([str(page), str(page)], "two paths")):
    result, sent, _ = run_caller(arguments, home)
    check(f"{case_name} is a usage error, and nothing is sent", result.returncode == 2 and "usage:" in result.stderr and sent is None,
          (result.returncode, result.stderr))

result, sent, _ = run_caller([str(page)], home, ssh_body="echo 'opened it'; exit 0")
check("the request travels as one remote-command argument: the verb and the absolute path",
      sent is not None and sent[-1] == f"open-in-browser {page}" and sent[-2] == "el@edwards-macbook-air.local" and sent[-3] == "--", sent)
check("a page the Mac opened exits 0 and passes the Mac's output on", result.returncode == 0 and "opened it" in result.stdout, result)

result, sent, _ = run_caller(["notice.html"], home, cwd=str(pages))
check("a relative path is sent as its absolute path", sent is not None and sent[-1] == f"open-in-browser {page}", sent)

for arguments, case_name, expected in (
        ([str(pages / "absent.html")], "a missing page", "is not a file on ned-box"),
        ([str(pages / "notes.md")], "a file that is not .html", "does not end in .html"),
        ([str(home / "outside-the-log-store.html")], "a page outside the log-store", "write the page there"),
        ([str(pages / "link-out.html")], "a link in the log-store that leads out of it", "write the page there"),
        ([str(pages / "a b.html")], "a name with a space", "such as a space"),
):
    result, sent, _ = run_caller(arguments, home)
    check(f"{case_name} is refused here, and nothing is sent",
          result.returncode == 2 and sent is None and "no request was sent, because" in result.stderr and expected in result.stderr,
          (result.returncode, sent, result.stderr))

result, sent, _ = run_caller([str(page)], home, ssh_body="echo 'ssh: connect to host edwards-macbook-air.local port 22: Operation timed out' >&2; exit 255")
check("an unreachable Mac exits 1 and says so, with the page's path on the Mac to tell the user",
      result.returncode == 1 and "could not reach the Mac" in result.stderr and "so the page was not opened" in result.stderr
      and f"which is /Volumes/nedhome/{page.relative_to(home)} on the Mac" in result.stderr, result.stderr)

result, sent, _ = run_caller([str(page)], home, ssh_body="echo 'refused for a reason' >&2; exit 2")
check("a refusal from the Mac exits 2 and passes the Mac's reason on", result.returncode == 2 and "refused for a reason" in result.stderr, result)

result, sent, _ = run_caller([str(page)], home, ssh_body="sleep 5", timeout_seconds=0.5)
check("an ssh that does not finish in time exits 1 and says the page may not have opened",
      result.returncode == 1 and "so the page may not have opened" in result.stderr, (result.returncode, result.stderr))

mount = None
for candidate, writable_inside in (("/dev/shm", "/dev/shm"), ("/System/Volumes/Data", "/System/Volumes/Data/private/tmp")):
    if os.path.ismount(candidate) and os.access(writable_inside, os.W_OK):
        mount = candidate
        break
if mount is None or not os.access(mount, os.W_OK):
    # The log-store must sit at the stand-in mount's top, which the Mac's /System/Volumes/Data does not let the user write.
    print("SKIP  round-trip case: they need a mount point whose top directory this user can write, "
          "to stand in for the Mac's mount of ned-box's home, and this machine has none; "
          "/dev/shm is one on Linux")
else:
    log_store = Path(mount) / "nedschorus-logs"
    # Shared with the other browser suite, which may run at the same time, so it is
    # created if missing and never removed: each suite removes only its own directory in it.
    log_store.mkdir(exist_ok=True)
    files = Path(tempfile.mkdtemp(prefix="open-browser-round-trip-", dir=log_store))
    round_trip_page = files / "notice.html"
    round_trip_page.write_text("<!doctype html>\n")
    result, sent, opened = run_caller([str(round_trip_page)], Path(mount), play_sshd_with_mount=mount)
    check("round trip: the Mac's forced command runs open on exactly this page",
          result.returncode == 0 and opened == [str(round_trip_page)], (result.returncode, opened, result.stderr))
    check("round trip: the Mac's confirmation reaches the caller",
          f"opened {round_trip_page} in the Mac's browser" in result.stdout, result.stdout)
    shutil.rmtree(files)

shutil.rmtree(home)

print()
if failures:
    print(f"{len(failures)} case(s) failed")
    sys.exit(1)
print("all cases passed")
