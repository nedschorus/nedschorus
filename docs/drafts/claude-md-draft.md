# CLAUDE.md draft — for the boss's line-by-line admission

Candidate lines for NC's CLAUDE.md (founding plan step 2; inputs consolidated at [43-step-2-claude-md-inputs.md](../issues/43-step-2-claude-md-inputs.md); the seed draft was pre-calibration input, not the base). Each line faces the ruled tests: training covers it → cut; training silent → state plainly; training conflicts → NOT/DO override; actionable at a decision point; no unprobed system-prompt collision. No rationale, no history, present-tense truth. Admission marks land inline here; the admitted set becomes `CLAUDE.md` at the repo root.

---

# nedschorus

## Who and where

1. One human — the boss — runs this project with the agents he launches. The boss reads every checked-in document.
2. Nothing gains automated review, publishing, or merge without the boss's explicit admission; automation is earned in steps: manual → script-you-run → automation.
3. This repository is `~/Projects/nedschorus` (NC). The legacy system at `~/Projects/nedlern` is read-only reference: read anything there freely; NOT: write, commit, or run anything there.
4. NC is not a rebuild of the legacy system: it starts from its own requirements, and legacy pieces enter only through the entry checkpoint.

## The entry checkpoint

5. Every legacy import records in `entry-manifest.md` — in the same commit — the legacy SHA it came from, a one-line purpose, and the date.

## How to work

6. Optimize for correctness and clarity over speed; work in small increments — one file, one decision at a time — walkable with the boss.
7. What can be code should be code; prose carries only judgment and meaning.
8. Commit as you go. Infrequently-updated files check in immediately after update; append-type logs at a logical breakpoint — session end or next session start. Every commit message carries your session id.
9. Any claim about code or a document names the revision it was verified against — a SHA, an issue, a quoted line. An absence claim carries its query and scope.
10. Use standard SDLC terms; never invent vocabulary.

## Writing

11. Write durable artifacts for a reader with zero context: the subject identifiable, the why stated, actionable without the conversation that produced it.
12. Using absolute imperatives like 'always' or 'never' can backfire in unforeseen conditions.
13. When creating or inventing names, for directories, file names, globals, functions, etc., use explicit, clear and precise multi-part names. Check newly invented names with glob (for path names) or grep (for names in files). If these checks return collisions or ambiguity, choose a more explicit name, with 3 or 4 parts, not 1 or 2. If the thing you are naming already has a name in the project, use the existing name instead of inventing a new one.
14. A skill answers three questions, worded as simply and plainly as reasonable: when to use it, what to do, how to do it. It contains clear instructions, never information whose point in the file is unclear; justifying data lives in the records and git history.
15. Skills stay atomic: a skill references other MD files by explicit path, never by assumed knowledge; the shared concepts skills rely on are defined here, once.

## Sessions

16. Session start: read the handoff named by your launch prompt and take its next step.
17. Session end: write the handoff and check it in. Machine-local transcripts under `~/.claude/projects/` hold what handoffs do not; the handoff points there when needed.

## Definitions

18. The boss — the one human operator; every walk, admission, and ruling in these files means him.
19. Check-in — getting a change onto main. Through the git-gatekeeper once built; by plain commit and push until then.
20. GHI — a GitHub issue on nedschorus. The MD-GHI pair — an issue carrying the walkable state plus a `docs/issues/<n>-<slug>.md` document carrying the substance.
21. A walk — presenting material to the boss one item at a time, per `.claude/skills/walk-me-through/SKILL.md`.
