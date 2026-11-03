---
issue: "[A session-handoff's next step carries forward a step that a later ruling or skill change removed](https://github.com/nedschorus/nedschorus/issues/2412)"
---

# A session-handoff's next step carries forward a step that a later ruling or skill change removed

Filed by agent-instructions-editor on 2026-11-02, from a report by cold-read-research, a Mac agent-seat.

## What happens

A retiring agent-session writes its session-handoff's next step by hand, as step 2 of `.claude/skills/handoff/SKILL.md` says, and `nc-systems/handoff/handoff-write-and-check-supervisor.py` writes that text into the handoff file unchecked. The retiring agent-session's own first prompt held its predecessor's next step, so it tends to copy that step's lines forward. Nothing checks a carried-forward line against what changed since it was first written: a commit to the skill it describes, or a ruling of the user's. The successor's prompt, which `nc-systems/handoff/handoff-supervisor.py` composes, tells it to "be wary of obsolescence and drift in everything in this handoff in proportion to that gap", but that gap is the handoff file's age, often seconds, not the age of the line.

## The case

cold-read-research's next steps, read from the user-message records of its agent-session transcripts mirrored on ned-box under `nedlern@ned-box:/home/nedlern/nedschorus-logs/agent-session-files-by-machine/mac/projects/-Users-el-agents-cold-read-research/`:

- From 2026-10-28T06:35Z (`87e00ba1-357a-4f2b-ac40-d652a90d0185.jsonl`), each next step said to close the approval-walk "then delete the item pages", which `.claude/skills/walk-me-through/SKILL.md` asked for then.
- Commit `25e8fc4fd` ("walk-me-through skill: keep item pages after the approval-walk closes", 2026-10-31T05:26Z) removed that step from the skill on main.
- The next steps of 2026-10-31T13:58Z (`09e94124-3417-4283-b62d-ba423aa69997.jsonl`, "delete the item pages") and 2026-11-01T18:21Z (`adebe3e4-b679-40ef-b598-a1d887794e99.jsonl`, "4. Delete the item pages this account owns.") still carried it.
- The successor carried it out. Each Artifact tool delete waits for the user to confirm it; cold-read-research reported that its 11 deletes held one turn for about 2.5 hours, until the user ruled on 2026-11-02: "Do not delete any artifacts or item pages; skip that step." (`7c539a67-7d69-49bd-be3f-e49ec00f2a4a.jsonl`, whose next step quotes the ruling).

## Why it matters

A next step is the successor's first instruction, and the successor trusts it over the skill it describes. A carried-forward step that a later change removed is carried out as if current: here it stopped an agent-seat's work for 2.5 hours and asked the user to confirm 11 actions he had already ruled out by changing the skill. The step can be carried through any number of session-handoffs, because each one copies the last.

## Related issues

ghi-guide-agent, asked on 2026-11-02, found no issue with this subject. The handoff issues it listed ([754](https://github.com/nedschorus/nedschorus/issues/754), [1125](https://github.com/nedschorus/nedschorus/issues/1125), [1129](https://github.com/nedschorus/nedschorus/issues/1129) and [2036](https://github.com/nedschorus/nedschorus/issues/2036), all open) cover recovery and restart, not stale next-step content. Nearest in shape:
- [Trigger-first instruction delivery](https://github.com/nedschorus/nedschorus/issues/30) and [Save each lesson where agents meet it at the moment it applies](https://github.com/nedschorus/nedschorus/issues/1349): a ruling that does not reach the place it applies.
- [Nothing checks that a design document still describes the code a pull request changes](https://github.com/nedschorus/nedschorus/issues/2078): the same drift between a written step and the current source, for another pair of files.

## Next action

Choose how a next step stops carrying a removed step, and put the choice to the user. Three candidates, which can be combined:
- Code drafts the mechanical part of the next step: the open approval-walks with the item each one's last `#next_to_present` line names, and the ready tasks. The retiring agent then writes only what the user is waiting on, so fewer lines are there to copy forward.
- Code tracks each line's age: `handoff-write-and-check-supervisor.py` keeps, beside the handoff, the time each next-step line first appeared, carried across handoffs, and the successor's prompt lists beside each line older than the last handoff the commits on `origin/main` since then, such as `git log --since=<that time> origin/main -- <the files the line names, or .claude/ nc-systems/ CLAUDE.md>`. In the case, that list would have shown `25e8fc4fd` beside "delete the item pages". Matching a line to its earlier copy must survive renumbering and small rewordings, for example by comparing the text without its list number with `difflib.SequenceMatcher`, because the case's own line changed from "delete the item pages" to "4. Delete the item pages this account owns."; the three next steps of the case make its test. Rulings since that time could be listed the same way, from the walk-minutes under `/home/nedlern/agents/*/docs/walk/` and `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/`. Only judging whether a listed commit or ruling makes the line obsolete is left to the successor.
- Instruction: step 2 of the handoff skill says to write the next step from the current task list and walk-minutes, not by copying the previous next step. This relies on the retiring agent following English, which `CLAUDE.md` asks to avoid for a step that needs no judgment.

A line carried forward is not always stale, such as "continue the approval-walk at item 6", so no candidate may drop or refuse a line only because it was repeated.
