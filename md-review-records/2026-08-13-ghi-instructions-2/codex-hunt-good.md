<!-- provenance: runtime=codex model=gpt-5.6-sol effort=xhigh cell=defect-hunt tier=good target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/agents/ghi-instructions.md -->

1. Line 3: “it defines the words used here — pile, seat, walked approval, instruction-class, handoff.”

   `walked approval` and `instruction-class` are not used anywhere else in this file. Taken literally, the sentence falsely identifies them as necessary vocabulary and makes a reader expect approval constraints that the brief never invokes. Confidence: sure.

2. Lines 5 and 26: “Your pile is **GitHub-issue knowledge and the tooling around it**” and “**memory instrumentation** — echoing every memory read and write to the console.”

   Nothing in the file connects general memory instrumentation to GitHub-issue knowledge, issue-routing doctrine, or the stated shared design documents. This makes #39 read either as assigned work or as an accidentally included adjacent concern, which also affects the completion condition. Confidence: unsure because the inaccessible linked issue #39 may explain a relationship absent from this file.

3. Line 7: “its two companion tools are designed or ruled out.”

   “The companions” lists three items: run-agent, the reference-integrity checker, and memory instrumentation. The phrase could mean the first two, any two, or all three with an incorrect count. Consequently, the agent cannot determine which designs or rulings are required before stopping. Confidence: sure.

4. Line 7: “ghi-info has a built first slice or a written reason it should wait, its two companion tools are designed or ruled out, and each issue below carries the current state.”

   Several completion states are not operationally defined. The file does not identify where a “written reason” must exist or who decides it is sufficient; what artifact or decision makes a tool “designed” or “ruled out”; whether the ruling must come from the user; which occurrences count as “each issue below”; or what part of an issue must “carry” which state. Different agents can satisfy this sentence with materially different—and possibly merely conversational—outputs. Confidence: sure.

5. Line 13: “a dedicated agent that answers ‘which issues bear on this file, or this edit?’”

   This naturally includes arbitrary code, wiki, and document files or edits. The referenced design instead says questions about “the wiki or the code” receive the fixed `out-of-scope` response, and line 20 describes asks in connection with issue writes. A caller therefore cannot know whether ghi-info maps issues to arbitrary repository edits or only advises issue authors. Confidence: sure.

6. Line 13: “Its answers come from a local mirror of issue state rather than live GitHub calls — a rule stated by its purpose … rather than by prohibition.”

   The referenced design explicitly prohibits the agent from fetching GitHub state: “Answer from the mirror only — never fetch issue state from GitHub.” Thus “rather than by prohibition” is factually wrong. Purpose alone is also not executable: a live call could still appear cheap and fast, so this wording permits the behavior the design forbids. Confidence: sure.

7. Line 17: “read it before proposing anything gate-shaped.”

   `gate-shaped` is undefined and supports incompatible readings. It might mean only the rejected credential/single-door architecture, or any mechanism that intercepts and refuses writes. The latter reading prohibits the soft-refusal hook and write tool described immediately afterward and required by the referenced design. The absolute “anything” makes this more than harmless shorthand. Confidence: sure.

8. Line 18: “An agent still convinced after reconsidering passes exactly one resubmit by writing its reasoning into a marker file.”

   This defines a one-write override mechanism without stating how the marker is associated with the refused issue, payload, or refusal reason. A stale marker, an intervening issue write, two overlapping attempts, or a failed resubmit can consume or apply the override to the wrong operation. Neither this file nor the referenced design states or discards those reachable cases. Confidence: sure.

9. Line 20: “The `ghi-write` skill … governs every issue write — filing, editing a body, commenting, promoting queue material.”

   “Every issue write” is broader than both the list and the referenced skill’s triggers. Ordinary counterexamples are closing or reopening an issue and changing only its title, labels, or milestone. The referenced design expressly lets close/reopen and non-body edits bypass the write hook. Confidence: sure.

10. Line 20: “that fallback is the current state of the world, because the ask tool does not exist yet. Building it is your pile.”

    The referenced design makes the failed-ask ladder permanent even after the ask tool exists: “A failed ask never blocks a write.” The stated causal relationship therefore mischaracterizes fallback as an interim consequence of the missing tool. Moreover, the required build makes “does not exist yet” false during this seat’s intended work, with no stated transition in the brief. Confidence: sure.

11. Line 24: “one command to invoke a Claude or Codex agent headlessly from any caller, shell or Python, either runtime.”

    “Any caller” has no platform, installation, authentication, permission, working-directory, or transport limits. An ordinary shell or Python caller without the selected runtime executable or its credentials cannot invoke it. This makes the promised interface and its acceptance boundary impossible to determine literally. Confidence: sure.

12. Line 25: “verifying that links resolve and that cited revision-paths exist.”

    `revision-paths` is not defined: it could mean `revision:path`, a path cited alongside a commit, a URL pinned to a revision, or merely a versioned file path. Those interpretations require different parsing and existence checks, so the checker cannot be designed from this description. Confidence: unsure because linked issue #42 may define the syntax; that issue was unavailable from this environment.

13. Line 25: “the designated home for the broader question of what else code can check instead of an LLM.”

    If this is part of the companion’s assigned design work, “what else” ranges over an unbounded set of model tasks and has no inventory boundary or stopping test. If “home” merely routes future discoveries, it assigns no present work at all. The sentence does not choose between those readings. Confidence: unsure because “designated home” may be intended only as routing metadata.

14. Line 26: “echoing every memory read and write to the console.”

    “Every” lacks a defined access surface. Direct filesystem access, an unhooked tool, startup loading, or a new runtime path is an ordinary counterexample to hook coverage. The mechanism states neither its coverage boundary nor what happens when an access bypasses or outlives the hooks. Confidence: sure.

15. Line 26: “hooks that remind rather than block, with no context injection.”

    The audience for the reminder is undefined. If it is the agent, “no context injection” leaves no stated way for the agent to receive it; if it is the human, a headless or unattended run can have no console observer. The mechanism does not state what happens when console output is captured, hidden, or unavailable. Confidence: sure.

16. Line 30: “comments are for genuinely new events only.”

    This supports the reading that any genuinely new event may be commented. The referenced `ghi-write` skill permits only two fixed event kinds—an instance outcome or a ruling challenge—and its tool denies other comments. An agent following the broader reading can produce a write that the required mechanism refuses. Confidence: sure.

17. Line 30: “A to-do is a task rather than a memory.”

    This duplicates a checkout-level definition. `CLAUDE.md` says: “Before saving or proposing a memory, check whether it is actually a task — something to do, removed when done. If so make it a task, not a memory; memory holds durable facts and every memory write requires the user's approval.” The local version omits the checkout definition’s removal condition, durable-fact distinction, and approval rule, leaving two non-identical classification statements that can drift or yield different decisions. Confidence: sure.

18. Line 34: “seats cannot hand work to each other directly.”

    Taken literally, `cannot` is broader than the actual technical constraint. Seats can communicate through ordinary shared artifacts such as commits, issue records, or machine-local files; the file establishes a workflow rule, not an impossibility. This wording can cause unnecessary user escalation whenever any cross-seat information transfer is needed. Confidence: sure.

19. Line 38: “the answer decides the order of your whole pile.”

    Deciding whether #41 precedes ghi-info orders only those two items. It does not order #42 or #39, nor resolve which “two companion tools” the completion condition means. The claimed consequence is therefore impossible literally and leaves the remainder of the pile unordered. Confidence: sure.

clean sections: none
