---
issue: "[Check every prerequisite of the fleet's programs before an agent-session starts](https://github.com/nedschorus/nedschorus/issues/1055)"
---

# Check every prerequisite of the fleet's programs before an agent-session starts

The fleet's programs depend on tools and settings on each machine, and almost none of those dependencies is checked before an agent-session starts. A missing one shows up late, in the middle of an agent's work, as an error from whichever program first needs it, and each such program has to carry its own message for the case. The proposal is one prerequisites program that `scripts/launch-claude-mac`, `scripts/launch-claude-ubuntu` and `nc-systems/handoff/handoff-supervisor.py` all run before they start an agent-session, and that refuses to start the agent-session, naming the fix, when a required prerequisite is missing.

## What is checked today

Read on main:

- `scripts/launch-claude-mac` checks three things before it starts an agent-session: that `tmux` is on PATH, that `claude` is on PATH, and that the handoff-supervisor file exists. Each refusal names its fix.
- `scripts/launch-claude-ubuntu` lists what it needs on ned-box in a comment, "Requires on the box: tmux, claude on ~/.local/bin, ~/Projects/nedschorus.", and checks none of the three before it starts.
- `nc-systems/handoff/handoff-supervisor.py` refuses to start when the agent command, `claude`, is not on PATH or its working directory does not exist. When its appended-system-prompt file is missing, it warns and starts the agent-session without that file.

Nothing checks, before an agent-session starts, any of these, each of which a program on main depends on:

- `python3`, which the git hooks, the handoff-supervisor and most of `scripts/` run under. `scripts/git-client-side-hooks/pre-push` checks for `python3` itself and, when it is missing, prints its own message and lets the push go ahead unchecked.
- `gh`, installed and able to authenticate, which every program that reads or writes pull requests and GitHub issues calls. An agent-session authenticates with its agent-seat's token when the launcher finds one, and otherwise with the machine's own `gh` login. No program on main runs `gh auth status` (searched: `git grep 'gh auth status' origin/main -- scripts nc-systems`).
- `jq`, which `scripts/merge-gate.sh` needs; that script checks for `jq` itself and refuses to run without it.
- ssh from the Mac to ned-box, which `scripts/launch-claude-ubuntu` and other Mac-side programs use.
- Each clone's `core.hooksPath` setting, which installs the git hooks in `scripts/git-client-side-hooks/`. The hooks' own comments say how to set it; no program checks that it is set (searched: `git grep -l hooksPath origin/main -- scripts nc-systems`, which finds three of the hooks and six test files, and no check).

## Why

When a prerequisite is missing, an agent learns of it only when some program fails mid-task. The program's message then has to explain a machine problem to an agent that cannot fix the machine, and every program that depends on the tool needs such a message of its own. Part two of GHI [Every refusal and warning a program hands an agent says why and what to do instead](https://github.com/nedschorus/nedschorus/issues/956) is removing the pre-push hook's own message for a missing `python3` for this reason: python3 is present on both machines, and one check at launch would cover the case better than a special message in each hook. A check at launch catches a missing prerequisite once, before any work starts, where the user can fix it.

## Related GHIs

Each of these covers one prerequisite or one start path, and the program this GHI proposes would sit beside or under them:

- GHI [Run named agents on the Ubuntu box, reachable from iTerm2 by name: launch-claude with tmux attach-or-create, and the migration it requires](https://github.com/nedschorus/nedschorus/issues/45): the launchers this program would gate.
- GHI [Fleet survives a machine restart without losing seat context: detect, hand off on notice, relaunch at boot, resume from transcript](https://github.com/nedschorus/nedschorus/issues/116): the restart path, which also starts agent-sessions.
- GHI [Tell the user when ned-box's claude is logged out or ned-box's subscription has run out](https://github.com/nedschorus/nedschorus/issues/337): one prerequisite, `claude` being usable.
- GHI [A crash-recovered ned-box seat runs without its own GitHub token, and the Mac launcher warns of a missing token when it only attaches](https://github.com/nedschorus/nedschorus/issues/759): one prerequisite, the agent-seat's GitHub token.

## Kinds of prerequisite the inventory covers

The list above is what a quick read of main found, not the whole set. The inventory covers every kind of prerequisite the fleet depends on, among them:

- the agent binaries, `claude`, which every agent-session runs, and `codex`, which the review programs such as `scripts/code-review-codex-cell.py` run, and that each is logged in;
- PATH setups, such as `~/.local/bin` coming first on the Mac;
- Unix tools the programs call, such as `tmux`, `jq` and `rg`;
- access to GitHub: `gh`, its authentication, and each agent-seat's token;
- Claude and Codex settings that programs rely on, in each machine's own configuration as well as the repository's `.claude/settings.json`;
- desktop tools the user works with, such as the Typora markdown editor and the iTerm2 terminal, which are recommended rather than required.

A recommended tool is not required: the check reports a missing one and still starts the agent-session.

## What the design must settle

The inventory will show that not every prerequisite should stop a start. Today a missing agent-seat token and a missing appended-system-prompt file each warn and carry on, by design. The design has to settle, for each prerequisite, whether a missing one refuses or warns. It also has to settle: which machine each check runs on, since `scripts/launch-claude-ubuntu` runs on the Mac and starts the agent-session on ned-box; whether a launcher's attach to a running agent-session runs the checks; how a refusal reaches the user when the handoff-supervisor starts an agent-session with nobody watching, as on a handoff or a restart at boot; whether a prerequisite only some agent-seats need, such as `jq` for merge-lane-2, is checked only for those agent-seats; what the prerequisites program itself runs under, so that a missing `python3` still gets a clean refusal; and how a Mac launch treats ssh to ned-box, since an agent-seat on the Mac keeps working when ned-box cannot be reached.

## Next action

Inventory every prerequisite the fleet's programs depend on, on each machine: each tool they call, with any minimum version they rely on, and each setting and credential. Record for each one which program needs it and how a missing one shows today, in a supporting document beside this GHI-MD, `docs/issues/1055-prerequisites-inventory.md`. Then design the prerequisites program from that inventory, and put the design to the user.
