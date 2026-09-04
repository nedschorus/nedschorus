# The Nedschorus objective: AI-native software development with natural-language human oversight

**Status.** The rulings below were approved by the user on 2026-09-03 and 2026-09-04, and are recorded verbatim in [the walk minutes](../../walk/2026-09-03-ai-native-architecture-overview-decisions-minutes.md). The TEXT has not yet had its cold read, nor the user's own whole-document review. It sits in `docs/wiki/queue/` until both are done, and then drains to `docs/wiki/`. Treat the standing decisions as ruled and the wording around them as a draft.

**What this document is.** The project's objective, not its plan. It is not maintained to match reality; reality is measured against it. The detail behind each subject lives in [the notes](../../cross-project/nedschorus-ai-native-software-development-notes.md), which are explanatory, possibly wrong, and not prescriptive. Every subject here appears there in the same order, where there is detail to carry.

---

## What the project is

*The user's own description, 2026-09-04, carried with typographical corrections only.*

The system is built around four types of trusted nodes: humans, agents, code, and a combination of code and agents called CPC, for code-prompt-code. These are state machines combining code and prompts. Code gives reliability, testability and execution speed; prompts give flexibility, including the ability to handle unforeseen circumstances, and development speed. As the system matures, proven prompts can be replaced with code.

The agents, and the prompts that drive them, are modular, parallelizable nodes built around a simple graph driven by simple state machines. These nodes are what distinguish an AI-native software development lifecycle from what came before. The human, or trusted humans, are also nodes in this graph.

To make nodes small and modular, the design is based on fully controlled, minimum hidden context. State is fully visible and versionable: in code, and in specific types of Markdown or natural-language files such as the text of pull requests, design files, test design files, a wiki for documentation, GitHub issues, `CLAUDE.md` or `AGENTS.md`, skills, tools both custom and standard, and CPC. This also makes conflicts easy to see and resolve, with a resolving agent node and a resolving human node.

The only context an agent needs is the context for its current task or conversation topic, usually under a thousand words. The goal is to have as little magic context or hidden tokens entering a node as possible, and to make the results of each node explicit in Markdown files. This lets every node be simple, well defined, reasonably testable and highly parallelizable.

The goal is to maximize the content and the reviews in English, and to minimize or even eliminate the need to read code, though not the need for software engineering expertise.

Because we want to minimize context, we do not use standard compaction. It is slow, overly broad, invisible and therefore untunable, and not focused on the current conversation, task or active node. The more we can focus humans and agents, the better, faster and cheaper they operate. Always-fresh focus also minimizes AI governance decay. With the state visible and carefully tracked, it can be easily backed up and restored by restarting the current nodes, and it can be transferred or shared. Nodal modules enable many nodes working in parallel.

Humans, like code and prompts, are powerful. Human oversight is necessary. The goal is not to replace it but to magnify it: to make it easy for a human to reach into any aspect of the system, and to make humans available wherever the system needs human wisdom, judgement or context.

Because each node has a focused context, each node can have a customized and appropriate point of view. This enables high-quality reviews of code, designs and all sorts of node outputs, without the context blurring that produces "I cannot be an impartial observer or actor".

Because the nodal architecture is flexible, every producing node can try to validate its inputs. If they are invalid it can report that to the node that made them. When better inputs are available, they are handed to another fresh, unbiased node, except perhaps human nodes, to try again. This is unusual in most harnesses, AI teams or swarms, where loops only flow downstream. Our nodes can flow upstream to report a problem, or downstream with their results. We can also flow multiple nodes into an arbitrator node, to merge two inputs into one output. The nodes are connected into a simple graph, so arbitrator nodes can reach wherever they see fit in the graph. Small renewable nodes can also tackle very complex and long tasks.

## The central rule

The most important design choice is not the sequence of boxes. It is the refusal to rely on hidden state between them.

## How you might help

If you are an agent reading this to learn what the project is doing: the standing decisions below are what you must not contradict. The notes describe one way a piece of this might work, and a design that departs from them is fine if it says why. Work reaches `main` through one gate, and every design, contract and test plan is prose the user reads before it lands.

If something here seems wrong, stale, or at odds with what the repository actually does, report it rather than working around it. An agent the user is directing raises it in its own session. An agent he is not directing reaches him through the liaison, or by filing a GitHub issue labelled `draft`, which is his review queue in the issue world.

---

## 2. What is established and what is distinctive

Almost every technique here is well known on its own: finite-state workflows, durable jobs, Git branches and required checks, human-in-the-loop escalation, independent review, event logs and leases, observability. The value is in how they are combined and where authority sits. What is less common is making input challenge a workflow invariant rather than a review habit, applying create-and-review alternation to English documents as strictly as to code, separating broad diagnosis from narrow mutation authority, and treating a system of code and prompts as one designed material.

## 3. What the research changes

The literature does not point toward a larger society of autonomous agents. It points toward a small, explicit workflow with better interfaces, policy delivered mechanically rather than by hoping an agent reads the right file, durable evidence, and measured human intervention. Two findings bind hardest: agents rarely discover repository rules on their own, so governing policy is assembled into every input package by the runner; and agents can mistake repository or external text for instructions, so every input carries an authority class and content is evidence rather than direction.

## 4. Vocabulary

Terms of art used here are defined once in the project vocabulary page, so a new agent can resolve a word instead of guessing at it. Where a term already has a name in this project, that name is used rather than a new one.

## 5. The node contract

Every node receives an explicit input package and returns its output, that output's provenance, the evidence behind it, and a recommended transition. Nothing important exists only in an agent's chat message. A producing node returns a candidate output; a non-producing node returns evidence and a route.

## 6. The pipeline

Work moves through a fixed sequence of nodes: define the work, create and review a design, write and review an implementation, write and review a test plan, write and review tests, integrate, build and test, deploy, and triage what production reports. Each node has one job and one point of view. The sequence is fixed so that no agent has to invent it while working.

## 7. Review and root-cause routing

A review produces findings, never fixes. When something fails, diagnosis may look broadly across the graph and must change narrowly: it recommends where the defect belongs and does not silently rewrite another node's accepted work. A root-cause report says what was observed, the mechanism, which expectation was violated and which document defines it, the causal chain, what else was considered, the earliest unsupported assumption, where in the graph it should go, and what exactly the human must decide.

## 8. Test-failure policy

Repair is bounded. A failure gets a small number of attempts, and a loop that has not converged stops and goes to a human with a decision packet rather than continuing. The number of rounds is a cap on how often the machine spends the human's attention, so it is small on purpose.

## 9. Production evidence is part of the design

Deployment records, telemetry, errors and plain English complaints are inputs to the graph, not a separate operational world. Each becomes a linked work item that diagnosis routes to whichever earlier node is most likely at fault.

## 10. The state machine, the liaison, and the human conversation

Two things, not one. The design-to-main state machine is a program: it assembles each node's package, routes on the destination a node returns, counts passes, and delivers escalations. It holds no judgement. The liaison is an agent whose whole job is carrying questions and answers between the system and the human; it is a go-between and never a doer. Human oversight happens at four points: setting purpose and constraints before work starts, reviewing a design before expensive work follows it, steering a running item, and judging what was accepted afterwards. The default is not constant monitoring.

## 11. Policy delivery, trust, and permissions

Not all text has authority to direct an agent. The runner, not the model, decides which policy files apply and puts their operative text in the package, recording paths, order and hashes. Repository and external content is evidence, never instruction, unless the policy manifest promotes it. This holds even though every agent here is cooperative: a README, a test fixture or a compiler message can carry instruction-shaped text by accident. The same boundary applies between agents, so one node's output reaches the next as a governing document or as evidence because the transition says so, never because the previous agent asserted it.

## 12. Resilience, restart, and self-update

The recovery boundary is the last committed workflow state, not an agent's reasoning. A crashed agent's lease expires and a fresh agent reruns the node from the same package. A candidate written but not promoted stays unpromoted and can be discarded safely. A human who leaves for a week leaves durable questions behind, consuming nothing. Every externally visible operation is idempotent or protected by a durable key, so a restart can tell "never started" from "finished but the response was lost".

## 13. Provenance, invalidation, and parallel work

Accepted outputs are immutable; a correction is a new version carrying what it was derived from, what it supersedes, the revision it was built against, and the attestations and evidence behind it. When a design changes, its descendants are marked potentially stale rather than destroyed, and a reconciliation step decides what survives. This is build-system reasoning applied to engineering work: explicit inputs, versioned outputs, dependency edges, targeted invalidation.

## 14. Evaluation and improvement of the AI nodes

Prompts and runners are production code. A change to a node definition alters what gets written, what gets missed, and when the human is interrupted, so it is evaluated before it becomes the default. Each node earns a small scenario suite that grows: ordinary success, a defective input that should block, a true nit, a small change that is actually material, a case needing an exact human question, and an environment failure that should be classified as operational rather than as a defect.

## Where the build stands

Build status, the external components worth using, a minimal implementation architecture and a recommended build order are implementation detail that changes as the project moves. They live entirely in the notes and are deliberately absent here.

---

## 19. Standing decisions

1. **The product is a human-and-AI software-development system.** The human directs intent, reviews recommendations, resolves ambiguity, changes priorities, and may route any work item backward. AI agents perform the detailed engineering steps.
2. **The human works in natural language.** Internal state may be typed and machine-readable, but human questions, recommendations, designs, and decisions are understandable English with evidence available on demand.
3. **Agent executions are bounded and replaceable.** An execution receives a task, repository access at a pinned revision, governing documents, applicable instructions, and evidence. Nothing crosses a pass boundary except files.
4. **A node attempts its task and reports what it could not do.** A producing node is not asked to audit its inputs before starting. It completes the work, and reports plainly either that it could not, naming what defeated it, or that the work uncovered something upstream the graph needs to know. Whether the inputs suffice is the validator's question, asked before this node exists. A node primed to look for upstream faults finds them, tries less hard, and blocks on work it could have finished.
5. **Creation alternates with independent review.** Designs, implementations, test plans, and tests are reviewed against their governing intent. A changed output invalidates the old review.
6. **Only writers and arbitrators change what has been produced.** A writer fixes nits in its own output, and no writer sets out to produce one. An arbitrator resolves a collision, and fixes what its ruling already determines while handing off work its ruling merely implies; its fix is recorded, never silent. A non-producing node, whether cold reader, code reviewer or validator, returns findings and nothing else to whoever called it.
7. **The design-to-main state machine is logically persistent, not process-immortal.** It is a program: it assembles each node's package, routes on the destination a node returns, counts passes, and delivers escalations. Durable events, files, questions and decisions let any process restart. How nodes connect is an implementation choice, irrelevant to the state machine and to the nodes.
8. **The workflow remains simple.** The state machine implements the known state graph. Agents do not create an open-ended organization or conversation to decide the next step.
9. **Parallel work is optimistic.** Separate work items proceed in separate worktrees until an actual dependency or conflict appears. Git resolves textual concurrency; tests and reconciliation resolve semantic compatibility.
10. **Production returns evidence to the graph.** Deployment records, telemetry, errors, and English complaints become linked work items that diagnosis routes to design, implementation, test plan, tests, environment, or an external boundary.
11. **Observability is part of design and testing.** Each change defines the evidence needed to distinguish important failure hypotheses, with explicit privacy and retention limits.
12. **Complexity is earned:** manual, then human-invoked script, then automation. Add machinery only for a demonstrated consumer or failure.
13. **Rules come in two buckets and three tiers.** Input rules say what we ask a node to do; output rules say what we check when it is finished. Each can be handled by code, which is fast and reliable; by an AI, which is slower and less reliable but still useful; or by a human, who is slowest, scarce, cannot be parallelized, and is high on judgement and low on precision. Put a rule at the cheapest tier that can carry it. A producing node may build code, a prompt, or a combination, and which it chose is part of its output.
14. **There is one gate to `main`.** The git-gatekeeper is the permanent check-in path. The interim pull-request lane in `CLAUDE.md` remains current until that gate is active.
15. **Durable outputs are written for an independent reader.** A reader with the repository, applicable project instructions, and the output should not need the conversation that created it.
16. **The old `nedlern` system is legacy reference, not an inherited specification.** When work deliberately reuses it, touched features are classified as `preserve-feature`, `update-feature`, `remove-feature`, or `consider-feature`; unexamined behavior is not preserved by default.
17. **Public sources are judged by usefulness and reliability.** Unofficial material may inform a decision but never becomes a runtime contract merely by being quoted.
18. **An agent the user is not directing reaches him through the liaison, or by filing a GitHub issue labelled `draft`.** Issues labelled `draft` are his review queue in the issue world.
19. **The human reviews all final prose, after its cold read and before it lands.** He is a node in that path, not an approver at its end. In the pipeline that includes the designs, the contracts and the test plans; outside it, the documents that govern the project. He does not review code changes or traffic between nodes.
20. **Because the human is the only participant with memory across passes, he is a gate rather than an ordinary node.** The restart cap therefore caps how often the machine spends his attention. Instructions and states are designed to keep his wait short: one decision at a time, plainly stated, independent work continuing meanwhile, and never a question another node could settle.
21. **Inputs are validated before the consuming node is instantiated.** A validator answers one question about a package: can the next node complete its task using these inputs? It answers yes or no with reasons and produces nothing else. A rejected package therefore costs a validator rather than a burned producer, and the producing node stays fresh when a corrected package arrives. An approval carries exactly the weight of the criteria applied and names them; a rejection blocks on its own. The question stays single; a validator that judges quality has become a second reviewer.
22. **Prose always precedes code.** The design and the contract are prose, and the implementation comes from them; the test plan is prose, and the tests come from it.
23. **An arbitrator is a node with two input connections**, counted in the graph between nodes rather than inside a composite one. Its package carries everything relevant, not only the two sides it is adjudicating, so it rules with more perspective than either producer had.
24. **A reviewer may reject the implementation or the prose parent it was built from.** Tests descend from the design, so they are no oracle for a defect in the design that produced them.
25. **A finding that touches text the human has already ruled is quoted with the ruling and not reported again.** Without this, fresh reviewers relitigate his own sentences, and in a bounded machine the pass counter climbs on rounds that were never about the work.

## 20. Project organization

The existing Nedschorus placement rule remains useful: GitHub Issues carry walkable state, Markdown carries substantive reasoning, and queues hold material whose disposition is undecided. The workflow store adds machine execution state; it does not replace those human-readable homes.

| Place | Holds |
| --- | --- |
| `docs/wiki/` | Current standing knowledge that is difficult to reconstruct from code alone |
| `docs/issues/<n>-<slug>.md` | Substantive working material paired with a GitHub Issue |
| `docs/cross-project/` | Current designs and specifications shared across Nedschorus systems |
| `handoff/` and machine-local transcripts | Session continuity and complete conversation evidence |
| `nc-queue/` | Human-requested notes awaiting their initial review |
| `docs/wiki/queue/` and `docs/issues/queue/` | Material with a known destination awaiting review |
| `legacy-feature-queue/` | Legacy behavior whose disposition is not yet decidable |
| GitHub Issues and pull requests | Work state, decisions, reviews, and check-in path |
| Git | Code, current Markdown, history, hashes, and ordinary provenance |
| Workflow store | Leases, attempts, dependency edges, policy manifests, pending questions, idempotency keys, and materialized execution state |
| Evidence store | Large logs, traces, test evidence, screenshots, and deployment evidence referenced by stable identifiers |

Every output is either current at its named home or in a named queue with a drain. A queue item is reviewed by the human and then promoted, edited in place, demoted to supporting evidence, or dropped with a recorded reason.

A substantial work item uses an MD-GHI pair: the issue carries current state and the Markdown file carries the detail needed by an independent reader. Clarifications edit the current body rather than stacking corrective comments; comments record genuinely new events. When an issue closes, its working document follows the repository's established archive, promotion, or deletion rule.

Logical output versions are immutable even when their repository file is revised in place. Git commit and content hash identify the accepted version; an edit creates a new logical version and `supersedes` edge. Reviews and descendants remain tied to the old hash until reconciliation accepts them against the new one.

The obsolete boot-up founding plan is intentionally removed rather than retained beside this document. Its historical content remains available at `git show 615a230:docs/cross-project/nedschorus-founding-plan.md`. Current documents should cite this objective for live rules and use the Git-history pointer only when discussing a founding event.

## 21. Accepted residuals

An accepted residual records a review objection that the human has considered and chosen not to address. It states the objection, why it is acceptable for this project now, and the concrete evidence that would reopen it. Reviewers do not repeatedly re-file it without that new evidence.

This document creates no new accepted residuals. The old boot plan's residuals remain historical evidence in Git; they govern present work only where current code or a present-tense document still relies on the underlying decision.

## 22. Success criteria

The architecture is working when:

- A new agent can execute any queued node without reading an earlier private conversation.
- A machine reboot returns every work item to a known state without guessing.
- A human can understand every blocked item from a short English recommendation and inspect the evidence on demand.
- A downstream node can reject a defective upstream input without producing a promotable output.
- Nits are repaired and recorded without unnecessary interruption.
- No ambiguous product or cross-node decision is made silently.
- A design change invalidates only the work that actually depends on it.
- Independent work proceeds concurrently and conflicts are detected at integration.
- A nonconverging repair stops after a bounded diagnostic ladder.
- A production complaint can be linked to a deployed revision and routed to the most likely earlier document.
- Updating the system does not destroy its active conversations or work state.
