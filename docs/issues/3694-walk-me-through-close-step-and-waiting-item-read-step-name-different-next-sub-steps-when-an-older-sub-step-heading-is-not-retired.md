---
issue: "[Walk-me-through close step and waiting-item read step name different next sub-steps when an older sub-step heading is not retired](https://github.com/nedschorus/nedschorus/issues/3694)"
---

# Walk-me-through close step and waiting-item read step name different next sub-steps when an older sub-step heading is not retired

## Reproduction

Run on main at [d0669489](https://github.com/nedschorus/nedschorus/tree/d0669489744104020aec67bee624b8987ae3cbea), in a scratch worktree, with the probe below. The probe loads the test file `nc-systems/skills/walk-me-through/tests/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close-test.py` for its `Case` class, which builds a walk in a scratch checkout and runs `nc-systems/skills/walk-me-through/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py` on it. Save the probe as `probe.py` beside a checkout of main, and run it from the checkout's top as `python3 ../probe.py nc-systems/skills/walk-me-through/tests/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close-test.py`.

Each walk-document holds item 1, then item 3 with sub-step 3.1, its sub-sub-steps 3.1.1 and 3.1.2, and sub-step 3.2, all headed `of 10`. Each also holds one older sub-step heading, headed `of 9`, that is not retired. A heading is retired when a later heading says `revised` right after its `of M`, or when it falls under a heading that opens with `Withdrawn`, as in `#### Withdrawn version 1 of item 4.1`; the module docstring of `nc-systems/skills/walk-me-through/walk-me-through-approval-walk-minutes-and-walk-document-item-finder-common.py` gives these rules. The four layouts differ only in the older heading's number and place.

The walk-minutes approve items 1 and 3.1.1, and the waiting item is 3.1.2. The probe runs `check` and then `close`, which approves 3.1.2 and writes the next `#next_to_present` line. It then appends `#next_to_present item 3 of 10` by hand, so that the waiting-item read step, `approval-walk-waiting-item-cold-read-fast-read`, must choose item 3's next sub-step itself, and runs that step. The read step steps into the first sub-step of item 3 that it does not count as decided.

```python
import importlib.util, sys, shutil
path = sys.argv[1]
spec = importlib.util.spec_from_file_location("t", path); t = importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
TAIL = ("## Item 3 of 10: the opening sentence\n\n### Item 3.1 of 10: the first half\n\n"
    "#### Item 3.1.1 of 10: its first part\n\nOne.\n\n#case_against weak: a.\n\nRecommendation: a.\n\n"
    "#### Item 3.1.2 of 10: its second part\n\nTwo.\n\n#case_against weak: b.\n\nRecommendation: b.\n\n"
    "### Item 3.2 of 10: the second half\n\nThree.\n\n#case_against weak: c.\n\nRecommendation: c.\n")
docs = {
 "older-3.1.3-below-item-1": "# A walk\n\n## Item 1 of 10: an older item\n\nOld.\n\n#### Item 3.1.3 of 9: an older part\n\nOlder.\n\n" + TAIL,
 "older-3.1.1-inside-item-3": "# A walk\n\n## Item 1 of 10: an older item\n\nOld.\n\n" + TAIL + "\n#### Item 3.1.1 of 9: an older version's part\n\nOlder.\n",
 "older-3.1.3-inside-item-3": "# A walk\n\n## Item 1 of 10: an older item\n\nOld.\n\n" + TAIL + "\n#### Item 3.1.3 of 9: an older part\n\nOlder.\n",
 "older-3.1.1-below-item-1": "# A walk\n\n## Item 1 of 10: an older item\n\nOld.\n\n#### Item 3.1.1 of 9: an older version's part\n\nOlder.\n\n" + TAIL,
}
try:
  for name, doc in docs.items():
    case = t.Case(next_to_present="item 3.1.2 of 10", document=doc)
    case.minutes.write_text("# Minutes\n\n" + t.approved_line("item 1 of 10") + t.approved_line("item 3.1.1 of 10") + "#next_to_present item 3.1.2 of 10\n")
    c = case.run("check"); closed = case.run("close")
    after_close = t.marker(case)
    case.minutes.write_text(case.minutes.read_text() + "#next_to_present item 3 of 10\n")
    read = case.run(t.WAITING_ITEM_READ_STEP_NAME)
    print(name, "| check rc", c.returncode, "| close rc", closed.returncode, "->", after_close, "| read rc", read.returncode, "->", t.marker(case))
finally:
  shutil.rmtree(t.SUITE_ROOT, ignore_errors=True)
```

Output on 2026-11-15:

```
older-3.1.3-below-item-1 | check rc 0 | close rc 0 -> #next_to_present item 3.2 of 2 | read rc 0 -> #next_to_present item 3.1 of 10
older-3.1.1-inside-item-3 | check rc 0 | close rc 0 -> #next_to_present item 3.2 of 2 | read rc 0 -> #next_to_present item 3.2 of 10
older-3.1.3-inside-item-3 | check rc 0 | close rc 0 -> #next_to_present item 3.2 of 2 | read rc 0 -> #next_to_present item 3.1 of 10
older-3.1.1-below-item-1 | check rc 0 | close rc 0 -> #next_to_present item 3.2 of 2 | read rc 0 -> #next_to_present item 3.2 of 10
```

When the older heading's number is 3.1.3, a number no current heading uses, `close` names sub-step 3.2 next, but the read step names 3.1 and reads it again, though the user has answered both of its sub-sub-steps. Where the older heading sits makes no difference. When the older heading reuses a current number, 3.1.1, both name 3.2.

### What the same walk does with nothing appended by hand

The hand-appended line is what makes the read step choose the sub-step. In the `older-3.1.3-inside-item-3` and `older-3.1.3-below-item-1` layouts, a second probe instead ran `check`, `close` and the read step in turn, approving each item the walk named. `close` named 3.2, the read step kept 3.2, and once 3.2 was approved `close` wrote `#next_to_present item 3.1.3 of 2`, naming the older heading as the next item to show the user. So in an untouched walk the user is shown the older, unretired part as if it were a live item. How a real walk comes to hand the read step `item 3` after 3.1's sub-sub-steps are answered, as the first probe does by hand, was not traced (unverified).

The mac-claude reviewer of [pull request 3674](https://github.com/nedschorus/nedschorus/pull/3674) found the disagreement first, in [its inline comment](https://github.com/nedschorus/nedschorus/pull/3674#discussion_r4577868960) on review 5910092527, with the `3.1.3` layout inside item 3. mac-claude is the GitHub account that the fresh Claude reviewer the merge agent-seat commissions for each pull request posts as.

## The problem

`approval_walk_minutes_read_returning_decided_item_numbers`, at line 2817 of `walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py`, builds the set of decided items from every number in every heading the walk finder's `item_unit_spans` returns, the older `3.1.3 of 9` included. `items_decided_through_sub_steps`, at line 2797, counts 3.1 decided only when each of its sub-steps is decided; the older 3.1.3 never is, so 3.1 stays undecided.

The two steps then use that undecided 3.1 differently. The following is read from the code and not traced (unverified). `close` runs `next_item` over the whole walk-document starting at the item just answered, 3.1.2, so it moves forward to 3.2 and does not come back to 3.1 on that pass. The read step's `approval_walk_item_first_numbered_sub_step_without_answer`, at line 2301, runs `next_item` over item 3's sub-steps from the start, so it finds 3.1 first. That function's docstring says it uses `next_item`'s rule "so the read step and the close step name the same sub-step", and in this case they do not.

The decided-set code was written by the agent-seat reboot-test in [pull request 3665](https://github.com/nedschorus/nedschorus/pull/3665): `git blame` on lines 2817 to 2827 gives commits 1c5824a715 and c524a637e6, both in that pull request.

[Pull request 3674](https://github.com/nedschorus/nedschorus/pull/3674), open and not yet on main on 2026-11-15, adds two tests to the test file that touch this case. One checks that an older `3.1.3 of 9` keeps 3.1 undecided. The other checks that, with an older `3.1.1 of 9` below item 1, close and the read step both name 3.2.

## Why it matters

The user answers each sub-step once, and the walk must then move on. With an unretired older sub-step heading in the walk-document, the walk instead shows him either sub-step 3.1 again, after he answered every part of it, or the older heading itself as a new item to answer. Which of the two he sees depends on whether `close` or the read step chooses the next sub-step. A walk-document holds older headings like this when an item was revised without a `revised` or `Withdrawn` heading retiring the old version.

## The count in close's line

`close` writes `of 2` where the headings say `of 10`. This is intended: close writes the count from `approval_walk_item_total_shown_and_waiting_counted_from_walk_document` in `nc-systems/skills/walk-me-through/walk-me-through-approval-walk-minutes-and-walk-document-item-finder-common.py`, whose docstring defines it as the number of distinct whole item numbers plus the unnumbered items in the walk-document, and here those are items 1 and 3. The probe's walk-documents claim 10 items but hold 2, so the `of 2` comes from the probe and is not part of this defect. The read step writes `of 10` because it keeps the count from the `#next_to_present` line it was given. The two new tests in pull request 3674 drop the count from close's line before comparing it, so no test checks it.

## Next action

The agent-seat reboot-test fixes the cause, so that `close` and the waiting-item read step name the same next sub-step, and neither names the older heading as a live item, when the walk-document holds an unretired older sub-step heading whose number no current heading uses. reboot-test chooses which sub-step that is and where the fix goes: in the decided set; in the order the two steps walk the sub-steps, for example by one function both steps call; or in `check`, refusing a walk-document that holds such a heading until it is retired. A fix that changes which items the decided set holds must also change the test that pull request 3674 adds for an older `3.1.3 of 9`, which checks that 3.1 stays undecided. The fix adds a test that runs `close` and the read step on each of the four layouts above and checks that both name the same sub-step.
