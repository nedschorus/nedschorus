#!/usr/bin/env python3
"""PreToolUse guard: block Bash commands that send synthetic keystrokes at a
surface an operator may be typing on, and teach the safe form in the error.

The rule (nedschorus#27, learned twice on 2026-08-17): synthetic keystrokes
race the human's real ones and splice. AppleScript `write text` corrupted a
window-open command on the user's Mac while he typed; tmux `paste-buffer`
carries the same hazard for any attached session. The safe forms pass the
command as an argument — scripts/open-iterm-window-running-command for a
user-facing window, tmux new-session/respawn-pane with a command for
lifecycle — and injection into a *detached* tmux session stays permitted
until the inbox design (nedschorus#37) replaces it.

Decisions, in order:
- `osascript` together with `write text` in one command: always denied; the
  opener script fully covers the legitimate use.
- `tmux send-keys`/`paste-buffer`: allowed when every `-t` target verifiably
  has no attached client (the guard itself runs `tmux display-message -p
  '#{session_attached}'`, over ssh when the command is ssh-wrapped); denied
  with the verification recipe when a target is attached, unnamed, or
  unverifiable. A target tmux does not know is allowed — keystrokes to a
  nonexistent session type nothing, and the command fails on its own.
- `CLAUDE_VERIFIED_DETACHED=1` anywhere in the command skips the tmux check:
  the escape hatch for a caller that has just verified detachment itself
  (e.g. when this guard's own probe cannot reach the box).

Detection is literal, not adversarial: it corrects the habit of composing
these commands directly, which is the only way the failures have happened.
An invocation laundered through a generated file can slip past by design.
"""

import json
import re
import subprocess
import sys

OPENER = "scripts/open-iterm-window-running-command"

WRITE_TEXT_REASON = (
    "Blocked: AppleScript `write text` sends synthetic keystrokes, which race "
    "the user's real typing and splice (this exact failure corrupted a command "
    "on 2026-08-17; rule on nedschorus#27). To open a terminal window running "
    f"a command for the user, run: {OPENER} <command...> — it passes the "
    "command as the new session's own process, no keystrokes involved."
)

ATTACHED_REASON = (
    "Blocked: tmux session '{target}' has an attached client, so "
    "send-keys/paste-buffer would splice into whoever is typing there "
    "(nedschorus#27; evidence on #37). Injection is permitted only into "
    "detached sessions. To show the user something, open them a window with "
    f"{OPENER}; for agent-to-agent messaging the durable path is the "
    "nedschorus#37 inbox design."
)

UNVERIFIED_REASON = (
    "Blocked: could not verify that tmux target '{target}' has no attached "
    "client ({error}). Verify yourself with: {probe} — 0 means detached — "
    "then re-run this command with CLAUDE_VERIFIED_DETACHED=1 prefixed. "
    "Never inject keystrokes at a session someone may be typing in "
    "(nedschorus#27)."
)

NO_TARGET_REASON = (
    "Blocked: this send-keys/paste-buffer names no -t target, so the "
    "keystrokes would land in an ambiguous pane and cannot be verified "
    "detached. Name the session with -t, or use "
    f"{OPENER} / the nedschorus#37 inbox instead (rule: nedschorus#27)."
)

# ssh options that consume a following value; anything else starting with "-"
# is a bare flag. Needed to find the hostname in an ssh-wrapped command.
SSH_VALUE_OPTIONS = {"-o", "-p", "-i", "-l", "-F", "-J", "-E", "-L", "-R", "-D", "-W", "-b", "-c", "-e", "-m", "-Q", "-S"}


HEREDOC_MARKER = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?")


def split_out_heredocs(command):
    """Return (shell_view, heredocs): the command with heredoc bodies removed,
    and a list of (consumer_line, body) pairs.

    A heredoc body is data to the shell — a commit message or a written file
    mentioning `osascript` and `write text` is prose, not keystrokes, and the
    guard blocked its own commit message before learning this. But the body IS
    the script when the consumer is osascript (`osascript <<EOF`), which is
    exactly the form the original incident used, so consumers are kept for the
    caller to judge."""
    shell_lines = []
    heredocs = []
    lines = command.split("\n")
    index = 0
    while index < len(lines):
        line = lines[index]
        marker = HEREDOC_MARKER.search(line)
        shell_lines.append(line)
        index += 1
        if not marker:
            continue
        terminator = marker.group(1)
        body_lines = []
        while index < len(lines) and lines[index].strip() != terminator:
            body_lines.append(lines[index])
            index += 1
        index += 1  # the terminator line itself
        heredocs.append((line, "\n".join(body_lines)))
    return "\n".join(shell_lines), heredocs


def extract_ssh_host(command):
    parts = command.split()
    try:
        start = parts.index("ssh") + 1
    except ValueError:
        return None
    index = start
    while index < len(parts):
        token = parts[index]
        if token in SSH_VALUE_OPTIONS:
            index += 2
            continue
        if token.startswith("-"):
            index += 1
            continue
        return token
    return None


def query_session_attached(target, ssh_host, runner=subprocess.run):
    """Return (attached_count, error). attached_count is None when unverifiable;
    a target tmux does not know counts as 0 — there is nothing to type into."""
    probe = ["tmux", "display-message", "-p", "-t", target, "#{session_attached}"]
    if ssh_host:
        probe = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", ssh_host] + probe
    try:
        result = runner(probe, capture_output=True, text=True, timeout=15)
    except Exception as error:  # timeout, missing binary — cannot verify
        return None, str(error)
    if result.returncode != 0:
        error_text = (result.stderr or "").strip()
        if "can't find" in error_text or "no server running" in error_text:
            return 0, error_text
        return None, error_text or "probe exited %d" % result.returncode
    try:
        return int((result.stdout or "").strip() or "0"), ""
    except ValueError:
        return None, "unparseable probe output: %r" % result.stdout


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))


def probe_recipe(target, ssh_host):
    prefix = f"ssh {ssh_host} " if ssh_host else ""
    return f"{prefix}tmux display-message -p -t '{target}' '#{{session_attached}}'"


def main(stdin=sys.stdin, runner=subprocess.run):
    try:
        payload = json.load(stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if payload.get("tool_name") != "Bash":
        return 0
    full_command = (payload.get("tool_input") or {}).get("command") or ""
    command, heredocs = split_out_heredocs(full_command)

    if re.search(r"\bosascript\b", command) and "write text" in command:
        deny(WRITE_TEXT_REASON)
        return 0
    for consumer_line, body in heredocs:
        if re.search(r"\bosascript\b", consumer_line) and "write text" in body:
            deny(WRITE_TEXT_REASON)
            return 0

    if not re.search(r"\btmux\b", command):
        return 0
    if not re.search(r"\b(send-keys|paste-buffer)\b", command):
        return 0
    if "CLAUDE_VERIFIED_DETACHED=1" in command:
        return 0

    # ssh's own -t (tty) flag also matches this pattern; the stray "target" it
    # yields is a hostname tmux does not know, which resolves to 0 and is
    # harmlessly skipped. Deduplicate, preserve order.
    targets = list(dict.fromkeys(re.findall(r"-t\s+['\"]?([\w.:@%+-]+)", command)))
    if not targets:
        deny(NO_TARGET_REASON)
        return 0

    ssh_host = extract_ssh_host(command)
    for target in targets:
        attached, error = query_session_attached(target, ssh_host, runner)
        if attached is None:
            deny(UNVERIFIED_REASON.format(
                target=target, error=error, probe=probe_recipe(target, ssh_host)))
            return 0
        if attached > 0:
            deny(ATTACHED_REASON.format(target=target))
            return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
