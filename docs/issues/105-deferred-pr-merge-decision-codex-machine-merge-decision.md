---
issue: "[Deferred: pr-merge-decision-codex — machine merge-decision review; revisit after code-review-codex-cell accrues lane experience](https://github.com/nedschorus/nedschorus/issues/105)"
---

# Deferred: pr-merge-decision-codex — machine merge-decision review; revisit after code-review-codex-cell accrues lane experience

Deferred component of the merge lane's review tooling, deferred by the user's ruling 2026-08-19. This issue is the tracker for that deferral; nothing is being built under it yet.

## What it is

A script, working name `pr-merge-decision-codex.py`, wrapping a plain `codex exec` call: given a pull request's base/head SHAs, its title and body, and independently gathered test evidence, it returns a machine-readable MERGE / DO_NOT_MERGE / INDETERMINATE verdict with findings. It covers the checks a pure code review does not: the body describes what the diff actually does; new tests fail without the fix; the change is one topic; changed prose claims about code are true; nothing contradicts documents on main.

## Why it is deferred, not rejected

Ruled 2026-08-19: build the small proven piece now (`code-review-codex-cell.py`, a thin wrapper over `codex exec review` — see the PR that lands it), defer this one. Reasons: it carries real design surface (output schema, evidence gathering, verdict semantics, trusted-base policy), which is the shape that overgrew twice that same day elsewhere in the project; and the checks it automates were being done by hand successfully, so the need for automation was asserted rather than demonstrated.

**Revisit trigger:** after `code-review-codex-cell.py` has been used across enough merges to show what the hand-run merge-decision checks miss or cost. Whoever reopens this then writes the design first.

## Design facts already established (verified against codex-cli 0.147.0, 2026-08-19)

- `codex exec review`'s `[PROMPT]` is mutually exclusive with `--base`/`--commit`/`--uncommitted` — custom merge-decision instructions therefore need plain `codex exec`, consuming the code review's output rather than replacing it.
- The CLI exit code is operational, not a verdict: exit 0 with P2 findings observed. A gate must parse the output artifact.
- `--output-schema` composes with `codex exec review` for structured findings.
- A PR head's `AGENTS.md` is candidate-controlled instruction surface; gate policy must come from the trusted base.
- Test counterfactuals ("does the new test fail without the fix") should be run mechanically in checkouts, not judged by the model.

## Outcome

Closed as not planned on 2026-09-30, by the user's "y" to item 5 of the walk eight-deferrals-with-no-trigger-2026-09-29, which took eight deferred issues whose revisit triggers nothing was watching (minutes: `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/eight-deferrals-with-no-trigger-2026-09-29-minutes.md`).

**The revisit trigger fired.** The Codex code-review cell has run on dozens of merges: merge-lane-2's merge reviews quote the Codex review cell's verdict on 38 pull requests merged between 2026-09-28 and 2026-09-30 alone.

**The one miss found is a miss this design would repeat.** PR [A recovered seat's supervisor runs from the reference clone, not from the checkout the recovery ran from](https://github.com/nedschorus/nedschorus/pull/778) merged with three new test cases that failed against the old program only because the old program had no `--checkout` option: the old program exited 2 on the unknown argument before launching anything. So failing first never showed the old bug. The merge-decision check "new tests fail without the fix" passed, because the merge lane checked that the tests failed, not why they failed. This issue's own design runs that same check mechanically — the design fact above, "Test counterfactuals ... should be run mechanically in checkouts, not judged by the model" — so building this script would not have caught that miss.

**Where the lesson lives instead.** The question that catches such a miss is why a test fails, not only whether the test fails. That question is a worked example in GHI [Build the design-to-main state machine: the Python machine, its per-state agent-instructions, and the nine items the design defers to the build](https://github.com/nedschorus/nedschorus/issues/282), section "Two test defects from 2026-09-29, as worked examples for the test-writing and test-review drafts", item 2, which carries the full case for that build's test reviewer.

**What this outcome does not settle.** The walk ruled on the test check alone. Nobody measured what the hand-run checks cost, and whether any of the other four checks this design covers (the body matches the diff, one topic, prose claims about code are true, nothing contradicts main) needs a machine is not decided here. Whoever wants one of them automated files a new issue for that check.

## Related, not the same matter

- GHI [main-gatekeeper — the single check-in gate (design: nc-systems/main-gatekeeper/main-gatekeeper-design.md)](https://github.com/nedschorus/nedschorus/issues/3) — the git-gatekeeper is this component's eventual consumer: the gate that can review, or refuse, what passes through it.
- GHI [run-agent: one CLI to invoke a Claude or Codex agent headlessly from any caller (Python, shell, either runtime)](https://github.com/nedschorus/nedschorus/issues/41) — run-agent, the headless invocation layer this could ride on.

Search receipt for filing new rather than amending: `gh issue list --state all --limit 100 --search "review"` and `--search "codex"` (2026-08-19) returned no issue covering a machine merge-decision or Codex PR-review component; GHI [nedsmessenger is deferred until nedschorus can build it; where its early context lives](https://github.com/nedschorus/nedschorus/issues/80) is the precedent shape for deferral issues.
