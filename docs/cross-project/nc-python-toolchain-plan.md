# NC tool-power plan — Python quality toolchain and the judgment layer (plan of record)

Walked and ratified at the boss walk, 2026-07-31; finalization review applied the same day. Sources: the toolchain phasing effort (ChatGPT source discussion → distilled brief → two independent agent decision runs → three adversarial review rounds across two model families, ~60 findings → two boss rulings) and the spec-kit read-for-ideas walk (10 items). Companion reference: [nc-python-toolchain-target-architecture.md](nc-python-toolchain-target-architecture.md) — the fully designed, review-hardened mechanism specs that the phase triggers pull from (the survey, not the road). The working notes behind this plan are machine-local and deliberately unmemorialized (an artifact needs a clear forward reason to be committed); this document and the reference are the record.

**Governing rulings (boss):**
- **Simplicity over completeness; practical over perfect.** Build the easy, certain layer first; learn from its run history; pull deferred mechanism when a real need appears.
- **Threat model:** defend mechanically against mistakes (T1) and shortest-path-to-green behavior (T2). Deceptive co-resident adversaries (T3) are a named non-goal, handled by records, attribution, per-agent git accounts, and the boss's walk — see target-architecture §T/§A.
- **Code beats prompts** (~1000× cheaper, ~10× more reliable): anything decidable by deterministic tooling is code; agent judgment enters through structured, checkable surfaces; prompt rules are the weak tier and never substitute for gate machinery.
- **Self-documenting names everywhere** (boss-ruled 2026-07-31): directories, files, functions, variables, checks, skills — the boss only reads; every name must teach what it names without opening it. A longer precise name beats a short ambiguous one; ease of typing is not a constraint.

## Phase 1 — First pass (built with the gatekeeper, step 7)

The whole phase is one small script plus stock tools. Estimated build: ~a day of agent work.

1. **`nc-checkin-quality-gate`**: one script — **the check battery of the git-gatekeeper, not a git hook and not a second door**. The door and its candidate workspace are specified in [git-gatekeeper-design.md](git-gatekeeper-design.md), the step-7 build task of [nedschorus-founding-plan.md](nedschorus-founding-plan.md): the git-gatekeeper builds the candidate from the declared files, invokes `nc-checkin-quality-gate` against exactly that tree at its run-the-checks step, and commits and pushes only on pass. Exact-tree evaluation is inherited by construction ("the checks ran against exactly the content that was pushed"), and the candidate workspace runs `uv sync --frozen` before the battery so checks never read the host environment. Agents may also invoke `nc-checkin-quality-gate check` directly against a worktree as an advisory pre-flight — no side effects, no commit power. Enforcement is permission-shaped (boss-ruled): agent sessions are denied git write verbs at the harness permission layer (worktree-guard pattern, proven in the legacy project); the sanctioned agent path is `git-gatekeeper.py check-in`; branch protection — LIVE since 2026-07-21 — makes the gatekeeper's credential the only identity that can push main; hooks are never the enforcement mechanism. **Every check runs on every check-in regardless of what the diff touches** (boss-ruled 2026-07-31): gitleaks plus the Python tool set — `ruff check --output-format json`, `ruff format --check`, `mypy`, `pytest` — full repo every time (the repo is small: full-run *is* the planner, and default-deny comes free; a skip rule would need a path classifier whose mistakes fail silently, and the ledger's duration data reopens skip logic if the suite ever gets slow). Any failure → refuse with the tool's structured output nested in the gatekeeper's three-part refusal. No lanes, no planner, no envelope schema. One invariant: **outer timeout** — the whole battery is wrapped in a wall-clock limit (default 10 min, target-arch §6) with process-group kill, so a hung test cannot wedge the gate. Gate output is **one JSON document** (tool outputs nested inside) so agents never parse prose; and every custom check ships with one red and one green fixture exercised by its own tests — the armed-backstop rule in miniature.
2. **Tool configs** (settled; the Ruff block inlined 2026-07-31 as the union of the two reviewed candidate lists): mypy strict with relaxed-`Any` overrides for `tests.*` and `nc_checkin_quality_gate.*` (the checker's own package); pytest with `--disable-socket`, `--timeout=30`, `xfail_strict`. Environment: uv, committed hash lockfile, `.python-version` = 3.13.x, `uv sync --frozen` as the one repair command. The Ruff block, verbatim (pin verified on PyPI 2026-07-31 — 0.16.1 is the current latest):

    ```toml
    [tool.ruff]
    required-version = "==0.16.1"
    target-version = "py313"

    [tool.ruff.lint]
    select = [
      "A","ASYNC","B","BLE","C4","DTZ","E4","E7","E9","EXE","F","FA","FLY",
      "FURB","G","I","ICN","INP","INT","ISC003","LOG","N","PGH","PIE","PLC",
      "PLE","PLW","PT","PTH","RET","RSE","RUF","S","SIM","SLOT","T10","TC",
      "TID","TRY","UP","W",
    ]
    ignore = []
    fixable = ["ALL"]

    [tool.ruff.lint.per-file-ignores]
    "tests/**/*.py" = ["S101"]  # pytest assertions are the test oracle
    ```

    (The Phase-2 retry pull adds the second per-file ignore — `"src/nc/runtime/retry.py" = ["TID251"]` — and the tenacity banned-api; not Phase 1.)
3. **Suppressions need reasons**: PGH003/PGH004/RUF100 enabled, plus a ~20-line check that every `noqa`/`type: ignore` carries `reason="…"` on or above the line. No registry, no lifecycle — `git log -S` is the audit.
4. **Run record — two logs with distinct purposes (boss-ruled 2026-07-31)**: (a) `quality/runs.jsonl`, the **committed evidence ledger** — the git-gatekeeper appends the run's JSON line into the candidate itself before committing, so every landed commit carries its own line: `{when, tree, checks: [{name, status, duration_ms}], failed_test_ids, needs_walk, posit_count, decision}`. Landed runs only; single writer by construction; the walkable substrate every adoption trigger reads. The ledger is machine-owned: a check-in declaring `quality/runs.jsonl` in `--files` refuses. (b) The **machine-local run store** (SQLite, one file beside the B4a workspace root — boss-ruled 2026-07-31: a store the gate queries by key is a DB, not a log to scan) — the gatekeeper writes one row per run there, landed *and refused*, including each check's failing file paths: operational telemetry for refusal statistics, cross-submission flake detection (fail-then-pass on an identical tree is only detectable if the failed run left a record), and the **loop counter** — the (file × check) consecutive-failure count that drives the fix ladder's tier escalation and, at the threshold (default 3 submitted failures), the **LOOP-BREAK refusal**: stop the fix cycle, the failing file may be symptom not cause, design-gap GHI minted with the receipt, routed to the walk (agent-loop rule 2, where the full mechanism lives). A bounded, named exception to the spec's no-side-logs rule, same class as the B4d refusal record. Target-arch §3's fuller ledger line is the future shape of (a); fields are added when their consumers arrive.
5. **NEEDS-WALK list**: the gate adjudicates nothing — diffs that delete tests/assertions, add skip/xfail, touch quality configs, the lockfile, dependencies, **or the gate itself** (`nc-checkin-quality-gate`, `git-gatekeeper.py`, or consumed tool configs → `NEEDS-WALK: GATE SELF-CHANGE` — the shortest green path past a failing check is editing the gate, and that must never pass silently) produce a loud `NEEDS-WALK:` section, **explicitly a heuristic** (a diff grep; renames and clever edits can slip it; the walk is the real check). The boss's walk of landed check-ins is the verdict layer. Plus `NEEDS-WALK: CHURN` (spec-kit walk yield): compare `git diff --stat` with `git diff -w --stat` — a diff that shrinks dramatically under whitespace-ignoring is mostly reformatting, flagged so the walk sees `200 lines changed, 6 meaningful` up front; canonical formatters and machine-owned files remove the churn axis where they exist, this catches the rest. The ledger line records the NEEDS-WALK items themselves (`needs_walk`, item 4 — count derivable), so the walk reads them from the landed record without re-deriving.
6. **Bypass accounting, break-glass, identity (RATIFIED 2026-07-31)**: the boss is the sole break-glass authority; break-glass is the `nc-bootstrap-N` **emergency lane** — human-signed, tagged, logged, each numbered use walked afterward — a deliberate, visible org-owner act, never a standing path: routinely the boss never commits directly ([git-gatekeeper-design.md](git-gatekeeper-design.md) § The credential and enforcement); a boss-originated change is drafted with an agent and checked in like any other. **Each agent gets its own git account** — attribution by construction, and at the remote tier agent accounts simply lack write access to protected branches; the gatekeeper's credential is the only pusher. Agents cannot bypass (item 1); drift detection is the spec's standing **trailer-absence audit**: every gatekeeper check-in carries `Gatekeeper-*` trailers (including B6's `Gatekeeper-agent` runtime/model line), so a commit on main without valid trailers IS the direct-commit marker, and the handoff-scrub audit files a `draft` issue naming it. **Identity tiering:** in Phases 1–2 identity is informational — per-agent declared names label commits and log lines for the walk; nothing blocks on identity. At the remote tier identities become authenticated per-account credentials; any future reviewer-independence machinery (Phase 3) computes only over authenticated identities, never declared ones.
7. **Posits as convention only**: the `# nc:posit {...}` comment grammar (explicit `id`, class, denominator, basis) plus `nc-checkin-quality-gate list-posits` — a subcommand, not a second tool; each gate run writes the posit count into its ledger line (`posit_count`, item 4). Nothing enforces; the pilot's first question is what posits are like to write and read.

## Phase 2 — Soon (direction settled; build when the need appears)

| Item | Trigger | Design ref |
|---|---|---|
| Tach import boundaries (config already drafted) | The diff that creates the second internal module — built in that same change | target-arch §5 |
| Retry wrapper (Tenacity behind one seam, TID251 + import check) | The diff that first needs retry — same change | §2 |
| Flake quarantine — diff-touched flaky tests still block; only pre-existing flakes quarantine | First flaky test (fail-then-pass on the identical tree — the one definition kept sharp, since the quarantine rule hangs off it) | §6 |
| pytest-testmon fast loop | The suite feels slow; the run log has the numbers if wanted | §6 |
| CI as authoritative runner (isolated, merge-tree evaluation) | CI exists (the GitHub remote already does; branch protection live since 2026-07-21) | §7 |
| Mechanical test-integrity diff (NC-TST001 predicates) | The walk feels loaded, or the first weakening the walk catches that the simple scan missed | §6 |
| Hypothesis property tests | First pure parser/serializer/state machine | §6 |

Trigger discipline is the existing pull-when-needed rule: a trigger is a need noticed in the course of work — usually the existence of a new artifact — and ratified at the walk. The run log informs these calls when numbers help; it is never a precondition for making them.

## Phase 3 — Maybe later (designed and reviewed; pull only if the system's shape demands it)

All in [nc-python-toolchain-target-architecture.md](nc-python-toolchain-target-architecture.md), pre-reviewed with round-2/3 findings folded — pulling any of these starts from a vetted design, not a blank page.

- Committed verdict files + reducer + per-rule policy digests — *a second trusted reviewer (human or agent) exists and the walk can't scale.*
- Identity and computed reviewer independence — *multiple humans or semi-trusted agents (over authenticated identities only).*
- Self-change lane, phased bootstrap, trust-surface manifest — *gate machinery grows enough that its own changes carry real risk.*
- Waiver machinery beyond logged direct commits — *same condition as verdicts.*
- §A audit automation (evidence replay, selftest-at-rev, identity graphs) — *CI plus scale or suspicion.*
- Coverage `dynamic_context` + posit-vs-coverage report (shadow) — *sustained posit use, read from the ledger (moved out of Phase 2, where "gatekeeper code exists" would have fired immediately and proven nothing).*
- Envelope schema v1, planner path-map, design-claims registry, posit enforcement (NC-POS rules) — *the posit-coverage report shows sustained, useful posits.*
- Mutation testing (mutmut, advisory) — *long green stretch plus a concrete reason to doubt test strength.*

**Rejected outright (standing, all reviews):** per-block mandatory annotation, universal semantic linker for dynamic Python, LLM-judgment quality gates, auto-rewriting declared intent to match observation, reimplementing mature linters.

## The judgment layer — spec-kit walk yield (2026-07-31)

The gate governs code mechanically; these govern how agents use *judgment* tools — skill contracts, not gate machinery. Accepted yield from the spec-kit read-for-ideas walk (source: [github/spec-kit](https://github.com/github/spec-kit) @ `642fa56`):

- **Rider on define-work ([#15](https://github.com/nedschorus/nedschorus/issues/15)) — clarification as a walk.** (1) *Scan first, then ask*: before asking anything, scan the whole artifact against a fixed category list (scope/success criteria; data/entities; interaction flows; non-functional attributes; integrations; edge cases; constraints; terminology; completion signals; unresolved placeholders and unquantified adjectives), grade each Clear/Partial/Missing; questions come from this coverage map ranked by impact — never from the first confusion encountered. (2) *Deliver as a walk, not a questionnaire*: one question per turn, each leading with the recommended answer and a one-line reason; the boss stopping is the budget; on stop, remaining Partial/Missing categories are listed as deferred, never silently dropped. (3) *Answers land in the artifact immediately*: dated clarification entry plus an edit to the clarified section, deleting now-contradicted text.
- **Rider on write-test-plan ([#18](https://github.com/nedschorus/nedschorus/issues/18)) — requirements-quality pass.** Run as the skill's first step, by the reader never the designer (legibility is measured at the point of consumption): checklist items test *what is written*, never the implementation ("is 'prominent display' quantified?"). Unresolved items are the `needs-design-clarification` refusal payload. Plus the traceability sentence: *the test plan lists, per requirement, its covering checks, and per check, its requirement; orphans in either direction are stated explicitly.*
- **Two authoring-checklist lines** (for `docs/wiki/queue/skill-authoring-checklist.md`): the wrong-vs-right example-pair device for teaching inversions; and *interactive steps belong to interactive sessions* — a skill needing the boss either runs interactively or, headless, defines its can't-ask behavior as **refuse-with-questions** (the unresolved items are the deliverable, routed to the boss); silent defaulting in place of an unanswered question is never the behavior.
- **`NEEDS-WALK: CHURN`** — landed directly in Phase 1 item 5 above.
- **Named reopening trigger** (E4, otherwise rejected): the first agent-cut plan containing a slice whose "Demonstrated by:" line couldn't be written reopens independent-test slicing as a [#16](https://github.com/nedschorus/nedschorus/issues/16) rider.
- **Build-time reference pointers** (no rider text): spec-kit's `tasks-template.md` conventions for [#16](https://github.com/nedschorus/nedschorus/issues/16)/[#20](https://github.com/nedschorus/nedschorus/issues/20); re-read at build time.

Rejected spec-kit imports (reasons as ruled): spec-as-single-source-of-truth (map/territory error — code is the truth past the initial phase), prompt-checklists where code/walk/artifact mechanisms exist, reviewer-carried doctrine, template severity tables, the fixed question cap.

## Multi-agent operating rules (from the 2026-07-30 five-agent experiment)

Rule-shaped findings from running five agents (two model families, three effort tiers) on this plan's production — they govern how NC uses agents as tools:

1. **Peer-awareness is a missing prior, installed by disclosure.** Agents sharing an environment never spontaneously hypothesize a concurrent writer — faced with impossible file state, every agent blamed itself or the disk; all coordinated flawlessly once told. Therefore: any prompt for an agent in a shared environment states that other agents are active and that unexplained state changes are probably peers (report, never rewrite on anomaly); output paths derive from agent identity; shared mutable files get exactly one owner (the ledger's union-merge and machine-owned files are this rule already applied). Evidence: the three-way output-file collision, 2026-07-30.
2. **Vary model family before reasoning effort in review panels.** Cross-family reviewers found different *categories* of defect; extra effort within one family found depth inside the same categories. Same-model agreement — which reached sentence-level similarity on identical prompts — counts as one opinion, not two.
3. **Force convergence with scenario discipline and commitment lines.** Requiring a concrete failure scenario per finding ("no scenario, no finding") and an explicit SAFE / NOT-SAFE commitment eliminated hedge-findings and converged an adversarial panel in three rounds.
4. **Non-converging reviews are a goal-level signal.** When finding counts do not shrink across fix cycles, stop patching: the goal is mis-scoped — the patch-cycle tripwire, observed firing at design level (the threat-model ruling collapsed ~30 "unfixable" findings at a stroke).
5. **Judgment tasks converge where adversarial tasks don't.** Blind cross-model phasing/prioritization agreed almost entirely; use panels for adversarial review, and a single agent plus spot-check for prioritization.

## What Phase 1 is designed to teach

Which checks fire and what they cost (the committed ledger plus the machine-local runner log, item 4); whether reason-required suppressions change agent behavior; NEEDS-WALK volume (calibrates the test-integrity pull); whether posit comments feel natural or like noise (decides the posit program's future); real flake and duration data (refusals live in the runner log). Phase transitions are needs noticed at work and ratified at the walk — the run log informs, never gates.
