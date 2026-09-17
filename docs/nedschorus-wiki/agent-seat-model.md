# The agent-seat model

How work is divided among named agents, and why. Every agent reads its own brief; this page is the shared background behind all of them.

## The words this model uses

The project glossary, `docs/nedschorus-wiki/nedschorus-glossary.md`, defines the words this page uses. The handoff-system overview, `docs/nedschorus-wiki/handoff-system-overview.md`, describes the machinery that retires a spent session and starts its successor.

## The grouping rule

An agent-seat's work is the body of related work it owns: a subject area with shared context, not an ordered queue. The tasks in it are named by its brief, not enumerated as a list to work through in order.

**Group tasks by shared context, not by workload.** The test for whether two tasks belong to one agent-seat: *does doing the first make the agent smarter about the second?* If yes, same agent-seat. If no, separate agent-seats — even when that leaves an agent-seat idle.

The user's reasoning, which this model serves:

- An agent with focused context is smarter than one carrying unrelated history. Confusion is the expensive failure.
- **An idle agent-seat costs almost nothing** — no tokens, no attention — so never merge two agent-seats' unrelated work to keep an agent-seat busy. It is not literally free: an unretired agent-seat holds a directory and a branch, and retiring it later takes the steps below. That cost is small and one-time.
- The natural unit of work is a series of related tasks; at the end of a series, the agent writes a handoff and the session is replaced, so the next series starts on a clean context.
- Agent-seats are resumed weeks later, so a name must say what the agent-seat is for without opening anything.

## Which agent-seats exist

The agent-seats that exist are the directories under `~/agents` on either machine; an agent-seat's brief under `docs/agents`, where it has one, says what it owns. The user chooses which of them run.

An agent-seat name is one word. It is an address typed to reach an agent, not a search key, so the multi-part naming rule in `CLAUDE.md` does not apply to it. `gatekeeper` naming the agent-seat that works on the main-gatekeeper is deliberate, not a collision to fix; the program keeps its `main-` prefix everywhere.

## Pausing and retiring an agent-seat

They are different, and confusing them loses work.

**Paused** — the agent-seat's current series is done and nobody is using it. Exit the session; the handoff-supervisor stops with it. The handoff, worktree and branch all stay exactly as they are. This is the ordinary way to leave an agent-seat, and it needs no cleanup.

**Retired** — the name is being freed or repurposed. Four steps, in order:

1. **Stop the handoff-supervisor first.** A running agent-seat writes a fresh handoff each time reincarnate-seat replaces its session, so archiving while its handoff-supervisor is alive only clears the file until the next one. Exit the session and confirm no handoff-supervisor process remains for the agent-seat.
2. **Archive the handoff.** Move it to `~/.claude/handoffs/retired/<seat>-handoff-YYYY-MM-DD.md`, creating the directory if needed; if that name exists, append `-2`, `-3` before `.md`; never move onto an existing archive.
3. **Release the worktree and the branch.** On the agent-seat's machine, `git -C ~/Projects/nedschorus worktree remove ~/agents/<seat>` (not `rm` — the worktree stays registered otherwise, and `git worktree prune` is then needed), and then delete the branch, `git -C ~/Projects/nedschorus branch -d <seat>`, since removing a worktree leaves its branch behind. An agent-seat launched but never used may have an empty directory and no worktree at all; `rmdir` is correct there.
4. **Retire the brief.** Put a dated retirement notice at the top of `docs/agents/<seat>-instructions.md`, naming what survives, in a pull request.

## Launching an agent-seat

From the **Mac**, using the Mac's own clone of this repository:

```
~/Projects/nedschorus/scripts/launch-claude-ubuntu <seat> \
    --first-prompt-file /home/nedlern/Projects/nedschorus/docs/agents/seat-first-prompt.md
```

The script runs on the Mac and reaches the box over SSH. The `--first-prompt-file` path is a **box-side** path, because the handoff-supervisor reads that file on the box. One generic file serves every agent-seat: the agent learns its own name from its working directory, so nothing needs substituting.

**Both halves must actually exist where they are named**, and they are read on different machines: the script in the Mac's clone, the prompt file in the box's. A clone that has not pulled since these landed has neither. Check before launching an agent-seat for the first time:

```
ls ~/Projects/nedschorus/scripts/launch-claude-ubuntu                        # on the Mac
ssh nedlern@ned-box 'ls /home/nedlern/Projects/nedschorus/docs/agents/seat-first-prompt.md'
```

If the box's copy is missing, `ssh nedlern@ned-box 'git -C ~/Projects/nedschorus pull'` and try again.

Three things about that command worth knowing before you rely on it:

- **It is attach-or-create.** Running the name again attaches to the live tmux session, or to the shell left behind when its handoff-supervisor stopped, rather than starting a second one — and in that case `--first-prompt-file` does nothing, because there is no new session to seed. To stop an agent-seat, the user exits the session inside it (`/exit`); to leave it running, he detaches from tmux (`Ctrl-b d`).
- **An unconsumed handoff outranks the first-prompt file.** If `~/.claude/handoffs/<seat>-handoff.md` holds a handoff the handoff-supervisor has not yet consumed, it boots from that; `--first-prompt-file` seeds every other launch. To seed an agent-seat from another agent-seat's context deliberately, copy that agent-seat's handoff to `~/.claude/handoffs/<seat>-handoff.md` before launching.
- **A session that ends without writing a handoff leaves no thread behind.** The next launch of that name starts from the first-prompt file. The handoff — not the session — is the thing that carries an agent-seat's thread. Its companion is the conversation tail, `~/.claude/handoffs/<seat>-dialog-NNNN.md`, numbered by generation: the successor is told to read it first, and when the tail leaves earlier turns out, the whole dialog waits beside it in `<seat>-dialog-NNNN-complete.md` for when it needs more.

The launcher creates the agent-seat's worktree on its own branch **before the session starts**, because project settings — the status line, the context-threshold handoff hook, the instruction-file guard — are wired through `.claude/settings.json` in the working directory, read at session start, and an agent started in a directory without it runs with none of them. When the worktree cannot be made, the launcher says so and starts the session anyway.

## What separate branches do and do not protect

Each agent-seat's worktree holds one branch at a time, its own seat branch or a topic branch cut from main, and git refuses to check one branch out in two worktrees. That keeps two agent-seats off one branch and nothing more: it is a check rather than a guarantee, since `git worktree add --force` overrides it and a separate clone is invisible to it, and two agent-seats editing the same file on different branches meet at the merge.

It protects nothing outside git. `~/.claude/handoffs/` and the tmux socket (`tmux -L <seat>`, one server per agent-seat since 2026-08-21, so one server crash takes down one agent-seat) are per-machine state keyed by the agent-seat's name. Two agent-seats using the same name would collide in that directory and in cross-session addressing, which is why one name means one agent-seat across both machines.

One class of file is guarded outside git: the agent-instructions, the files that tell agents how to behave. `CLAUDE.md`, an agent-seat's `CLAUDE.local.md`, the repository's `.claude/`, and the harness memory under `~/.claude/projects/` change only with walked-approval, enforced by `.claude/hooks/instruction-file-guard.py`. An agent-seat's brief and the first-prompt file, `docs/agents/seat-first-prompt.md`, are agent-instructions too but are not in that guarded set: they change by pull request, like the rest of the repository.

**Nothing that matters is left only in a session.** Work belongs in commits and pushes; decisions belong in the wiki, the designs and the issues. The handoff is the one durable thing that is never pushed: it lives on the agent-seat's machine only, and an agent-seat exited without one keeps its committed work and loses its thread.
