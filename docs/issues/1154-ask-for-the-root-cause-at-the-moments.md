---
issue: "[Ask for the root cause at the moments a defect is fixed: fix pull requests, review fix-rounds, and code fixed a third time](https://github.com/nedschorus/nedschorus/issues/1154)"
---

# Ask for the root cause at the moments a defect is fixed: fix pull requests, review fix-rounds, and code fixed a third time

## Problem

When an agent fixes a defect it usually fixes the case in front of it, and the same kind of defect returns elsewhere. CLAUDE.md now says to look for the root cause, but a standing instruction among many is easily lost in the middle of a fix, and no phrase reliably marks the moment: agents seldom write "root cause", and a defect can be fixed without the word "bug". The question has to arrive from outside the agent's memory, at the moment of the fix: from a program, or from the review every pull request already gets.

## The design

Three moments, each asking one question at the place the work happens.

1. **A pull request that fixes a defect.** Whether a pull request fixes a defect is a judgement: a test that fails on main and passes on the pull request's head commit marks a feature as often as a fix. So the judgement goes to the agent that already reads every pull request: the pull request reviewer instructions, `docs/agents/pr-reviewer-instructions.md`, ask whether the pull request fixes a defect, and if so whether its description carries one line, either `Root cause: <the reason the defect could happen at all, and what removes it>` or `Root cause not fixed: <why, and what the root cause is or that it was not found>`. A fix whose description lacks the line gets a finding that blocks the merge until the author adds it. The review scope gives prose no findings, so the same edit adds this one exception to it, in `docs/agents/pr-reviewer-instructions.md` and in the CLAUDE.md bullet that copies it. Whether the reason given is the real root cause is the reviewer's to judge, not the program's.
2. **A review that carries findings.** The review that merge-lane-2 posts on a pull request with findings ends with one sentence asking the author, for each finding the author fixes, whether the finding is one case of a wider pattern, and to name the pattern in the fix commit's message. The author's forked subagent reads that review when it starts the fix-round, so the question arrives with the findings. A finding answered as not holding needs no such line.
3. **Code fixed a third time.** A fix pull request is a merged pull request whose description carries a `Root cause:` or `Root cause not fixed:` line, so this item starts working once item 1 has run for a while. When a pull request changes lines that two earlier fix pull requests also changed, `scripts/merge-gate.sh` prints a note, without refusing the merge, naming those two pull requests and asking the author to add one of item 1's two lines to the pull request's description. Two earlier fixes to the same lines suggest each treated a symptom. Item 3 follows the changed lines back with `git log -L`; it is built only if it fits in one function of `scripts/merge-gate.sh` and its test.

## Not in scope

A root-cause analysis document, a template beyond the one line, or a separate reviewer. The line is the whole record; the commit message and the pull request carry any detail.

## Next action

merge-lane-2, which commissions the reviews, posts the review and owns `scripts/merge-gate.sh`, adds item 1 to `docs/agents/pr-reviewer-instructions.md` and item 2 to the review it posts, then builds item 3 once fix pull requests carry the line.
