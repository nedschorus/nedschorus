# Neural Efficiency

*Only the context each task needs.*

**Neural Efficiency is a design discipline built around focus: organizing humans, agents, and code so each step has a clear responsibility and only the context it needs.** A graph runtime such as LangGraph could run such a system; the discipline determines how to design it.

**Focus is the deliberate organization of work so that each step has a clear responsibility, sufficient relevant context, and an explicit result or escalation path.** Splitting a large task can give each participant simpler instructions, fewer competing objectives, and less unrelated history to process. Choose boundaries by information need, keeping together the facts that must be considered together. A focused design review may still need substantial context; shorter instructions and smaller nodes are useful only when they preserve what the task needs.

**Focus is the design principle; token efficiency is one measure of resource use.** Here, token efficiency means achieving a given quality of result with fewer tokens across the whole task, including review and retries. A focused workflow can use more tokens overall: a separate implementer and reviewer may both read the design, and that duplication can be worthwhile when their distinct responsibilities improve validation or reduce rework. The goal is better use of reasoning, not the shortest prompt or the fewest tokens at any cost.

The name **Neural Efficiency** expresses the intended benefit of focus. Assess that benefit through validated results, rework, human effort, token use, and elapsed time; the name itself does not establish an improvement.

**Neural Efficiency decomposes complex work into independently understandable and verifiable steps.** Each step receives sufficient information, uses the appropriate combination of code, agents, and humans, and returns a defined result. Cold Read tests whether the prose connecting those steps makes sense without hidden background knowledge. Independent validation checks the work. When something fails across a boundary, an arbitrator examines the relevant history, identifies the cause, and assigns a bounded repair.

There are six essential pieces:

1. **Decompose by information need.** Give each step one coherent responsibility and the information it needs. Reduce unrelated context while retaining facts that must be considered together. This also makes dependencies clearer and exposes opportunities for parallel work.

2. **Compose code, agents, and humans inside nodes.** Code handles mechanical operations, agents interpret and synthesize, and humans supply goals and judgment. A node can contain code–prompt–code or an entire smaller workflow involving all three.

3. **Test prose interfaces with Cold Read.** Fresh agents report what they understand instructions, requests, outputs, or templates to mean. Comparing their interpretations with the intended meaning exposes assumptions that the author’s context concealed. This makes context boundaries testable.

4. **Validate entry and exit.** Reject an underspecified request back to its sender. Check completed work against its requirements using code, independent agents, or humans. The precise rule is **self-reported success is insufficient evidence**; the architecture does not require claiming that agents can never recognize their own mistakes.

5. **Use simple outcomes and explicit transitions.** PASS, FAIL, and HELP can carry most routing decisions, with details in the accompanying explanation. A shared exception path keeps ordinary nodes simple.

6. **Expand context for diagnosis, then narrow the repair.** After bounded local attempts, the arbitrator investigates whether the problem lies in the work, its tests, or an upstream design. It identifies and routes the repair. A human joins when arbitration remains unresolved.

A particularly useful distinction is that **the system can retain extensive history while individual workers receive little of it**. Context minimization concerns what a participant must process; arbitration still needs access to the evidence.

The closest comparisons are these:

| Comparison | Why it matters |
| --- | --- |
| **PocketFlow** | A close mechanical match: preparation, execution, post-processing, action-string transitions, and flows nested inside other flows. That substantially overlaps with the code–prompt–code pattern and tags. [Nodes](https://the-pocket.github.io/PocketFlow/core_abstraction/node.html), [flows](https://the-pocket.github.io/PocketFlow/core_abstraction/flow.html). |
| **LangGraph** | Its documentation explicitly discusses different kinds of work, human input, state design, and the context each node needs. The specific Cold Read protocol and diagnostic arbitrator described here are not supplied in the documentation reviewed. [Design guide](https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph). |
| **XState / statecharts** | A relevant comparison for starting with state machines: explicit transitions, events, encapsulated state, and nested actors. Application designers supply the task and prose-interface discipline. [Actor documentation](https://stately.ai/docs/actors). |
| **BPMN / Camunda** | Strong precedent for combining humans, deterministic execution, agents, and subprocesses. Camunda explicitly discusses where deterministic work is preferable and how checking and escalation fit. [Architecture guidance](https://docs.camunda.io/docs/components/agentic-orchestration/ao-design/). |

LangGraph’s additional value includes persistent execution and resuming after human intervention. Whether a workflow needs that machinery is a separate question from whether its decomposition is sound. Small workflows can reasonably use ordinary code and explicit transitions. [Runtime overview](https://docs.langchain.com/oss/python/langgraph/overview).

**On originality, distinguish the ingredients from the operational method.** Modularity, contracts, states, human participation, and independent validation have extensive precedent. Context separation also has direct research antecedents: a 2023 study explicitly answered simpler subquestions in separate contexts. [Question decomposition study](https://arxiv.org/abs/2307.11768).

The strongest candidate for a distinctive contribution is **making prose interfaces systematically testable through a reusable naive-reader protocol, then building minimal-context execution and diagnostic arbitration around that capability**. The important detail is asking readers to report their interpretation under controlled knowledge conditions.

There is a related public description of giving prose to a model without surrounding context, but that article does not provide the reusable skill described here. It establishes overlap in the idea, without establishing equivalence to this implementation or who developed it first. [Cold-read discussion](https://falkster.com/blog/writing-for-machines).

**Neural Efficiency** is the working name, with the subtitle *Only the context each task needs*. The strongest substantiation would be examples showing that Cold Read catches hidden dependencies and reduces failed handoffs or rework—including the cost of performing those checks.

The additional details below explain how to apply the method and where its claims stop.

**A node has an explicit task and a sufficient brief.** Its inputs, expected output, and completion criteria define a bounded unit of work. “Context-free” means independent of undeclared project or conversation history. Every useful node still has its task, declared inputs, common vocabulary, and relevant background knowledge. Independent nodes can run in parallel once their dependencies are satisfied. Excessively small nodes can add handoff costs; useful decomposition minimizes the overall burden of reaching a validated result.

**Code can prepare, perform, and check work.** Mechanical operations include searching, extracting, transforming, computing, assembling inputs, filling templates, checking formats, and routing outcomes. Agents handle language interpretation, synthesis, and problems requiring flexible reasoning. Humans supply goals, judgment, resolution of ambiguity, and decisions requiring human authority. These are allocation principles, not exclusive categories. In a code–prompt–code node, code prepares a focused input, an agent performs a bounded task, and code processes or checks its output. Larger nodes can contain smaller workflows with the same mixed composition.

**Cold Read examines interpretation.** A prose interface is written material that one participant must interpret: instructions, requests, reports, findings, decisions, and handoffs. A cold reader receives the prose, a declared basic vocabulary, and instructions for reporting its interpretation. It lacks the author’s project history. The report describes the task or meaning the reader inferred, along with ambiguities, missing references, and assumptions. Comparing that interpretation with the intended meaning guides revision. This applies to humans as recipients as well as agents, because a human reader’s background context is also uncertain.

Cold Read can operate on concrete prose or on a template whose placeholders are explicitly identified. Code can supply exact dates, filenames, identifiers, and other mechanical values. A template review checks its reusable instructions and structure. An instantiated template can still require checking when inserted content changes its meaning or introduces a new dependency.

**Understandability and correctness require different checks.** At entry, code checks the construction and format of the request where possible. An agent also checks whether the task is sufficiently specified to attempt. Missing information normally goes back to the sender with a specific explanation. During execution, newly discovered blockers can be reported. At exit, a claimed success remains provisional until the appropriate tests or independent review accept the result. Cold Read checks understandability; task validation checks correctness.

A reviewer should receive the result, its requirements, and the evidence needed to evaluate it, without automatically inheriting the producer’s conversation. This gives the reviewer an opportunity to notice assumptions the producer took for granted. A fresh agent can still make mistakes, and several agents can share the same blind spot. Mechanical tests and human judgment remain useful where appropriate.

**Tags select transitions.** The normal vocabulary can remain PASS, FAIL, and HELP. Details travel in the accompanying result or explanation. A timeout, oversized input, or missing requirement need not create a large new vocabulary when it can be represented as a reason for an existing outcome. The workflow’s full state also includes its relevant data and artifacts; the tag is the compact routing signal.

**Arbitration follows dependencies.** Allow a small, bounded number of local correction attempts. If failure persists, the arbitrator follows the relevant dependencies and evidence to identify the responsible scope. It may discover a defect in the implementation, the test implementation, the test design, or the governing design. It may also resolve conflicting contributions, such as a merge. Its primary job is diagnosis and assignment of a bounded repair. The responsible node performs that repair, and validation runs again. If the arbitrator cannot resolve the issue within the allotted one or two passes, a human joins the arbitration.

Passing tests cannot settle a disagreement about whether those tests express the intended design. A diagnostic node can identify where a decomposition has hidden a dependency, allowing the interface or task boundary itself to be repaired.

**The mechanisms reinforce each other.** Clear prose makes task boundaries usable; boundaries make context selection practical; explicit inputs and outputs make validation and parallelism easier; arbitration provides a common path for failures whose cause crosses a boundary. The system can retain extensive history and provenance while exposing only a small part to an ordinary working node.

Two additional research comparisons help distinguish the contributions.

Decomposed Prompting, first published in 2022, uses modular subtasks that can employ prompts, models, or symbolic functions. It is a direct precedent for decomposing model work and giving mechanical subtasks to code. The 2023 question-decomposition study provides evidence for separate-context reasoning on its studied tasks, rather than a universal guarantee that less context always improves accuracy. [Decomposed Prompting](https://arxiv.org/abs/2210.02406), [question decomposition study](https://arxiv.org/abs/2307.11768).

PromptDoctor implements automated analysis and repair of developer prompts for bias, vulnerability, and performance. In that paper, “canonicalization” means normalizing extracted prompt expressions into a common template representation. Filling a prompt with exact runtime values is related programmatic construction, but the terms are not identical. Neither operation alone is the naive interpretation test described here. [PromptDoctor, including §3.1.3](https://arxiv.org/html/2501.12521v1).

The particular Cold Read skill could contribute through the details of its reporting procedure, its repeatability, and its systematic use across instructions, outputs, handoffs, and templates. The related cold-read article was published in July 2026; without the development history of both efforts, it cannot establish priority. The exact integrated method remains a candidate distinctive contribution based on its description, not an established claim of invention.

A useful evaluation would hold tasks and models reasonably constant, compare validated completion and total effort, and include the cost of Cold Read, review, retries, and human assistance. Removing Cold Read while retaining the same decomposition would help identify its particular contribution. Similar comparisons could isolate independent review and arbitration. Results should account for cases where excessive decomposition loses useful information or creates too much coordination overhead.

The name Neural Efficiency expresses the intended benefit of the design philosophy. Claims about measured human neural activity or changes to an LLM’s internal computation would require separate evidence.

This brief describes a design method. Repository instructions and the current NedsChorus architecture determine project operating rules. The comparisons reflect selected public sources reviewed on 6 September 2026; the Cold Read implementation was not inspected for this brief, and the comparison is not an exhaustive priority search.
