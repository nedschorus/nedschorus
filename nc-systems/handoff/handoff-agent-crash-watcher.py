#!/usr/bin/env python3
"""Restart a ned-box agent-seat whose agent-session died without writing a handoff.

Usage, on ned-box:
  nc-systems/handoff/handoff-agent-crash-watcher.py
      one run: assess every agent-seat and act. Cron runs this once a minute.
  nc-systems/handoff/handoff-agent-crash-watcher.py --show-notice FILE
      what a notice window on the user's Mac runs: print FILE, then wait for
      Enter and close.

Each run assesses every agent-seat under ~/agents with the assessment
scripts/recover-crashed-seats.py makes (assess_seat), and:
- notes each agent-seat it finds running;
- restarts, with scripts/recover-crashed-seats.py <seat>, an agent-seat it saw
  running earlier in this boot and has since found crashed (verdict resume or
  fresh-session-from-conversation-tail: no live supervisor, no waiting handoff, no recorded exit) on two runs
  at least CRASH_CONFIRMATION_SECONDS apart;
- tells the user, without restarting it, about an agent-seat it saw running
  that is now down in a state only he should restart from: a handoff waiting
  that no supervisor acted on, or an exit its supervisor recorded without
  resuming, other than a stop on purpose;
- hands the agent-seat a task, without restarting it, when it saw the agent-seat running
  and recover-crashed-seats.py now refuses it (verdict refuse), or its tmux
  session is now only the shell its launch left open (verdict
  ask-to-close-the-leftover-idle-shell), which recovery closes only on an
  operator's yes at a terminal; either stays silent over a stop on purpose,
  which the watcher reads from the seat's records itself, because recovery
  refuses before it reads them. Once the refusal clears, as when the user
  closes a leftover shell by hand, a crash beneath it is restarted;
- leaves every other agent-seat alone: a stop on purpose (a clean exit, an
  exit its supervisor recorded as a stop at an ask-user-before-restart
  handoff, or an ask-user-before-restart handoff waiting, verdict
  seat-asked-to-be-consulted), and an
  agent-seat not seen running since the machine booted, which the login
  restart or the user brings back;
- tries to restart an agent-seat at most once in RESTART_LIMIT_SECONDS, a
  failed attempt included; a second crash inside that time leaves it down and
  hands the agent-seat a task.

One rule says whether a death is already handled (death_already_handled): the
watcher records the seat supervisor's last poll when it handles a death, and
the death stays handled until that supervisor, or a new one, polls later. A
later poll shows the seat ran again, so its next death is a new crash. Times
are compared as parsed moments at the supervisor's own precision, which
carries microseconds. A restart that succeeded counts as a sighting of the
seat running; after a failed attempt the poll is recorded again, so the
attempt's own brief run is part of the death it was handling.

A failure an agent can fix becomes a task on an agent-seat's task list,
~/.claude/tasks/nedschorus-<seat>-tasks/, written with
nc-systems/general-tools/agent-seat-task-list-new-pending-task-write-common.py;
the task's subject names the failure's kind and what to fix, and its
description tells the agent-seat to find the cause and fix it, telling the
user only when the fix needs a guarded-file changed or the cause cannot be
found. A failure that leaves the seat down, a second crash inside
RESTART_LIMIT_SECONDS (second-crash), a failed restart (recovery-failed), a
seat recovery refuses (recovery-refuses) or a leftover shell holds
(leftover-shell), becomes a task on the seat's own list, which waits there
until the seat runs again, and one on the list of
AGENT_CRASH_WATCHER_PROGRAM_OWNER_AGENT_SEAT_NAME, which also says how to
restart the seat; when the seat down is that owner, the user is shown a
notice instead of the second task. A seat the watcher cannot assess
(assessment-failed) and a run that fails as a whole (run-failed) become a task
on the owner's list only. A seat recovery keeps refusing gets its tasks once
until it is seen running again or restarted, however long the refusal lasts.
A task that cannot be written is logged, and shown to the user as a notice
instead, quoting the task.

The user hears from the watcher about a seat down in a state only he should
restart from (the two cases above), about the owner left down, and about a
task it could not write. Each
becomes a notice. Each notice is kept as text, and also written as an
HTML page under notice-pages/ in LOG_DIRECTORY, which the program opens in the
browser on his Mac with scripts/open-html-page-in-mac-browser-from-ned-box.py:
a browser tab stays findable where one more terminal window is easily lost.
When the page cannot be written, or the Mac refuses it (its mount of ned-box's
home is missing, or its clone does not yet know the request), the notice opens
instead in a terminal window on his Mac, with
scripts/open-mac-window-from-ned-box.py running --show-notice. Each notice is
also written as an alert, with the shared user-alerts module, which the
walk-me-through hook brings into his approval-walk on ned-box; an alert that
cannot be written is logged, and the page or window still opens. The cases it leaves
alone stay silent, logged only: a stop on purpose, and a seat not seen running
since the machine booted. A restart it carries out shows no
notice: recover-crashed-seats.py opens a window on the Mac attached to the
restarted seat's tmux session. The one exception is a restart whose recovery
output holds `STARTED OUTSIDE THE USER'S SYSTEMD MANAGER` (the constant
AGENT_SEAT_STARTED_OUTSIDE_USER_SYSTEMD_MANAGER_RECOVERY_REPORT_LINE_MARKER):
the seat runs, but outside the user's systemd manager, so the test suites' low CPU weight does
not reach it, and that gets a notice, with no alert. A page or window the Mac cannot be reached for,
a notice's or a restarted seat's, stays pending and is tried again on every run. Every decision, each restart
and each task included, is appended to decisions.jsonl in LOG_DIRECTORY; the notices are
kept beside it.

Off ned-box the program refuses: the agents root it reads is ned-box's.

SCHEDULED. The job is declared in
nc-systems/general-tools/scheduled-jobs-on-each-machine.json and installed
with nc-systems/general-tools/install-scheduled-jobs-on-this-machine.py
--install --job handoff-agent-crash-watcher,
on ned-box only, as the cron line
    * * * * * /usr/bin/python3 /home/nedlern/Projects/nedschorus/nc-systems/handoff/handoff-agent-crash-watcher.py >> /home/nedlern/.claude/handoff-agent-crash-watcher.log 2>&1
Cron starts it with cron's own short environment, so no agent-session's
variables reach a seat it restarts.

NEDSCHORUS_HANDOFF_AGENT_SEAT_DIED_WITHOUT_SESSION_HANDOFF_RESTART_WATCHER_STATE_DIRECTORY,
NEDSCHORUS_HANDOFF_AGENT_SEAT_DIED_WITHOUT_SESSION_HANDOFF_RESTART_WATCHER_LOG_DIRECTORY and
NEDSCHORUS_HANDOFF_AGENT_SEAT_DIED_WITHOUT_SESSION_HANDOFF_RESTART_WATCHER_TASK_LISTS_DIRECTORY
override where the state, the log and the task lists go: the seams the
nc-test-suite uses.
"""

import argparse
import fcntl
import html
import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROGRAM = "handoff-agent-seat-died-without-session-handoff-restart-watcher"

REPOSITORY = Path(__file__).resolve().parent.parent.parent
RECOVERY_PROGRAM = REPOSITORY / "scripts" / "recover-crashed-seats.py"
LOGIN_RESTART_PROGRAM = REPOSITORY / "scripts" / "restart-live-seats-at-login.py"
MAC_WINDOW_OPENER_PROGRAM = REPOSITORY / "scripts" / "open-mac-window-from-ned-box.py"
MAC_BROWSER_PAGE_OPENER_PROGRAM = REPOSITORY / "scripts" / "open-html-page-in-mac-browser-from-ned-box.py"
_ned_box_home_specification = importlib.util.spec_from_file_location(
    "ned_box_home_directory_and_its_mac_mount_point_path_constants_common",
    REPOSITORY / "nc-systems" / "general-tools" / "ned-box-home-directory-and-its-mac-mount-point-path-constants-common.py")
ned_box_home_path_constants = importlib.util.module_from_spec(_ned_box_home_specification)
_ned_box_home_specification.loader.exec_module(ned_box_home_path_constants)
_user_alerts_specification = importlib.util.spec_from_file_location(
    "user_alerts_pending_and_claimed_files_write_claim_release_and_delete_common",
    REPOSITORY / "nc-systems" / "general-tools" / "user-alerts-pending-and-claimed-files-write-claim-release-and-delete-common.py")
user_alerts = importlib.util.module_from_spec(_user_alerts_specification)
_user_alerts_specification.loader.exec_module(user_alerts)
_agent_seat_task_list_specification = importlib.util.spec_from_file_location(
    "agent_seat_task_list_new_pending_task_write_common",
    REPOSITORY / "nc-systems" / "general-tools" / "agent-seat-task-list-new-pending-task-write-common.py")
agent_seat_task_list = importlib.util.module_from_spec(_agent_seat_task_list_specification)
_agent_seat_task_list_specification.loader.exec_module(agent_seat_task_list)

LOG_DIRECTORY = Path(ned_box_home_path_constants.NED_BOX_HOME) / "nedschorus-logs" / PROGRAM
STATE_DIRECTORY = Path("~/.local/state/nedschorus").expanduser()
STATE_DIRECTORY_ENVIRONMENT_VARIABLE = "NEDSCHORUS_HANDOFF_AGENT_SEAT_DIED_WITHOUT_SESSION_HANDOFF_RESTART_WATCHER_STATE_DIRECTORY"
LOG_DIRECTORY_ENVIRONMENT_VARIABLE = "NEDSCHORUS_HANDOFF_AGENT_SEAT_DIED_WITHOUT_SESSION_HANDOFF_RESTART_WATCHER_LOG_DIRECTORY"
TASK_LISTS_DIRECTORY_ENVIRONMENT_VARIABLE = (
    "NEDSCHORUS_HANDOFF_AGENT_SEAT_DIED_WITHOUT_SESSION_HANDOFF_RESTART_WATCHER_TASK_LISTS_DIRECTORY")

CRASHED_VERDICTS = ("resume", "fresh-session-from-conversation-tail")
RUNNING_VERDICT = "seat-already-running"
WAITING_HANDOFF_VERDICT = "defer-to-boot-ignition"
RECORDED_EXIT_VERDICT = "offer-after-recorded-exit"
REFUSED_VERDICT = "refuse"
LEFTOVER_SHELL_VERDICT = "ask-to-close-the-leftover-idle-shell"
ASK_USER_BEFORE_RESTART_HANDOFF_VERDICT = "seat-asked-to-be-consulted"
REFUSED_VERDICTS = (REFUSED_VERDICT, LEFTOVER_SHELL_VERDICT)
# Two sightings a minute apart keep a run from acting on a seat that a launch,
# resupervise-seat.py or the login restart is bringing up at that moment.
CRASH_CONFIRMATION_SECONDS = 50
RESTART_LIMIT_SECONDS = 3600

# A path in a notice is rewritten to the Mac's mount, so the user can open it there.
NED_BOX_HOME = ned_box_home_path_constants.NED_BOX_HOME
MAC_MOUNT_OF_NED_BOX_HOME = ned_box_home_path_constants.MAC_MOUNT_OF_NED_BOX_HOME
# launch-claude-ubuntu is not on the Mac's PATH; the Mac's checkout holds it.
MAC_LAUNCHER = "/Users/el/Projects/nedschorus/scripts/launch-claude-ubuntu"

# open-html-page-in-mac-browser-from-ned-box.py's EXIT_USAGE_OR_REFUSED: the page was refused,
# here or by the Mac, so retrying the page cannot help.
MAC_BROWSER_PAGE_REFUSED_EXIT_STATUS = 2

# recover-crashed-seats.py's ALL_AGENT_SEATS_RECOVERED_BUT_MAC_WINDOW_OPEN_FAILED_EXIT_STATUS:
# the seat came up, but its window on the Mac did not open.
RECOVERY_WINDOW_NOT_OPENED_EXIT_STATUS = 3

# recover-crashed-seats.py's AGENT_SEAT_STARTED_OUTSIDE_USER_SYSTEMD_MANAGER_RECOVERY_REPORT_LINE_MARKER.
AGENT_SEAT_STARTED_OUTSIDE_USER_SYSTEMD_MANAGER_RECOVERY_REPORT_LINE_MARKER = "STARTED OUTSIDE THE USER'S SYSTEMD MANAGER"

# How a notice hands its problem on: the user sits at his Mac, whose windows onto
# ned-box's agent-seats are where he types to them.
PASTE_THIS_NOTICE_INTO_A_NED_BOX_AGENT_SEAT = (
    "Paste this whole notice into the window of an agent-seat on ned-box, such as "
    "fleet-restart-at-login, which built the crash watcher, and ask it to ")

WAITING_HANDOFF_NOTICE_TEMPLATE = (
    "{seat} is down, and the crash watcher did not restart it. Its supervisor stopped "
    "at about {died_at} while a handoff it had not acted on was waiting, so no successor "
    "started. The watcher restarts only an agent-session that crashed, and a waiting "
    "handoff is the agent's own request for a successor, so the watcher does not start "
    "it.\n"
    "To start {seat}'s successor from that handoff, run in a Terminal on your Mac:\n"
    "  {mac_launcher} {seat}\n"
    "It starts {seat}'s supervisor, which starts the successor the handoff asks for, and "
    "opens {seat}'s window; if {seat} is already running, it only opens the window.\n"
    "Record: {record}\n"
)

RECORDED_EXIT_NOTICE_TEMPLATE = (
    "{seat} is down, and the crash watcher did not restart it. Its agent-session ended "
    "at about {died_at} with {exit_description}, and its supervisor recorded the exit and "
    "stopped instead of resuming it. A supervisor stops like this after several resumes "
    "that added no work, or when it has no terminal to resume on.\n"
    "Recommendation: read the end of its last conversation, the newest .jsonl file in "
    "{transcripts}, before you restart it.\n"
    "To restart it, run in a Terminal on your Mac:\n"
    "  ssh -t nedlern@ned-box 'cd ~/Projects/nedschorus && python3 scripts/recover-crashed-seats.py {seat}'\n"
    "It asks \"{question}\". Answer y, and it {restart_effect}. Answer n, and it starts "
    "nothing and prints the commands to bring {seat} back by hand later.\n"
    "When recovery restarts {seat}, it opens {seat}'s window on your Mac itself. If "
    "instead the last line recovery prints in your Terminal says WINDOW NOT OPENED, open "
    "the window, also in a Terminal on your Mac, with:\n"
    "  {mac_launcher} {seat}\n"
    "Record: {record}\n"
)

# Every text below that an agent reads is written to
# docs/nedschorus-wiki/nedschorus-how-to-write-a-tool-message-to-agent-such-as-a-hook-refusal-or-script-error.md.
# The agent-seat that owns the crash watcher: a failure of a whole run, which concerns no one
# agent-seat, is its task.
AGENT_CRASH_WATCHER_PROGRAM_OWNER_AGENT_SEAT_NAME = "fleet-restart-at-login"

# A failure an agent can fix becomes a task on the agent-seat it concerns: its subject, by the
# failure's kind, then its description. The user hears only from the agent-seat, and only when
# the fix needs a guarded-file changed or the cause cannot be found.
FAILURE_KIND_TO_AGENT_SEAT_TASK_SUBJECT_TEMPLATE = {
    "second-crash": "Crash watcher, second-crash: {seat} stopped twice within an hour without a "
                    "session-handoff; find why and fix the cause",
    "recovery-failed": "Crash watcher, recovery-failed: scripts/recover-crashed-seats.py could "
                       "not restart {seat}; find why and fix the cause",
    "assessment-failed": "Crash watcher, assessment-failed: the crash watcher cannot check {seat}; "
                         "find why and fix the cause",
    "run-failed": "Crash watcher, run-failed: the crash watcher fails and watches no agent-seat; "
                  "find why and fix the cause",
    "leftover-shell": "Crash watcher, leftover-shell: a leftover shell kept {seat} down after it "
                      "stopped; find why and fix the cause",
    "recovery-refuses": "Crash watcher, recovery-refuses: scripts/recover-crashed-seats.py "
                        "refused to restart {seat}; find why and fix the cause",
}
FAILURE_KIND_TO_AGENT_SEAT_TASK_DESCRIPTION_TEMPLATE = {
    "second-crash": (
        "{seat} stopped at about {died_at} without writing a session-handoff. The crash watcher "
        "{earlier_attempt}. The watcher restarts an agent-seat at most once an hour, so it left "
        "{seat} down after this second stop.\n"
        "The conversations that stopped are the newest .jsonl files in {transcripts}.\n"),
    "recovery-failed": (
        "{seat} stopped at about {died_at} without writing a session-handoff, and the crash "
        "watcher could not restart it: scripts/recover-crashed-seats.py {seat} exited {exit_code}. "
        "Recovery's last line was:\n"
        "  {recovery_last_line}\n"
        "Recovery's whole output is in the record named below. The watcher did not try again for "
        "that stop.\n"),
    "assessment-failed": (
        "The crash watcher could not check {seat}: {error}\n"
        "Until the cause is fixed, the watcher cannot restart {seat} if {seat} crashes. The watcher "
        "writes this task again only if the error changes; until then each run writes the error "
        "to the record.\n"),
    "run-failed": (
        "The crash watcher on ned-box, nc-systems/handoff/handoff-agent-crash-watcher.py, failed "
        "and is watching no agent-seat: {error}\n"
        "Until the cause is fixed, an agent-seat that crashes is not restarted. The watcher "
        "writes this task again only if the error changes; until then each failed run writes "
        "the error to the record.\n"),
    "leftover-shell": (
        "{seat} stopped at about {died_at}, and its tmux session on ned-box was left as only the "
        "shell its launch left open. scripts/recover-crashed-seats.py closes that shell only "
        "when someone at a terminal answers yes, so the crash watcher, which runs unattended, "
        "left {seat} down.\n"),
    "recovery-refuses": (
        "{seat} was down, or could not be shown to be running, and the crash watcher could not "
        "restart {seat}: scripts/recover-crashed-seats.py refused {seat}, saying:\n"
        "  {refusal}\n"
        "The watcher had seen {seat} running; its supervisor last checked in at about "
        "{died_at}.\n"),
}
# The kinds that leave the agent-seat down: its own task waits until it runs again, so the
# owner gets the task too, with the restart.
DOWN_AGENT_SEAT_FAILURE_KINDS = ("second-crash", "recovery-failed", "leftover-shell",
                                 "recovery-refuses")
DOWN_AGENT_SEAT_RESTART_BY_OWNER_TEMPLATE = (
    "{seat} is down, and no other program restarts it; its own copy of this task waits on its "
    "task list until it runs again. Once the cause is fixed, restart {seat} on ned-box, from "
    "~/Projects/nedschorus, with:\n"
    "  python3 scripts/recover-crashed-seats.py {seat}\n"
    "If recovery's output says it restarts {seat} only on an operator's yes at a terminal, tell "
    "the user that command and why recovery needs his yes: he runs it in a Terminal on his Mac "
    "as ssh -t nedlern@ned-box 'cd ~/Projects/nedschorus && python3 "
    "scripts/recover-crashed-seats.py {seat}'.\n")
AGENT_SEAT_TASK_DESCRIPTION_CLOSING_TEMPLATE = (
    "Find the cause and fix it going forward. A fix to code, settings or instructions goes in a "
    "pull request.\n"
    "If the fix needs a change to a guarded-file, tell the user what change it needs and why.\n"
    "If you cannot find the cause, or cannot fix it, tell the user what you found.\n"
    "A subagent tells the agent that dispatched it instead of the user.\n"
    "Record: {record}\n")

# What the user is shown when the agent-seat left down is the owner itself: no agent-seat reads
# its task until he restarts it.
OWNER_AGENT_SEAT_DOWN_NOTICE_TEMPLATE = (
    "{seat} is down, and the crash watcher left it down. {seat} is the agent-seat that restarts "
    "the agent-seats the crash watcher leaves down, so no agent-seat can restart it.\n"
    "To restart it, run in a Terminal on your Mac:\n"
    "  ssh -t nedlern@ned-box 'cd ~/Projects/nedschorus && python3 scripts/recover-crashed-seats.py {seat}'\n"
    "When recovery restarts {seat}, it opens {seat}'s window on your Mac itself. If "
    "instead the last line recovery prints in your Terminal says WINDOW NOT OPENED, open "
    "the window, also in a Terminal on your Mac, with:\n"
    "  {mac_launcher} {seat}\n"
    "{seat} then finds on its task list the task below, to find why it went down and fix the "
    "cause.\n"
    "Task subject: {subject}\n"
    "Task description:\n"
    "{description}"
)

# What the user is shown when a failure's task cannot be written: the task, for an agent to do.
AGENT_SEAT_TASK_NOT_WRITTEN_NOTICE_TEMPLATE = (
    "The crash watcher could not hand a failure to {owner} as a task. Writing the task to "
    "{owner}'s task list failed: {task_write_error}\n"
    + PASTE_THIS_NOTICE_INTO_A_NED_BOX_AGENT_SEAT + "fix why the task could not be written, and "
    "then do the task quoted below.\n"
    "Task subject: {subject}\n"
    "Task description:\n"
    "{description}"
)
AGENT_SEAT_TASK_NOT_WRITTEN_USER_ALERT_ACTION_TEXT_SAYING_WHAT_AN_AGENT_CAN_DO = (
    "An agent on ned-box can fix why the crash watcher could not write the task the notice "
    "quotes, and then do that task.")

# Each notice's alert: its title, by the notice's kind, and what an agent on ned-box can do about it.
FAILED_RESTART_NOTICE_KIND_TO_USER_ALERT_TITLE_TEMPLATE = {
    "second-crash": "{seat} crashed twice within an hour, and the crash watcher left it down",
    "recovery-failed": "{seat} is down: the crash watcher could not restart it",
    "assessment-failed": "The crash watcher cannot check {seat}",
    "run-failed": "The crash watcher on ned-box failed and is watching no agent-seat",
    "waiting-handoff": "{seat} is down with a handoff no supervisor acted on",
    "recorded-exit": "{seat} is down: its supervisor recorded its exit and stopped",
    "leftover-shell": "{seat} is down: a leftover shell holds its tmux session",
    "recovery-refuses": "{seat} is down, and recovery refuses it",
}
FAILED_RESTART_NOTICE_USER_ALERT_ACTION_TEXT_SAYING_WHAT_AN_AGENT_CAN_DO = (
    "An agent on ned-box can read the record the notice names, find out why, fix what the notice asks an agent "
    "to fix, and restart the agent-seat by running on ned-box the command the notice gives after "
    "`ssh -t nedlern@ned-box`, answering its question as the notice says. Only the notice's "
    "launch-claude-ubuntu command, which opens the agent-seat's window on the Mac, needs the user at his Mac.")
STARTED_OUTSIDE_USER_SYSTEMD_MANAGER_NOTICE_TEMPLATE = (
    "{seat} is running again: the crash watcher restarted it after its agent-session "
    "stopped at about {died_at} without writing a handoff. But on ned-box its tmux server "
    "could not be started inside your systemd user manager, so while test suites run, "
    "{seat} gets no more CPU than they do, instead of most of it. Recovery said:\n"
    "  {reason_line}\n"
    "{seat} works; only its CPU priority is affected, so do not restart it for this alone. "
    + PASTE_THIS_NOTICE_INTO_A_NED_BOX_AGENT_SEAT + "find out why the user manager could not "
    "be reached: recovery's whole output, in the record named below, gives the commands "
    "that check it. Once the user manager answers, {seat}'s next start, at its next crash "
    "recovery or launch, puts it inside the user manager.\n"
    "Record: {record}\n"
)
STARTED_OUTSIDE_USER_SYSTEMD_MANAGER_NOTICE_TITLE_TEMPLATE = (
    "{seat}: started outside the user systemd manager, so its CPU priority is normal")

SHOW_NOTICE_CLOSE_PROMPT = "Press Enter to close this window."

# A notice's indented line is a command when it starts like one of these; every one runs on the Mac.
MAC_COMMAND_PREFIXES = ("ssh -t nedlern@ned-box ", MAC_LAUNCHER + " ")

NOTICE_PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root {{ --background: #ffffff; --text: #1b1b1b; --muted: #5a5a5a; --block: #f2f2f2;
         --border: #d0d0d0; --accent: #b3261e; --button: #e6e6e6; }}
@media (prefers-color-scheme: dark) {{
  :root {{ --background: #1a1a1a; --text: #e8e8e8; --muted: #a8a8a8; --block: #262626;
           --border: #444444; --accent: #ff8a80; --button: #333333; }}
}}
body {{ background: var(--background); color: var(--text); margin: 0 auto; max-width: 52rem;
        padding: 1.5rem 1rem; font: 16px/1.5 -apple-system, system-ui, sans-serif; }}
h1 {{ color: var(--accent); font-size: 1.4rem; margin: 0 0 0.25rem; }}
.when {{ color: var(--muted); margin: 0 0 1.25rem; font-size: 0.9rem; }}
p {{ margin: 0 0 0.9rem; overflow-wrap: anywhere; }}
.block {{ border: 1px solid var(--border); border-radius: 6px; margin: 0 0 1rem; }}
.label {{ display: flex; justify-content: space-between; align-items: center; gap: 0.5rem;
          padding: 0.35rem 0.6rem; border-bottom: 1px solid var(--border); color: var(--muted);
          font-size: 0.85rem; }}
pre {{ background: var(--block); margin: 0; padding: 0.6rem; overflow-x: auto;
       font: 14px/1.4 ui-monospace, Menlo, monospace; white-space: pre-wrap; word-break: break-all; }}
button {{ background: var(--button); color: var(--text); border: 1px solid var(--border);
          border-radius: 4px; padding: 0.15rem 0.6rem; font-size: 0.85rem; cursor: pointer; }}
</style>
</head>
<body>
<h1>{title}</h1>
<p class="when">Written by the crash watcher on ned-box at {written_at}.</p>
{body}
<script>
for (const button of document.querySelectorAll("button[data-copy]")) {{
  button.addEventListener("click", () => {{
    const text = document.getElementById(button.dataset.copy).textContent;
    const done = () => {{ button.textContent = "Copied"; setTimeout(() => {{ button.textContent = "Copy"; }}, 1500); }};
    if (navigator.clipboard) {{
      navigator.clipboard.writeText(text).then(done, () => {{ button.textContent = "Select and copy by hand"; }});
    }} else {{
      button.textContent = "Select and copy by hand";
    }}
  }});
}}
</script>
</body>
</html>
"""


def failed_restart_notice_html_page_build(seat, text, written_at, title=None) -> str:
    """The HTML page of one notice: each line a paragraph, each indented line a block.

    An indented line that starts like a command gets a label naming the Mac, where all of
    them run, and a Copy button; any other indented line is quoted output. The page's
    title is title when given, else the seat's name and "the crash watcher needs you".
    """
    parts = []
    for number, line in enumerate(text.splitlines()):
        if not line.strip():
            continue
        if not line.startswith("  "):
            parts.append(f"<p>{html.escape(line)}</p>")
            continue
        content = line.strip()
        identifier = f"block-{number}"
        if content.startswith(MAC_COMMAND_PREFIXES):
            label = ("<span>Run in a Terminal on your Mac</span>"
                     f'<button type="button" data-copy="{identifier}">Copy</button>')
        else:
            label = "<span>Output, quoted</span>"
        parts.append(f'<div class="block"><div class="label">{label}</div>'
                     f'<pre id="{identifier}">{html.escape(content)}</pre></div>')
    if title is None:
        title = ("The crash watcher needs you" if seat == "watcher"
                 else f"{seat}: the crash watcher needs you")
    return NOTICE_PAGE_TEMPLATE.format(title=html.escape(title), written_at=html.escape(written_at),
                                       body="\n".join(parts))


def load_module(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def timestamp(moment: datetime) -> str:
    # Full precision: a handled death is matched against the supervisor's last_poll_at,
    # which carries microseconds; rounding would make every later run see a newer poll.
    return moment.astimezone(timezone.utc).isoformat()


def parse_timestamp(text):
    if not text:
        return None
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def path_on_the_mac(path) -> str:
    """The form of a ned-box path the user can open on his Mac, where ned-box's home is mounted."""
    text = str(path)
    if text == NED_BOX_HOME or text.startswith(NED_BOX_HOME + "/"):
        return MAC_MOUNT_OF_NED_BOX_HOME + text[len(NED_BOX_HOME):]
    return text


def clock_text(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def read_state(state_path: Path) -> dict:
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"seats": {}, "pending_notices": [], "reported_errors": []}
    state.setdefault("seats", {})
    state.setdefault("pending_notices", [])
    state.setdefault("reported_errors", [])
    return state


def write_state(state_path: Path, state: dict):
    state_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = state_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(state_path)


class Watcher:
    """One run's decisions; every outside effect comes in as a callable, for the tests."""

    def __init__(self, *, state, now, boot_at, log_directory, assess, died_at_about,
                 transcripts_directory, recover, open_window, show_notice_words,
                 agent_seat_task_write, stopped_on_purpose=None, recorded_exit_question=None, open_seat_window=None,
                 seat_session_alive=None, assess_as_though_leftover_shell_closed=None,
                 down_agent_seat_records_stopped_on_purpose=None, open_page=None, user_alert_write_to_pending=None):
        self.state = state
        # (agent-seat, subject, description) -> (task id, task list): writes a new pending task
        # on that agent-seat's task list. Raises OSError.
        self.agent_seat_task_write = agent_seat_task_write
        # (title, notice text, action) -> alert id: writes the notice's alert. None writes none.
        self.user_alert_write_to_pending = user_alert_write_to_pending
        # path -> (exit code, output): opens a notice's HTML page in the Mac's browser. None
        # shows every notice in a terminal window instead.
        self.open_page = open_page
        self.stopped_on_purpose = stopped_on_purpose or (lambda seat, detail: False)
        self.recorded_exit_question = recorded_exit_question or (
            lambda seat, exit_code: f"Restart {seat}? y/n")
        self.now = now
        self.boot_at = boot_at
        self.log_directory = log_directory
        self.assess = assess
        self.died_at_about = died_at_about
        self.transcripts_directory = transcripts_directory
        self.recover = recover
        self.open_window = open_window
        self.show_notice_words = show_notice_words
        # recover-crashed-seats.py's opener, which returns (opened, detail), opened None when a
        # window is already attached; None leaves a restarted seat's window pending.
        self.open_seat_window = open_seat_window
        # recover-crashed-seats.py's tmux_session_alive_anywhere, which returns (alive, detail),
        # alive None when tmux cannot answer.
        self.seat_session_alive = seat_session_alive
        # recover-crashed-seats.py's predicted_assessment_once_the_leftover_idle_shell_is_closed,
        # bound to the agents root: (seat, pane process ids) -> (verdict, detail). It tells
        # whether recovery, run by the user, would ask its question about a leftover shell.
        # None counts it as asking.
        self.assess_as_though_leftover_shell_closed = assess_as_though_leftover_shell_closed
        # seat -> whether the seat's records say it stopped on purpose; recovery refuses before
        # it reads them. None counts no refused seat as stopped on purpose.
        self.down_agent_seat_records_stopped_on_purpose = (
            down_agent_seat_records_stopped_on_purpose)

    @property
    def decisions_path(self) -> Path:
        return self.log_directory / "decisions.jsonl"

    def log(self, seat, decision, **details):
        self.log_directory.mkdir(parents=True, exist_ok=True)
        entry = {"at": timestamp(self.now), "seat": seat, "decision": decision, **details}
        with self.decisions_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(entry, sort_keys=True) + "\n")

    def notice_path(self, seat, kind) -> Path:
        stamp = self.now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = self.log_directory / "notices" / f"{stamp}-{seat}-{kind}.txt"
        # One failure can write two notices in a run, as when both of its tasks cannot be written.
        number = 2
        while path.exists():
            path = self.log_directory / "notices" / f"{stamp}-{seat}-{kind}-{number}.txt"
            number += 1
        return path

    def write_notice(self, seat, kind, template, title_template=None,
                     user_alert_action=FAILED_RESTART_NOTICE_USER_ALERT_ACTION_TEXT_SAYING_WHAT_AN_AGENT_CAN_DO,
                     **fields) -> dict:
        path = self.notice_path(seat, kind)
        path.parent.mkdir(parents=True, exist_ok=True)
        # The user may hand a notice to an agent on ned-box, which needs the ned-box path.
        record = (f"{path_on_the_mac(self.decisions_path)} "
                  f"(on ned-box: {self.decisions_path})")
        text = template.format(seat=seat, record=record, mac_launcher=MAC_LAUNCHER, **fields)
        path.write_text(text, encoding="utf-8")
        self.write_alert(seat, kind, path, text, user_alert_action)
        notice = {"path": str(path)}
        title = None if title_template is None else title_template.format(seat=seat)
        page = self.write_notice_page(seat, path, text, title)
        if page is not None:
            notice["page"] = str(page)
        self.show(notice)
        return notice

    def write_alert(self, seat, kind, notice_path: Path, text, action) -> bool:
        """Write the notice's user-alert; return whether one was written."""
        title_template = FAILED_RESTART_NOTICE_KIND_TO_USER_ALERT_TITLE_TEMPLATE.get(kind)
        # A kind without a title, such as the notice written after a successful restart, gets no
        # alert: that agent-seat runs, so nothing waits on the user.
        if self.user_alert_write_to_pending is None or title_template is None:
            return False
        try:
            alert_id = self.user_alert_write_to_pending(title_template.format(seat=seat), text, action)
        except OSError as error:
            self.log(seat, "user alert not written; the notice's page or window still opens",
                     notice=str(notice_path), error=f"{type(error).__name__}: {error}")
            return False
        self.log(seat, "user alert written", notice=str(notice_path), alert=alert_id)
        return True

    def report_failure_to_agent_seat(self, seat, kind, **fields):
        """Hand a failure an agent can fix to the agent-seats that fix it, as tasks.

        A failure that leaves the seat down becomes a task on the seat's own list and one, with
        the restart, on AGENT_CRASH_WATCHER_PROGRAM_OWNER_AGENT_SEAT_NAME's; when the seat down is
        that owner, the user is shown a notice with its user-alert instead of the second task.
        Any other failure becomes a task on the owner's list only.
        """
        owner = AGENT_CRASH_WATCHER_PROGRAM_OWNER_AGENT_SEAT_NAME
        subject = FAILURE_KIND_TO_AGENT_SEAT_TASK_SUBJECT_TEMPLATE[kind].format(seat=seat)
        values = dict(seat=seat, record=f"nedlern@ned-box:{self.decisions_path}", **fields)
        description = (FAILURE_KIND_TO_AGENT_SEAT_TASK_DESCRIPTION_TEMPLATE[kind]
                       + AGENT_SEAT_TASK_DESCRIPTION_CLOSING_TEMPLATE).format(**values)
        if kind not in DOWN_AGENT_SEAT_FAILURE_KINDS:
            self.agent_seat_task_write_or_notice(seat, kind, owner, subject, description)
            return
        self.agent_seat_task_write_or_notice(seat, kind, seat, subject, description)
        if seat == owner:
            self.log(seat, "the agent-seat left down is the crash watcher's owner; the user is "
                     "shown a notice", kind=kind)
            self.write_notice(seat, kind, OWNER_AGENT_SEAT_DOWN_NOTICE_TEMPLATE, subject=subject,
                              description=description)
            return
        owner_description = (FAILURE_KIND_TO_AGENT_SEAT_TASK_DESCRIPTION_TEMPLATE[kind]
                             + DOWN_AGENT_SEAT_RESTART_BY_OWNER_TEMPLATE
                             + AGENT_SEAT_TASK_DESCRIPTION_CLOSING_TEMPLATE).format(**values)
        self.agent_seat_task_write_or_notice(seat, kind, owner, subject, owner_description)

    def agent_seat_task_write_or_notice(self, seat, kind, task_owner, subject, description):
        """Write the task on task_owner's list; when it cannot be written, show the user a
        notice quoting it, with its user-alert."""
        try:
            task_id, task_list = self.agent_seat_task_write(task_owner, subject, description)
        except OSError as error:
            task_write_error = f"{type(error).__name__}: {error}"
            self.log(seat, "task not written; the user is shown it as a notice instead",
                     kind=kind, owner=task_owner, error=task_write_error)
            self.write_notice(seat, kind, AGENT_SEAT_TASK_NOT_WRITTEN_NOTICE_TEMPLATE,
                              user_alert_action=AGENT_SEAT_TASK_NOT_WRITTEN_USER_ALERT_ACTION_TEXT_SAYING_WHAT_AN_AGENT_CAN_DO,
                              owner=task_owner, task_write_error=task_write_error,
                              subject=subject, description=description)
            return
        self.log(seat, "task written for the agent-seat to find the cause and fix it", kind=kind,
                 owner=task_owner, task=task_id, task_list=str(task_list))

    def write_notice_page(self, seat, notice_path: Path, text, title=None):
        """Write the notice's HTML page; return its path, or None to show the text instead."""
        if self.open_page is None:
            return None
        page = self.log_directory / "notice-pages" / f"{notice_path.stem}.html"
        try:
            page.parent.mkdir(parents=True, exist_ok=True)
            page.write_text(failed_restart_notice_html_page_build(seat, text, clock_text(self.now),
                                                                  title),
                            encoding="utf-8")
        except OSError as error:
            self.log(seat, "notice page not written; the notice opens in a terminal window instead",
                     notice=str(notice_path), error=f"{type(error).__name__}: {error}")
            return None
        return page

    def show(self, window) -> bool:
        """Open a pending window on the Mac: a notice ({"path"}) or a restarted seat ({"attach_seat"})."""
        if "page" in window and self.open_page is not None:
            what = window["page"]
            exit_code, output = self.open_page(window["page"])
            if exit_code == MAC_BROWSER_PAGE_REFUSED_EXIT_STATUS:
                # The Mac refuses a page while its mount of ned-box's home is missing, or before
                # its clone knows the request; a terminal window needs neither. The page is
                # dropped from the notice, so a notice still pending retries only the window.
                self.log(None, "page refused by the Mac; the notice opens in a terminal window "
                         "on the Mac instead", refused_page=what, opener_output=output)
                window.pop("page")
                what = window["path"]
                exit_code, output = self.open_window(self.show_notice_words(window["path"]))
            opened = exit_code == 0
        elif "path" in window:
            what = window["path"]
            exit_code, output = self.open_window(self.show_notice_words(window["path"]))
            opened = exit_code == 0
        else:
            what = f"{window['attach_seat']}'s session"
            if self.open_seat_window is None:
                opened, exit_code, output = False, None, "no window opener in this run"
            else:
                result, output = self.open_seat_window(window["attach_seat"])
                opened, exit_code = result is not False, None
        session_gone, session_detail = False, ""
        if not opened and "attach_seat" in window:
            session_gone, session_detail = self.seat_session_gone(window["attach_seat"])
        if session_gone:
            # A window has nothing to attach to; a seat that died is the restart path's to handle.
            if window in self.state["pending_notices"]:
                self.state["pending_notices"].remove(window)
            self.log(window["attach_seat"], "pending window dropped: the seat's tmux session is gone",
                     window=what, opener_output=output,
                     next_step="none here: this watcher's crash check restarts the seat if it died")
            return False
        if opened:
            if window in self.state["pending_notices"]:
                self.state["pending_notices"].remove(window)
                self.log(None, "pending window shown", window=what)
            return True
        if window not in self.state["pending_notices"]:
            # Logged once per window; later runs retry quietly until the Mac answers.
            self.state["pending_notices"].append(window)
            self.log(None, "window not opened on the Mac; retried on every run",
                     window=what, exit_code=exit_code, opener_output=output)
        if session_detail:
            # Logged once per distinct error, so a tmux broken for days does not fill the log.
            key = f"{window['attach_seat']}: session check: {session_detail}"
            if key not in self.state["reported_errors"]:
                self.state["reported_errors"].append(key)
                self.log(window["attach_seat"],
                         "pending window kept, retried each run: " + session_detail,
                         window=what)
        return False

    def seat_session_gone(self, seat):
        """Return (gone, detail): gone only when tmux answered that the session does not exist."""
        if self.seat_session_alive is None:
            return False, ""
        alive, detail = self.seat_session_alive(seat)
        if alive is None:
            return False, ("recovery's tmux check could not say whether the session exists, "
                           f"and said: {detail}")
        return alive is False, ""

    def run(self, seat_names):
        for notice in list(self.state["pending_notices"]):
            self.show(notice)
        for seat in seat_names:
            try:
                verdict, detail = self.assess(seat)
            except Exception as error:  # noqa: BLE001 - any failure here must be reported
                self.report_assessment_failure(seat, f"{type(error).__name__}: {error}")
                continue
            self.decide(seat, verdict, detail)

    def report_assessment_failure(self, seat, error_text):
        self.log(seat, "could not assess", error=error_text)
        key = f"{seat}: {error_text}"
        if key in self.state["reported_errors"]:
            return
        self.state["reported_errors"].append(key)
        self.report_failure_to_agent_seat(seat, "assessment-failed", error=error_text)

    def down_kind(self, seat, verdict, detail):
        """Return "crash" to restart, "for-the-user" or "refused" to report, or None to leave alone."""
        if verdict in CRASHED_VERDICTS:
            return "crash"
        if verdict == WAITING_HANDOFF_VERDICT:
            return "for-the-user"
        if verdict == RECORDED_EXIT_VERDICT and not self.stopped_on_purpose(seat, detail):
            return "for-the-user"
        if verdict in REFUSED_VERDICTS and not self.refused_seat_stopped_on_purpose(seat):
            return "refused"
        return None

    def refused_seat_stopped_on_purpose(self, seat) -> bool:
        """Recovery refuses before it reads why the seat stopped, so the watcher reads that.

        A stop on purpose leaves its seat open to refusals that are no crash: an attached
        launch's shell stays open, and any process may take its working directory there.
        """
        if self.down_agent_seat_records_stopped_on_purpose is None:
            return False
        try:
            return self.down_agent_seat_records_stopped_on_purpose(seat)
        except Exception as error:  # noqa: BLE001 - unsure of a stop on purpose, report the refusal
            self.log(seat, "could not read whether it stopped on purpose; counted as not",
                     error=f"{type(error).__name__}: {error}")
            return False

    def leftover_shell_reported_without_asking(self, seat, detail):
        """Return what recovery would report instead of asking about the shell, or None.

        Recovery asks about a leftover shell only when the seat, the shell closed, is one it
        would restart; otherwise, run by the user, it reports and asks nothing.
        """
        if self.assess_as_though_leftover_shell_closed is None:
            return None
        _, pane_process_ids, _ = detail
        try:
            verdict, predicted = self.assess_as_though_leftover_shell_closed(
                seat, pane_process_ids)
        except Exception as error:  # noqa: BLE001 - recovery would fail too; report the error
            self.log(seat, "could not assess as though its leftover shell were closed",
                     error=f"{type(error).__name__}: {error}")
            return (f"assessing {seat} as though its leftover shell were closed failed: "
                    f"{type(error).__name__}: {error}")
        if verdict in (REFUSED_VERDICT, RUNNING_VERDICT):
            return (f"{predicted} (found assessing {seat} as though its leftover shell were "
                    "closed; once that is cleared, recovery asks whether to close the shell)")
        return None

    def mark_seen_running(self, record, moment):
        record["last_seen_running_at"] = timestamp(moment)
        for key in ("first_seen_crashed_at", "crash_handled", "handled_at_supervisor_last_poll",
                    "refusal_noticed"):
            record.pop(key, None)

    def death_already_handled(self, seat, record) -> bool:
        """Return True while the death the watcher handled is still the seat's latest one.

        The key is the seat supervisor's last poll when the death was handled. A later
        poll shows a supervisor ran the seat again: the handled death is over, the seat
        counts as seen running at that poll, and its present death is a new one.
        """
        if not record.get("crash_handled"):
            return False
        handled = parse_timestamp(record.get("handled_at_supervisor_last_poll"))
        latest_poll = self.died_at_about(seat)
        if latest_poll is None or (handled is not None and latest_poll <= handled):
            return True
        self.mark_seen_running(record, latest_poll)
        self.log(seat, "ran again since its last handled crash; watching this one as a new crash",
                 supervisor_last_poll_at=timestamp(latest_poll))
        return False

    def mark_handled(self, seat, record):
        """Record that the seat's present death is handled, keyed by its supervisor's last poll."""
        record["crash_handled"] = True
        latest_poll = self.died_at_about(seat)
        record["handled_at_supervisor_last_poll"] = (
            timestamp(latest_poll) if latest_poll is not None else None)

    def record_recovery_attempt(self, record, died_at, outcome):
        record.setdefault("recovery_attempts", []).append(
            {"attempted_at": timestamp(self.now), "died_at_about": timestamp(died_at),
             "outcome": outcome})
        record["recovery_attempts"] = record["recovery_attempts"][-5:]

    def recent_recovery_attempts(self, record):
        return [attempt for attempt in record.get("recovery_attempts", [])
                if (self.now - parse_timestamp(attempt["attempted_at"])).total_seconds()
                < RESTART_LIMIT_SECONDS]

    def decide(self, seat, verdict, detail):
        record = self.state["seats"].setdefault(seat, {})
        if verdict == RUNNING_VERDICT:
            self.mark_seen_running(record, self.now)
            record.pop("left_alone_verdict", None)
            return
        # A refusal can last while its supervisor still polls, which makes each poll a new
        # death below; one notice per refusal until the seat is seen running again.
        if verdict in REFUSED_VERDICTS and record.get("refusal_noticed"):
            return
        kind = self.down_kind(seat, verdict, detail)
        if kind is None:
            record.pop("first_seen_crashed_at", None)
            if record.get("left_alone_verdict") != verdict:
                record["left_alone_verdict"] = verdict
                self.log(seat, "left alone: not a crash this watcher restarts or reports",
                         verdict=verdict, detail=str(detail))
            return
        record.pop("left_alone_verdict", None)
        if self.death_already_handled(seat, record):
            return
        last_seen_running = parse_timestamp(record.get("last_seen_running_at"))
        if last_seen_running is None or last_seen_running < self.boot_at:
            self.mark_handled(seat, record)
            self.log(seat, "left alone: down, but not seen running by this watcher "
                     "since the machine booted; the login restart or the user brings it back",
                     verdict=verdict)
            return
        first_seen_crashed = parse_timestamp(record.get("first_seen_crashed_at"))
        if first_seen_crashed is None:
            record["first_seen_crashed_at"] = timestamp(self.now)
            self.log(seat, "found down; acting if still down on a later run", verdict=verdict)
            return
        if (self.now - first_seen_crashed).total_seconds() < CRASH_CONFIRMATION_SECONDS:
            return
        died_at = self.died_at_about(seat) or last_seen_running
        if kind == "refused":
            # Not marked handled: once the refusal clears, as when the user closes a leftover
            # shell by hand, the crash beneath it is restarted, after two sightings of its own.
            record["refusal_noticed"] = verdict
            record.pop("first_seen_crashed_at", None)
            self.report_refused(seat, verdict, detail, died_at)
            return
        self.mark_handled(seat, record)
        if kind == "for-the-user":
            self.report_down_for_the_user(seat, verdict, detail, died_at)
            return
        recent = self.recent_recovery_attempts(record)
        if recent:
            earlier = recent[-1]
            earlier_attempted_at = clock_text(parse_timestamp(earlier["attempted_at"]))
            earlier_died_at = clock_text(parse_timestamp(earlier["died_at_about"]))
            earlier_attempt = (
                f"had restarted it at {earlier_attempted_at}, after it stopped at about "
                f"{earlier_died_at}" if earlier["outcome"] == "restarted"
                # Recovery gives up on a launch after its deadline, but that launch's own
                # supervisor may still come up late; either way the seat ran again since.
                else f"had tried to restart it at {earlier_attempted_at}, after it stopped at "
                     f"about {earlier_died_at}, and recovery reported that attempt as failed; "
                     f"{seat} then ran again, either because that attempt came up late or "
                     f"because it was started by hand or by another program")
            self.log(seat, "not restarted: a restart was attempted less than an hour ago",
                     died_at_about=timestamp(died_at), earlier_attempt=earlier)
            self.report_failure_to_agent_seat(
                seat, "second-crash", died_at=clock_text(died_at),
                earlier_attempt=earlier_attempt, transcripts=self.transcripts_directory(seat))
            return
        exit_code, output = self.recover(seat)
        if (exit_code in (0, RECOVERY_WINDOW_NOT_OPENED_EXIT_STATUS)
                and "ALREADY RUNNING" not in output):
            # Recovery exits 0 or 3 only once the seat's supervisor survived its settle: a sighting.
            self.mark_seen_running(record, self.now)
            self.record_recovery_attempt(record, died_at, "restarted")
            self.log(seat, "restarted", died_at_about=timestamp(died_at),
                     recovery_output=output)
            if exit_code == RECOVERY_WINDOW_NOT_OPENED_EXIT_STATUS:
                self.show({"attach_seat": seat})
            outside_lines = [
                line.strip() for line in output.splitlines()
                if AGENT_SEAT_STARTED_OUTSIDE_USER_SYSTEMD_MANAGER_RECOVERY_REPORT_LINE_MARKER in line]
            if outside_lines:
                self.write_notice(seat, "started-outside-user-systemd-manager",
                                  STARTED_OUTSIDE_USER_SYSTEMD_MANAGER_NOTICE_TEMPLATE,
                                  title_template=STARTED_OUTSIDE_USER_SYSTEMD_MANAGER_NOTICE_TITLE_TEMPLATE,
                                  died_at=clock_text(died_at), reason_line=outside_lines[0])
            return
        if exit_code == 0:
            self.mark_seen_running(record, self.now)
            self.log(seat, "not restarted: running again by the time recovery ran",
                     recovery_output=output)
            return
        # A launch that did not come up may have polled before it died; that brief run
        # belongs to this death, so the handled poll moves past it.
        self.mark_handled(seat, record)
        self.record_recovery_attempt(record, died_at, "failed")
        self.log(seat, "recovery failed", exit_code=exit_code,
                 died_at_about=timestamp(died_at), recovery_output=output)
        output_lines = [line for line in output.strip().splitlines() if line.strip()]
        self.report_failure_to_agent_seat(seat, "recovery-failed",
                                          died_at=clock_text(died_at), exit_code=exit_code,
                                          recovery_last_line=(output_lines[-1].strip() if output_lines
                                                              else "(it printed nothing)"))

    def report_refused(self, seat, verdict, detail, died_at):
        if verdict == LEFTOVER_SHELL_VERDICT:
            reported_instead = self.leftover_shell_reported_without_asking(seat, detail)
            if reported_instead is None:
                self.log(seat, "not restarted: its tmux session is a leftover shell, which "
                         "recovery closes only on an operator's yes",
                         died_at_about=timestamp(died_at), detail=str(detail))
                self.report_failure_to_agent_seat(seat, "leftover-shell",
                                                  died_at=clock_text(died_at))
                return
            detail = reported_instead
        self.log(seat, "not restarted: recovery refuses it",
                 died_at_about=timestamp(died_at), detail=str(detail))
        self.report_failure_to_agent_seat(seat, "recovery-refuses",
                                          died_at=clock_text(died_at), refusal=str(detail))

    def report_down_for_the_user(self, seat, verdict, detail, died_at):
        if verdict == WAITING_HANDOFF_VERDICT:
            self.log(seat, "not restarted: a handoff waits that no supervisor acted on; user told",
                     died_at_about=timestamp(died_at), detail=str(detail))
            self.write_notice(seat, "waiting-handoff", WAITING_HANDOFF_NOTICE_TEMPLATE,
                              died_at=clock_text(died_at))
            return
        exit_code, recorded_at, session_id = detail[0], parse_timestamp(detail[1]) or died_at, detail[2]
        exit_description = ("an unknown exit code" if exit_code is None
                            else f"exit code {exit_code}")
        self.log(seat, "not restarted: its supervisor recorded an exit without resuming; "
                 "user told", exit_code=exit_code, recorded_at=timestamp(recorded_at))
        self.write_notice(seat, "recorded-exit", RECORDED_EXIT_NOTICE_TEMPLATE,
                          died_at=clock_text(recorded_at), exit_description=exit_description,
                          transcripts=path_on_the_mac(self.transcripts_directory(seat)),
                          question=self.recorded_exit_question(seat, exit_code),
                          restart_effect=(f"resumes {seat}'s last conversation" if session_id
                                          else f"starts {seat} as a fresh session"))


def run_command(command, environment=None):
    completed = subprocess.run(command, capture_output=True, text=True, env=environment,
                               check=False)
    return completed.returncode, (completed.stdout + completed.stderr).strip()


def recover_seat_in_clean_environment(seat, environment, run=run_command):
    # launch_seat in recover-crashed-seats.py removes agent-session and tmux variables on
    # both of its launch paths, and cron's environment carries none.
    return run([sys.executable, str(RECOVERY_PROGRAM), seat], environment)


def show_notice(path: str):
    """What a notice window on the Mac runs: the notice, then Enter closes it."""
    sys.stdout.write(Path(path).read_text(encoding="utf-8"))
    try:
        input(f"\n{SHOW_NOTICE_CLOSE_PROMPT}")
    except EOFError:
        pass
    return 0


def run_once(environment) -> int:
    state_directory = Path(environment.get(STATE_DIRECTORY_ENVIRONMENT_VARIABLE)
                           or STATE_DIRECTORY)
    log_directory = Path(environment.get(LOG_DIRECTORY_ENVIRONMENT_VARIABLE) or LOG_DIRECTORY)
    task_lists_directory = Path(environment.get(TASK_LISTS_DIRECTORY_ENVIRONMENT_VARIABLE)
                                or Path.home() / ".claude" / "tasks")
    state_directory.mkdir(parents=True, exist_ok=True)
    with (state_directory / f"{PROGRAM}.lock").open("w") as lock_stream:
        try:
            fcntl.flock(lock_stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            # A run that is still restarting a seat owns this minute.
            return 0
        try:
            return watch(environment, state_directory, log_directory, task_lists_directory)
        except Exception as error:  # noqa: BLE001 - a failed run must reach its owner, not only cron's log
            report_run_failure(f"{type(error).__name__}: {error}", state_directory,
                               log_directory, task_lists_directory)
            raise


def report_run_failure(error_text, state_directory: Path, log_directory: Path,
                       task_lists_directory: Path):
    """Log the failure, and hand it to AGENT_CRASH_WATCHER_PROGRAM_OWNER_AGENT_SEAT_NAME as a task the first time
    this error is seen.

    A task that cannot be written becomes a notice for the user, with its user-alert. A notice the
    Mac misses waits in the state every run reads, so a later run, failing or healthy, shows it
    once the Mac can be reached; when that state cannot be read or saved, the notice is not
    retried, and its user-alert alone reaches the user.
    """
    now = datetime.now(timezone.utc)
    reported_path = state_directory / f"{PROGRAM}-reported-run-failures.txt"
    reported = (reported_path.read_text(encoding="utf-8").splitlines()
                if reported_path.is_file() else [])
    state_path = state_directory / f"{PROGRAM}-state.json"
    try:
        state = read_state(state_path)
        state_readable = True
    except (OSError, ValueError):
        # The failure may be this file.
        state = {"seats": {}, "pending_notices": [], "reported_errors": []}
        state_readable = False
    watcher = Watcher(state=state, now=now, boot_at=now, log_directory=log_directory,
                      assess=None, died_at_about=None, transcripts_directory=None,
                      recover=None, open_window=open_mac_window,
                      show_notice_words=show_notice_words_for_window,
                      agent_seat_task_write=agent_seat_task_list_new_pending_task_writer_function_factory_for_task_lists_directory(task_lists_directory),
                      open_page=open_mac_browser_page,
                      user_alert_write_to_pending=user_alerts.user_alert_write_to_pending)
    watcher.log(None, "run failed", error=error_text)
    for notice in list(state["pending_notices"]):
        watcher.show(notice)
    if error_text not in reported:
        watcher.report_failure_to_agent_seat("watcher", "run-failed", error=error_text)
    if state_readable:
        try:
            write_state(state_path, state)
        except OSError as error:
            watcher.log(None, "could not save the watcher's state; a notice the Mac missed is not "
                        "retried", error=f"{type(error).__name__}: {error}")
    if error_text not in reported:
        with reported_path.open("a", encoding="utf-8") as stream:
            stream.write(error_text + "\n")


def agent_seat_task_list_new_pending_task_writer_function_factory_for_task_lists_directory(task_lists_directory: Path):
    """Return the Watcher's agent_seat_task_write, for the task lists under task_lists_directory."""
    def agent_seat_task_write(agent_seat, subject, description):
        task_list = task_lists_directory / f"nedschorus-{agent_seat}-tasks"
        return (agent_seat_task_list.agent_seat_task_list_new_pending_task_write(
            task_list, subject, description), task_list)
    return agent_seat_task_write


def open_mac_window(words):
    return run_command([sys.executable, str(MAC_WINDOW_OPENER_PROGRAM), *words])


def open_mac_browser_page(path):
    return run_command([sys.executable, str(MAC_BROWSER_PAGE_OPENER_PROGRAM), path])


def show_notice_words_for_window(path):
    return [sys.executable, str(Path(__file__).resolve()), "--show-notice", path]


def stopped_on_purpose_predicate(supervisor, handoff_directory: Path):
    """Return a test of a recorded exit: a clean exit, or one its supervisor recorded as a
    stop at an ask-user-before-restart handoff.

    The supervisor's own record of why it stopped decides, not the handoff file: an
    ask-user-before-restart handoff answered y stays on disk, consumed, while its successor runs,
    and that successor's later failure must still reach the user.
    """
    def stopped_on_purpose(seat, detail):
        if detail[0] == 0:
            return True
        return supervisor.agent_exit_record_is_a_stop_at_an_ask_user_before_restart_handoff(
            supervisor.read_supervisor_state(supervisor.supervisor_state_path(handoff_directory, seat)))
    return stopped_on_purpose


def handoff_down_agent_seat_records_stopped_on_purpose_predicate_factory(
        supervisor, records_reader, handoff_directory: Path):
    """Return a test of a down seat's records, read in recovery's order: a waiting
    ask-user-before-restart handoff, else a recorded exit that stopped_on_purpose_predicate accepts.

    A launch clears the exit record, so a record found here is the seat's latest stop.
    """
    stopped_on_purpose = stopped_on_purpose_predicate(supervisor, handoff_directory)

    def down_agent_seat_records_stopped_on_purpose(seat):
        state_path = supervisor.supervisor_state_path(handoff_directory, seat)
        waiting = records_reader.waiting_handoff_verdict(handoff_directory, seat, state_path)
        if waiting is not None:
            return waiting[0] == ASK_USER_BEFORE_RESTART_HANDOFF_VERDICT
        exit_record = supervisor.agent_exit_record_from_supervisor_state(
            supervisor.read_supervisor_state(state_path))
        return exit_record is not None and stopped_on_purpose(seat, exit_record)
    return down_agent_seat_records_stopped_on_purpose


def watch(environment, state_directory: Path, log_directory: Path,
          task_lists_directory: Path) -> int:
    login_restart = load_module("restart_live_seats_at_login", LOGIN_RESTART_PROGRAM)
    recovery = login_restart.recovery
    supervisor = login_restart.supervisor
    agents_root = recovery.default_agents_root()
    handoff_directory = recovery.default_handoff_directory()
    projects_root = Path("~/.claude/projects").expanduser()
    state_path = state_directory / f"{PROGRAM}-state.json"
    state = read_state(state_path)

    def assess(seat):
        return recovery.assess_seat(seat, agents_root, handoff_directory, projects_root)

    def died_at_about(seat):
        state_path_of_seat = supervisor.supervisor_state_path(handoff_directory, seat)
        return parse_timestamp(
            supervisor.read_supervisor_state(state_path_of_seat).get("last_poll_at"))

    def transcripts_directory(seat):
        return recovery.harness_project_directory(agents_root / seat, projects_root)

    def recover(seat):
        return recover_seat_in_clean_environment(seat, environment)

    def assess_as_though_leftover_shell_closed(seat, pane_process_ids):
        return recovery.predicted_assessment_once_the_leftover_idle_shell_is_closed(
            seat, agents_root, handoff_directory, projects_root, pane_process_ids)

    watcher = Watcher(
        state=state, now=datetime.now(timezone.utc), boot_at=login_restart.machine_boot_time(),
        log_directory=log_directory, assess=assess, died_at_about=died_at_about,
        transcripts_directory=transcripts_directory, recover=recover,
        open_window=open_mac_window, show_notice_words=show_notice_words_for_window,
        agent_seat_task_write=agent_seat_task_list_new_pending_task_writer_function_factory_for_task_lists_directory(task_lists_directory),
        open_page=open_mac_browser_page,
        user_alert_write_to_pending=user_alerts.user_alert_write_to_pending,
        stopped_on_purpose=stopped_on_purpose_predicate(supervisor, handoff_directory),
        recorded_exit_question=recovery.restart_question_for_a_seat_with_a_recorded_exit,
        open_seat_window=recovery.agent_seat_mac_window_open_unless_tmux_client_already_attached,
        seat_session_alive=recovery.tmux_session_alive_anywhere,
        assess_as_though_leftover_shell_closed=assess_as_though_leftover_shell_closed,
        down_agent_seat_records_stopped_on_purpose=(
            handoff_down_agent_seat_records_stopped_on_purpose_predicate_factory(
                supervisor, recovery.records_reader, handoff_directory)))
    try:
        watcher.run(recovery.list_agent_seat_names_with_agent_session_records(
            agents_root, handoff_directory))
    finally:
        write_state(state_path, state)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog=PROGRAM, description=__doc__.splitlines()[0])
    parser.add_argument("--show-notice", metavar="FILE")
    arguments = parser.parse_args(argv)
    if arguments.show_notice:
        return show_notice(arguments.show_notice)
    if sys.platform != "linux":
        print(f"{PROGRAM}: refused: this program watches ned-box's agent-seats and runs only "
              "on ned-box, where cron starts it.", file=sys.stderr)
        return 2
    return run_once(dict(os.environ))


if __name__ == "__main__":
    sys.exit(main())
