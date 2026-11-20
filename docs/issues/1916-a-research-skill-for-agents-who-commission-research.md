---
issue: "[A research skill for agents who commission research whose numbers reach the user](https://github.com/nedschorus/nedschorus/issues/1916)"
---

# A research skill for agents who commission research whose numbers reach the user

This GHI proposes a project skill that an agent follows whenever it commissions research and the figures the research produces will reach the user. The research may be on the session dialogs at `nedlern@ned-box:/home/nedlern/nedschorus-logs/session-dialogs/`, on the repository, or on the web, and may be done by Codex or by Claude subagents. The skill would say how to write the task given to the researcher, how the researcher reports its figures, and how the commissioning agent carries those figures, with their limits, into an approval-walk item or a message to the user. Nothing is designed yet. The user asked for this GHI on 2026-10-24: "There probably should be a generic research skill. And if you want to file a GHI to do that, we'll get to it someday. You can put your notes into it."

## Why: figures from small samples were shown to the user as firm

On 2026-10-24, in the approval-walk `ned-box-helper-combined-open-items-2026-10-22`, items 6.1 to 6.3, the agent-seat ned-box-helper commissioned five Codex reports. Three were on absolute words, such as "always", "every" and "never", in agents' messages to the user; one was on words of the user's that confuse agents; one was on agents misquoting the user's decisions. Items 6.1 to 6.3 asked whether to build hooks that warn on such words or check such quotes. The reports are in the log-store directory that "Sources" below names, and the line numbers cited here are lines of those reports.

The first report, `codex-absolute-word-warn-categories-report-2026-10-24.md`, labelled a sample of 150 uses per word, each labelled once, by Codex alone. Codex found that a use states a rule an ordinary exception breaks, an overclaim, in 35 of 150 uses of "always" (23%) and 19 of 150 uses of "every" (13%) (table at line 31). The report qualified its figures. Of its proposed warning rule's precision it said, at line 5: "This is optimistic, same-annotator, in-sample judgment—not validated hook performance." Of the per-word shares it said, at line 89: "Forty observations cannot establish a reliable ranking; neither can 150 establish that never is riskier than every."

The agent dropped both caveats. It showed the user the shares as firm percentages, and revised item 6.1 three times on them, designing an absolute-word hook each time. A third absolute-word report, `codex-absolute-word-constructs-report-2026-10-24.md`, had Codex label 2,833 uses, 600 per word for "every", "always" and "never", with a separate held-out sample of 100 per word to test any rule found (lines 11 and 13). The overclaim shares came out lower: for "always", 12.8% in the discovery sample and 11.0% in the held-out sample; for the "every" family, which is every, everything, everyone, everybody and everywhere, 7.7% and 3.0% (tables at lines 123 and 131). No pattern reliably told overclaims from fine uses on the held-out sample. The held-out samples held only 3 to 11 overclaims per word, which the report itself calls too few for its recall estimates (line 139). That report also had a single labeller, Codex: it improved the sample size and added a held-out test, and nothing more.

The user called the data he had been shown "very deceptive", and asked how to avoid this in future. He also said the agent may not have given Codex a good task, and that a simple rule that catches a defect found in about 5% of uses, with few false positives and few false negatives, is still worth having.

## Sources

- The five reports are in `nedlern@ned-box:/home/nedlern/nedschorus-logs/analysis/absolute-word-warn-categories-2026-10-24/`: `codex-absolute-word-warn-categories-report-2026-10-24.md`, `codex-absolute-word-hook-messages-report-2026-10-24.md`, `codex-absolute-word-constructs-report-2026-10-24.md`, `codex-user-words-that-confuse-agents-report-2026-10-24.md` and `codex-misquoted-user-rulings-report-2026-10-24.md`. The directory also holds each Codex invocation's log.
- The approval-walk's walk-document and walk-minutes are in the agent-seat ned-box-helper's working tree, not in the repository: `nedlern@ned-box:/home/nedlern/agents/ned-box-helper/docs/walk/ned-box-helper-combined-open-items-2026-10-22.md` and `nedlern@ned-box:/home/nedlern/agents/ned-box-helper/docs/walk/ned-box-helper-combined-open-items-2026-10-22-minutes.md`. Lines 163 to 199 of the walk-minutes record each revision of items 6.1 to 6.3 and the user's words quoted above.

## Related work

- GHI [use-codex skill: one place that says how this project invokes Codex headlessly](https://github.com/nedschorus/nedschorus/issues/165) covers how Codex is invoked; the research skill would cover what research is asked for and how its figures are reported, and would point to the use-codex skill for the invocation.
- GHI [A project style guide: words to avoid, a mechanical checker, and a check on unbacked promises](https://github.com/nedschorus/nedschorus/issues/14) records measurement practice, such as sample counts, in its supporting documents, for its own measurements only.
- The `anthropic-skills:deep-research` skill, which Claude Code supplies and which is not in this repository, coordinates subagents that research the web and write a narrative report. The skill does not cover the session dialogs, labelling samples, agreement between labellers, held-out testing, or carrying a report's caveats into what the user is shown.
- Absence receipt: on 2026-10-24, ghi-info, asked with `--include-closed` whether any GHI covers a generic research skill with labeller agreement, held-out samples and the reporting of sample sizes and caveats, found none, open or closed. A search of origin/main's paths and file contents for `research[-_ ]?skill` found nothing.

## Proposals for the design

These are notes for whoever designs the skill. The user has not decided on any of them. Proposals 1 and 5 assume research that labels a sample; the design says what applies to other research, such as counts taken from git history.

1. Before any figure is used, the task given to the researcher asks for a second, independent labeller on the same sample, Claude and Codex each labelling it, with the rate at which they agree; and for a held-out sample on which any rule the research finds is tested.
2. Every share is reported with its sample size and a range, as "19 of 150 (13%, 95% Wilson interval 8% to 19%)", not as "13%". The report's own caveats travel with the figure into any approval-walk item or message. A program could check that a percentage in an approval-walk item carries its sample size.
3. When an approval-walk item rests on a sample, the one sentence stating the strongest case against the item's recommendation, which `.claude/skills/walk-me-through/SKILL.md` requires, names the weakness of the data.
4. The task given to the researcher states the decision the research serves and the threshold that would change it, such as "warn only if held-out precision is at least 80%", so the research answers the question that was asked.
5. The research looks for narrow rules of high precision, worth having even when they cover only a few percent of cases, and not only for blanket rules.

## Next action

Design the skill, as `.claude/skills/<name>/SKILL.md` or as a design added to this GHI-MD, using the proposals above as a starting point; then put the design to the user in an approval-walk. The user set no date.
