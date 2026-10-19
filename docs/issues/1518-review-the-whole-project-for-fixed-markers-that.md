---
issue: "[Review the whole project for fixed markers that would be clearer as hashtags](https://github.com/nedschorus/nedschorus/issues/1518)"
---

# Review the whole project for fixed markers that would be clearer as hashtags

## Why

Agents and programs in this project look for fixed words in documents and output: a line in a pull request's description that begins `Root cause:`, the line `VERDICT: CONFLICT` that `scripts/branch-conflict-check.py` prints, the first line `Report complete: no findings.` of an empty cold-read report, the walk-minutes classes such as `<approved as revised>`. Each is written in its own style, and a reader cannot always tell a fixed marker from ordinary prose, nor search for one without knowing its exact spelling and punctuation.

A hashtag — `#` followed by lowercase words joined by underscores, such as `#not_in_this_run` — stands out to a reader, and a program or an agent finds it with one exact search. Underscores keep it apart from project-terms, which are hyphenated. `#` with no space after it does not make a Markdown heading.

## The example that prompted this review

The design-to-main proposal for sorting a design's deferred-decisions (nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/prime-intellect/design-to-main-deferred-decisions-proposal-2026-10-15.md) marks each line of a design's `Deferred-decisions` section that the user has deferred. The approval-walk on that proposal, design-to-main-deferred-decisions-proposal-two-buckets-2026-10-15 (item 1.1, before the user when this GHI-MD was written; its minutes ship to nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/design-to-main-deferred-decisions-proposal-two-buckets-2026-10-15-minutes.md when it closes), proposes the markers as hashtags:

- `#not_in_this_run` begins a deferred line: "#not_in_this_run retry a failed push. Reason: an optimisation; one failure stops the run and tells the user."
- `#rejected` begins a line the user turned down for good.
- `#revisit_when` names the event before which a deferred line must be decided.

The hashtag form is proposed, not yet a project convention. If the user rejects item 1.1, this review still asks whether a shared marker form is worth having, without assuming hashtags.

## Proposed project-term

It goes to the user with the review's first findings, and is used here only as a proposal:

- **hashtag** — a fixed marker that agents or programs look for in a document or in output, written `#` followed by lowercase words joined by underscores, such as `#not_in_this_run`; the underscores keep hyphens reserved for project-terms and system-terms.

## The work

1. List every fixed marker the project uses that an agent or a program looks for, from agent-instructions, skills and their prompts, GHI-MDs, designs, hooks, and the scripts that parse or print markers. Starting points, each found on main: `Root cause:`, `Root cause not fixed:` and `No defect fixed.` (`CLAUDE.md`, written by `scripts/ghi-issue-write.py`, checked by `scripts/merge-gate.sh`); `VERDICT: CONFLICT` (`CLAUDE.md`, printed by `scripts/branch-conflict-check.py` and read by programs such as `scripts/git-client-side-hooks-pre-push-conflict-check.py`); `Report complete: no findings.` and `clean sections:` (`.claude/skills/cold-read/prompts/defect-hunt.md`); the walk-minutes classes `<accepted>`, `<approved as revised>`, `<revised, awaiting ruling>`, `<moved on, no decision>` (`.claude/skills/walk-me-through/SKILL.md`).
2. For each, record where it is written, which programs or agents read it, and what changing it would break: the parsing code, its tests, and the documents that quote it.
3. Recommend, for each, to keep it or to make it a hashtag, with the reason. A marker a program prints for a person, or one that an outside tool fixes (such as a git trailer), likely stays.
4. Bring the recommendations to the user in an approval-walk. Nothing changes without his ruling; each approved change is its own pull request, with its parser and tests.

## Related issues

- GHI [Daily maintenance in one daily step, starting with a daily check of every wiki page](https://github.com/nedschorus/nedschorus/issues/1058): its daily check for names a reader cannot understand away from where they are defined already lists short fixed-set values such as the walk-minutes classes.
- GHI [Type definitions for the project's kinds of markdown: what each contains, leaves out, and how long it runs](https://github.com/nedschorus/nedschorus/issues/1080): the natural home for any marker convention per kind of document.

ghi-info, asked on 2026-10-15 whether an issue covers conventions for fixed markers or hashtags (`scripts/ghi-info-ask.py --include-closed`), found none: "No open or closed issue proposes a general convention for fixed line-start labels, VERDICT lines, or `#hashtag`-style markers as a reusable pattern across the project."

## Next action

An agent-seat takes step 1 and writes its list as a supporting document beside this GHI-MD, named with the issue's number as the GHI write tool links it, such as `<number>-fixed-markers-list.md`.
