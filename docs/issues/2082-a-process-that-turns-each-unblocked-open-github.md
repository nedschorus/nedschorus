---
issue: "[A process that turns each unblocked open GitHub issue into a task](https://github.com/nedschorus/nedschorus/issues/2082)"
---

# A process that turns each unblocked open GitHub issue into a task

This GHI carries the `queue-drain-candidate` label: it waits for the user, who has not decided whether, when or how to build it. It records the problem and one rule.

The user approved filing it on 2026-10-28 at 06:23 UTC, answer "A" to item 5 of approval-walk ned-box-helper-open-items-2026-10-27; the walk-document is `nedlern@ned-box:/home/nedlern/agents/ned-box-helper/docs/walk/ned-box-helper-open-items-2026-10-27.md` (heading "Item 5 of 12") and its minutes `nedlern@ned-box:/home/nedlern/agents/ned-box-helper/docs/walk/ned-box-helper-open-items-2026-10-27-minutes.md`.

## The problem

Agents look for work on their task lists, not in GHIs, so an open GHI that no agent-seat holds as a task can wait unnoticed.

The user, 2026-10-21, in approval-walk ned-box-helper-all-open-items-2026-10-15, item 15 (minutes `nedlern@ned-box:/home/nedlern/agents/ned-box-helper/docs/walk/ned-box-helper-all-open-items-2026-10-15-minutes.md`): "it would be nice if some process picked up GitHub issues to become tasks, though maybe that's a completely separate problem and we should not deal with it for now."

The user, 2026-10-26, in approval-walk ned-box-helper-combined-open-items-2026-10-22-remaining-items (minutes `nedlern@ned-box:/home/nedlern/agents/ned-box-helper/docs/walk/ned-box-helper-combined-open-items-2026-10-22-remaining-items-minutes.md`), said that GHIs need prerequisites: "It's not a tree. It's just a graph." The minutes record his purpose: a program can then tell which GHIs are ready.

## The rule

The rule, word for word as the user approved it in item 5:

"An open issue is unblocked when every issue listed under its GitHub "Blocked by" relationship is closed, or when none is listed; a process turns each unblocked open issue into a task."

GitHub stores the relationship itself: a GHI can be marked "blocked by" other GHIs ([GitHub changelog, 2025-08-21](https://github.blog/changelog/2025-08-21-dependencies-on-issues/)). A program reads a GHI's blockers with `gh api repos/nedschorus/nedschorus/issues/<number>/dependencies/blocked_by` ([REST API: issue dependencies](https://docs.github.com/en/rest/issues/issue-dependencies)); GitHub allows at most 50 per relationship type on one GHI. This read has not been tried in this repository.

This GHI asks for no program that checks for a loop between GHIs, because no such loop has happened; the loop case is listed under Deferred-decisions.

## Related GHIs

ghi-info, asked on 2026-10-28 with closed GHIs included, found none that covers turning GHIs into tasks or deciding from "blocked by" which GHIs are unblocked. It named these as nearest:

- GHI [Tasks raise themselves when their due time passes or their prerequisite is met](https://github.com/nedschorus/nedschorus/issues/940) already builds an item that becomes active when its prerequisite is met, for tasks rather than GHIs.
- GHI [Check each new task against the open issues when it is filed, and add a match to that issue's GHI-MD](https://github.com/nedschorus/nedschorus/issues/1432) links the two in the opposite direction, from a new task to an existing GHI.

## Next action

The user decides, through the queue-drain (GHI [Queue drain procedure — the review process that empties the wiki queue, the pair queue, nc-queue, the drafts directory and the queue-drain-candidate-label issue queue](https://github.com/nedschorus/nedschorus/issues/24)), whether to build this, drop it, or leave it waiting. Until he decides, no agent builds it.

## Deferred-decisions

Each line below is a question this GHI leaves open, for the user to settle when he decides on it, or for its build.

- A loop, where two GHIs each block the other, so that neither is ever unblocked. GitHub's documentation does not say whether it refuses one.
- A blocker closed as "not planned": does it count as closed, and so unblock the GHIs it blocked?
- A blocker that is a pull request, or a GitHub issue in another repository: does the rule count it, and how?
- Which open GHIs the process takes: by the rule as written, an open GHI with no blockers becomes a task, which would include undecided ones such as those labelled `queue-drain-candidate`, this one among them.
- What starts the process: a schedule, an event on GitHub, or a command someone runs.
- Which agent-seat's task list receives each task, what the task holds, and what stops the process from making a second task for a GHI that already has one.
- What happens to a task when its GHI gains a new blocker or a closed blocker is reopened, and whether finishing the task closes the GHI or closing the GHI ends the task.
- A task made this way is unblocked, which is not yet ready in the project glossary's sense: it is ready only once nothing is left for the user to decide, and no unmerged pull request or other agent-seat's work blocks it.
