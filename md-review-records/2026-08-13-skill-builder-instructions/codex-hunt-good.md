<!-- provenance: runtime=codex model=gpt-5.6-sol effort=xhigh cell=defect-hunt tier=good target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/agents/skill-builder-instructions.md -->

1. > “Your pile is **the queue of proposed skills** … so the seventh should cost far less than the first.”
   >
   > “let the next session take the next.”
   >
   > “the order is his”

   “Queue,” the numbered ordinals, and “the next” support an ordered-list reading, while the final sentence says no order exists until the user rules. A successor therefore cannot know whether “next” means the next table row, the next unprocessed issue, or a newly user-selected skill. This can cause work to begin without the required ruling. Confidence: sure.

2. > “every build has the same shape”

   This absolute is broader than the referenced checklist supports. For example, the checklist gives scripted testing to agent-facing skills with silent failures but live-use evaluation to user-supervised interaction skills. Those builds have materially different validation shapes. An agent could force inappropriate steps onto a skill because the sentence does not say how abstract “shape” is. Confidence: unsure — it is defensible if “shape” means only the high-level read/draft/walk/review sequence, but the phrase does not establish that scope.

3. > “reading two of those closely is the cheapest way to learn the house style.”

   “Cheapest” is an unsupported absolute. An ordinary counterexample is an agent for whom the mandatory checklist plus one short example provides enough information at lower cost than two examples; another is an agent already familiar with the house style. The claim can consume unnecessary context and gives no basis for choosing among examples whose lengths and purposes differ considerably. Confidence: sure.

4. > “each issue below”
   >
   > “You will not finish all seven”

   Issue #24 also appears below this sentence, making “each issue below” naturally include eight issues, while “all seven” refers only to the skill issues. It is therefore unclear whether #24 must reach one of the stated terminal states before the pile is complete. This can either omit owned work or incorrectly treat the governing procedure as another skill build. Confidence: sure.

5. > “**Your work is done when** each issue below is either built and landed, ruled out with the reason recorded in the issue, or left with a stated blocker.”
   >
   > “build one, hand off … Then write a handoff and stop.”

   These give incompatible stopping points unless “your work” silently changes meaning from the seat’s whole pile to one session’s series. Under the first sentence, work is not done until every issue is terminal; under the second, the occupant must stop after one build. This makes completion and handoff status unreliable. Confidence: sure.

6. > “built and landed”
   >
   > “commit and push for his Mac-side agent to merge”

   “Landed” ordinarily means merged to `main`, but the later sentence and `CLAUDE.md` assign that merge to the user’s Mac-side agent and prohibit agents from pushing to `main`. Thus the seat’s completion condition depends on an external action it cannot perform. The agent can either wait indefinitely or call a merely pushed branch “landed.” Confidence: sure.

7. > “left with a stated blocker”

   This terminal state does not say where the blocker is stated, what qualifies as a blocker, who owns the remaining action, or whether a transient failure counts. Unlike the “ruled out” branch, it does not require the issue to record the result. Because this branch declares work done, a temporary API failure or an unsupported assertion of blockage can permanently strand an issue without durable state. Confidence: sure.

8. > “build one, hand off, and let the next session take the next. Then write a handoff and stop.”

   The explicitly referenced seat model and `handoff` skill make writing the handoff the mechanism that lets the successor start. Literally, this sentence hands off and lets the successor act before instructing the current session to write the handoff. If “hand off” already includes writing it, the next sentence commands the same operation again. The order is therefore impossible or duplicative depending on the reading. Confidence: sure.

9. > “riders in `docs/issues/queue/18-write-test-plan-agent-native-riders.md`”

   “Riders” is introduced as project-specific terminology without a definition of its authority or lifecycle. The referenced packets say they await queue-drain dispositions, while some contents describe themselves as binding rulings. An agent cannot tell whether riders are mandatory requirements, proposals to drain before building, or merely source evidence. Acting under different readings materially changes the skill. Confidence: sure.

10. > “honest exits”

    This is not standard SDLC terminology and does not identify any terminal states or the conditions selecting them. It therefore does not make the `design-change` proposal understandable enough to compare with the other candidates during the prescribed first action. Confidence: unsure — issue #17 may define the expression, but the instruction only requires reading #24 and #18 before making the comparison.

11. > “how the project empties its wiki queue, its pair queue, and its `draft`-labelled issue queue”

    “Empties” promises an outcome without a stopping rule. Ordinary reachable counterexamples include an item receiving an “edit” disposition and remaining queued or a new item arriving during a drain. The agent cannot know whether completion means processing a snapshot, processing every item present at the end, or reaching a globally empty state; the last reading can run without termination. Confidence: sure.

12. > “its wiki queue, its pair queue”

    These store names are not mapped to paths, and “pair queue” is neither standard nor readily searchable as a directory name—the visible directory is `docs/issues/queue/`. The agent must locate, measure, and drain the stores, but the sentence does not establish what “pair” means. Confidence: unsure — linked issue #24 may provide the missing mapping, but it was not available from this checkout and the names are not self-documenting here.

13. > “it lands only through the user's walked approval, enforced by `.claude/hooks/instruction-file-guard.py`.”

    The absolute enforcement claim is false literally. The hook describes itself as a soft block, handles only configured Edit/Write/NotebookEdit calls, accepts any nonempty `.walk-approved` content without verifying it against the claimed approval, and does not prevent a shell write or the commit of an already-modified file. An ordinary bypass is writing the file through a command rather than a guarded editing tool. Treating this as mechanical enforcement can allow unapproved instruction changes to land. Confidence: sure.

14. > “Rationale asides get cut”

    This supports a reading incompatible with the required skill-authoring checklist, which says: “Explain why a rule matters instead of stacking MUSTs.” “Rationale aside” is not distinguished from the reason that scopes or makes an instruction understandable. A literal application can remove reasons the governing checklist requires and undermine the stated zero-context bar. Confidence: unsure — “aside” could mean only detachable historical anecdotes, but the file never limits it that way.

15. > “A settled draft gets an md-review before it lands, which is `scripts/md-review-grid.py`.”

    The relative clause incorrectly equates the complete md-review with its launcher script. The referenced `md-review` skill requires running the script, reading and triaging every report, keeping judgments provisional until all cells finish, and walking the real problems and proposed actions with the user. The script itself also prints those follow-up instructions. An agent obeying this sentence literally can stop after launching the grid and omit most of the review. Confidence: sure.

16. > “read the issue and its riders”

    This presents riders as a universal input to every build, but the queue identifies rider files only for #18 and #20 and a differently named detail document for #21; it identifies none for #22, #23, #19, or #17. A literal agent must search indefinitely for nonexistent rider material or cannot execute those builds. Confidence: sure.

17. > “apply what the review finds”

    This treats all reviewer output as authoritative. The referenced md-review procedure explicitly requires triage and a judgment about which reported problems are real; independent cells can overlap, produce false positives, or recommend incompatible actions. Applying everything can damage the draft and bypass the required user ruling on proposed dispositions. Confidence: sure.

18. > “A settled draft gets an md-review before it lands”
   >
   > “md-review the settled draft, apply what the review finds, then commit and push”

    The version being committed is not the reviewed version whenever findings cause edits. Landing it violates the first sentence; reviewing it again re-enters the same sequence, with no stopping condition if another review produces another change. The sequence also places the only explicit item-by-item walk before these edits, although instruction-class changes require walked approval. This creates a choice between landing unreviewed or unapproved changes and entering an unbounded review loop. Confidence: sure.

19. > “`review-change` | defect-first code review at an exact revision, with a five-part gate a finding must pass to be reported”
   >
   > “The `sanity-checker` seat owns review methodology — how reviews are delivered”

    Building `review-change` necessarily defines how code reviews are delivered, so the queue assigns the skill-builder work that the boundary assigns to `sanity-checker`. The referenced sanity-checker brief reinforces the collision by calling code-review-prompt work “plainly” its subject. The skill-builder cannot both take #22 to a terminal state and avoid deciding review methodology. Confidence: sure.

20. > “seats cannot hand work to each other directly”

    As a literal capability claim, this is too broad. An ordinary counterexample exists in the explicitly reachable sanity-checker brief, which directs that seat to route surviving work by writing it into the receiving seat’s brief or an issue-queue document. Shared repository artifacts therefore provide a direct durable routing path even if live seat-to-seat messaging is absent. The absolute may cause an agent to reject a supported routing mechanism. Confidence: unsure — “hand work” may intend only live assignment or communication, but that narrower meaning is not stated.

21. > “Using the review machinery on your own draft is ordinary work, not a boundary crossing. Changing how it behaves is.”

    “Review machinery” has no fixed referent. It can mean only the eight-cell md-review grid, the entire md-review skill and walk, the sanity-checker prompt, or the queued `review-change` capability. Because the term controls the ownership boundary, different readings change whether an action is allowed locally or must be routed to the user. Confidence: sure.

clean sections: none
