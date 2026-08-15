<!-- provenance: runtime=codex model=gpt-5.6-sol effort=xhigh cell=restate tier=good target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/agents/agent-seat-model.md -->

# The agent seat model

1. This document explains how work on the Ubuntu machine is assigned among agents with persistent names, and why that assignment scheme was chosen.
2. The user established this model on 2026-08-14, after a day when parallel agent sessions were created or accumulated faster than anyone kept track of them.
3. The instructions specific to each seat are stored in the same directory as this document, in files named `<seat>-instructions.md`, with `<seat>` replaced by the seat’s name.

## The grouping rule

1. Tasks should be assigned together when they benefit from the same relevant background and history, rather than merely to distribute the quantity of work evenly.
2. To decide whether two tasks belong to the same seat, ask whether completing the first task would give the agent knowledge or understanding that improves its ability to complete the second.
3. If doing the first task would help with the second in that way, both tasks should go to the same seat.
4. If it would not, the tasks should go to different seats, even if doing so means that one of the seats has no current work.
5. The following statements give the user’s reasoning, and the purpose of this model is to implement that reasoning.
6. An agent performs better when its context is small and limited to the relevant topic than when it carries history from unrelated work.
7. In this model, an agent becoming confused by unrelated context is considered costly, while leaving an agent unused is not considered costly.
8. An unused agent seat costs nothing, so unrelated collections of work must not be combined merely to give an otherwise idle seat something to do.
9. The intended unit of work is a sequence of related tasks; after that sequence, the agent should create a handoff and clear or leave its current context before beginning a different sequence.
10. Because a seat may be resumed after several weeks, its name must make its subject recognizable from the session list alone, without requiring anyone to open the session or its files.

## How many seats exist, and how many run

1. Seven seats have been defined.
2. Normally, two or three of those seats are active at the same time, and the user does not want more than five active simultaneously.
3. When a seat finishes its current group of work, its running agent is simply exited.
4. The seat’s name and handoff information are preserved, allowing the same topic thread to be resumed days or weeks later if relevant work returns.
5. The table identifies each seat and the collection of related work assigned to it.
6. `gatekeeper` owns the sequence of credential-related work required to activate the git-gatekeeper.
7. `sanity-checker` owns work concerning review quality, specifically the sanity-checker reviewer and the system called the “md-review grid.”
8. `skill-builder` owns the queue of proposed skills and the procedure for processing or emptying that queue.
9. `ghi` owns knowledge about GitHub issues and the tools associated with that work.
10. `fleet` owns the mechanisms used to manage sessions and agents, including launchers, handoffs, and isolation between agents.
11. `doctrine` owns decisions and documentation about how the project should operate, including preservation, delivery of instructions, and research.
12. `sidebar` is the spare seat for questions unrelated to the established topics, so those questions do not introduce irrelevant context into a topic-specific seat.

## Why there is no master agent

1. The idea of having a master or coordinating agent was considered and rejected on 2026-08-14.
2. A dedicated coordinating seat has no useful role while the user personally decides which two or three seats should be active.
3. The evidence cited is that `choirmaster`, although created to direct other work, gradually became a normal thread devoted to its own topics instead.
4. The decision should be reconsidered if seats eventually need to transfer work among themselves without the user participating in those transfers.

## Retiring a seat, and reusing its name

1. A seat is retired by exiting its running agent, but the seat’s handoff file remains after that agent exits, and the launcher will give that handoff to the next agent launched under the same seat name.
2. Consequently, permanently retiring a seat name requires archiving `~/.claude/handoffs/<seat>-handoff.md`.
3. Archiving means renaming the handoff to `<seat>-handoff-retired-<date>.md`; it must not be deleted because these handoff files exist only on that machine and are not preserved in Git.
4. If the launcher finds no handoff for a seat name, it starts the agent with the normal initial or “ignition” prompt, which is the intended behavior when an old seat name is reused for a new purpose.
5. The document records two cautions learned on 2026-08-14.
6. A running supervised agent stream continues producing handoff files.
7. If someone archives a stream’s handoff while its supervisor is still running, the handoff remains absent only until the supervisor next recycles the agent and writes another one; therefore, the live stream must be retired first and its handoff archived afterward.
8. A seat’s agent home is itself a Git worktree checked out on that seat’s branch.
9. Therefore, making a retired name available for reuse also requires handling both `~/agents/<seat>` and the branch checked out there by using `git worktree move` or `git worktree remove`, rather than deleting the directory directly with `rm`.
10. `choirmaster` is the current concrete example of this retirement-and-reuse process: the work originally assigned to it is being reassigned among the topic-specific seats listed earlier, and the user plans eventually to reuse `choirmaster` as the name of a coordinating agent.
11. Its handoff dated 2026-08-12 was archived on 2026-08-14, ensuring that a future agent named `choirmaster` begins without inheriting the context of a stream that has ceased to exist.

## Filing new work

1. When a new task appears, it should be assigned to the seat whose existing knowledge and context reduce the effort needed to perform it, rather than to whichever seat currently has the least work.
2. If the task fits none of the existing groups, it either goes to `sidebar` when it is a temporary question to be answered and then forgotten, or it becomes the first task in a new collection of related work.
3. Creating that new collection is a choice the user must make, rather than an automatic response by an agent.
4. The document calls this possible new collection a “seventh pile,” although it has already listed seven seats. I cannot tell whether “seventh” means the seventh substantive topic pile after excluding the spare `sidebar`, or whether the number is inconsistent and the text would produce an eighth seat overall.

## Mechanics every seat shares

1. A seat is launched from the Mac with a single command, and the supplied first-prompt file gives an agent with no prior context everything it needs, including instructions for determining which seat it occupies.
2. The shown command runs `~/Projects/nedschorus/scripts/launch-claude-ubuntu`, passes the desired seat name as `<seat>`, and supplies `/home/nedlern/Projects/nedschorus/docs/agents/seat-first-prompt.md` through `--first-prompt-file`.
3. The first-prompt file’s path refers to its location on the Ubuntu box, because the supervisor reads that file on the box rather than on the Mac from which the launch command is issued.
4. The same first-prompt file can initialize every seat because an agent derives its seat name from its working directory, so the file itself does not require seat-specific substitutions.
5. `--first-prompt-file` supplies context only to the seat’s first session; after the supervisor’s first recycling of that session, the seat’s own handoff becomes the source of context.
6. Launching uses attach-or-create behavior: invoking the launcher again with a seat name that is already running reconnects to the existing live agent instead of creating another agent with the same name.
7. Each seat’s working home is `~/agents/<seat>` on the Ubuntu box, and each seat uses its own Git branch.
8. Separate homes and branches prevent two seats from modifying the same working files or racing to push competing work from the same checkout.
9. The launcher initially creates the seat’s home as an empty directory rather than as a checked-out Git worktree.
10. During its first run, the first-prompt file instructs the agent to turn that empty directory into a checkout by running `git worktree add`; the document says that adding a worktree into an already existing but empty directory was tested successfully on 2026-08-14.
11. When a seat starts, the supervisor reads `~/.claude/handoffs/<seat>-handoff.md` if that file exists.
12. To initialize a seat with context from another thread, either give that thread’s context file to the launcher using `--first-prompt-file <path>`, or copy the other thread’s handoff to the new seat’s expected handoff path before launching it.
13. The handoff produced by a forked session records the state and location at which that forked session eventually stopped, rather than describing the earlier point in history from which it was forked.
14. If the fork point itself is what the new seat needs to understand, direct it to the corresponding `-dialog-` extract or to the raw transcript instead of relying on the forked session’s final handoff, and explicitly identify which portion of that history matters.
15. No information or work that must survive should exist only inside an agent session.
16. Completed work must be committed to Git and pushed, while decisions must be written into the documents and issues that govern the project.
17. Once a seat’s work has been pushed, its running session can be exited at any time without losing that work.
