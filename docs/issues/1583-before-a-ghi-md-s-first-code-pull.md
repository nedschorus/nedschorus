---
issue: "[Before a GHI-MD's first code pull request, the agent sorts every line of its deferred-decisions with the user, using fixed hashtag markers](https://github.com/nedschorus/nedschorus/issues/1583)"
---

# Before a GHI-MD's first code pull request, the agent sorts every line of its deferred-decisions with the user, using fixed hashtag markers

## Why

Until design-to-main is deployed, work reaches main as a GHI-MD followed by pull requests. A GHI-MD's "Deferred-decisions" section lists what the work does not decide; today nothing asks anyone to look at that list again before the code is written, so a line deferred by mistake, or a decision nobody noticed was missing, surfaces only when a reviewer or the user meets it in the code. The user ruled that design-to-main sorts every deferred line at the start of each coding run, with the user reviewing the sort, and approved the markers below (approval-walk design-to-main-deferred-decisions-proposal-two-buckets-2026-10-15, items 1 to 9, minutes `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/design-to-main-deferred-decisions-proposal-two-buckets-2026-10-15-minutes.md`). This GHI brings the same sort to the interim system, so the GHI-MDs written now already carry the markers design-to-main will read.

## What changes

Before an agent opens the first pull request that carries code for a GHI-MD, it sorts the GHI-MD's deferred-decisions with the user in an approval-walk:

- Every line under the heading "Deferred-decisions" goes into one of two buckets. Settle now: the agent recommends a decision, the user rules, and the decision moves into the GHI-MD's body. Not in this run: the line begins `#not_in_this_run` and gives its reason after `#reason`.
- The agent also lists decisions the GHI-MD is missing, from the answers to "What it does not cover" in a cold-read-fast-read of the GHI-MD (`python3 nc-systems/cold-read/cold-read-fast-read.py --target <GHI-MD>`), and sorts each the same way. A GHI-MD with no deferred lines and no missing decisions needs no walk.
- Besides the two buckets, a line the user turns down for good begins `#rejected` and gives its reason after `#reason`; it stays in the section and counts as sorted, and no agent proposes it again unless the user asks.
- A deferred line may end with `#revisit_before`, naming an event after which the decision becomes expensive to change, or `#revisit_after`, naming an event the work waits on, or both. The event is named, by preference, as a GHI by its title and link; a deferred line in another design, quoted with that design's path; a task, by its agent-seat, number and subject, which `scripts/seat-task-list-read-nbd.py` finds on either machine; or one plain sentence. No dates. A line whose event nobody can name carries neither.
- A line that another step, agent-seat or document decides goes under a separate heading, "Decided elsewhere", naming its owner; the sort does not apply to it.
- A line that was already decided before the walk moves into the GHI-MD's body.

Example lines: "#not_in_this_run a version field in the results file. #reason one reader today. #revisit_before a second program reads this file." and "#rejected a web dashboard for runs. #reason the user reads status in the terminal."

## Deferred-decisions

- #not_in_this_run a program that checks a GHI-MD's deferred-decisions section for unmarked lines. #reason the rule is new, and the walk shows whether agents follow it. #revisit_after five GHI-MDs have been sorted this way.
- #not_in_this_run sorting GHI-MDs whose code has already started. #reason the sort is for the start of coding.
- #not_in_this_run what happens to a line the user leaves unruled in the walk. #reason the first walks show how often it happens.

## Next action

Find where the rule belongs, among the places an agent reads or meets before it starts a GHI-MD's first code pull request (`CLAUDE.md`, the building agent-seat's brief, or a hook that notices a code pull request citing a GHI-MD with unmarked lines), write it there, and bring the exact text to the user before editing, because these are guarded files that change what agents are told. Then give the text a /cold-read and open the pull request.

## Prior work

- GHI [Build the design-to-main state machine: the Python machine, its per-state agent-instructions, and the nine items the design defers to the build](https://github.com/nedschorus/nedschorus/issues/282): design-to-main's version of the same sort lands there, by the proposal `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/prime-intellect/design-to-main-deferred-decisions-proposal-2026-10-15.md`.
- GHI [Review the whole project for fixed markers that would be clearer as hashtags](https://github.com/nedschorus/nedschorus/issues/1518): the project-wide hashtag review; its rulings may rename these markers, and this GHI follows them.
- The best-practice research behind the buckets and markers: `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/prime-intellect/deferred-decision-categories-best-practice-research-2026-10-15/`.
