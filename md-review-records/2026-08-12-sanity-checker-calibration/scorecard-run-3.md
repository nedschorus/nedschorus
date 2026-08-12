# Sanity-checker calibration, run 3 — scorecard against the S1–S9 rulings

Same protocol and inputs as runs 1–2; the prompt now also carries the replacement test on the leanness certification (ruled 2026-08-12). Full report: `claude-calibration-run-3.md` in this directory.

## Per-ruling results

| Ruling | User's disposition | Run 3 result | Verdict |
|---|---|---|---|
| S1 cut the slice-4 worker machinery | rejected | Certified under the roadmap rule; the trigger overlap "raised as an observation, not a finding" | **PASS** |
| S2 manual deploy instead of self-update | rejected | Not proposed | **PASS** |
| S3 delete the trailer-absence audit | accepted | **F1 — surfaced as a Delete finding**, three quoted grounds (dead trigger; the tripwire's escalation target already admitted; C2/C3 remove the detection class), collisions flagged, blind spot named in LOST, interim-keep offered honestly | **HIT** (discovered) |
| S4 retire the C-bindings doc | accepted | F2 — surfaced | **HIT** (discovered) |
| S5 delete the `imports` subcommand | accepted | Certified again ("`imports` derives its table from trailers") — the replacement test was not pressed to "one `git log --grep` is the view" | **MISS** |
| S6 drop `--issue` | rejected | Kept, citing the precedent | **PASS** (taught) |
| S7 absorb `--base` | accepted | F3 — surfaced, collision flagged; the reviewer even suspected it might be re-deriving an applied ruling and told triage to check | **HIT** (taught) |
| S8 C7 refusals to zero | accepted | Certified ("the minimal answer to a real privilege surface") — replacement test not applied against the token's scope | **MISS** |
| S9 collapse the refusal catalog; delete dead `empty-change` | accepted | F6 again adds catalog entries for completeness; unreachability not caught | **MISS** |

## Totals and trajectory

Rejected cuts: 3/3, third consecutive run — zero false positives across all three runs. Accepted cuts surfaced: run 1 → 2/6, run 2 → 2/6, run 3 → **3/6** (S3 landed; each ruled fix moved the item it targeted).

Notable: the replacement test was applied in good faith where the reviewer thought to (the digest got a genuine git-commit-hash comparison, considered and correctly rejected) but not pressed against small built conveniences (imports, C7's refusals, catalog granularity) — the persistent misses are now the three smallest, least consequential of the six accepted cuts.

## Status

Run 3 scored. User ruling 2026-08-12: **accepted** — three clean runs on the rejected cuts, all deep cuts surfacing, the residual miss class (S5/S8/S9, the three smallest cuts) costs thoroughness not safety, and perfection is not the goal. The protocol's second-document run proceeds against the live `docs/cross-project/fast-handoff-design.md` (no ruled ground truth exists there; the user's triage of its findings is the judgment).
