<!-- provenance: runtime=codex model=gpt-5.6-sol effort=xhigh cell=restate tier=good target=.claude/skills/d-review/SKILL.md -->

## YAML frontmatter

1. The skill’s registered name is `d-review`.
2. Its purpose is to examine an already-written design, specification, or doctrine document skeptically before anyone implements what it describes and before the document is accepted or “lands.” The examples given are a design pair document, architecture specification, skill file, `CLAUDE.md`, or rule change.
3. The document must already have been written. This skill evaluates that document and must not participate in composing it.
4. The skill has two modes. The proposal mode checks design soundness through the listed concerns: unsupported assumptions, confusion between designed and implemented things, instructions falsely described as enforcement, omitted failure cases, needless complexity, uncontrolled growth, risky implementation order, and naming. The doctrine/instruction mode examines individual sentences by having them independently restated and read adversarially and literally across multiple model-capability levels and execution environments.
5. The skill is not intended to determine whether code is correct, nor whether an implementation conforms to its design.
6. Use the skill when people are about to implement a document, when the document is about to be accepted, or when the person called “the boss” explicitly requests a `d-review`. Such an explicit request overrides the normal exclusions just stated.

# Design review (d-review)

1. Review a written document before reliance on it makes defects costly: review a completed design before implementation begins, and review doctrine before readers are required or expected to obey it.
2. The document must already exist and contain enough completed material for a reviewer to make judgments. Review means judging that artifact, not helping write it.
3. A review must not create a replacement design or prescribe a remedy. A finding must instead explain the defect so completely—what is wrong, the circumstances in which it causes harm, and why it causes that harm—that the author can devise and apply a correction without needing further explanation from the reviewer. The parenthetical attributes this rule to a boss decision dated 2026-08-04.
4. The author owns the work of designing the correction. If a reviewer starts proposing an alternative design, that reviewer is no longer performing review and has entered a separately owned design-creation task.
5. A design can appear internally coherent while still depending on an assumption that has not been tested, treating something merely designed as though it already exists, relying on agent obedience for a guarantee essential to the design, or omitting a failure case without acknowledging it. Such defects are less expensive to correct in the document than after implementation.
6. An instruction file that has already been deployed has a different typical failure: an individual sentence may be ambiguous, contradict itself, or be literally false, while a cooperative reader unconsciously substitutes a sensible meaning and therefore usually does not report the defect.
7. The fixed checklists that follow are intended to make review results consistent rather than dependent on a reviewer’s temporary disposition.

## Input and mode choice

1. The input is a repository-relative path to the document. Possible targets include an issue companion or “pair” document under `docs/issues/<n>-<slug>.md`, a specification under `docs/cross-project/`, a skill file, `CLAUDE.md`, or a page containing rules.
2. If the caller has not identified a target document, ask which document should be reviewed.
3. Select the mode according to the kind of document, regardless of the surrounding system’s implementation state. Use the soundness checklist for a design from which nothing has yet been built; use the clarity review for doctrine or instructions; and, if a document is simultaneously doctrine and a description of designed mechanisms, apply both modes as separate passes.

## Steps

1. Steps 1 through 4 and step 6 apply in both modes. Mode 2’s clarity matrix fulfills the function of step 5, so step 5 is not separately performed there.

### Step 1 — Read the whole document

1. Read every part of the document rather than skimming it.
2. Identify its load-bearing claims, meaning claims whose truth is necessary for the design to work as described.
3. Scrutinize those load-bearing claims more aggressively than other material.

### Step 2 — Write out your understanding first

1. Before looking for defects, explicitly describe your understanding of every mechanism, rule, and load-bearing claim. Include subtle details such as boundary conditions, behavior at edges, excluded cases, and effects on nearby state. Be no more specific than the document permits, and record unresolved omissions as omissions instead of guessing how to fill them.
2. If that written understanding differs from the document’s words, treat the difference as a finding after first excluding the possibility that the reviewer simply misunderstood clear language. The remaining readings are either that the document’s wording allowed the misunderstanding or that the reviewer’s correct understanding of reality conflicts with what the document says.
3. The given example is a prior review that accepted the false claim that uncommitted work existed only in a conversation. Explicitly modeling the relevant boundary would have conflicted with that claim because, in this project’s runtime, files written to disk persist across session restarts.
4. Restatement cannot reliably find a defect when both the document and reviewer share the same incorrect belief. Step 4 and the independent reviews exist to address that limitation.
5. This step is preparation performed by the invoking, context-holding agent. In mode 2, delegated restatement cells produce their own paraphrases independently and without being primed by this invoker-side analysis.

### Step 3 — Run the selected checklist

1. Apply the checklist belonging to the selected mode.
2. Every finding must identify a precise location and explain the defect deeply enough for the author to act without further questions: what is wrong, when it causes harm, and why. A finding must not be a nonspecific concern, propose a correction, or contain a severity or importance rating. The stated reason for banning cell-level ratings is that a reviewer without the full context cannot assess importance and that an early rating biases later readers. The parenthetical attributes this rule to a boss decision dated 2026-08-04.
3. An individual review cell may state only whether it is confident in its finding or, if it is not confident, why it is uncertain.
4. Prefer surfacing possibly valid findings over suppressing them because of uncertainty. State the uncertainty and leave the later synthesis process to decide what survives.

### Step 4 — Verify cheap claims and label the rest

1. Perform inexpensive spot checks only on load-bearing claims, and label the remaining load-bearing claims rather than trying to verify everything. The parenthetical says the boss ruled on 2026-08-04 that universal verification would exceed the reviewer’s proper scope.
2. If a load-bearing claim can be resolved through one command or one file read—for example, checking that a cited file exists, that quoted text matches its source, or that a commit is present—perform that check. Claims that something already exists are singled out as especially prone to being falsely believed. The standing example is a supposedly operational backup script whose output directory had never received a commit anywhere in the repository’s history.
3. If verification would be difficult, labor-intensive, or impossible, do not try it. Mark the claim as `unverified`, and use that status when lens 7 classifies the mechanism as measured or merely believed. In this case, producing the label is itself the required output.
4. Comprehensive mechanical verification should be implemented as code, if it is worthwhile at all, rather than consuming a reviewer’s manual effort.

### Step 5 — Obtain independent passes

1. Obtain reviews that are independent of one another.
2. A single reader is biased by the context already occupying that reader’s attention, and authors are especially poor reviewers of their own text because they have already supplied private rationalizations for weak passages.
3. Create fresh subagents to examine the same document on every available runtime. Give each subagent only its assigned task, without passing along the current session’s context.
4. For a doctrine file, the clarity-review matrix defined under mode 2 constitutes this independent-pass step.

### Step 6 — Write the findings

1. Produce the final findings.
2. Only the invoking agent—the agent holding the complete context—assigns severity, and it does so at this stage. `HIGH` means that literal compliance produces incorrect behavior with a meaningful cost; `MED` means capable readers can interpret the text in ways that produce different behavior; and `LOW` means the text creates friction but readers will probably recover successfully.
3. If a potentially high-consequence finding has not been confirmed, label it `HIGH (unconfirmed)` rather than reducing its prominence.
4. Sort findings by severity and use consequence to order findings of equal severity. Explain each one deeply enough that it is ready for the author to correct.
5. Identify sound parts when there are any. If nothing is sound, state that directly.
6. Finish with exactly one status line using one of three forms: `sound`, `sound-with-named-risks`, or `not-ready-because-X`. In the third form, `X` must name the single reason that blocks readiness.

# Mode 1 — the design-soundness checklist

## Running Mode 1

1. Distribute the lenses among agents, assigning one agent per lens or one agent to a related group of lenses; the invoking agent decides the grouping and combines the results.
2. When delegation exists, one reviewer must not apply the entire lens set within one context. If no subagent mechanism exists, a single reviewer may apply the lenses sequentially as an explicitly inferior but accepted fallback.
3. Every re-review must reread the complete document. The stated reason is that design defects can involve any part of the document and that revised text can conflict with untouched text as readily as it can conflict internally. The parenthetical reports that several defects in the first complete-grid review were conflicts between changed and unchanged text.
4. Revision size controls how many reviewers are used, not how much of the document each reviewer reads. A small revision may receive one full-document pass from a good-tier reviewer plus checks that every earlier finding was corrected; a large revision receives the entire review grid.
5. The complete file is the review unit. The text also says that doctrine and design files are intentionally kept small and self-contained in part to keep whole-file review practical.

## Lens 1 — Unvalidated runtime-boundary claims

1. When an essential claim depends on reasoning from first principles about runtime behavior—such as loading time, hook order, or what a session can observe—the claim requires either an empirical experiment or an authoritative specification of that behavior. Reasoning or assumption alone is insufficient.
2. Do not invent an experiment for something that is true by construction: a fact that necessarily follows from the artifact’s definition such that, if it were false, the mechanism would have no point.
3. Require experiments for facts that are genuinely unknown. Whether the consequences are large or small is not what determines the need for an experiment.

## Lens 2 — EXISTS-vs-NEW honesty

1. Flag anything described as already existing when it is only proposed or designed, and also flag the reverse misclassification. The text identifies this as the most significant observed source of design confusion.
2. Check every such existing-versus-new label against actual repository or runtime facts using step 4’s verification rules.

## Lens 3 — How each rule is backed

1. Every essential rule in a design is supported either by an enforcement mechanism, such as a gate, check, or tool boundary, or by a written instruction that agents are expected to obey.
2. Check that the document truthfully identifies which kind of support each rule has. If it claims an enforcement mechanism, that mechanism must really exist, as checked under lens 2; if it is merely an instruction, the document must describe it as an instruction.
3. The defect identified by this lens is an obedience-dependent rule presented as enforced—a false description of what supports the rule.
4. A design is allowed to decide freely which behavior will be implemented in code and which will remain in written instructions. Those choices are ordinary design decisions rather than automatic defects.
5. This review does not reconsider whether a particular prompt rule should instead be code, or vice versa. The text assigns that per-candidate question to NedsChorus issue 42 and attributes the boundary to a boss ruling dated 2026-08-04. The exception is when the document or reviewed section is itself deciding between code and prompts; then that choice is reviewed as an ordinary design decision.

## Lens 4 — Gaps and silently dropped cases

1. For every mechanism, enumerate the relevant state space rather than relying on memory. Examine actor states such as busy, idle, partway through a turn, and dead; dependency failures involving files, tools, and output channels; and concurrency cases such as multiple sessions, re-entry, and repeated activation. Require the document either to address or explicitly reject every combination that is both reachable and consequential.
2. This enumeration is a device for prompting the reviewer. It does not require the design document to reproduce a written account of every enumerated cell.
3. Omitting a reachable and relevant case is a finding even if the normal successful path is perfect. The text says the most valuable defects often occur in states that the design’s own narrative never considers.

## Lens 5 — Over-complexity

1. Look for mechanisms whose benefit does not justify their cost.
2. Two specific warning signs are defined. “Unnecessary tracked state” means maintained state that would become unnecessary if the mechanism did not depend on state; a “compensating mechanism” means extra machinery covering a deficiency that a simpler primitive would remove entirely.
3. The finding must identify the simpler sufficient mechanism, but it must present that mechanism only as evidence that the current design is unnecessarily complex, not as a proposed replacement design.

## Lens 6 — Internal consistency

1. Check whether the document conflicts with itself, with principles it states, or with recorded project rulings. For this lens, those rulings mean the governing planning documents and issue bodies supplied to the lens agent with the reviewed document.
2. Treat an internal inconsistency as strong evidence that the choice was not consciously examined, but determine whether it is an intentional exception before reporting it as a defect.

## Lens 7 — Reliability grounding

1. Classify every load-bearing mechanism as one of three things: measured through an experiment, canary, or field observation; guaranteed by definition or authoritative contract; or merely believed.
2. If a load-bearing mechanism is merely believed, identify that as a risk until it has been measured.

## Lens 8 — Build-order sanity

1. Determine whether the proposed implementation order addresses the largest currently live risk first, where risk is ranked as the probability of failure multiplied by the cost of discovering that failure late.
2. Determine whether the component with the greatest value is scheduled appropriately or placed after work of lower value.

## Lens 9 — Scale and growth

1. If the design accumulates data without an inherent limit, it must state a bound. That bound may take the form of retention, archival, or the project’s lifecycle rule requiring every accumulating store to have a named destination and a process that drains it. The document must also give an approximate expected volume.
2. The text treats unlimited growth overlooked by correctness-focused reasoning as a common default error. Report a missing bound even if the system appears unlikely to reach its practical capacity soon.

## Lens 10 — Test-plan completeness

1. A test plan must cover the cases already represented in the design, but that is insufficient unless it also uses generative methods such as fuzzing or property tests, because a non-generative plan tests only cases the design author anticipated.
2. If the designed mechanism can be executed, require an additional adversarial test layer involving concerns such as load, scale, and unanticipated behavior. That layer must not begin from the assumption that the design is correct.

## Lens 11 — Naming

1. For this lens, a “name” is an identifier that something outside the reviewed document will use to locate or invoke the named thing. The included categories are file and directory names; script, function, command, and skill names; issue and test labels; and formally defined terms that other documents will cite. The parenthetical attributes this scope to the boss on 2026-08-04.
2. Normal prose words, words used only once, and labels defined locally at their point of use—such as a tier system or severity scale—do not count as names for this lens and therefore are not reviewed here.
3. Every name within scope must explain itself and be easy to locate through text search. The stated requirements are complete words that a search can match exactly, one common token shared by names in the same family, no opaque abbreviations, no labels consisting only of an unexplained sequence, and no prose references containing only an issue number without a descriptive handle.
4. Almost every genuinely self-explanatory name should be expected to contain two to five words. A one-word name is presumptively worth reporting when it is generic or conflicts with another meaning in its context, as with `parser`, `data`, or `manager`. Standard domain tokens such as `README`, `checksum`, and `SHA-256` are explicitly acceptable. The calibration is attributed to the boss on 2026-08-03.
5. Prefer a longer, precise name to a shorter, ambiguous one. Convenience of typing must not constrain the name.
6. Because a poor design-stage name will spread into implementation, tests, and instructions, report it while it remains inexpensive to change.

# Mode 2 — the clarity review

1. The relevant failure occurs at sentence level: either a reader must guess to comply with a sentence, or different readers can comply with it in behaviorally different ways.
2. There are two pass types, and different agents must perform them. One agent must never perform both because the first task would bias the second: searching for defects first would make the later restatement unnaturally hostile, while restating first would make the later defect search an after-the-fact justification of the restatement.

## Restatement pass — innocent, zero-charity

1. The cell’s prompt must contain only the paraphrase template and target path. It must contain no framing that says the work is a review or defect hunt.
2. The paraphrase itself is not a finding. A finding is a difference between that paraphrase and the author’s intended meaning.
3. A straightforward paraphrase can reveal ambiguity when the cell naturally interprets the sentence differently from its intended meaning.

## Defect-hunt pass — adversarial-literal

1. Assign this pass to a separate agent and explicitly tell it to find defects. It must flag every sentence that contradicts itself, conflicts with another sentence, permits incompatible interpretations, produces incorrect behavior when followed literally, cannot be executed by a zero-context reader, or requires work an agent cannot reasonably finish. Here, a zero-context reader knows only the checkout’s applicable instruction file—`CLAUDE.md` or `AGENTS.md`—the reviewed document, and files that document explicitly references by path. Examples of unreasonable work include verification or enumeration with no bound, facts about the current world that exceed the model’s training knowledge, control over another agent’s private internal state, and labor lacking a stopping condition.
2. The unreasonable-work category is only a source of possible findings, not an automatic conclusion. Because agents can assess their own capabilities incorrectly, the invoking agent decides which reported cases are actual overreach.
3. A confusion report must never be rejected merely because the reviewer lacked prior project knowledge. The parenthetical attributes this rule to the boss on 2026-08-04.
4. The reviewer is guaranteed only the instruction floor and the reviewed document. Therefore, if a concept is absent from both and confuses the reviewer, triage must select one of three remedies: define the concept in the reviewed file, add an explicit path to its definition, or move the definition into the shared instruction floor when many documents use it.
5. Also flag absolute statements whose scope is broader than reality permits, supplying an ordinary counterexample, and conditional rules whose triggering condition depends on subjective judgment rather than an observable fact.
6. Each flag must quote the relevant sentence, explain its competing readings or conflict, and—when the defect category makes this possible—give an example in which literal obedience produces the wrong result. It must explain what is wrong, when it matters, and why deeply enough for correction, without proposing a correction or assigning severity. The cell may report only its own confidence.

## Running the cells

1. The mapping from each capability tier to a model is a fixed value chosen by the operator. The boss chooses the models, and agents must use those choices rather than replacing them with their own assessment of current models, because the text treats an agent’s model-market knowledge as necessarily several months out of date. The parenthetical attributes this rule to the boss on 2026-08-04.
2. Claude-runtime cells must be new subagents. The `good` tier is the pinned highest model run at high effort; the `floor` tier is the pinned minimum acceptable model, described as Sonnet-class “today.” “Today” is deictic: the sentence does not explicitly say whether it means the file’s date, the current run date, or another operational date. The model and tier must be selected separately for every launch.
3. Codex-runtime cells must be launched through `scripts/d-review-codex-cell.py`, once per cell, with `--cell restate|defect-hunt`, `--tier good|floor`, and `--target <path>`. The script runs a noninteractive `codex exec` in a read-only sandbox and writes the cell’s final response to standard output.
4. Files under `prompts/` are the sole source of cell prompts for both runtime families, so prompt wording for both is maintained in one place.
5. The authoritative tier-to-model and reasoning-effort mappings are stored at the beginning of the script; model identifiers written elsewhere are only snapshots. At the time identified by the text, the mappings are `gpt-5.6-sol` and `gpt-5.6-terra`, both at `xhigh`, selected by the boss and checked live on 2026-08-03. Pinning these values in the script prevents a cell from inheriting the particular machine’s local Codex configuration.

## The matrix

1. The matrix is the Cartesian product of two cell types—restatement and defect hunt—two capability tiers—good and floor—and every available runtime. If two runtimes are available, as the text says they currently are, that produces eight cells.
2. The good tier is especially capable of finding contradictions between separate rules.
3. The floor tier is defined as the lowest-capability tier that can genuinely read the file, not the lowest-capability model that exists. A model below that floor would primarily report deficiencies caused by its own capability. The additional statement that the framework’s subagent default is “the current instance” appears to define the default model source, but the sentence does not fully specify how that default relates to the pinned floor-tier assignment.
4. Run the complete matrix for every review, and require every cell to read the complete document.
5. Any future removal of cells must be based on accumulated evidence showing which cells produce findings that survive informed triage across tens of preserved reviews. Such pruning must be decided through analysis of the stored records, not by adding an unsupported doctrinal rule. The parenthetical attributes this requirement to the boss on 2026-08-04.
6. The clarity cells use the runtimes available at the time of review. Creating a Codex-side wrapper for the entire skill is a separate runtime-parity matter, said to arrive at “companion admission”; that expression is not defined here, so I cannot determine the exact event or artifact it denotes.

## The prompt is the lever

1. A prior review of an older doctrine file reportedly produced seventeen findings with an adversarial, literal-reading prompt but only two with a charitably phrased prompt. The charitable prompt implicitly corrected the defects instead of identifying them.
2. Prompts must compel literal reading, prohibit charitable reinterpretation, and keep the restatement template free from language suggesting a review or defect hunt.
3. The prompt templates are described as the highest-leverage text in the process. Anyone may criticize them during or outside reviews, but modifications must be intentional, decided individually by the context-holding agent, and preferably tested with small focused experiments. They must not change unnoticed. The parenthetical attributes this rule to the boss on 2026-08-04.

## Synthesize — two roles, strictly split

1. Synthesis must use two roles that remain strictly separate. The heading attributes this arrangement to a boss design dated 2026-08-04.
2. First, an independent merge agent with exactly one task and no discretionary judgment combines every cell report into one file. It deduplicates defect-hunt reports only when they flag the same sentence for the same reason, in which case it records every cell that found the issue. Different complaints about the same sentence remain separate but adjacent. The merge agent must neither omit nor filter anything, must preserve expressions of uncertainty exactly as written, and must order entries by their position in the reviewed document rather than by any cell’s rating or opinion. The stated reasons are that report ordering biases the author as the author reads and that document order is neutral while also grouping all complaints about the same passage.
3. Merge the restatement reports into that same file, organized by document section, so each divergence appears next to the passage from which it diverges.
4. Next, the author reads the merged file with full context. Cells contribute observations but never assessments of importance; the author assigns severity only at step 6 and plans a second pass. “Second pass” is not further defined in this sentence. The supplied measurement says that the first full-grid raw results arrived with 47 cell-assigned `HIGH` labels and that those labels, rather than the actual content, initially shaped triage.
5. Preserve a record of every review in a dated directory under `d-review-records/`. The record must include merged findings attributed to their cells, triage decisions, and every complete cell output. Every file must record its runtime, exact model identifier, effort level, cell type, and tier. The reason given is that tier names change between model generations while exact pinned model identifiers do not. The Codex script adds its own provenance stamp; Claude cell files must be stamped when saved. The parenthetical attributes this record requirement to the boss on 2026-08-04.
6. Deduplicate overlapping cell findings and expect substantial duplication. The examples say that a five-cell review of an approximately 120-line skill produced 109 raw reports and about 35 distinct ones, while the first complete matrix produced 191 raw reports and 110 distinct ones.
7. Only the author compares restatements with intended meaning because no other participant is assumed to possess that intent. A comparator lacking the intent could see a paraphrase accurately reflect defective wording and therefore fail to recognize that both differ from what the author meant.
8. The roles must never be combined. Cells produce review findings so that the author does not review the author’s own text; the author receives those findings and rewrites the document, which the text identifies as the purpose of review notes.
9. If the author’s rewrite is defective, the following review round must detect it. The process must not instead constrain the author’s freedom to rewrite.
10. After this synthesis, produce findings according to step 6.

# When NOT to use

1. Do not use this skill to review code correctness or compare an implementation with its design. Those tasks belong to a code-review skill; the text says the “review-change candidate” will own that work once it has been built, though it does not further define that candidate here.
2. Do not use this skill for an ordinary re-review of doctrine that has been deployed for a long time. Use a deliberately planned consistency sweep instead, because this skill is intended to gate proposed changes rather than reassess the accumulated archive.
