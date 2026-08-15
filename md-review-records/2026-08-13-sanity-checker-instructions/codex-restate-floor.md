<!-- provenance: runtime=codex model=gpt-5.6-luna effort=xhigh cell=restate tier=floor target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/agents/sanity-checker-instructions.md -->

# `sanity-checker` — seat instructions

1. This seat is responsible for examining how the project conducts reviews and how effective those reviews are.
2. The relevant subjects are the sanity-checker reviewer, the md-review grid that the reviewer might join, and the skill rules controlling how reviews are conducted.
3. The seat model explains how seats function, and this file serves as the sanity-checker’s instructions.

## The decision waiting on the user

1. The unresolved question is whether the sanity-checker should join the md-review grid by running three separate attacks—cut, mechanization, and fresh-eyes—using both Fable and `gpt-5.6-sol` at the `xhigh` setting.
2. The entire attack-split experiment was designed to answer that question, and the question has remained unresolved since 2026-08-13.
3. The evidence is recorded in `md-review-records/2026-08-12-attack-split-experiment/scorecard.md` and also appears in PR #53: the split performed better than the unsplit baseline, with the gatekeeper accepting 4 of 5 in-band cuts compared with the baseline’s best result of 3 of 6, fast-handoff matching parity and finding additional issues in all 7 of 7 cases, no unflagged false positives across 8 judgment cells, and each runtime finding cuts that the other runtime failed to find.
4. The operating decisions already discussed with the user—scope, trigger, order, models, piecemeal delivery, and triage ownership—are recorded in the header of `docs/drafts/sanity-checker-prompt-draft.md`.
5. Any change to a skill must first be walked through with the user before it is applied, so the present task is to conduct that discussion rather than immediately change anything.

## The un-triaged novel findings

1. The experiment found four issues that were absent from both ground-truth sets.
2. None of these findings has been presented or triaged, and every one was based on an archived snapshot; therefore, every factual claim quoted from those findings must be checked against the current code before any proposal is made.
3. The gatekeeper specification says that, when a test suite exists, the tests run in this location, but that condition never caused anything to run even though the test suite now exists; consequently, the gate currently performs no checks.
4. There is no safeguard for the case where the gate edits the gate itself.
5. There is a proposal for a writer to stamp the pin—apparently the 40-character SHA—so that agents do not have to write those full SHA values manually.
6. A session can become stuck while remaining below the threshold that would cause it to be recycled, and there is no watchdog monitoring for that condition.
7. Findings 1 and 2 belong to the gatekeeper seat, while finding 4 belongs to the fleet seat; the sanity-checker should assess them here and then pass any surviving findings to those seats instead of implementing the findings itself.

## Background you will need

1. `docs/drafts/sanity-checker-prompt-draft.md` contains the settled prompt, which was developed from the beginning after an earlier draft was rejected because it attempted to redefine the ordinary meaning of “simple.”
2. `md-review-records/2026-08-09-git-gatekeeper-design/subtract-cell-prompt-lessons.md` records the requirements learned from the flawed first subtraction review, including the user’s exact statement of the relevant axis; its calibration procedure is the active prerequisite that every grid seat must pass before participating.
3. The md-review of the prompt draft is located in `md-review-records/2026-08-11-sanity-checker-prompt-draft/`.
4. The md-review system consists of `.claude/skills/md-review/`, `scripts/md-review-grid.py`, and the individual runtime cells; on 2026-08-13, PR #57 changed the minimum Codex floor tier from terra to luna.
5. PR #51 and PR #53 are the pull requests this seat is responsible for guiding: the choice items in PR #51 are proposals, and md-review will deliver them incrementally under the supervision of a Monitor; PR #53 contains the attack-split experiment.
6. PR #52, which applies the fast-handoff findings, is related but not one of the primary PRs to shepherd; if it needs work, coordinate with the `fleet` seat.

## An unowned thread worth claiming

1. Session `29d66917`, which was 3.67 MB and last active on 2026-08-13, drafted a code-review prompt intended to improve reliability in `~/agents/choirmaster`.
2. There is no currently active session for that work, it is not mentioned in any handoff, and it is clearly related to the sanity-checker’s assigned subject matter.
3. The transcript is stored at `~/.claude/projects/-home-nedlern-agents-choirmaster/29d66917-9767-47cb-a221-d4876d8014cd.jsonl`.
4. That transcript must be read before beginning any work on a code-review prompt because part of the same work has already been done.

## The user's standing bar for reviewers

1. At step S6 of the 2026-08-10 walk, the user stated that asking for simplification is like asking for optimization without specifying the context.
2. The reviewer must explicitly state the axis along which something is being judged.
3. For this project, the preferred axis is operational simplicity over ease of implementation, guarantees enforced mechanically over behavior people merely learn to follow, useful detectors over detectors whose results no one consumes, and deterministic scripts over agent behavior that is only probabilistically reliable.

## First action

1. The first steps are to read the scorecard and the prompt draft’s header, check all four novel findings against the current code, and then offer the user the grid-seat walk, because reaching that decision is the purpose of this seat’s assignment.
2. The user has already been asked whether to do the walk or the triage first but has not answered, so the question must be asked again directly and the user must be allowed to choose.
