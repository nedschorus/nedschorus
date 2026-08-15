<!-- provenance: runtime=codex model=gpt-5.6-luna effort=xhigh cell=restate tier=floor target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/agents/agent-seat-model.md -->

# The agent seat model

1. This document explains how work on the Ubuntu computer is allocated among agents with distinct names, and explains the reason for that allocation.

2. The user established these rules on 2026-08-14, after experiencing a day when parallel sessions multiplied more quickly than anyone could keep track of.

3. Each seat has a brief stored next to this document, using the filename pattern `<seat>-instructions.md`.

## The grouping rule

1. Tasks should be grouped according to the context and knowledge they share, rather than according to how much work they contain.

2. To decide whether two tasks belong to the same seat, ask whether completing the first task would give the agent useful understanding that would help it complete the second task.

3. If the answer is yes, the two tasks should use the same seat.

4. If the answer is no, they should use separate seats, even if separating them means one of the seats sometimes has nothing to do.

5. The following points state the user's reasons for adopting this model.

6. An agent with a small, concentrated body of relevant context should perform better than an agent burdened with unrelated history.

7. The costly failure is confusion caused by unrelated context; leaving an agent temporarily unused is not considered costly.

8. Idle agents consume nothing important, so two unrelated collections of work should never be merged merely to keep a seat occupied.

9. The basic unit of work is a sequence of related tasks, followed by handing off the relevant state and clearing the seat before beginning a different sequence.

10. Because a seat may be resumed weeks after it was last used, its name must be understandable from a session list alone, without requiring someone to open the session.

## How many seats exist, and how many run

1. There are seven defined seats; normally two or three operate simultaneously, and five is the maximum number the user permits to operate at once.

2. When all work belonging to a seat is finished, that seat is exited. Its name and handoff remain available, allowing the same topic thread to be resumed days or weeks later when relevant work returns.

3. The `gatekeeper` seat owns work concerning the credentials needed to activate the git-gatekeeper.

4. The `sanity-checker` seat owns review quality, including the sanity-checker reviewer and the md-review grid.

5. The `skill-builder` seat owns the candidate-skill queue and the process for draining that queue.

6. The `ghi` seat owns knowledge about GitHub issues and the tools used with them.

7. The `fleet` seat owns session and agent infrastructure, including launchers, handoffs, and isolation.

8. The `doctrine` seat owns questions about how the project ought to operate, including preservation, instruction delivery, and research.

9. The `sidebar` seat is the spare seat for unrelated questions, so those questions do not introduce irrelevant context into a topic-specific seat.

## Why there is no master agent

1. The idea of a master or coordinating seat was considered and rejected on 2026-08-14.

2. A coordinating seat would have no necessary work while the user personally decides which two or three seats should run; the evidence for this is that `choirmaster`, which was created to direct other work, gradually became an ordinary seat focused on one topic.

3. This decision should be reconsidered if seats ever need to transfer work to one another without the user participating in the transfer.

## Retiring a seat, and reusing its name

1. To retire a seat, exit it; its handoff file remains after the exit, and the launcher will give that handoff directly to the next agent that uses the same name.

2. Therefore, retiring a seat name requires archiving `~/.claude/handoffs/<seat>-handoff.md` by renaming it to `<seat>-handoff-retired-<date>.md`; the file must be preserved rather than deleted because it exists only on the machine and is not tracked by Git.

3. If a launch finds no handoff file, it starts the agent from the normal initial prompt with no previous handoff context, which is the desired behavior when a retired name is reused.

4. The following are two cautions learned on 2026-08-14.

5. A live agent stream continues to write handoffs, so archiving its handoff while the supervisor is still running only removes the file temporarily; the next recycle will write it again. The stream must therefore be retired before its handoff is archived.

6. The agent's home directory is a Git worktree on the seat's branch, so making a name available for reuse also requires handling `~/agents/<seat>` and the branch associated with it, using `git worktree move` or `git worktree remove` rather than `rm`.

7. `choirmaster` demonstrates this process: the work originally assigned to the founding seat is being redistributed among the topic seats listed above, and the user plans to reuse the `choirmaster` name later for a coordinating agent.

8. The handoff created for `choirmaster` on 2026-08-12 was archived on 2026-08-14, so a future agent named `choirmaster` will begin without resuming the old stream, which no longer exists.

## Filing new work

1. When a new task arrives, assign it to the seat whose existing context makes the task least costly to handle, rather than assigning it to whichever seat currently has the least work.

2. If no existing seat is a good fit, the task should either go to `sidebar` as a temporary question that is answered and then discarded, or be treated as the beginning of a new category of work; creating that new category requires the user to decide and must not happen automatically.

## Mechanics every seat shares

1. A seat is launched from the Mac with one command, and the first-prompt file gives an agent with no prior context all necessary information, including how to determine which seat it is.

2. The launch command is `~/Projects/nedschorus/scripts/launch-claude-ubuntu <seat> --first-prompt-file /home/nedlern/Projects/nedschorus/docs/agents/seat-first-prompt.md`.

3. The path supplied to `--first-prompt-file` refers to a location on the Ubuntu box because the supervisor reads that file on the box.

4. The same generic first-prompt file is used for every seat. The agent identifies its seat name from its working directory, so the prompt does not need a seat-specific value substituted into it.

5. The `--first-prompt-file` option supplies initial instructions only to the first session; after that session is recycled, the seat's own handoff file supplies the continuing context.

6. Launching uses attach-or-create behavior: if the requested name already has a live agent, launching that name attaches to the existing agent instead of creating a second agent.

7. Each seat has its own directory at `~/agents/<seat>` on the Ubuntu box and uses its own Git branch; this separation prevents seats from modifying the same files or competing while pushing changes.

8. The launcher creates the seat's home as an empty directory rather than as an existing checkout. On its first run, the agent uses the first-prompt instructions to turn that directory into a worktree; `git worktree add` can create a worktree inside an already existing empty directory, and this was verified on 2026-08-14.

9. When a seat arrives, the supervisor reads `~/.claude/handoffs/<seat>-handoff.md` if that file exists.

10. To give a seat context from another thread, either pass that thread's file as `--first-prompt-file <path>` when launching, or copy the thread's handoff into `~/.claude/handoffs/<seat>-handoff.md` before launching the seat.

11. The handoff from a forked session records the point where that session stopped, not the point from which it was forked.

12. If the subject of interest is the fork point itself, the new seat should instead be directed to the `-dialog-` extract or the unprocessed transcript, and the instructions should identify which portion of that history is relevant.

13. A session is not a durable place for important state to live.

14. Code or other work must be committed and pushed, while decisions must be recorded in the governing documents and issues. Once the work has been pushed, the seat can be exited at any time without losing that work.
