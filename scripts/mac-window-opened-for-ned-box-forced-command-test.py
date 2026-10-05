#!/usr/bin/env python3
"""Tests for mac-window-opened-for-ned-box-forced-command.py.

No test opens a real window: the opener is replaced by a stub that records its
arguments (NEDSCHORUS_MAC_WINDOW_OPENER), or the real opener runs in its dry-run
mode, which prints the AppleScript instead of running it. HOME points at a
scratch directory, so the request log is written there.

Run: python3 scripts/mac-window-opened-for-ned-box-forced-command-test.py
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROGRAM_PATH = Path(__file__).with_name("mac-window-opened-for-ned-box-forced-command.py")
REAL_OPENER = Path(__file__).with_name("open-iterm-window-running-command")

specification = importlib.util.spec_from_file_location("forced_command", PROGRAM_PATH)
forced_command = importlib.util.module_from_spec(specification)
specification.loader.exec_module(forced_command)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def refusal_of(request):
    try:
        forced_command.window_command_words(request)
    except forced_command.RequestRefused as refusal:
        return str(refusal)
    return None


ACCEPTED = {
    "open-window tmux attach -t merge-lane-2": ["tmux", "attach", "-t", "merge-lane-2"],
    "open-window less /home/nedlern/nedschorus-logs/walk/a-minutes.md": ["less", "/home/nedlern/nedschorus-logs/walk/a-minutes.md"],
    "open-window git -C /home/nedlern/Projects/nedschorus diff origin/main -- scripts/a.py":
        ["git", "-C", "/home/nedlern/Projects/nedschorus", "diff", "origin/main", "--", "scripts/a.py"],
    "open-window tail -n 100 -f run.log": ["tail", "-n", "100", "-f", "run.log"],
    "open-window env A=1 B=x,y prog --flag=%s user@host:path +5": ["env", "A=1", "B=x,y", "prog", "--flag=%s", "user@host:path", "+5"],
    "open-window true -oProxyCommand=/usr/bin/true": ["true", "-oProxyCommand=/usr/bin/true"],
}
for request, words in ACCEPTED.items():
    result = None
    try:
        result = forced_command.window_command_words(request)
    except forced_command.RequestRefused as refusal:
        result = f"refused: {refusal}"
    check(f"accepted: {request!r}", result == words, result)

REFUSED = {
    "no SSH_ORIGINAL_COMMAND (an interactive login)": (None, "interactive shell"),
    "an empty request": ("", "empty"),
    "a request with no verb": ("tmux attach", "does not start with the verb"),
    "a verb that only starts like the verb": ("open-windows tmux", "does not start with the verb"),
    "the verb alone": ("open-window", "names no command"),
    "the verb and a trailing space": ("open-window ", "word 1 is empty"),
    "a leading space": (" open-window tmux", "does not start with the verb"),
    "two spaces between words": ("open-window tmux  attach", "word 2 is empty"),
    "a first word starting with '-'": ("open-window -oProxyCommand=/usr/bin/true", "starts with '-'"),
    "a first word that is only '-'": ("open-window - x", "starts with '-'"),
    "too many words": ("open-window " + " ".join(["w"] * (forced_command.MAXIMUM_WORD_COUNT + 1)), "over the limit of"),
    "an overlong word": ("open-window " + "a" * (forced_command.MAXIMUM_WORD_LENGTH + 1), "over the limit of"),
    "an overlong request": ("open-window " + " ".join(["a" * 200] * 11), "characters, over the limit"),
}
for character_name, character in {
    "a semicolon": ";", "a pipe": "|", "an ampersand": "&", "a dollar sign": "$", "a backtick": "`",
    "a single quote": "'", "a double quote": '"', "a backslash": "\\", "a less-than": "<", "a greater-than": ">",
    "an asterisk": "*", "a question mark": "?", "a bracket": "[", "a tilde": "~", "a parenthesis": "(",
    "a brace": "{", "an exclamation mark": "!", "a hash": "#", "a tab": "\t", "a newline": "\n",
    "a carriage return": "\r", "a NUL": "\x00", "a non-ASCII letter": "é", "a non-breaking space": " ",
}.items():
    REFUSED[f"a word holding {character_name}"] = (f"open-window tmux a{character}b", "outside letters, digits")
for case_name, (request, expected) in REFUSED.items():
    reason = refusal_of(request)
    check(f"refused: {case_name}", reason is not None and expected in reason, reason)

check("a request at exactly the word limit is accepted",
      refusal_of("open-window " + " ".join(["w"] * forced_command.MAXIMUM_WORD_COUNT)) is None)
check("a word at exactly the length limit is accepted",
      refusal_of("open-window " + "a" * forced_command.MAXIMUM_WORD_LENGTH) is None)

check("the window command ends option parsing before the destination",
      forced_command.window_command(["tmux"]) == ["ssh", "-t", "--", "nedlern@ned-box", "tmux"],
      forced_command.window_command(["tmux"]))

if shutil.which("ssh"):
    # ssh -G prints the configuration a command line would use, without connecting.
    # The first-word rule refuses this request; building the command line directly
    # shows that '--' alone would also stop it.
    window = forced_command.window_command(["-oProxyCommand=/usr/bin/true", "true"])
    printed = subprocess.run(["ssh", "-G", *window[1:]], capture_output=True, text=True)
    check("after '--', ssh does not read a word after the destination as an option",
          printed.returncode == 0 and "proxycommand /usr/bin/true" not in printed.stdout.lower(),
          printed.stdout[-400:] + printed.stderr)
    unguarded = subprocess.run(["ssh", "-G", "-t", "nedlern@ned-box", "-oProxyCommand=/usr/bin/true", "true"],
                               capture_output=True, text=True)
    check("without '--', this ssh reads a word right after the destination as an option (the reason for both guards)",
          "proxycommand /usr/bin/true" in unguarded.stdout.lower(), unguarded.stdout[-400:])
else:
    print("SKIP  ssh option-parsing cases: ssh is not on PATH")


def run_program(request, opener_body=None, use_real_opener=False, log_unwritable=False):
    scratch = Path(tempfile.mkdtemp(prefix="mac-window-test-"))
    if log_unwritable:
        (scratch / ".claude").write_text("a regular file where the log's directory belongs\n")
    environment = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(scratch), "SHELL": "/bin/zsh"}
    if request is not None:
        environment["SSH_ORIGINAL_COMMAND"] = request
    record = scratch / "opener-arguments.json"
    if use_real_opener:
        environment["NEDSCHORUS_MAC_WINDOW_OPENER"] = str(REAL_OPENER)
        environment["OPEN_ITERM_WINDOW_DRY_RUN"] = "1"
    else:
        stub = scratch / "opener-stub"
        stub.write_text(opener_body or f"""python3 -c 'import json,sys; json.dump(sys.argv[1:], open("{record}","w"))' "$@"\n""")
        environment["NEDSCHORUS_MAC_WINDOW_OPENER"] = str(stub)
    result = subprocess.run([sys.executable, str(PROGRAM_PATH)], capture_output=True, text=True, env=environment)
    opened = json.loads(record.read_text()) if record.exists() else None
    log_path = scratch / ".claude" / "mac-window-opened-for-ned-box.log"
    log = log_path.read_text() if log_path.is_file() else ""
    shutil.rmtree(scratch)
    return result, opened, log


result, opened, log = run_program("open-window tmux attach -t merge-lane-2")
check("an accepted request exits 0", result.returncode == 0, result.stderr)
check("an accepted request hands the opener ssh back to ned-box, word for word",
      opened == ["ssh", "-t", "--", "nedlern@ned-box", "tmux", "attach", "-t", "merge-lane-2"], opened)
check("an accepted request is logged as opened", " opened 'open-window tmux attach -t merge-lane-2'" in log, log)
check("an accepted request is logged before its window opens",
      log.index(" accepted 'open-window tmux attach -t merge-lane-2'") < log.index(" opened "), log)
check("an accepted request says what the window runs",
      "opened a window on the Mac running: ssh -t -- nedlern@ned-box tmux attach -t merge-lane-2" in result.stdout, result.stdout)

for request in ["tmux; open -a Calculator", "open-window tmux; rm -rf ~", "open-window $(touch /tmp/x)", None,
                "open-window -oProxyCommand=/usr/bin/true"]:
    result, opened, log = run_program(request)
    check(f"a refused request opens nothing: {request!r}", opened is None, opened)
    check(f"a refused request exits 2: {request!r}", result.returncode == 2, result.returncode)
    check(f"a refused request says no window was opened, and why: {request!r}",
          "no window was opened, because" in result.stderr and "Send a request of the form" in result.stderr, result.stderr)
    check(f"a refused request is logged as refused: {request!r}", " refused " in log, log)

result, opened, log = run_program("open-window tmux", opener_body="echo 'osascript failed' >&2; exit 1\n")
check("an opener failure exits 1", result.returncode == 1, result.returncode)
check("an opener failure is reported with the opener's own error",
      "the window opener exited 1" in result.stderr and "osascript failed" in result.stderr, result.stderr)
check("an opener failure is logged", "opener-failed-1" in log, log)

result, opened, log = run_program("open-window tmux attach -t merge-lane-2", log_unwritable=True)
check("a request that cannot be logged opens no window", opened is None, opened)
check("a request that cannot be logged exits 3", result.returncode == 3, result.returncode)
check("a request that cannot be logged says so, and why no window opened",
      "no window was opened, because the request could not be added to the request log" in result.stderr
      and "none opens unlogged" in result.stderr, result.stderr)

result, opened, log = run_program("open-window tmux; rm -rf ~", log_unwritable=True)
check("a refusal that cannot be logged still refuses, exits 2, and reports the log failure",
      opened is None and result.returncode == 2 and "could not be added to the request log" in result.stderr, result.stderr)

result, opened, log = run_program(
    "open-window tmux",
    opener_body='chmod 0444 "$HOME/.claude/mac-window-opened-for-ned-box.log"; echo opener-ran\n')
check("an outcome line that cannot be written still exits 0, since the window opened",
      result.returncode == 0 and "opener-ran" in result.stdout, (result.returncode, result.stdout, result.stderr))
check("an outcome line that cannot be written is reported, with the instruction not to ask again",
      "the window opened, but its outcome could not be added to the request log" in result.stderr
      and "Do not ask for the window again" in result.stderr, result.stderr)

result, opened, log = run_program(
    "open-window tmux",
    opener_body='chmod 0444 "$HOME/.claude/mac-window-opened-for-ned-box.log"; echo \'osascript failed\' >&2; exit 1\n')
check("an opener failure that cannot be logged still exits 1, with the opener's own error",
      result.returncode == 1 and "the window opener exited 1" in result.stderr and "osascript failed" in result.stderr,
      (result.returncode, result.stderr))
check("an opener failure that cannot be logged reports the failed log write",
      "The opener's failure could not be added to the request log" in result.stderr, result.stderr)

result, opened, log = run_program("open-window tmux attach -t merge-lane-2", use_real_opener=True)
check("through the real opener's dry run, the AppleScript runs ssh back to ned-box",
      result.returncode == 0 and "open-iterm-window-running-command ssh -t -- nedlern@ned-box tmux attach -t merge-lane-2" in result.stdout,
      result.stdout + result.stderr)

result, opened, log = run_program("open-in-typora tmux")
check("an open-in-typora request opens no window", opened is None, opened)
check("a window request that is refused names the open-in-typora form too",
      "To open a file in Typora instead, run on ned-box: scripts/open-file-in-typora-on-mac-from-ned-box.py" in run_program("open-windowx tmux")[0].stderr)


def typora_refusal_of(request, ned_box_home="/home/nedlern"):
    try:
        forced_command.typora_path_on_ned_box(request, ned_box_home)
    except forced_command.RequestRefused as refusal:
        return str(refusal)
    return None


for request in ["open-in-typora /home/nedlern/nedschorus-logs/walk/a-minutes.md",
                "open-in-typora /home/nedlern/a.md",
                "open-in-typora /home/nedlern/Projects/nedschorus/docs/x_y.z,v=1@2+3%4:5.md"]:
    check(f"typora accepted: {request!r}", typora_refusal_of(request) is None, typora_refusal_of(request))

TYPORA_REFUSED = {
    "no SSH_ORIGINAL_COMMAND": (None, "interactive shell"),
    "another verb": ("open-window /home/nedlern/a.md", "does not start with the verb 'open-in-typora'"),
    "the verb alone": ("open-in-typora", "exactly one path"),
    "an empty path": ("open-in-typora ", "names no path"),
    "two paths": ("open-in-typora /home/nedlern/a.md /home/nedlern/b.md", "exactly one path"),
    "a path with a space": ("open-in-typora /home/nedlern/a b.md", "exactly one path"),
    "a relative path": ("open-in-typora a.md", "not under /home/nedlern/"),
    "a path outside the home": ("open-in-typora /etc/passwd", "not under /home/nedlern/"),
    "a home that only starts like the home": ("open-in-typora /home/nedlernx/a.md", "not under /home/nedlern/"),
    "the home itself": ("open-in-typora /home/nedlern", "not under /home/nedlern/"),
    "a '..' component": ("open-in-typora /home/nedlern/../../etc/passwd", "'..' component"),
    "a '..' deeper in": ("open-in-typora /home/nedlern/a/../../b.md", "'..' component"),
    "a '.' component": ("open-in-typora /home/nedlern/./a.md", "'..' component"),
    "an empty component": ("open-in-typora /home/nedlern//a.md", "'..' component"),
    "a trailing slash": ("open-in-typora /home/nedlern/docs/", "'..' component"),
    "a NUL": ("open-in-typora /home/nedlern/a\x00.md", "outside letters, digits"),
    "a newline": ("open-in-typora /home/nedlern/a\n.md", "outside letters, digits"),
    "a semicolon": ("open-in-typora /home/nedlern/a;b.md", "outside letters, digits"),
    "a quote": ("open-in-typora /home/nedlern/a'b.md", "outside letters, digits"),
    "an overlong path": ("open-in-typora /home/nedlern/" + "a" * forced_command.MAXIMUM_PATH_LENGTH, "over the limit of"),
}
for case_name, (request, expected) in TYPORA_REFUSED.items():
    reason = typora_refusal_of(request)
    check(f"typora refused: {case_name}", reason is not None and expected in reason, reason)

for length, accepted in ((forced_command.MAXIMUM_PATH_LENGTH - 1, True), (forced_command.MAXIMUM_PATH_LENGTH, True),
                         (forced_command.MAXIMUM_PATH_LENGTH + 1, False)):
    path = "/home/nedlern/" + "a" * (length - len("/home/nedlern/"))
    reason = typora_refusal_of(f"open-in-typora {path}")
    check(f"typora: a path of {length} characters is {'accepted' if accepted else 'refused'}",
          (reason is None) if accepted else (reason is not None and "over the limit of" in reason), reason)
check("typora: the path limit is 1024 characters", forced_command.MAXIMUM_PATH_LENGTH == 1024, forced_command.MAXIMUM_PATH_LENGTH)


def writable_mount_point():
    """A real mount point this test may write inside, and the directory to write in."""
    for mount, writable_inside in (("/dev/shm", "/dev/shm"), ("/System/Volumes/Data", "/System/Volumes/Data/private/tmp")):
        if os.path.ismount(mount) and os.access(writable_inside, os.W_OK):
            return mount, writable_inside
    return None, None


def run_typora(request, home, mount, open_body=None, log_unwritable=False):
    scratch = Path(tempfile.mkdtemp(prefix="mac-typora-test-"))
    if log_unwritable:
        (scratch / ".claude").write_text("a regular file where the log's directory belongs\n")
    record = scratch / "open-arguments.json"
    stub = scratch / "open-stub"
    stub.write_text("#!/bin/sh\n" + (open_body or f"""python3 -c 'import json,sys; json.dump(sys.argv[1:], open("{record}","w"))' "$@"\n"""))
    stub.chmod(0o755)
    environment = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(scratch), "SSH_ORIGINAL_COMMAND": request,
                   "NEDSCHORUS_MAC_OPEN_PROGRAM": str(stub), "NEDSCHORUS_NED_BOX_HOME": home,
                   "NEDSCHORUS_MAC_NED_BOX_HOME_MOUNT": mount,
                   "NEDSCHORUS_MAC_WINDOW_OPENER": str(scratch / "no-window-opener-must-run")}
    result = subprocess.run([sys.executable, str(PROGRAM_PATH)], capture_output=True, text=True, env=environment)
    opened = json.loads(record.read_text()) if record.exists() else None
    log_path = scratch / ".claude" / "mac-window-opened-for-ned-box.log"
    log = log_path.read_text() if log_path.is_file() else ""
    shutil.rmtree(scratch)
    return result, opened, log


mount, writable_inside = writable_mount_point()
if mount is None:
    print("SKIP  open-in-typora end-to-end cases: no writable mount point (/dev/shm or /System/Volumes/Data) on this machine")
else:
    # ned-box's home and the Mac's mount are both the same real mount point, so a
    # path maps onto itself and the mount check sees a real mount.
    files = Path(tempfile.mkdtemp(prefix="mac-typora-files-", dir=writable_inside))
    document = files / "notes.md"
    document.write_text("# notes\n")
    (files / "folder").mkdir()
    (files / "escape.md").symlink_to("/etc/hosts")
    (files / "inside-link.md").symlink_to(document)
    # The unmounted stand-in holds the same file, so only the mount check can refuse it.
    not_mounted = Path(tempfile.mkdtemp(prefix="mac-typora-not-mounted-"))
    (not_mounted / document.relative_to(mount)).parent.mkdir(parents=True)
    (not_mounted / document.relative_to(mount)).write_text("# notes\n")

    result, opened, log = run_typora(f"open-in-typora {document}", mount, mount)
    check("typora: an accepted file exits 0", result.returncode == 0, result.stderr)
    check("typora: open gets an argument list naming Typora and the mapped file",
          opened == ["-a", "Typora", str(document)], opened)
    check("typora: an accepted file says what was opened",
          f"opened {document} in Typora on the Mac" in result.stdout, result.stdout)
    check("typora: an accepted file is logged before it opens",
          f" accepted 'open-in-typora {document}'" in log and log.index(" accepted ") < log.index(" opened "), log)

    # ned-box's home and the Mac's mount differ here, and the file exists only under
    # the mount, so the file is found only if the path is mapped onto the mount.
    stand_in_home = "/nedbox-home-stand-in-that-does-not-exist"
    relative = document.relative_to(mount)
    result, opened, log = run_typora(f"open-in-typora {stand_in_home}/{relative}", stand_in_home, mount)
    check("typora: a ned-box path is mapped onto the Mac's mount, and open gets the mapped path",
          result.returncode == 0 and opened == ["-a", "Typora", str(document)], (result.returncode, opened, result.stderr))

    result, opened, log = run_typora(f"open-in-typora {document}", mount, mount, open_body="kill -9 $$\n")
    check("typora: an open killed by a signal is reported as failed, not opened",
          result.returncode == 1 and "open exited -9" in result.stderr and "opened " not in result.stdout,
          (result.returncode, result.stdout, result.stderr))
    check("typora: an open killed by a signal is logged as failed", "open-failed--9" in log, log)

    result, opened, log = run_typora(f"open-in-typora {files / 'inside-link.md'}", mount, mount)
    check("typora: a link that stays inside the mount is opened", result.returncode == 0 and opened is not None, result.stderr)

    for case_name, request, mount_used, expected in [
        ("a missing file", f"open-in-typora {files / 'absent.md'}", mount, "there is no"),
        ("a folder", f"open-in-typora {files / 'folder'}", mount, "is not a file"),
        ("a link leading outside the mount", f"open-in-typora {files / 'escape.md'}", mount, "leads outside"),
        ("an unmounted mount", f"open-in-typora {document}", str(not_mounted), "the Mac's mount of ned-box's home, is not mounted"),
        ("a '..' path", f"open-in-typora {mount}/../etc/passwd", mount, "'..' component"),
        ("two paths", f"open-in-typora {document} {document}", mount, "exactly one path"),
    ]:
        result, opened, log = run_typora(request, mount, mount_used)
        check(f"typora: {case_name} opens nothing", opened is None, opened)
        check(f"typora: {case_name} exits 2 and says why", result.returncode == 2 and expected in result.stderr
              and "Typora was not opened, because" in result.stderr, (result.returncode, result.stderr))
        check(f"typora: {case_name} is logged as refused", " refused " in log, log)

    result, opened, log = run_typora(f"open-in-typora {document}", mount, mount,
                                     open_body="echo 'Unable to find application named Typora' >&2; exit 1\n")
    check("typora: an open that fails exits 1 with open's own error and the Typora hint",
          result.returncode == 1 and "Unable to find application named Typora" in result.stderr
          and "Typora is not installed" in result.stderr and "Whatever the error, tell the user" in result.stderr, result.stderr)
    check("typora: an open that fails is logged", "open-failed-1" in log, log)

    result, opened, log = run_typora(f"open-in-typora {document}", mount, mount, log_unwritable=True)
    check("typora: a request that cannot be logged opens nothing and exits 3",
          opened is None and result.returncode == 3 and "none opens unlogged" in result.stderr, (result.returncode, result.stderr))

    shutil.rmtree(files)
    shutil.rmtree(not_mounted)

print()
if failures:
    print(f"{len(failures)} case(s) failed")
    sys.exit(1)
print("all cases passed")
