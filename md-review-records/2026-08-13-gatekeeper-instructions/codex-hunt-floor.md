<!-- provenance: runtime=codex model=gpt-5.6-luna effort=xhigh cell=defect-hunt tier=floor target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/agents/gatekeeper-instructions.md -->

1. “Every task here shares one specification, one program, and one threat model, so each makes the next cheaper.” (line 3) — “Threat model” is not defined in the brief or its local references. “Every” and “each” also overstate the dependency: reviewing PR #55 or applying credential infrastructure does not inherently make evidence-format design cheaper. This can misdirect sequencing. Confidence: sure.

2. “nothing routes through it yet” (line 7) — The referenced test suite routes pushing cases through the program against throwaway repositories. The gate is dormant only for the real main lane; the sentence literally conflates dormant production use with no use. Confidence: sure.

3. “the user's Mac-side seat reviews and merges” (line 7) — This introduces an undefined actor and duplicates the checkout’s canonical definition. The target says “Mac-side seat,” while `CLAUDE.md` says “the user's Mac-side agent reviews and merges” and the seat model lists no Mac-side seat. The ownership and mechanism are therefore ambiguous. Confidence: sure.

4. “Design the walked-approval evidence format. What does the user's approval of an instruction-class change look like as a checkable artifact?” (line 15) — This requires design work but gives no completion condition: there is no defined artifact structure, acceptance test, recording location, or decision point that marks the design complete. Confidence: sure.

5. “Undesigned today, and everything downstream waits on it.” (line 15) — “Everything” is broader than the document supports. The brief itself assigns PR #55 review and status reporting while this design is still undesigned, so those tasks do not wait on it. Confidence: sure.

6. “Class definition and guards: [nedschorus#31](https://github.com/nedschorus/nedschorus/issues/31).” (line 15) — The load-bearing definition of “instruction-class” and “guards” is available only through an external issue, not the local context this brief says is sufficient. Without issue access, the agent cannot determine what belongs to the class or what the guards must enforce. Confidence: sure.

7. “Build slice 6 — the review-evidence check, which enforces that format at the gate.” (line 16) — The slice plan identifies slice 6 as future work but supplies no slice-6 scope, test set, or completion condition. Once the format exists, an agent still cannot determine from the provided context when this build is finished. Confidence: sure.

8. “that is only safe once its own source cannot reach main without walked approval” (line 16) — “Only safe once” is an absolute claim. An independently reviewed, immutable, or manually deployed source could be safe before this particular check exists. Confidence: unsure — the project may intend “safe” only within its chosen threat model, but that scope is not stated here.

9. “(C1/C3: a collaborator with write on this one repository, never an org owner)” (line 17) — `C1/C3` is a cryptic combined label rather than a self-documenting name, and the brief does not identify which requirement belongs to which ruling. An agent must search the specification to understand what is actually settled. Confidence: unsure — the specification does define the codes.

10. “The credential work — the dedicated GitHub account … the dedicated Unix user … the sudoers rule … and moving branch protection's push restriction onto the new account.” (line 17) — This is a multi-system task with no exact account or Unix-user identity, execution procedure, verification condition, or stopping point. “The user does this part” delegates the mutation but does not tell the seat how to track or recognize completion. Confidence: unsure — the delegation may be intentional, but the agent’s remaining responsibility is unspecified.

11. “Also yours: PR #55 … open and awaiting review.” (line 19) — “Also yours” creates an ownership obligation without saying whether the agent must review it, monitor it, respond to feedback, or merely report its state. The bare PR number has no local path or direct location, and the phrase supplies no completion condition. Confidence: sure.

12. “`--issue` stays (a mechanical forcing function is never traded for trained habit)” (line 23) — This supports an incompatible reading with the specification’s definition that `--issue` accepts `none` and that an issue is “never mandated per invocation.” Literally, an agent could read this as requiring a real issue on every check-in rather than requiring an explicit issue-or-`none` choice. Confidence: unsure — the intended forcing function may be the explicit choice, but the sentence does not say that.

13. “the trailer-absence audit is deleted (a detector with no consumer is cost without value)” (line 23) — This is an absolute generalization. A detector can have value through human review, historical evidence, or a future consumer even without automated consuming machinery. The sentence can cause a future agent to discard useful detection solely because its current consumer is absent. Confidence: unsure — the project’s ruling may intentionally limit “value” to this system’s current consumer model.

14. “C7 is struck to zero.” (line 23) — `C7` is not self-documenting, and “struck to zero” does not identify the behavior it changes. The target does not say that this concerns the absence of privileged-mode guards on `--repo` and `--remote`, so an agent cannot apply the ruling without searching elsewhere. Confidence: sure.

15. “check whether PR #55 has merged” (line 31) — The brief gives no status source, command, or local record for this check. If the PR is still open, it also gives no instruction for what follows beyond the general report. Confidence: sure.

16. “## The road, in order” (line 13) and “ask which step he wants first” (line 31) — The numbered road and the statements that downstream work waits on evidence define a sequence: evidence format, slice 6, then credential work. Asking which step the user wants first permits an incompatible reading in which step 3 starts before steps 1 and 2. Confidence: sure.

clean sections: `## Boundaries`
