#!/usr/bin/env python3
"""Add claimed user alerts to the open approval-walk as the items right after its waiting item.

Usage:
  walk-me-through-user-alert-insert-after-waiting-item-raise-item-count-and-record-in-walk-minutes.py [--cwd DIR] ALERT_ID...

The walk-me-through UserPromptSubmit hook that claims alerts prints this command with the ids it claimed. For
each alert, read from user-alerts/claimed/<id>.json under ALERTS_MODULE_FILE's directory, in the order given:
- the walk-document gets a new item right after the unit holding the last waiting item N, which the walk-minutes'
  last `#next_to_present` line names, numbered N.K with K the lowest number no item of the walk uses, as the
  walk-me-through skill's Re-planning section says; its heading copies the waiting item's heading level and
  reads `Item N.K of M: <the alert's title>`, and its body holds the alert's notice text in a fence and what can
  be done about it;
- every running count `Item ... of M` that opens a line outside code in the walk-document gets M raised by one;
- the walk-minutes get a re-planning line, the line `#user_alert <id>`, and, below every earlier one, a
  `#next_to_present` line naming the same waiting items with the new M.
The open approval-walk is found with WALK_FINDER_FILE, in the checkout --cwd names, as the other walk-me-through
programs find it. The item gets no recommendation: the agent writes the case against and the `Recommendation:`
line, as the program's output says.

Exit 0 when every alert was added; 1, before changing any file, when no approval-walk is open, its waiting item
cannot be found in its walk-document, or an alert's file is missing or unreadable, with one line on stderr
saying which and what to do.

Agent-facing messages follow
docs/nedschorus-wiki/nedschorus-how-to-write-an-agent-facing-message-such-as-a-hook-refusal-or-script-error.md.
"""
import argparse
import importlib.util
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHECKOUT = HERE.parents[2]
PROGRAM = Path(__file__).stem
WALK_FINDER_FILE = HERE / "walk-me-through-approval-walk-minutes-and-walk-document-item-finder-common.py"
ALERTS_MODULE_FILE = (CHECKOUT / "nc-systems" / "general-tools"
                      / "user-alerts-pending-and-claimed-files-write-claim-and-release-common.py")
LINE_OPENING = re.compile(r"^(?:#{1,6}\s+|[-*+]\s+)?")
HEADING_LEVEL = re.compile(r"^(#{1,6})\s")

NO_WALK_MESSAGE = (
    "no approval-walk is open in {walk_directory}, so the alerts were not added. Open an approval-walk whose "
    "items are these alerts alone, as the walk-me-through skill says, and write a line `#user_alert <id>` into "
    "its walk-minutes for each alert as soon as you create them.")
UNUSABLE_WALK_MESSAGE = (
    "the open approval-walk's waiting item cannot be found, so no file was changed: {problem} Fix the walk-minutes' "
    "last `#next_to_present` line or the walk-document's heading as that says, then run this command again.")
ALERT_UNREADABLE_MESSAGE = (
    "the alert {alert_id} cannot be read from {path}, so no file was changed: {error}. Run this command again "
    "with only the ids the user-alerts hook printed on the user's latest prompt; an alert that is no longer in "
    "claimed/ has gone back to pending/ or been recorded, and is offered again on his next prompt.")
REPLANNED_MINUTES_LINE = ("- Re-planned {date}: added {items}, from the alerts a program wrote for the user, "
                          "right after item {waiting}; the walk now has {total} items.")
ADDED_LINE = "Added item {number} of {total}, {title}, to {document}."
NEXT_STEPS_LINES = (
    "Under each added item, write the strongest case against your recommendation and a line `Recommendation: "
    "<what you will do on ned-box, or what the user does and where>`, as the walk-me-through skill's section "
    "\"Each item\" says; until you do, the short-answer hook finds no recommendation for the item.",
    "In your next message to the user, say that you added the items and that the walk now has {total} items, as "
    "the skill's section \"Re-planning\" says. Present each added item when its turn comes, as for any item.",
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


def item_lines(heading_hashes, number, total, alert):
    notice = str(alert.get("notice_text", "")).rstrip("\n")
    fence = fence_for(notice)
    return ["", f"{heading_hashes} Item {number} of {total}: {alert.get('title')}", "",
            f"A program on ned-box wrote this alert for the user at {alert.get('written_at')}:", "",
            fence + "text", notice, fence, "", f"What can be done: {alert.get('action')}", ""]


def raised_counts(text, total, new_total, walk_finder, parser):
    """text with M raised to new_total in every running count `Item ... of M` that opens a line outside code."""
    lines = text.split("\n")
    prose = walk_finder.prose_lines(text, parser)
    count = re.compile(rf"(items?\s+{walk_finder.NUMBER_LIST}\s+of\s+){total}\b", re.I)
    for index, line in enumerate(prose):
        rest = line[LINE_OPENING.match(line).end():]
        match = walk_finder.HEADING_COUNT.match(rest)
        if match and match[2] == total:
            start = len(line) - len(rest)
            lines[index] = lines[index][:start] + count.sub(rf"\g<1>{new_total}", rest, count=1)
    return "\n".join(lines)


def insert(cwd, alert_ids, now=None):
    walk_finder = load_module("walk_me_through_approval_walk_minutes_and_walk_document_item_finder_common",
                              WALK_FINDER_FILE)
    user_alerts = load_module("user_alerts_pending_and_claimed_files_write_claim_and_release_common",
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
        raise Refused(UNUSABLE_WALK_MESSAGE.format(problem=f"its `#next_to_present` line, `{value}`, {problem}"))
    alerts = []
    for alert_id in alert_ids:
        path = user_alerts.user_alerts_directory() / "claimed" / f"{alert_id}.json"
        try:
            alerts.append(user_alerts.user_alert_read_from_json_file(path))
        except (OSError, ValueError) as error:
            raise Refused(ALERT_UNREADABLE_MESSAGE.format(alert_id=alert_id, path=path, error=error))
    waiting = numbers[-1]
    unit = next(unit for unit in units if waiting in unit[0])
    text = document.read_text(encoding="utf-8")
    lines = text.split("\n")
    level = HEADING_LEVEL.match(lines[unit[3]])
    heading_hashes = level[1] if level else "##"
    used = {number for each in walk_finder.item_unit_spans(text, parser) for number in each[0]}
    new_total = str(int(total) + len(alerts))
    added, new_lines = [], []
    for alert in alerts:
        index = 1
        while f"{waiting}.{index}" in used:
            index += 1
        number = f"{waiting}.{index}"
        used.add(number)
        added.append((number, alert))
        new_lines += item_lines(heading_hashes, number, new_total, alert)
    end = unit[4]
    while end > unit[3] + 1 and not lines[end - 1].strip():
        end -= 1
    text = "\n".join(lines[:end] + new_lines + lines[end:])
    document.write_text(raised_counts(text, total, new_total, walk_finder, parser), encoding="utf-8")
    count = walk_finder.VALUE_COUNT.match(value)
    named = f"item{'s' if len(numbers) > 1 else ''} {count[1]} of {new_total}"
    date = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%d")
    minutes_lines = [REPLANNED_MINUTES_LINE.format(
        date=date, items=", ".join(f"item {number}" for number, _ in added), waiting=waiting, total=new_total)]
    minutes_lines += [f"#user_alert {alert.get('id')}" for _, alert in added]
    minutes_lines.append(f"#next_to_present {named}")
    existing = minutes.read_text(encoding="utf-8")
    separator = "" if existing.endswith("\n") or not existing else "\n"
    minutes.write_text(existing + separator + "\n".join(minutes_lines) + "\n", encoding="utf-8")
    output = [ADDED_LINE.format(number=number, total=new_total, title=alert.get("title"), document=document)
              for number, alert in added]
    return output + [line.format(total=new_total) for line in NEXT_STEPS_LINES]


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
