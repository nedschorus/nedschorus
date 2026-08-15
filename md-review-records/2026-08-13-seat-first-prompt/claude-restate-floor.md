<!-- provenance: runtime=claude model=claude-sonnet-5 effort=high cell=restate tier=floor target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/agents/seat-first-prompt.md -->

# seat-first-prompt.md — sentence-by-sentence restatement

No YAML frontmatter is present; the file begins directly with prose.

## Opening paragraph (unlabeled)

1. The reader of this document is functioning as one instance of a designated, named slot ("seat") assigned to work on the project called nedschorus, and that instance's process is executing on a computer host called `ned-box`, which runs the Ubuntu operating system.
2. The human user does his work from a separate computer (a Mac) that shares the same local network as `ned-box`, and he never operates `ned-box`'s own terminal/console directly; as a result, whenever the agent gives the user a command to type, the agent must specify explicitly which of the two machines that command is meant to be run on, since an identical-looking command could be intended for either one.
3. At the start, the agent possesses no information about its situation or task other than what is written in this document, and it is possible to obtain everything the agent needs starting from this document (i.e., this file is the entry point from which the rest of the needed context can be located).

## Step 1 — find out which seat you are

1. This section's stated purpose is for the agent to determine the name of the seat it occupies.
2. The name of the agent's seat is defined as being identical to the name of its current working directory.
3. The agent should run the `pwd` command; if the resulting output is a path matching the pattern `/home/nedlern/agents/` followed by some name, then that trailing name segment is the agent's seat name.

## Step 2 — confirm your home is a checkout

1. This section's stated purpose is for the agent to verify that its home/working directory is in fact a git checkout (a working copy of the project repository), rather than some other kind of directory.
2. The launcher process — whatever starts the agent's session — is responsible for turning the agent's home directory into a checkout of the project, on a branch unique to that agent, and it does this before the agent's session actually begins; consequently, if this happened correctly, running `git rev-parse --show-toplevel` (which reports the top-level directory of the enclosing git repository) should report the agent's own working directory, and running `git branch --show-current` (which reports the name of the currently checked-out branch) should report a name equal to the agent's seat name.
3. If, upon checking, the home directory turns out not to be a checkout, that means something failed during launch, and this failure has consequences more serious than they might seem at first: specifically, certain project configuration — the status-line display, the "recycle hook" (a mechanism that hands the session off to a fresh one when the available context is running low), and a safeguard restricting edits to instruction files — is loaded from the `.claude/` directory inside the working directory, and this loading happens only once, at the moment the session starts; because that loading already happened (or failed to happen) at that one moment, the agent is now running without any of that configuration active, and there is no way to obtain it retroactively simply by fixing the directory afterward — the configuration was already either loaded or not, permanently for this session.
4. The agent should notify the user of this situation and should wait for the user to start a new session for it (relaunch it), rather than the agent proceeding to do further work in this state.
5. However, if the user explicitly directs the agent to keep working despite this problem, then the remedy is the command given next.
6. The given git command instructs git, acting on the repository at `/home/nedlern/Projects/nedschorus`, to create a new worktree (an additional linked working directory for the same repository) located at `/home/nedlern/agents/<name>`, simultaneously creating a new branch named `<name>` (via the `-b` flag), with both the new worktree and the new branch based on the current state of the `origin/main` branch (main as known from the remote called "origin").
7. This parenthetical explains a variant: if a branch with the seat's name already exists rather than needing to be created, the `-b` flag should be left out and the existing branch's name given as the final argument instead; it further explains that this distinction matters because git's design permits a given branch to be checked out in only one worktree at a time, and that very restriction is the mechanism that prevents different agent seats from colliding with one another (i.e., from ending up using the same branch in two places at once).

## Step 3 — read your instructions, in this order

1. This section's stated purpose is for the agent to read a specific set of documents, located inside its own checkout, in a specific sequence, starting from within that checkout.
2. The first document, `docs/agents/<name>-instructions.md`, is described as "your brief" — meaning it is this particular agent's individual assignment document.
3. This brief document is stated to specify: the body of work assigned to this seat, the specific issues and pull requests that make up that work, which documents the agent should read first (ahead of others), the limits of this seat's responsibility relative to the work of other seats (presumably to avoid overlap or interference), and an explicitly designated action the agent is meant to take first.
4. The second document, `docs/agents/agent-seat-model.md`, is described as explaining how seats work, specifically covering: the reasoning behind why work has been divided into groups the way it has, how many seats/agents operate at the same time (concurrently), and the process by which a seat is either permanently ended ("retired") or paused and later continued ("resumed").
5. The third document, `CLAUDE.md`, located at the top level (root) of the repository, contains the project's ongoing/standing rules, and these rules are binding on — apply to and must be followed by — every agent operating in this project.
6. If the agent looks in the `docs/agents/` directory and finds no file whose name corresponds to its own seat name, the agent should stop what it is doing and ask the user for direction, rather than making up a task or purpose for itself on its own initiative.

## Step 4 — do what your brief's "First action" says

1. This section's stated purpose is for the agent to carry out whatever is specified under the heading or label "First action" within its own brief document.
2. In every seat's brief document, the action labeled as the first action always consists of reading, verifying, and reporting to the user, and is never to begin building — meaning the first action never involves starting actual implementation, construction, or substantive changes.
3. The sequencing/prioritization of subsequent work is a decision that belongs to the user (referred to as "he"), not to the agent — the agent should not decide on its own what order to tackle tasks in, but should wait for the user to specify it.

## Two standing rules worth knowing before you touch anything

1. This closing note introduces two permanent, ongoing rules the agent should be aware of before taking any action.
2. Changes only reach the `main` branch by passing through a review process carried out by the user via a designated agent seat running on the user's Mac (called the "review seat" here); the agent's role is to commit its changes to its own branch, push that branch to the remote, and then let the user perform the merge into `main` — the agent must never push directly to `main` itself.
3. A category of files called "instruction-class files" — specifically `CLAUDE.md`, `CLAUDE.local.md`, and any file under the `.claude/` directory — may be changed only after obtaining the user's approval given in "walked" form, meaning (per the project's walk-through convention) the proposed change is presented to the user one part at a time with a pause for his go-ahead at each step, rather than being approved in one bulk request; this requirement is enforced automatically by a hook (an automated script triggered by certain actions), and if the agent attempts such a change without going through this process, the hook will inform the agent of the correct, sanctioned way to do it.

