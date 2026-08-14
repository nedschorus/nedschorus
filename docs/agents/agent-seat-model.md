# The agent seat model

How work on the Ubuntu box is divided among named agents, and why it is divided that way. Ruled by the user 2026-08-13, after a day in which parallel sessions accumulated faster than anyone tracked them. The per-seat briefs live beside this file as `docs/agents/<seat>-instructions.md`; every agent reads its own brief, and this file is the shared background behind all of them.

## The words this model uses

Defined here because the briefs use them as if established, and an agent reading one cold has nowhere else to look.

- **Seat** — a named, long-lived agent identity: a name, a home directory (`~/agents/<seat>`), its own git branch, and a brief. A seat is *occupied* by a session and outlives any one session. One place the word is used loosely and deliberately: the **Mac-side agent**, which reviews branches and merges them to `main`, is the user's own agent on his Mac and is not one of the seats defined here.
- **Session** — one running conversation. Sessions end and are replaced; the seat persists.
- **Supervisor** — `scripts/handoff-supervisor.py`, the process that launches a seat's session, replaces it when it hands off, and exits when its agent stops without handing off. One supervisor per seat, holding a lock that refuses a second.
- **Recycle** — the supervisor replacing a session with a fresh one, carrying the handoff forward. Triggered when the agent writes a handoff, usually because the `Stop` hook `scripts/handoff-context-threshold-hook.py` asked it to as context ran low.
- **Handoff** — `~/.claude/handoffs/<seat>-handoff.md`, written by a session for its successor. Machine-local, never committed. Its companion `~/.claude/handoffs/<seat>-dialog-NNNN.md` holds that session's conversation tail, which a successor reads when it needs the discussion rather than the conclusion.
- **Pile** — the body of related work a seat owns. A subject area with shared context, not an ordered queue: the tasks in it are named by the seat's brief, not enumerated as a list to work through in order.
- **Brief** — `docs/agents/<seat>-instructions.md`. What a seat's occupant reads to learn its job. Briefs vary in shape; read yours for what it says.
- **Walked approval** — the user's approval given item by item through a walk (the `walk-me-through` skill), not one yes to a bundle. Recorded by quoting his words into `.walk-approved` at the repository root, which `.claude/hooks/instruction-file-guard.py` consumes for the single write it approves. Written *walked approval*; the hyphenated *walked-approval* only as a compound adjective.
- **Instruction-class** — files that tell agents how to behave: `CLAUDE.md`, `CLAUDE.local.md`, anything under `.claude/`. They change only with walked approval.
- **Slice** — one numbered increment of a build plan, built and landed on its own.
- **C-numbers** (`C1`, `C3`, `C7`…) — identifiers of the git-gatekeeper's credential rulings, defined in `docs/cross-project/git-gatekeeper-design.md` § The credential and enforcement. Meaningful only inside that document.

## The grouping rule

**Group tasks by shared context, not by workload.** The test for whether two tasks belong to one seat: *does doing the first make the agent smarter about the second?* If yes, same seat. If no, separate seats — even when that leaves a seat idle.

The user's reasoning, which this model serves:

- An agent with focused context is smarter than one carrying unrelated history. Confusion is the expensive failure.
- **An idle seat costs almost nothing** — no tokens, no attention — so never merge two unrelated piles to keep a seat busy. It is not literally free: an unretired seat holds a directory and a branch, and retiring it later takes the steps below. That cost is small and one-time.
- The natural unit of work is a series of related tasks; at the end of one, the agent writes a handoff and the session is replaced, so the next series starts on a clean context.
- Seats are resumed weeks later, so a name must say what the seat is for without opening anything.

`sidebar` is the deliberate exception to the grouping rule: it holds no pile at all and answers whatever is asked, precisely so that off-topic questions never land in a seat whose context they would pollute.

## The seats

Seven are defined. Each row's brief is the authority on what that seat owns.

| Seat | What it owns | Brief |
|---|---|---|
| `gatekeeper` | the remaining work to activate the git-gatekeeper: the walked-approval evidence format, build slice 6, then the credential work | `gatekeeper-instructions.md` |
| `sanity-checker` | review quality — the sanity-checker reviewer (a prompt that proposes simplifications, `docs/drafts/sanity-checker-prompt-draft.md`) and whether it joins the eight-cell md-review grid run by `scripts/md-review-grid.py` | `sanity-checker-instructions.md` |
| `skill-builder` | the seven proposed skills queued as issues #17–#23, and the queue-drain procedure that empties the project's queues ([#24](https://github.com/nedschorus/nedschorus/issues/24)) | `skill-builder-instructions.md` |
| `ghi` | GitHub-issue knowledge and tooling: ghi-info ([#46](https://github.com/nedschorus/nedschorus/issues/46)), run-agent ([#41](https://github.com/nedschorus/nedschorus/issues/41)), the reference-integrity checker ([#42](https://github.com/nedschorus/nedschorus/issues/42)) | `ghi-instructions.md` |
| `fleet` | session and agent machinery: the launchers, the handoff supervisor, seat isolation | `fleet-instructions.md` |
| `doctrine` | how the project should work: what it preserves ([#32](https://github.com/nedschorus/nedschorus/issues/32)), instruction delivery ([#30](https://github.com/nedschorus/nedschorus/issues/30)), the research bundles | `doctrine-instructions.md` |
| `sidebar` | nothing — the spare, for off-topic questions | `sidebar-instructions.md` |

**A naming caution, unresolved:** these are one-word names, which the project's own rule in `CLAUDE.md` warns against for anything likely to be grepped — and `gatekeeper` collides with the git-gatekeeper program it works on, so `~/agents/gatekeeper` reads as the program's home. The names stand until the user rules otherwise; when searching, prefer the full path (`docs/agents/gatekeeper-instructions.md`) over the bare word.

## How many run

Two or three at a time is the working pattern; **five is the ceiling the user set**. Four is allowed and unusual — if you find yourself launching a fourth, it is worth asking whether one of the running seats is finished.

## When a seat's work is done

A seat's pile is finished when everything in it that an *agent* can do is done, and what remains has been handed to the user with the groundwork prepared. Several piles end in an act only he can perform — creating a GitHub account, applying branch protection, approving an instruction-class change — so a seat whose completion is defined as "the outcome happened" can never finish, and an agent with no completion criterion either invents adjacent work or stalls waiting for an event it cannot observe.

Each brief states its own criterion. The shared shape: **land what you can, prepare what you cannot, tell the user exactly what is left and whose it is, write a handoff, and stop.** Stopping is a legitimate ending.

## The two ways a seat ends

They are different, and confusing them loses work.

**Paused** — the seat's current series is done and nobody is using it. Exit the session. Its handoff, home directory and branch all stay exactly as they are, which is what makes the seat resumable weeks later: relaunching the same name boots from that handoff. This is the ordinary ending, and it needs no cleanup.

**Retired** — the name is being freed or repurposed. Three steps, in order:

1. **Stop the stream first.** A running seat writes a fresh handoff at every recycle, so archiving while its supervisor is alive only clears the file until the next one. Exit the session and confirm no supervisor remains.
2. **Archive the handoff**, do not delete it — these files are machine-local and not in git, so a delete is unrecoverable. Rename it `~/.claude/handoffs/<seat>-handoff-retired-YYYY-MM-DD.md`. If that name already exists, append `-2`, `-3`; never rename onto an existing archive.
3. **Release the home and the branch.** `git worktree remove ~/agents/<seat>` (not `rm` — the worktree stays registered otherwise, and `git worktree prune` is then needed), and then delete the branch separately with `git branch -d <seat>` if the name is to be reused, since removing a worktree leaves its branch behind. A seat launched but never used may have an empty directory and no worktree at all; `rmdir` is correct there.

`choirmaster` is the live case: the founding seat, whose work has been redistributed into the seats above. Its 2026-08-12 handoff was archived on 2026-08-13 so a future agent of that name starts fresh, and the user intends to reuse the name for a coordinating seat later. Until he does, no `choirmaster` seat is defined by this model.

## Why there is no master agent

Considered and declined 2026-08-13. A coordinating seat has nothing to do while the user chooses which seats run, and the evidence is `choirmaster` itself: created to direct, it drifted into being an ordinary topic thread. Revisit if seats ever need to hand work to each other without the user in the loop — which today they cannot, since a seat's only channel to another seat is through him.

## Filing new work

Put a new task in the seat whose existing context makes it cheapest — not the emptiest seat. If it fits none of them, it is either a question for `sidebar`, answered and forgotten, or the seed of a new pile, which is the user's decision rather than a default.

## Launching a seat

From the **Mac**, using the Mac's own checkout of this repository:

```
~/Projects/nedschorus/scripts/launch-claude-ubuntu <seat> \
    --first-prompt-file /home/nedlern/Projects/nedschorus/docs/agents/seat-first-prompt.md
```

The script runs on the Mac and reaches the box over SSH. The `--first-prompt-file` path is a **box-side** path, because the supervisor reads that file on the box. One generic file serves every seat: the agent learns its own name from its working directory, so nothing needs substituting.

Three things about that command worth knowing before you rely on it:

- **It is attach-or-create.** Running the name again attaches to the live session rather than starting a second one — and in that case `--first-prompt-file` does nothing, because there is no new session to seed. To exit a seat, exit the session inside it (`/exit`); to leave it running, detach from tmux (`Ctrl-b d`).
- **A handoff outranks the first-prompt file.** If `~/.claude/handoffs/<seat>-handoff.md` exists, the supervisor boots from it; `--first-prompt-file` seeds only a session that has no handoff waiting, which in practice means a seat's very first launch. To seed a seat from another thread's context deliberately, copy that thread's handoff into the seat's name before launching.
- **A session that ends without writing a handoff leaves nothing behind.** The next launch of that name starts from the first-prompt file as if new. That is why a seat being paused should hand off first, and why the handoff — not the session — is the thing that carries a seat's thread.

The launcher creates the seat's home as a checkout on its own branch **before the session starts**, because project settings — the status line, the recycle hook, the instruction-file guard — are read from `.claude/` in the working directory at session start, and an agent booted into a bare directory runs without any of them.

## What separate branches do and do not protect

Each seat works on its own branch, and git permits a branch in only one worktree at a time. That is what normally keeps two seats from editing the same files or racing each other's pushes, and it is a check rather than a guarantee: `git worktree add --force` overrides it, a separate clone of the repository is invisible to it, and two seats editing the same file on different branches simply defer their collision to the merge.

It protects nothing outside git. `~/.claude/handoffs/`, the job scratch directories, and the tmux server are shared machine-local state that every seat writes. Two seats using the same *name* would collide there regardless of branches — which is why one name means one seat.

**Nothing that matters is left only in a session.** Work belongs in commits and pushes; decisions belong in the governing documents and issues. The exception is the handoff, which is durable, machine-local, never pushed, and the one artifact that makes a paused seat resumable — so a seat exited without one loses its thread even though its committed work is safe.
