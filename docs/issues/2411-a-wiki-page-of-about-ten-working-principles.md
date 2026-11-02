---
issue: "[A wiki page of about ten working principles for how agents work with the user](https://github.com/nedschorus/nedschorus/issues/2411)"
---

# A wiki page of about ten working principles for how agents work with the user

## Why

The user wrote, on 2026-10-28 in cold-read-improvement's agent-session on ned-box: "we don't have a good high concept document for this project, and we probably need one that collects maybe 10 of these sort of high level approaches. And that's maybe something that should be a GHI or a task". He approved filing this GHI on 2026-11-01, as item 7 of approval-walk cold-read-improvement-handoff-intake-decisions-2026-10-31. Its walk-minutes are `/home/nedlern/agents/cold-read-improvement/docs/walk/cold-read-improvement-handoff-intake-decisions-2026-10-31-minutes.md` on ned-box.

The section "Standing decisions" in `docs/nedschorus-wiki/nedschorus-ai-native-software-development-objective.md` lists 26 decisions, most of them about what the system is built from. No page states how agents work with the user. So an agent meets each of these principles only in a single ruling that arrived too late, or not at all.

## The principles he has already named

1. Agents do what they are trusted to do without telling him, and spend his attention only on what they need to ask him about.
2. Agents overweight cost, such as more code or a rename that cascades through many files. He counts that cost as a win when the result works better.
3. Agents judge prose poorly.
4. An agent may state a weak case against its own recommendation honestly, and need not inflate it. He accepts that about 5% of the decisions he makes on such recommendations will turn out wrong.
5. A case against that says only "this takes work" is not a real case. He said this on 2026-11-01, answering item 6.2 of the same approval-walk, an item the walk-minutes above record: "case against is merely this takes work."

## What the page is, and how it avoids drifting

- It is a new wiki page under `docs/nedschorus-wiki/`, named by `docs/nedschorus-wiki/nedschorus-how-to-choose-a-name-for-files-code-and-glossary-terms.md`, with about ten principles. Each principle is one or two sentences, followed by the user-ruling it comes from.
- A principle is a rule for how agents work with the user across tasks. A ruling on one task's content is not a principle.
- The objective page links to it from the section "Standing decisions", and the new page links back to that section.
- No principle is stated on both pages. Where a principle overlaps a Standing decision, the Standing decision stays where it is, and the new page links to it in place of restating it.

The case against is that a second page of principles can drift away from the Standing decisions. The alternative is to add the principles to the Standing decisions. The user chose a separate page: the Standing decisions say what the system is built from, and this page says how agents work with him.

## Next action

1. Gather the user's earlier rulings that state a working principle with the /find-info skill. It runs `scripts/log-store-past-discussions-regex-search-newest-first.py` over the walk files and his typed messages.
2. Draft the page in `docs/nedschorus-wiki/queue/` from the five principles above and those rulings, following `docs/nedschorus-wiki/nedschorus-style-guide.md`. When more than about ten principles qualify, keep the ones his rulings repeat most. GHI [wiki-write skill, and the detect-set-aside-ask hook that enforces it — checking the file, not the tool call](https://github.com/nedschorus/nedschorus/issues/343) plans a skill for writing wiki pages. While that skill is not built, draft by hand.
3. Give the draft its /cold-read.
4. Put the draft to the user in an approval-walk, one principle per item. A principle he disapproves is dropped. A principle he revises is redrafted and goes back to him as a new item.
5. In one pull request, move the approved page out of the queue to its name under `docs/nedschorus-wiki/`, and add the objective page's link.

Related, not duplicates: GHI [Save each lesson where agents meet it at the moment it applies, and decide whether a store that recalls lessons by subject is worth building](https://github.com/nedschorus/nedschorus/issues/1349) is about where single lessons live, not about one collected page.
