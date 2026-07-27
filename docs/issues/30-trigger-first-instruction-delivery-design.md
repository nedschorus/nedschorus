> **Carried from nedlern 2026-07-27** (boss-directed, part of the nedlern
> decommissioning): original path `docs/working/trigger-first-instruction-delivery-design.md`
> at nedlern main. Pair: [nedschorus#30](https://github.com/nedschorus/nedschorus/issues/30).
> The companion 348-line CLAUDE.md scan is carried alongside as
> [30-trigger-first-claude-md-scan-first-pass.md](30-trigger-first-claude-md-scan-first-pass.md).
> The other sibling files this document links (thoughts, cold-review,
> hook-spam-audit, restructure-synthesis) were NOT carried — the boss ruled
> them notes and speculative design for a pruned mechanism; those relative
> links are dead here by design and resolve only in nedlern history.

# Trigger-First Instruction Delivery — Wave-0 Design

- **Status:** wave-0 design of record for [nedlern/nedlern#1972](https://github.com/nedlern/nedlern/issues/1972) (`priority:high`). **Revision 3, 2026-07-19 — /d-review COMPLETE, verdict READY:** round 1 (author pass + independent cold review: not-ready, 4 HIGH / 8 MED / 5 LOW) fully incorporated in revision 2; the same reviewer's finding-by-finding verification of revision 2 returned **ready — all 17 resolved**, with two NEW wrinkles (loose pre-filter anchors; ambiguous session-fallback key) folded into this revision. Review record: [trigger-first-instruction-delivery-design-cold-review.md](trigger-first-instruction-delivery-design-cold-review.md). Nothing here executes without the boss's per-piece review; ops execution is additionally held by the boss's priority gate (ops paused 2026-07-19).
- **Inputs, all on main:** the boss's ten candidate dispositions + standing rules ([trigger-first-instruction-delivery-thoughts.md](trigger-first-instruction-delivery-thoughts.md) § Boss walk decisions), the 67-row first-pass scan ([trigger-first-instruction-delivery-scan-first-pass.md](trigger-first-instruction-delivery-scan-first-pass.md)), the hook-spam audit ([trigger-first-instruction-delivery-hook-spam-audit.md](trigger-first-instruction-delivery-hook-spam-audit.md)), and the D1–D5 records ([claude-md-restructure-synthesis-and-boss-decisions.md](claude-md-restructure-synthesis-and-boss-decisions.md)).
- **Tracked-by:** [nedlern/nedlern#1972](https://github.com/nedlern/nedlern/issues/1972).

## What this designs

One generic instruction-injector mechanism plus a declarative trigger map, delivering CLAUDE.md rules just-in-time per the boss's D4 architecture; the packaging of the nine approved candidates as atomic PRs; two CI checks; and the periodic real-world audit loop. Boundaries: **injection only, no new blocks** — a PreToolUse `additionalContext` payload arrives *after* the triggering call executes, so it cannot guide that call; for the guide-this-call candidates the **retained CLAUDE.md kernel one-liner** covers the triggering use and injection refreshes the fuller version for ongoing use (see [Guide-this-call delivery](#guide-this-call-delivery--injection-plus-retained-kernel-one-liner-2026-07-19-corrected), which supersedes the withdrawn soft-block proposal); the enforcement ladder is untouched, and neither tool calls nor turn-ends are ever blocked by this mechanism; no CLAUDE.md text changes outside the per-candidate atomic PRs and the final kernel-rewrite PR; Codex-side delivery parked to the [#1925](https://github.com/nedlern/nedlern/issues/1925) reconciliation per D1.

## Architecture

### Injection surfaces — proven vs probed (d-review F-STOP / F-UPS-PRECEDENT)

Ground truth in this harness today: **PreToolUse and PostToolUse `additionalContext` injection is proven in production** (auto-read-before-write, pylint, worktree-guard). **UserPromptSubmit and Stop are NOT**: no repo hook injects consumable context via UserPromptSubmit, and the only production Stop injector (`mail-pull.sh`) delivers via `decision:block` — its non-blocking `additionalContext` path is an untested kill-switch mode. Consequences:

- **Stop matches never inject at Stop.** A Stop-surface match writes a **queue row**; the queued payload is delivered by the injector's PreToolUse/PostToolUse leg on the **next tool event** (any tool), a proven surface. This lands the correction at the start of the next action — before the next fix attempt, which is when it matters — and preserves the never-blocks boundary with no unproven channel.
- **UserPromptSubmit rows require a pre-enable probe:** a one-shot hook returning `additionalContext` on a phrase match, confirmed to reach the model's context, before any UserPromptSubmit row enables (PR-1 gate). If the probe fails, UserPromptSubmit rows convert to queue-rows delivered on the next tool event, same as Stop.

### Guide-this-call delivery — injection plus retained kernel one-liner (2026-07-19, corrected)

*This subsection supersedes an earlier same-day amendment that made guide-this-call candidates deliver via a deny+reason soft-block. That mechanism was proposed, then withdrawn by ops after the boss flagged it as unnecessary complexity, and is not built. The corrected resolution below is injection-only; the deny-path is retained only as a bounded future option (see the proportionality bar at the end).*

**The finding (ccr on [#2085](https://github.com/nedlern/nedlern/pull/2085)/[#2086](https://github.com/nedlern/nedlern/pull/2086); the surface contract re-read at source by code-reviewer, documented in [claude-code-hook-events-and-payloads.md](../wiki/reference/claude-code-hook-events-and-payloads.md)):** a PreToolUse `additionalContext` payload is delivered to the model *next to the tool result* — **after** the triggering tool call has executed. So for a guide-this-call rule (`postal-tier-table`, `merge-protocol`, `review-trailer-protocol`, the git trio) injection cannot shape *that* call, only the next one. Refresh rules are unaffected — they target the *next* action by design (Stop-queue rows delivered on the next tool event).

**The resolution — injection-only, kernel one-liner covers the triggering call:** for each guide-this-call candidate the CLAUDE.md kernel **retains a minimal one-liner** that is the complete decision-point guide (e.g. the T0–T3 + default-T1 tier gloss). Because CLAUDE.md is always in context, that one-liner guides the triggering call with no timing dependency; the injected full payload refreshes the fuller version for ongoing use. Nothing is uncovered: kernel one-liner for the in-flight call, injection for later ones. The per-candidate kernel trim therefore **keeps the one-liner** and only moves the fuller table into the injected payload — it does not zero the kernel guidance.

**Why not a soft-block (the withdrawn proposal, on the merits):** a deny+reason soft-block is proportionate only for a rule whose wrong action is *harmful* AND *not otherwise prevented* AND *must be stopped in-flight* ([how-rules-are-enforced.md](../wiki/operations/how-rules-are-enforced.md) § per-occurrence-harm axis). No current candidate clears that bar: `postal-tier-table`'s wrong tier is low-harm and self-correcting (**remind-class, not block-class** — the same axis that makes an urgency-softener a remind); `review-trailer-protocol` and the git trio are advisory or already-guarded. `merge-protocol` is the one that looks closest to clearing the bar and does not — but for a different reason than "already prevented" (correcting the earlier draft, ccr on #2098): the harmful case, a bare `gh pr merge --squash` that skips the review gate, is **not** hook-prevented — `no-raw-gh-pr-merge.sh` blocks only the `--delete-branch` worktree-checkout variant (see line 99 and CLAUDE.md). It is harmful and unprevented, yet CLAUDE.md **deliberately accepts it as a cooperative residual** ("the gate binds the sanctioned path, not a rogue one … use the tool anyway"), and this design's candidate table already scopes the row as the ONE teach with an explicit silent-bypass warning (line 99). Mechanically blocking the bypass would reverse the fleet's cooperative-trust model — a policy decision above a wave-0 nudge's scope, not a gap for this row to fill. So it stays a teach. Building deny for any candidate would interrupt the common *correct* call to catch a rare low-harm or deliberately-accepted miss — the complexity the boss flagged. The deny+reason path stays **UNBUILT**; it is reconsidered only if a future candidate is demonstrably harmful AND unprevented AND must-stop-in-flight AND not a deliberately-accepted cooperative residual, and then for that candidate only.

**Candidate-10 (`working-drafts`) is a separate mechanism (ccr on #2086):** native `.claude/rules/` loads on **Read, not Write**, so a fresh draft's first Write gets no nudge, and trimming the CLAUDE.md `working-drafts` line also loses its ripgrep-time coverage. **Interim: keep the CLAUDE.md `working-drafts` line** — candidate-10's kernel trim is not safe as-is. A longer fix (a PreToolUse-Write nudge) is out of scope here and does not ride the injection-only mechanism above.

### The injector

ONE hook script (`instruction-trigger-injector.sh`, bash front + python core), registered at PreToolUse (all tools), PostToolUse (all tools), UserPromptSubmit, and Stop. Per fire:

1. **Bash pre-filter (the hot path, d-review F-HOTPATH):** a pure-bash literal screen built from the union of each enabled row's declared `anchor` string (case-statement substring checks against the raw hook input), plus a queue-nonempty check. Python spawns ONLY past the pre-filter or when the queue is nonempty. Every enabled row MUST declare a **selective** literal `anchor` (e.g. `gh pr merge`, `git push`, `root cause`); a row without one cannot enable. **Anchor selectivity rule (verification NEW-1):** bare high-frequency substrings (`bug`, `root`) are rejected at map load UNLESS the row explicitly declares them as accepted-overlap anchors — undeclared, they pass the pre-filter on common non-matching inputs (`debug`, `REPO_ROOT`) and route them onto the python path, creating a latency blind spot the "no-match" budget doesn't bound. Every declared-overlap anchor obliges the latency load test's input distribution to include anchor-passing-but-regex-failing inputs, so the p99 budget bounds that middle path too.
2. Python core: load the map (parsed once, cached by mtime), evaluate matching rows' `subject_pattern` against the row's declared `subject`, check spacing, inject via `hookSpecificOutput.additionalContext` — on PreToolUse always alongside `permissionDecision: "allow"` (d-review F-PERM-DECISION), with a test asserting a matched row never changes the tool's permission outcome. (All current candidates deliver by injection; see [Guide-this-call delivery](#guide-this-call-delivery--injection-plus-retained-kernel-one-liner-2026-07-19-corrected) for why the guide-this-call set relies on the retained kernel one-liner rather than a block.)
3. Deliver any queued rows (from Stop/UserPromptSubmit queue-writes) first, subject to the same spacing check.

**Latency contract (merge-blocking on PR-1):** p99 no-match overhead under a stated budget (proposal: ≤ 25 ms), measured by a 1,000-call load test against the real injector; the budget and measurement land in PR-1's test suite.

**Fail-open contract (merge-blocking on PR-1):** any injector error — unparseable map, python crash, missing state DB — exits 0 with no output and a line in its own log file; a deliberately-crashing injector must demonstrably let the tool through (test). The injector never blocks anything, structurally.

### The trigger map

Proposed location `config/instruction-triggers/triggers.json`, payload texts as `config/instruction-triggers/payloads/<rule-id>.md`. Row schema (d-review F-NAMING-SUBJECT):

| Field | Meaning |
|---|---|
| `rule_id` | self-documenting slug, e.g. `postal-tier-table` |
| `surface` | `PreToolUse` / `PostToolUse` / `UserPromptSubmit` / `Stop` (the latter two are queue-writers) |
| `tool_pattern` | regex over tool name (Pre/PostToolUse only) |
| `subject` | what the row matches: `tool_input.command` / `tool_input.file_path` / `prompt` / `agent_output` / `tool_result` |
| `subject_pattern` | regex over the selected subject |
| `anchor` | REQUIRED literal substring for the bash pre-filter |
| `payload_file` | path under `payloads/` |
| `min_spacing_tokens` | default 50000; per-rule override |
| `subagent_delivery` | default `true`; set `false` to exclude a heavy payload from subagent sessions on audit evidence (d-review F-SUBAGENT) |
| `enabled` | rows land disabled and flip on in their atomic PR |

Map load applies a **regex-cost lint**: rows with catastrophic-backtracking shapes (nested quantifiers over overlapping classes) are rejected at load with a log line, not evaluated.

Ownership classification (open question for ops+vp): injector script in `.claude/hooks/` (hard, ops/vp); map + payloads proposed **free-logged** — they only add instructions, never block, and wiki-lane agents must be able to PR payload wording.

### Spacing state — NEW code (d-review F-SPACING; supersedes revision 1's "reference implementation" claim)

The spacing store is **new code, not a port**. Revision 1 mis-described `nedlern_postal/comms_card.py`'s accumulator as a per-session token-denominated reference: ground truth is it is keyed `(recipient_name, card_version)` — per agent, cross-session, no session column — denominated in mail-message-body bytes, and has never executed in production (env-gated off). It supplies only the *accumulate-and-floor shape*.

Decided here (not deferred): a sqlite table `instruction_injection_state(session_id, rule_id, transcript_bytes_at_last_injection, updated_at)`, keyed **per (session, rule)**, denominated in **transcript-byte growth** (the only denominator the hook environment can actually feed; ~200KB ≈ 50k tokens, the boss's rider). Session key: the harness session id; **fallback when absent is the PARENT Claude-session process's PID+start-time — never the injector's own PID (a fresh process per event, which would reset the window every fire and disable spacing entirely — verification NEW-2), and never a worktree-shared value** (a repo-root fallback would clobber all sessions in a worktree into one window, d-review F-GAPS/F-SUBAGENT). Subagent sessions carry their own ids and therefore their own independent windows (test: two session ids, independent accumulate/cross/reset). Unit tests: accumulate → cross-floor → reset with synthetic ids.

**Retention (d-review F-GROWTH):** on injector start, prune rows with `updated_at` older than 14 days (cheap DELETE, tested). Sessions are minted constantly (every /clear, every subagent); without GC this table is the unbounded-state class [nedlern/nedlern#1061](https://github.com/nedlern/nedlern/issues/1061) exists for.

**D3 decoupled (d-review F-D3-COUPLING):** the D3 deletion of `comms_card.py`'s render machinery is NOT blocked on any extraction — the injector's store is independent new code. Delete the render once `mail-pull.sh`'s import is removed or guarded; port nothing unless ops finds the shape genuinely reusable.

### Delivery surfaces that are NOT the injector

- `.claude/rules/` path-scoped files (candidates 7 and 10) — the proven native mechanism, **kept native** (d-review F-SCHEMA-EXT: no path-matching duplicated into the injector). Measure native dedup/spacing behavior; if it cannot be spaced, **accept native per-touch semantics for these two rows** — their payloads are small and the wiki-editing precedent shows the volume is tolerable. Revision 1's `file_path_pattern` injector fallback is dropped.
- Existing enforcement hooks (candidates 2, 3) — already fire at their moments; the work is payload audits, **each backed by a regression test** asserting the required teach strings (e.g. `NEDLERN_DEVIATION_REQUEST`, "reconcile") remain present in the hook/block messages after the kernel lines drop (d-review F-AUDIT-DISCIPLINE) — the kernel-drop is protected by a test, not memory.
- SessionStart (comms card, handoff inject) — priming half of dual deliveries; fires on all start sources including /clear (verified 35/35).

## Failure modes (d-review F-GAPS — every cell explicit)

| Condition | Behavior | Test |
|---|---|---|
| `triggers.json` unparseable | fail open: no injections, log line, tool proceeds | yes |
| `payload_file` missing | skip that row, log line | yes |
| session id absent | PID+start-time fallback key (never worktree-shared) | yes |
| transcript path absent / unreadable | inject WITHOUT spacing (over-delivery beats a clobbered window; boss's over-fire tolerance), log line | yes |
| injector crash / timeout | fail open, exit 0, tool proceeds | yes (deliberate-crash test) |
| map edited between cache and fire | benign: mtime cache reloads next event; a one-event stale window is accepted | noted, no test |
| concurrent sessions, same worktree | independent windows by session key | yes (two-id test) |

## Trigger map v1 — the approved candidates as rows

| rule_id | surface + matcher | payload (source of text) | pairs with (same PR) |
|---|---|---|---|
| `postal-tier-table` | PreToolUse, tool `mcp__postal__(send_to_agent\|respond\|respond_packed)`, anchor `postal` | full T0–T3 table + default-T1 (kernel verbatim) | kernel trim to the boss-approved one-liner + SessionStart-card pointer update (candidate 1) |
| `hard-problem-checklist` | UserPromptSubmit (probe-gated) `(?i)\b(bug\|broken\|regression\|root.?cause\|why (does\|is\|did)\|investigate\|repro\|debug\|intermittent\|flaky\|fail(s\|ing\|ed) (on\|in\|when))\b`, anchor set = a COVERING set for every alternation {`broken`, `regression`, `investigate`, `repro`, `intermittent`, `flaky`, `why `, plus declared-overlap anchors `bug` (also covers "debug"), `root`, `fail` — accepted per the NEW-1 selectivity rule, bounded by the load test's anchor-passing-non-matching inputs}; Stop **queue-writer** `(?i)\b(as a workaround\|added a (guard\|retry)\|restart(ed\|ing)? (the\|it) (fixed\|resolved)\|clear(ed\|ing) the cache\|reset it and)\b`, delivered next tool event | D2-approved four-clause block + closure line + hard-problem-method.md pointer | nothing — pure addition, D2 kernel text unchanged (candidate 4-A; ops WIP) |
| `merge-protocol` | PreToolUse, Bash `\b(gh pr merge\|nedlern-pr-merge)\b`, anchor `pr merge` | sanctioned-path + silent-bypass warning + read-branch-policy-comment | kernel trim to the candidate-5 one-liner. **Single deliverer (d-review F-MERGE-DOUBLE): this row is the ONE teach; `no-raw-gh-pr-merge.sh` stays scoped to its delete-branch block, unchanged** |
| `review-trailer-protocol` | PreToolUse, Bash `\bgh pr (review\|comment)\b`, anchor `gh pr` | trailer protocol + trailer-as-audit.md pointer | same PR as `merge-protocol` (one candidate-5 atomic PR) |
| `use-nedlern-sync` | PreToolUse, Bash `\bgit (pull\|rebase)\b`, anchor `git p`/`git rebase` | one line | candidate-9 kernel trims (one PR for the trio) |
| `use-nedlern-push` | PreToolUse, Bash `\bgit push\b` minus `nedlern-push`, anchor `git push` | one line | ditto |
| `shell-edit-staleness` | PreToolUse, Bash `\b(perl\|sed)\s+-[A-Za-z]*i\b\|\bawk -i inplace\b` + repo-path redirects, anchor set {`sed -i`,`perl -p`} | the `git log -1 -- <file>` rule | ditto |
| `mail-arrival-protocol` | PostToolUse, tool `mcp__postal__check_mail` with ≥1 message, anchor `check_mail`; **plus `mail-pull.sh` consulting the SAME spacing row via a shared helper before appending its footer** (d-review F-CROSS-HOOK: one spacing decision, two readers — mail-pull reads/writes `(session, mail-arrival-protocol)` through the injector's store API) | the ~50-word comply/blocked-on-you/answer-on-the-wire card | candidate-8 kernel trims (three bullets); **first-arrival-per-session then 50k spacing — never per-delivery (boss)** |
| (rules file) `code-editing` | `.claude/rules/code-editing.md`, paths `**/*.py, **/*.sh, **/*.ts, **/*.js, scripts/**, .claude/hooks/**` | code-quality block + naming detail + both wiki pointers | candidate-7 kernel trims + wiki-editing heading-naming clause; native semantics accepted |
| (rules file) `working-drafts` | `.claude/rules/working-drafts.md`, paths `docs/working/**` | scratch-not-doctrine rule + the `Tracked-by:` GHI nudge line (orphaned-MD rule) | candidate-10 kernel trim; native semantics accepted |

Candidates 2 and 3 (already-hook-delivered lines) and 6 (rejected — stays kernel) produce no rows: 2/3 are payload audits + teach-string regression tests; any message gap ships with its kernel trim in one PR, otherwise the trims ride the kernel-rewrite PR. **Candidate-2 condition (Codex P2, PR #1978 review): the check-mail kernel line drops only when idle-wake/inbox-drain coverage is live** — `mail-pull.sh` is Stop-only and a dormant session surfaces no mail unaided; until minimal-idle-wake ([nedlern/nedlern#58](https://github.com/nedlern/nedlern/issues/58)) or equivalent ships, the kernel keeps a residual drain clause.

## Packaging — the atomic PR train

Per the atomic-across-layers doctrine (PR [#1978](https://github.com/nedlern/nedlern/pull/1978)): each PR carries a mechanism change AND the kernel trim it replaces. Order (each gated on the boss's per-piece review; ops co-authors all hook-touching PRs):

0. **[#1982](https://github.com/nedlern/nedlern/issues/1982) lands BEFORE or WITH PR-1** (d-review F-BUILD-ORDER): the measured 196k-word auto-read spam is the fleet's live injection baseline; fix it before stacking a new all-tools injector on top — it also cleans the latency picture PR-1 measures against.
1. **PR-1 (ops WIP, re-scoped): surface probes (UserPromptSubmit inject; Stop `additionalContext` behavior for the record) + injector core + bash pre-filter + spacing store + queue mechanism + `hard-problem-checklist` rows.** Pure addition, no trim. Merge-blocking tests: spacing suppress-then-refire, fail-open crash test, latency load test, two-session independence, retention prune, adversarial suite (below).
2. **PR-2: `postal-tier-table` row + kernel trim + card pointer update.**
3. **PR-3: `merge-protocol` + `review-trailer-protocol` rows + kernel trim** (no `no-raw-gh-pr-merge.sh` changes).
4. **PR-4: the raw-git trio rows + kernel trims.**
5. **PR-5: `code-editing` rules file + kernel trims + wiki-editing clause.**
6. **PR-6: `working-drafts` rules file + kernel trim + Tracked-by nudge.**
7. **PR-7 (audit-dependent): candidate-2/3 teach-string regression tests + any payload-gap fixes + their trims.**
8. **Kernel-rewrite PR (last):** pure KERNEL-row rewording, no mechanism changes — the one PR eligible for the [#1597](https://github.com/nedlern/nedlern/issues/1597) fast track, boss verbatim approval.

## CI checks (ops-lane, branch-policy additions)

1. **`Trigger:` section check (D4.6):** a PR removing lines from CLAUDE.md or a must-read page must carry a `Trigger:` section naming what now delivers each removed rule. Error level.
2. **Orphaned-MD check (boss, 2026-07-19):** a PR adding/modifying a work-bearing `docs/working/` MD (unchecked boxes, `next steps`, `#in-process`, `#tabled`, `TODO`) must reference a GHI in the file or PR body; `Record-only: no pending work` opts out. WARN level first; calibrated against the orphan-scan results (which found the discipline already near-universal — 1 live orphan in 202 files — supporting WARN as sufficient).

## The real-world audit loop — scheduled, skip-visible (d-review F-AUDIT)

The audit is the program's only decay check and gates all further kernel reduction, so it cannot be an unenforced human cadence. Mechanism: a **scheduled routine** (the repo's schedule/cron surface) fires per period (with each restructure wave, then monthly), runs the transcript scan for violations of trigger-delivered rules (the `/scan-errors` pattern), writes the ledger entry (reading-set ledger, R7), and **on a lapsed period with no entry raises a postal T1 alert to wiki** — a missed audit is visible, never silent. Owner: wiki executes; the scheduler enforces the cadence. Full demotion of dual-delivery rules (candidate 4's Option B harvest) is decided only on this evidence.

## Verification

- **Cooperative (per-PR, merge-blocking):** spacing suppress-then-refire; fail-open crash test; permission-outcome-unchanged test; two-session window independence; retention prune; queue-delivery test (Stop match → next-event delivery); teach-string regression tests (candidates 2/3).
- **Adversarial (PR-1, d-review F-ADVERSARIAL-TESTS):** 1 MB prompt through the UserPromptSubmit path; 1 MB agent output through the Stop matcher; malformed tool-input JSON; the regex-cost lint's own worst-case input; the p99 latency assertion under a 1,000-call load.
- **Program-level:** the scheduled audit loop above, plus the restructure wave-3 old→new diff proving every trimmed kernel clause survives at its named delivery (zero-doctrine-loss across map rows, rules files, and wiki pages).

## Rejected / non-goals (do not re-open without the boss)

- **Candidate 6:** the soft-block section stays kernel — counter-training content is KERNEL regardless of firing frequency (boss principle).
- **Mandatory MD-per-GHI:** declined — linkage + (if wanted) a *generated* open-work index instead.
- **New blocks:** the injector never blocks — structurally (fail-open contract), not just by policy.
- **Fresh-session evals as behavioral proof:** rejected at D4; they survive only as trigger smoke tests / surface probes.
- **Injecting at Stop or UserPromptSubmit without a passed probe:** queue-and-deliver-next-event is the default; unproven surfaces never carry payloads directly.

## Open questions (narrowed by /d-review round 1)

1. Map + payloads protected-path class (proposed free-logged) — ops+vp call.
2. Native `.claude/rules` dedup/spacing behavior — measure; outcome only affects whether candidates 7/10 accept per-touch semantics (they stay native either way).
3. The UserPromptSubmit probe outcome — determines whether `hard-problem-checklist`'s prompt leg injects directly or queue-delivers.
4. Codex-side delivery — parked to #1925 (D1); the map schema's `subject` field is runtime-neutral by design.

## See Also

- [trigger-first-instruction-delivery-design-cold-review.md](trigger-first-instruction-delivery-design-cold-review.md) — /d-review round 1 record (4 HIGH / 8 MED / 5 LOW, all incorporated in this revision).
- [trigger-first-instruction-delivery-thoughts.md](trigger-first-instruction-delivery-thoughts.md) — decision provenance: the ten dispositions, standing rules, audit summary.
- [trigger-first-instruction-delivery-scan-first-pass.md](trigger-first-instruction-delivery-scan-first-pass.md) — the 67-row scan backing every map row.
- [trigger-first-instruction-delivery-hook-spam-audit.md](trigger-first-instruction-delivery-hook-spam-audit.md) — the measured spam baseline.
