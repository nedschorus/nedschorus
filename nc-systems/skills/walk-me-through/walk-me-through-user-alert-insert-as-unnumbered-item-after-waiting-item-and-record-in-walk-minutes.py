#!/usr/bin/env python3
"""Add claimed user alerts to the open approval-walk as the items right after its waiting item.

Usage:
  walk-me-through-user-alert-insert-as-unnumbered-item-after-waiting-item-and-record-in-walk-minutes.py [--cwd DIR] ALERT_ID...

The walk-me-through UserPromptSubmit hook that claims alerts runs this command with the ids it claimed. For
each alert, read from user-alerts/claimed/<id>.json under ALERTS_MODULE_FILE's directory, in the order given:
- the walk-document gets a new unnumbered item, `## <the alert's title>`, right after the unit holding the last
  waiting item, which the walk-minutes' last `#next_to_present` line names, as the walk-me-through skill's
  Re-planning section says; its body holds a `#approval_walk_item_first_entered` line giving the day, on this
  machine's clock, the alert was written, the alert's text in a fence and what can be done about it. A title
  that a `##` heading would not read as an unnumbered item, such as "Item 3 of 9: reboot", gets the prefix
  "User alert: ". This program writes no number and no category line: the walk check program's close step
  chooses when, among the items not yet shown, the user sees the item, by its category, the items it waits on
  and that day, so it need not come right after the waiting item, and writes `Item K of M: ` into its heading
  then; the category needs judgment, so the program's output tells the agent to write it;
- the walk-minutes get a re-planning line, each title in it a code span so that a `#next_to_present` in a
  title is not read as the walk's marker, and the line `#user_alert <id>`.
The open approval-walk is found with WALK_FINDER_FILE, in the checkout --cwd names, as the other walk-me-through
programs find it. The item gets no recommendation: the agent writes the case against and the `Recommendation:`
line, as the program's output says.

Exit 0 when every alert was added; 1, before changing any file, when no approval-walk is open, its waiting item
cannot be found in its walk-document, the walk-document's items sit under `##` part headings, where a `##`
heading is not an item, or an alert's file is missing or unreadable, its `written_at` included, with a message
on stderr saying which and what to do.

Tool-messages-to-agent follow
docs/nedschorus-wiki/nedschorus-how-to-write-a-tool-message-to-agent-such-as-a-hook-refusal-or-script-error.md.
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
WALK_CHECK_PROGRAM = HERE / "walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py"
ALERTS_MODULE_FILE = (CHECKOUT / "nc-systems" / "general-tools"
                      / "user-alerts-pending-and-claimed-files-write-claim-release-and-delete-common.py")

NO_WALK_MESSAGE = (
    "no approval-walk is open in {walk_directory}, so the alerts were not added. Open an approval-walk whose "
    "items are these alerts alone, as the walk-me-through skill says, and write a line `#user_alert <id>` into "
    "its walk-minutes for each alert as soon as you create them.")
MORE_THAN_ONE_WALK_MESSAGE = (
    "more than one approval-walk is open or paused in {walk_directory}, so this program cannot tell which one the "
    "alerts belong in, and no file was changed. A paused approval-walk counts as unclosed, the same as an open one. "
    "The walk-minutes of each unclosed approval-walk:\n"
    "{minutes}\n"
    "Close each of them that has no item the user has yet to answer. To close one, add the line "
    "`#next_to_present none, closed` as the last line of its walk-minutes, then run, from the checkout that holds "
    "{walk_directory}: python3 nc-systems/skills/walk-me-through/walk-files-ship.py <name>, <name> being its walk-minutes file name without "
    "-minutes.md.\n"
    "If more than one still has items the user has yet to answer: keep the one your last message to him showed an "
    "item of, or else the one whose walk-minutes changed last; move the others' unanswered items into its "
    "walk-document as the walk-me-through skill's paragraph on more than one open approval-walk says, and close the "
    "others.\n"
    "If the approval-walk you keep is paused: resume it, by adding the line `#next_to_present item N of M`, naming "
    "its waiting item, below its `#approval_walk_paused` line.\n"
    "Then run again: {rerun}\n"
    "If none is left unclosed, the run again tells you to open a new approval-walk for the alerts; do that.")
UNUSABLE_WALK_MESSAGE = (
    "the open approval-walk's waiting item cannot be found, so no file was changed: {problem} Fix, as that problem "
    "says, the last `#next_to_present` line of the walk-minutes {minutes} or the item's heading in the "
    "walk-document {document}, then run again: {rerun}")
ALERT_UNREADABLE_MESSAGE = (
    "the alert {alert_id} cannot be read from {path}, so no file was changed: {error}.\n"
    "{rerun_line}"
    "Then, if {path} no longer exists, nothing more is needed for {alert_id}: it is either offered again on the "
    "user's next prompt or already recorded in walk-minutes.\n"
    "If {path} still exists, it holds no readable alert: tell the user its path, because nobody else will see "
    "it.")
ALERT_UNREADABLE_RERUN_LINE = "Run again with the other alerts, leaving out {alert_id}: {rerun}\n"
NO_UNNUMBERED_ITEMS_MESSAGE = (
    "the walk-document {document} holds its items under `##` part headings, so a `##` heading added there is "
    "not an item, and no file was changed. Add each alert to the walk-document by hand, as an item right after "
    "the waiting item, with the alert's title, its text and what can be done about it from its file under "
    "{claimed_directory}, and write a line `#user_alert <id>` into the walk-minutes {minutes} for each of these "
    "alerts: {ids}")
UNNUMBERED_TITLE_PREFIX = "User alert: "
REPLANNED_MINUTES_LINE = ("- Re-planned {date}: added {count} unnumbered item(s) right after item {waiting}, from "
                          "the alerts a program wrote for the user: {titles}.")
ADDED_LINE = "Added the unnumbered item `## {title}` to {document}, right after item {waiting}."
NEXT_STEPS_LINES = (
    "Under the heading of each item added to the walk-document, write a line of its own naming its category, the "
    "one for how soon its work must happen, one of {category_tags}, and a line `{waits_on_tag} <title>` for each "
    "item it must follow, as the walk-me-through skill's section \"Re-planning\" says; the walk check program's "
    "close step refuses to move the walk on until each has its category line.",
    "At the end of each item added to the walk-document, write a line `#case_against <rating>: <the strongest case against your "
    "recommendation>`, the rating one of weak, medium, strong or very strong, or the line `#case_against none.` "
    "when there is no case against; then a line `The alternative: <what you will do if the user disapproves>`; then a line "
    "`Recommendation: "
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


def heading_title(title, walk_finder, parser):
    """title, with UNNUMBERED_TITLE_PREFIX when a `##` heading of title alone would not be an unnumbered item."""
    probe = f"## Item 1 of 1: probe\n\n## {title}\n"
    if sum(map(walk_finder.approval_walk_unit_is_unnumbered_item, walk_finder.item_unit_spans(probe, parser))) == 1:
        return title
    return UNNUMBERED_TITLE_PREFIX + title


def first_entered_day(alert):
    """The day, on this machine's clock, of the alert's `written_at`; raise ValueError when it is not an ISO 8601
    time."""
    return datetime.fromisoformat(str(alert.get("written_at"))).astimezone().date().isoformat()


def item_lines(alert, title, first_entered_tag):
    notice = str(alert.get("alert_text", "")).rstrip("\n")
    fence = fence_for(notice)
    return ["", f"## {title}", "", f"{first_entered_tag} {first_entered_day(alert)}", "",
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
    try:
        walk = walk_finder.open_walk(walk_directory, parser) if walk_directory.is_dir() else None
    except walk_finder.MoreThanOneUnclosedApprovalWalk as several:
        raise Refused(MORE_THAN_ONE_WALK_MESSAGE.format(
            walk_directory=walk_directory, minutes="\n".join(f"  {path}" for path in several.minutes_paths),
            rerun=rerun_command(cwd, alert_ids)))
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
            alert = user_alerts.user_alert_read_from_json_file(path)
            # Read here, before any file is changed, so an unreadable `written_at` refuses like an unreadable file.
            first_entered_day(alert)
            alerts.append(alert)
        except (OSError, ValueError) as error:
            others = [other for other in alert_ids if other != alert_id]
            rerun_line = (ALERT_UNREADABLE_RERUN_LINE.format(alert_id=alert_id, rerun=rerun_command(cwd, others))
                          if others else "")
            raise Refused(ALERT_UNREADABLE_MESSAGE.format(alert_id=alert_id, path=path, error=error,
                                                          rerun_line=rerun_line))
    waiting = numbers[-1]
    unit = next(unit for unit in units if waiting in unit[0])
    text = document.read_text(encoding="utf-8")
    lines = text.split("\n")
    titles = [heading_title(str(alert.get("title")), walk_finder, parser) for alert in alerts]
    check_program = load_module("walk_me_through_answer_added_texts_cold_read_fast_read_check_and_close",
                                WALK_CHECK_PROGRAM)
    new_lines = [line for alert, title in zip(alerts, titles)
                 for line in item_lines(alert, title, check_program.WALK_FIRST_ENTERED_TAG)]
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
        date=date, count=len(alerts), waiting=waiting,
        titles="; ".join(map(walk_finder.text_wrapped_as_markdown_code_span, titles)))]
    minutes_lines += [f"#user_alert {alert.get('id')}" for alert in alerts]
    existing = minutes.read_text(encoding="utf-8")
    separator = "" if existing.endswith("\n") or not existing else "\n"
    minutes.write_text(existing + separator + "\n".join(minutes_lines) + "\n", encoding="utf-8")
    output = [ADDED_LINE.format(title=title, document=document, waiting=waiting) for title in titles]
    category_tags = ", ".join(f"`{check_program.WALK_CATEGORY_TAG}{category}`"
                              for category in check_program.WALK_CATEGORIES)
    return output + [line.format(category_tags=category_tags, waits_on_tag=check_program.WALK_WAITS_ON_TAG)
                     for line in NEXT_STEPS_LINES]


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
