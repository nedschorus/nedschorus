---
issue: "[Review the whole project for fixed markers that would be clearer as hashtags](https://github.com/nedschorus/nedschorus/issues/1518)"
---

# Review the whole project for fixed markers that would be clearer as hashtags

## Why

Agents and programs in this project look for fixed words in documents and output: a line in a pull request's description that began `Root cause:` before it became the hashtag `#root_cause`, the line `VERDICT: CONFLICT` that `scripts/branch-conflict-check.py` prints, the first line `Report complete: no findings.` of an empty cold-read report, the walk-minutes classes such as `<approved as revised>`. Each is written in its own style, and a reader cannot always tell a fixed marker from ordinary prose, nor search for one without knowing its exact spelling and punctuation.

A hashtag — `#` followed by lowercase words joined by underscores, such as `#not_in_this_run` — stands out to a reader, and a program or an agent finds it with one exact search. Underscores keep it apart from project-terms, which are hyphenated. `#` with no space after it does not make a Markdown heading.

## The example that prompted this review

The design-to-main proposal for sorting a design's deferred-decisions (nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/prime-intellect/design-to-main-deferred-decisions-proposal-2026-10-15.md) marks each line of a design's `Deferred-decisions` section that the user has deferred. The approval-walk on that proposal, design-to-main-deferred-decisions-proposal-two-buckets-2026-10-15 (item 1.1, before the user when this GHI-MD was written; its minutes ship to nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/design-to-main-deferred-decisions-proposal-two-buckets-2026-10-15-minutes.md when it closes), proposes the markers as hashtags:

- `#not_in_this_run` begins a deferred line: "#not_in_this_run retry a failed push. Reason: an optimisation; one failure stops the run and tells the user."
- `#rejected` begins a line the user turned down for good.
- `#revisit_when` names the event before which a deferred line must be decided.

The hashtag form is proposed, not yet a project convention. If the user rejects item 1.1, this review still asks whether a shared marker form is worth having, without assuming hashtags.

The user ruled on 2026-10-19 that the pull-request-description labels `Root cause:`, `Root cause not fixed:` and `No defect fixed.` become the hashtags `#root_cause`, `#root_cause_not_fixed` and `#no_defect_fixed`: "we're moving to hashtags instead of something colon. So I'd like that changed." Pull request [#1728](https://github.com/nedschorus/nedschorus/pull/1728) carried it out; `scripts/merge-gate.sh` reads both forms.

## Proposed project-term

It goes to the user with the review's first findings, and is used here only as a proposal:

- **hashtag** — a fixed marker that agents or programs look for in a document or in output, written `#` followed by lowercase words joined by underscores, such as `#not_in_this_run`; the underscores keep hyphens reserved for project-terms and system-terms.

## The work

1. List every fixed marker the project uses that an agent or a program looks for, from agent-instructions, skills and their prompts, GHI-MDs, designs, hooks, and the scripts that parse or print markers. Starting points, each found on main: `#root_cause`, `#root_cause_not_fixed` and `#no_defect_fixed`, already hashtags (`CLAUDE.md` tells an author to write one in each pull request's description, `scripts/ghi-issue-write.py` writes `#no_defect_fixed` in the descriptions of the pull requests it opens, and `scripts/merge-gate.sh` checks them); `VERDICT: CONFLICT` (printed by `scripts/branch-conflict-check.py`, quoted by `docs/nedschorus-wiki/nedschorus-how-a-program-reports-success-failure-and-findings-with-its-exit-code.md` and read by programs such as `scripts/git-client-side-hooks-pre-push-conflict-check.py`); `Report complete: no findings.` and `clean sections:` (`.claude/skills/cold-read/prompts/defect-hunt-prompt.md`); the walk-minutes classes `<accepted>`, `<approved as revised>`, `<revised, awaiting ruling>`, `<moved on, no decision>` (`.claude/skills/walk-me-through/SKILL.md`).
2. For each, record where it is written, which programs or agents read it, and what changing it would break: the parsing code, its tests, and the documents that quote it.
3. Recommend, for each, to keep it or to make it a hashtag, with the reason. A marker a program prints for a person, or one that an outside tool fixes (such as a git trailer), likely stays.
4. Bring the recommendations to the user in an approval-walk. Nothing changes without his ruling; each approved change is its own pull request, with its parser and tests.
5. Build a maintenance-job that keeps the list from drifting, because new programs and prompts keep adding fixed markers after the sweep. The job renames nothing: a conversion is still put to the user under step 4 and made in its own pull request. Its design, for its build:
   - **What it reads.** The files under `scripts/`, `nc-systems/`, `.claude/guard-hooks/` and `.claude/skills/`, and the standing instruction files (`CLAUDE.md`, `AGENTS.md`, every seat-brief and every `-instructions.md` and `-prompt.md` file), changed on main since the job's last run, and main's copy of the supporting list, `docs/issues/1518-fixed-markers-list-every-literal-string-programs-and-prompts-match-with-its-readers-and-proposed-hashtag.md`.
   - **The program part.** A program, with no model, lists the candidates in the lines changed since the last run: a string literal that a program compares, searches for or splits text on, such as the argument of `in`, `startswith`, `re.search` or `grep`; and a backquoted literal that agent-instructions tell an agent to write or look for. For each candidate it says whether the supporting list already holds it, and whether it is a hashtag. A candidate is judged once: the next run reads only the lines changed after this one.
   - **The agent part.** For each candidate the supporting list does not hold, the job's agent-session judges whether it is a fixed marker by the list's own definition, text that crosses a boundary between programs or agents, and for each that is one, writes a row in the list's table format, with a recommendation to keep it or make it a hashtag.
   - **How often.** Weekly. Fixed markers enter only through merged pull requests, a few in a week, and a marker that waits up to a week to be listed costs nothing, because none is converted before the user rules on it under step 4; a daily run would mostly report nothing. No single moment marks the change either, so the job stays weekly for the reason GHI 1058 gives for its weekly hook and program measurement.
   - **What it reports, and where.** One line per fixed marker, added since the last run, that the supporting list does not hold, with its proposed row; and one line per place, added since the last run, that writes or reads a fixed marker in a form the user has ruled replaced by a hashtag, such as a new `Root cause:` line. The report is one file per run in the maintenance report directory in the log-store that GHI 1058 decides. A week with no finding says so in one line; a file the job could not read is named, with the reason, and never reported as clean.
   - **How it reaches the user.** As every maintenance-job does, by the route GHI 1058 decides in its sections "How the maintenance jobs run each night, and how often (decided)" and "How a daily job is handed to the user and tracked (decided)": a scheduled program on ned-box runs the job's program part, and one nightly overseer agent-session, which the handoff-supervisor starts under a fixed name so that the user reaches it through Remote Control, puts the questions of every due job to him in one approval-walk and links each report file; a question he has not answered stays queued for the next night.
   - **What becomes of its rows.** The agent-session adds the rows the user accepts to the supporting list as an edit of that file through the ghi-write-tool; the user's ruling on each recommendation still waits for step 4's approval-walk.

The user ruled on 2026-10-27, answering item 1 of the approval-walk issue-design-file-edits-and-alert-term-approval-walk-2026-10-27 in the agent-seat `fleet-restart-at-login` (its minutes ship to nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/issue-design-file-edits-and-alert-term-approval-walk-2026-10-27-minutes.md when it closes), that the remaining systems are swept now and that a maintenance-job follows the sweep: "You can edit, yeah, approve, and maybe we need a maintenance check to see about cleaning up the other things that should be #hashtags. We'll need a maintenance check, even if there's a one-time, because it'll slowly get drift. Doesn't sound like there's any reason to defer doing the full sweep. So if you think that's reasonable, you can start that too with Codex or subagents".

## Related issues

- GHI [Regular maintenance: the list of maintenance jobs, how often each runs, and how each reaches the user](https://github.com/nedschorus/nedschorus/issues/1058): its daily check for names a reader cannot understand away from where they are defined already lists short fixed-set values such as the walk-minutes classes. Step 5's maintenance-job joins that GHI's list of maintenance jobs and reaches the user by its route.
- GHI [Type definitions for the project's kinds of markdown: what each contains, leaves out, and how long it runs](https://github.com/nedschorus/nedschorus/issues/1080): the natural home for any marker convention per kind of document.

ghi-guide-agent, asked on 2026-10-15 whether an issue covers conventions for fixed markers or hashtags (`scripts/ghi-guide-agent-ask.py --include-closed`), found none: "No open or closed issue proposes a general convention for fixed line-start labels, VERDICT lines, or `#hashtag`-style markers as a reusable pattern across the project."

## Next action

Steps 1 to 3 are in the supporting document `docs/issues/1518-fixed-markers-list-every-literal-string-programs-and-prompts-match-with-its-readers-and-proposed-hashtag.md`, one section per system. Its sweep is done: every program and prompt under `scripts/`, `nc-systems/`, `.claude/guard-hooks/` and `.claude/skills/`, and every standing instruction file on ned-box, falls in a section, as its last section says. Two pieces remain before step 4: an agent-seat on the Mac sweeps the Mac's seat-briefs, which ned-box cannot reach, and adds a section for them; and the list gains a row for the fixed text that merge-lane-2's seat-brief, `/home/nedlern/agents/merge-lane-2/CLAUDE.local.md` on ned-box, sets for a review that carries findings, such as the three sentences it says such a review ends with, word for word. Then step 4's approval-walk takes the list to the user, and step 5's maintenance-job is built so that the list does not drift.
