<!-- provenance: runtime=claude model=claude-opus-5 effort=high cell=restate tier=good target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/issues/queue/45-session-seat-and-isolation-riders.md -->

The file contains no YAML frontmatter; it begins with the H1 title.

## Title and opening paragraph

1. **"# Session seat and isolation riders"** — The document's title. I read "session seat" as a session that has a visible terminal home a person can sit at (a tmux window / attached terminal for a named agent), and "isolation" as keeping sessions in separate working directories so they don't interfere. "Riders" I take in the legislative sense: small additional items attached to a larger existing piece of work (issue #45) rather than filed as their own issues. So: "extra proposals about session seats and session isolation, attached to an existing issue."

2. **"Queued for nedschorus#45 (named agents, launch and reattach)."** — This document sits in the queue directory as pending, not-yet-filed material belonging to GitHub issue number 45 in the nedschorus/nedschorus repository; the parenthesis gives that issue's subject matter, which is named agents and the launching and reattaching of them.

3. **"Raised in conversation 2026-08-13 while untangling why several sessions on the box were hard to tell apart and one had forked into another's checkout."** — These items came up during a discussion held on 13 August 2026. The discussion's purpose was to figure out two confusing situations on ned-box (the Ubuntu machine): first, that several concurrently running Claude sessions were difficult to distinguish from one another when listed; second, that one session had been created by forking and, as a result, had ended up doing its work inside a different session's git checkout (its clone/worktree directory).

4. **"Each item below was discussed and left undone deliberately — none is in flight."** — Every numbered item that follows was talked about and then consciously chosen not to be acted on; the not-doing is a decision, not an oversight or a forgotten task. "None is in flight" adds that no item is currently being worked on by anyone right now.

## 1. A guard that enforces one live session per directory

1. **Heading: "A guard that enforces one live session per directory"** — A proposed automated check ("guard") that makes it impossible for more than one currently-running ("live") Claude session to be operating in any single working directory.

2. **"**The invariant:** two live sessions must never share a working directory."** — Stating the rule that the proposal exists to preserve: at no time should two simultaneously running sessions have the same working directory.

3. **"Forks are the common road to breaking it — a fork inherits the parent's directory along with its conversation — and a background job launched from a session inherits the same cwd, which is what made several jobs look like duplicates in `~/agents/choirmaster`."** — The usual way that rule gets violated is forking a session: when you fork, the new session receives a copy of the parent's conversation history and also the parent's working directory, so both now sit in that one directory. A second route is launching a background job from within a session: the job starts with the same current working directory as its launching session. That second route is the cause of an observed symptom — in a listing of sessions, several background jobs all showed `~/agents/choirmaster` as their directory and therefore appeared to be copies of the same thing when they were actually distinct jobs.

4. **"**The proposal:** a PreToolUse hook on `Edit|Write` that refuses when another live Claude process shares this session's working directory, teaching the fix — "another session is live here; call `EnterWorktree` first"."** — The suggested build: a hook script registered to run in the PreToolUse position (i.e. before a tool call is executed) for the Edit and Write tools. When it runs, it checks whether some other currently-running Claude process has the same working directory as the session making the call; if so, it denies the tool call. The denial message is written to tell the agent what to do instead, quoted here as "another session is live here; call `EnterWorktree` first" — `EnterWorktree` being the tool that moves the session into its own separate worktree.

5. **"Reads and searches stay unblocked; they never collide."** — The hook deliberately does not cover read-type or search-type tools; those are allowed to proceed even when two sessions share a directory, because reading and searching cannot cause the interference (concurrent conflicting file modification) that the guard exists to prevent.

6. **"**Detection is the open problem, and the obvious method does not work.**"** — The unsolved part of this proposal is not the blocking mechanism but the step of determining whether another live session shares the directory; and the approach that first suggests itself has been shown to fail.

7. **"A `/proc` scan comparing each Claude process's `cwd` was the first proposal; it was tried 2026-08-13 and found unreliable — an *attached* background session's process reports the directory the `claude attach` command was typed in, not the directory the session actually works in, so real duplicates hide and viewer windows masquerade as sessions."** — The first idea was to walk the Linux `/proc` filesystem, read the recorded current working directory of every running Claude process, and look for two with the same value. This was actually tested on 13 August 2026 and did not give trustworthy answers. The reason: when a background session has been attached to via `claude attach`, the process that the scan sees reports as its cwd the directory from which the operator typed the `claude attach` command, rather than the directory in which that session is actually performing its work. Two consequences follow. First, two sessions that genuinely do share a working directory can go undetected, because at least one of them reports some other directory. Second, an attached terminal — which is only a window onto an existing session, not a separate session — is counted by the scan as though it were an independent session occupying a directory (I read "viewer windows masquerade as sessions" as this false-positive case).

8. **"A working detector needs the session's own view of its working directory (its transcript records it, and the session itself answers correctly when asked), not the process table."** — Any detection method that would actually work has to obtain the directory from the session's own internal record of where it is working, rather than from operating-system process information. Two sources of that internal record are named as evidence it exists and is correct: the session's transcript file, which stores the working directory, and the session itself, which gives the right answer if you ask it directly.

9. **"Resolve this before building the hook: a guard whose detection is wrong is worse than none, because it teaches the wrong lesson at the wrong moment."** — An instruction about sequencing: settle the detection question first, and only then write the hook. The justification: a hook whose check gives wrong answers is a worse outcome than having no hook at all, because when it fires incorrectly it delivers its instructional denial message ("another session is live here; call EnterWorktree first") to an agent that is not in that situation, at the moment the agent is trying to do legitimate work — so the agent is trained into an incorrect belief and interrupted for no reason.

10. **"**Why this shape:** `EnterWorktree` already relocates a running session correctly, so capability is not the gap — the trigger is."** — Explaining why the proposal takes the form it does. The ability to fix the problem already exists: the `EnterWorktree` tool successfully moves an already-running session into its own worktree. What is missing is therefore not a new capability, but something that causes the fix to be invoked at the moment it is needed.

11. **"A SessionStart warning was considered and judged weaker: it advises, where the PreToolUse form blocks."** — An alternative design — emitting a warning message once at session startup, via a SessionStart hook — was evaluated and rejected as the less effective of the two. The reason given is the difference in force: a startup warning only offers advice, which an agent may ignore or forget, whereas the PreToolUse form actually prevents the offending action from happening.

12. **"The project already runs this exact pattern in `.claude/hooks/instruction-file-guard.py`."** — Supporting argument that the design is proven here: this repository already contains and uses a hook of precisely this kind (a PreToolUse hook that refuses a tool call), at the named path, so the pattern is established rather than novel.

13. **"**Cost/caveat:** needs an entry in `.claude/settings.json` (instruction-class, so it lands through the user's walk), and a PreToolUse hook runs for every session on the machine, so a defect in it is felt everywhere."** — The downsides to weigh. First, installing the hook requires adding a registration entry to the `.claude/settings.json` file; that entry counts as "instruction-class" material — I read this as the project's category for text/configuration that governs how agents behave — and material in that category is subject to the project convention that the user reviews it item by item before it lands (the "walk", which I take to be the walk-me-through presentation). Second, because a PreToolUse hook of this kind is active for every Claude session running on the machine, any bug in the hook has machine-wide consequences rather than affecting only one session.

## 2. A `--directory` flag for the launchers

1. **Heading: "A `--directory` flag for the launchers"** — A proposal to add a command-line option named `--directory` to the scripts that start agent sessions.

2. **"`scripts/launch-claude-ubuntu` and `scripts/launch-claude-mac` place every agent in `<agents-root>/<name>` by convention and accept no directory argument, so a seat cannot adopt an existing worktree."** — The two named launcher scripts (one for the Ubuntu box, one for the Mac) always derive an agent's working directory from a fixed rule: a common agents root directory plus the agent's name. They provide no way to pass in a directory. The consequence is that you cannot start a visible, sit-at-able session ("a seat") that takes over and works in a git worktree that already exists elsewhere on disk.

3. **"That makes "promote this background thread to a visible tmux seat" harder than it needs to be."** — Because of that limitation, the operation of taking work that is currently running as a background session and giving it a visible terminal home in tmux is more difficult than the underlying task warrants. ("Background thread" here means a background session/job, not an OS thread.)

4. **"Roughly ten lines per launcher."** — An effort estimate: implementing the flag would take on the order of ten lines of code changed or added in each of the two launcher scripts.

5. **"Weakened, though not eliminated, by a fact discovered the same day: `claude attach <job-id>` already opens a background session in a terminal, so a seat is not the only route to visibility."** — The case for building this flag is made less compelling — but not made void — by something learned on 13 August 2026: the existing `claude attach` command, given a job id, already puts a background session into a terminal window. Therefore, if the goal is simply to see and interact with a background session, creating a launcher-made seat is not the only way to achieve it.

## 3. A CLAUDE.md rule: background jobs push their own branch

1. **Heading: "A CLAUDE.md rule: background jobs push their own branch"** — A proposal to add a written instruction to the project's CLAUDE.md file, stating that a background job must push to a branch of its own rather than to a shared one.

2. **"Several sessions pushing to one shared agent branch produced the `Merge remote-tracking branch 'origin/choirmaster' into choirmaster` commits in that branch's history, and a non-fast-forward rejection that cost a rebase mid-task."** — The observed damage from the current situation: because multiple sessions all pushed to a single branch named after the agent (`choirmaster`), each session periodically had to pull and merge the others' work, leaving automatic merge commits with that standard message cluttering the branch's history. It also produced at least one occasion where a push was rejected by git as non-fast-forward (someone else's commits had landed first), forcing the session to stop what it was doing and perform a rebase.

3. **"One branch per session removes the class: git already refuses one branch in two worktrees, so the discipline only has to cover which branch a session pushes."** — Giving each session its own branch eliminates that whole category of problem, not just individual instances. The supporting point: git itself already prevents the same branch from being checked out in two worktrees simultaneously, so that half of the separation is enforced by the tool; the written rule therefore only needs to govern the remaining, unenforced half — the choice of which branch a session pushes to.

4. **"Instruction-class text, so it lands through the user's walk."** — This proposed CLAUDE.md addition falls into the project's "instruction-class" category (text that directs agent behavior), and by the same convention noted in section 1, such text reaches main only after being presented to the user for review item by item.

## 4. md-review the fleet paths reference

1. **Heading: "md-review the fleet paths reference"** — A task: run the md-review skill over the document that serves as the reference for fleet machine paths.

2. **"`docs/cross-project/fleet-machine-paths-and-checkouts.md` was written 2026-08-13 and is a lasting reference, which is the md-review skill's stated target."** — The named file was authored on 13 August 2026 and is a document intended to remain useful over time; documents of lasting value are exactly the kind of file that the md-review skill's own description says it is for. (The implication I take: it therefore qualifies for review.)

3. **"Not yet reviewed."** — That md-review has not been performed on the file so far.

## 5. Migrating `choirmaster` to a machine-suffixed name

1. **Heading: "Migrating `choirmaster` to a machine-suffixed name"** — The item concerns renaming the agent currently called `choirmaster` to a name that has the machine it runs on appended to it (e.g. something of the form `choirmaster-<machine>`).

2. **"Considered and deferred."** — This change was evaluated and the decision was to postpone it rather than do it or reject it outright.

3. **"The two machines share no agent state, so the same name on both is two unrelated agents rather than a conflict — the suffix buys legibility in a listing that spans machines, nothing more."** — The Mac and ned-box keep entirely separate agent data; nothing about agents is shared between them. Consequently, an agent named `choirmaster` on the Mac and one named `choirmaster` on the box are simply two different, independent agents that happen to share a name; the duplicate name causes no technical collision. The only benefit of adding a machine suffix would be human readability — being able to tell the two apart when looking at a single list that shows agents from both machines — and no benefit beyond that.

4. **"Migrating the live seat means `git worktree move`, renaming its handoff files, and a restart, which is disruptive to a working agent for a cosmetic gain."** — Carrying out the rename on the currently-running session would require three operations: moving its git worktree with the `git worktree move` command, renaming the handoff files associated with that agent (the files used to pass work from one session to its successor), and stopping and restarting the session. That amount of interruption to an agent that is actively working is not justified when the payoff is only appearance/readability.

5. **"Revisit only if a cross-machine listing becomes a routine view."** — The condition under which this decision should be reopened: if looking at a combined list of agents from both machines becomes a regular, habitual thing to do. Until then, leave it alone.

## Session-management facts worth keeping (verified 2026-08-13, Claude Code 2.1.231)

1. **Heading: "Session-management facts worth keeping (verified 2026-08-13, Claude Code 2.1.231)"** — This section holds pieces of knowledge about managing sessions that are worth recording; the parenthesis states that they were confirmed to be true on 13 August 2026 against version 2.1.231 of Claude Code (implying they could change in other versions).

2. **"Not riders, but hard-won and easy to lose:"** — Unlike the numbered items above, these entries are not proposed pieces of work attached to issue #45; they are recorded here because they took real effort to discover and would readily be forgotten or have to be rediscovered if not written down.

3. **"**Job ids are not session ids.**"** — A warning that two identifiers which might be assumed to be the same thing are in fact distinct: the identifier of a job and the identifier of a session.

4. **"`claude attach <id>` takes the 8-character job id (the directory names under `~/.claude/jobs/`), not the session UUID."** — The argument the `claude attach` command expects is the job id, which is eight characters long and is the same string used as the name of the job's directory inside `~/.claude/jobs/`. It is not the session's UUID (the longer universally-unique identifier that identifies a session).

5. **"Attaching by session id fails with "No job matching"."** — If you pass a session UUID to `claude attach` instead, the command does not work and reports the error message "No job matching".

6. **"**`claude agents`** opens the agent view: every session grouped by state, `Space` peeks without attaching, `Ctrl+R` renames, `Ctrl+T` pins against the ~1-hour idle reap, `Ctrl+X` stops."** — Running the command `claude agents` brings up an interactive screen listing agents. In it: all sessions are displayed organised into groups by their state (running, idle, and so on); pressing Space shows you a preview of the highlighted session without actually attaching your terminal to it; Ctrl+R lets you rename the highlighted session; Ctrl+T marks it as pinned so that it is exempt from the automatic cleanup that kills sessions after roughly an hour of inactivity; Ctrl+X terminates it.

7. **"`Ctrl+S` groups by *directory*, which makes the shared-directory hazard visible."** — Within that same view, pressing Ctrl+S switches the grouping from state to working directory. The practical value: when sessions are grouped by directory, two sessions occupying one directory appear together under one heading, so the very problem section 1 is about becomes visible at a glance.

8. **"**It must run on the machine whose sessions you want.**"** — The `claude agents` command reports only on the machine where it is executed, so you have to run it on whichever machine hosts the sessions you are trying to inspect.

9. **"Typed on the Mac it lists the Mac's jobs; the box needs `ssh nedlern@ned-box -t 'claude agents'`."** — Concretely: entering the command in a terminal on the Mac shows the jobs running on the Mac only. To see the jobs on ned-box, you must run it there over SSH using the given command, where the `-t` flag forces allocation of a terminal (needed because the agent view is an interactive full-screen interface).

10. **"**No side-by-side view exists** in the harness."** — Claude Code itself provides no feature for displaying two or more sessions next to each other on screen at the same time.

11. **"Simultaneous views mean one terminal (or tmux window) per session."** — Therefore, if you want to watch several sessions at once, you have to arrange it yourself outside the tool, by opening a separate terminal — or a separate tmux window — for each session.

12. **"**Process uptime is not idle time.**"** — Another pair of things not to confuse: how long a session's operating-system process has been running is a different quantity from how long the session has been sitting idle.

13. **"A session showing 23 hours of `etime` may have been active a minute ago; the honest staleness check is the modification time of its transcript under `~/.claude/projects/<project>/<session-id>.jsonl`."** — For example, a session whose process reports an elapsed running time (`etime`, the ps field) of 23 hours could nevertheless have been doing work sixty seconds ago; the long uptime says nothing about recent activity. The reliable way to judge whether a session has actually gone stale is to look at the last-modified timestamp of that session's transcript file, which lives at the path given, where `<project>` is the project's directory name and `<session-id>` is the session's UUID — since the transcript is written to each time the session does something.

