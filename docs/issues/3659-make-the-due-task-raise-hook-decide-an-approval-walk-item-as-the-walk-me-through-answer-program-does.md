---
issue: "[Make the due-task raise hook decide an approval-walk item as the walk-me-through answer program does](https://github.com/nedschorus/nedschorus/issues/3659)"
---

# Make the due-task raise hook decide an approval-walk item as the walk-me-through answer program does

## Reproduction

`scripts/agent-seat-due-task-raise-hook.py` raises a task whose prerequisite is an approval-walk item once that item is decided. Its check, `approval_walk_item_decided_or_problem`, at lines 415-419 on main at commit 12e91e8df, keeps its own rule for "decided":

```python
    def decided_through_itself_or_sub_steps(number):
        sub_steps = [other for unit in units for other in unit[0] if other.startswith(number + ".")]
        return number in decided or (bool(sub_steps) and all(step in decided for step in sub_steps))

    return {"met": all(decided_through_itself_or_sub_steps(number) for number in numbers)}
```

The walk-me-through answer program, `nc-systems/skills/walk-me-through/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py`, decides with `decided_with_items_whose_sub_steps_are_all_decided(items, decided, unresolved)`, given the set `held_answers_unresolved(...)` returns; `next_item` (line 2846) and `new_item_for_held_answer_numbered` (line 2709) both call it that way. The two rules disagree in two cases. reboot-test reproduced both on origin/main at commit 12e91e8df with the script below, saved to a file named `repro_due_task_hook_decided.py` and run as `python3 repro_due_task_hook_decided.py <checkout>`; the script is not in the repository, so save it from the block below to run it again:

```python
"""Reproduce Codex's two cases: the due-task hook's approval_walk_item_decided predicate
against the answer program's view (held_answers_unresolved / decided_with_... / next_item).
Usage: python3 repro_due_task_hook_decided.py <checkout>"""
import importlib.util, sys, tempfile
from pathlib import Path

top = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("hook", top / "scripts/agent-seat-due-task-raise-hook.py")
hook = importlib.util.module_from_spec(spec); spec.loader.exec_module(hook)
finder, answer = hook.walk_finder_and_answer_program()

def run(name, document, minutes_lines, heading, item):
    d = Path(tempfile.mkdtemp())
    doc = d / "w-2026-11-14.md"; doc.write_text(document)
    minutes = d / "w-2026-11-14-minutes.md"
    text = "# Minutes: w-2026-11-14\n\n" + "".join(l + "\n" for l in minutes_lines)
    minutes.write_text(text)
    hook_view = hook.approval_walk_item_decided_or_problem(
        {hook.WALK_MINUTES_FIELD: str(minutes), hook.ITEM_HEADING_FIELD: heading})
    parser = finder.markdown_parser()
    units = finder.item_unit_spans(document, parser)
    order = [n for u in units for n in u[0]]
    decided, deferrals = answer.minutes_record(finder, text, parser)
    unresolved = answer.held_answers_unresolved(finder, text, parser)
    full = answer.decided_with_items_whose_sub_steps_are_all_decided(order, decided, unresolved)
    nxt = answer.next_item(order, None, [], [], decided, deferrals, unresolved=unresolved)
    print(f"== {name}")
    print("walk-document:\n" + document)
    print("walk-minutes:\n" + text)
    print(f"hook predicate for item {item}: {hook_view}")
    print(f"answer program: recorded decided={sorted(decided)} held_answers_unresolved={sorted(unresolved)}")
    print(f"answer program: decided with sub-step inference={sorted(full)}; item {item} decided: {item in full}")
    print(f"answer program: next_item={nxt}")
    agree = hook_view.get("met") == (item in full)
    print("RESULT:", "agree (does not reproduce)" if agree else "DISAGREE (reproduces)")
    print()

A = "approved; every text the change adds has had a fast read. <accepted>"
run("Case 1: answer held, all sub-steps decided",
    "# Walk\n\n## Item 1 of 3: First\n\n## Item 2 of 3: Parent\n\n## Item 2.1 of 3: Sub one\n\n"
    "## Item 2.2 of 3: Sub two\n\n## Item 3 of 3: Last\n",
    [f"item 1 of 3: {A}",
     "item 2 of 3: answer held: item 2.1 of 3, raised by a fast-read finding, waits for the user's answer. <open>",
     f"item 2.1 of 3: {A}", f"item 2.2 of 3: {A}"],
    "Parent", "2")
run("Case 2: three-level item, intermediate sub-step decided only by inference",
    "# Walk\n\n## Item 1 of 2: Parent\n\n## Item 1.1 of 2: Sub one\n\n## Item 1.2 of 2: Sub two\n\n"
    "## Item 1.2.1 of 2: Sub two A\n\n## Item 1.2.2 of 2: Sub two B\n\n## Item 2 of 2: Last\n",
    [f"item 1.1 of 2: {A}", f"item 1.2.1 of 2: {A}", f"item 1.2.2 of 2: {A}"],
    "Parent", "1")
```

Its output, with the walk-documents and walk-minutes it wrote left out, since they are in the script:

```
== Case 1: answer held, all sub-steps decided
hook predicate for item 2: {'met': True}
answer program: recorded decided=['1', '2.1', '2.2'] held_answers_unresolved=['2']
answer program: decided with sub-step inference=['1', '2.1', '2.2']; item 2 decided: False
answer program: next_item=['2']
RESULT: DISAGREE (reproduces)

== Case 2: three-level item, intermediate sub-step decided only by inference
hook predicate for item 1: {'met': False}
answer program: recorded decided=['1.1', '1.2.1', '1.2.2'] held_answers_unresolved=[]
answer program: decided with sub-step inference=['1', '1.1', '1.2', '1.2.1', '1.2.2']; item 1 decided: True
answer program: next_item=['2']
RESULT: DISAGREE (reproduces)
```

- Case 1, raised too early: the walk-minutes accept items 1, 2.1 and 2.2 and hold an answer on item 2. The hook says item 2's prerequisite is met, so the task is raised and the agent is told to act; the answer program still has the held answer on item 2 unresolved, does not count item 2 decided, and presents item 2 next.
- Case 2, never raised: the walk-minutes decide items 1.1, 1.2.1 and 1.2.2. The answer program infers that 1.2, and so 1, are decided. The hook needs 1.2 recorded in the walk-minutes itself, so it says item 1's prerequisite is not met, and the task waits for good.

Codex found both cases in its review of pull request [#3074](https://github.com/nedschorus/nedschorus/pull/3074), which does not change the hook: the review compared the pull request's head with base commit bace1711, which is older than commit 17af03c7f, so the review's diff took in the hook from main. Its report is `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers/cx/pr3074-bace1711/codex-code-review-report.md`. The check came in with commit 17af03c7f, "Due-task hook: raise a task when the approval-walk item it waits on is decided, and name prerequisites it cannot use", by reboot-test.

## Why it matters

A task raised before its walk item is decided tells an agent to act on a decision the user has not made; a task never raised leaves work waiting after the user has decided, with nothing to show it.

## Root cause

The hook keeps a decision rule of its own instead of calling the answer program's. Any later change to how the answer program decides an item would open a new disagreement.

## What to do

reboot-test, which owns the hook, changes `approval_walk_item_decided_or_problem` so that it decides with the answer program's rule and keeps no rule of its own, and removes `decided_through_itself_or_sub_steps`. The hook's prerequisite is met when every number of the matching item is in the set `decided_with_items_whose_sub_steps_are_all_decided(order, decided, unresolved)` returns, where `order` is every item number in the walk-document in order (`[number for unit in units for number in unit[0]]`), `decided` is the first value `minutes_record` returns for the walk-minutes, and `unresolved` is what `held_answers_unresolved` returns for them. Better still, so that the hook cannot drift from how the answer program builds those three inputs either, the answer program exports one function that reads a walk-document and its walk-minutes and returns the decided set, and the hook and the answer program's own callers both call it. The pull request adds a test for each case above to `scripts/agent-seat-due-task-raise-hook-test.py`, and its description cites this issue in its `#root_cause` line. The design the hook was built from is GHI [Tasks raise themselves when their due time passes or their prerequisite is met](https://github.com/nedschorus/nedschorus/issues/940).
