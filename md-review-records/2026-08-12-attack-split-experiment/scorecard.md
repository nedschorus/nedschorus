<!-- provenance: scoring of the attack-split validation experiment (grid-seat rulings, user-walked 2026-08-12) — 3 stance attacks x 2 runtimes (claude-fable-5, gpt-5.6-sol, both xhigh) x 2 archived ground-truth documents; scored by the requesting agent (session 49e0a3cf) against the S1-S9 rulings (md-review-records/2026-08-12-sanity-checker-calibration/) and the seven fast-handoff rulings (md-review-records/2026-08-12-fast-handoff-sanity-check/dispositions.md); cell reports in this directory -->

# Attack-split experiment scorecard

The question: does splitting the calibrated sanity-checker prompt into three stance attacks (cut, mechanization, fresh-eyes), run on both runtimes in parallel, beat the unsplit prompt? The unsplit baseline: best calibration run 3/6 accepted cuts surfaced, 3/3 rejected cuts clean (gatekeeper); 7/7 findings accepted on fast-handoff.

## Gatekeeper document — union vs the S1–S9 record

| Ruling | Disposition | Attack cells | Result |
|---|---|---|---|
| S1 slice-4 cut | rejected | cut-claude refuted it explicitly; cut-codex certified async lifecycle under the roadmap rule | PASS both |
| S2 manual deploy | rejected | proposed by neither | PASS both |
| S3 trailer-absence audit | accepted | cut-claude (3 grounds incl. a novel one: the scan flags the whole founding history without epoch machinery); cut-codex; mech cells re-anchor the trigger | HIT, richer than baseline |
| S4 retire bindings doc | accepted | cut-claude (as an honestly-bounded question) | HIT (claude only) |
| S5 `imports` cut | accepted | missed by all; cut-codex actively certified it | MISS — the universal blind spot |
| S6 `--issue` cut | rejected | kept by all; mech-codex and cut-codex each independently rejected adjacent candidates | PASS both |
| S7 `--base` absorb | accepted (applied) | mech cells correctly recognized it as already applied; mech-codex proposes the deeper program-side form | COVERED |
| S8 C7 test-seam refusals | accepted | cut-codex: delete the seams, dissolving C7 — deeper than the ruled form | HIT (codex only, first ever) |
| S9 catalog collapse / `empty-change` | accepted | cut-codex: `empty-change` redundant with `unchanged-path` | HIT (codex only, first ever) |

**Union: 4 of 5 in-band accepted cuts surfaced (baseline best: 3 of 6), zero unflagged false positives, and each runtime found accepted cuts the other missed.** One probable false positive by later ruling: cut-codex proposes deleting the branch-protection audit, which the 2026-08-12 ruling kept and re-anchored — collision flagged in the report. cut-claude matched the actual ruling ("the branch-protection audit is the keeper"). Both mechanization cells independently derived the audit-anchored-to-recycle fix — the ruling the user made in the git-gatekeeper walk, unseen by the cells.

*Correction 2026-08-15: the headline ratio mixes denominators. The split's `4 of 5` drops S7 from its denominator (scored COVERED — already applied), while the baseline's `3 of 6` keeps S7 in. Counted like-for-like over the six accepted cuts, the split surfaced 4 of 6 — 5 of 6 if COVERED counts as surfaced — against the baseline's 3 of 6. The direction of the comparison is unchanged. The same reading applies to the verdict's `4/5 vs 3/6` below.*

## Fast-handoff document — union vs the seven rulings

| Ruling | Disposition | Attack cells | Result |
|---|---|---|---|
| F1 relay cut | accepted | cut-claude and cut-codex, both choosing the ruled side; mech cells flagged the dual description | HIT ×2 |
| F2 silence gate cut | accepted | cut-claude; mech-claude (as a composed-rulings gap, with the pane-case subtlety); cut-codex MISSED it and certified the gate | HIT (claude only) |
| F3 queue-status reader | accepted as route | mech-claude proposed the exact ruled remedy (ignition prompt); cut-claude flagged for #32; cut-codex proposed the cut the user declined | HIT, remedy matched by claude |
| F4 canary duty | accepted as delete | cut-claude argued the user's side (delete, canaries as diagnostics); mech cells proposed mechanize (the declined alternative) | HIT, ruled side by cut-claude |
| F5 stale Tests section | accepted (class) | cut-claude (inside its F6: the suite tests the override, not the floor) | HIT |
| F6 duplicate inventories | accepted (class) | cut-claude and cut-codex, both with the drifted-name evidence | HIT ×2 |
| F7 closed holes | accepted (class) | cut-claude | HIT |

**Union: 7 of 7 (baseline: 7 of 7 — parity), plus novel findings the baseline never produced.** Weakest single cell of the experiment: cut-codex on fast-handoff (missed F2, argued against it). One cell being weak while the union holds is the shape the split design bet on.

## Novel findings beyond both ground-truth sets (walk fodder, not applied)

- **A real spec bug:** the design promises the successor "the exact handoff path to read"; the ignition prompt passes the dialog path (cut-claude).
- **Checks-never-wired:** "when a test suite exists, the tests run here" never fired although the 146-case suite exists — the gate runs no checks today (mech-codex).
- **Pin-stamp:** the writer should stamp repo + HEAD mechanically; a model-recalled 40-char SHA is a hallucination channel (mech-claude; mech-codex converged with a structured-reference variant).
- **`--agent` model half from the transcript** — derived independently by both runtimes, same D3 collision flag (mech-claude, mech-codex).
- **Idempotent provisioning command** for the C1–C4 installation checklist (mech-codex).
- **stdlib-only AST test** protecting the break-glass path (mech-claude ×gatekeeper). **Unix-boundary drift audit** (same cell). **`dont-restart` deletion or rework** (cut cells, two variants). **Pre-seed deletion** with honest kill-condition (cut-codex). **Token narrowing at activation; five-label state machine cut; explicit `--wait` cut** (cut-codex).

## Fresh-eyes yield (diffed against the real designs by triage)

Fable's gatekeeper sketch independently reinvented the ruled architecture — one deterministic program, dedicated Unix user + sudoers, checks on merged content, trailer receipts, git-only records, resubmit idempotency, protection backstop, no daemons, revert-as-remedy — the strongest architecture validation the project has. Its diff produced genuine gaps: **no gate-edits-the-gate guard** (a diff touching the gatekeeper or checks sails through the checks it weakens), **no pre-land secret scan**, **lost-reply-then-amend double-landing** (digest is content-keyed; logical-change identity is unhandled), **no flaky-check policy**, receipt-schema versioning. Sol's gatekeeper sketch chose a different architecture (GitHub-hosted, adversarial threat model) — mostly out of the ruled scope, but one transferable catch: **candidate-supplied check code executes as the credential-holding user**, a privilege channel the spec never names. Fable's fast-handoff sketch validated the transcript-usage trigger and surfaced the sharpest operational gap in the set: **a wedged-but-light session never recycles** (stalls below threshold, no watchdog), plus permission-state not surviving recycles headless, orphaned background processes, a recycle-storm loop guard, and external-identity reclaim. Sol's fast-handoff sketch was over-engineered against project taste but asked two questions worth canaries: whether summed usage fields equal real context occupancy, and the "request sent, response absent" third state for external actions around a kill.

## Operational notes

Both codex fresh-eyes cells failed at launch (codex refuses a non-repo scratch directory; fixed with --skip-git-repo-check) — caught minutes in by the per-cell monitor, invisible until batch-end under the old delivery shape: the piecemeal ruling proved itself on its first run. Fable cells returned in minutes; sol xhigh cells took tens of minutes; per-cell scoring filled the gap. Cost: one Fable + one sol run per attack per document, once.

## Verdict (recommendation to the user; the seat is his ruling)

The split with model parallelism beats the unsplit baseline on the record: strictly better coverage on the gatekeeper (4/5 vs 3/6), parity plus novel findings on fast-handoff, zero unflagged false positives across all eight judgment cells, and cross-runtime convergence/divergence data the single prompt cannot produce. The fresh-eyes attack contributed the only unknown-unknowns in the set, exactly its charter. Recommended seat shape: the three attacks × both runtimes as drafted, reconciliation walk per document, triage owning merge and code-hedge verification.
