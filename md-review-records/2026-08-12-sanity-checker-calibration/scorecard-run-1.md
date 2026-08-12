# Sanity-checker calibration, run 1 — scorecard against the S1–S9 rulings

Protocol: `md-review-records/2026-08-09-git-gatekeeper-design/subtract-cell-prompt-lessons.md` § Calibration protocol before any grid seat. The settled sanity-checker prompt (post-md-review revision of `docs/drafts/sanity-checker-prompt-draft.md`, 2026-08-12) reviewed the pre-walk gatekeeper spec (commit `0890848`) with its three linked documents as context; the reviewer had no access to the S rulings. Report: `claude-calibration-run-1.md` in this directory. Ground truth: Group S in `md-review-records/2026-08-09-git-gatekeeper-design/dispositions.md`.

Contamination note: the prompt's two worked examples ARE S7 (`--base`, accepted) and S6 (`--issue`, rejected) from this very spec — those two score as taught, not discovered.

## Pass bar (from the protocol)

The six accepted cuts should surface; the three rejected cuts should either not surface or surface with their trade stated honestly.

## Per-ruling results

| Ruling | User's disposition | Run 1 result | Verdict |
|---|---|---|---|
| S1 cut the slice-4 worker machinery | rejected (slow checks are planned) | Surfaced in the "A better way" hunt as "a question, not a deletion," explicitly flagged as colliding with the boss-walked core and cancel ruling | **PASS** — exemplary handling |
| S2 manual `sudo cp` deploy instead of self-update | rejected (operator cost) | Not proposed | **PASS** |
| S3 delete the trailer-absence audit | accepted (detector with no consumer; log-consuming machinery is the cost) | Found the audit's dead trigger ("at each handoff scrub" names retired machinery) but proposed re-homing the trigger and splitting the audit sentence (F5) — repair, not deletion | **MISS** (territory found, opposite remedy) |
| S4 retire the C-bindings doc; dedupe spec↔slice-plan | accepted | F2 proposes exactly the C-doc retirement as a duplicated-normative-homes cut; the spec↔slice-plan section dedup half not surfaced | **HIT** (main part; genuine discovery, untaught) |
| S5 delete the `imports` subcommand | accepted (the trailer plus `git log --grep` is the view) | Not surfaced; the leanness certification cites "import → the `imports` derived view" as the trailer's consumer, blessing the redundant reader | **MISS** |
| S6 drop `--issue` | rejected (forcing function) | Kept, citing the forced-answer precedent | **PASS** (taught by the worked example) |
| S7 absorb `--base` into the program | accepted | F4, a full Encode finding grounded in the spec's own C6 text, with the walked-core collision flagged | **HIT** (taught by the worked example) |
| S8 C7's privileged refusals shrink to zero | accepted (guards that guard nothing; token scope is the guard) | Not surfaced; F6 goes the other way — asks to give the C7 refusal a catalog name | **MISS** (opposite direction) |
| S9 collapse the refusal catalog (~19→~10); delete dead `empty-change` | accepted | Not surfaced; F6 adds three catalog entries; `empty-change` unreachability not caught | **MISS** (opposite direction) |

## Totals and verdict

Rejected cuts: 3/3 handled correctly (the first run's entire failure class — S1, S2, S6 all proposed badly there — is eliminated). Accepted cuts surfaced: 2/6, one of them taught. **Run 1 does not meet the pass bar.**

## Diagnosis

The prompt's discipline rules work: no bad cut was proposed, collisions were flagged rather than dodged, quoted grounds were delivered throughout. The failure is one-sided — under-subtraction. All four misses are deletions of existing machinery that the reviewer instead defended (S5's redundant reader cited as a consumer; S8's refusals treated as legitimate) or repaired (S3's dead-triggered audit re-homed; S9's catalog extended). Two levers absent from the prompt that the S rulings used:

1. "Logging is cheap; log-consuming machinery is the cost" (the user's S3/S-headnote lesson) appears nowhere — the reviewer weighed detectors by whether a consumer could exist, not by whether consuming machinery is worth building.
2. Nothing tells the reviewer that when a mechanism is found broken or unanchored (dead trigger, unnamed refusal, unreachable code path), deletion is the first candidate and repair the second — F5 and F6 both repaired where the rulings deleted.

Novel findings beyond the ground truth, for what they show about the prompt's strengths: the sudo environment-stripping catch (origin silently `none` forever — a real latent defect the S walk never saw), the advisory-vs-only-read contradiction (F7), the read-once `status` non-idempotency (F1, correctly flagged against B4d), and the dead resolved sections (F3).

## Status

Run 1 scored; prompt iteration and rerun pending the user's rulings. The protocol requires a second document after a passing run, before any grid-seat proposal.

## Walk order

Walk of these results and the proposed fixes, opened 2026-08-12; dispositions marked here per item.

1. Purpose: what this walk decides and the bar — processed 2026-08-12 → accepted
2. Result, good half: the rejected cuts — 3/3 handled correctly — processed 2026-08-12 → accepted, with the user's standing note: perfection is not the goal — it is unreachable; the pass bar is a target for tuning, not a demand for 9/9
3. Result, bad half: the accepted cuts — 2/6 surfaced — processed 2026-08-12 → accepted
4. The four misses share one shape: defended or repaired instead of cut
5. Proposed fix 1: add the log-machinery lesson to the prompt — processed 2026-08-12 → accepted as revised in discussion: the lesson plus the not-ignoring clause (problem handled elsewhere, or the blind spot named in LOST) added to the no-consumer cut class
6. Proposed fix 2: deletion-before-repair rule
7. The findings beyond the ground truth (informational)
8. Next step: rerun, then the second document
