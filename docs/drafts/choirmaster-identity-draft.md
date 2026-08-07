# choirmaster identity file — draft for the user's walk

Proposed content for choirmaster's `CLAUDE.local.md`, the per-agent identity scope ruled on [nedschorus#45](https://github.com/nedschorus/nedschorus/issues/45): gitignored, one worktree, one agent. The project floor (`CLAUDE.md`) auto-loads beside it and carries everything shared, so this file says only what is true of choirmaster alone. Bare, per the skill-authoring checklist's Register rules.

Two step-6 decisions ride with this walk, because landing the file requires both:

1. **What choirmaster's directory is.** `launch-claude choirmaster` creates `~/agents/choirmaster` on the box. Proposal: make that directory a git worktree of the box's `~/Projects/nedschorus` clone, so the agent boots inside the repository with its identity file sitting untracked at the worktree root.
2. **Where `CLAUDE.local.md` gets ignored.** NC's `.gitignore` does not list it yet. Proposal: add it, so no agent's identity file can ever be committed by accident.

One resurrection flagged plainly: the commit-session-id line below was in the pre-walk settled list but is NOT in the walked floor — the admission walk did not carry it. It reappears here because it is operational and per-agent, which is what this file scopes to.
*Walk item 1 processed 2026-08-07 → KEPT (user: "I'm ok with a sanity check in the instructions"): the line stays as cheap traceability — every ruling in NC's record traces to its session through commit messages. A related idea raised and deliberately NOT adopted: a post-reboot footing check for booting agents. Premature twice over — no reboot has broken an agent (rules are added when problems repeat), and nothing relaunches agents unattended after a reboot, so the guarded scenario cannot occur. Its trigger: the day supervisors get unattended relaunch-after-reboot (a systemd unit), the footing check arrives paired with it.*

Everything below the line is the proposed file, verbatim.

---

```
# choirmaster

You are choirmaster, this project's primary agent. This file only says who you are; CLAUDE.md carries the rules.

Your work comes from your launch prompt first; when it directs nothing further, work the founding plan (docs/cross-project/nedschorus-founding-plan.md) and the open issues, and when neither decides your next act, ask the user.

Include your session id in commit messages.
```
