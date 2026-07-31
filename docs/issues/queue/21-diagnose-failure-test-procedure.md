# Boss-walked core for pair #21 (diagnose-failure) — the test-failure procedure

Queued for the boss's drain (promote / edit / demote / drop). Boss-walked 2026-07-31 (superpowers-extracts walk, item 3 discussion); sources: the boss's two-scenario framing and cluster rule, the daemon incident, the superpowers `verification-before-completion` extract, and the ruled agent-loop ladder. Destination: [nedschorus#21](https://github.com/nedschorus/nedschorus/issues/21).

## The cluster rule (boss, 2026-07-31)

Most reproduction rates are 0%, 1%, 99%, or 100% — and which one is unknowable in advance. Two reruns therefore separate the clusters about as well as twenty. Rate is not a property of the bug: bugs are deterministic functions of input, state, schedule, and environment; "flaky" means the triggering condition is not in the controlled set. **"Repros aren't random, they are just subtle."**

## The fork procedure (test-detected failures)

1. **Red observed → rerun ×2.**
   - Both red → deterministic; proceed to step 2.
   - One of each → the middle is subtle: further sampling cannot FIND the hidden variable — stop sampling and start differencing. Capture one failing and one passing run fully (trace, environment, state snapshots) and diff them; the hidden variable is in that diff — a mechanical, patience-free job suited to agents. Control the variable; the bug promotes to ~100% and re-enters at step 2.
   - If honest differencing fails to locate the variable: escalate BLOCKED with the paired evidence package — one failing and one passing run, traces, environment, and state snapshots attached. If the boss rules the fix ships anyway, the weak-evidence path below applies, recorded as a named residual.
2. **Causal hypothesis with discriminating evidence — before the first fix.** Obvious cause → fix directly. Cause not obvious → debugger/trace *now*, not after a failed fix; a fix without an evidenced hypothesis spends a breaker round on a guess.
3. **Fix, with the reach proof**: the failing run must be shown to execute the code being changed (the daemon guard, below).
4. **Green → revert the fix → red returns → restore → green.** The revert-red step proves the fix — not environment drift, leftover state, or luck — produced the green (the bidirectional witness; scope: applies where a repro exists, at the fidelity category it honestly earned — minimal / partial / not-reproduced).
5. **A round that never reaches green** is a failed round: record theory, action, result (R1); root-cause analysis required at R2; breaker trips at R3 per the agent-loop ladder.

**Verification under residual nondeterminism:** if the failure resists determinization, rep-based confidence rests on a stationarity assumption the hidden variable defeats — N clean runs across varied environments is recorded as weak evidence with a named residual; it is never the witness.

## The daemon specimen (environment-verdict class)

Agents repeatedly "fixed" daemon code, never succeeding, because the running process was never reloaded — the code being edited was not the code executing. Three ruled mechanisms independently catch it: the breaker (red-stays-red trips at 3, and the widened frame includes environment); the environment/instrument verdicts; and sharpest, **the reach proof applied to the fix itself** — one probe showing "changed line never executed" reveals the stale process on attempt one. Aftermath belongs to the interrogation loop: one boot-context line ("after editing daemon code, reload the daemon") corrects every future agent.

## Debugger-first diagnosis (boss, 2026-07-31)

Agents can do what humans lack patience for: use debugger/attach instruments instead of logging to trace back up the actual execution — no edit, no rerun, no reload. This is also structurally safer than logging in the hard cases: log-based debugging requires editing code and reloading — the exact step that silently failed in the daemon incident — while an attached instrument can only show the code that is actually executing. Mechanics vary by situation (`py-spy dump` snapshots a live process non-invasively; `debugpy`/`pdb` want the process launched under them): the doctrine is *prefer trace/attach instruments over edit-and-rerun instruments for diagnosis*, tool chosen per case.

## Production-class failures and the system-understanding gap

Hard-to-repro production failures are diagnosed by instrumentation up the chain from the visible failure point — agent-duplicable (boundary instrumentation + the differencing above). The genuinely hard class (boss): design flaws, and one agent's failure to understand the large system around the code it sees. Status of countermeasures, stated precisely (new-vp flank correction, 2026-07-31): **one ruled countermeasure exists** — the broad-expert half of the reset pair, whose job is carrying the surrounding-system picture. The *doctrine* that explanatory architecture description is regenerated from code on demand and never carries authority is boss-ruled (queue note §6a item 1(b), 2026-07-29), but **no view-generation machinery or practice exists or is ruled** — "current architecture view on request" goes on the table as a candidate instance of that doctrine, not as existing machinery.
