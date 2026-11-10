---
issue: "[Make approval-walks wrap up faster: read the next item ahead, reread after a fix only when the fix touches facts, and stop the /Volumes false alarm in cold reads](https://github.com/nedschorus/nedschorus/issues/2464)"
---

# Make approval-walks wrap up faster: read the next item ahead, reread after a fix only when the fix touches facts, and stop the /Volumes false alarm in cold reads

In an approval-walk, after the user answers one item, the agent runs checks before it shows the next item, chiefly a cold-read-fast-read (`nc-systems/cold-read/cold-read-fast-read.py`) of the next item and of each revision of it. The user waits through those checks. This GHI holds three changes, built as code, that cut the wait without dropping the first read of an item. Owner: the agent-seat cold-read-improvement, which owns the fast read.

## The measurement

On 2026-11-01 a subagent of merge-lane-2 measured 284 waits between the user's answer and the next item, across 9 agent-seats, 2026-10-18 to 2026-11-01. Its data and scripts are in `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-2/walk-wrap-up-check-measurement-2026-11-01/`; the hand classification of 33 reads is `classification.tsv` there, and the full cold read runs are `fullruns.txt`. The figures, as item 7.1.1 of the approval-walk merge-lane-2-open-rulings-2026-10-30 gave them to the user:

- The median wait is 3.4 minutes. With no fast read it is 0.7 minutes; with one it is 5.2 minutes, and the read itself takes a median of 196 seconds. Fast reads are at least 37% of all the waiting.
- The walk-me-through skill already asks for one fast read of the whole walk before item 1. Then it asks for a fast read of each item that is revised, and again after each fix that is more than an obvious-error-fix. Items are almost never read again unchanged: of 444 pairs of reads of the same item, only 4 were of identical text. The repeats are that read, fix, read loop, most within 5 minutes.
- A read's time is mostly a fixed start-up cost: about 2 minutes on Gemini, the main reader, plus about 20 seconds per 1,000 words. Sonnet takes about a third as long. One read of a whole 16-item walk takes about 4 minutes, against about 30 for 16 item reads, but it returns about 8 findings in all, against about 7 for each item read on its own, about 110 for the 16.
- First reads find real defects: 6 of 21 sampled reads before showing an item caught one, such as "a test already checks that they match" when no such test exists. The rereads in the sample found only wording.
- The full cold read at the end of a design or skill takes a median of 28 minutes. In 5 of 8 sampled runs it found real defects the fast reads had missed, such as two false statements about what the worktree cleaner does today.
- The /Volumes false alarm comes up in 313 of 320 reads whose text has a Mac link. The reader runs on ned-box and never sees the rule that `file:///Volumes/nedhome/` is ned-box's home seen from the Mac.

## Decided

The user approved item 7.1.1 of merge-lane-2's approval-walk merge-lane-2-open-rulings-2026-10-30 on 2026-11-02 at 09:56 Pacific time (17:56Z), in his words "A approved is with the Gemini fast read." Walk-document: `/home/nedlern/agents/merge-lane-2/docs/walk/merge-lane-2-open-rulings-2026-10-30.md` on ned-box, section "Item 7.1.1 of 25"; walk-minutes: `/home/nedlern/agents/merge-lane-2/docs/walk/merge-lane-2-open-rulings-2026-10-30-minutes.md`, the line "item 7.1.1 of 25: the user answered approved #case_against_weak (2026-11-02 09:56)". The item's recommendation was: "file the GHI for the three changes and hand it to cold-read-improvement."

The case against that the user saw, graded weak: change 2 lets a wording fix that adds a new mistake reach the user unread, and only 33 reads were classified by hand, 21 before showing an item and 12 in the check step. The alternative he did not take: change nothing until a larger sample is classified.

The approval keeps the Gemini fast read as the reader. The full cold read at the end of a design or skill stays as it is, apart from change 3.

## The three changes

1. **Read the next item ahead.** The walk check program, `nc-systems/skills/walk-me-through/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py`, gets a step that starts the fast read of item N+1 in the background as item N is shown, keyed to a hash of item N+1's text. When the user answers item N, the agent uses that read if item N+1's text is unchanged, and waits for it if it is still running; if item N+1's text changed meanwhile, the program reads it again.
2. **Reread after a fix only when the fix touches facts.** After a fast read's fixes, the walk check program compares the item before and after, and starts another read only when the change touches a number, a path, a file or program name, a link, or the item's line that begins "Recommendation:", "The alternative:" or a `#case_against` tag such as `#case_against_weak`. Today `.claude/skills/walk-me-through/SKILL.md` leaves that call to the agent: "give it another fast read if a fix was more than an obvious-error-fix". The pull request for this change also changes that sentence of the skill, and the new wording goes to the user for approval before it merges, as every standing instruction does.
3. **Stop the /Volumes false alarm.** `nc-systems/cold-read/cold-read-fast-read.py` rewrites `file:///Volumes/nedhome/` to `/home/nedlern/` in the copy of the text it hands the reader, and the full cold read, `nc-systems/cold-read/cold-read-grid.py`, does the same.

## Next action

cold-read-improvement designs and builds the three changes, each with a test that fails without it. Changes 1 and 2 may land in one pull request and change 3 in another, since change 3 runs the cold-read test suites and not the walk's.

The design settles these points, which the GHI-MD's own fast read raised:

- What starts the read ahead. The walk check program's `close` step, which already sets the walk-minutes' `#next_to_present` line, can start item N+1's read itself, so the saving does not depend on the agent remembering to start it.
- Which side compares the hash and waits. The program can do both and hand the agent findings only for item N+1's text as it stands, leaving the agent only to apply them.
- The last item of a walk, which has no item N+1, and item 1, which the read of the whole walk covers.
- A background read that fails or never ends: the agent must not show item N+1 unread because of it.
- Where the program keeps the item's text from before the fixes, to compare against.
- How code tells that a change touches a program name. One rule the fast read proposed: a changed word counts when it is in backquotes, ends in a file extension, or is a path or file name that `git ls-files` lists; any changed digit counts as a number.
- Whether change 3 also rewrites `/Volumes/nedhome/` written without `file://`, and whether a finding that quotes a rewritten path is shown with the path as the item has it. One function that both programs import keeps the two rewrites the same.

## Not in this GHI

The user's further ideas, given with his approval, are not decided and are not part of this work: a ready pool of warm readers, trying other reader models, and having readers name the instruction behind each finding. A separate research GHI, which links to this one, holds them.
