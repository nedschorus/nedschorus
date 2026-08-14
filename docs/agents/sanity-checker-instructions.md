# `sanity-checker` — seat instructions

Your pile — the body of related work this seat owns — is **how this project reviews things, and how well that works.** Read [the seat model](agent-seat-model.md) first: it defines the words used here (pile, seat, walked approval, instruction-class) and explains how seats operate.

**A name that does double duty.** `sanity-checker` is both this seat and the thing it works on: a reviewer *prompt* that reads a design or plan and proposes simplifications. Below, "this seat" means you; "the sanity-checker prompt" means the artifact. They are never the same thing.

**Your work is done when** the grid-seat decision below has been put to the user and ruled, the four un-triaged findings have been verified and routed to the seats that own them, and the PRs listed here are merged or their remaining work is stated. Then write a handoff and stop.

## The decision this pile exists to reach

**Should the sanity-checker prompt become part of the md-review grid** — the eight-cell reviewer array that `scripts/md-review-grid.py` runs over a document — and if so, as three separate reviewers rather than one?

The proposal is three *stances*, each a differently-framed instance of the prompt: **cut** (what should be removed), **mechanization** (what an English instruction could become deterministic code), and **fresh-eyes** (what a reader without history would misread). The three prompt files are in `md-review-records/2026-08-12-attack-split-experiment/`, alongside the evidence.

What is already settled, walked with the user and recorded in the header of `docs/drafts/sanity-checker-prompt-draft.md`: the prompt's scope, its trigger, the order of its sections, **which models it runs on** (Fable and gpt-5.6-sol at xhigh), piecemeal delivery, and who owns triage of its output. **Do not reopen those.** The open question is only whether the prompt takes seats in the grid at all, and as three stances or one.

The evidence is `md-review-records/2026-08-12-attack-split-experiment/scorecard.md`, also in PR #53. Read it before the walk, because the user's first question will be what its numbers mean, and this file deliberately does not restate them — a summary you cannot defend is worse than none.

**A skill change is walked with the user before it is committed.** That is the part within your power; merging is his Mac-side agent's. So the deliverable here is a walk and a ruling, not an applied change.

## Four findings needing triage before anything is proposed

The attack-split experiment surfaced these beyond what the experiment was scored against. They have never been presented to the user. **Every one was written against an archived snapshot of the code, so each claim must be checked against the repository as it is now** — and each is restated here in full, because the original wording was shorthand no one could act on.

1. **The gatekeeper specification promises checks it does not run.** The spec says that when a test suite exists, the tests run at check-in time. A suite now exists (`scripts/git-gatekeeper-test.py`), but nothing wires it into the check-in path. Note carefully what this does and does not mean: the gate is dormant anyway — no credential, so nothing routes through it — so this is not a live hole today. It is an unimplemented promise that would become a live hole on the day the gate activates. Verify by reading the check-in path in `scripts/git-gatekeeper.py`.
2. **Nothing stops the gatekeeper approving a change to its own source.** An agent could edit `scripts/git-gatekeeper.py` and check that edit in through the very program it just changed. Build slice 6 is the intended answer, since it would require walked approval for instruction-class files, and the gatekeeper's own source is proposed to join that class — so verify against the slice plan whether this is already covered by a ruling rather than open.
3. **Agents hand-write 40-character commit ids into records, and mistype them.** The proposal is that whatever writes such a record stamps the id itself rather than an agent transcribing it. No mechanism was designed; the finding is that the manual path exists at all. Verify by looking for hand-written full SHAs in recent records.
4. **A session can stall without anything noticing.** The handoff system replaces a session when its context runs low, but a session that hangs while still well under that threshold trips nothing — no timer, no liveness check. Verify against `scripts/handoff-supervisor.py` and `scripts/handoff-context-threshold-hook.py`, and note this one cannot be settled by reading code alone: it is a claim about runtime behaviour, so if you cannot verify it, say so rather than manufacturing a code-level test.

**Where each goes after verification.** Findings 1 and 2 belong to the `gatekeeper` seat, 4 to `fleet`, and 3 to whichever seat owns the record-writing path it turns out to touch — decide that when you know, and say why. Seats cannot hand work to each other directly: write the survivor into the receiving seat's brief or a queue document under `docs/issues/queue/`, and tell the user what you routed where. A triage whose output is not written down evaporates, which is precisely how these four went un-presented for two days.

## Background you will need

- `docs/drafts/sanity-checker-prompt-draft.md` — the settled prompt, plus the header recording what has been walked.
- `md-review-records/2026-08-09-git-gatekeeper-design/subtract-cell-prompt-lessons.md` — the requirements record behind it, including the user's verbatim statement of what "simplify" must mean, and a calibration protocol proposed as a precondition for adopting the prompt into the grid. Read that protocol before the walk and form a view: it is a proposal, not a rule, and whether it should gate adoption is part of what the user is deciding.
- `md-review-records/2026-08-11-sanity-checker-prompt-draft/` — the md-review of that draft.
- The grid itself: `.claude/skills/md-review/SKILL.md`, `scripts/md-review-grid.py`, and the per-runtime cell scripts. The grid runs each document past eight reviewers — two runtimes (Claude and Codex) × two model tiers × two cell kinds (defect hunt and restate). The Codex lower tier changed model on 2026-08-13; that affects which model produces those cells and nothing about how the grid is run.

**PRs yours to shepherd:** [#51](https://github.com/nedschorus/nedschorus/pull/51) (skill rules — walk choice items are proposals; md-review delivers piecemeal under a Monitor) and [#53](https://github.com/nedschorus/nedschorus/pull/53) (the attack-split experiment and its scorecard). If either has merged, note it. If either has review comments, address them on its branch. Merging is not yours.

## An unowned thread worth claiming

Session `29d66917` (3.67 MB, last active 2026-08-13) drafted a **code-review prompt for reliability improvement** in `~/agents/choirmaster`. No live session, no handoff, mentioned nowhere else — and plainly your subject. Its transcript is `~/.claude/projects/-home-nedlern-agents-choirmaster/29d66917-9767-47cb-a221-d4876d8014cd.jsonl`. Read it before starting any code-review-prompt work; that wheel is partly built.

## The user's standing bar for reviewers

From the 2026-08-10 walk: *"asking to simplify is like asking to optimize without context."* State the axis. This project's axis is **simple-to-operate over simple-to-build; mechanical guarantees over trained habit; a detector with no consumer is cost without value; never trade a deterministic script for probabilistic agent behavior.**

## First action

Read the scorecard and the prompt draft's header, verify the four findings against current code, and route them. Then offer the user the grid-seat walk. He was asked once which should come first — the walk or the triage — and never answered; do the triage first, since its results may bear on the walk, and say that is what you did.
