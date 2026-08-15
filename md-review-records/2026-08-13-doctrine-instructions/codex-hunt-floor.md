<!-- provenance: runtime=codex model=gpt-5.6-luna effort=xhigh cell=defect-hunt tier=floor target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/agents/doctrine-instructions.md -->

1. Lines 3, 22, 42 — “Read the seat model … first”; “read it first”; and “## First action … Read the founding plan”. These give incompatible startup orders. An agent cannot know whether the seat model or founding plan is the first required action. Confidence: sure.

2. Lines 5, 22 — “each one amends the same foundation” versus “Most items here amend or extend it”. “Each” excludes the exceptions implied by “most”. If “same foundation” means something else, that foundation is undefined. Confidence: unsure because the terms might be intended to refer to different foundations.

3. Line 7 — “the item the user chose has a written ruling in its durable home — an issue body, a governing document, or a CLAUDE.md line … and the others are left where the next session can find them.” “Ruling”, “durable home”, “governing document”, “settled”, and “the others” are not operationally defined. This does not identify how to choose among destinations, what happens when several artifacts are involved, or where unresolved work is to be left. Confidence: sure.

4. Line 13 — “the git-gatekeeper’s slice 6 needs a walked-approval evidence format”. The seat model defines “slice” only as a numbered build increment; nothing identifies slice 6 or defines the evidence format, its fields, consumer, validation, or durable home. The assigned design work therefore cannot be executed from this context. Confidence: sure.

5. Line 13 and line 38 — “Coordinate with `gatekeeper` before designing it … whichever of you takes it” versus “review methodology to `sanity-checker`” and “the gatekeeper’s specification belongs to `gatekeeper`”. The file gives no rule for deciding whether this evidence format is doctrine work, gatekeeper specification, or review methodology. “Coordinate” also has no channel or completion condition. Confidence: unsure because the evidence format might be intended as a gatekeeper specification rather than review methodology.

6. Line 14 — “reconciling the entry checkpoint, the rewrite policy, and the gatekeeper’s import check”. The target names the gatekeeper’s import check without providing its specification or an explicit local path, and “reconciling” supplies neither an output nor a stopping condition. An agent cannot tell when this item is settled. Confidence: sure.

7. Line 15 — “infrequently-updated files committed immediately after update; append-type logs at logical breakpoints.” “Infrequently”, “append-type”, and “logical breakpoints” have no thresholds or decision procedure. Reachable cases such as an update spanning breakpoints or a failed commit are unaddressed. Confidence: sure.

8. Line 16 — “Usage versus expectation”. The name does not identify whose usage, whose expectation, or what object is becoming obsolete. The accompanying “open research thread” has no research question, deliverable, or stopping point. Confidence: sure.

9. Line 17 — “denoised artifacts”, “monitoring method”, “instruction compression”, “deliberate scrub”, “instruction precedence”, “output styles”, “context clearing”, and “memory maintenance”. These terms are not defined by the target or its explicit local references, so the two “research bundles” have no clear scope or completion boundary. Confidence: sure.

10. Line 18 — “sparring pairs, on-tap domain experts, spy-triaged oversight. Design capture; research pending.” “Spy-triaged oversight” is unexplained, and no actors, triggers, data, mechanism, or output are specified. “Research pending” is an unbounded assignment with no stopping point. Confidence: sure.

11. Line 22 — “the fix ladder”. This named concept does not occur in the target, the seat model, or the explicitly referenced founding plan. A proposal cannot identify which rule or decision the phrase denotes. Confidence: sure.

12. Line 24 — “changes land only through the user’s walked approval, enforced by `.claude/hooks/instruction-file-guard.py` and a quoted marker.” The referenced hook is explicitly documented as a soft block, not a wall: it only runs for certain tool calls, accepts any nonempty marker content without checking that it quotes approval, and can be bypassed by direct writes or other tools. The absolute claim is therefore false when read literally, and the mechanism leaves its bypass and validation cases unstated. Confidence: sure.

13. Line 24 — “expect walks rather than commits.” Approval and committing are different operations: a walk authorizes an instruction change, while a commit makes the change durable. This wording supports the reading that a walked CLAUDE.md change need not be committed, conflicting with the repository’s durable-artifact rules. Confidence: unsure because “rather than” could be intended only to contrast approval with ordinary review.

14. Line 30 — “This project’s axis: simple-to-operate over simple-to-build; mechanical guarantees over trained habit; deterministic code over LLM prompts wherever the choice exists.” A singular “axis” is defined as three separate comparisons, with no precedence or tie-breaking rule. An agent cannot apply the instruction when those priorities conflict. Confidence: sure.

15. Line 31 — “Machinery with no consumer gets cut.” “Consumer” is not defined, and the universal rule has ordinary counterexamples such as required audit, safety, compliance, or forensic machinery whose consumer is intermittent or future. Confidence: sure.

16. Lines 32, 34 — “A deterministic script is not traded for probabilistic agent behaviour” conflicts with the nearby instruction that absolutes “can backfire” and should be used cautiously. The prohibition has no exception for cases where a deterministic script is impractical, unsafe, or unable to express the required judgment. Confidence: sure.

17. Line 38 — “Where a ruling lands in their territory, write it down and tell the user, who routes it”. “Territory” and “lands” do not identify a destination, and “write it down” does not specify which artifact or home applies. Overlapping rulings and a user who does not route the work have no stated behavior or stopping point. Confidence: sure.

18. Line 38 — “seats cannot hand work to each other.” Read literally, this is false: seats can communicate through issues, handoffs, shared files, or other machine-local state. If it is meant as a governance prohibition rather than a capability claim, the sentence does not say so. Confidence: sure.

19. Line 42 — “Then ask the user which item he wants thought about, and put one question to him first: whether #31’s … format should be designed here or in `gatekeeper`.” The sentence has two incompatible readings of “first”: the item-selection question first, or the #31 ownership question first. It also mandates an unrelated #31 question when the user chooses another item, without stating whether work waits for both answers. Confidence: unsure because the intended question order is grammatically ambiguous.

20. Line 42 — “doing it twice is worse than doing it once in the wrong seat.” This is an absolute comparative claim with no defined measure of “worse”. Two parallel designs can provide useful cross-checking, while work done in the wrong seat can create greater rework or defects. Confidence: sure.

clean sections: none.
