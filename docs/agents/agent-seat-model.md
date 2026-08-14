# The agent seat model

How work on the Ubuntu box is divided among named agents, and why it is divided that way. Ruled by the user 2026-08-14 after a day in which parallel sessions accumulated faster than anyone tracked them. The per-seat briefs live beside this file as `<seat>-instructions.md`.

## The words this model uses

Defined here because the briefs use them as if established, and an agent reading one cold has nowhere else to look.

- **Seat** — a named, long-lived agent identity: a name, a home directory on the box, its own git branch, and a brief. `gatekeeper` is a seat. A seat is *occupied* by a session, and outlives any one session: sessions recycle, the seat persists. Note the one place this word is used loosely: the **Mac-side review seat**, which merges branches to `main`, is not one of the seats defined here — it is the user's own agent on his Mac, outside this model entirely.
- **Pile** — the body of related work a seat owns. Not a queue and not an ordered task list: a pile is a *subject area* with shared context, and the tasks in it are named by the seat's brief rather than enumerated anywhere as a list to be worked through in order.
- **Brief** — the file `docs/agents/<seat>-instructions.md`. It states the seat's pile, the issues and PRs in it, what to read, its boundaries against other seats, and its first action.
- **Walked approval** — the user's approval given item by item through a walk (the `walk-me-through` skill: material presented one item at a time, each ruled on separately) rather than as a single yes to a bundle. Certain changes require it, and one mechanism records it: the approver's exact words are written into `.walk-approved` at the repository root, where the instruction-file guard consumes them for the one write they approve. Written **walked approval** throughout; the hyphenated form *walked-approval* appears only as a compound adjective, as in "walked-approval evidence".
- **Instruction-class** — files that tell agents how to behave: `CLAUDE.md`, `CLAUDE.local.md`, and anything under `.claude/`. They change only with walked approval, enforced by a hook rather than by rule.
- **Slice** — one numbered increment of a build plan, built and landed on its own. The git-gatekeeper's plan has five original slices plus a sixth added later by ruling, which is why "all five slices are built" and "build slice 6" are both true.
- **C-numbers** (`C1`, `C3`, `C7`…) — the identifiers of the git-gatekeeper's credential and enforcement rulings, defined in `docs/cross-project/git-gatekeeper-design.md` § The credential and enforcement. They are meaningful only inside that document; grepping the bare token across the repository is noise.

## The grouping rule

**Group tasks by shared context, not by workload.** The test for whether two tasks belong to one seat is: *does doing the first make the agent smarter about the second?* If yes, same seat. If no, separate seats — even when that leaves a seat idle.

The user's reasoning, which this model exists to serve:

- An agent with minimal, focused context is smarter than one carrying unrelated history. Confusion is the expensive failure, not idleness.
- **Idle agents are free.** There is no cost to a seat nobody is using, so never merge two unrelated piles to keep a seat busy.
- The natural unit of work is a *series of related tasks*, then handoff-and-clear before the next series.
- Seats are resumed weeks later, so **names must be recognisable in a session list** without opening anything.

## How many seats exist, and how many run

Seven seats are defined; **two or three run at a time**, five is the user's maximum. A seat whose group is finished is simply exited; its name and handoff remain, so the thread can be resumed days or weeks later when that topic comes back.

| Seat | The pile it owns |
|---|---|
| `gatekeeper` | the credential road to activating the git-gatekeeper |
| `sanity-checker` | review quality: the sanity-checker reviewer and the md-review grid |
| `skill-builder` | the candidate-skill queue and the queue-drain procedure |
| `ghi` | GitHub-issue knowledge and the tooling around it |
| `fleet` | session and agent machinery: launchers, handoffs, isolation |
| `doctrine` | how the project should work: preservation, instruction delivery, research |
| `sidebar` | the spare — off-topic questions, so they never pollute a topic seat |

## Why there is no master agent

Considered and declined 2026-08-14. A coordinating seat has nothing to do while the user is the one choosing which two or three seats run: today's evidence is that `choirmaster`, created as a directing seat, drifted into being an ordinary topic thread. Revisit if seats ever need to hand work to each other without the user in the loop.

## When a seat's work is done

A seat's pile is finished when everything in it that an *agent* can do is done, and whatever remains has been handed to the user with the groundwork prepared. Several piles end in an act only the user can perform — creating a GitHub account, applying branch protection, approving an instruction-class change — so a seat whose completion is defined as "the outcome happened" can never finish, and an agent with no completion criterion either invents adjacent work or stalls waiting for an event it cannot observe.

Each brief therefore states its own completion criterion. The shared shape: **land what you can, prepare what you cannot, tell the user exactly what is left and who must do it, write the handoff, and stop.** Stopping is a legitimate ending, not a failure — the seat is exited and its name resumed when that pile comes back.

## Retiring a seat, and reusing its name

A seat is retired by exiting it — but its **handoff file outlives it**, and the launcher will boot the next agent of that name straight into it. So retiring a name has one required step: archive `~/.claude/handoffs/<seat>-handoff.md` (rename it `<seat>-handoff-retired-<date>.md`, do not delete — these files are machine-local and not in git). A launch that finds no handoff starts clean on the ordinary ignition prompt, which is what a reused name should do.

Two cautions learned 2026-08-14. **A live stream keeps writing handoffs**: archiving while its supervisor is still running only clears the file until the next recycle, so retire the stream first and archive second. And **the agent home is a git worktree on the seat's branch** — freeing a name for reuse also means dealing with `~/agents/<seat>` and the branch it holds, via `git worktree move` or `git worktree remove`, not `rm`.

`choirmaster` is the live example: the founding seat's work is being redistributed into the topic seats above, and the user intends to reuse the name later for a coordinating agent. Its 2026-08-12 handoff was archived on 2026-08-14 so a future `choirmaster` starts fresh rather than resuming a stream that no longer exists.

## Filing new work

When a new task arrives, put it in the seat whose existing context makes it cheapest — not the emptiest seat. If it fits none of them, it either belongs in `sidebar` (a question, answered and forgotten) or it is the seed of a seventh pile, which is a decision for the user rather than a default.

## Mechanics every seat shares

- **Launch,** from the Mac, in one line — the first-prompt file tells a zero-context agent everything, including how to find out which seat it is:

  ```
  ~/Projects/nedschorus/scripts/launch-claude-ubuntu <seat> \
      --first-prompt-file /home/nedlern/Projects/nedschorus/docs/agents/seat-first-prompt.md
  ```

  The path is a **box-side** path, since the supervisor reads the file on the box. One generic file serves every seat: the agent learns its own name from its working directory, so nothing needs substituting. `--first-prompt-file` seeds only the first session; after the first recycle the seat's own handoff takes over. Launching is attach-or-create — running the same name again attaches to the live agent rather than starting a second one.
- **Home and branch:** each seat lives in `~/agents/<seat>` on the box, on its own branch — which is what keeps two seats from touching the same files or racing each other's pushes. The launcher creates that home as an **empty directory, not a checkout**; the first-prompt file has the agent make it one on its first run (`git worktree add` into an empty existing directory works, verified 2026-08-14).
- **Context on arrival:** the supervisor reads `~/.claude/handoffs/<seat>-handoff.md` if one exists. To seed a seat from another thread's context, pass `--first-prompt-file <path>` to the launcher, or copy that thread's handoff to `~/.claude/handoffs/<seat>-handoff.md` before launching.
- **A forked session's handoff describes where it ended, not where it forked.** When the fork point is the subject, point the new seat at the `-dialog-` extract or the raw transcript instead, and say which part of the history matters.
- **Nothing durable lives in a session.** Work is committed and pushed; decisions are recorded in the governing documents and issues. A seat can be exited at any time without loss once its work is pushed.
