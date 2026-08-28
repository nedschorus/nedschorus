# draft-md: the write hook that routes durable-file drafting through the skill

Queued for build after the `draft-md` skill exists (specification: `docs/issues/142-draft-md-skill-design.md`, § "The sequence", the paragraph "How the skill gets invoked"). User-ruled 2026-08-27: a CLAUDE.md line will not make agents invoke the skill; a PreToolUse hook might, if it does not over-trigger.

**What it does.** A PreToolUse hook on Write, Edit, and NotebookEdit, in the pattern of the three guards in `.claude/hooks/` (soft block; a deny message that teaches the sanctioned path; the shared approval-marker lane in `guard_approval_marker.py`). When the session itself writes a durable file, the hook soft-blocks and says: draft this under `draft-md`, or approve the direct write. Reason: the moment the skill must fire is the moment the session is about to write, mid-task, when skill descriptions are the last thing in mind; a hook runs at that moment deterministically.

**Scope — where it fires.** Paths under `docs/issues/` (not `docs/issues/queue/`), `docs/wiki/` (not `docs/wiki/queue/`), and `.claude/skills/*/SKILL.md`. Never `md-review-records/` or other gitignored working material.

**Controls against over-triggering, in order of how much they buy.**
1. A size floor: an Edit that changes fewer words than a sentence — a path, a date, a rename, a typo; the design notes' "mechanical edits" — passes untouched. Whether the floor is one sentence or one paragraph is set by watching false triggers for a week after the hook lands.
2. A content-hash marker: when `draft-md`'s fork writes a file, the skill records the file's content hash in the marker lane; a write that matches a recorded hash (the fork's own write, or a revision through the skill) passes, so one file is never asked for twice.
3. The approval marker the other guards use, for a direct write the user has approved.

**Tests before it lands** (the skill-authoring checklist's false-trigger discipline): near-miss negatives — a one-word fix in a design, a queue file, a records file, the fork's own write — must pass; a Write of a new design and an Edit that adds a paragraph to a wiki page must block.

**Next action:** build after the skill's first use, when the marker the skill sets exists to test against.
