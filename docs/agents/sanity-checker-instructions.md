# `sanity-checker` — seat instructions

Your pile — the body of related work this seat owns — is **how this project reviews things, and how well that works.** Read [the seat model](agent-seat-model.md) first: it defines the words used here (pile, seat, walked approval, instruction-class) and explains how seats operate.

**A name that does double duty.** `sanity-checker` is both this seat and the thing it works on: the project's second review instrument — three audit prompts and the runner that dispatches them. Below, "this seat" means you; "the sanity-checker" means the instrument. They are never the same thing.

**Your work is done when** the owed re-review below has run and its findings are walked, the first live run (walk-order item 6) is ruled and executed, and the record directories this work leaves behind are disposed per the house rule. Then write a handoff and stop.

## The standing shape (ruled — do not reopen)

- **A separate instrument, never a grid cell** (user-ruled 2026-08-17, on the attack-split validation experiment's scorecard — recoverable at `git show 'ab541cc^':md-review-records/2026-08-12-attack-split-experiment/`).
- **Three stance audits, each in its own fresh context**: cut, mechanization, fresh-eyes. Amended by user ruling 2026-08-21: a fourth audit — hidden dependencies, untestable claims, criteria vs intent — is wanted; its build is [nedschorus#121](https://github.com/nedschorus/nedschorus/issues/121), and the shape stays three until that prompt earns its STANDING header. The prompts are the instrument's entire instruction surface, at `docs/agents/sanity-checker-{cut,mechanization,fresh-eyes}-attack-prompt.md`, each with a STANDING header; the runner is prompt-free by ruling.
- **The runner**: `scripts/sanity-check-attacks.py`. Its docstring is the operating-rules home — both runtimes at xhigh, manual call after md-review on actionable (work-directing) MDs only, never automatic, records in `sanity-check-records/` under the house disposal rule.
- **The 2026-08-17/18 revision**: all three prompts went through a full md-review findings walk, every flagged sentence ruled. Fresh-eyes now runs the instructed-isolation model — the agent is told what not to read (the review request carries off-limits and read-first lists the requester writes; the requester-facing problem-statement section sits above the fresh-eyes divider), and the runner's coined-name leak scan checks the problem statement and the injected instruction files, printing LEAK-WARNING lines for triage (the agent's own report is not scanned — its instructed disclosures are the check, user-ruled 2026-08-19). Calibration evidence: `md-review-records/2026-08-17-fresh-eyes-canary/`.
- **Owed before first live use (user-ruled 2026-08-17):** a full md-review grid re-review of all three revised prompts, then the sanity-check run of walk-order item 6.

## Closed history (pointers only)

- The grid-seat decision this pile existed to reach: RULED as above; the scorecard at the `git show` pointer is the evidence.
- The attack-split experiment's four side findings: verified, routed, closed via PR #77.
- The parent prompt draft and its predecessors: deleted from `docs/drafts/`; each path's git history is its decision trail.
- PRs [#51](https://github.com/nedschorus/nedschorus/pull/51) and [#53](https://github.com/nedschorus/nedschorus/pull/53): closed 2026-08-13 as already landed — not rejections.
- First live run (2026-08-19, target: the cut attack prompt): six cells, all saved; the 19-item triage walk landed every accepted change in the prompts, the runner, CLAUDE.md, and the walk skill (commits eaaef96 through the seat-model row fix, same day). Rejected with reopen conditions, so they are not re-proposed from scratch: a runner-built ruling-marker inventory and report-section presence checks — both insure against failures with no occurrence on this instrument's record; reopen on the first observed miss. The report-side leak scan was deleted the same day: the cell's instructed disclosures are the check, the input-side scan stays.
- The user's read of the assembled fresh-eyes cell prompt (2026-08-20): he edited the whole assembly; a 7-item walk routed every edit home. The attack is reframed as a competitive design for a best-of-both synthesis (it subsumes the old verify-by-diff purpose); the priorities are his four-item form; the cell is invited to beat the withheld design. Request-authoring patterns for the remaining two first-run targets: the problem statement names the carefully-described-yet-useless trap, a specimen input is listed read-first and marked not-for-review, CLAUDE.md stays on read-first (ruled when no AGENTS.md existed; AGENTS.md exists since 2026-08-20, codex agents receive it injected, and the runner's leak scan already lists it among the injected instruction files). His edit is preserved at `sanity-check-records/2026-08-20-user-edit-fresh-eyes-assembled.md` (machine-local) until those runs land. The cut and mech assembled prompts await his read; the evidence-paragraph and priorities wordings may then need a sync ruling.
- Mechanization-guard amendment held (user-ruled 2026-08-21): a clause naming a short linear sequence of simple prompt steps as a non-finding — prompts execute ordered steps reliably; sequencing earns code when it carries state, branching, or retries, or when a missed step fails silently. Held because no mechanization report has proposed scripting such a sequence (first live run: both mechanization reports routed simple steps to stays-with-the-model or not-worth-building); reopen and land the clause on the first report that does.

## An unowned thread worth claiming

Session `29d66917` (3.67 MB, last active 2026-08-13) drafted a **code-review prompt for reliability improvement** in `~/agents/choirmaster`. No live session, no handoff, mentioned nowhere else — and plainly this seat's subject. Its transcript is `~/.claude/projects/-home-nedlern-agents-choirmaster/29d66917-9767-47cb-a221-d4876d8014cd.jsonl`. Read it before starting any code-review-prompt work; that wheel is partly built. (Noted, not claimed — walk-order item 5.)

## The user's standing bar for reviewers

From the 2026-08-10 walk: *"asking to simplify is like asking to optimize without context."* State the axis. This project's axis is **simple-to-operate over simple-to-build; mechanical guarantees over trained habit; a detector with no consumer is cost without value; never trade a deterministic script for probabilistic agent behavior.**

## Walk order (opened 2026-08-16, doctrine-queue-drain seat — operationalizing the proven attack-split shape; the four-finding triage closed via PR #77)

1. Purpose: finish the sanity-checker — record the ruled shape, make it runnable, close this brief's open items. Nothing settled is reopened.
   *processed 2026-08-17 → accepted (purpose item; no capture).*
2. Record the standing ruling: a separate instrument, never a grid cell — three stance attacks in separate contexts, both runtimes, manual call after md-review; evidence the attack-split scorecard.
   *processed 2026-08-17 → accepted: the standing rule confirmed as stated (separate instrument, never a grid cell; three stance attacks in fresh contexts; both runtimes; manual call after md-review on work-directing MDs only; requester triages, the user rules on every applied change; unsplit form retired). One clause open: the effort tier — xhigh vs max, per runtime, decided by the running probe (cut attack at max on the gatekeeper ground truth, scored against S1–S9; headline question whether max finds S5; the user established codex has a max tier by direct test). Capture: this mark now; the runner and its commit at item 3's landing.*
3. Operational home: recover the experiment runner from git history and adapt it as the standing runner; the three attack prompts graduate from docs/drafts/ to a durable home.
   *processed 2026-08-17 → accepted with two user amendments folded (records to the instrument's own sanity-check-records/ directory, not md-review-records/; effort tier xhigh confirmed for both runtimes by the max probe — item 2's open clause closed by the same ruling). Built and committed at 1250104: scripts/sanity-check-attacks.py; prompts promoted to docs/agents/ with STANDING headers; sanity-check-records/ gitignored with the house disposal rule.*
4. Disposal: the three attack-prompt drafts and the prompt draft leave docs/drafts/ once homed, settled header rulings re-homed first (the ruled disposal).
   *processed 2026-08-18 → done: the attack-prompt drafts left at promotion (commit 1250104); the parent draft's two orphan rules re-homed into the runner docstring (md-review-first with reason; never-automatic with the suggestion-note rule), then the draft deleted via git rm — its path's git history is the decision trail, as the prompt headers state. The orphaned source file docs/drafts/simplification-review-codex-naming-notes.jsonl deleted under the same disposal (its only citing document was that draft).*
5. This brief rewritten to its post-decision state (triage done, decision ruled, deleted-record citations replaced); the unowned code-review-prompt thread noted, not claimed.
   *processed 2026-08-18 → done: this file is the rewrite (user-ruled shape; the pre-rewrite text is this path's git history).*
6. First live run: target and staffing (the seat is blank; the instrument runs from any seat).
   *processed 2026-08-18 → RULED: first targets are the instrument's own three prompts — three runs, each prompt as target with its siblings as context, fresh-eyes statements authored per the requester section; run from this seat, after the owed grid re-review and its findings walk. WALK CLOSED 2026-08-18: all six items processed; captures in this brief, the three prompts, the runner, and the md-review dispositions anchor.*

## First action

Run the owed re-review — the md-review grid over each of the three audit prompts — and walk its findings. Then bring walk-order item 6, the first live run's target and staffing, to the user.
