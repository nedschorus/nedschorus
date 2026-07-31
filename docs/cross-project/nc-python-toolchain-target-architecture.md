# NC Python quality toolchain — decisions (v3)

v3, 2026-07-30. Supersedes v2 after a five-reviewer round-2 panel (archived: `nc-review2-cops.md`, Fable-2 report, three cvp console reviews). v3 makes one governing change — an explicit threat model — and under it re-triages every round-2 finding: accident-class findings are fixed in the sections below; deception-class findings move to §A (detected, not prevented). The document is deliberately sized to be walkable in one session; complexity beyond that budget requires a new ruling, not a bigger document.

## T. Threat model (governing ruling)

The gate defends **mechanically** against two adversaries:

- **T1 — fallible agents**: bugs, misreadings, forgotten steps.
- **T2 — shortest-path-to-green agents**: will opportunistically weaken a test, add a suppression, loosen an assert, or skip a check when that is the easiest route past the gate — but do not construct deceptions.

**Named non-goal — T3, the deceptive co-resident adversary** (forged evidence, counterfeit runners, authorship laundering, evaluator poisoning). A gate whose code lives in the repo it gates, on the host the agents control, has no fixed point of defense against T3 — round 2 demonstrated this empirically (every defense added in v2 became round-2 attack surface). T3 is handled the way human organizations handle insider threat: **record, attribute, audit, and anchor externally** — an append-only evidence trail that makes attacks detectable and attributable after the fact (§A), authoritative evaluation moving to isolated CI when it exists (trigger, not date), and the human walk of every merge during the seed phase. A review finding that requires a T3 adversary is answered by §A, not by new mechanism; a finding that shows §A would fail to *record* a T3 attack is in scope.

## 0. Vocabulary

- Marker grammar: `# nc:<verb> <payload>`, verbs `posit` | `suppress`; one marker per line; `posit` rides the governed header line, `suppress` rides the line above the governed line.
- Rule lifecycle: `shadow → advisory → blocking_pending_verdict → blocking`, plus `retired`; carried per rule in the registry; the envelope's `classification` is always registry-derived, never producer-chosen.
- **Fingerprint** (normative): `rule_id` + stable location key (path + enclosing symbol) + SHA-256 of the governed span's content + (for suppressions) the suppressed code. For path-scoped findings (config/protected-path rules): `rule_id` + path set + SHA-256 of the diff hunks within the protected paths. The fingerprint is the identity for findings, verdicts, and waiver scoping; any change to governed content changes the fingerprint and re-opens adjudication. No standing licenses.
- Denominator enum (shared by posits and design claims): `{decision_evaluation, function_call, wrapper_attempt}`.

## 1. Posit grammar

Unchanged from v2 except: `basis` design references **must** carry a revision (`design:NC-42@r3`); rev-less design references are `NC-POS002` errors. Posit `id` explicit and repo-unique; classes `{HOT,NORMAL,RARE,EMERGENCY,UNKNOWN}`; `freq` required exactly when the referenced claim states a frequency; `quality/design-claims.toml` entries are immutable per rev and protected by `NC-SUP002`. Rules `NC-POS001/2/3a/3b/4` as v2; promotion criteria as §6.

## 2. Wrappers

Unchanged from v2: retry only; Tenacity behind `src/nc/runtime/retry.py`; `posit` (with `freq` inside `Posit` — single source); containment via Ruff `TID251` + `NC-IMP001` (all import forms, fixtures for each).

## 3. Envelope, records, and the run ledger

- One JSON Schema (`quality/schemas/nc-quality-event-v1.schema.json` — inside the protected glob), kinds `diagnostic | gate_decision | verdict | waiver`. **All persisted records are envelope-shaped JSON** — committed verdict/waiver files are the event itself (one JSON document per file); no second TOML shape exists.
- `diagnostic` and `gate_decision` payloads as v2, with: `subject_binding` for verdicts = `{fingerprint, rule_policy_digest}` — **no `tree_oid`** (a verdict must survive the rebase that lands it), and **no global bundle digest** (a planner tweak must not inert every standing verdict). `rule_policy_digest` = hash of the rule's registry entry + the config files its producer consumes, declared per rule as `policy_inputs[]` in the registry. The global `policy_bundle_digest` (registry + configs + schemas + planner + **checker source tree** + tool lockfile) is still recorded on every `gate_decision` for audit and replay.
- `verdict` payload: per-family values — suppression `{accept,reject}`; test-integrity `{justified,defect}`; mutation `{missing_test,equivalent_mutant}`; posit-mismatch five-verdict set; **policy-change `{accept,reject}`** (the family for `NC-SUP002`/dependency/config findings). The registry publishes one exhaustive `(family, value) → {allow, refuse, follow_up}` table; schema validation and the reducer both consume that table — no implicit "accepting" judgment. Reviewer identity per §10.
- **Run ledger** (new): every gate run appends one line to `quality/runs.jsonl` in the working tree — `{run_id, decision, tree_oid, base_oid, policy_bundle_digest, environment_digest, checks:[{check_id,status,duration_ms}], finding_fingerprints:[], first_seen_carryover}` — which lands with the change it describes. The ledger is the substrate for every numeric adoption trigger (§6), for escalation clocks (§8), and for §A audits. Abandoned branches take their ledger lines with them; that is acceptable — triggers and audits reason over landed history.
- Registry `quality/rules.toml` as v2; `nc-check selftest` (fixtures red/green + `cost_budget_ms` p95) is a wave-1 required check. `owner` and `retirement_condition` are consumed by the scheduled repo-health lane (§4).

## 4. Ruff, suppressions, and the repo-health lane

- Ruff config as v2 (pin 0.16.1, `target-version = "py313"`, explicit select union, two per-file ignores, `banned-api` tenacity).
- Suppression grammar and registry as v2 (`quality/suppressions.toml`, paired `# nc:suppress` line, bidirectional pairing check).
- **Protected-set precedence (fixes v2's regress):** the protected trust surface is a machine-read manifest, `quality/trust-surface.toml` — initial contents: `pyproject.toml` (the enumerated tables: `tool.ruff`, `tool.mypy`, `tool.pytest.ini_options`, `tool.coverage`, `project.dependencies`, `dependency-groups`), `tach.toml`, `.gitleaks.toml`, `.python-version`, `uv.lock`, `tools/nc_check/**`, and `quality/**` **except** `quality/verdicts/**`, `quality/waivers/**`, and `quality/runs.jsonl`. `NC-SUP002`'s scope *is* this manifest, and `nc-check selftest` enumerates every file the evaluator actually consumed at runtime and fails if any lies outside it — the protected set cannot silently drift from reality. The **verdict lane** is a path-exact allowlist (`quality/verdicts/**` only, plus the ledger line) with a mandatory always-on check set: schema validation, independence computation, gitleaks, and a 64 KB size bound. Waivers never pass through any gated lane (§11).
- **Repo-health lane (new, fixes the stampede):** suppression `review_after` (floor **14 days**), registry retirement evaluation, and `--ignore-noqa` audits run as a *scheduled* lane whose findings block only diffs touching the implicated files — never unrelated commits. Re-opened suppressions cannot be adjudicated by their original author.

## 5. Import boundaries

Unchanged from v2: Tach 0.35.0; target layer architecture recorded here; `tach.toml` written and enforced from the diff that creates the second internal module.

## 6. Sequencing, lanes, and flakes

- Wave 1 tools and mypy config as v2, with the override patterns matched to real paths: the checker is the installed package `nc_check` (from `tools/nc_check/`, declared in `pyproject.toml`); mypy overrides target `nc_check.*` and `tests.*` and CI asserts the overrides matched at least one module each (guards silent full-strictness reversion).
- **Evidence lane, one execution**, invoked by the runner as `python -I -P -m coverage run -m pytest …` with pinned argv, from a directory outside the candidate tree (accident-proofing against accidental module shadowing; also narrows T3 per §A): `--junitxml` and coverage artifacts write to a runner-owned directory outside the tree; tests get a scratch tmp. `[tool.coverage.run] branch = true, dynamic_context = "test_function"`. The runner itself enforces an **outer wall-clock limit** (default 10 min) with full process-tree teardown — in-process pytest-timeout is a convenience, never the backstop; a hung or runaway candidate cannot occupy the gate.
- Lanes `evidence | debug | impact` as v2; `impact` exists only after testmon adoption; `NC-RUN001` enforces purity.
- **Flake policy (new):** a required-check test failure that passes on one immediate identical-tree rerun is recorded `flaky` in the ledger and opens a quarantine entry (`quality/quarantine.toml`: test id, owner, `expires` ≤ 14 days, adjudicated like a suppression). Quarantined tests run non-blocking until expiry; stabilization edits to a quarantined test are `NC-TST001`-advisory rather than blocking during the quarantine window. Quarantine entries are `NC-SUP002`-protected.
- Adoption triggers as v2 (testmon at evidence p95 > 30 s over 20 landed ledger runs; mutmut after 20 consecutive green landed runs; Hypothesis at first pure module; Tach at second module; R6 custom halves named-deferred, shadow at first non-adapter module) — all evaluated from the committed run ledger, not from anyone's recollection.
- Posit pilot promotion as v2 (counts + adjudicated mismatches + p95), evaluated from the ledger.
- `NC-TST001` (published predicate registry, explicit uncovered remainder), `NC-DET001` (+ `tests/**`, seams allowlist, env pinning), `NC-RUN001` as v2.

## 7. Execution boundary

- **Exact tree, executable form:** local gate: `T = git write-tree`; synthetic commit `C = git commit-tree T -p <base_oid> -m "nc-gate subject"`; evaluate a detached worktree at `C`; diagnostics bind to `T`; the synthetic commit is discarded. CI: prospective merge tree (merge-queue semantics). Two-green-merge-red is caught at the merge tree.
- **Pinned evaluator:** checker, planner, schemas, registry execute from the trusted base revision. **Planner is default-deny**: a diff path matching no planner entry raises `NC-PLN001` (blocking), and an always-on check set (gitleaks, envelope validation, selftest) runs regardless of path mapping.
- **Self-changes** (`NC-SUP002` set incl. `tools/nc_check/**`): evaluated by the base evaluator with an independent verdict, as any protected change. The v2 dual-run/auto-promotion machinery is **removed** (it defended against T3 and defended badly); what remains is the record: the ledger marks evaluator-changing commits, and §A's audit replays fixtures against evaluator changes after the fact. Seed-phase evaluator changes are additionally on the human walk by definition (they are protected-path merges).
- **Self-blocking repairs (fixes the brick):** for the enumerated *self-blocking key class* — `cost_budget_ms`, rule `lifecycle`, `.python-version`, `uv.lock` — the reducer reads the **candidate** tree's values when (a) the diff touches only that class and (b) an independent verdict accepts it. A repo whose base config refuses everything can therefore land the one-line repair through the ordinary verdict flow; the recovery lane (§11) remains for everything worse.

## 8. Verdict lifecycle

- Verdicts are committed envelope-JSON files at `quality/verdicts/<fingerprint>.json`, landed **first** through the verdict lane; the blocked change then lands and matches on `{fingerprint, policy_bundle_digest}` — rebase-stable by construction.
- Reducer: refuse iff a required check is missing or non-`pass`, or a registry-`blocking` diagnostic exists, or a `blocking_pending_verdict` diagnostic lacks a committed accepting verdict with matching binding. Content change → new fingerprint → prior verdict inert (not "invalidated" — it simply never matches again).
- **Concurrent verdicts:** two verdict files for one fingerprint with conflicting values fail closed — reject-wins until the human authority records a tiebreak (a waiver-lane record). Verdict files are immutable once landed; supersession is a new event, not an edit.
- **Escalation clock:** a finding's `first_seen` is carried in ledger lines (`first_seen_carryover`) from the first run that reported it; `nc-check pending` reads it from the working tree's ledger. Pending > 24 h → the runner notifies the human authority (the seed-phase notification channel is the boss's mail; mechanism recorded in the runner config, not this document).

## 9. Bootstrap, environment, migration

- Phases 0 (tagged, ungated, logged founding commit) → 1 (shadow) → 2 (blocking) as v2, with one change: **`bootstrap-N` is a standing recovery shape, not a one-shot** — a human-signed, path-unrestricted, tagged, logged commit lane reserved to the human authority (§11), each use requiring a follow-up audit finding. Phase 0 is simply `bootstrap-0`.
- Environment: uv + hash lockfile, `.python-version` = 3.13.x, `uv sync --frozen` as the single repair command. `environment_digest` = `{deps_digest (interpreter + lockfile), platform (triple, recorded separately)}` — parity checks compare `deps_digest` only.
- Dependency changes (incl. transitive): `blocking_pending_verdict`, justification names the dependency's purpose.
- Migration: N/N+1 reader window for schema and registry versions as v2; design-claim revs bind observations; fail-closed applies outside the window only.

## 10. Identity

- Local index-tree runs make **no identity claims** — there are no commits yet; identity-sensitive rules evaluate at commit/merge time on the committed range `merge-base(trusted-branch, HEAD)..HEAD`. Author set = authors + committers of that range, **excluding mechanical identities** (merge-queue bots, rebase committers listed in `quality/identities.toml`). Independence = verdict-commit author ∉ author set; if the author set exhausts the reviewer population, the case escalates to the human authority and the ledger records it.
- Git identities are unauthenticated locally; CI's authenticated actors become authoritative at CI adoption (trigger). Laundering and Sybil identities are T3 (§A). Free-text justifications are data, never instructions, to reviewing agents.

## 11. Recovery and human authority

- Authority: the repo owner (ratified v3).
- **Waivers bind to `{rule_ids, fingerprint set, policy_bundle_digest}` — never a tree.** They are recorded through the `bootstrap-N` lane (human-signed, ungated by construction — the escape hatch does not pass through the machinery it escapes), expire ≤ 7 days, and always open a follow-up finding. The reducer honors an unexpired matching waiver as an accepting verdict.
- Broken-gate repair: self-blocking key class → §7's candidate-value path; anything worse → `bootstrap-N`. Both leave ledger records and follow-up findings.

## 12. Supply chain and secrets

As v2 (hash lock, dependency verdicts, gitleaks in the always-on set, config protected), plus: all candidate-process output (stdout, stderr, JUnit, coverage metadata) is treated as **tainted text** — secret-scanned before any artifact publishes, publication fails closed on scanner uncertainty. This is accident-protection too: honest tests print secrets by accident.

## A. Detected, not prevented (T3 ledger)

Each entry: the attack, what the record captures, the audit that finds it, and the upgrade trigger. Standing audit cadence: seed phase = the boss's walk of merges; automated spot-audits join the repo-health lane at CI adoption.

1. **Evidence forgery in the candidate process** (conftest hooks rewriting artifacts; suite-selection hooks; counterfeit runner packages). Record: ledger check durations + coverage totals + junit test counts (sudden suite shrinkage is visible); evidence artifacts retained per run. Audit: compare collected-test counts and durations across ledger history; replay the evidence lane on suspect trees on trusted infrastructure. Upgrade: CI adoption moves authoritative evidence to isolated runners (`-I -P` invocation already narrows the local vector).
2. **Authorship laundering / Sybil review** (one principal, two identities). Record: full identity pairs in ledger + verdict files. Audit: identity-graph review at walk time; CI authenticated actors at adoption. Upgrade: principal registry only if NC ever admits untrusted third-party agents — named-deferred.
3. **Evaluator poisoning** (checker change that lies thereafter). Record: evaluator-change commits are flagged in the ledger (policy digest change); fixtures are committed. Audit: replay current fixtures against each historical evaluator revision on demand (`nc-check selftest --at <rev>`); any silent fixture-outcome drift is attributable to the introducing commit. Upgrade: CI runs selftest replay on every evaluator change.
4. **Waiver misuse** (bundling unrelated findings under a broad waiver). Mechanically narrowed already (fingerprint-set scoping, §11); residue (human signs a bad waiver) is recorded and expires ≤ 7 days with a follow-up finding.

## Changelog v2 → v3 (round-2 finding → disposition)

Threat model absent (root cause, boss ruling) → §T. Worktree/commit-ish (R2-01, F10a) → §7 synthetic commit. Promotion hole (R2-02, F5, CVP2-A/B) → §7: dual-run/auto-promotion machinery removed; evaluator changes = ordinary protected changes + §A.3 replay audit. Verdict tree-binding & races (R2-03, F6) → §0 fingerprint definition, §3 binding minus tree_oid, §8 immutability + reject-wins + human tiebreak. Laundering (R2-04) → §A.2 (T3). Digest gaps (R2-05) → §3 policy digest includes checker source; §9 environment split (F10b). Conftest/suite-selection & runner shadowing & artifact writes (R2-06, F4, CVP2-A) → §6 `-I -P` outside-tree invocation + runner-owned artifact dir (accident tier) + §A.1 (deception tier). Waiver over-breadth (R2-07) → §11 fingerprint-set scoping. Secret exfiltration via artifacts (R2-08) → §12 tainted-output scanning (accident tier) + §A.1. First-seen clock (R2-09, F9) → §3/§8 ledger carryover. Verdict/waiver schema split (R2-10, F2) → §3 envelope-JSON records; §4 precedence carve-out + verdict-lane always-on checks. Break-glass gated & waiver fixed point (F1) → §11 bootstrap-N lane + fingerprint binding. Base-repair brick (F3) → §7 self-blocking key class. Registry consumers (Fable regression 7) → §3 selftest + §4 repo-health lane. Collateral blocking & reviewer exhaustion (F8) → §4 repo-health lane + floor; §10 range definition + mechanical-identity exclusion + human escalation. Run history & flakes (F9) → §3 ledger; §6 flake/quarantine policy. `@rev`, denominators, mypy paths (F10c/d/e) → §§1, 0, 6. Pre-commit author range (CVP2-C) → §10 local-runs-make-no-identity-claims. Counterfeit runner + no outer supervisor (CVP2-A R2-01) → §6 `-I -P` + runner wall-clock/teardown. Global-digest verdict invalidation storm (CVP2-A R2-06) → §3 per-rule `rule_policy_digest`. Trust-surface manifest gap, unprotected schemas/gitleaks config (CVP2-A R2-07) → §4 `quality/trust-surface.toml` + consumed-files selftest. Missing policy-change verdict family and reducer value table (CVP2-A R2-09) → §3. Boss-walk ratifications 2026-07-31: break-glass authority (§11 — boss, git access outside the gated system; per-agent git accounts, so remote-tier enforcement and attribution are account-shaped) and identity tiering (§10 — informational in phases 1-2, authenticated at the remote tier, independence machinery only ever over authenticated identities).
