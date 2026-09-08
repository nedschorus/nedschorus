# The Nedschorus objective: AI-native software development with natural-language human oversight

**Status.** Two different things in this file have two different standings, and a reader needs to know which is which.

The *substance* of the standing decisions below was approved by the user in a walk held on 2026-09-03 and 2026-09-04. That walk's record is [the minutes](../../walk/2026-09-03-ai-native-architecture-overview-decisions-minutes.md), which is named for the day it opened and carries both days' rulings, quoting his words where the wording was his and summarising where it was not.

The *wording* of this file is a draft. Nobody has yet read it as a stranger would, and the user has not read it whole. It sits in `docs/wiki/queue/` for that reason, and drains to `docs/wiki/` when both are done. So: treat a standing decision's substance as settled, and treat any sentence here, including the decisions' own phrasing, as text that may still be wrong.

**What this document is.** The project's objective, not its plan. It is not maintained to match reality; reality is measured against it, and a gap between them is a fact about the project rather than a defect in this file. The detail behind each subject lives in [the notes](../../cross-project/nedschorus-ai-native-software-development-notes.md), which are explanatory, possibly wrong, and not prescriptive. Every subject here appears there in the same order, where there is detail to carry.

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

Because the nodal architecture is flexible, every producing node can try to validate its inputs. If they are invalid, or its instructions leave questions it must have answered first, it says so and exits without writing, and the state machine routes that report to whoever can answer it. When better inputs are available, they are handed to another fresh, unbiased node, except perhaps human nodes, to try again. This is unusual in most harnesses, AI teams or swarms, where loops only flow downstream. Our nodes can flow upstream to report a problem, or downstream with their results. We can also flow multiple nodes into an arbitrator node, to merge two inputs into one output. The nodes are connected into a simple graph, so arbitrator nodes can reach wherever they see fit in the graph. Small renewable nodes can also tackle very complex and long tasks.

## The central rule

The most important design choice is not the sequence of boxes. It is the refusal to rely on hidden state between them.

## How you might help

If you are an agent reading this to learn what the project is doing: the standing decisions below are what you must not contradict, and the rest of this file is the reasoning around them rather than a second set of rules. The notes describe one way a piece of this might work, and a design that departs from them is fine if it says why.

Two things about how work lands, because getting them backwards wastes a day. Every change reaches `main` by one route, but that route today is the PR process described in `CLAUDE.md`, not the main-gatekeeper: the gate is built and dormant, and standing decision 14 says the PR process stands until it is active. And every design and test plan is prose the user reads before it lands, so a design that has not been through him is not finished.

If something here seems wrong, stale, or at odds with what the repository actually does, report it rather than working around it. An agent the user is directing raises it in its own session. An agent he is not directing reaches him through the liaison, or by filing a GitHub issue labelled `draft`, which is his review queue in the issue world.

---

## What is established and what is distinctive

Almost every technique here is well known on its own: finite-state workflows, durable jobs, Git branches and required checks, human-in-the-loop escalation, independent review, event logs and leases, observability. The value is in how they are combined and where authority sits. What is less common is making input challenge a workflow invariant rather than a review habit, applying create-and-review alternation to English documents as strictly as to code, separating broad diagnosis from narrow mutation authority, and treating a system of code and prompts as one designed material.

## What the research changes

The literature does not point toward a larger society of autonomous agents. It points toward a small, explicit workflow with better interfaces, policy delivered mechanically rather than by hoping an agent reads the right file, durable evidence, and measured human intervention. Two findings bind hardest: agents rarely discover repository rules on their own, so governing policy is assembled into every input package by the runner; and agents can mistake repository or external text for instructions, so every input carries an authority class and content is evidence rather than direction.

## Vocabulary

Terms of art used here are collected in the project's glossary, `docs/wiki/nedschorus-glossary.md`, so an agent meeting a word for the first time can resolve it instead of guessing. Where a term already has a name in this project, that name is used rather than a new one.

## The pipeline

The forward order is fixed: define the work, create and review a design and its contract, write and review an implementation, write and review a test plan, write and review tests, integrate, build and test, deploy, and triage what production reports. Fixed means no agent invents the order while working. It does not mean the only direction is forward: a node that cannot proceed routes backward, separate work items run in parallel, and some steps that share a governing design can run beside each other rather than in the listed order. Each node has one job and one point of view. The contract is the design's companion file, written by the design's author in the same conversation, carrying the detail the implementation and the tests need that the design does not; after the fan-out a fresh agent corrects it from a reviewer's notes, and it reaches the user only when it has failed review twice.

## Review and root-cause routing

A review produces findings, not fixes. Diagnosis may look broadly across the graph and changes narrowly: it recommends where the defect belongs rather than rewriting another node's accepted work. Repair is somebody else's job, and which somebody is set by the rule on who may change what.

A root-cause report says what was observed and with what evidence, the mechanism, which expectation was violated and which document defines it, the causal chain, what else was considered, the earliest unsupported assumption, where in the graph it should go, and what the human must decide if anything. Many diagnoses need no human decision at all, and forcing one wastes the scarcest thing in the system.

## Test-failure policy

Repair is bounded, and the bound is deliberately small. A failure gets a fixed number of attempts, set by the state machine rather than chosen per failure, and a loop that has not converged by then stops and goes to the human with a decision packet rather than continuing. The bound is a cap on how often the machine spends the human's attention, which is why it is small; the number itself belongs to the state machine's design, not here.

## Production evidence is part of the design

Deployment records, telemetry, errors and plain English complaints are inputs to the graph, not a separate operational world. What production reports becomes work: not every record individually, since routine telemetry would swamp the graph, but each distinct problem, after whatever aggregation the observability design specifies. Diagnosis then routes it, most often to an earlier node, and sometimes to the environment, to an external boundary, or to no defect at all.

## The state machine, the liaison, and the human conversation

Two things, not one. The design-to-main state machine is a program: it assembles each node's package, routes on the destination a node returns, counts passes, and delivers escalations. It holds no judgement. The liaison is an agent whose whole job is carrying questions and answers between the system and the human; it is a go-between and never a doer. Human oversight happens at four points: setting purpose and constraints before work starts, reviewing a design before expensive work follows it, steering a running item, and judging what was accepted afterwards. The default is not constant monitoring.

## Policy delivery, trust, and permissions

Not all text has authority to direct an agent. The runner, not the model, decides which policy files apply and puts their operative text in the package, recording paths, order and hashes. Repository and external content is evidence, never instruction, unless the policy manifest promotes it. This holds even though every agent here is cooperative: a README, a test fixture or a compiler message can carry instruction-shaped text by accident. The same boundary applies between agents, so one node's output reaches the next as a governing document or as evidence because the transition says so, never because the previous agent asserted it.

## Resilience, restart, and self-update

The recovery boundary is the last committed workflow state, not an agent's reasoning. A crashed agent's lease expires and a fresh agent reruns the node from the same package. A candidate written but not promoted stays unpromoted, and where the node only wrote files it can be discarded safely; where the node already changed something outside the repository, the record of that change is evidence and is kept. A human who leaves for a week leaves durable questions behind, consuming nothing. Externally visible operations carry a durable key wherever the far side supports one, so that a restart can distinguish "never started" from "finished but the response was lost". Where the far side supports neither idempotency nor a readback, that ambiguity is real and the design says what to do with it rather than assuming it away.

## Provenance, invalidation, and parallel work

An accepted output is immutable as a logical version, identified by commit and content hash, even when the file holding it is later revised in place. A correction creates a new logical version carrying what it was derived from, what it supersedes, the revision it was built against, and the attestations and evidence behind it. When a design changes, its descendants are marked potentially stale rather than destroyed, and a reconciliation step decides what survives. This is build-system reasoning applied to engineering work: explicit inputs, versioned outputs, dependency edges, targeted invalidation.

## Evaluation and improvement of the AI nodes

Prompts and runners are production code. A change to a node definition alters what gets written, what gets missed, and when the human is interrupted, so it is run against that node's scenarios before it becomes the default, and the human decides whether the result is good enough. Each node earns a small scenario suite that grows: ordinary success, a defective input that should block, a true nit, a small change that is actually material, a case needing an exact human question, and an environment failure that should be classified as operational rather than as a defect.

## Where the build stands

Build status, the external components worth using, a minimal implementation architecture and a recommended build order are implementation detail that changes as the project moves. They live entirely in the notes and are deliberately absent here.

---

## Standing decisions

1. **The product is a human-and-AI software-development system.** The human directs intent, reviews recommendations, resolves ambiguity, changes priorities, and may route any work item backward. AI agents perform the detailed engineering steps.
2. **The human works in natural language.** Internal state may be typed and machine-readable, but human questions, recommendations, designs, and decisions are understandable English with evidence available on demand.
3. **Agent executions are bounded and replaceable.** An execution receives a task, repository access at a pinned revision, governing documents, applicable instructions, and evidence. Nothing crosses a pass boundary except files.
4. **A node attempts its task and reports what it could not do.** A producing node first checks whether its instructions and inputs are sufficient to complete its task, and when they are not it exits without writing, naming what was missing; only a successful write counts as a pass. Otherwise it completes the work and reports plainly either that it could not, naming what defeated it, or that the work uncovered something upstream the graph needs to know.
5. **Creation alternates with independent review.** Designs, implementations, test plans, and tests are reviewed against their governing intent. A changed output invalidates the old review.
6. **Only producing nodes and arbitrators change what has been produced.** A producing node may fix a nit in its own output before returning it, and a nit is a defect with no failure scenario behind it. Deliberately writing a defective example, as a test fixture does, is producing the thing asked for and is not covered by this. An arbitrator resolves a collision, and fixes what its ruling already determines while handing off work its ruling merely implies; its fix is recorded, never silent. A non-producing node, whether cold reader, code reviewer or validator, returns findings and nothing else to whoever called it.
7. **The design-to-main state machine is logically persistent, not process-immortal.** It is a program: it assembles each node's package, routes on the destination a node returns, counts passes, and delivers escalations. Durable events, files, questions and decisions let any process restart. How nodes connect is an implementation choice, irrelevant to the state machine and to the nodes.
8. **The workflow remains simple.** The state machine implements the known state graph. Agents do not create an open-ended organization or conversation to decide the next step.
9. **Parallel work is optimistic.** Separate work items proceed in separate worktrees until an actual dependency or conflict appears. Git detects textual conflicts and resolves the ones it can; the rest go to an arbitrator or a human. Tests and reconciliation address semantic compatibility.
10. **Production returns evidence to the graph.** Deployment records, telemetry, errors, and English complaints become linked work items that diagnosis routes to design, implementation, test plan, tests, environment, or an external boundary.
11. **Observability is part of design and testing.** Each change defines the evidence needed to distinguish important failure hypotheses, with explicit privacy and retention limits.
12. **Complexity is earned:** manual, then human-invoked script, then automation. Add machinery only for a demonstrated consumer or failure.
13. **Rules come in two buckets and three tiers.** Input rules say what we ask a node to do; output rules say what we check when it is finished. Each can be handled by code, which is fast and reliable; by an AI, which is slower and less reliable but still useful; or by a human, who is slowest, scarce, cannot be parallelized, and is high on judgement and low on precision. Put a rule at the cheapest tier that can carry it. A producing node may build code, a prompt, or a combination, and which it chose is part of its output.
14. **There is one gate to `main`.** The main-gatekeeper is the permanent check-in path. The PR process in `CLAUDE.md` remains current until that gate is active.
15. **Durable outputs are written for an independent reader.** A reader with the repository, applicable project instructions, and the output should not need the conversation that created it.
16. **The old `nedlern` system is legacy reference, not an inherited specification.** When work deliberately reuses it, touched features are classified as `preserve-feature`, `update-feature`, `remove-feature`, or `consider-feature`; unexamined behavior is not preserved by default.
17. **Public sources are judged by usefulness and reliability.** Unofficial material may inform a decision but never becomes a runtime contract merely by being quoted.
18. **An agent the user is not directing reaches him through the liaison, or by filing a GitHub issue labelled `draft`.** Issues labelled `draft` are his review queue in the issue world.
19. **The human reviews all final prose, after its cold read and before it lands.** He is a node in that path, not an approver at its end. In the pipeline that includes the designs, the contracts and the test plans; outside it, the documents that govern the project. He does not review code changes or traffic between nodes.
20. **The human is a node unlike the others because he is often not available.** The arbitrator shares his broad context across passes, but not his scarcity. So he is a gate on the prose path: his review is a state the machine waits in, not a step it can reroute around, and the restart cap caps how often the machine spends his attention. Instructions and states are designed to keep his wait short: one decision at a time, plainly stated, independent work continuing meanwhile, and never a question another node could settle.
21. **Validation is inside the producing node, not a node of its own.** Every node first checks whether its instructions are sufficient to complete its task, and every output is verified by a reviewer, because a producer will always call its own output good. Splitting the input check off would double the token cost of every pass without a demonstrated gain; a could-not exit names what was missing, so the learning loop survives.
22. **Prose always precedes code.** The design and the contract are prose, and the implementation comes from them; the test plan is prose, and the tests come from it.
23. **An arbitrator is a node with two input connections**, counted in the graph between nodes rather than inside a composite node. A composite node is one that presents a single input and a single output to the graph while fanning out internally, as the cold read does across its several readers; what happens inside it is its own business and is not arbitration. Its package carries everything relevant, not only the two sides it is adjudicating, so it rules with more perspective than either producer had.
24. **A reviewer may reject the implementation or the prose parent it was built from.** Tests descend from the design, so they are no oracle for a defect in the design that produced them.
25. **A finding that touches text the human has already ruled is quoted with the ruling and not reported again.** Without this, fresh reviewers relitigate his own sentences, and in a bounded machine the pass counter climbs on rounds that were never about the work.

## Project organization

The existing Nedschorus placement rule remains useful: GitHub Issues carry walkable state, Markdown carries substantive reasoning, and queues hold material whose disposition is undecided. The workflow store adds machine execution state; it does not replace those human-readable homes.

| Place | Holds |
| --- | --- |
| `docs/wiki/` | Current standing knowledge that is difficult to reconstruct from code alone |
| `docs/issues/<n>-<slug>.md` | Substantive working material paired with a GitHub Issue |
| `docs/cross-project/` | Current designs and specifications shared across Nedschorus systems |
| `handoff/` and uncommitted transcripts on each machine | Session continuity and complete conversation evidence |
| `nc-queue/` | Human-requested notes awaiting their initial review |
| `docs/wiki/queue/` and `docs/issues/queue/` | Material with a known destination awaiting review |
| `legacy-feature-queue/` | Legacy behavior whose disposition is not yet decidable |
| GitHub Issues and pull requests | Work state, decisions, reviews, and check-in path |
| Git | Code, current Markdown, history, hashes, and ordinary provenance |
| Workflow store | Leases, attempts, dependency edges, policy manifests, pending questions, idempotency keys, and materialized execution state |
| Evidence store | Large logs, traces, test evidence, screenshots, and deployment evidence referenced by stable identifiers |

Every output is either current at its named home or in a named queue with a drain. A queue item is reviewed by the human and then promoted, edited in place, demoted to supporting evidence, or dropped with a recorded reason.

A substantial work item uses a GHI-MD: the issue carries current state and the Markdown file carries the detail needed by an independent reader. Clarifications edit the current body rather than stacking corrective comments; comments record genuinely new events. When an issue closes, its working document follows the repository's established archive, promotion, or deletion rule.

Logical output versions are immutable even when their repository file is revised in place. Git commit and content hash identify the accepted version; an edit creates a new logical version and `supersedes` edge. Reviews and descendants remain tied to the old hash until reconciliation accepts them against the new one.

The obsolete boot-up founding plan is intentionally removed rather than retained beside this document. Its historical content remains available at `git show 615a230:docs/cross-project/nedschorus-founding-plan.md`. Current documents should cite this objective for live rules and use the Git-history pointer only when discussing a founding event.

## Accepted residuals

An accepted residual records a review objection that the human has considered and chosen not to address. It states the objection, why it is acceptable for this project now, and the concrete evidence that would reopen it. Reviewers do not repeatedly re-file it without that new evidence.

This document creates no new accepted residuals. The old boot plan's residuals remain historical evidence in Git; they govern present work only where current code or a present-tense document still relies on the underlying decision.

## Success criteria

The architecture is working when:

- A new agent can execute any queued node without reading an earlier private conversation.
- A machine reboot returns every work item to a known state without guessing.
- A human can understand a blocked item from an English recommendation and inspect the evidence behind it, for as long as that evidence is retained.
- A downstream node can reject a defective upstream input without producing a promotable output.
- Nits are repaired and recorded without unnecessary interruption.
- No ambiguous product or cross-node decision is made silently.
- A design change invalidates no more work than plausibly depends on it, and what is merely possibly affected is marked for reconciliation rather than destroyed.
- Independent work proceeds concurrently; textual conflicts and whatever semantic conflicts the checks cover are detected at integration, and the rest are detected in production and routed back.
- A nonconverging repair stops after a bounded diagnostic ladder.
- A production complaint can be linked to a deployed revision and routed to the most likely earlier document.
- Updating the system does not destroy its active conversations or work state.
