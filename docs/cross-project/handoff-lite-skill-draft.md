---
status: draft
---

# handoff-lite — the successor project's handoff skill (draft for the boss's markup)

**Design constraints:** one human + one agent, one repo, no fleet, no postal, no task stores, no auto-push machinery. The whole procedure must survive being run at 5% context by a tired agent — so it is one file, four sections, three commands, nothing conditional.

---

## SKILL.md content (what ships in the new repo at `.claude/skills/handoff/SKILL.md`)

# Handoff — write the file that lets your successor continue

Your successor starts with zero memory of this session. The handoff file is the only continuity. Write it before context runs out — when the boss says "handoff," or when you judge you are near your limit, whichever comes first.

## The one file

Overwrite `HANDOFF.md` at the repo root. Git history is the archive of prior handoffs — never a dated copy, never a second file.

Four sections, every time, complete sentences a stranger can act on:

1. **State** — what is true right now: what shipped this session (with SHAs), what is half-done and exactly where it stands, what is broken and known.
2. **Decisions** — what the boss ruled this session, verbatim where it matters, so nothing gets re-litigated. Mark anything proposed-but-not-confirmed as exactly that.
3. **Next** — the successor's first actions, in order, literal enough to execute without judgment. If the order matters, say why.
4. **Traps** — anything that will look wrong but is right, or look fine but is wrong. One line each.

## The three commands

```bash
git add HANDOFF.md
git commit -m "handoff: <one-line state summary>"
git push
```

## Rules

- NOT: summarize or compress to save space — the successor has a fresh context window; length is free, lost facts are not.
- NOT: paste live status that will rot (test counts, "X is running"); link or name the thing instead.
- NOT: list what you finished beyond State's one-line-with-SHA — git log is the record.
- If a bridge log entry (see comms-bridge-spec) contains something durable, promote it into the handoff NOW — logs are gitignored and will not survive.
- The handoff is done when you can answer: could a stranger with only this file, CLAUDE.md, and the charter continue the work? If no, the missing piece goes in.

---

## What was deliberately cut from the old system's handoff skill (for the record, so the cuts are auditable)

Mail drain (no postal) · session-id scripts and resume pointers (the harness's own resume covers it; if not, the boss relaunches fresh — the file IS the continuity) · task-store carryover procedure (no task stores yet) · overflow files and safe-pattern staging (one file, one repo) · co-author/session trailers (one agent; git author is identity) · size-cap debates (no cap; clarity wins) · the prior-handoff audit step (the successor reads HANDOFF.md as its first act per CLAUDE.md — auditing is its natural next move, not a ceremony).

Each cut is a re-admission candidate the day the system grows the thing that needed it.
