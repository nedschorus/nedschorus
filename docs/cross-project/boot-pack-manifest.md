---
status: draft
---

# Next-System Boot Pack — Manifest

**What this is:** the complete list of artifacts the successor project needs at boot, for the boss's markup BEFORE content is finalized. The flip decision (boss + new-vp, 2026-07-20 conversation): a fresh sibling repo, one human + one agent, the old project quiesced into a read-only quarry, components imported one at a time through an entry checkpoint. Nothing in this pack is doctrine until the boss has read it.

**Method note:** the pack is validated by BOOT-TESTING, not by review alone — launch a session in the new home, interrogate it (who are you; what are we building; what is the quarry and its rules; hand off and resume; run a design review on a sample), and every wrong or empty answer is a named gap. Fix, re-boot, repeat. The old system (this session's role) is the harness until a boot passes.

| # | Artifact | Purpose | Size target | Status |
|---|----------|---------|-------------|--------|
| 1 | Seed CLAUDE.md | The new project kernel: operating doctrine only, every line boss-admitted. Mission-state deliberately excluded (that is #2/#3's job) — conflating them is how the old kernel bloated. | ~20 lines | DRAFT — [seed-claude-md-draft.md](seed-claude-md-draft.md) |
| 2 | Charter | The mission: the flip, the quarry relationship, the quiesce plan for the old project, the re-automation ladder (manual → script-you-run → automation, each step earned). | 1 page | WRITTEN 2026-07-21 as the repo README (the one place humans and agents both look first) |
| 3 | Founding handoff | The life-file: current state, decisions made, next steps — written LAST, at cutover, so it captures true state. | 1-2 pages | to write at cutover |
| 4 | Three skills, dependency-trimmed | d-review (design review), walk-me-through (one-item-at-a-time presentation), handoff-lite (streamlined: write file, commit, done — no fleet machinery). Each current version references fleet doctrine that will not exist in the new home; import = trim or inline those references, not copy-paste. | 3 files | to port |
| 5 | Comms bridge spec | The two-log-file protocol between old and new systems, plus boss cut-and-paste as fallback. Logs are .gitignored (boss directive 2026-07-20); durable content promotes to committed files via handoff. | half page | DRAFT — [comms-bridge-spec.md](comms-bridge-spec.md) |
| 6 | Quarry guide | ~20 read-only pointers into the old system (wiki directories, session logs, key scripts, the decision-of-record file) so the new agent FETCHES knowledge on demand instead of pre-importing it. | 1 page | to write |
| 7 | Boot-test checklist | The interrogation script for #Method above — pass criteria for trusting a booted session with real work. | half page | to write |
| 8 | Entry manifest (empty at boot) | The append-only ledger every import crosses: source SHA in the quarry, one-line purpose, date. The system map that grows exactly as fast as the system, never behind it. | grows | created at repo init |
| 9 | Boss launcher scripts | The scripts the boss runs to start or restart the nedschorus agent: open an iTerm2 window at the new repo running `claude` (fresh start) or `claude --continue` (resume), restoring the boss's keyboard focus after the window opens. Quarry sources to crib: `scripts/iterm2-open-window.sh` (the focus-restore mechanism, boss-tested in nedlern/nedlern#1381) and the `claude` invocation inside `scripts/nedlern-reincarnate` — fleet machinery (worktree sync, postal names, grid layout, ping) removed. These are for the boss's hands, not the agent's; the zero-context-reader writing rule does not apply to them. | 1-2 small scripts | to write |

**Open items for the boss:** the project NAME (identity — his pick); which global `~/.claude/CLAUDE.md` treatment (near-empty, or per-project pointer); when to run the first boot test.

**What is deliberately NOT in the pack:** postal/comms daemons (the bridge replaces them until earned), hooks and gates (manual by construction), the wiki corpus (quarry, fetched on demand), the fleet (dormant; roles re-admitted one at a time when parallel execution is actually needed).
