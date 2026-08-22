# Built-in /code-review — reconstructed from the binary
Source: strings of /opt/homebrew/Caskroom/claude-code@latest/2.1.235/claude (Claude Code 2.1.235)
Not published as source. Minified identifiers noted so the extraction can be re-run.

## Argument parsing  (function Ffs)
  flags parsed by DOg(e, ["comment","fix","post","no-post"])
  first token may be a level (low|medium|high|xhigh|max) or the literal `ultra`
  remainder = target (PR number / branch / path)
  full argumentHint (CIE): [low|medium|high|xhigh|max|ultra] [--fix] [--comment] [<pr#>|<branch>|<path>]

## Level persistence
  TIE() reads config key `codeReviewLastEffort`; wIE() writes it.
  With no level typed, the last level you used is reused.

## Shared Phase 0 (constant f8e — same block /simplify uses)
Run `git diff @{upstream}...HEAD` (or `git diff main...HEAD` / `git diff HEAD~1`
if there's no upstream). If there are uncommitted changes, or the range diff is
empty, also run `git diff HEAD` — the review often runs before the commit. If a
PR number, branch name, or file path was passed as an argument, review that
target instead.

## The angle library (shared constants)

CORRECTNESS
### Angle A — line-by-line diff scan          (ZxE)
  Read every hunk line by line, then Read the enclosing function — bugs in
  unchanged lines of a touched function are in scope. Inverted/wrong conditions,
  off-by-one, null deref, missing `await`, falsy-zero, wrong-variable copy-paste,
  error swallowed in catch, unescaped regex metachars.
### Angle B — removed-behavior auditor        (QxE)
  For every DELETED/replaced line, name the invariant it enforced, then find
  where the new code re-establishes it. If you can't: candidate.
### Angle C — cross-file tracer               (eIE)
  Grep callers of each changed function; check for new preconditions, changed
  return shape, new exceptions, ordering dependencies. Also check callees.
### Angle D — language-pitfall specialist     (tIE)   [xhigh/max only]
  JS falsy-zero / `==` coercion / closure-captured loop var; Python mutable
  default args, late-binding closures; Go nil-map write, range-var capture;
  SQL injection; timezone/DST; float equality.
### Angle E — wrapper/proxy correctness       (rIE)   [xhigh/max only]
  Cache/proxy/decorator/adapter types: does every method route to the wrapped
  instance rather than back through a registry/session/global (re-entrancy or
  recursion)? Does the wrapper forward every method callers use?

CLEANUP (identical text to /simplify's four angles)
### Reuse (NOG/Nvo) / ### Simplification (S0t) / ### Efficiency (v0t) / ### Altitude (T0t)
### Conventions (CLAUDE.md)                   (wfn)   [code-review only, not /simplify]
  Find the CLAUDE.md files governing the changed code (~/.claude/CLAUDE.md,
  repo root, and any CLAUDE.md/CLAUDE.local.md in an ancestor dir of a changed
  file). Flag a violation only when you can quote the exact rule and the exact
  line that breaks it. Name the CLAUDE.md path and quote the rule.

## Level → shape

low     (jOg / zOg / JOg — three A/B-tested variants; see `code-review-low-fast`)
        `low effort → 1 diff pass → no verify → ≤4 findings`
        Two turns. Turn 1: one tool call reads the diff. Turn 2: flag only bugs
        visible from the hunk alone. No subagents, no full-file reads. Some
        variants skip test/fixture hunks; some set a floor of min(files,4).
        Cap ≤4 or ≤8 depending on variant.

medium  (qOg)  `medium effort → 3+5 angles × 6 candidates → 1-vote verify → ≤8 findings`
        Lead-in: "reviewing for **precision** — every finding should be one a
        maintainer would act on."
        Phase 1: 8 finder angles (A,B,C + Reuse, Simplification, Efficiency,
        Altitude, Conventions) via the Agent tool, ≤6 candidates each.
        Phase 2 (FOg): dedup, then ONE verifier per candidate returning
        CONFIRMED / PLAUSIBLE / REFUTED. Keep CONFIRMED + PLAUSIBLE.

high    (WOg)  `high effort → 3+5 angles × 6 candidates → 1-vote verify (recall-biased) → ≤10`
        Same 8 angles. Lead-in flips to **recall**: "catching real bugs matters
        more than avoiding false positives. Err on the side of surfacing."
        Phase 2 (sIE) uses the recall-biased verifier rubric (iIE):
        PLAUSIBLE by default — do not refute for being "speculative" when the
        state is realistic (races, rare-but-reachable nil, falsy-zero,
        off-by-one, retry storms, unanchored regex). REFUTED only when
        constructible from the code.

xhigh / max  (GOg("xhigh") / GOg("max"))
        `<level> effort → 5+5 angles × 8 candidates → 1-vote verify → sweep → ≤15`
        Phase 1: 10 angles (adds D and E), ≤8 candidates each, and: "Do NOT let
        one angle's conclusions suppress another's."
        Phase 2: FOg + "a single non-REFUTED vote carries the finding."
        Phase 3 — Sweep for gaps (aIE): one more finder, given the verified
        list, hunting ONLY for what the first pass misses ($Og): moved/extracted
        code that dropped a guard, second-tier footguns (dataclass default
        evaluated once, non-deterministic hash(), lock-scope shrink, predicate
        methods with side effects), setup/teardown asymmetry, flipped config
        defaults. ≤8 more candidates. "If nothing new, return an empty sweep —
        do not pad."

ultra   Not a local prompt — dispatches to the cloud multi-agent review
        (same engine as `claude ultrareview`). --post / --no-post apply here.

## Output contract
  UOg — when ReportFindings (F7) is available: one tool call with
        {level, findings}; each entry has file, line, summary, short_summary
        (≤60 chars), failure_scenario, category (correctness | simplification |
        efficiency | reuse | altitude | conventions | e.g. test-coverage),
        plus verdict when a verify pass produced one.
  BOg — otherwise: a JSON array, and explicitly "Do not call the ReportFindings
        tool even if it is available."
  Ranked most-severe first; truncate to the cap; empty array if nothing survives.
  Wwr: "Correctness bugs always outrank cleanup, altitude, and conventions
  findings when the output cap forces a cut."

## No-Agent-tool fallback (rNc + lIE + cIE)
  Every level above medium has a single-pass inline variant used when the Agent
  tool is absent: same angles, run sequentially in-context, no subagent verify,
  and the summary must state that the fan-out did not run.
