# CLAUDE.md draft — for the boss's line-by-line admission

Candidate lines for NC's CLAUDE.md (founding plan step 2; inputs consolidated at [43-step-2-claude-md-inputs.md](../issues/43-step-2-claude-md-inputs.md); the seed draft was pre-calibration input, not the base). Each line faces the ruled tests: training covers it → cut; training silent → state plainly; training conflicts → NOT/DO override; actionable at a decision point; no unprobed system-prompt collision. No rationale, no history, present-tense truth. Admission marks land inline here; the admitted set becomes `CLAUDE.md` at the repo root.

---

# nedschorus

## Who and where

1. ~~One human — the boss — runs this project with the agents he launches. The boss reads every checked-in document.~~
   *admission 2026-08-06 → CUT: training covers working with a human; token waste.*
2. ~~Nothing gains automated review, publishing, or merge without the boss's explicit admission; automation is earned in steps: manual → script-you-run → automation.~~
   *admission 2026-08-06 → CUT.*
3. This repository is `~/Projects/nedschorus` (NC). The legacy system at `~/Projects/nedlern` is read-only reference: read anything there freely; NOT: write, commit, or run anything there.
   *admission 2026-08-06 → ADMITTED.*
4. ~~NC is not a rebuild of the legacy system: it starts from its own requirements, and legacy pieces enter only through the entry checkpoint.~~
   *admission 2026-08-06 → CUT (the import duty itself lives in the next line).*

## The entry checkpoint

5. ~~Every legacy import records in `entry-manifest.md` — in the same commit — the legacy SHA it came from, a one-line purpose, and the date.~~
   *admission 2026-08-06 → CUT from the floor, with a scope direction (boss): NC's goal is building a Claude–Codex–Python team, not learning from or reusing nedlern; beyond manually selected pieces, carefully tracking imports is a distraction. Reconciling the committed import-tracking doctrine (founding plan checkpoint + rewrite policy, gatekeeper import check) with that direction is nedschorus#44.*

## How to work

6. ~~Optimize for correctness and clarity over speed; work in small increments — one file, one decision at a time — walkable with the boss.~~
   *admission 2026-08-06 → CUT.*
7. ~~What can be code should be code; prose carries only judgment and meaning.~~
   *admission 2026-08-06 → CUT. Boss's operative bar, stated here: keep only lines clearly unique to this project or to his preferred methods of working — general good practice is training's job, and a ruling recorded in a GHI (#42 for this one) does not need a floor line.*
8. ~~Commit as you go. Infrequently-updated files check in immediately after update; append-type logs at a logical breakpoint — session end or next session start. Every commit message carries your session id.~~
   *admission 2026-08-06 → CUT. #25's floor-line destination died with this cut (recorded on the issue); the timing rule and session-id stamping are gatekeeper-automatable when built.*
9. ~~Any claim about code or a document names the revision it was verified against — a SHA, an issue, a quoted line. An absence claim carries its query and scope.~~
   *admission 2026-08-06 → CUT.*
10. Use standard SDLC terms.
    *admission 2026-08-06 → REVISED and admitted as the four words above; the never-invent clause cut. Boss's governing approach, stated here: simplify and streamline — add rules when problems repeat, never by speculating which rules might be needed.*

## Writing

11. Write durable artifacts for a reader with zero context: the subject identifiable, the why stated, actionable without the conversation that produced it.
    *admission 2026-08-06 → ADMITTED.*
12. Absolute imperatives like 'always' or 'never' can backfire in unforeseen conditions. Use them cautiously.
    *admission 2026-08-06 → REVISED and admitted in the boss's rewording (adds the positive instruction; supersedes the morning's input-1 text — noted in the #43 pair).*
13. When creating or inventing names, for directories, file names, globals, functions, etc., use explicit, clear and precise multi-part names. Check newly invented names with glob (for path names) or grep (for names in files). If these checks return collisions or ambiguity, choose a more explicit name, with 3 or 4 parts, not 1 or 2. If the thing you are naming already has a name in the project, use the existing name instead of inventing a new one.
    *admission 2026-08-06 → ADMITTED verbatim.*
14. ~~A skill answers three questions, worded as simply and plainly as reasonable: when to use it, what to do, how to do it. It contains clear instructions, never information whose point in the file is unclear; justifying data lives in the records and git history.~~
    *admission 2026-08-06 → CUT from the floor, RE-HOMED by boss ruling: this belongs in the skill-making governor, not CLAUDE.md — landed verbatim in docs/wiki/queue/skill-authoring-checklist.md (the current skill-build rulebook; a future skill-writing skill inherits it from there).*
15. Skills stay atomic: a skill references other MD files by explicit path, never by assumed knowledge; the shared concepts skills rely on are defined here, once.

## Sessions

16. Session start: read the handoff named by your launch prompt and take its next step.
17. Session end: write the handoff and check it in. Machine-local transcripts under `~/.claude/projects/` hold what handoffs do not; the handoff points there when needed.

## Definitions

18. The boss — the one human operator; every walk, admission, and ruling in these files means him.
19. Check-in — getting a change onto main. Through the git-gatekeeper once built; by plain commit and push until then.
20. GHI — a GitHub issue on nedschorus. The MD-GHI pair — an issue carrying the walkable state plus a `docs/issues/<n>-<slug>.md` document carrying the substance.
21. A walk — presenting material to the boss one item at a time, per `.claude/skills/walk-me-through/SKILL.md`.
