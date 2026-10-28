#!/usr/bin/env python3
"""UserPromptSubmit hook, on ned-box only: on a prompt the user typed, claim the alerts programs wrote for him,
and tell the agent to add them to his approval-walk as items right after the waiting item.

Wired as a UserPromptSubmit hook in .claude/settings.json. Off Linux, that is on the Mac, it exits 0 at once:
Mac agent-sessions take no alerts until a renaming test over /Volumes/nedhome says they can.

ONLY A PROMPT THE USER TYPED claims. Claude Code also starts this hook for a background-task notice and for
another agent-session's message. The transcript's newest record carrying `turnOrigin` decides, `human` for his
own, when that record's text is the payload's prompt; Claude Code may not have written the prompt's record yet
when this hook runs, and the newest record is then the previous turn's. Otherwise the prompt itself decides: one
that opens as NOT_TYPED_PROMPT_OPENINGS lists is not his.

ON A TYPED PROMPT the hook calls, from ALERTS_MODULE_FILE, user_alerts_claimed_delete_if_recorded_in_approval_walk_minutes_else_release_to_pending_after_30_minutes,
then user_alerts_claim_every_pending_by_rename_into_claimed, whose docstrings say what each moves. When it claimed nothing it prints nothing.
Otherwise it finds the open approval-walk of the checkout the payload's cwd names with WALK_FINDER_FILE, the
module the other walk-me-through hooks use, and its additionalContext tells the agent:
- with an approval-walk open: to run INSERT_PROGRAM with the claimed ids before acting on the prompt, so each
  alert becomes the item right after the waiting item;
- with none open: to answer the prompt first, then open an approval-walk with the alerts as its only items and
  write each alert's `#user_alert <id>` line into its walk-minutes;
- when the walk files cannot be read: both, each under its condition.

FAILURES. A payload that is not JSON: one line on stderr, exit 1. A failure claiming alerts: additionalContext
says what failed and that alerts may be waiting unseen, and has the agent tell the user, since an alert is
how a program reaches him.

Agent-facing messages follow
docs/nedschorus-wiki/nedschorus-how-to-write-an-agent-facing-message-such-as-a-hook-refusal-or-script-error.md.
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHECKOUT = HERE.parents[2]
WALK_FINDER_FILE = HERE / "walk-me-through-approval-walk-minutes-and-walk-document-item-finder-common.py"
INSERT_PROGRAM = HERE / "walk-me-through-user-alert-insert-after-waiting-item-raise-item-count-and-record-in-walk-minutes.py"
ALERTS_MODULE_FILE = (CHECKOUT / "nc-systems" / "general-tools"
                      / "user-alerts-pending-and-claimed-files-write-claim-release-and-delete-common.py")
TRANSCRIPT_READER_FILE = CHECKOUT / "scripts" / "claude-code-session-transcript-records-read-backward-common.py"
USER_TURN_ORIGIN = "human"
# How Claude Code opens a background-task notice, another agent-session's message and a subagent's hand-back.
NOT_TYPED_PROMPT_OPENINGS = ("<task-notification>", "<cross-session-message", "<agent-message",
                             "Another Claude session sent a message", "A peer session sent a message")

CLAIMED_OPENING = ("The user-alerts hook claimed {count} alert(s) that programs on ned-box wrote for the user, "
                   "each a problem he has not yet seen:")
ALERT_LINE = "- {title} (alert {id}, file {path})"
WALK_OPEN_LINES = (
    "Before you act on the user's prompt, add the alerts to approval-walk {walk} as items right after its "
    "waiting item, by running:",
    "  python3 {program} --cwd {cwd} {ids}",
    "It numbers each item as the walk-me-through skill's Re-planning section says, raises the walk's item count, "
    "and writes each alert's `#user_alert <id>` line into the walk-minutes, which keeps the alert from being "
    "offered again. Then do what it prints, and act on the user's prompt.",
)
NO_WALK_LINES = (
    "No approval-walk is open in this checkout. First answer the user's prompt. Then open an approval-walk, as "
    "the walk-me-through skill says, whose items are these alerts alone, one each, its point the alert's title "
    "and its text from the alert's file.",
    "As soon as you create its walk-minutes, write these lines into them, one per alert; an alert that no "
    "walk-minutes name 30 minutes after this prompt is offered again on the user's next prompt:",
)
USER_ALERT_LINE = "  #user_alert {id}"
WALK_UNKNOWN_LINE = ("The hook could not tell whether an approval-walk is open in this checkout, because reading "
                     "the walk files failed: {error}. Look yourself: the last `#next_to_present` line in each "
                     "docs/walk/*-minutes.md names its waiting item, and a value other than `none` or `closed` "
                     "marks the approval-walk open.")
IF_WALK_OPEN = "If an approval-walk is open:"
IF_NO_WALK = "If no approval-walk is open:"
CLAIM_FAILED_LINES = (
    "The user-alerts hook failed while claiming alerts, so an alert a program on ned-box wrote for the user may "
    "be waiting in {directory} where nobody sees it: {error}.",
    "Tell the user in one line, after answering his prompt: \"The hook that brings program alerts into your "
    "approval-walk failed on ned-box ({error}), so a program's alert may be waiting unseen in {directory}.\" "
    "Recommend that an agent on ned-box fix the cause.",
    "If you are a subagent, pass the same fact to the agent that dispatched you.",
)


def load_module(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def record_text(record):
    content = (record.get("message") or {}).get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(block.get("text", "") for block in content
                       if isinstance(block, dict) and block.get("type") == "text")
    return None


def typed_by_user(payload):
    prompt = payload.get("prompt") or ""
    transcript = payload.get("transcript_path")
    if transcript and Path(transcript).expanduser().is_file():
        reader = load_module("claude_code_session_transcript_records_read_backward_common", TRANSCRIPT_READER_FILE)
        for record in reader.records_newest_first(Path(transcript).expanduser()):
            if "turnOrigin" in record:
                if record_text(record) == prompt:
                    return record["turnOrigin"] == USER_TURN_ORIGIN
                break
    return not prompt.lstrip().startswith(NOT_TYPED_PROMPT_OPENINGS)


def open_walk_name(cwd):
    """The open approval-walk's name, or None when none is open in cwd's checkout."""
    walk_finder = load_module("walk_me_through_approval_walk_minutes_and_walk_document_item_finder_common",
                              WALK_FINDER_FILE)
    top = walk_finder.checkout_top(Path(cwd))
    if top is None or not (top / walk_finder.WALK_DIRECTORY).is_dir():
        return None
    walk = walk_finder.open_walk(top / walk_finder.WALK_DIRECTORY, walk_finder.markdown_parser())
    return None if walk is None else walk[0].name[:-len(walk_finder.MINUTES_SUFFIX)]


def context_for(alerts, claimed_directory, cwd):
    lines = [CLAIMED_OPENING.format(count=len(alerts))]
    lines += [ALERT_LINE.format(title=alert.get("title"), id=alert.get("id"),
                                path=claimed_directory / f"{alert.get('id')}.json") for alert in alerts]
    ids = " ".join(str(alert.get("id")) for alert in alerts)
    no_walk_lines = list(NO_WALK_LINES) + [USER_ALERT_LINE.format(id=alert.get("id")) for alert in alerts]

    def walk_lines(walk):
        return [line.format(program=INSERT_PROGRAM, cwd=cwd, ids=ids, walk=walk) for line in WALK_OPEN_LINES]
    try:
        walk = open_walk_name(cwd)
    except Exception as error:  # noqa: BLE001 - any failure reading the walk is reported with both branches
        return "\n".join(lines + [WALK_UNKNOWN_LINE.format(error=repr(error)), IF_WALK_OPEN]
                         + walk_lines("<its name>") + [IF_NO_WALK] + no_walk_lines)
    return "\n".join(lines + (no_walk_lines if walk is None else walk_lines(walk)))


def output_for(payload, user_alerts=None):
    """Return the hook's output for the payload as a dict, or None."""
    if sys.platform != "linux" or not typed_by_user(payload):
        return None
    user_alerts = user_alerts or load_module(
        "user_alerts_pending_and_claimed_files_write_claim_release_and_delete_common", ALERTS_MODULE_FILE)
    directory = user_alerts.user_alerts_directory()
    try:
        user_alerts.user_alerts_claimed_delete_if_recorded_in_approval_walk_minutes_else_release_to_pending_after_30_minutes()
        alerts = user_alerts.user_alerts_claim_every_pending_by_rename_into_claimed()
    except Exception as error:  # noqa: BLE001 - a failed claim must reach the user through the agent
        context = "\n".join(line.format(directory=directory, error=repr(error)) for line in CLAIM_FAILED_LINES)
    else:
        if not alerts:
            return None
        context = context_for(alerts, directory / "claimed", payload.get("cwd") or os.getcwd())
    return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": context}}


def main():
    try:
        output = output_for(json.loads(sys.stdin.read()))
    except Exception as error:  # noqa: BLE001
        print(f"walk-me-through-pending-user-alerts-claim-and-hand-to-agent-as-approval-walk-items-user-prompt-submit-hook: the "
              f"hook failed, so no alert was claimed or offered on this prompt: {error!r}", file=sys.stderr)
        return 1
    if output is not None:
        print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
