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

result, opened, log = run_program("open-window tmux attach -t merge-lane-2", use_real_opener=True)
check("through the real opener's dry run, the AppleScript runs ssh back to ned-box",
      result.returncode == 0 and "open-iterm-window-running-command ssh -t -- nedlern@ned-box tmux attach -t merge-lane-2" in result.stdout,
      result.stdout + result.stderr)

print()
if failures:
    print(f"{len(failures)} case(s) failed")
    sys.exit(1)
print("all cases passed")
