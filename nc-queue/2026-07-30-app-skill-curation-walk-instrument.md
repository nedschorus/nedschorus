# App-skill curation walk — instrument (boss-commissioned 2026-07-30)

Scope: the skills visible in NC project sessions of the Claude Code app — 47 total, from the `claude-plugins-official` marketplace bundles (engineering, design, productivity, anthropic-skills, cowork-plugin-management), app built-ins, and one user skill. Purpose: rule keep / drop / maybe per skill by judgment now (no significant project runs yet, so usage data cannot exist; routing measurement resumes when NC's own skills boot). Ruling scope is **NC project sessions only** — nothing here uninstalls anything globally. Mechanism at execution: per-project plugin enablement in `.claude/settings.json` (the update-config skill handles it); app built-ins are mostly not removable and are inventoried for the field pin only.

**How to walk it:** groups A, B, D are ruled as blocks with a veto pass (name any skill to pull out); group C is the walk's real time. One line per skill: what it is → REC → reason.

**Prior grades carried in** (marked ◆): the skill-creation deep-dive (archived 2026-07-22) — skill-creator is the only official skill shipping a measurement loop, its eval machinery read-for-ideas-only; the doc skills are real systems by the files-not-lines filter; description budget is the true constraint (every skill dilutes every other's routing claim). The COPS delta packet (archived 2026-07-23) grades the NC candidates' *sources*, which fixes which engineering-bundle skills collide with planned NC siblings (#15–#23).

## Group A — obvious keep (block rule + veto pass)

- **anthropic-skills:skill-creator** — skill authoring + eval harness. KEEP — ◆ the strongest official skill; the reference for building NC's own. Routing collision with NC skill-building practice: none yet.
- **anthropic-skills:docx / pdf / pptx / xlsx** (4) — document read/write systems. KEEP — ◆ real systems (50–60 files each); document work recurs and NC will never build siblings.
- **walk-me-through** (user skill) — one-item-at-a-time presentation. KEEP — in active use; NC's own future version supersedes it only at boot.
- **update-config** — harness/settings editor. KEEP — operational necessity; it is the mechanism this walk's own rulings execute through.

## Group B — obvious drop from NC sessions (block rule + veto pass)

- **design:accessibility-review / design-critique / design-handoff / design-system / research-synthesis / user-research / ux-copy** (7) — UX/design workflows. DROP — no design-surface work exists or is planned in NC; zero expected triggers, pure description-budget weight.
- **cowork-plugin-management:cowork-plugin-customizer / create-cowork-plugin** (2) — Cowork plugin authoring. DROP — wrong product surface for NC.
- **anthropic-skills:setup-cowork** — Cowork onboarding. DROP — same reason.
- **anthropic-skills:morning** — personal morning brief. DROP from NC scope — personal-assistant surface, not project work (remains available outside NC sessions).
- **productivity:memory-management / start / task-management / update** (4) — TASKS.md/CLAUDE.md task-and-memory system. DROP — collides head-on with NC's own continuity doctrine (handoff files, queues, GHI pairs); two memory systems is how records fork.

## Group C — contested middle: the walk's real time (rule one by one)

Engineering bundle — each useful *today*, each colliding with a planned NC sibling *later*. Standing pattern to consider per skill: keep until the NC sibling boots, then the sibling's near-miss routing tests (with this skill present) decide which yields.

- **engineering:code-review** — PR/diff review workflow. MAYBE-KEEP — the founding plan names "the code-review skill" as choirmaster's likely task 2; this is the interim stand-in and the routing-collision test case for review-change ([#22](https://github.com/nedschorus/nedschorus/issues/22)).
- **engineering:testing-strategy** — test strategy/plan design. MAYBE-DROP — collides with write-test-plan ([#18](https://github.com/nedschorus/nedschorus/issues/18)), the first NC pull; ◆ COPS graded generic strategy prose the weakest capability class; NC's contract is stronger than this skill's register.
- **engineering:debug** — structured debugging workflow. MAYBE-KEEP — diagnose-failure ([#21](https://github.com/nedschorus/nedschorus/issues/21)) is unbuilt and unpulled; useful until then; re-test at its boot.
- **engineering:architecture** — ADR creation/evaluation. MAYBE — pairs with design-change ([#17](https://github.com/nedschorus/nedschorus/issues/17)); ADR form is close to NC's decisions-append-only layer; could inform rather than collide.
- **engineering:system-design** — system/API/data-model design. MAYBE-DROP — same territory as design-change with a vaguer trigger; two design skills dilute each other before NC's third arrives.
- **engineering:tech-debt** — debt audit/prioritization. MAYBE-DROP — NC's stance is the usage/obsolescence program (#35 + the design-change sweep), which contradicts generic debt-audit framing.
- **engineering:documentation** — docs/README/runbook writing. MAYBE — NC's md-write covers durable-artifact writing with the zero-context rule; this is the generic sibling; likely yields at boot.
- **engineering:deploy-checklist** — pre-deploy verification. MAYBE-DROP — NC has no deploy surface (scope ends at main) until a long-running process exists; trigger named for revisit.
- **engineering:incident-response** — incident triage/postmortem. MAYBE-DROP — no production surface yet; the blameless-postmortem mechanism NC wants is already encoded in the interrogation protocol (#20 packet); revisit at first real incident (learn-from-failure's own trigger).
- **engineering:standup** — standup generation from activity. MAYBE-DROP — NC's handoff + queue-depth scrub already reports state; no audience for standups.

## Group D — app built-ins: field pin only (block rule; mostly not removable)

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

Descriptions are as loaded in the 2026-07-30 session; they live in the app's plugin cache (`~/.claude/plugins/marketplaces/claude-plugins-official/`), not duplicated here — the name digest is the change detector, and a name-stable description change is caught by re-digesting descriptions at test time.

## Walk shape

Four items: (1) Group A block + veto · (2) Group B block + veto · (3) Group C, ten skills one at a time · (4) Group D block + the two flagged stragglers. Rulings execute via update-config in the same session they land.
