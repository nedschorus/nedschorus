<!-- provenance: runtime=codex model=gpt-5.6-luna effort=xhigh cell=defect-hunt tier=floor target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/agents/agent-seat-model.md -->

1. [L3] “Ruled by the user 2026-08-14” is impossible as of the supplied current date, 2026-08-13. The document presents a future ruling as established provenance. Confidence: sure.

2. [L7] “The test for whether two tasks belong to one seat is: does doing the first make the agent smarter about the second? If yes, same seat. If no, separate seats” is not executable: “smarter” has no observable meaning or test. It is also too rigid; two tasks may share context but require isolation, or share no context but need one atomic seat. Confidence: sure.

3. [L12] “Idle agents are free. There is no cost to a seat nobody is using” is false literally. Idle seats can consume machine capacity, model quotas, supervision, and administrative attention. Confidence: sure.

4. [L12] “never merge two unrelated piles” is broader than can hold. An ordinary counterexample is a temporary capacity constraint where only one seat is available and the user explicitly accepts mixed work. Confidence: sure.

5. [L13] “The natural unit of work is a series of related tasks, then handoff-and-clear before the next series” requires work but defines neither “series” nor “handoff-and-clear.” An agent cannot tell when a series is complete, what “clear” does, or when it is safe to proceed. Confidence: sure.

6. [L14] “names must be recognisable in a session list without opening anything” is contradicted by the later seat name `ghi`, which is not recognisable without the table. Confidence: sure.

7. [L18] “Seven seats are defined; two or three run at a time, five is the user's maximum” supports incompatible readings. It does not say whether four or five may run, or whether “two or three” is an ordinary target rather than a limit. Confidence: sure.

8. [L18] “A seat whose group is finished is simply exited; its name and handoff remain” is not guaranteed by simply exiting. A session can exit without having written a handoff, leaving no context for resumption. The sentence supplies no handoff-creation or validation step. Confidence: sure.

9. [L25] “`ghi` | GitHub-issue knowledge and the tooling around it” introduces a cryptic name that is hard to find or interpret in a session list. It also conflicts with CLAUDE.md’s definition: “use explicit, clear and precise multi-part names” for names likely to be grepped, with more explicit names when ambiguity exists. Confidence: sure.

10. [L28] “the spare — off-topic questions, so they never pollute a topic seat” makes an absolute guarantee without any routing or enforcement mechanism. A user can send a topic question to `sidebar`, or an off-topic question can turn into project work. Confidence: sure.

11. [L32] “Considered and declined 2026-08-14” is impossible as of the supplied current date, 2026-08-13. Confidence: sure.

12. [L32] “A coordinating seat has nothing to do while the user is the one choosing which two or three seats run” is wrong literally. A coordinating seat could still monitor state, resolve conflicts, track handoffs, or route work while the user chooses the active seats. Confidence: sure.

13. [L32] “Revisit if seats ever need to hand work to each other without the user in the loop” requires future work but defines neither who detects that condition nor what “need” means. There is no clear stopping point for the revisit. Confidence: unsure — this may be intended only as a policy reminder.

14. [L36] “retiring a name has one required step: archive `~/.claude/handoffs/<seat>-handoff.md`” conflicts with the later requirement to “retire the stream first and archive second.” For a live seat, exiting the stream and archiving the handoff are two required operations, not one. Confidence: sure.

15. [L36] “rename it `<seat>-handoff-retired-<date>.md`” is not executable precisely. The date format, timezone, and collision behavior are unspecified, so two archives on the same date can target the same name. Confidence: sure.

16. [L36] “A launch that finds no handoff starts clean on the ordinary ignition prompt” uses the undefined term “ordinary ignition prompt.” The file does not state its contents, location, or how it differs from `--first-prompt-file`, so an agent cannot determine what will run. Confidence: sure.

17. [L38] “Two cautions learned 2026-08-14” records a future event as already learned. Confidence: sure.

18. [L38] “archiving while its supervisor is still running only clears the file until the next recycle” supports two incompatible readings. Renaming clears the current pathname, but it does not clear the archived handoff data; the archive remains and a new current file may later be created. Confidence: sure.

19. [L38] “retire the stream first” requires an operation that is never defined. “Stream” is not given a command, state, or completion test, so the agent cannot know how to retire it or verify that it stopped writing. Confidence: sure.

20. [L38] “the agent home is a git worktree on the seat's branch” conflicts with the later statement, “The launcher creates that home as an empty directory, not a checkout; the first-prompt file has the agent make it one on its first run.” It also conflicts with the referenced first-prompt file: “The launcher makes your home a checkout of the project on your own branch before your session starts.” These cannot all describe the same launch lifecycle. Confidence: sure.

21. [L38] “via `git worktree move` or `git worktree remove`, not `rm`” gives two materially different operations without stating which applies in which case, what happens to uncommitted work, or how branch ownership is resolved. The retirement procedure has no clear stopping point. Confidence: sure.

22. [L40] “the founding seat's work” introduces “founding seat” without defining it. The reader can infer that it concerns `choirmaster`, but cannot tell whether it means the first seat created, the directing seat, or something else. Confidence: unsure — the preceding sentence suggests one interpretation.

23. [L40] “Its 2026-08-12 handoff was archived on 2026-08-14” again records an event on a future date. Confidence: sure.

24. [L44] “`sidebar` (a question, answered and forgotten)” is narrower than the referenced `sidebar-instructions.md`, which also assigns small errands such as status checks, file reads, and one-off scripts. It also assumes every question can be forgotten, although a question may become durable project work. Confidence: sure.

25. [L44] “it is the seed of a seventh pile” conflicts with “Seven seats are defined” and the table’s seven existing piles, including `sidebar`. It is unclear whether this means the already-existing seventh pile or an eighth pile, and no corresponding seat procedure is stated. Confidence: sure.

26. [L48] “the first-prompt file tells a zero-context agent everything” is an overbroad absolute claim. The first-prompt file directs the agent to other files and does not resolve the seat-count ambiguity, retirement procedure, handoff format, or failure cases described above. Confidence: sure.

27. [L51-L52] The launch command contains the literal placeholder “`<seat>`”, while the later sentence says “nothing needs substituting.” The launcher requires an actual name and rejects the angle brackets, so the command is ambiguous as written. Confidence: sure.

28. [L52] “`/home/nedlern/Projects/nedschorus/docs/agents/seat-first-prompt.md`” does not exist in the inspected checkout. The document calls it a box-side path, so it might intentionally refer to a different canonical checkout, but that distinction is not stated and the command is not executable from the available context. Confidence: unsure — the missing path may exist in the box’s separate main checkout.

29. [L55] “`--first-prompt-file` seeds only the first session; after the first recycle the seat's own handoff takes over” omits reachable cases where the first session exits without a handoff, requests no restart, or has an unreadable handoff. In those cases there may be no successor session or no usable handoff to take over. Confidence: sure.

30. [L55] “One generic file serves every seat” leaves the roster boundary undefined. The launcher accepts arbitrary names, but the document defines seven seats and gives no rule for whether an unlisted name may launch, become a new pile, or must be rejected. Confidence: sure.

31. [L56] “on its own branch — which is what keeps two seats from touching the same files or racing each other's pushes” misstates the mechanism. Separate worktree directories isolate checkout files; branch names alone do not prevent shared files outside those directories or concurrent operations against a remote branch. Confidence: sure.

32. [L56] “verified 2026-08-14” claims verification on a future date. Confidence: sure.

33. [L57] “the supervisor reads `~/.claude/handoffs/<seat>-handoff.md` if one exists” defines a store without defining the handoff format, validity rules, malformed-file behavior, or stale-file behavior. An agent cannot create or assess a usable handoff from this file alone. Confidence: sure.

34. [L57] “copy that thread's handoff to `~/.claude/handoffs/<seat>-handoff.md` before launching” is incomplete. It does not explain how to locate the source handoff, what happens if the destination already exists, whether copying overwrites live state, or how to verify that the copy is complete. Confidence: sure.

35. [L58] “point the new seat at the `-dialog-` extract or the raw transcript instead” introduces two unexplained artifacts and no path or procedure for locating them. “`-dialog-`” is also a cryptic search name rather than a self-documenting filename. Confidence: sure.

36. [L59] “Nothing durable lives in a session” is false literally and conflicts with the document’s own references to durable handoffs and raw session transcripts. A pushed branch does not make machine-local session state, task state, or transcript state disappear. Confidence: sure.

37. [L59] “Work is committed and pushed” is an unqualified invariant that fails for read-only sessions, unfinished work, failed pushes, and uncommitted local artifacts. No behavior is stated for those ordinary cases. Confidence: sure.

38. [L59] “A seat can be exited at any time without loss once its work is pushed” is too broad. Pushing the branch does not preserve an unwritten handoff, local task records, untracked files, or the session context needed to resume. Confidence: sure.

clean sections: none
