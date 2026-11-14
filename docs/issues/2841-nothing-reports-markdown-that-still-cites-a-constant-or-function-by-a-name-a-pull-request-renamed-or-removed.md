---
issue: "[Nothing reports Markdown that still cites a constant or function by a name a pull request renamed or removed](https://github.com/nedschorus/nedschorus/issues/2841)"
---

# Nothing reports Markdown that still cites a constant or function by a name a pull request renamed or removed

## What is wrong

When a pull request renames or removes a constant, a function or a class, Markdown that cites the old name in backticks, such as a GHI-MD under `docs/issues/`, a design or a wiki page, keeps the old name, and no program reports it. A file path that a pull request removes is already checked, by `scripts/branch-leaves-no-citations-of-removed-paths-test.py` and `scripts/dangling-path-citation-check.py`; a code name is not.

## The evidence

- PR [Memory refusal prints only the caller's instructions, chosen by agent_id](https://github.com/nedschorus/nedschorus/pull/2818), merged as commit ce0e1fc, replaced the constant `MEMORY_WRITE_DENY_MESSAGE` in `.claude/guard-hooks/instruction-file-guard.py` with `MAIN_AGENT_MEMORY_WRITE_DENY_MESSAGE` and `SUBAGENT_MEMORY_WRITE_DENY_MESSAGE`, both built by `memory_write_deny_message`.
- At that commit, three GHI-MDs still cite the old name: `docs/issues/30-trigger-first-instruction-delivery-design.md` three times, `docs/issues/1349-save-each-lesson-where-agents-meet-it-at.md` twice and `docs/issues/2118-ruling-agent-keeps-user-rulings-checks-approval-walk.md` once. On main at d7ad9fb2f, `git grep -nw MEMORY_WRITE_DENY_MESSAGE -- '*.md'` still finds those six lines.
- A Claude pull request reviewer, posting as `mac-claude`, found them by running `git grep` for the old name, and made no finding on them because no program parses those lines, in [review 5819097651](https://github.com/nedschorus/nedschorus/pull/2818#pullrequestreview-5819097651). merge-lane-2 carried them as non-blocking item 1 of [review 5819112007](https://github.com/nedschorus/nedschorus/pull/2818#pullrequestreview-5819112007) and merged PR 2818. No program reported them.
- PR [Issue files cite the split memory refusal constants](https://github.com/nedschorus/nedschorus/pull/2829) fixes the six lines; the `#root_cause_not_fixed` line of its description links this issue.

## Why the existing tools say nothing

- `scripts/md-drift-lint.py` checks paths, links, dates, a command's flags, and a number in backticks against the one code file its sentence names; its module docstring lists no check of a code name. Run at commit ce0e1fc on the three GHI-MDs above, it exits 1 with 20 lines of output, none of which names `MEMORY_WRITE_DENY_MESSAGE`.
- `scripts/dangling-path-citation-check.py` and `scripts/branch-leaves-no-citations-of-removed-paths-test.py` check paths; PR 2818 removed no path.
- `scripts/stale-code-citation-check.py` checks only citations with a line number, in documents with a `design-as-of` line.

A search for an existing GHI came up empty: on 2026-11-08, `scripts/ghi-guide-agent-ask.py --include-closed`, asking for a GHI, open or closed, about a check that finds Markdown still citing a constant, function or class a pull request renamed or removed, named only adjacent issues (listed under Related), none about code names; and `gh issue list --repo nedschorus/nedschorus --state all --search 'renamed constant OR "renamed function" OR "stale identifier" OR "old name" in:title,body'` returned only GHI [dangling-path-citation-check: three measured blind spots — two for code, one for disclosure](https://github.com/nedschorus/nedschorus/issues/614), closed, which is about path blind spots in `dangling-path-citation-check.py`.

## Whether CLAUDE.md's rule on proposing a guard or a validation is met

CLAUDE.md lets an agent propose a guard or a validation only when two things hold: the failure has happened, or concrete evidence shows it is foreseeable within the next 30 days; and it would lose or damage work, stop work beyond the task that failed, or go unnoticed until it does one of those.

- **The failure has happened:** the case above.
- **The harm is not shown.** A pull request reviewer noticed the stale name at review, before any agent acted on it. An agent that searches the code for a name a GHI-MD gives would find nothing and could take the feature for missing, but no such case is cited here.

Whether to build anything on one case is the user's decision.

## Options for the user

1. **Build nothing now.** A pull request reviewer caught this case, and PR 2829 fixes it. Reopen the question when a second case shows harm.
2. **A test of removed names, run on the nc-topic-branch before merge as the path test is.** For each Python name defined at module level that the branch's diff against main removes from a file and does not define again in that file, which covers a rename because a rename removes the old name, search tracked Markdown for the name in backticks, and report each hit. It would be one more check beside `scripts/branch-leaves-no-citations-of-removed-paths-test.py`, the path check, or a mode of `scripts/dangling-path-citation-check.py`. It would have reported the six lines above. It misses names in other languages, names defined inside functions or classes, a name moved to another file, and a name cited without backticks. Before this is built, a measurement over recent merged pull requests should count how many hits are real and how many come from historical prose that is meant to keep an old name; the counts go to the user, who decides whether to build the test and how it tells the two apart.
3. **Fold it into GHI 42**, the reference-integrity checker, as a candidate for code to check, and build nothing until that checker is built.

Recommendation: option 1, because the harm condition of CLAUDE.md's rule is not met, and the user's ruling of 2026-11-01 recorded in GHI [Nothing checks that a design document still describes the code a pull request changes](https://github.com/nedschorus/nedschorus/issues/2078) chose to build no program for the closely related case of design prose that drifts from code.

## What the user ruled, 2026-11-08

The user chose option 1, build nothing now, answering "A" at 2026-11-08 19:10 to item 4 of 5 of the approval-walk whose minutes are `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/memory-refusal-only-the-callers-lines-and-restored-branch-task-rebase-gap-approval-walk-2026-11-08-minutes.md`, which `scripts/walk-files-ship.py` puts there when the walk closes; on 2026-11-08 the walk was still open and the file was there only in the walk's checkout, under `docs/walk/`. The one case did no harm: a pull request reviewer found the six lines and PR 2829 fixed them, so the harm condition of CLAUDE.md's rule on proposing a guard or a validation is not met. The issue closes as not planned, until a second case shows harm.

## Next action

None: the issue closes as not planned, under the ruling above.

## Related, not parents

- GHI [Reference-integrity checker: links resolve and cited revision-paths exist — pure-code review check (and the home for what-else-can-code-check)](https://github.com/nedschorus/nedschorus/issues/42), where checks that code can decide are collected.
- GHI [Nothing checks that a design document still describes the code a pull request changes](https://github.com/nedschorus/nedschorus/issues/2078), the same drift for sentences about behavior rather than names.
- GHI [Cite files by name, not by path](https://github.com/nedschorus/nedschorus/issues/610), the same problem for file names.
- GHI [Sort the 60 standing md-drift-lint findings into forward references and stale citations, then fix the stale ones](https://github.com/nedschorus/nedschorus/issues/572) and GHI [Test the agent-instructions files: a Vale trial for the style-guide word checker, and md-drift-lint findings on changed lines block the merge](https://github.com/nedschorus/nedschorus/issues/1990), the lint's own work.
