---
issue: "[Nothing checks that a design document still describes the code a pull request changes](https://github.com/nedschorus/nedschorus/issues/2078)"
---

# Nothing checks that a design document still describes the code a pull request changes

## What is wrong

When a pull request changes what a program does, a design document or an architecture-overview that describes the old behavior can stay as it was, and no program reports the false sentence. A pull request reviewer may notice it by reading, and nothing directs the reviewer to look.

## The evidence

- PR [Approval-walks continue across a handoff, with no 20% handoff after a walk closes, and items checked against the user's earlier rulings](https://github.com/nedschorus/nedschorus/pull/2063), merged on 2026-10-28 as commit 9d25344, removed from `scripts/handoff-context-threshold-hook.py` the lower threshold that asked for a session-handoff after an approval-walk closed, and removed from `scripts/walk-files-ship.py` the marker file that set it off.
- The same pull request edited `nc-systems/handoff/handoff-design.md` itself: it deleted the paragraph recording the user's approval of that threshold on 2026-10-24. Line 20 of the same file, the line describing the threshold hook, kept the words "or reaches a third, lower one after an approval-walk has closed", and still has them on main at c9a5e3b03.
- A fresh Claude pull request reviewer, which posts on GitHub as the account `mac-claude`, found the line by reading, in [review 5677913146](https://github.com/nedschorus/nedschorus/pull/2063#pullrequestreview-5677913146).
- merge-lane-2, the agent-seat that reviews and merges every pull request, carried the line in [review 5677953426](https://github.com/nedschorus/nedschorus/pull/2063#pullrequestreview-5677953426) as non-blocking finding 1, adding that "no program reads the line", and merged the pull request with the line unchanged.
- PR [Handoff design drops the walk-close threshold clause, and the walk shipper's test checks a close writes no walk-closed marker](https://github.com/nedschorus/nedschorus/pull/2073) drops the clause. On 2026-10-28 its description's `#root_cause` line says that nothing checks design prose against the code it describes, and that the pull request adds no such program.

## Why the existing tools say nothing

- `scripts/md-drift-lint.py` checks that the paths and links a Markdown file names exist, that dates are real, that a command names only flags its script accepts, and that a number in backticks on a line naming one code file appears in that file. Line 20 names a file that exists and carries no flag and no number in backticks. Run on `nc-systems/handoff/handoff-design.md` at c9a5e3b03, the lint reports two findings, both on line 249, and none on line 20. GHI [Test the agent-instructions files: a Vale trial for the style-guide word checker, and md-drift-lint findings on changed lines block the merge](https://github.com/nedschorus/nedschorus/issues/1990) and GHI [Sort the 60 standing md-drift-lint findings into forward references and stale citations, then fix the stale ones](https://github.com/nedschorus/nedschorus/issues/572) are about the same lint and its findings, which are stale citations, not sentences describing removed behavior.
- `scripts/stale-code-citation-check.py` reports a citation with a line number whose code file changed after the document's design-as-of date. It skips `nc-systems/handoff/handoff-design.md` whole, printing "carries no design-as-of stamp, so no citation in it is dated; not checked", because the file's front matter carries a `rulings-as-of` line, the date of the user-rulings it records, in place of a `design-as-of` line; and line 20 cites no line number, so the script would pass it even in a file it checks.
- `scripts/dangling-path-citation-check.py` reports new citations and citations of removed paths. The pull request removed no path line 20 names.
- `docs/agents/pr-reviewer-instructions.md`, in its Review scope section, already lets a code finding name "a markdown file the change breaks". The reviewer who found line 20 raised a finding of that kind. The sentence permits such a finding and does not ask the reviewer to look for one, and merge-lane-2 recorded this finding as non-blocking.

A search for an existing GHI came up empty: `scripts/ghi-guide-agent-ask.py --include-closed` (then named `ghi-info-ask.py`) on 2026-10-28, asking for a GHI, open or closed, about checking that design prose still matches the code it describes, and `gh issue list --repo nedschorus/nedschorus --state all --search '"design prose" OR "stale design" OR "design drift" OR "design still describes"'`, which returned nothing.

## What a listing of lines would have shown

A list of the design documents that name a file a pull request changes would have named `nc-systems/handoff/handoff-design.md`, the file the author had already edited, so it would have told the author nothing new. A list of the lines that name a changed file would have pointed at line 20. The measurement, at commit 9d25344, covered the 6 files outside `docs/issues/` whose names end in `-design.md`, the one architecture-overview, `docs/nedschorus-wiki/nedschorus-handoff-architecture-overview.md`, and the page `docs/nedschorus-wiki/nedschorus-how-to-write-an-architecture-overview.md`. `docs/issues/`, which holds GHI-MDs, was not searched; the page on how to write an architecture-overview was included because its name matched, though no line in it names a changed file. Each file was searched for the file name of each of the 6 non-Markdown files the pull request changed:

- 25 lines name one of those files: 19 name `handoff-supervisor.py` and 6 name `handoff-context-threshold-hook.py`; none name `walk-files-ship.py` or a test file.
- Of the 6 lines naming the threshold hook, line 20 of `nc-systems/handoff/handoff-design.md` is false. The other 5, lines 29, 71 and 80 of `docs/nedschorus-wiki/nedschorus-handoff-architecture-overview.md`, line 246 of `nc-systems/handoff/handoff-design.md` and line 59 of `nc-systems/cold-read/cold-read-grid-cell-failure-handling-design.md`, describe behavior the pull request kept.
- The pull request's only change to `handoff-supervisor.py` was the wording of the instruction that tells a successor agent-session how to bring the user's open items in an approval-walk. Of the 19 lines naming `handoff-supervisor.py`, one mentions an approval-walk, line 23 of the architecture-overview, about the daily memory review, which the change left alone. The 19 lines were not otherwise read against the code.

## Whether CLAUDE.md's rule on proposing a guard or a validation is met

CLAUDE.md lets an agent propose a guard or a validation only when the failure has happened and it would lose or damage work, stop work beyond the task that failed, or go unnoticed until it does one of those.

- **The failure has happened:** the pull request cited above is one case.
- **The harm is not shown.** A pull request reviewer noticed the line before any agent acted on it, and merge-lane-2 found that no program reads it. A false line in a design can lead an agent who trusts it to build on, or ask the user to decide about, behavior that no longer exists, but no such case is cited here.

Whether a new program or a new reviewer instruction is worth building on one case is the user's decision.

## The user's ruling of 2026-11-01

On 2026-11-01 the user answered "A", approving the rule quoted below and ruling out options 3 and 4, at item 2.25 of cold-read-research's approval-walk cold-read-research-carried-items-2026-10-28 (minutes: `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/cold-read-research-carried-items-2026-10-28-minutes.md` once shipped):

> Until a pull request merges, while its code is built, tested and reviewed, the design document that describes that code is expected to drift from it; no agent is asked to sync the two before the merge, and a mismatch between them blocks no push and no merge of that pull request.

His words at that item, where "this mutation period" is the time while code is built, tested and reviewed: "during this mutation period, we just have to let things get out of sync, and then only after code's been fully tested does it make any sense to try to sync back the design. And even then, I probably would wait ... So I'd probably wait to update the design until we have a reason to update the design."

What happens to the design after its code lands is his rule of 2026-10-29 on line 40 of `docs/nedschorus-wiki/nedschorus-file-naming-and-location-standards.md`: once its code lands, a design "is revised only to fix a flaw found in it, and only after human review".

Options 3 and 4 below are ruled out because each would ask an agent to sync a design to its code before the merge: option 3 by blocking the merge on a design line the code has drifted from, option 4 by handing the pull request reviewer a list of such lines to judge. Options 1, 2 and 5 stay open.

## Options for the user

Options 3 and 4 are ruled out by the user's ruling of 2026-11-01 above. Options 1, 2 and 5 are not decided; the user chooses among them.

1. **Build nothing now.** A pull request reviewer caught this case without being asked to look, and PR [Handoff design drops the walk-close threshold clause, and the walk shipper's test checks a close writes no walk-closed marker](https://github.com/nedschorus/nedschorus/pull/2073) fixed the line; it merged on 2026-10-29 as commit 55895b0.
2. **Remove the prose that restates the code.** The header of `nc-systems/handoff/handoff-design.md` says the document "was gutted to that charter on 2026-08-12 (user-ruled: there is no utility in prose that documents what is better understood by reading the code — mechanism prose drifts)", and that each script's module docstring says what it does. Line 20 is one of the bullets that still say what each script does. Replacing those bullets with the file names alone, pointing at the docstrings, leaves fewer sentences that can go false. The same could be done in other designs.
3. **Ruled out on 2026-11-01: make such a line a blocking finding.** `docs/agents/pr-reviewer-instructions.md` could say explicitly that a design or architecture-overview line the change makes false is "a markdown file the change breaks", so that a finding on it blocks the merge, and could ask the reviewer to look for such lines.
4. **Ruled out on 2026-11-01: a program that lists the lines for the reviewer.** For each non-Markdown file a pull request changes, the program lists each line in a design document or an architecture-overview that names the file, and the pull request reviewer judges each one. On the approval-walk pull request above it would have listed 25 lines, one false. It finds only lines that name a changed file: no design line names `scripts/walk-files-ship.py`, though that pull request changed what the file does. Code would narrow and the reviewer would decide, so the program would be a candidate under the reference-integrity checker GHI listed below.
5. **Rely on refresh-design.** GHI [refresh-design: when a system's code lands, bring its design, build-slice plan and overview into line — removing, never revising](https://github.com/nedschorus/nedschorus/issues/670) brings a system's design and architecture-overview into line with merged code, run at a session-handoff for each system whose code moved. It is not built, and it runs per system over a range of commits rather than per pull request.

Recommendation: options 1 and 2 together, and not option 5: remove the prose that restates the code in `nc-systems/handoff/handoff-design.md` (option 2), because that removes the kind of line that went false, and build no program and no refresh-design step for this (option 1), because CLAUDE.md's rule on proposing a validation is not met for a new program.

## Next action

cold-read-research, the agent-seat that held the 2026-11-01 approval-walk, brings options 1, 2 and 5 to the user as one item of a later approval-walk, with the recommendation above, and records his choice in this GHI-MD.

## Related, not parents

- GHI [Reference-integrity checker: links resolve and cited revision-paths exist — pure-code review check (and the home for what-else-can-code-check)](https://github.com/nedschorus/nedschorus/issues/42), where review aids that code decides, or narrows for a reviewer to decide, are collected.
- GHI [refresh-design: when a system's code lands, bring its design, build-slice plan and overview into line — removing, never revising](https://github.com/nedschorus/nedschorus/issues/670), the same underlying problem solved at a session-handoff rather than at review.
- GHI [Test the agent-instructions files: a Vale trial for the style-guide word checker, and md-drift-lint findings on changed lines block the merge](https://github.com/nedschorus/nedschorus/issues/1990) and GHI [Sort the 60 standing md-drift-lint findings into forward references and stale citations, then fix the stale ones](https://github.com/nedschorus/nedschorus/issues/572), the lint's own work.
