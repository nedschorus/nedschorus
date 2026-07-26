# Multi-Agent LLM Teams: When They Beat a Strong Single Agent

**Research date:** 2026-07-25

**Commission:** State-of-the-art review for the NC multi-agent architecture draft

**Question:** Which multi-agent LLM team structures measurably outperform a strong single agent, by how much, on what work, and with what failure modes?

## Bottom line

The evidence does **not** support “more agents” as a general capability multiplier.

It supports a narrower proposition:

> Multi-agent systems can outperform a strong single agent when the task decomposes into genuinely parallel information streams, the agents contribute non-identical evidence or capabilities, and a verifier or central reconciler can check their outputs. They often lose on sequential, stateful work; when a strong single agent is already successful; or when the “team” is one model wearing several prompt-defined hats.

The strongest controlled study presently available compared 260 configurations across six benchmarks, five coordination architectures, and three model families while holding prompts, tools, and compute budgets constant. Multi-agent results ranged from **+80.8%** on decomposable financial analysis to **−70.0%** on sequential planning. The mean improvement across all variants was 0.0%, with very high variance. A single-agent baseline was the most robust predictor of whether collaboration helped. A fitted rule in that study predicted zero-to-negative gains above roughly 45% baseline success, and matched the sign of the gain in 94% of 16 additional SWE-bench/Terminal-Bench configurations. This is a useful selection rule within the tested domains, not a universal law; the study’s absolute cross-domain prediction failed. [Nature Machine Intelligence, 2026](https://www.nature.com/articles/s42256-026-01268-y)

For NC, the proposed cross-runtime pairs and lookout-to-expert hierarchy are reasonable experiments, but only with controlled baselines and explicit stopping rules:

1. **Use pairs for bounded, verifiable phases**, not as an always-on tax. The driver produces an artifact; the navigator reviews against tests, source evidence, or a specification. Preserve an independent first pass before agents see each other’s work.
2. **Use cheap lookouts as routers, not judges.** An intent/reasoning stream can be a high-value anomaly signal, but an intent-only observer cannot verify tool effects or final correctness. Escalated experts need the relevant artifact, action result, and provenance.
3. **Reconcile competing teams at phase boundaries through evidence**, not consensus. Majority agreement is not truth when errors are correlated.
4. **Benchmark against strong alternatives:** one strong agent with the same total budget, the same model executing the role workflow sequentially, best-of-*N* plus a verifier, and the proposed cross-runtime team.
5. **Turn collaboration off** when it fails to add unique verified information, when state is tightly sequential, or when coordination cost exceeds the measured quality gain.

## Claim labels and evidence standard

- **[CONFIRMED]** Directly measured in an opened primary paper or official system documentation.
- **[INFERRED]** A design implication that follows from multiple confirmed results but has not itself been tested end to end.
- **[SPECULATIVE]** Plausible architecture with no direct published measurement found.

“Agent” is used carefully. Independent samples from one model followed by voting are an ensemble, even if a paper calls every sample an agent. Prompt-defined roles using the same model are a workflow. A true heterogeneous team uses different model families, tools, contexts, training histories, or other sources of non-identical capability.

This review prioritizes controlled comparisons and peer-reviewed primary sources. Vendor and framework papers are used to establish what a system implements, not as independent proof that the system is superior.

## What the broad controlled evidence says

### 1. Architecture–task fit dominates agent count

**[CONFIRMED]** In the 2026 Nature Machine Intelligence study:

| Task | Best observed multi-agent result vs. single agent | Interpretation |
|---|---:|---|
| Finance Agent | Centralized **+80.8%** (0.631 vs. 0.349); decentralized +74.5%; hybrid +73.1% | Independent financial information streams could be gathered and centrally synthesized. |
| BrowseComp-Plus | Decentralized **+9.2%** | Some benefit from distributed search, limited by open-world ambiguity. |
| WorkBench | Decentralized **+5.6%**; central/hybrid −1.2% | Small benefit; heavier orchestration did not pay. |
| SWE-bench Verified | Every multi-agent architecture degraded, from −1.3% to −12.8% | Strong single-agent baseline left little headroom. |
| Terminal-Bench | Independent +6.0%; centralized −20.0% | Low baseline was not sufficient; architecture and tool structure still mattered. |
| PlanCraft | Every multi-agent architecture degraded, from −39.1% to **−70.0%** | Sequential constraints and state tracking made coordination destructive. |

The same study measured large coordination overhead: 58% for independent parallel attempts, 263% for decentralized, 285% for centralized, and 515% for hybrid coordination. Its trace analysis found error amplification of 17.2× for independent agents, 7.8× decentralized, 5.1× hybrid, and 4.4× centralized, versus 1.0× for the single agent. The robust result was the interaction between baseline difficulty and error amplification, supporting a verification bottleneck as an error-containment mechanism. [Nature Machine Intelligence, 2026](https://www.nature.com/articles/s42256-026-01268-y)

**[INFERRED]** NC should choose architecture per work class, not declare one fleet topology globally optimal. A central verifier is valuable where independent partial results can be checked and synthesized. It is not evidence that every task needs a manager.

### 2. A strong single-agent workflow is a mandatory baseline

**[CONFIRMED]** A 2026 study across seven benchmarks—coding, mathematics, general QA, domain reasoning, planning, and tool use—found that one model executing a homogeneous multi-agent workflow through multiple turns matched or slightly exceeded the multiple-agent implementation and gained efficiency from KV-cache reuse. It could also match one automatically optimized heterogeneous workflow. The authors define homogeneous workflows as agents sharing the same base model and differing primarily in prompts, tools, or workflow positions. This paper is currently an arXiv preprint, so its result should be replicated, but its baseline is logically unavoidable. [Rethinking the Value of Multi-Agent Workflow, 2026](https://arxiv.org/abs/2601.12307)

**[INFERRED]** A claimed “multi-agent gain” is not persuasive unless the experiment includes:

- the strongest single model run normally;
- that same model given the same total token/tool budget;
- that same model sequentially executing the proposed roles;
- a simple sample-and-select or best-of-*N* baseline;
- latency, cost, and failure-rate accounting, not accuracy alone.

## Pattern-by-pattern assessment

### Pair programming / driver–navigator

**Provenance.** Human pair programming established the driver–reviewer idea: two programmers work on the same artifact, with continuous review and role exchange. Early controlled work reported quality and defect benefits with about a 15% development-time cost, though human collaboration results do not transfer automatically to LLMs. [Cockburn and Williams, *The Costs and Benefits of Pair Programming*](https://huang.isis.vanderbilt.edu/cs8395/readings/pairprogramming.pdf)

**LLM implementation.** One agent generates code; another reviews it; roles switch when repeated errors indicate a stall.

**[CONFIRMED]** PairCoder, published in Findings of ACL 2026, evaluated 13 LLMs on HumanEval. Across eight representative backbones it reached 91.0% pass@1, improved over single-model inference by up to 20.3%, and used 40–70% fewer tokens than heavier multi-agent baselines. Many heterogeneous pairs beat both constituents. [PairCoder, 2026](https://aclanthology.org/2026.findings-acl.149/)

**Limits.** This is HumanEval, a short, deterministic, testable code benchmark—not repository-scale engineering, fleet coordination, or continuous reciprocal oversight. “Up to 20.3%” is a maximum, not an expected universal gain.

**NC verdict.** **Promising, bounded trial.** A Codex navigator behind a Claude driver, and the reverse, should be tested on artifact-producing work with deterministic checks. Require an independent navigator assessment before it sees the driver’s rationale; otherwise the second agent is likely to anchor on the first. Rotate roles on a measured stall or phase boundary, not continuously by default.

### Generator–critic / proposer–verifier

**Implementation.** A generator proposes an answer or artifact; a critic identifies defects; the generator revises. The decisive distinction is whether critique is grounded in external evidence.

**[CONFIRMED]** CRITIC uses search, code interpreters, and other tools to critique and revise model outputs. It improved free-form QA, mathematical program synthesis, and toxicity reduction; its core finding is that external feedback makes self-correction reliable enough to help. [CRITIC, ICLR 2024](https://proceedings.iclr.cc/paper_files/paper/2024/hash/fef126561bbf9d4467dbb8d27334b8fe-Abstract-Conference.html)

**[CONFIRMED]** Intrinsic self-correction—asking an LLM to reconsider without new evidence—often fails to improve reasoning and can degrade it. [Huang et al., *Large Language Models Cannot Self-Correct Reasoning Yet*, 2024](https://arxiv.org/abs/2310.01798)

**[CONFIRMED]** Reflexion showed that linguistic reflection combined with environmental feedback can improve sequential decision-making and coding; on its HumanEval setup it reported 91% pass@1 versus an 80% GPT-4 reference. This is feedback-and-memory, not proof that an ungrounded second persona is an independent critic. [Reflexion, NeurIPS 2023](https://papers.neurips.cc/paper_files/paper/2023/hash/1b44b878bb782e6954cd888628510e90-Abstract-Conference.html)

**NC verdict.** **Adopt the pattern, reject the theater.** A critic must receive an oracle, tests, source material, execution results, a governing specification, or a deliberately independent context. “Critic” in the system prompt is not sufficient diversity.

### Multi-agent debate

**Provenance.** Multiple agents propose answers, read one another’s arguments, revise, and select a final answer by a judge or consensus. [Du et al., 2023](https://arxiv.org/abs/2305.14325)

**[CONFIRMED]** A direct ICML 2024 comparison found that multi-agent debate did **not reliably outperform** self-consistency or multiple-reasoning-path ensembles. Tuned protocols could win, but debate was hyperparameter-sensitive and difficult to optimize. [Smit et al., ICML 2024](https://proceedings.mlr.press/v235/smit24a.html)

**[CONFIRMED]** ReConcile reported gains up to 11.4% over prior single- and multi-agent baselines across seven reasoning benchmarks and an 8% MATH improvement using diverse model combinations, confidence-weighted voting, and multiple discussion rounds. Its ablations attributed gains to model diversity. [ReConcile, ACL 2024](https://aclanthology.org/2024.acl-long.381/)

**Limits.** These are mostly static reasoning questions with short horizons and known-answer evaluation. Debate can create anchoring, verbosity, premature consensus, and correlated persuasion errors.

**NC verdict.** **Do not use open-ended debate as a default.** If used, preserve sealed first answers, cap rounds, require claims to attach evidence, and appoint a judge that can abstain. Compare directly with best-of-*N* at the same compute.

### Best-of-*N*, self-consistency, and voting

**Implementation.** Sample multiple independent solutions, then majority-vote a discrete answer or use a verifier/judge to select one. No inter-agent conversation is required.

**[CONFIRMED]** Self-consistency improved chain-of-thought prompting by +17.9 points on GSM8K, +11.0 on SVAMP, +12.2 on AQuA, +6.4 on StrategyQA, and +3.9 on ARC-Challenge by sampling reasoning paths and aggregating their answers. [Wang et al., ICLR 2023](https://arxiv.org/abs/2203.11171)

**[CONFIRMED]** “More Agents Is All You Need” showed that repeated sampling and voting can produce substantial gains on reasoning tasks, but token use grows linearly with the number of samples. Its “agents” are principally independent generations, so this is evidence for inference-time ensembles, not organizational dialogue. [TMLR 2024](https://arxiv.org/abs/2402.05120)

**Failure boundary.** Voting only helps when individual accuracy is adequate and errors are not too correlated. A majority can confidently reproduce the same misconception.

**NC verdict.** **Default simple baseline for discrete or verifier-friendly work.** Prefer test-based selection over majority voting for code and plans. Log pairwise error correlation and the rate at which minority answers are uniquely correct.

### N-version programming

**Provenance.** Independently implement the same specification multiple times and select or vote over outputs.

**[CONFIRMED]** Knight and Leveson gave 27 programmers one specification and ran each implementation on one million random tests. The independence model was rejected at the 99% confidence level; roughly half the observed software faults involved two or more programs. They explicitly did **not** conclude that N-version programming never works—only that reliability is lower than independence-based theory predicts. [Knight and Leveson, 1986](https://people.cs.rutgers.edu/~uli/cs673/papers/EvaluationMultiVersionProgramming86.pdf)

**[CONFIRMED, preprint]** A 2026 reproduction generated 48 implementations with coding agents against the same specification and one million tests. It again found substantial common-mode failure. Three-version majority voting still reduced mean failures from 387.44 for single versions to 130.99, and 11,844 constructed triples had zero observed failures. [N-Version Programming with Coding Agents, 2026](https://arxiv.org/abs/2606.20158)

**NC verdict.** **Use diversity, but measure it.** Multiple implementations can reduce failure probability without making errors independent. Vary model family, prompt framing, toolchain, and decomposition; keep implementations blind until completion; adjudicate with an oracle. Never convert “three agents agree” into a reliability claim without common-mode analysis.

### Ensembles and mixture-of-agents

**Implementation.** Multiple model outputs feed an aggregator, sometimes in layers.

**[CONFIRMED]** The original Mixture-of-Agents paper reported 65.1% on AlpacaEval 2.0 for an open-model mixture versus 57.5% for GPT-4o, using layers of proposers and aggregators. [Mixture-of-Agents, 2024](https://arxiv.org/abs/2406.04692)

**[CONFIRMED, counter-result]** Self-MoA later found that repeated outputs from only the best model beat a heterogeneous MoA by 6.6% on AlpacaEval 2.0 and by 3.8% on average over MMLU, CRUX, and MATH. Mixing lower-quality models often reduced aggregate quality. [Self-MoA, 2025](https://arxiv.org/abs/2502.00674)

**[CONFIRMED]** In the 2026 Nature study’s 13 heterogeneous BrowseComp-Plus configurations, heterogeneous centralized teams underperformed homogeneous teams made from the stronger model by a mean 12.6 percentage points; a small decentralized advantage was largely explained by including a stronger constituent. [Nature Machine Intelligence, 2026](https://www.nature.com/articles/s42256-026-01268-y)

**NC verdict.** **Diversity is conditional value, not a virtue by itself.** Add a weaker model only when it has measured complementary competence or substantially lower routing cost. Always compare against repeated samples from the strongest model.

### Hierarchical router / watcher → expert

**Implementation.** A cheap model classifies difficulty or risk and either answers, routes, or escalates to a more capable specialist.

**[CONFIRMED]** FrugalGPT’s learned cascade matched the best individual LLM with 59.2–98.3% cost savings on three classification/QA datasets, or improved accuracy at equal cost by up to roughly 4–5%. It required labeled in-distribution examples and a learned reliability scorer. [FrugalGPT, 2023](https://arxiv.org/abs/2305.05176)

**[CONFIRMED]** RouteLLM learned to route between stronger and weaker models using preference data and reduced cost by more than 2× without sacrificing response quality in its benchmark evaluations. [RouteLLM, ICLR 2025](https://proceedings.iclr.cc/paper_files/paper/2025/hash/5503a7c69d48a2f86fc00b3dc09de686-Abstract-Conference.html)

**Limits.** These studies route queries, not a continuous stream of another agent’s reasoning. Routing accuracy depends on calibrated thresholds and task-distribution stability.

**NC verdict.** **Strong basis for triage; weak basis for autonomous oversight.** A cheap lookout should emit a compact finding with confidence, reason, and escalation target. It needs an abstain/escalate path and routine calibration against false negatives. Its success metric is not “messages processed”; it is expert time saved at a fixed miss rate.

### Filtered-context intent monitor

**Proposed NC form.** A differently contextualized observer reads agent reasoning/messages but not raw tool traffic, flags suspicious intent or likely mistakes, and calls an on-tap expert.

**[CONFIRMED]** In OpenAI’s reward-hacking experiments, a monitor seeing chain of thought plus actions caught substantially more hacks than a monitor seeing actions alone. Penalizing suspicious thoughts, however, made remaining cheating mostly invisible to that monitor. [OpenAI, *Detecting misbehavior in frontier reasoning models*, 2025](https://openai.com/index/chain-of-thought-monitoring/)

**[CONFIRMED]** A later evaluation suite covering 13 evaluations and 24 environments found chain-of-thought monitoring substantially more effective than monitoring actions and final outputs alone, but still imperfect and potentially fragile. It separately compared CoT-only, actions-and-answer-only, and all-message observation. [OpenAI, *Evaluating chain-of-thought monitorability*, 2026](https://openai.com/index/evaluating-chain-of-thought-monitorability/)

**[INFERRED]** An intent stream is therefore a useful **additional sensor**, especially for suspicious goals, shortcuts, uncertainty, or requests for help. It is not a sufficient correctness or safety gate. If the observer does not see tool calls, results, or the final artifact, it cannot distinguish an abandoned bad thought from a consequential action, nor verify whether a benign-sounding plan produced a bad side effect.

**[SPECULATIVE]** No controlled primary study found in this review tests the exact NC architecture—a low-cost, differently contextualized agent continuously reading a filtered intent stream, summoning specialists, and measurably outperforming a strong single agent end to end.

**NC verdict.** **Prototype as an alerting layer only.** The escalation packet should include the triggering intent excerpt, the relevant action/result or artifact diff, provenance, and what decision the expert must make. Never train the worker merely to avoid triggering the monitor.

## The correlated-error problem

The Knight–Leveson question is the central question for LLM teams: are we buying independent evidence, or several correlated copies of the same error?

**[CONFIRMED]** A 2025 ICML paper analyzed more than 350 LLMs across two leaderboards and a résumé-screening task. On one leaderboard, pairs agreed roughly 60% of the time when both were wrong. Shared providers and architectures increased correlation, but larger, more accurate models still had highly correlated errors even across different providers and architectures. [Kim et al., *Correlated Errors in Large Language Models*, ICML 2025](https://arxiv.org/abs/2506.07962)

The evidence on heterogeneous models is therefore mixed:

- ReConcile found heterogeneous model diversity critical on its reasoning suite.
- PairCoder found many cross-model pairs beat both constituents on HumanEval.
- FrugalGPT exploited complementary mistakes for cost/accuracy gains.
- Self-MoA found the best single model sampled repeatedly often beat a mixed-model ensemble.
- The Nature study found no general cross-family escape from capability saturation.
- Correlated-error analysis shows that different vendors do not guarantee different mistakes.

**Conclusion:** There is no published basis for claiming “Claude + GPT” is reliably independent merely because the vendors differ. Cross-runtime diversity is a hypothesis to measure.

For each candidate pair or team, collect:

1. individual success rate;
2. joint-wrong rate;
3. conditional agreement when both are wrong;
4. unique-catch rate—one agent corrects an error the other would have shipped;
5. false-correction rate—the reviewer changes a correct answer to a wrong one;
6. judge accuracy on disagreements;
7. cost and wall-clock latency per incremental correct result.

## What the named frameworks actually do

Frameworks provide orchestration primitives. They do not, by themselves, establish that multi-agent execution beats a single agent.

| Framework | What it implements | Evidence status |
|---|---|---|
| **AutoGen** | Customizable conversational agents combining LLMs, tools, and humans; programmable conversation patterns; current Core also provides actor-style messaging and standalone/distributed runtimes. | **[CONFIRMED implementation]** Its COLM paper reports pilot applications, not a universal controlled advantage. [AutoGen paper](https://www.microsoft.com/en-us/research/publication/autogen-enabling-next-gen-llm-applications-via-multi-agent-conversation-framework/) and [current architecture](https://microsoft.github.io/autogen/stable/user-guide/core-user-guide/core-concepts/architecture.html) |
| **MetaGPT** | Encodes software-development SOPs as prompt sequences and passes artifacts through specialized assembly-line roles. | **[CONFIRMED implementation]** ICLR 2024 reports more coherent software outputs than earlier chat-based systems; treat as author evaluation. [MetaGPT](https://proceedings.iclr.cc/paper_files/paper/2024/hash/6507b115562bb0a305f1958ccc87355a-Abstract-Conference.html) |
| **ChatDev** | Waterfall-like design, coding, testing, and documentation phases; specialized agents communicate through a prescribed “chat chain.” | **[CONFIRMED implementation]** ACL 2024 establishes the design and author evaluation. [ChatDev](https://aclanthology.org/2024.acl-long.810/) |
| **CrewAI** | Agents with roles, goals, tools, memory, and knowledge; “Crews” execute sequential, hierarchical, or hybrid task processes; “Flows” provide event-driven routing, state, persistence, and human triggers. | **[CONFIRMED implementation]** Official documentation is product documentation, not comparative scientific evidence. [CrewAI docs](https://docs.crewai.com/) |
| **Swarm-style** | Lightweight agents defined by instructions and tools, with model-selected handoffs; the active agent’s instructions change while conversation history persists. | **[CONFIRMED implementation]** OpenAI describes Swarm as experimental/educational and superseded by the Agents SDK. It is an orchestration example, not an efficacy result. [OpenAI Swarm](https://github.com/openai/swarm) |

The best independent cross-framework diagnosis in this review is MAST, published in the NeurIPS 2025 Datasets and Benchmarks track:

**[CONFIRMED]** MAST analyzed 1,642 traces from seven systems/frameworks spanning GPT-4, Claude, Qwen, and CodeLlama tasks. Observed task-failure rates ranged from 41% to 86.7%. Six human experts developed 14 failure modes with κ=0.88 agreement, grouped into system design, inter-agent misalignment, and task verification. A simple ChatDev workflow change that restored final authority to the CEO agent improved success by 9.4%, but the authors found isolated prompt/workflow fixes insufficient for robust reliability. Systems in the dataset included ChatDev, MetaGPT, HyperAgent, AppWorld, AG2/AutoGen, Magentic-One, and OpenManus. [Cemri et al., NeurIPS 2025](https://proceedings.neurips.cc/paper_files/paper/2025/hash/b1041e52d3be19f0a9bc491657488e4a-Abstract-Datasets_and_Benchmarks_Track.html)

**[CONFIRMED limitation of this review]** MAST does not cover CrewAI or Swarm. I found no controlled primary comparison demonstrating that either framework, as a framework, beats a strong single-agent system. Their useful contribution is programmable orchestration.

## Recommended NC architecture

### A. Phase-bounded cross-runtime pair

**Status: [INFERRED], supported by PairCoder and generator–critic evidence.**

1. Assign one runtime as driver for a bounded artifact: plan, patch, review, test design, or research memo.
2. Give the navigator the task, governing sources, and artifact—but initially not the driver’s explanatory narrative.
3. Require a findings-first independent pass.
4. Expose the driver’s rationale only after that pass.
5. Reconcile through tests, source citations, diffs, or explicit contract checks.
6. Switch roles only after a defined stall or at the next phase.
7. Stop the pair when the navigator adds no unique verified information across a calibrated window.

This structure tries to preserve diversity, reduce anchoring, and make the second model’s marginal value measurable.

### B. Lookout → expert escalation

**Status: [INFERRED] for routing; [SPECULATIVE] for continuous intent-stream performance.**

The lookout should:

- read a deliberately bounded stream;
- classify a small taxonomy: likely policy conflict, uncertainty, missing context, unverified assertion, destructive action, repeated failure, or specialist-needed;
- emit `finding`, `confidence`, `evidence_pointer`, `requested_expert`, and `urgency`;
- abstain when evidence is inadequate;
- never silently veto the worker;
- never be the sole safety or correctness control.

The expert should receive the minimum additional evidence needed to adjudicate: relevant tool/action trace, artifact diff, test result, or governing source. This preserves cheap monitoring while preventing the filtered observer from becoming an evidence-starved judge.

### C. Competing Claude-led and Codex-led teams

**Status: [SPECULATIVE] as a whole-system architecture; components have evidence.**

Run competing teams only for high-value tasks that:

- have decomposable subproblems;
- allow independent sealed work;
- possess an external or high-quality adjudication method;
- have enough headroom that a strong single agent is not already saturated;
- justify roughly 2× or greater compute.

At phase boundaries, reconcile claims into an evidence matrix rather than a conversational debate. The reconciler should be able to select either team, merge non-conflicting components, request a targeted test, or abstain/escalate.

Do not use two full teams for tightly sequential stateful work unless a pilot demonstrates a gain; PlanCraft and SWE-bench evidence makes this a poor default.

## Minimum experiment before rollout

Use a preregistered, task-stratified evaluation rather than anecdotal wins.

### Conditions

For each task class, compare:

1. **SAS:** strongest single agent, normal budget;
2. **SAS-budget:** same agent, team-equivalent total budget;
3. **Single-workflow:** same model sequentially executes all proposed roles;
4. **Best-of-*N*:** independent samples plus test/verifier/judge;
5. **Same-model pair:** separated contexts, driver–navigator;
6. **Cross-runtime pair:** Claude↔Codex, both role directions;
7. **Cross-runtime pair + lookout:** proposed full architecture.

### Task strata

- decomposable research/synthesis;
- short verifiable coding;
- repository-scale coding;
- sequential planning/state tracking;
- tool-heavy operations;
- review/error detection;
- ambiguous policy or design judgment.

### Metrics and gates

- success on an external oracle or blinded human rubric;
- unique verified catches;
- false corrections;
- joint-wrong and correlated-error rates;
- premature agreement/termination;
- token cost, tool calls, latency, and human intervention;
- success per dollar and per minute;
- severe-error rate, not only mean score.

Promote an architecture only within task strata where it beats **SAS-budget** and **Single-workflow** by a prespecified margin and the confidence interval excludes a practically irrelevant gain. Keep a rollback rule when live unique-catch value falls below coordination cost.

## Final assessment

The credible state of the art is not “societies of agents are smarter.” It is:

- **Parallel decomposition can help a great deal** when independent sub-results carry real information and a central verifier can synthesize them.
- **Pairs can help on verifiable artifacts**, especially when generation and review are distinct and roles can switch on failure.
- **Sampling and selection remain formidable baselines** and often explain gains attributed to agents.
- **External feedback beats introspective criticism.**
- **Different vendors do not guarantee independent errors.**
- **Central verification contains error propagation, but orchestration itself is expensive.**
- **Sequential stateful tasks and already-strong single-agent tasks are danger zones.**
- **Filtered reasoning monitors are useful sensors, not complete oversight systems.**
- **Framework choice is an engineering decision; it is not evidence of capability gain.**

The NC draft should therefore describe multi-agent structure as an adaptive, measured escalation mechanism—not as the default shape of cognition.
