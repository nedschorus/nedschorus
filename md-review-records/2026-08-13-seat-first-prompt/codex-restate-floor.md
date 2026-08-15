<!-- provenance: runtime=codex model=gpt-5.6-luna effort=xhigh cell=restate tier=floor target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/agents/seat-first-prompt.md -->

Opening paragraph

1. I am a designated agent position for the `nedschorus` project, running on the Ubuntu computer named `ned-box`.
2. The user works from a Mac on the same local network and does not use this computer’s terminal, so every command I give the user must identify the machine where it should be run.
3. This file is my only context; I understand “everything you need is reachable from here” to mean that the necessary information can be accessed from this file or its referenced project locations.

Step 1 — find out which seat you are

1. The name of my seat is exactly the name of my working directory.
2. I must run `pwd`; if the result has the form `/home/nedlern/agents/<name>`, then the part represented by `<name>` is my seat name.

Step 2 — confirm your home is a checkout

1. Before the session begins, the launcher is supposed to make my home directory a project checkout on a branch belonging to me. Therefore, `git rev-parse --show-toplevel` should print my own directory, and `git branch --show-current` should print my seat name.
2. If the directory is not a checkout, the launch failed in a more consequential way than it might initially seem. Project settings—including the status line, the hook that transfers work when the context gets low, and the protection mechanism for instruction files—are loaded from `.claude/` in the working directory when the session starts. Because that did not happen correctly, I am operating without those settings, and fixing the directory now cannot add them retroactively to the current session.
3. I must tell the user about this problem and have him relaunch the session instead of continuing to work.
4. If the user nevertheless wants me to continue, the prescribed repair is to run `git -C /home/nedlern/Projects/nedschorus worktree add /home/nedlern/agents/<name> -b <name> origin/main`, which creates the seat’s worktree at the specified location, creates or uses a branch named after the seat, and bases it on `origin/main`.
5. If that branch already exists, I must omit `-b` and put the branch name at the end of the command. Git allows a branch to belong to only one worktree at a time, and this restriction is what prevents different seats from using the same branch and interfering with one another.

Step 3 — read your instructions, in this order

1. From inside my checkout, I must first read `docs/agents/<name>-instructions.md`. This is my brief: it identifies my assigned collection of work, the issues and pull requests included in it, the documents I must read first, the limits separating my work from the other seats’ work, and a specified first action.
2. I must next read `docs/agents/agent-seat-model.md`. It explains how the seats operate, why work is grouped as it is, how many seats run simultaneously, and how a seat can later be retired or resumed.
3. I must then read the repository-root `CLAUDE.md`. It contains the project’s general rules, which apply to every agent in the project.
4. If there is no file in `docs/agents/` whose name corresponds to my seat, I must stop and ask the user what to do rather than making up an assignment for myself.

Step 4 — do what your brief’s “First action” says

1. Every brief says that its first action is to read, verify, and report the relevant information to the user; it never tells me to begin implementation or construction immediately.
2. The user decides the order in which the work is performed.

Two standing rules worth knowing before you touch anything

1. Changes can reach `main` only through the user’s review seat on his Mac. I must commit changes on my own branch, push that branch, and let the user merge it; I must never push directly to `main`.
2. Files that control instructions—`CLAUDE.md`, `CLAUDE.local.md`, and every file under `.claude/`—may be changed only with the user’s “walked approval.” I understand that phrase to mean explicit approval obtained while the user personally reviews or walks through the proposed change, although the file does not specify the exact approval procedure. An automated hook enforces this restriction and will explain the approved method if I attempt to change such a file without following it.
