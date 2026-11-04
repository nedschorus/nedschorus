#!/usr/bin/env python3
"""Add claimed user alerts to the open approval-walk as the items right after its waiting item.

Usage:
  walk-me-through-user-alert-insert-after-waiting-item-raise-item-count-and-record-in-walk-minutes.py [--cwd DIR] ALERT_ID...

The walk-me-through UserPromptSubmit hook that claims alerts prints this command with the ids it claimed. For
each alert, read from user-alerts/claimed/<id>.json under ALERTS_MODULE_FILE's directory, in the order given:
- the walk-document gets a new unnumbered item, `## <the alert's title>`, right after the unit holding the last
  waiting item, which the walk-minutes' last `#next_to_present` line names, as the walk-me-through skill's
  Re-planning section says; its body holds the alert's text in a fence and what can be done about it. The
  walk check program's close step numbers it when it is shown, and counts M, so no other heading changes;
- the walk-minutes get a re-planning line and the line `#user_alert <id>`.
The open approval-walk is found with WALK_FINDER_FILE, in the checkout --cwd names, as the other walk-me-through
programs find it. The item gets no recommendation: the agent writes the case against and the `Recommendation:`
line, as the program's output says.

Exit 0 when every alert was added; 1, before changing any file, when no approval-walk is open, its waiting item
cannot be found in its walk-document, the walk-document's items sit under `##` part headings, where a `##`
heading is not an item, or an alert's file is missing or unreadable, with a message on stderr saying which and
what to do.

Agent-facing messages follow
docs/nedschorus-wiki/nedschorus-how-to-write-an-agent-facing-message-such-as-a-hook-refusal-or-script-error.md.
"""
import argparse
import importlib.util
import os
import re
import shlex
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHECKOUT = HERE.parents[2]
PROGRAM = Path(__file__).stem
WALK_FINDER_FILE = HERE / "walk-me-through-approval-walk-minutes-and-walk-document-item-finder-common.py"
ALERTS_MODULE_FILE = (CHECKOUT / "nc-systems" / "general-tools"
                      / "user-alerts-pending-and-claimed-files-write-claim-release-and-delete-common.py")

NO_WALK_MESSAGE = (
    "no approval-walk is open in {walk_directory}, so the alerts were not added. Open an approval-walk whose "
    "items are these alerts alone, as the walk-me-through skill says, and write a line `#user_alert <id>` into "
    "its walk-minutes for each alert as soon as you create them.")
UNUSABLE_WALK_MESSAGE = (
    "the open approval-walk's waiting item cannot be found, so no file was changed: {problem} Fix, as that problem "
    "says, the last `#next_to_present` line of the walk-minutes {minutes} or the item's heading in the "
    "walk-document {document}, then run again: {rerun}")
ALERT_UNREADABLE_MESSAGE = (
    "the alert {alert_id} cannot be read from {path}, so no file was changed: {error}.\n"
    "If the user-alerts hook printed other alert ids on the user's latest prompt, run again with those ids, "
    "leaving out {alert_id}: {rerun_without_ids} <the other ids>\n"
    "If it printed no other id, run nothing more.\n"
    "If {path} is gone, {alert_id} has either gone back to {pending_directory}, and is offered again on the "
    "user's next prompt, or was recorded in walk-minutes and deleted; nothing more is needed for it.\n"
    "If {path} is still there, it holds no readable alert: tell the user its path, because nobody else will see "
    "it.")
NO_UNNUMBERED_ITEMS_MESSAGE = (
    "the walk-document {document} holds its items under `##` part headings, so a `##` heading added there is "
    "not an item, and no file was changed. Add each alert to the walk-document by hand, as an item right after "
    "the waiting item, with the alert's title, its text and what can be done about it from its file under "
    "{claimed_directory}, and write a line `#user_alert <id>` into the walk-minutes {minutes} for each of these "
    "alerts: {ids}")
REPLANNED_MINUTES_LINE = ("- Re-planned {date}: added {count} unnumbered item(s) right after item {waiting}, from "
                          "the alerts a program wrote for the user: {titles}.")
ADDED_LINE = "Added the unnumbered item `## {title}` to {document}, right after item {waiting}."
NEXT_STEPS_LINES = (
    "Under each added item, write a line `#case_against <rating>: <the strongest case against your "
    "recommendation>`, the rating one of none, weak, medium, strong or very strong, and a line `Recommendation: "
    "<what you will do on ned-box, or what the user does and where>`, as the walk-me-through skill's section "
    "\"Each item\" says; until the `Recommendation:` line is there, the short-answer hook finds no recommendation "
    "for the item.",
    "In your next message to the user, say that you added the items, as the skill's section \"Re-planning\" "
    "says. Present each added item when its turn comes, as for any item; the walk check program numbers it then.",
)


def load_module(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


class Refused(Exception):
    pass


def fence_for(text):
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    return "`" * max(3, longest + 1)


def item_lines(alert):
    notice = str(alert.get("alert_text", "")).rstrip("\n")
    fence = fence_for(notice)
    return ["", f"## {alert.get('title')}", "",
            f"A program on ned-box wrote this alert for the user at {alert.get('written_at')}:", "",
            fence + "text", notice, fence, "", f"What can be done: {alert.get('action')}", ""]


def rerun_command(cwd, alert_ids):
    return " ".join(["python3", shlex.quote(str(Path(__file__).resolve())), "--cwd", shlex.quote(str(cwd)),
                     *(shlex.quote(alert_id) for alert_id in alert_ids)])


def insert(cwd, alert_ids, now=None):
    walk_finder = load_module("walk_me_through_approval_walk_minutes_and_walk_document_item_finder_common",
                              WALK_FINDER_FILE)
    user_alerts = load_module("user_alerts_pending_and_claimed_files_write_claim_release_and_delete_common",
                                ALERTS_MODULE_FILE)
    parser = walk_finder.markdown_parser()
    top = walk_finder.checkout_top(Path(cwd))
    walk_directory = (top or Path(cwd)) / walk_finder.WALK_DIRECTORY
    walk = walk_finder.open_walk(walk_directory, parser) if walk_directory.is_dir() else None
    if walk is None:
        raise Refused(NO_WALK_MESSAGE.format(walk_directory=walk_directory))
    minutes, value, _ = walk
    document = minutes.with_name(minutes.name[:-len(walk_finder.MINUTES_SUFFIX)] + ".md")
    try:
        numbers, total = walk_finder.parse_items(value)
        total, units = walk_finder.waiting_item_units(document, value, numbers, total, parser)
    except walk_finder.UnusableRange as problem:
        raise Refused(UNUSABLE_WALK_MESSAGE.format(problem=f"its `#next_to_present` line, `{value}`, {problem}",
                                                   minutes=minutes, document=document,
                                                   rerun=rerun_command(cwd, alert_ids)))
    alerts = []
    for alert_id in alert_ids:
        path = user_alerts.user_alerts_directory() / "claimed" / f"{alert_id}.json"
        try:
            alerts.append(user_alerts.user_alert_read_from_json_file(path))
        except (OSError, ValueError) as error:
            raise Refused(ALERT_UNREADABLE_MESSAGE.format(alert_id=alert_id, path=path, error=error,
                                                          pending_directory=path.parent.parent / "pending",
                                                          rerun_without_ids=rerun_command(cwd, [])))
    waiting = numbers[-1]
    unit = next(unit for unit in units if waiting in unit[0])
    text = document.read_text(encoding="utf-8")
    lines = text.split("\n")
    new_lines = [line for alert in alerts for line in item_lines(alert)]
    end = unit[4]
    while end > unit[3] + 1 and not lines[end - 1].strip():
        end -= 1
    new_text = "\n".join(lines[:end] + new_lines + lines[end:])
    unnumbered = walk_finder.approval_walk_unit_is_unnumbered_item
    if (sum(map(unnumbered, walk_finder.item_unit_spans(new_text, parser)))
            != sum(map(unnumbered, walk_finder.item_unit_spans(text, parser))) + len(alerts)):
        raise Refused(NO_UNNUMBERED_ITEMS_MESSAGE.format(
            document=document, minutes=minutes, ids=" ".join(alert_ids),
            claimed_directory=user_alerts.user_alerts_directory() / "claimed"))
    document.write_text(new_text, encoding="utf-8")
    date = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%d")
    minutes_lines = [REPLANNED_MINUTES_LINE.format(
        date=date, count=len(alerts), waiting=waiting, titles="; ".join(str(alert.get("title")) for alert in alerts))]
    minutes_lines += [f"#user_alert {alert.get('id')}" for alert in alerts]
    existing = minutes.read_text(encoding="utf-8")
    separator = "" if existing.endswith("\n") or not existing else "\n"
    minutes.write_text(existing + separator + "\n".join(minutes_lines) + "\n", encoding="utf-8")
    output = [ADDED_LINE.format(title=alert.get("title"), document=document, waiting=waiting) for alert in alerts]
    return output + list(NEXT_STEPS_LINES)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("alert_ids", nargs="+", metavar="ALERT_ID")
    parser.add_argument("--cwd", default=os.getcwd(), help="a directory in the walk's checkout")
    arguments = parser.parse_args(argv)
    try:
        print("\n".join(insert(arguments.cwd, arguments.alert_ids)))
    except Refused as refusal:
        print(f"{PROGRAM}: {refusal.args[0]}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
