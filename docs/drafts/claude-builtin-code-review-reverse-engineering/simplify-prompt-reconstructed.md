# /simplify — reconstructed prompt template
# Source: strings of /opt/homebrew/Caskroom/claude-code@latest/2.1.235/claude (Claude Code 2.1.235)
# Minified identifiers: EOn="simplify", fi="Agent", tDE=fan-out variant, rDE=fallback variant,
# f8e=shared Phase 0 block, Nvo/S0t/v0t/T0t = the four angle bodies (shared with /code-review).
# Not published as source anywhere; compiled into the binary.

--- PRIMARY VARIANT (tDE) — used when the Agent tool is available ---

`/simplify → 4 cleanup agents in parallel → apply the fixes`

You are improving the quality of the changed code, not hunting for bugs. Review
it for reuse, simplification, efficiency, and altitude issues, then fix what you
find. Do not look for correctness bugs — that is what `/code-review` is for.

## Phase 0 — Gather the diff

Run `git diff @{upstream}...HEAD` (or `git diff main...HEAD` / `git diff HEAD~1`
if there's no upstream) to get the unified diff under review. If there are
uncommitted changes, or the range diff is empty, also run `git diff HEAD` and
include the working-tree changes in scope — the review often runs before the
commit. If a PR number, branch name, or file path was passed as an argument,
review that target instead. Treat this diff as the review scope.

## Phase 1 — Review (4 cleanup agents in parallel)

Launch **4 independent review agents** via the Agent tool, all in a
single message so they run concurrently. Pass each agent the diff and one of
the four angles below. Each returns its findings with `file`, `line`, a
one-line `summary`, and the concrete cost (what is duplicated, wasted, or
harder to maintain).

### Reuse
Flag new code that re-implements something the codebase
already has — Grep shared/utility modules and files adjacent to the change,
and name the existing helper to call instead.

### Simplification
Flag unnecessary complexity the diff adds: redundant or derivable state,
copy-paste with slight variation, deep nesting, dead code left behind. Name
the simpler form that does the same job.

### Efficiency
Flag wasted work the diff introduces: redundant computation or repeated I/O,
independent operations run sequentially, blocking work added to startup or
hot paths. Also flag long-lived objects built from closures or captured
environments — they keep the entire enclosing scope alive for the object's
lifetime (a memory leak when that scope holds large values); prefer a
class/struct that copies only the fields it needs. Name the cheaper
alternative.

### Altitude
Check that each change is implemented at the right depth, not as a fragile
bandaid. Special cases layered on shared infrastructure are a sign the fix
isn't deep enough — prefer generalizing the underlying mechanism over adding
special cases.

## Phase 2 — Apply the fixes

Wait for all four agents to complete, dedup findings that point at the same
line or mechanism, and fix each remaining one directly. Skip any finding whose
fix would change intended behavior, require changes well outside the reviewed
diff, or that you judge to be a false positive — note the skip rather than
arguing with it. Finish with a brief summary of what was fixed and what was
skipped (or confirm the code was already clean).

--- FALLBACK VARIANT (rDE) — used when the Agent tool is NOT available ---

Same four angles and same Phase 0. Differences only:

Header:  `/simplify → Agent tool unavailable → single-pass inline cleanup → apply the fixes`

Extra paragraph after the intro:
  The Agent tool isn't available in this context, so the usual
  4-agent fan-out can't run. Work through all four angles below yourself, in
  this same context, in one pass — do not skip an angle for lack of fan-out.

Phase 1 heading: "## Phase 1 — Review (4 cleanup angles, single pass)"
  Review the diff against each angle below in turn. For each, note findings with
  `file`, `line`, a one-line `summary`, and the concrete cost (what is
  duplicated, wasted, or harder to maintain).

Phase 2 adds a final sentence:
  State clearly in your summary that this was a single-pass
  review done without the Agent tool, not the full 4-agent
  fan-out, so whoever reads it isn't misled about what actually ran.

--- ARGUMENT HANDLING ---

argumentHint: [<target>]
If an argument is given, the line  Review target: `<arg>`  is prepended to the
prompt above. No other flags (no --fix; it always applies fixes).

--- VARIANT SELECTION (function Hfs) ---

function Hfs(e){
  if(e.agentContext && Yk(e.agentContext) >= $q()) return false;   // nesting depth cap
  let t = e.options?.tools;
  if(!t) return true;
  return t.some((r)=>Qa(r,"Agent"));                                // Agent tool present?
}
