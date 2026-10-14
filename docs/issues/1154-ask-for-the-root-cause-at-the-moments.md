---
issue: "[Ask for the root cause at the moments a defect is fixed: fix pull requests, review fix-rounds, and code fixed a third time](https://github.com/nedschorus/nedschorus/issues/1154)"
---

# Ask for the root cause at the moments a defect is fixed: fix pull requests, review fix-rounds, and code fixed a third time

## Problem

When an agent fixes a defect it usually fixes the case in front of it, and the same kind of defect returns elsewhere. CLAUDE.md now says to look for the root cause, but a standing instruction among many is easily lost in the middle of a fix, and no phrase reliably marks the moment: agents seldom write "root cause", and a defect can be fixed without the word "bug". The question has to arrive from outside the agent's memory, at the moment of the fix: from a program, or from the review every pull request already gets.

## The design

Three moments, each asking one question at the place the work happens.

1. **A pull request that fixes a defect.** Whether a pull request fixes a defect is a judgement: a test that fails on main and passes on the pull request's head commit marks a feature as often as a fix. So the judgement goes to the agent that already reads every pull request: the pull request reviewer instructions, `docs/agents/pr-reviewer-instructions.md`, ask whether the pull request fixes a defect, and if so whether its description carries, for each defect it fixes, a line, either `Root cause: <the reason the defect could happen at all, and what removes it>` or `Root cause not fixed: <why, and what the root cause is or that it was not found>`. A fix whose description lacks the line gets a finding that blocks the merge until the author adds it. The section "A pull request that fixes a defect" in `docs/agents/pr-reviewer-instructions.md` carries this; CLAUDE.md has no copy of the section, and CLAUDE.md's root-cause sentence tells authors where the line goes. Adding the line to the description settles the blocking finding without a new commit. Whether the reason given is the real root cause is the reviewer's to judge, not the program's.
2. **A review that carries findings.** The review that merge-lane-2 posts on a pull request with findings ends with one sentence asking the author, for each finding the author fixes, whether the finding is one case of a wider pattern, and to name the pattern in the fix commit's message. The author's forked subagent reads that review when it starts the fix-round, so the question arrives with the findings. A finding answered as not holding needs no such line.
3. **Code fixed a third time.** A fix pull request is a merged pull request whose description carries a `Root cause:` or `Root cause not fixed:` line. When a pull request changes lines that two earlier fix pull requests also changed, `scripts/merge-gate.sh` prints a note, without refusing the merge, naming those two pull requests and asking the author to add one of item 1's two lines to the pull request's description. Two earlier fixes to the same lines suggest each treated a symptom. Item 3 follows the changed lines back with `git log -L`.

   Part 3 waits until two things are true: at least 10 merged pull requests carry a `Root cause:` or `Root cause not fixed:` line, and the user has ruled on the report of the research into kinds of root cause (it lands in `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/cold-read-improvement/root-cause-kinds-research-2026-10-10/`). Part 3 does not fit in one function of `scripts/merge-gate.sh`: finding the earlier pull requests that changed the same lines takes one GitHub read per earlier commit, and its test needs a git repository with real line history. When both are true, check this design first: merge-lane-2 copies the `Root cause:` or `Root cause not fixed:` line into the merge commit's message as it merges, so the note can find earlier fixes in git history without reading GitHub.

   Part 3 finds code fixed repeatedly; it does not find process root causes, where a weak instruction let a defect through. design-to-main has the nearest mechanism: when a later step fails on an input that passed an earlier writer's input check, the failure shows which check that writer's checklist lacks, and whoever builds design-to-main adds it; the running machine does not (`docs/design-to-main/design-to-main-state-machine-design.md` § 4). design-to-main's build is paused, and design-to-main covers only work that goes through it.

## Not in scope

A root-cause analysis document, a template beyond the one line, or a separate reviewer. The line is the whole record; the commit message and the pull request carry any detail.

## Next action

Items 1 and 2 are done. Item 1 is the section "A pull request that fixes a defect" in `docs/agents/pr-reviewer-instructions.md`, added by pull request [PR reviewer instructions: a pull request that fixes a defect carries a Root cause line](https://github.com/nedschorus/nedschorus/pull/1166); merge-lane-2's review asks item 2's question. Item 3 waits on the two conditions in item 3 above. The agent-seat cold-read-improvement checks them weekly and, when both hold, builds item 3 with merge-lane-2, which owns `scripts/merge-gate.sh`.
