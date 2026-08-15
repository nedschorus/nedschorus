<!-- provenance: runtime=codex model=gpt-5.6-luna effort=xhigh cell=defect-hunt tier=floor target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/agents/ghi-instructions.md -->

1. **Line 5:** “Your pile is **GitHub-issue knowledge and the tooling around it**.” Later, #39 is included as a companion, but it is described as generic memory instrumentation, not GitHub-issue tooling. The shared seat model also lists only #46, #41, and #42 under `ghi`. The file does not explain why #39 belongs here. Confidence: unsure — memory instrumentation might be intended as GHI-adjacent, but that connection is unstated.

2. **Line 7:** “ghi-info has a built first slice or a written reason it should wait.” `Slice` is defined as a numbered build-plan increment, but neither this file nor the referenced design defines numbered slices or what the first one contains. “A written reason” also has no specified artifact or acceptance condition, so completion cannot be determined consistently. Confidence: sure.

3. **Line 7:** “its two companion tools are designed or ruled out.” The later “The companions” section lists three companions: #41, #42, and #39. The text never says whether #39 is excluded because it is not considered a tool. Confidence: unsure — #39 may intentionally be a non-tool, but that reading is not stated.

4. **Line 7:** “designed or ruled out.” Neither outcome has a definition, required contents, decision owner, or evidence standard. An agent can keep designing indefinitely or declare a tool ruled out without a documentable stopping condition. Confidence: sure.

5. **Line 7:** “each issue below carries the current state.” “Current state” is not defined as an issue-body field, label, open/closed status, or other operation. The completion condition therefore does not tell the agent what it must update or how to know it is current. Confidence: sure.

6. **Line 11:** “it landed 2026-08-11 after an md-review, with the walk scaffolding deliberately stripped so it stands alone.” `md-review` and `walk scaffolding` are unexplained project terms with no explicit reference. A future agent cannot know what was removed or what consequence that has for using the design. Confidence: sure.

7. **Line 13:** “It lives on the box at `~/agents/ghi-info`, is resumed headlessly for each question, and answers on exit.” The same file says the design is awaiting build and that the ask tool does not exist yet; the named `~/agents/ghi-info` directory is also absent in this checkout environment. Taken literally, an unbuilt agent cannot already live there and answer questions. Confidence: sure.

8. **Line 13:** “Its answers come from a local mirror of issue state rather than live GitHub calls — a rule stated by its purpose ... rather than by prohibition.” The referenced design explicitly says: “Answer from the mirror only — never fetch issue state from GitHub (no gh queries, no API, no web).” This sentence misstates a hard design prohibition as merely a purpose-based preference, which could lead to live GitHub calls being treated as permissible. Confidence: sure.

9. **Line 17:** “That plan survives marked SUPERSEDED ... — read it.” The plan is not named or linked here, and neither the marker’s location nor its syntax is given. The referenced design indirectly names a rejected plan, but this instruction requires the agent to discover that relationship rather than stating it. Confidence: unsure — reading the design first may make the plan findable, but the instruction itself is incomplete.

10. **Line 17:** “before proposing anything gate-shaped.” `Gate-shaped` has no defined boundary. The agent cannot tell whether a proposal involving a hook, refusal, write path, or validation check falls into the prohibited category. Confidence: sure.

11. **Line 18:** “passes exactly one resubmit by writing its reasoning into a marker file.” This defines a mechanism without naming the marker, specifying its scope, or stating what happens if the marker is stale, malformed, written concurrently, or consumed by a failed write. The “exactly one” guarantee is therefore not executable in reachable failure cases. Confidence: sure.

12. **Line 20:** “governs every issue write.” Taken literally, this includes writes through unhooked paths such as `gh api`, MCP tools, creative shell quoting, the web UI, or another agent. The referenced design explicitly accepts such enumeration holes, so the claim is broader than the mechanism can enforce. Confidence: unsure — it may be intended as a normative instruction only for this seat’s own work.

13. **Line 20:** “Building it is your pile.” The nearest antecedent is “the ask tool,” but the surrounding section is about `ghi-info`; “it” could also refer to the live `ghi-write` skill. Those readings assign different work, and the last would conflict with the statement that `ghi-write` is already live. Confidence: unsure — context suggests `ghi-info`, but the sentence does not establish that.

14. **Line 24:** “one command to invoke a Claude or Codex agent headlessly from any caller, shell or Python, either runtime.” “Any caller” is broader than the listed shell/Python cases, and “either runtime” has no clear grammatical referent. The command’s supported inputs, environments, and failure behavior are not defined well enough to decide whether it is a prerequisite for `ghi-info`. Confidence: unsure — the linked issue may define the intended contract, but that content is not available here.

15. **Line 25:** “that cited revision-paths exist.” `Revision-paths` is not defined anywhere in the allowed context. It could mean repository paths at a revision, revision-qualified Git paths, or something else; the checker cannot be designed or evaluated from this description. Confidence: unsure — it may be terminology defined in issue #42, but this file does not provide that context.

16. **Line 25:** “the designated home for the broader question of what else code can check instead of an LLM.” This assigns an open-ended research question to the companion without scope, bounds, or a stopping condition. It can require investigating every possible deterministic check rather than completing a defined checker. Confidence: sure.

17. **Line 26:** “echoing every memory read and write to the console; hooks that remind rather than block, with no context injection.” The memory store and the intercepted read/write operations are undefined. “Every” is also not literally attainable for operations outside the hooks or when a hook fails, is bypassed, or cannot observe a store. No behavior is stated for those cases. Confidence: sure.

18. **Line 30:** “queue documents (`docs/issues/queue/`) hold material whose fate is undecided.” The referenced routing plan distinguishes destination-known pair material in `docs/issues/queue/` from decision queues such as `nc-queue/` and `legacy-feature-queue/`. This wording collapses distinct queues and can route all undecided material into the wrong directory. Confidence: sure.

19. **Line 30:** “A to-do is a task rather than a memory.” This duplicates a definition in `CLAUDE.md`.

   Target definition: “A to-do is a task rather than a memory.”

   `CLAUDE.md` definition: “Before saving or proposing a memory, check whether it is actually a task — something to do, removed when done. If so make it a task, not a memory; memory holds durable facts and every memory write requires the user's approval.”

   The shorter definition omits the removal-when-done distinction and the approval requirement, allowing the two instruction files to drift or an agent to follow the target without the constraints in `CLAUDE.md`. Confidence: sure.

20. **Line 34:** “since seats cannot hand work to each other directly.” The seat model qualifies this as a current condition (“which today they cannot”) and describes it as something to revisit if inter-seat communication becomes necessary. The unqualified absolute can remain wrong once that mechanism exists. Confidence: unsure — it may be intended as a statement of the current system only.

21. **Line 38:** “the answer decides the order of your whole pile.” The linked seat model defines a pile as related work “not an ordered queue.” This sentence gives the pile an explicit execution order and conflicts with that definition, potentially causing the agent to treat the seat brief as a queue. Confidence: sure.

22. **Line 38:** “what ghi-info's first build slice should be.” This repeats the undefined `first build slice` criterion from line 7. The referenced design describes duties and verification items but no numbered build slices, so the first-action proposal has no specified unit to propose. Confidence: sure.

clean sections: title/preamble.
