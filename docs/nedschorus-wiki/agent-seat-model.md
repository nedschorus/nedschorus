# The agent seat model

How work is divided among named agents, and why. Every agent reads its own brief; this page is the shared background behind all of them.

## The words this model uses

Defined here because the briefs use them as if established; the project glossary, `docs/nedschorus-wiki/nedschorus-glossary.md`, holds the rest.

- **Seat** — a named, long-lived agent identity: a name, a worktree (`~/agents/<seat>`), its own git branch, and a brief. A seat is occupied by a session while one runs, and outlives any one session.
- **Session** — one running conversation. Sessions end and are replaced; the seat persists.
- **Supervisor** — `scripts/handoff-supervisor.py`, the process that launches a seat's session, replaces it when it hands off, and exits when its agent stops without handing off. One supervisor per seat, holding a lock, `~/.claude/handoffs/<seat>-supervisor.lock`, that refuses a second.
- **Reincarnate** — the supervisor replacing a session with a fresh one, carrying the handoff forward. Triggered when the agent writes a handoff, usually because the `Stop` hook `scripts/handoff-context-threshold-hook.py` asked it to as context ran low.
- **Handoff** — `~/.claude/handoffs/<seat>-handoff.md`, written by a session for its successor. On the seat's machine only, never committed. Its companion `~/.claude/handoffs/<seat>-dialog-NNNN.md`, numbered in sequence, holds that session's conversation tail, which a successor reads when it needs the discussion rather than the conclusion.
- **A seat's work** — the body of related work a seat owns. A subject area with shared context, not an ordered queue: the tasks in it are named by the seat's brief, not enumerated as a list to work through in order.
- **Brief** — `docs/agents/<seat>-instructions.md`. What a seat's occupant reads to learn its job. Briefs vary in shape; read yours for what it says.
- **Walked approval** — the user's approval given item by item through a walk (the `walk-me-through` skill under `.claude/skills/`), not one yes to a bundle. Recorded by quoting his words into `.walk-approved` at the root of the session's own checkout, which `.claude/hooks/instruction-file-guard.py` consumes for the single write it approves. Written *walked approval*; the hyphenated *walked-approval* only as a compound adjective.
- **Agent-instructions files** — files that tell agents how to behave: `CLAUDE.md`, `~/agents/<seat>/CLAUDE.local.md`, the repository's `.claude/`. They change only with walked approval; a brief is not one of these.
- **Slice** — one numbered increment of a build plan, built and merged on its own.
- **C-numbers** (`C1`, `C3`, `C7`…) — identifiers of the main-gatekeeper's credential rulings, defined in `docs/cross-project/main-gatekeeper-design.md` § The credential and enforcement. Defined only there.

## The grouping rule

**Group tasks by shared context, not by workload.** The test for whether two tasks belong to one seat: *does doing the first make the agent smarter about the second?* If yes, same seat. If no, separate seats — even when that leaves a seat idle.

The user's reasoning, which this model serves:

- An agent with focused context is smarter than one carrying unrelated history. Confusion is the expensive failure.
- **An idle seat costs almost nothing** — no tokens, no attention — so never merge two seats' unrelated work to keep a seat busy. It is not literally free: an unretired seat holds a directory and a branch, and retiring it later takes the steps below. That cost is small and one-time.
- The natural unit of work is a series of related tasks; at the end of a series, the agent writes a handoff and the session is replaced, so the next series starts on a clean context.
- Seats are resumed weeks later, so a name must say what the seat is for without opening anything.

## Which seats exist

The seats that exist are the directories under `~/agents` on either machine; a seat's brief under `docs/agents`, where it has one, says what it owns. The user chooses which of them run.

A seat name is one word. It is an address typed to reach an agent, not a search key, so the multi-part naming rule in `CLAUDE.md` does not apply to it. `gatekeeper` naming the seat that works on the main-gatekeeper is deliberate, not a collision to fix; the program keeps its `main-` prefix everywhere.

## Pausing and retiring a seat

They are different, and confusing them loses work.

**Paused** — the seat's current series is done and nobody is using it. Exit the session; the supervisor stops with it. The handoff, worktree and branch all stay exactly as they are. This is the ordinary way to leave a seat, and it needs no cleanup.

**Retired** — the name is being freed or repurposed. Four steps, in order:

1. **Stop the supervisor first.** A running seat writes a fresh handoff at every reincarnation, so archiving while its supervisor is alive only clears the file until the next one. Exit the session and confirm no supervisor process remains for the seat.
2. **Archive the handoff.** Move it to `~/.claude/handoffs/retired/<seat>-handoff-YYYY-MM-DD.md`, creating the directory if needed; if that name exists, append `-2`, `-3` before `.md`; never move onto an existing archive.
3. **Release the worktree and the branch.** On the seat's machine, `git -C ~/Projects/nedschorus worktree remove ~/agents/<seat>` (not `rm` — the worktree stays registered otherwise, and `git worktree prune` is then needed), and then delete the branch, `git -C ~/Projects/nedschorus branch -d <seat>`, since removing a worktree leaves its branch behind. A seat launched but never used may have an empty directory and no worktree at all; `rmdir` is correct there.
4. **Retire the brief.** Put a dated retirement notice at the top of `docs/agents/<seat>-instructions.md`, naming what survives, in a pull request.

## Launching a seat

From the **Mac**, using the Mac's own clone of this repository:

```
~/Projects/nedschorus/scripts/launch-claude-ubuntu <seat> \
    --first-prompt-file /home/nedlern/Projects/nedschorus/docs/agents/seat-first-prompt.md
```

The script runs on the Mac and reaches the box over SSH. The `--first-prompt-file` path is a **box-side** path, because the supervisor reads that file on the box. One generic file serves every seat: the agent learns its own name from its working directory, so nothing needs substituting.

**Both halves must actually exist where they are named**, and they are read on different machines: the script in the Mac's clone, the prompt file in the box's. A clone that has not pulled since these landed has neither. Check before launching a seat for the first time:

```
ls ~/Projects/nedschorus/scripts/launch-claude-ubuntu                        # on the Mac
ssh nedlern@ned-box 'ls /home/nedlern/Projects/nedschorus/docs/agents/seat-first-prompt.md'
```

If the box's copy is missing, `ssh nedlern@ned-box 'git -C ~/Projects/nedschorus pull'` and try again.

Three things about that command worth knowing before you rely on it:

- **It is attach-or-create.** Running the name again attaches to the live tmux session, or to the shell left behind when its supervisor stopped, rather than starting a second one — and in that case `--first-prompt-file` does nothing, because there is no new session to seed. To stop a seat, the user exits the session inside it (`/exit`); to leave it running, he detaches from tmux (`Ctrl-b d`).
- **An unconsumed handoff outranks the first-prompt file.** If `~/.claude/handoffs/<seat>-handoff.md` holds a handoff the supervisor has not yet consumed, it boots from that; `--first-prompt-file` seeds every other launch. To seed a seat from another seat's context deliberately, copy that seat's handoff to `~/.claude/handoffs/<seat>-handoff.md` before launching.
- **A session that ends without writing a handoff leaves no thread behind.** The next launch of that name starts from the first-prompt file. The handoff — not the session — is the thing that carries a seat's thread.

The launcher creates the seat's worktree on its own branch **before the session starts**, because project settings — the status line, the context-threshold handoff hook, the instruction-file guard — are wired through `.claude/settings.json` in the working directory, read at session start, and an agent started in a directory without it runs with none of them. When the worktree cannot be made, the launcher says so and starts the session anyway.

## What separate branches do and do not protect

Each seat's worktree holds one branch at a time, its own seat branch or a topic branch cut from main, and git refuses to check one branch out in two worktrees. That keeps two seats off one branch and nothing more: it is a check rather than a guarantee, since `git worktree add --force` overrides it and a separate clone is invisible to it, and two seats editing the same file on different branches meet at the merge.

It protects nothing outside git. `~/.claude/handoffs/` and the tmux socket (`tmux -L <seat>`, one server per seat since 2026-08-21, so one server crash takes down one seat) are per-machine state keyed by the seat's name. Two seats using the same name would collide in that directory and in cross-session addressing, which is why one name means one seat across both machines.

**Nothing that matters is left only in a session.** Work belongs in commits and pushes; decisions belong in the wiki, the designs and the issues. The handoff is the one durable thing that is never pushed: it lives on the seat's machine only, and a seat exited without one keeps its committed work and loses its thread.
