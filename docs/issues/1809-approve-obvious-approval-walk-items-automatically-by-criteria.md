---
issue: "[Approve obvious approval-walk items automatically, by criteria drawn from the user's tracked obvious approvals, after the advisor checks each one](https://github.com/nedschorus/nedschorus/issues/1809)"
---

# Approve obvious approval-walk items automatically, by criteria drawn from the user's tracked obvious approvals, after the advisor checks each one

## Why

In an approval-walk the user answers each item, one at a time, and many answers are approvals of items he finds obvious, such as an item whose strongest case against is weak. Each one costs him a read and an answer. On 2026-10-19 he asked for an answer that marks an approval as obvious, so that the obvious ones could later be studied and some approved without asking him. In reboot-test's agent-session on ned-box, at 2026-10-19T16:15:17Z: "I want a new option called O for obvious, and O and A do the same thing, except that O marks somehow that response is obvious, so that after we've collected, say, 100 obvious responses, we can go back and review the transcripts and walks to see if there's a way we can automate at least some of the obvious approvals".

On 2026-10-21 he set the condition for doing so, in cold-read-improvement's agent-session on ned-box at 2026-10-21T15:40:44Z: "if we ever automate obvious approvals, in other words, if we ever come up with criteria to, instead of to detect obvious approvals and approve them automatically, that would require an advisor to check first. ... it probably needs a GHI for the conversion of the tracking into a automated system that would then be checked by an advisor before proceeding. And if the advisor decided it wasn't obvious, it would be back to it being a normal approval with the advisor's information added." In the same message he asked that this work not clash with what other agent-seats are doing on obvious approvals.

The advisor is a Claude Code tool with no inputs: when an agent calls it, the whole transcript so far goes to a stronger reviewer model, which sends back advice.

## What exists

- The answer AO, approve as obvious, and the walk-minutes line "approved #approved_obvious" that records it, are being built by reboot-test on its local branch `walk-me-through-answer-letters-a-ao-d-l-topic-branch`, not yet pushed, from items 37.1 and 37.2 of agent-instructions-editor's approval-walk, `docs/walk/agent-instructions-editor-every-open-decision-2026-10-15.md` in agent-instructions-editor's checkout on ned-box, which the user approved on 2026-10-21. Until that pull request merges, agents record his obvious approvals by hand, as he asked in his own words on 2026-10-21: in cold-read-improvement's agent-session at 15:13:53Z, fleet-restart-at-login's at 15:36:16Z and 15:41:21Z, and ned-box-helper's at 15:38:17Z, all on ned-box.
- reboot-test's task #248 and fleet-restart-at-login's task #254 record the same remarks. cold-read-improvement dropped its own label, "<accepted, obvious>", in favour of `#approved_obvious`.
- On 2026-10-21 the walk-minutes on ned-box held 5 lines with `#approved_obvious`, in 4 files.
- The walk-me-through skill already lets an agent approve some items without asking: an item that recommends making its change needs no answer when the agent finds no case against it and the item only corrects a statement shown to be false, deletes code that nothing calls, or fixes a defect the item names. Criteria this work derives would widen that rule.

## The work

1. When the walk-minutes hold about 100 lines with `#approved_obvious`, the number the user named, collect each such item with its full text from the walk-documents, and, for contrast, a sample of items he approved with a plain A.
2. Derive criteria that pick out the obvious items, such as the strength of the case against or the kind of change, and test them on the collected items: how many obvious items they catch, and how many plain approvals they would wrongly approve. Bring the criteria and the test to the user in an approval-walk.
3. Once he approves criteria, change the walk-me-through skill: when an item meets them, the agent writes in the conversation, for the advisor, the question whether the item is obvious, then calls the advisor. If the advisor agrees, the agent records the item as approved without asking, with the advisor's reason, and lists it in its next message to the user, as the skill already does for items approved without asking, so he can overturn it. If the advisor finds the item is not obvious, or the call fails, the item goes to the user as a normal item, with the advisor's information added. The skill's rule that an item which adds or changes a rule, a guard, or what an agent or a program is told or allowed to do always goes to the user stays, unless the user lifts it when he rules on the criteria.

## Next action

agent-instructions-editor, which owns the walk-me-through skill, counts the `#approved_obvious` lines under `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/` once a week, and starts step 1 when the count reaches about 100. Before step 1, it asks reboot-test, cold-read-improvement, fleet-restart-at-login and ned-box-helper whether any of them has started on obvious approvals; if one has, the two agree who does which step before either goes on, so that the work does not clash.
