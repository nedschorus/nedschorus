<!-- provenance: runtime=codex model=gpt-5.6-luna effort=xhigh cell=defect-hunt tier=floor target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/agents/skill-builder-instructions.md -->

1. “Your pile is **the queue of proposed skills**”

   This conflicts with the linked seat model, which defines a pile as “the body of related work a seat owns” and explicitly says it is “not an ordered queue.” The later instruction to take “the next” item reinforces the conflicting ordered reading. This can make the agent process tasks sequentially instead of selecting by shared context and user ruling. Confidence: sure.

2. “every build has the same shape … so the seventh should cost far less than the first.”

   “Every” is broader than the file can support: the listed work includes different kinds of skills, and the pile also includes a queue-drain procedure rather than a skill build. A build may also be ruled out or blocked instead of following the stated build shape. “Same shape” and “far less” have no measurable meaning. Confidence: unsure, because “shape” might mean only the high-level authoring sequence.

3. “reading two of those closely is the cheapest way to learn the house style.”

   “Closely” has no completion criterion, and no rule says which two examples to choose or how to establish that the style has been learned. The agent can read arbitrary examples for an indefinite amount of time. Confidence: sure.

4. “Your work is done when each issue below is either built and landed, ruled out with the reason recorded in the issue, or left with a stated blocker.”

   The pile was defined to include the queue-drain procedure, but this completion condition covers only the seven table issues. It therefore permits the seat to be considered complete while that procedure remains untouched. Confidence: sure.

5. “built and landed, ruled out with the reason recorded in the issue, or left with a stated blocker”

   The workflow later produces a reachable fourth state: a skill can be committed and pushed while awaiting the Mac-side merge. The file does not say whether that is landed, blocked, or incomplete. It also treats recording a reason as sufficient for “ruled out,” while the referenced `ghi-write` instructions require recording the outcome and closing the issue. Confidence: sure.

6. “You will not finish all seven in one series — build one, hand off, and let the next session take the next.”

   “Will not” is an unsupported absolute. An ordinary counterexample is a session in which the remaining issues are already resolved or can all be completed quickly. It also imposes one-item sequencing despite the seat model saying a pile is not an ordered queue. Confidence: sure.

7. “Then write a handoff and stop.”

   This conflicts with the `handoff` skill: if the handoff supervisor cannot start or is not watching, that skill explicitly says to continue working rather than stop. The sentence gives no condition for the stop and can leave the active work abandoned. Confidence: sure.

8. “consequence-ranked test plans”

   Neither this file nor the local riders file defines what is ranked, what the consequence scale is, or how ties and unranked claims are handled. The agent cannot determine what the #18 skill is supposed to produce from this description alone. Confidence: unsure, because the external issue may define the term.

9. “with a five-part gate a finding must pass to be reported”

   The five parts are not named or linked to a local document. A future agent cannot implement, test, or even apply this gate without retrieving unavailable issue content. Confidence: sure.

10. “A/B comparison of a baseline agent against a candidate over trigger cases, reporting raw counts”

    “Trigger cases” and “raw counts” are undefined: the file does not say what triggers a case, what is counted, or which outcomes are reported. The description is insufficient to construct the evaluation. Confidence: unsure, because issue #23 may define these terms externally.

11. “isolated adversarial review; filed as a comparison question rather than a settled design”

    “Isolated,” “adversarial review,” and “comparison question” have no operational definition or comparison criteria. The agent cannot tell what context to exclude, what artifacts to compare, or what output is expected. Confidence: unsure, because issue #19 may supply the missing procedure.

12. “read-only, evidence-grounded design producing one recommendation and honest exits”

    “Evidence-grounded” and especially “honest exits” are undefined. The file gives no criteria for acceptable evidence or for what counts as an exit, so the required output cannot be judged or completed consistently. Confidence: unsure, because issue #17 may define them.

13. “[#24] is the **queue-drain procedure** — how the project empties its wiki queue, its pair queue, and its `draft`-labelled issue queue.”

    The procedure exists only as an external issue link; there is no local body or explicit local path containing it. Under the stated only-this-context constraint, the agent cannot know how to drain any queue or how that procedure governs this pile. Confidence: sure under the stated context restriction.

14. “A skill is instruction-class, so it lands only through the user's walked approval, enforced by `.claude/hooks/instruction-file-guard.py`.”

    The referenced hook describes itself as a “Soft block, not a wall.” It intercepts only particular tool calls; a direct shell or programmatic write can bypass it. Its nonempty `.walk-approved` marker is also consumed without checking that it contains the exact approval for the current change. Thus the literal “only” and “enforced” claims are false. Confidence: sure.

15. “Rationale asides get cut”

    The authoring checklist says, “Explain why a rule matters instead of stacking MUSTs.” The phrase can therefore be read either as removing all rationale or only removing incidental parenthetical prose; the file does not distinguish them. Following the first reading removes context the checklist requires, while following the second requires an unstated boundary. Confidence: unsure, because “aside” may be intended to mean only irrelevant rationale.

16. “A settled draft gets an md-review before it lands, which is `scripts/md-review-grid.py`.”

    The script only launches the eight review cells and saves their reports. The `md-review` skill additionally requires reading every report, keeping judgments provisional, formulating a response, and walking the findings with the user. Equating the review with the script can cause an agent to run the script and land without completing the review process. Confidence: sure.

17. “read the issue and its riders”

    Only issues #18, #20, and #21 have rider/detail files listed locally. The other four issues have no rider path in the checkout, so this instruction leaves a reachable missing-file case: the agent cannot know whether a nonexistent rider is intentionally absent or has been overlooked. Confidence: sure.

18. “draft the skill, walk it with the user item by item”

    If “draft the skill” means writing it in `.claude/skills/`, this order conflicts with the instruction-class guard, which blocks that write until walked approval has already been recorded. If it means drafting elsewhere, the file gives no location or handoff between that draft and the protected skill. Confidence: sure.

19. “md-review the settled draft, apply what the review finds”

    The referenced review process requires a further user walk of the review findings, but this sequence applies them directly. It also gives no stopping condition for applying findings, no definition of “settled,” and no branch for failed or missing review cells. Confidence: sure.

20. “then commit and push for his Mac-side agent to merge.”

    This hardcodes the interim merge lane. `CLAUDE.md` says the git-gatekeeper is the permanent path and that the Mac-side merge lane applies only until its credential work lands. Once that work lands, following this sentence would bypass the required gatekeeper path. Confidence: sure.

21. “The `sanity-checker` seat owns review methodology — how reviews are delivered…”

    The seat model assigns that seat “review quality” and whether its reviewer joins the md-review grid; it does not assign all review delivery to it. The broader phrase conflicts with or at least expands the seat’s defined ownership, while the next sentence says ordinary use of review machinery is not a boundary crossing. Confidence: unsure, because “review quality” might be intended to include delivery methodology.

22. “Changing how it behaves is.”

    This is an incomplete sentence, and “it” and “review machinery” have no defined boundary. An agent cannot determine whether changing prompts, reviewer counts, scripts, thresholds, or report handling requires routing to the other seat. Confidence: sure.

23. “a skill is walked before it lands.”

    The stated build sequence walks the draft, then applies md-review findings, then commits and pushes. Those later review changes are not included in the walk described, so the final artifact can differ from the walked artifact. This also conflicts with the instruction-class guard’s approval requirement. Confidence: sure.

clean sections: none.
