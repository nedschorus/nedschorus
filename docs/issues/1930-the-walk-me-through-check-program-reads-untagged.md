---
issue: "[The walk-me-through check program reads untagged walk-minutes lines as decisions by their keywords](https://github.com/nedschorus/nedschorus/issues/1930)"
---

# The walk-me-through check program reads untagged walk-minutes lines as decisions by their keywords

## What is wrong

The walk-me-through check program, `nc-systems/skills/walk-me-through/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py`, decides which items of an approval-walk the user has already answered by reading the walk-minutes. A minutes line that carries an outcome tag, such as `<accepted>`, is read by that tag. A line with no outcome tag counts as deciding every item it names whenever a deciding word appears anywhere in it: approved, disapproved, accepted or rejected (`minutes_record()`, lines 508 to 544 on main). The word deferred counts the same way as a deferral. The close step then names the first item the minutes do not record as the next item to present, so a note that only mentions such a word marks items the user has not answered as answered, and the walk skips them.

## What it has broken

On 2026-10-24 at 17:05 local time, in prime-intellect's approval-walk `prime-intellect-open-decisions-for-the-user-2026-10-22-2`, the user approved item 6.1 of 17, and `close` wrote `#next_to_present item 16 of 17`, the summary item, instead of item 7. At that close the walk-minutes held this untagged re-plan note, which prime-intellect has since reworded to avoid the word (line 71 now ends "the definition item 4 settled"): `Items 5 to 15: "loose end" respelled "loose-end" after item 4; item 5 cites the approved definition.` Its word "approved" made the program count items 7 to 15 as decided. The evidence is the `#next_to_present item 16 of 17` line and prime-intellect's correction below it in `/home/nedlern/agents/prime-intellect/docs/walk/prime-intellect-open-decisions-for-the-user-2026-10-22-2-minutes.md`.

PR [walk-me-through close: a deciding word right after a determiner, as in "the approved definition", records no decision](https://github.com/nedschorus/nedschorus/pull/1924) narrows the rule: a deciding word right after "the", "a" or "an" no longer counts. That ends the outage, but other forms still decide every item a note names. The PR's reviewers found these: "our approved definition", "the previously approved definition", "the user-approved definition", "item 4's approved definition", "the definition item 4 approved", and "Items 3 to 4 of 5: item 3 cites its approved definition."

A second weakness of the same kind: a note's item range, such as "Items 5 to 15", is applied to whatever those numbers mean after a later re-plan renumbers the walk, because minutes lines are read without the walk's total.

## Why it matters

The close step's `#next_to_present` line is now the one place an approval-walk resumes from after an interruption, by the walk-me-through skill. A wrong line sends the user past items he has not ruled on, with nothing that tells him so.

## What to decide

The root fix is to stop reading untagged lines by keyword. For example, only an outcome tag would decide a minutes line that names more than one item, or every minutes line. Older walks' minutes record decisions in untagged forms such as `ITEM 5 ACCEPTED` and `ruled: "y" (accepted)`, so the change also has to say what becomes of those lines: convert the walk-minutes of every approval-walk still open, and keep the old reading only for approval-walks already closed, or convert all of them. Changing which minutes lines decide an item changes the minutes-writing rules, so the choice goes to the user.

The renumbering weakness goes in the same choice: whether a walk-minutes line must name the approval-walk's total, as in "items 5 to 15 of 16", so the check program can ignore a line written before a re-plan.

## Next action

agent-instructions-editor puts the choice to the user as an approval-walk item: which minutes lines may decide an item, and what happens to existing minutes. It then builds the fix in the check program, with a test for the note quoted under "What it has broken" and for each of the six forms the reviewers found. Once untagged lines can no longer decide an item, the program's the/a/an exclusion has no job: remove it in the same pull request. A test then shows that "the approved definition" still records no decision.
