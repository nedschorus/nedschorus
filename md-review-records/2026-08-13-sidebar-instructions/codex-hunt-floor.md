<!-- provenance: runtime=codex model=gpt-5.6-luna effort=xhigh cell=defect-hunt tier=floor target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/agents/sidebar-instructions.md -->

1. “the questions that belong to no topic seat” (line 5) is undefined. Neither this file nor the seat model states exactly what makes a seat a “topic seat,” so routing is not executable. Confidence: unsure — the contrast with `sidebar` suggests a meaning, but does not state it.

2. “how something in the harness works” (line 9) introduces “harness” without defining or locating it. A future agent cannot know which system is in scope. Confidence: unsure — it may be conventional project terminology, but it is absent from the available context.

3. “Small errands with no home” (line 9) uses “home” ambiguously. The seat model uses “home” for an agent directory, while this appears to mean work with no owning seat. That can produce inconsistent routing. Confidence: unsure.

4. “the user exits and restarts you freely, and that costs nothing precisely because you were never holding anything” (line 13) conflicts with the seat model’s statement that an idle seat is “not literally free” because it retains a directory and branch. Restarting can also consume time and lose transient context. Confidence: sure.

5. “Do not write a handoff at the end of a conversation” (line 17) conflicts with the seat model’s shared ending shape: “write a handoff, and stop,” and with its paused-seat procedure. The file states only that `sidebar` owns no pile, not that it is exempt from handoff rules. Confidence: sure.

6. “If the user asks you to hand off, do it” (line 17) is not executable. The file gives no handoff procedure or content requirements; the referenced model gives a path and purpose, but not how this agent performs the requested operation. Confidence: unsure — the surrounding system may supply an implicit mechanism.

7. “If a conversation here has grown long and wandered” (line 18) provides no stopping point or test for “long” or “wandered.” Agents can restart too early, too late, or disagree about whether the instruction applies. Confidence: sure.

8. “If a question turns into real project work, do not adopt it: name the seat it belongs to — `gatekeeper`, `sanity-checker`, `skill-builder`, `ghi`, `fleet`, or `doctrine`” (line 19) conflicts with the seat model’s rule that work fitting none of the existing seats may be the seed of a new pile, at the user’s decision. It also leaves “real project work” undefined. Confidence: sure.

9. “A question needing deep history from another pile” (line 20) has no threshold or operational meaning. The agent cannot consistently tell when ordinary context has become “deep history,” which affects whether it answers or redirects. Confidence: unsure.

10. “Your work is done when the user's question is answered. There is no larger completion criterion, and none is missing.” (line 22) conflicts with the later requirements to commit and push disk changes and to persist information a topic seat will need. It also conflicts with the referenced model’s shared handoff-and-stop shape. Confidence: sure.

11. “Anything you change on disk is committed and pushed like any other seat's work.” (line 26) is too broad literally. A one-off script can create temporary output, caches, logs, or other files that are not project work and cannot meaningfully be committed or pushed. Confidence: sure.

12. “Anything you learn that a topic seat will need is written where that seat will find it — an issue, a queue document under `docs/issues/queue/`, or the relevant design file.” (line 26) defines a persistence requirement without stating how to determine which seat will need the information, which destination applies, whether an existing artifact is required, or when the task is complete. Confidence: sure.

13. “An answer that exists only in this conversation is lost the moment it closes” (line 26) is broader than established by the file. The user may retain the conversation or transcript, so “lost” is at least ambiguous about whose access is meant. Confidence: sure.

14. “which is the one way this seat can do harm” (line 26) is an absolute claim that is false literally. A wrong answer, an unsafe command, or an incorrect durable artifact are ordinary additional ways for the seat to cause harm. Confidence: sure.

15. “commits carry the session id” (line 28) requires information the available instructions never identify: what the session id is, where to obtain it, or what format it has. This becomes un-executable whenever the seat changes files. Confidence: sure.

16. “nothing is pushed to `main`” (line 28) conflicts with the seat model’s description of the Mac-side agent reviewing branches and merging them to `main`; that merge must eventually update `main`. If the sentence is intended to restrict only this seat, its scope is unstated. Confidence: unsure — a narrow agent-local reading is possible.

17. “Every command you hand him names the machine it runs on — box-side commands take the form `ssh nedlern@ned-box '<command>'`” (line 32) is too absolute. Commands requiring interactive behavior or shell quoting that contains single quotes do not fit that literal form, and machine-independent commands do not inherently need a machine designation. Confidence: sure.

18. “No status report, no inventory, no plan” (line 36) supports an incompatible reading with “checking a status” in line 9. If the first user request is a status check, one instruction permits it while the first-action instruction appears to forbid it. Confidence: unsure — “no” may be intended to restrict only the initial greeting.

clean sections: none
