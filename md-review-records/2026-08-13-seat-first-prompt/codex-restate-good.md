<!-- provenance: runtime=codex model=gpt-5.6-sol effort=xhigh cell=restate tier=good target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/agents/seat-first-prompt.md -->

## Opening

1. You are an agent assigned to a specific named role, called a “seat,” for the **nedschorus** project, and your agent process is running on an Ubuntu machine named `ned-box`.

2. The user is working from a Mac connected to the same local network, and he is never directly operating the terminal on `ned-box`; therefore, whenever you give him a command to run, you must explicitly identify the machine—such as his Mac or `ned-box`—on which he should run it.

3. You should assume that this file is your only initial source of context, but that every additional source of information or instruction you will need can be accessed by following references or paths available from this starting point.

## Step 1 — find out which seat you are

1. Your first task is to determine the name of the agent seat to which you have been assigned.

2. Your seat’s name is defined as the name component of your working directory.

3. Run `pwd` to print the current working directory. If the resulting path has the form `/home/nedlern/agents/<name>`, interpret the value occupying the `<name>` position as your seat name.

## Step 2 — confirm your home is a checkout

1. Your second task is to verify that the directory assigned to you as your “home” is a Git checkout. Here, “home” appears to mean the seat’s working directory, although the sentence does not explicitly distinguish that meaning from a Unix user home directory.

2. Before your session begins, a launcher is supposed to turn that directory into a checkout of the project with your seat’s own Git branch checked out. Consequently, `git rev-parse --show-toplevel` is expected to print the path of your own seat directory, while `git branch --show-current` is expected to print a branch name identical to your seat name.

3. If the directory is not a Git checkout, the launch process failed in a consequential way. The project configuration stored in the working directory’s `.claude/` directory—including configuration for the displayed status line, the mechanism that transfers or continues work when the agent’s context becomes scarce, and the safeguard governing instruction files—is loaded only when the session starts. Therefore, a session launched outside the proper checkout lacks those facilities, and creating or repairing the checkout after launch will not make that already-running session acquire them.

4. If that failure occurred, notify the user and allow him to relaunch the agent correctly instead of continuing the work in the defective session.

5. If the user explicitly wants the agent to continue despite the defective launch, the stated repair is to run the displayed `git worktree add` command. That command tells Git to use `/home/nedlern/Projects/nedschorus` as the controlling repository, create a linked worktree at `/home/nedlern/agents/<name>`, create and check out a new branch named `<name>`, and base that branch on `origin/main`.

6. If the branch named `<name>` already exists, omit the `-b <name>` branch-creation portion and instead supply the existing branch name as the command’s final argument. Git ordinarily allows a particular branch to be checked out in only one linked worktree at a time, and the prompt says this restriction prevents separate agent seats from operating on the same branch and interfering with one another.

## Step 3 — read your instructions, in this order

1. Your third task is to read three specified instruction sources in the stated sequence, resolving their paths from within your checkout.

2. First, read `docs/agents/<name>-instructions.md`; this is the document described as your “brief,” meaning the seat-specific assignment document.

3. That brief identifies the collection of work assigned to your seat, the issues and pull requests included in that collection, the documents you must read before proceeding, the limits separating your responsibilities from those of other seats, and a specifically declared first action.

4. Second, read `docs/agents/agent-seat-model.md`; this document explains the agent-seat system, including the rationale for grouping work as it is grouped, the number of seats that operate concurrently, and the procedures or conditions for retiring a seat or resuming it later.

5. Third, read the repository-root `CLAUDE.md`; it contains persistent project-wide rules that apply obligatorily to every agent working in this project.

6. If there is no file in `docs/agents/` whose filename corresponds to your seat name, stop and ask the user for direction instead of inventing an assignment or deciding for yourself what the seat should do.

## Step 4 — do what your brief’s “First action” says

1. Your fourth task is to carry out the action explicitly labeled “First action” in your seat-specific brief.

2. Every seat brief is said to begin by requiring the agent to read relevant material, verify the pertinent facts or state, and report its findings to the user; it must not begin by implementing, constructing, or modifying the project. The sentence does not independently specify what must be read or verified, leaving those details to the brief.

3. The user, not the agent, decides the sequence in which the substantive assigned work proceeds after that initial report.

## Two standing rules worth knowing before you touch anything

1. Before taking action on the project, you must understand the following two rules that remain continuously applicable.

2. Changes may enter the `main` branch only through the review seat operated from the user’s Mac. You must commit your work to your seat’s own branch, push that branch to the relevant remote, and leave the merge for the user or that review-seat workflow; you must never push commits directly to `main`.

3. Files classified as instructions—specifically `CLAUDE.md`, `CLAUDE.local.md`, and every file located anywhere beneath `.claude/`—may be changed only with the user’s “walked approval.” That coined phrase is not defined here; I take it to mean an approval process in which the user explicitly accompanies or guides the proposed change, but the sentence does not establish whether ordinary explicit approval alone is sufficient. A hook enforces this restriction and, if you attempt such a change without following the required procedure, will identify the authorized procedure you should use.
