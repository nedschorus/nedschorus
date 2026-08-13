# Sanity-checker calibration, run 2 — scorecard against the S1–S9 rulings

Same protocol and inputs as run 1 (`scorecard-run-1.md`); the prompt now carries the two fixes ruled in the run-1 walk: the log-machinery lesson on the no-consumer cut class, and the broken-mechanism-reopens-Delete rule. Report: `claude-calibration-run-2.md` in this directory.

## Per-ruling results

| Ruling | User's disposition | Run 2 result | Verdict |
|---|---|---|---|
| S1 cut the slice-4 worker machinery | rejected | Raised as "a question only," with the boss rulings noted; suggested slice 5 might build before 4 | **PASS** |
| S2 manual deploy instead of self-update | rejected | Not proposed; the self-updating copy strengthened by F4 instead | **PASS** |
| S3 delete the trailer-absence audit | accepted | F5 applied the new broken-mechanism rule, searched for dependents, found documented ones (T12, B3c outcomes, slice-5 row) → repaired (re-homed); separately flagged the audit's post-C2 demotion as "a question for the walk" | **MISS**, improved — deletion was weighed and the demotion question surfaced |
| S4 retire the C-bindings doc | accepted | F2 — surfaced | **HIT** |
| S5 delete the `imports` subcommand | accepted | Not surfaced; leanness certification praised the imports view | **MISS** |
| S6 drop `--issue` | rejected | Kept, citing the precedent | **PASS** (taught) |
| S7 absorb `--base` | accepted | F7 — surfaced with an override retained, walked-core collision flagged | **HIT** (taught) |
| S8 C7 refusals to zero | accepted | Not surfaced; C4–C7 certified lean | **MISS** |
| S9 collapse the refusal catalog; delete dead `empty-change` | accepted | Not surfaced; catalog certified ("no guard whose failure cannot occur") | **MISS** |

## Totals

Rejected cuts 3/3 (held). Accepted cuts surfaced 2/6 (unchanged from run 1), with S3 materially closer.

## Qualitative movement run 1 → run 2

- Two more independent rediscoveries of post-snapshot rulings, on top of run 1's advisory fix: F4 item (1) demands the sudoers rule point at an installed copy unwritable by agents — the root-owned-copy ruling of 2026-08-10; F3's idempotent-status argument anticipates the 30-day expiry sweep ruled 2026-08-10. The prompt reliably finds true things.
- F6 is a new, well-argued Encode finding (derive the `Gatekeeper-agent` model from the origin transcript; collision with B6/D3 flagged) — the prompts-to-code hunt now closes with a target state: "no fact reaches the gate by agent recall; only judgment does."
- The persistent miss class is now precise: S5, S8, S9 all fail the same way — built machinery presented by the document as purposeful (a subcommand, named refusals, catalog entries) gets certified lean rather than questioned. The broken-mechanism rule fires only when something is visibly broken; these three were intact, just not worth their weight. The reviewer trusts the document's own account of intact machinery's value.

## Status

Run 2 scored. Options pending the user's ruling: iterate again on the intact-but-unearned miss class; or accept the current state (per his standing note that perfection is unreachable) and proceed to the protocol's second document; or stop here.
