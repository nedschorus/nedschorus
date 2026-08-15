<!-- provenance: runtime=codex model=gpt-5.6-sol effort=xhigh cell=defect-hunt tier=good target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/agents/sanity-checker-instructions.md -->

1. “Your pile: **how this project reviews things, and how well that works.** The sanity-checker reviewer, the md-review grid it may join, and the skill rules that govern how reviews are delivered.”

   The first sentence assigns all project review practice and review effectiveness; the next can be read as narrowing the pile to three named subjects. That ambiguity affects whether this seat owns unrelated code-review, PR-review, or security-review work. The referenced seat model uses the narrower definition. Confidence: unsure — the second sentence may be intended as examples rather than an exhaustive scope.

2. “the split beat the unsplit baseline — gatekeeper 4 of 5 in-band accepted cuts against the baseline's best 3 of 6”

   “In-band” is undefined here and in the scorecard. The scorecard records six accepted gatekeeper rulings but appears to exclude already-applied S7 from one denominator while retaining six in the baseline denominator. Without knowing what the band includes, a future agent cannot interpret the comparison or the conclusion that one result “beat” the other. Confidence: sure.

3. “zero unflagged false positives across eight judgment cells”

   The described experiment has three attacks, two runtimes, and two documents: twelve cells. “Judgment cells” is not defined, so eight could mean the cut and mechanization cells only, all non-fresh-eyes cells, or some other subset. This matters because the quoted false-positive result changes according to which outputs were counted. Confidence: sure.

4. “zero unflagged false positives across eight judgment cells”

   This conflicts with “Never presented, never triaged” for the novel findings. At least the checks-never-wired and pin-stamp findings came from mechanization cells, so some outputs within the apparent eight-cell set have unknown truth status. “Zero” is therefore either unsupported or means only “zero found against the existing ground truth,” a narrower reading the sentence does not state. Confidence: sure.

5. “The already-walked operating rulings — scope, trigger, order, models, piecemeal delivery, triage ownership — are in the header of `docs/drafts/sanity-checker-prompt-draft.md`.”

   The referenced Markdown has no formally delimited header or YAML frontmatter. It has a title, a status paragraph, and a nine-bullet “Grid-seat operating rulings” section before a horizontal rule. “Header” can therefore mean the first paragraph, that whole section, or everything before the rule; the first reading omits the named rulings. The same ambiguity recurs in “Read the scorecard and the prompt draft's header.” Confidence: sure.

6. “**A skill change is walked with the user before it lands**”

   This is an unqualified rule covering every kind of skill change. Ordinary counterexamples include an emergency rollback of harmful instructions and a purely non-behavioral metadata correction; the sentence supplies neither a scope nor an exception path. `CLAUDE.md` also cautions that absolute imperatives such as “always” and “never” can fail in unforeseen conditions, although it does not define a conflicting skill-change rule. Confidence: unsure — the project may deliberately require a user walk even for these cases, but that unusually broad policy is not bounded here.

7. “The experiment surfaced four findings beyond both ground-truth sets.”

   The referenced scorecard lists substantially more than four novel findings: pre-land secret scanning, double-landing after a lost reply, flaky-check policy, receipt-schema versioning, candidate-supplied check execution, permission-state loss, orphaned processes, and several others. The sentence does not say these are four selected findings, so its literal count contradicts its evidence source. Confidence: sure.

8. “Never presented, never triaged”

   “Never presented” is literally false: the findings are presented in the scorecard and again immediately below this phrase. It probably means “never presented to the user in a walk,” but neither recipient nor presentation channel is stated. This can make an agent mistake recorded evidence for undisclosed evidence or repeat a presentation unnecessarily. Confidence: sure.

9. “and each read an *archived* snapshot”

   Grammatically, “each” refers to the four findings, but findings cannot read documents. If it refers to the cells that produced them, those cells are not identified, and the scorecard says the fresh-eyes cells received problem statements rather than the designs. The ambiguity obscures exactly which evidence is stale and must be rechecked. Confidence: sure.

10. “**verify every quoted ground against current code before proposing anything**”

    This cannot be obeyed literally. Some quoted grounds are design promises, user rulings, or operational behavior rather than facts represented in code; the wedged-session claim, for example, concerns observed liveness as well as the absence of a watchdog. “Anything” also has no stated scope and literally blocks unrelated proposals. Confidence: sure.

11. “Findings 1 and 2 are gatekeeper territory and 4 is fleet territory — triage them here, then hand the survivors to those seats rather than implementing them yourself.”

    The routing mechanism omits finding 3. “Those seats” identifies only `gatekeeper` and `fleet`, while the pin-stamp finding actually concerns the fast-handoff writer and therefore cannot be routed from this sentence without reconstructing experiment context. This leaves one reachable survivor without an assigned destination. Confidence: sure.

12. “Its calibration protocol is the live gate before any grid seat.”

    The file earlier says the attack-split experiment was completed and produced the evidence now awaiting the user's decision. The referenced protocol describes the runs that formed the baseline and required a second document. “Live gate” can therefore mean an outstanding run that still blocks the decision or a prerequisite already satisfied but still governing adoption; those readings lead to rerunning versus not rerunning the experiment. Confidence: unsure — “live” may mean still normative rather than still incomplete.

13. “and the per-runtime cells”

    “Per-runtime cells” is not a path, established filename, or defined component name. Searching that phrase does not identify `scripts/md-review-claude-cell.py` and `scripts/md-review-codex-cell.py`; a reader has to infer them by opening the grid script. Because this appears in a list of background artifacts to inspect, the missing identity makes the reading task indeterminate. Confidence: unsure — the grid script does contain the launcher paths once the reader guesses to inspect its implementation.

14. “**Open PRs yours to shepherd:**”

    “Shepherd” does not define the work: it could mean monitor status, answer review comments, update branches, conduct user walks, merge, or merely retain ownership. It also lacks an explicit completion condition beyond the informal implication that the PR eventually closes. This harms handoff because a future agent cannot tell which duties remain or when this obligation is complete. Confidence: unsure — PR closure is a plausible implied stopping point, but the required duties remain undefined.

15. “md-review delivers piecemeal under a Monitor”

    “Monitor” is introduced as a capitalized mechanism but is not identified as a tool, process, agent, or script. The referenced md-review skill repeats the instruction and describes the events it should emit, but does not explain how to create or arm it; the grid script itself only prints progress lines. An agent without a runtime feature already named `Monitor` cannot execute this requirement. Confidence: unsure — a particular Claude runtime may expose a self-describing tool of that name, but the brief does not state that dependency.

16. “coordinate with `fleet` if it needs work”

    Neither condition nor procedure is executable from the supplied context. The brief does not say how to determine that PR #52 “needs work,” how to contact or wake the `fleet` seat, or what artifact records the coordination. The seat model says the user presently coordinates seats and provides no seat-to-seat handoff process, making direct coordination an especially uncertain reading. Confidence: sure.

17. “Session `29d66917` (3.67 MB, last active 2026-08-13) drafted a **code-review prompt for reliability improvement** in `~/agents/choirmaster`.” / “that wheel is already partly built.”

    The referenced transcript’s opening assignment is to create `docs/drafts/sanity-checker-prompt-draft.md`, and the session proceeds through that prompt’s walk and calibration. That prompt reviews MD designs and instructions; it is the already-settled sanity-checker artifact named elsewhere in this brief, not a separate, partly built code-review prompt. The transcript’s generated title uses “code review,” but its actual task and output do not. This false classification sends a future agent toward duplicate work and a 3.67 MB irrelevant prerequisite. Confidence: sure.

18. “No live session, mentioned in no handoff”

    These are mutable present-tense absolutes in a brief explicitly intended for seats resumed weeks later. An ordinary counterexample is that the session is resumed or a later handoff mentions its ID; either event makes the sentence false without changing this file. The nearby “last active” date grammatically qualifies only that parenthetical fact, not these claims. Confidence: sure.

19. “Read it before starting any code-review-prompt work”

    “Any” makes the 3.67 MB transcript mandatory for every code-review-prompt task, including an unrelated prompt in another subsystem. The transcript is about the sanity-checker MD-review prompt, so it does not justify that universal prerequisite. The broad trigger can impose substantial irrelevant reading and contaminate fresh-context work. Confidence: sure.

20. “State the axis.”

    The imperative does not say where, when, or to whom the axis must be stated. It can mean repeat it in every review, include it in the grid-seat walk, enforce its presence in reviewer prompts, or merely use it during triage. Because the axis is already printed in the following sentence, even completion of the command is not observable. Confidence: sure.

21. “a detector with no consumer is cost without value”

    This is an unqualified absolute. An ordinary counterexample is a legally required tamper log whose compliance value exists even when no routine process reads it, or a temporarily deployed detector whose data establishes whether later machinery is warranted. The linked prompt supplies important qualifiers about planned consumers, forcing functions, practical value, and declared blind spots; this shortened rule omits them and can authorize deleting useful evidence. Confidence: unsure — a sufficiently broad definition of “consumer” could include regulators, deterrence, and later analysis, but that definition is not present here.

22. “never trade a deterministic script for probabilistic agent behavior”

    The absolute is broader than the linked reviewer doctrine, which assigns ambiguous interpretation and open-ended judgment to models and reopens the deletion question for broken mechanisms. An ordinary counterexample is a deterministic script that reliably produces obsolete or incorrect output after its environment changes, while an agent can interpret the new case until deterministic behavior is redesigned. Taken literally, this sentence requires retaining the known-wrong script. Confidence: sure.

23. “verify the four novel findings against current code”

    The brief provides no current-code locations for the handoff writer, watchdog/recycle behavior, gate self-edit protection, or gate checks. `CLAUDE.md` happens to identify the gatekeeper program, but neither it nor this brief identifies the fleet implementation needed for findings 3 and 4. A zero-context agent must conduct an unbounded repository search and decide for itself which code constitutes sufficient verification. Confidence: sure.

24. “Read the scorecard and the prompt draft's header, verify the four novel findings against current code, then offer the user the grid-seat walk” / “He has already been asked ‘which first, the walk or the triage?’ and has not answered; ask again plainly and let him choose.”

    The first sentence orders verification before offering the walk. The second says the user must first choose between the walk and triage. The referenced prompt explicitly defines triage as including quote verification and targeted code reads, so the mandated verification is already part of the activity the user has not chosen. An agent cannot both preserve that choice and obey the stated sequence. Confidence: sure.

25. “then offer the user the grid-seat walk”

    The brief names a binary decision but does not identify the walk’s anchor, item list, capture location, or what “offer” means—ask whether to start, or immediately present item one. Those are required elements of the referenced walk-me-through procedure. This becomes harmful if the user chooses the walk: the agent must invent the durable record and scope before it can open it. Confidence: unsure — PR #53 or its scorecard may be intended as the anchor, but the brief never selects either.

clean sections: none
