# What `/code-review xhigh` Does

**Subject:** the `xhigh` effort level of Claude Code's built-in `/code-review` slash command.

**Why this document exists:** the built-in `/code-review` is not a script or a `SKILL.md` file — it is a
prompt template compiled into the Claude Code binary, with no published source. This document explains, in
ordinary software-development terms, what the `xhigh` level actually orchestrates, so it can be evaluated
and compared against other review tooling without reverse-engineering the binary again.

**Source:** reconstructed from `/opt/homebrew/Caskroom/claude-code@latest/2.1.235/claude`
(Claude Code 2.1.235, macOS arm64) on 2026-08-21. Behavior may change between releases.

---

## The stance it takes

Of the five local effort levels (`low`, `medium`, `high`, `xhigh`, `max`), `xhigh` is a **recall-oriented**
review: its instruction is to catch every real defect, explicitly accepting that some findings will be false
positives. The reasoning given in the prompt is that a missed bug ships. This is the opposite posture from
`medium`, which optimizes for precision — surface only what a maintainer would definitely act on.

**`xhigh` and `max` are identical.** Both are produced by the same generator function. The only difference is
the word used in the prompt text — "extra-high" versus "maximum". Same ten reviewers, same candidate budget,
same verification, same sweep, same output cap. There is nothing to choose between them.

---

## Stage 0 — Establish the review scope

Determine the set of changes under review by running `git diff` against the upstream tracking branch, falling
back to `main` or the previous commit if there is no upstream. If there are uncommitted working-tree changes,
or if the committed range comes back empty, the working tree is also diffed and included — because a review is
usually run *before* committing. If a pull request number, branch name, or file path was passed as an
argument, that becomes the scope instead.

## Stage 1 — Ten independent reviewers, run in parallel

Ten subagents launch concurrently, each given the change set and exactly one review lens. Each returns up to
eight candidate defects, with a file, a line number, a one-sentence summary, and a concrete failure scenario —
the specific inputs or state that produce the wrong behavior. The ceiling is therefore 80 candidates.

### Five lenses looking for correctness defects

1. **Line-by-line scan** — read every changed block, then read the whole enclosing function, because a defect
   on an unchanged line of a function you touched is in scope. Looking for inverted conditions, off-by-one
   errors, dereferencing a value that can be absent, missing `await` on async calls, treating zero as missing,
   copy-paste that references the wrong variable, exceptions swallowed in a catch block.
2. **Removed-behavior audit** — for every line the change *deletes*, name the rule or guarantee that line
   enforced, then find where the new code re-establishes it. If it does not, that is a candidate: a dropped
   validation, a removed guard, a deleted test that covered a real case.
3. **Cross-file impact trace** — for each function whose signature or behavior changed, find its callers and
   check whether the change breaks them: a new precondition, a different return shape, a new exception, a new
   ordering dependency. Callees are checked too.
4. **Language and framework pitfalls** — the classic footguns of the language the change is written in, plus
   injection risks, timezone and daylight-saving drift, and floating-point equality.
5. **Wrapper and proxy correctness** — when the change adds or modifies a caching layer, proxy, decorator, or
   adapter, verify every method delegates to the wrapped object rather than re-entering through a global
   registry or session (which causes infinite recursion or cache re-entry), and that it forwards every method
   callers actually use.

### Five lenses looking for maintainability rather than defects

6. **Duplication** — new code that reimplements an existing shared helper. The reviewer must name the helper
   to call instead.
7. **Unnecessary complexity** — derivable state stored redundantly, near-duplicate code, deep nesting, dead
   code left behind.
8. **Wasted work** — repeated computation or I/O, independent operations run sequentially that could run
   concurrently, blocking work added to startup or hot paths, and long-lived objects built from closures that
   pin their entire enclosing scope in memory.
9. **Fix depth** — whether each change is made at the right architectural level or is a band-aid. Special
   cases piled onto shared infrastructure signal the fix is not deep enough.
10. **Project conventions** — read the `CLAUDE.md` files governing the changed files and flag violations, but
    only where the exact rule and the exact offending line can both be quoted.

### Two anti-suppression rules

- Reviewers must not let one lens's conclusion override another's. If two lenses flag the same line for
  different reasons, both are recorded.
- Reviewers must pass through any candidate with a nameable failure scenario rather than self-censoring. The
  prompt identifies silent dropping at this stage as the single biggest cause of missed bugs.

## Stage 2 — Deduplicate, then verify each candidate independently

Candidates pointing at the same line and mechanism are merged, keeping whichever has the most concrete failure
scenario. Every surviving candidate then goes to its own fresh verifier subagent, which sees the change set,
the relevant files, and that one candidate, and returns exactly one of three verdicts:

| Verdict | Meaning |
| --- | --- |
| **Confirmed** | Can name the inputs or state that trigger it and the resulting wrong output or crash, quoting the line. |
| **Plausible** | The mechanism is real but the trigger is uncertain (timing, environment, configuration). States what would confirm it. |
| **Refuted** | Factually wrong, provably impossible, already guarded elsewhere in this change, or pure style with no observable effect. Must quote the line that proves it. |

At this level a single non-refuted verdict is enough to carry a finding through. Uncertainty is not grounds
for dropping it.

## Stage 3 — Gap sweep

One additional reviewer runs last, given the verified list, with a single job: find defects *not already on
it*. It is told not to re-derive or re-confirm anything already present, and to focus on categories the first
pass characteristically misses:

- code that was moved or extracted and lost a guard along the way
- second-tier language footguns — a default value evaluated once at definition time, non-deterministic
  hashing, a lock's scope accidentally narrowed, predicate methods with hidden side effects
- setup and teardown asymmetry in tests
- configuration defaults that got flipped

Up to eight more candidates. If it finds nothing it returns empty; it is explicitly told not to pad.

## Output

Findings are ranked most-severe first and capped at 15. Correctness defects always outrank maintainability
findings when that cap forces a cut. Each finding carries the file, line, a one-sentence summary, a short
label under 60 characters, the concrete failure scenario, a category, and the verification verdict. If nothing
survives verification, an empty result is returned rather than manufactured findings.

## Fallback when subagents are unavailable

There is a separate path for contexts where parallel subagents cannot be launched. All ten lenses run
sequentially in a single context with no independent verification step, and the summary is required to state
that the full fan-out did not run — so nobody misreads a single-pass review as the real thing.

## Rough cost

Ten finders, plus one verifier per deduplicated candidate, plus one sweeper: roughly 20–40 subagent
invocations on a typical change set. That is the trade being made for recall.

---

## How the neighbouring levels differ

| Level | Reviewers | Candidates each | Verification | Cap |
| --- | --- | --- | --- | --- |
| `low` | none — two turns, one diff read, defects visible in the changed block alone | — | none | 4 or 8 |
| `medium` | 8 (drops language-pitfalls and wrapper/proxy) | 6 | 1 verifier, precision-biased | 8 |
| `high` | 8 | 6 | 1 verifier, recall-biased | 10 |
| `xhigh` | 10 | 8 | 1 verifier + gap sweep | 15 |
| `max` | identical to `xhigh` | 8 | identical to `xhigh` | 15 |
| `ultra` | dispatches to the cloud multi-agent review instead of running locally | — | — | — |
