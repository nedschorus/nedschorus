#!/usr/bin/env python3
"""Tests for the handoff-supervisor's line naming the open approval-walk's
waiting item and its last page link in a successor's
initial-agent-instructions:
successor_initial_agent_instructions_line_naming_waiting_approval_walk_item
on fixture walk-minutes and walk-documents (open, closed, paused, no `#item_page` line, a failed
publish, two open walks, several waiting items, no point, an unreadable
walk), and where the line goes in the prompts both ignition plans compose and
in the prompt the launch site hands the successor.

Run: python3 nc-systems/handoff/tests/handoff-supervisor-successor-initial-agent-instructions-line-naming-waiting-approval-walk-item-test.py

Prints one line per case and exits non-zero if any case fails.
"""

import contextlib
import importlib.util
import io
import os
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "handoff_supervisor_test_fixture", Path(__file__).resolve().with_name("handoff-supervisor-test-fixture.py"))
fixture = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fixture)

supervisor = fixture.supervisor
check = fixture.check

WALK = "fixture-open-items-2026-11-10"
LINK = "https://claude.ai/artifact/FixtureItemTwoPage"
WALK_DOCUMENT = (
    "# Fixture open items\n\n"
    "## Item 1 of 3: Keep the first thing\n\nRecommendation: keep it.\n\n"
    "## Item 2 of 3: Show the waiting item's working link\n\nRecommendation: show it.\n\n"
    "## Item 3 of 3\n\nRecommendation: none.\n")


def lines_for(root):
    return supervisor.successor_initial_agent_instructions_line_naming_waiting_approval_walk_item(root)


def walk_in(root, minutes, document=WALK_DOCUMENT, name=WALK):
    walk_directory = root / "docs" / "walk"
    walk_directory.mkdir(parents=True, exist_ok=True)
    if document is not None:
        (walk_directory / f"{name}.md").write_text(document, encoding="utf-8")
    minutes_path = walk_directory / f"{name}-minutes.md"
    minutes_path.write_text(minutes, encoding="utf-8")
    return minutes_path


def approved_line(walk, count_and_point, link, count):
    """The approved text of item 5.2.2.8 of approval-walk ned-box-helper-open-items-2026-10-27, filled in."""
    return (f"Approval-walk {walk}: item {count_and_point} is waiting for the user; its last page link is "
            f"{link}. Before your first message, open that page with the Artifact tool. If it is gone, publish "
            f"the item again from docs/walk/{walk}.md and append the line \"#item_page item {count} <new link>\" "
            f"to docs/walk/{walk}-minutes.md. Show the item in full, and end your first message with its closing "
            f"line, holding the link that opens.")


def without_link_line(walk, count_and_point, count):
    return (f"Approval-walk {walk}: item {count_and_point} is waiting for the user; the walk-minutes record no "
            f"page link for it. Before your first message, publish the item from docs/walk/{walk}.md and append "
            f"the line \"#item_page item {count} <new link>\" to docs/walk/{walk}-minutes.md. Show the item in "
            f"full, and end your first message with its closing line, holding the link that opens.")


OPEN_MINUTES = (
    "#next_to_present item 1 of 3\n"
    "#item_page item 2 of 3 https://claude.ai/artifact/OlderPage\n"
    "item 1 of 3: approved.\n"
    "#next_to_present item 2 of 3\n"
    f"#item_page item 2 of 3 {LINK}\n")
POINT = "Show the waiting item's working link"


def run_walk_minutes_cases(workspace):
    root = workspace / "no-walk-directory"
    root.mkdir(parents=True)
    check("no docs/walk: no line", lines_for(root) == (), repr(lines_for(root)))

    root = workspace / "open"
    walk_in(root, OPEN_MINUTES)
    expected = (approved_line(WALK, f"2 of 3, {POINT},", LINK, "2 of 3"),)
    check("an open walk: the approved text, with the walk, the waiting item, its point and its newest page link",
          lines_for(root) == expected, f"{lines_for(root)!r}\nexpected {expected!r}")

    root = workspace / "closed"
    walk_in(root, OPEN_MINUTES + "item 2 of 3: approved.\n#next_to_present none, closed\n")
    check("a closed walk: no line", lines_for(root) == (), repr(lines_for(root)))

    root = workspace / "paused"
    walk_in(root, OPEN_MINUTES + "#approval_walk_paused the user is away\n")
    check("a paused walk: no line", lines_for(root) == (), repr(lines_for(root)))

    root = workspace / "resumed"
    walk_in(root, OPEN_MINUTES + "#approval_walk_paused the user is away\n#next_to_present item 2 of 3\n")
    check("a walk resumed after a pause: the line",
          lines_for(root) == expected, repr(lines_for(root)))

    root = workspace / "no-item-page"
    walk_in(root, "#next_to_present item 2 of 3\n#item_page item 1 of 3 https://claude.ai/artifact/ItemOne\n")
    check("no `#item_page` line for the waiting item: the line says so and says to publish it",
          lines_for(root) == (without_link_line(WALK, f"2 of 3, {POINT},", "2 of 3"),), repr(lines_for(root)))

    root = workspace / "publish-failed"
    walk_in(root, OPEN_MINUTES + "#item_page item 2 of 3 publish failed: the Artifact tool timed out\n")
    check("a newest `#item_page` line recording a failed publish: the line without a link",
          lines_for(root) == (without_link_line(WALK, f"2 of 3, {POINT},", "2 of 3"),), repr(lines_for(root)))

    root = workspace / "no-point"
    walk_in(root, "#next_to_present item 3 of 3\n#item_page item 3 of 3 https://claude.ai/artifact/ItemThree\n")
    check("a heading that states no point: the count alone",
          lines_for(root) == (approved_line(WALK, "3 of 3", "https://claude.ai/artifact/ItemThree", "3 of 3"),),
          repr(lines_for(root)))

    root = workspace / "no-total"
    walk_in(root, "#next_to_present item 2\n" f"#item_page item 2 of 3 {LINK}\n")
    check("a `#next_to_present` line without `of M`: M counted from the walk-document",
          lines_for(root) == expected, repr(lines_for(root)))

    root = workspace / "several-items"
    walk_in(root, "#next_to_present items 2 and 3 of 3\n"
                  f"#item_page item 2 of 3 {LINK}\n#item_page item 3 of 3 https://claude.ai/artifact/ItemThree\n")
    check("a line naming several waiting items: the first, where the walk resumes",
          lines_for(root) == expected, repr(lines_for(root)))

    root = workspace / "two-open"
    older = walk_in(root, "#next_to_present item 1 of 3\n#item_page item 1 of 3 https://claude.ai/artifact/Old\n",
                    name="fixture-older-walk")
    newer = walk_in(root, OPEN_MINUTES)
    # Modification times set explicitly, newer first in file-name order, so neither write order nor name order
    # can pick the walk.
    os.utime(newer, (2_000_000_000, 2_000_000_000))
    os.utime(older, (1_000_000_000, 1_000_000_000))
    check("two open walks: the one with the latest walk-minutes",
          lines_for(root) == expected, repr(lines_for(root)))
    os.utime(older, (3_000_000_000, 3_000_000_000))
    check("two open walks, the other's walk-minutes now latest: that one",
          lines_for(root) == (approved_line("fixture-older-walk", "1 of 3, Keep the first thing,",
                                            "https://claude.ai/artifact/Old", "1 of 3"),),
          repr(lines_for(root)))

    root = workspace / "open-and-paused"
    paused = walk_in(root, "#next_to_present item 1 of 3\n#approval_walk_paused away\n", name="fixture-paused-walk")
    walk_in(root, OPEN_MINUTES)
    os.utime(paused, (3_000_000_000, 3_000_000_000))
    check("an open walk beside a later paused one: the open one",
          lines_for(root) == expected, repr(lines_for(root)))

    root = workspace / "no-walk-document"
    walk_in(root, OPEN_MINUTES, document=None)
    console = io.StringIO()
    with contextlib.redirect_stdout(console):
        lines = lines_for(root)
    walk_directory = root / "docs" / "walk"
    check("a walk-document that cannot be read: one line naming the walk directory and the error",
          len(lines) == 1
          and lines[0].startswith(f"The handoff-supervisor could not read the waiting item of the open "
                                  f"approval-walk in {walk_directory}: FileNotFoundError: ")
          and lines[0].endswith(". Find it in the walk-minutes as /walk-me-through says, and tell the user "
                                "this error."),
          repr(lines))
    check("a walk-document that cannot be read: the supervisor's console says so",
          "handoff-supervisor: waiting approval-walk item check failed: FileNotFoundError: " in console.getvalue(),
          console.getvalue())

    root = workspace / "unusable-value"
    walk_in(root, "#next_to_present item 9 of 3\n")
    with contextlib.redirect_stdout(io.StringIO()):
        lines = lines_for(root)
    check("a waiting item the walk-document has no heading for: the line naming the error",
          len(lines) == 1 and ": UnusableRange: " in lines[0], repr(lines))


def run_prompt_placement_cases(workspace):
    line = approved_line(WALK, f"2 of 3, {POINT},", LINK, "2 of 3")
    fields = {"written-at": "2026-11-10T10:00:00Z", "next-step": "finish the review"}
    report = "launch-time-git-sync: fixture-branch is up to date with main"
    without = supervisor.DialogIgnitionPlan(Path("/tmp/dialog-0002.md"), fields).compose(report)
    with_line = supervisor.DialogIgnitionPlan(Path("/tmp/dialog-0002.md"), fields).compose(
        report, waiting_approval_walk_item=(line,))
    instruction = supervisor.ITEMS_NEEDING_THE_USER_IN_ONE_APPROVAL_WALK_INSTRUCTION
    check("dialog plan: the line follows the approval-walk instruction, and nothing else changes",
          with_line == without.replace(instruction, instruction + " " + line, 1) and with_line != without,
          repr(with_line))
    without = supervisor.IgnitionPlanWithoutConversationTail("finish the review").compose(report)
    with_line = supervisor.IgnitionPlanWithoutConversationTail("finish the review").compose(
        report, waiting_approval_walk_item=(line,))
    check("plan without a conversation-tail: the line follows the approval-walk instruction, and nothing else "
          "changes",
          with_line == without.replace(instruction, instruction + " " + line, 1) and with_line != without,
          repr(with_line))

    # Through the launch site: a supervisor starting a fresh agent-session from an unconsumed handoff, in a
    # working directory holding an open walk, hands the successor the line.
    root = workspace / "launch"
    walk_in(root, OPEN_MINUTES)
    handoff_directory = root / "handoffs"
    handoff_directory.mkdir(parents=True)
    settings = supervisor.SupervisorSettings(
        agent="fixture-seat", working_directory=root, handoff_directory=handoff_directory,
        agent_command="unused-stub-agent", first_prompt="")
    settings.handoff_path.write_text(
        "written-at: 2026-11-10T00:00:00Z\nnext-step: resume the audit\nsession-handoff-sequence-number: 5\n",
        encoding="utf-8")
    supervisor.write_supervisor_state(settings.state_path, {"consumed_counter": 4, "generation": 4})
    launched_prompts = []

    def launch_recording(agent_command, session_id, working_directory, prompt, **_):
        launched_prompts.append(prompt)
        return fixture.StubLaunchedSession(0)

    console = io.StringIO()
    with fixture.supervisor_names_replaced(
            launch_agent_session=launch_recording,
            launch_time_git_sync=lambda working_directory: report,
            choose_branch_state_instruction_from_working_directory_push_state=lambda working_directory: "",
            overview_refresh_due_lines=lambda working_directory: (),
            memory_review_due_lines=lambda: (),
            stdin_isatty=False), contextlib.redirect_stdout(console):
        supervisor.supervise_sessions(settings)
    check("launch site: the successor's first prompt carries the line right after the approval-walk instruction",
          len(launched_prompts) == 1 and f"{instruction} {line} " in launched_prompts[0],
          f"{launched_prompts!r}\n{console.getvalue()[-900:]}")


with fixture.handoff_supervisor_suite_workspace() as workspace:
    run_walk_minutes_cases(workspace / "walk-minutes")
    run_prompt_placement_cases(workspace / "placement")

fixture.print_summary_and_exit_nonzero_if_any_case_failed()
