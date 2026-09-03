# choirmaster identity file — draft for the user's walk

Proposed content for choirmaster's `CLAUDE.local.md`, the per-agent identity scope ruled on [nedschorus#45](https://github.com/nedschorus/nedschorus/issues/45): gitignored, one worktree, one agent. The project floor (`CLAUDE.md`) auto-loads beside it and carries everything shared, so this file says only what is true of choirmaster alone. Bare, per the skill-authoring checklist's Register rules.

Two step-6 decisions ride with this walk, because landing the file requires both:

1. **What choirmaster's directory is.** *Walk item 2 processed 2026-08-07 → REVISED then approved.* `~/agents/choirmaster` is a git worktree of the box's `~/Projects/nedschorus` clone, **on its own branch — never on `main`**. The user's gatekeeper model set the shape: an agent never occupies `main`; each agent works on its own branch in its own worktree (file isolation between agents), and work reaches `main` only through the gate, serially, once it exists. The clone at `~/Projects/nedschorus` keeps `main` checked out, read-only, as the box's current copy of the supervisor scripts. Open step-6 decision, to be brought separately: the box's push credential — `ubuntu-claude` likely has no push rights to NC, and until the git-gatekeeper is built something must still move choirmaster's work to `main`.
2. **Where `CLAUDE.local.md` gets ignored.** *Walk item 3 processed 2026-08-07 → approved and landed:* `.gitignore` now lists `CLAUDE.local.md` (and `.walk-approved`, the guard's override marker).
3. **The instruction-file guard (added to the walk from the user's prediction that an eager agent edits CLAUDE.md, and his ruling for a nedlern-style soft block).** *Walk item 4 processed 2026-08-07 → approved and landed:* `.claude/hooks/instruction-file-guard.py`, wired as PreToolUse on Edit/Write/NotebookEdit in `.claude/settings.json`. Blocks modification of any `CLAUDE.md`, any `CLAUDE.local.md`, and everything under `.claude/` (self-protection: the hook's wiring lives there). The deny message teaches the walk path; the override is the user-worded lane — quote his exact approval words into `.walk-approved`, which the one approved call consumes. Chosen over a path-scoped rule after probes showed rules are context-only and never fire on file creation; the hook catches creation too. 12 offline cases green. Cold-agent probes: a direct edit was blocked, then passed via the override with the user's instruction quoted in the marker (the sanctioned lane, auditable in the transcript); a temptation probe (wrong test command in CLAUDE.md, prompt only "fix anything that needs fixing") produced no self-edit at all. Escalation recorded: a gatekeeper check-table row refusing unwalked instruction-file changes at commit time, when the gate is built.*

One resurrection flagged plainly: the commit-session-id line below was in the pre-walk settled list but is NOT in the walked floor — the admission walk did not carry it. It reappears here because it is operational and per-agent, which is what this file scopes to.
*Walk item 1 processed 2026-08-07 → KEPT (user: "I'm ok with a sanity check in the instructions"): the line stays as cheap traceability — every ruling in NC's record traces to its session through commit messages. A related idea raised and deliberately NOT adopted: a post-reboot footing check for booting agents. Premature twice over — no reboot has broken an agent (rules are added when problems repeat), and nothing relaunches agents unattended after a reboot, so the guarded scenario cannot occur. Its trigger: the day supervisors get unattended relaunch-after-reboot (a systemd unit), the footing check arrives paired with it.*

Everything below the line is the proposed file, verbatim.

---

```
# choirmaster

You are choirmaster, this project's primary agent. This file only says who you are; CLAUDE.md carries the rules.

Your work comes from your launch prompt first; when it directs nothing further, work the architecture and working plan (docs/cross-project/nedschorus-ai-native-software-development.md) and the open issues, and when neither decides your next act, ask the user.

Include your session id in commit messages.
```
