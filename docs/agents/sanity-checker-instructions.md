# `sanity-checker` — seat instructions

Your pile: **how this project reviews things, and how well that works.** The sanity-checker reviewer, the md-review grid it may join, and the skill rules that govern how reviews are delivered. Read [the seat model](agent-seat-model.md) for how seats work; this file is your brief.

## The decision waiting on the user

**Does the sanity-checker join the md-review grid as three stance attacks** — cut, mechanization, fresh-eyes — run on both Fable and gpt-5.6-sol at xhigh? This is the decision the whole attack-split experiment was built to answer, and it has been waiting since 2026-08-13.

The evidence is `md-review-records/2026-08-12-attack-split-experiment/scorecard.md` (also in PR #53): the split beat the unsplit baseline — gatekeeper 4 of 5 in-band accepted cuts against the baseline's best 3 of 6, fast-handoff 7 of 7 parity plus novel findings, zero unflagged false positives across eight judgment cells, and each runtime surfacing cuts the other missed. The already-walked operating rulings — scope, trigger, order, models, piecemeal delivery, triage ownership — are in the header of `docs/drafts/sanity-checker-prompt-draft.md`. **A skill change is walked with the user before it lands**, so this is a walk, not an application.

## The un-triaged novel findings

The experiment surfaced four findings beyond both ground-truth sets. Never presented, never triaged, and each read an *archived* snapshot — so **verify every quoted ground against current code before proposing anything**:

1. The gatekeeper spec's "when a test suite exists, the tests run here" never fired, though the suite now exists — so the gate runs no checks today.
2. No gate-edits-the-gate guard.
3. A writer-stamps-the-pin proposal, to stop agents hand-writing 40-character SHAs.
4. The wedged-but-light session: stalls below the recycle threshold with no watchdog.

Findings 1 and 2 are gatekeeper territory and 4 is fleet territory — triage them here, then hand the survivors to those seats rather than implementing them yourself.

## Background you will need

- `docs/drafts/sanity-checker-prompt-draft.md` — the settled prompt, walked from scratch after a first draft was rejected for trying to redefine the everyday meaning of "simple".
- `md-review-records/2026-08-09-git-gatekeeper-design/subtract-cell-prompt-lessons.md` — the requirements record: what the flawed first subtraction review taught, including the user's verbatim axis statement. Its calibration protocol is the live gate before any grid seat.
- `md-review-records/2026-08-11-sanity-checker-prompt-draft/` — the md-review of that draft.
- The md-review machinery itself: `.claude/skills/md-review/`, `scripts/md-review-grid.py`, and the per-runtime cells. Note the Codex floor tier moved terra → luna on 2026-08-13 (in PR #57).

**Open PRs yours to shepherd:** [#51](https://github.com/nedschorus/nedschorus/pull/51) (walk choice items are proposals; md-review delivers piecemeal under a Monitor) and [#53](https://github.com/nedschorus/nedschorus/pull/53) (the attack-split experiment). [#52](https://github.com/nedschorus/nedschorus/pull/52) — fast-handoff findings applied — is adjacent; coordinate with `fleet` if it needs work.

## An unowned thread worth claiming

Session `29d66917` (3.67 MB, last active 2026-08-13) drafted a **code-review prompt for reliability improvement** in `~/agents/choirmaster`. No live session, mentioned in no handoff, and plainly related to your pile. Its transcript: `~/.claude/projects/-home-nedlern-agents-choirmaster/29d66917-9767-47cb-a221-d4876d8014cd.jsonl`. Read it before starting any code-review-prompt work — that wheel is already partly built.

## The user's standing bar for reviewers

Stated at S6 of the 2026-08-10 walk: *"asking to simplify is like asking to optimize without context."* State the axis. This project's axis is **simple-to-operate over simple-to-build; mechanical guarantees over trained habit; a detector with no consumer is cost without value; never trade a deterministic script for probabilistic agent behavior.**

## First action

Read the scorecard and the prompt draft's header, verify the four novel findings against current code, then offer the user the grid-seat walk — the decision this pile exists to reach. He has already been asked "which first, the walk or the triage?" and has not answered; ask again plainly and let him choose.
