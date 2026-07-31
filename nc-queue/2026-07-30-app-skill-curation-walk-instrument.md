# App-skill curation walk — instrument (boss-commissioned 2026-07-30)

Scope: the skills visible in NC project sessions of the Claude Code app — 47 total, from the `claude-plugins-official` marketplace bundles (engineering, design, productivity, anthropic-skills, cowork-plugin-management), app built-ins, and one user skill. Purpose: rule keep / drop / maybe per skill by judgment now (no significant project runs yet, so usage data cannot exist; routing measurement resumes when NC's own skills boot). Ruling scope is **NC project sessions only** — nothing here uninstalls anything globally. Mechanism at execution: per-project plugin enablement in `.claude/settings.json` (the update-config skill handles it); app built-ins are mostly not removable and are inventoried for the field pin only.

**How to walk it:** groups A, B, D are ruled as blocks with a veto pass (name any skill to pull out); group C is the walk's real time. One line per skill: what it is → REC → reason.

**Prior grades carried in** (marked ◆): the skill-creation deep-dive (archived 2026-07-22) — skill-creator is the only official skill shipping a measurement loop, its eval machinery read-for-ideas-only; the doc skills are real systems by the files-not-lines filter; description budget is the true constraint (every skill dilutes every other's routing claim). The COPS delta packet (archived 2026-07-23) grades the NC candidates' *sources*, which fixes which engineering-bundle skills collide with planned NC siblings (#15–#23).

## Group A — obvious keep (block rule + veto pass) — processed 2026-07-30 → KEEP, all seven, boss-approved, no vetoes

- **anthropic-skills:skill-creator** — skill authoring + eval harness. KEEP — ◆ the strongest official skill; the reference for building NC's own. Routing collision with NC skill-building practice: none yet.
- **anthropic-skills:docx / pdf / pptx / xlsx** (4) — document read/write systems. KEEP — ◆ real systems (50–60 files each); document work recurs and NC will never build siblings.
- **walk-me-through** (user skill) — one-item-at-a-time presentation. KEEP — in active use; NC's own future version supersedes it only at boot.
- **update-config** — harness/settings editor. KEEP — operational necessity; it is the mechanism this walk's own rulings execute through.

## Group B — obvious drop from NC sessions (block rule + veto pass) — processed 2026-07-30 → DROP fourteen, boss-ruled, after one catch: the block was mis-scoped as "purely visual." Boss catch: ux-copy (error messages) and research-synthesis (qualitative synthesis) are not visual-only. Rulings: **ux-copy = extract-then-drop** — four refusal-copy heuristics extracted to the pair #3 packet (B5); the skill itself drops with its bundle. research-synthesis drops on corrected grounds (no matching inputs — NC has no interviews/tickets/NPS), not "it's visual." Mechanism note at execution: drops apply per-project; morning + setup-cowork ride inside the anthropic-skills bundle whose other members are Group-A keeps — if per-skill disable is unavailable, they are ruled-dropped with a recorded mechanism gap (harmless per the lazy-load ruling).

- **design:accessibility-review / design-critique / design-handoff / design-system / research-synthesis / user-research / ux-copy** (7) — UX/design workflows. DROP — no design-surface work exists or is planned in NC; zero expected triggers, pure description-budget weight.
- **cowork-plugin-management:cowork-plugin-customizer / create-cowork-plugin** (2) — Cowork plugin authoring. DROP — wrong product surface for NC.
- **anthropic-skills:setup-cowork** — Cowork onboarding. DROP — same reason.
- **anthropic-skills:morning** — personal morning brief. DROP from NC scope — personal-assistant surface, not project work (remains available outside NC sessions).
- **productivity:memory-management / start / task-management / update** (4) — TASKS.md/CLAUDE.md task-and-memory system. DROP — collides head-on with NC's own continuity doctrine (handoff files, queues, GHI pairs); two memory systems is how records fork.

## Group C — contested middle: the walk's real time (rule one by one)

Engineering bundle — each useful *today*, each colliding with a planned NC sibling *later*. Standing pattern to consider per skill: keep until the NC sibling boots, then the sibling's near-miss routing tests (with this skill present) decide which yields.

- **engineering:code-review** — PR/diff review workflow. processed 2026-07-30 → **DROP** (boss-confirmed) — superseded by review-change [#22](https://github.com/nedschorus/nedschorus/issues/22): the NC adaptation is already planned (task 2) from stronger graded donors (OpenAI review-agent spine, Google criteria); this skill adds nothing as donor and squats on #22's trigger territory. Interim reviews stay boss-walked. Pattern set for Group C: the question is "does an NC sibling's plan already subsume it?"
- **engineering:testing-strategy** — test strategy/plan design. processed 2026-07-30 → **DROP** (boss-approved) — subsumed by write-test-plan [#18](https://github.com/nedschorus/nedschorus/issues/18) (first scheduled pull; contract + dogfood + taxonomy + riders all exist); this skill is the weakest-graded capability class (generic strategy prose, no oracle/red discipline) squatting on the highest-value NC trigger territory. Nothing survives as donor.
- **engineering:debug** — structured debugging workflow. processed 2026-07-30 → **KEEP with named eviction** (boss-approved) — the one real interim window: diagnose-failure [#21](https://github.com/nedschorus/nedschorus/issues/21) builds only "when the project has a diagnosis task" while the gatekeeper build will produce real bugs before then; no doctrine conflict (same donor family; the breaker ladder counts fix attempts from outside any debugging procedure); collision cost zero until #21 boots. Eviction: #21's near-miss routing tests run with this skill present; the loser leaves.
- **engineering:architecture** — ADR creation/evaluation. processed 2026-07-30 → **DROP + extract** (boss-approved) — the design-evaluation half is subsumed by design-change [#17](https://github.com/nedschorus/nedschorus/issues/17); the ADR *form* (the real complement — NC's append-only decisions layer needs exactly this shape) extracted to `docs/wiki/queue/adr-form-extract.md` for the md-write build or wiki doctrine, with a claims-line addition per the SSOT rulings.
- **engineering:system-design** — system/API/data-model design. processed 2026-07-30 → **DROP** (boss-ruled) — fully subsumed by design-change [#17](https://github.com/nedschorus/nedschorus/issues/17) (code-architect spine + boss terminal states); no extractable remainder; vaguest trigger in the bundle, the exact class the description-budget finding warns degrades routing.
- **engineering:tech-debt** — debt audit/prioritization. processed 2026-07-30 → **DROP** (boss-ruled) — contradicted by ruled doctrine, not merely subsumed: the accumulate-then-triage model lost to detect-at-the-mechanism (usage/posits [#35](https://github.com/nedschorus/nedschorus/issues/35), design-change sweep, patch-cycle tripwire); every legitimate concern has a stronger NC owner.
- **engineering:documentation** — docs/README/runbook writing. processed 2026-07-30 → **DROP** (boss-ruled) — subsumed by the imminent md-write founding build (step 1, skills-first): zero-context-reader discipline and artifact-lifecycle rules own this whole territory; genre checklists are generic filler, no extract.
- **engineering:deploy-checklist** — pre-deploy verification. processed 2026-07-30 → **DROP** (boss-ruled, C8-C10 block) — no deploy surface by explicit ruling (scope ends at main); revisit trigger = first long-running process (same trigger gating release-transition).
- **engineering:incident-response** — incident triage/postmortem. processed 2026-07-30 → **DROP** (boss-ruled, C8-C10 block) — no production surface; the blameless mechanism already sharper in the interrogation protocol (#20 packet); revisit at first real incident, re-judged against learn-from-failure, never restored by default.
- **engineering:standup** — standup generation from activity. processed 2026-07-30 → **DROP** (boss-ruled, C8-C10 block) — no standup audience; state reporting served structurally by handoff + queue-depth scrub; no revisit trigger (a one-off ask, not a skill).

## Group D — app built-ins: field pin only — processed 2026-07-31 → approved: block no-action on the 13 built-ins (slash-command-shaped, low collision risk, included in the field pin so #22's routing tests see them); stragglers ruled: **anthropic-skills:schedule DROP** (live name collision with the built-in `schedule`; the built-in survives and suffices), **anthropic-skills:consolidate-memory KEEP** (operates on the app memory store NC sessions actually use; no sibling planned).

- **simplify / review / security-review / init** — app-side code-review/init commands. NOTE — overlap group C's territory; app-level, not plugin-removable; included in the field pin so routing tests see them.
- **loop / schedule / run / dataviz / artifact-design / artifact-capabilities / claude-api / keybindings-help / fewer-permission-prompts** — operational app machinery. KEEP (no action available) — harmless, occasionally used. Name collision noted: `schedule` (built-in) vs `anthropic-skills:schedule` — one more reason the anthropic-skills copy adds nothing; it rides Group B's veto pass if the boss wants it dropped too.
- **productivity:start** is listed in Group B with its bundle; `consolidate-memory` (anthropic-skills) — memory-file maintenance. MAYBE-DROP — same two-memory-systems argument as the productivity bundle, but it operates on the app's own memory directory, which NC sessions do use; cheap to keep, cheap to drop.

## Pinned field inventory (for future routing tests)

47 skills; sorted-name digest `sha256:e6c477cc3a7e43c6…` (first 16 hex; full list below is the digest's input, one name per line, sorted). Description-set digest `sha256:326676fa40d0cbae…` — input: one line per skill, `<name>: <description>` exactly as the session skill listing renders it, sorted by name, LF-joined, UTF-8, computed over the 47 descriptions as loaded 2026-07-30. A future routing test records both digests; a name mismatch means the pile was renamed or resized, a description mismatch with matching names means the pile was re-described — either stales the test's verdict.

```
anthropic-skills:consolidate-memory  anthropic-skills:docx  anthropic-skills:morning
anthropic-skills:pdf  anthropic-skills:pptx  anthropic-skills:schedule
anthropic-skills:setup-cowork  anthropic-skills:skill-creator  anthropic-skills:xlsx
artifact-capabilities  artifact-design  claude-api
cowork-plugin-management:cowork-plugin-customizer  cowork-plugin-management:create-cowork-plugin
dataviz  design:accessibility-review  design:design-critique  design:design-handoff
design:design-system  design:research-synthesis  design:user-research  design:ux-copy
engineering:architecture  engineering:code-review  engineering:debug
engineering:deploy-checklist  engineering:documentation  engineering:incident-response
engineering:standup  engineering:system-design  engineering:tech-debt
engineering:testing-strategy  fewer-permission-prompts  init  keybindings-help  loop
productivity:memory-management  productivity:start  productivity:task-management
productivity:update  review  run  schedule  security-review  simplify
update-config  walk-me-through
```

Descriptions are as loaded in the 2026-07-30 session; they are as rendered in the app session's own skill listing, not duplicated here and with no verified filesystem path — `~/.claude/plugins/marketplaces/claude-plugins-official/` does NOT contain these bundles (verified 2026-07-30 by listing that marketplace: it holds a different plugin set), so description-digest re-verification must run from inside an app session — the name digest is the change detector, and a name-stable description change is caught by re-digesting descriptions at test time.

## Walk shape

Four items: (1) Group A block + veto · (2) Group B block + veto · (3) Group C, ten skills one at a time · (4) Group D block + the two flagged stragglers. Rulings execute via update-config in the same session they land.

## Execution (for new-vp at landing) — walk complete 2026-07-31

**Tally over 47:** 9 keep (Group A's 7 + engineering:debug with eviction at #21 boot + consolidate-memory) · 25 drop (design 7 incl. ux-copy extract-then-drop, cowork 2, setup-cowork, morning, productivity 4, engineering 9 — two with extracts: B5 refusal-copy → pair #3 packet, ADR form → wiki queue, anthropic-skills:schedule) · 13 built-ins no-action (field-pinned).

**Settings edit (NC project scope):** disable plugins `design`, `cowork-plugin-management`, `productivity` from `claude-plugins-official` in the project settings (update-config mechanism: `enabledPlugins` / per-plugin disable in `.claude/settings.json`).

**Mechanism gaps — RESOLVED at enactment (2026-07-31, commit 19d8d49):** the settings schema supports per-skill disable (`skillOverrides`: `"<skill-name>": "off"`), so both gaps below are moot — the rulings execute verbatim: `engineering` stays enabled with its nine drops individually off and `debug` surviving; `anthropic-skills` stays enabled with its three drops individually off. Enacted in `.claude/settings.json` (bundle-level `enabledPlugins: false` for design/cowork/productivity + twelve `skillOverrides` entries). A live app session picks this up at its next load boundary (restart or new session), not mid-session. Original gap text kept below for the record:

**Mechanism gaps as flagged at walk close (superseded):** (1) `engineering` bundle — 9 drops but debug keeps; if per-skill disable is unavailable, recommendation: disable the whole bundle and let debug's eviction arrive early (#21's donor material lives in the source-evidence archive; the 9 drops outweigh one interim keep) — boss confirms at landing. (2) `anthropic-skills` bundle — keeps outweigh its three drops (morning, setup-cowork, schedule); bundle stays enabled, the three ride as ruled-dropped-with-mechanism-gap (harmless per the lazy-load ruling; revisit if per-skill disable exists).
