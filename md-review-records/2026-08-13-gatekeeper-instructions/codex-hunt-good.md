<!-- provenance: runtime=codex model=gpt-5.6-sol effort=xhigh cell=defect-hunt tier=good target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/agents/gatekeeper-instructions.md -->

1. “Every task here shares one specification, one program, and one threat model”

   The specification and program are identified later, but no threat model is named, pathed, or defined in the brief or its explicit references. A future agent cannot determine which assumptions constitute the authoritative threat model or check new work against it. Confidence: sure.

2. “Read [the seat model](agent-seat-model.md) for how seats work”

   The referenced seat model says the launcher creates an empty directory and the agent turns it into a worktree. Its explicitly referenced first-prompt file says the launcher creates the checkout before the session, and that an agent finding no checkout must stop rather than retrofit it. The current launcher implements the latter behavior. Obeying the former during a launch failure would make the agent continue without project settings and guards. Confidence: sure.

3. “`scripts/git-gatekeeper.py` is built through all five slices” conflicts with “Build slice 6.”

   “All five” normally states an exhaustive total, while the road subsequently identifies a sixth slice that remains unbuilt. The references reveal the intended history—five original slices followed by an added sixth—but the brief itself supports both “the build is complete” and “one build slice remains.” Confidence: sure.

4. “The gate is dormant: no host holds a main-capable credential” and “the user's Mac-side seat reviews and merges.”

   Updating protected `main` through a GitHub merge requires an authenticated actor with permission to perform that update. The canonical design also says the live protection currently admits `NedLern`. Thus either the Mac or GitHub-mediated session uses a main-capable credential, contradicting “no host,” or “credential” narrowly means a credential installed for the gatekeeper; that qualification is absent. This changes what credential inventory and activation work the agent reports. Confidence: sure.

5. “The full review history — two md-review grids, a subtraction review, and every ruling with its reasoning — is in `md-review-records/2026-08-09-git-gatekeeper-design/`.”

   The later PR #55 description says PR #49 review rulings are folded into the slice plan, outside that directory. If “full review history” means all gatekeeper review history, the claim is false; if it means only the 2026-08-09 design review, that scope is unstated. An agent relying on this sentence before reopening a question can miss the later code-review rulings. Confidence: sure.

6. “roughly forty decisions are recorded with dates and grounds”

   The referenced Codex disposition record describes the completed walk as “26 items across dispositions.md and this file.” Counting individual findings inside batch approvals produces other, much larger totals; the claimed figure is not reproducible from a stated counting rule. This makes it impossible to tell whether the agent has found the complete set. Confidence: unsure, because “decision” might informally count selected subitems within the approved batches.

7. “What does the user's approval of an instruction-class change look like as a checkable artifact? Undesigned today”

   The explicitly referenced slice plan points to `.claude/hooks/instruction-file-guard.py`, which already defines a checkable artifact: `.walk-approved`, containing the user’s exact approval words and consumed by one permitted write. The brief does not distinguish “no approval artifact exists” from “the existing transient marker is unsuitable as durable gate evidence.” The two readings lead respectively to reinvention or reuse of a mechanism that may not satisfy the gate’s needs. Confidence: sure.

8. “Design the walked-approval evidence format.”

   This required work has no stated completion boundary. The brief names no resulting artifact, required properties, decision record, validation obligations, or point separating completed format design from slice-6 implementation. The final go-ahead requirement controls when work starts, not when it is complete. Confidence: sure.

9. “Undesigned today, and everything downstream waits on it.”

   “Everything” is broader than the actual dependency. PR #55 can be reviewed independently, and preparatory credential work such as creating the Unix identity can occur before the evidence format even though activation cannot. Taken literally, the sentence unnecessarily freezes independent work. Confidence: sure.

10. “Build slice 6 — the review-evidence check, which enforces that format at the gate.”

    This does not presently define executable build work. The references say the format is undesigned and provide no slice-6 request field, evidence lookup, protected-class detection behavior, refusal contract, acceptance cases, or completion test. If the user selects this step—as the first-action question permits—the agent cannot determine what implementation would count as complete. Confidence: sure.

11. “that is only safe once its own source cannot reach main without walked approval”

    “Only safe” is an absolute broader than the technical claim can sustain. Ordinary counterexamples include a self-updater restricted to signed artifacts or pinned hashes, neither of which inherently requires this project’s walked-approval mechanism. Confidence: unsure, because “safe” may be intended narrowly as “satisfies this project’s chosen approval invariant,” but that scope is not stated.

12. “the sudoers rule pointing at a root-owned copy outside every checkout that keeps itself current from main”

    This combines incompatible Unix properties without defining the missing privilege boundary. A normally protected root-owned file cannot update itself while running as the dedicated non-root credential user. Giving that user permission to overwrite or replace it weakens the root-owned protection the design relies on. No updater identity, replacement protocol, validation boundary, or failure behavior resolves the conflict. Confidence: sure.

13. “Requires an org owner to apply; the user does this part.”

    The listed work mixes GitHub administration with host administration. Moving the protection restriction may require an organization owner, but creating a Unix user, installing a root-owned file, and configuring sudoers require machine-root authority instead. “This part” can mean either the entire credential step or only its GitHub portions, leaving the agent unable to determine its own implementation and handoff boundary. Confidence: sure.

14. “Also yours: PR #55 … open and awaiting review” together with “check whether PR #55 has merged”

    The first statement is an undated mutable status, while the prescribed check handles only one possible transition. A pull request may be closed unmerged, superseded, converted to draft, or remain open with requested changes. In all those cases “has merged” is false, but “open and awaiting review” may also be false, and the brief gives no resulting course or accurate status interpretation. Confidence: sure.

15. “Consult `dispositions.md` and `codex-dispositions.md` there before reopening any settled question” conflicts with “What is settled, and must not be relitigated.”

    “Before reopening” implies that consultation can permit reopening, while “must not be relitigated” forbids it absolutely. The file does not distinguish reconsideration based on new facts from repetition of previously rejected arguments. This matters when implementation evidence, a security defect, or changed GitHub behavior invalidates a ruling’s premise. Confidence: sure.

16. “a mechanical forcing function is never traded for trained habit”

    “Never” admits no failure or emergency case. An ordinary counterexample is a broken or unavailable forcing mechanism during recovery, when a documented manual procedure may be the only way to proceed. Taken literally, the rule prevents even temporary fallback regardless of consequences. Confidence: sure.

17. “a detector with no consumer is cost without value”

    “Without value” is an absolute zero-value claim. Detector output can have retrospective forensic or manual audit value even when no automated consumer exists at production time. Confidence: unsure, because “consumer” might be intended to include every possible human or future consumer, in which case the premise excludes that counterexample.

18. “The handoff and supervisor machinery belongs to `fleet`, review methodology to `sanity-checker`.”

    This conflicts with the gatekeeper road’s first assignment: designing the artifact that represents review approval. That task can reasonably be read as review methodology, while the boundary assigns review methodology elsewhere. No distinction separates the semantics owned by `sanity-checker` from the evidence format owned by `gatekeeper`, so either seat can reject the work as out of scope. Confidence: sure.

19. “If your work needs a change there, say so rather than reaching into it”

    “Say so” is not an executable cross-seat procedure. It identifies neither the recipient nor whether the gatekeeper agent stops, records a dependency, requests work from the other seat, or merely mentions it in its next report. A reachable cross-seat dependency can therefore remain indefinitely unowned. Confidence: sure.

20. “The road, in order” conflicts with “ask which step he wants first.”

    If the order is mandatory, only step 1 can be first because step 2 requires its output and activation requires step 2. If the user may choose any step first, the heading and dependency claims are not binding. The question invites a selection that the preceding road says cannot be executed. Confidence: sure.

21. “Design the walked-approval evidence format” and “its shape is his ruling to make.”

    The first assigns design to the seat; the second can mean the user, not the seat, determines the design. “Go-ahead” establishes permission to begin but does not explain whether the agent proposes alternatives, records a user-supplied design, or makes a design that the user later approves. This ambiguity can cause either unauthorized design decisions or an empty request that asks the user to do the assigned work. Confidence: sure.

clean sections: none
