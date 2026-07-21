---
design-as-of: 2026-07-21
---

# Prior-art cross-check of the nine founding patterns

Production is the source of truth: this page records the two-pass research verdicts as of its date; the built system and open issues may have advanced past it. Both reports are by Codex gpt-5.6-sol (xhigh reasoning, web search, this repository read-only at HEAD 188ee38), admitted verbatim below — including the second pass's references to this file's pre-promotion path, `docs/issues/5-prior-art-cross-check.md`. Origin pair: https://github.com/nedlern/nedschorus/issues/5 (closed at this page's promotion; every borrowing's disposition is a comment there). Deferred mechanisms with raise-triggers: https://github.com/nedlern/nedschorus/issues/6.

# Scope and evidence boundary

I read the four required repository documents:

- [README.md](/Users/el/Projects/nedschorus/README.md)
- [nedschorus-founding-plan.md](/Users/el/Projects/nedschorus/docs/cross-project/nedschorus-founding-plan.md)
- [fast-handoff-design.md](/Users/el/Projects/nedschorus/docs/cross-project/fast-handoff-design.md)
- [fast-pr-to-prod-design.md](/Users/el/Projects/nedschorus/docs/cross-project/fast-pr-to-prod-design.md)

I also read [comms-bridge-spec.md](/Users/el/Projects/nedschorus/docs/cross-project/comms-bridge-spec.md), [entry-manifest.md](/Users/el/Projects/nedschorus/entry-manifest.md), and [boot-pack-manifest.md](/Users/el/Projects/nedschorus/docs/cross-project/boot-pack-manifest.md) where needed to disambiguate P3, P8, and P9.

“READ” below means I inspected the cited repository file or fetched source. “INFERENCE” means my synthesis, especially novelty judgments. Novelty here means “I found no close implementation in reputable published sources,” not patent-level novelty. I made no edits.

Executive verdict:

- P1: known-but-rare; High confidence.
- P2: exact composition appears genuinely novel; Medium confidence.
- P3: known-but-rare and substantially prefigured by Anthropic’s skill-evaluation practice; High confidence.
- P4: established practice; High confidence.
- P5: established practice, although the slogan is too absolute; High confidence.
- P6: established practice; High confidence.
- P7: known-but-rare as a universal lifecycle rule; High confidence.
- P8: exact “quarry plus import ledger” composition appears genuinely novel; Medium confidence.
- P9: known-but-rare; Medium confidence.

## P1. Agent-lifetime taxonomy

### Closest existing art — READ

Claude Code distinguishes its long-lived main conversation from subagents that start with isolated context and are intended for focused tasks. A subagent does not inherit the parent conversation, although it still receives configured project instructions, memory, its system prompt, and task description. Anthropic also distinguishes isolated subagents from independent agent-team sessions. [Claude Code subagents](https://code.claude.com/docs/en/sub-agents), [Claude Code feature overview](https://code.claude.com/docs/en/features-overview).

LangGraph makes persistence a first-class concept: checkpointed thread state supports resumable long-running execution, while stores preserve information across threads. This corresponds to sustained execution, although it models persistent state rather than an identity spanning numbered LLM sessions. [LangGraph threads](https://langchain-ai.github.io/langgraph/cloud/concepts/threads/), [LangGraph overview](https://langchain-ai.github.io/langgraph/index.html).

AutoGen similarly supports saving and restoring agent/team state, giving task executions resumable continuity. [AutoGen state persistence](https://microsoft.github.io/autogen/dev/user-guide/agentchat-user-guide/tutorial/state.html).

The closest explicit taxonomy I found is the AgentSandbox paper: persistent personal agents can delegate bounded tasks to ephemeral agents that receive restricted context and privileges and are discarded after use. It is close to sustained-versus-ephemeral, although the paper’s emphasis is security isolation rather than epistemic testing. [AgentSandbox paper](https://arxiv.org/abs/2505.24019).

### What validates nedschorus

The separation between sustained identity, task-bounded isolated workers, and disposable workers aligns with existing systems’ increasingly explicit separation of persistent thread state from fresh-context workers. It is a coherent architectural taxonomy rather than an arbitrary naming scheme.

Fresh context also has recognized value: subagents reduce context pollution, parallelize independent work, and allow narrow instructions. What appears unusual in nedschorus is treating context absence itself as a deliberate measurement instrument, rather than merely a resource-management or security property.

### What to borrow

- Specify the exact context contract for each lifetime class. “Zero context” must enumerate what still loads: repository instructions, model system prompt, tool schema, git status, environment metadata, task text, and memory. Claude Code’s nominally isolated subagents are not literally blank. [Claude Code subagents](https://code.claude.com/docs/en/sub-agents).
- Separate identity continuity from conversation continuity. A sustained agent should have durable identity/state records independent of any provider’s resumable session identifier.
- Give task-scoped agents explicit termination conditions, scope, privilege, artifact contract, and cleanup semantics.
- Divide kleenex agents into at least:
  - comprehension probes;
  - execution probes;
  - adversarial/negative probes;
  - control agents receiving no candidate document.
- Record model/runtime/version and loaded context with every probe result. Otherwise a later model improvement can be mistaken for a document improvement.

### Verdict

**Known-but-rare — High confidence.**

Persistent versus ephemeral agents is established. A named three-level lifetime taxonomy is uncommon but not surprising. “Empty context as the test instrument” is the potentially original component.

Confidence would rise further with a broader literature search in human-computer interaction, machine-teaching, and agent-memory evaluation, especially under terms such as “cold-start agent evaluation,” “context isolation evaluation,” and “epistemic contamination.”

## P2. Fresh-agent transcript-derived handoffs and permanent denoised archives

### Closest existing art — READ

Anthropic’s long-running-agent harness uses a progress file plus git history so successive fresh-context sessions can reconstruct state. Each session inspects prior work, makes bounded progress, and leaves the repository in a clean condition. [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents).

Anthropic’s later harness architecture is even closer: context resets are paired with structured handoff artifacts, and generator/evaluator roles communicate through files rather than relying on retained conversational context. [Harness design for long-running applications](https://www.anthropic.com/engineering/harness-design-long-running-apps).

Anthropic’s context-engineering guidance recommends compaction and structured note-taking, emphasizing that summarization policy must preserve high-recall facts from complex traces before removing irrelevant material. [Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents).

Claude’s SDK persists complete sessions, including conversation and tool activity, and permits resume/fork operations. That provides trace retention but does not create a compact, independently authored handoff. [Claude Agent SDK sessions](https://code.claude.com/docs/en/agent-sdk/sessions).

SWE-agent stores trajectories containing the query, actions, observations, configuration, and related logs, making executions inspectable and replayable. [SWE-agent trajectories](https://github.com/SWE-agent/SWE-agent/blob/main/docs/usage/trajectories.md).

A recent preprint, Handoff Debt, experimentally compares repository-only takeovers with raw traces and structured handoff artifacts. It reports substantial median reductions in events and token use from handoff context, but the result is model-dependent and the paper is not yet mature evidence. [Handoff Debt](https://arxiv.org/abs/2606.02875).

### What validates nedschorus

The underlying architecture is strongly validated:

- long work must survive context boundaries;
- repository state alone is not sufficient;
- raw traces are too noisy to be the normal startup surface;
- structured handoffs and git history materially reduce reconstruction cost;
- the full trace should remain available for audit and later evaluation.

What I did **not** find is the exact nedschorus procedure: a zero-context third agent reading the transcript, drafting a self-handoff on behalf of the ending agent, followed by a correction-only pass from that ending agent. Existing systems generally have the active session write its own progress notes, generate a summary directly, or rely on automatic compaction.

That difference is technically meaningful: nedschorus uses an independent reader to expose what the transcript actually communicates, then uses the original agent only as a factual residual-corrector.

### What to borrow

- Turn the current dogfood plan into a comparative evaluation:
  - self-authored handoff;
  - fresh-agent transcript-authored handoff;
  - fresh draft plus original-agent correction;
  - raw denoised transcript only;
  - repository-only control.
- Measure pickup success, omitted blockers, false claims, correction count, startup tokens, events-to-first-useful-action, duplicated work, and final task success. Handoff Debt provides a useful experimental shape even if its results remain preliminary. [Handoff Debt](https://arxiv.org/abs/2606.02875).
- Do not restrict archival extraction permanently to a fixed final 1,000-line tail. Use semantic/event boundaries, referenced-file closure, and a reserved token budget; otherwise early decisions in long sessions disappear.
- Store a schema/version beside every handoff and transcript. Denoising rules are part of the provenance and will evolve.
- Treat transcript commit as a security boundary. Run secret scanning, high-entropy/token detection, path/credential redaction, and explicit inclusion policies before history is created. GitHub’s secret-scanning and push-protection model is relevant because committed secrets become repository-history incidents, not ordinary editable text. [GitHub secret scanning and push protection](https://docs.github.com/en/code-security/getting-started/github-security-features).
- Preserve pointers from each handoff to its base commit, terminal commit, source session identifier, transcript digest, model/runtime, denoiser version, and correction diff.
- Consider keeping raw or lightly denoised transcripts in a restricted artifact store while committing only the scrubbed research corpus. Deleting an ordinary repository file does not remove its previous contents from Git history. [GitHub file deletion behavior](https://docs.github.com/en/repositories/working-with-files/managing-files/deleting-files-in-a-repository).

### Verdict

**Genuinely novel as an exact composition — Medium confidence.**

Structured cross-session handoffs, progress files, persistent traces, and independent evaluators are established. I found no reputable implementation of “fresh transcript reader drafts the ending agent’s handoff; ending agent only corrects; numbered handoff plus committed denoised transcript becomes a permanent analytic corpus.”

Searches included combinations of: `fresh agent writes handoff from transcript`, `LLM session handoff independent summarizer`, `agent transcript takeover structured handoff`, `long running coding agent progress file`, and `multi-session agent trajectory archive`.

Confidence would rise with a systematic GitHub code search and scholarly search across agent-memory, conversation summarization, and shift-handoff literature.

## P3. Documents as boot-tested artifacts

### Closest existing art — READ

Anthropic’s official Agent Skills guidance comes very close. It recommends defining evaluations before writing extensive instructions, measuring baseline behavior without the skill, using multiple realistic scenarios, and having one Claude instance author the skill while a fresh Claude instance tests it on real tasks. [Agent Skills best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices).

Anthropic’s enterprise guidance extends this to isolation, coexistence, triggering, output quality, non-trigger cases, ambiguous cases, and separation of duties. [Enterprise Agent Skills](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/enterprise).

Classical usability testing similarly evaluates a complete content artifact by giving representative users realistic tasks rather than asking whether the text appears clear. [Digital.gov usability testing](https://digital.gov/guides/plain-language/test/usability-testing).

### What validates nedschorus

This pattern is directly validated. A document intended to initialize or constrain an agent is executable infrastructure in the operational sense: its quality is the behavior obtained from a representative cold reader, not the author’s subjective judgment.

The nedschorus extension is breadth. Anthropic applies the practice to agent skills; nedschorus proposes applying it to durable project documentation generally.

### What to borrow

- Treat each important document as a versioned evaluation target with:
  - required-context declaration;
  - positive tasks;
  - negative/non-trigger tasks;
  - ambiguous tasks;
  - required facts and prohibited assumptions;
  - scoring rubric;
  - model/runtime matrix.
- Measure a no-document baseline. Otherwise the test cannot distinguish information supplied by the document from model prior knowledge.
- Use several fresh readers, not one. One pass has high variance.
- Test both comprehension and action. A reader can recite a design correctly but still execute it incorrectly.
- Preserve failed answers as regression fixtures.
- Test documents in coexistence. Individually clear files can conflict once README, project instructions, handoff, and task document are all loaded.
- Normalize “zero-context” precisely. For the current design, “only project instructions plus the document” is a controlled-context test, not literal zero context.

### Verdict

**Known-but-rare — High confidence.**

The core mechanism is already explicit in Anthropic’s maintained guidance. Applying it systematically to all durable operating documents is distinctive, but “fresh agent validates an agent-readable artifact” is not novel.

Confidence would rise through evidence of broad adoption outside skill authoring, but the classification is unlikely to change.

## P4. The single-writer throat

### Closest existing art — READ

Git’s integration-manager workflow has contributors work in separate clones or forks while one maintainer integrates, tests, and pushes to the canonical repository. Dictator-and-lieutenants is the larger-scale variant. [Git integration-manager workflow](https://git-scm.com/book/en/v2/Distributed-Git-Distributed-Workflows.html).

Protected branches can restrict who may push, require reviews and status checks, require signed commits, use merge queues, and prohibit bypasses. [GitHub protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).

GitHub’s merge queue tests a candidate in relation to the current target branch and preceding queued changes, addressing the stale-base race that ordinary branch CI misses. [GitHub merge queues](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/merging-a-pull-request-with-a-merge-queue).

Rust’s bors workflow historically prohibited manual merges and tested the exact merge candidate before allowing it onto the main branch. Bors is commonly configured as the only direct writer. [Rust CI and bors](https://rust.googlesource.com/rust-lang/rustc-dev-guide/+/a888bf34dbd7510a10f8180a39671d7e5e84bda4/src/tests/ci.md), [bors documentation](https://bors.tech/documentation/getting-started/).

SLSA source requirements formalize protected branches, technical enforcement of required checks, provenance, and—for its highest source level—two-party review. [SLSA source requirements](https://slsa.dev/spec/v1.2/source-requirements).

### What validates nedschorus

The high-level topology is thoroughly established:

- non-authoritative producers work independently;
- one controlled integration path updates main;
- validation runs against the candidate that will actually land;
- provenance accompanies promotion;
- remote authorization protects the canonical branch.

The “single writer” is therefore not pioneering. It is a deliberately small implementation of integration-manager, gated-submit, and merge-queue patterns.

### What existing systems do better

The current design makes one identity the only authorized pusher, but `throat.py land` is a local cooperative convention. If that credential can also run raw `git push`, the remote proves **who** pushed, not that the throat’s provenance, import, hygiene, and review checks ran. The design itself acknowledges this residual.

The stronger form is:

1. Agents and the choirmaster produce a proposal commit or temporary ref.
2. An unprivileged local command submits that exact object ID.
3. A GitHub App or CI identity—the sole main writer—checks the proposal against current main.
4. It records a signed/attested result.
5. It updates main by compare-and-swap only if the tested base still matches.
6. The human identity cannot bypass that path under ordinary operation.

This preserves the desired no-PR fast path if PR ceremony is unwanted; PRs and GitHub’s merge queue are implementation options, not architectural requirements.

Additional borrowings:

- Put base SHA, proposal SHA, source clone, agent/runtime, task/issue ID, imported paths, review evidence, and validation result in machine-readable provenance. Git trailers can provide a human-readable projection. [Git interpret-trailers](https://git-scm.com/docs/git-interpret-trailers).
- Validate the exact tree that lands, not merely the working tree before a final commit.
- Use separate credentials for proposal submission and canonical update.
- Add replay protection so one promotion request cannot be landed twice.
- Require a clean comparison between declared and actual changed paths.
- Preserve a server-side audit log even if the user-facing workflow is local.
- If “all mechanical checks from day one” is intended literally, remove the raw-push bypass before making that claim.

### Verdict

**Established practice — High confidence.**

The precise user experience—one human choirmaster, no mandatory PR, local scripted promotion—is customized. The security and integration architecture is conventional.

## P5. Prompts/code split and Python-first scripting

### Closest existing art — READ

OpenAI’s Agents SDK explicitly distinguishes LLM-driven orchestration from orchestration in ordinary code. Code orchestration is recommended where deterministic order, branching, loops, parallelism, speed, cost, and predictability matter. [OpenAI Agents SDK orchestration](https://openai.github.io/openai-agents-python/multi_agent/).

Anthropic similarly distinguishes predefined workflows from dynamic agents: workflows suit well-defined, predictable execution, while agents are appropriate where the solution path cannot be predetermined. [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents).

Anthropic’s Agent Skills guidance recommends matching freedom to risk: fragile and consistency-sensitive operations should use low-freedom scripts, while prose should govern decisions requiring judgment. Reusable scripts also reduce repeated token expenditure. [Agent Skills best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices).

Google’s shell style guide recommends shell for small or simple wrappers and a structured language when logic becomes nontrivial. [Google Shell Style Guide](https://google.github.io/styleguide/shellguide.html).

### What validates nedschorus

The operational choice is well founded:

- deterministic mechanics belong in testable code;
- model judgment should select among explicit operations rather than reimplementing mechanics in prose;
- a single structured scripting language reduces quoting, portability, error-handling, and state-management failures;
- Python provides better schemas, libraries, tests, and exception handling than an expanding shell layer.

### Where I disagree

“English is not a programming language” is useful rhetoric but technically overstates the boundary. Prompts, instructions, and document ordering are behavior-bearing configuration. They can alter execution just as decisively as Python. Moving deterministic behavior into Python does not make prose non-executable; it means prose should be restricted to policy, semantic judgment, intent, and invocation selection.

Consequently, prompts still require version control, evals, compatibility testing, and ownership. Anthropic’s skill guidance is effectively a testing discipline for prose-driven behavior. [Agent Skills best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices).

### What to borrow

- Define a mechanical/judgment decision table:
  - parsing, validation, state transitions, retries, path selection, formatting, git operations → Python;
  - prioritization, semantic review, ambiguity resolution, synthesis → model;
  - model outputs crossing into code → schema-validated typed data.
- Make every state-changing script idempotent or explicitly single-use.
- Provide dry-run and explain modes.
- Use stable exit codes and machine-readable results.
- Keep shell only for transparent process composition where Python would add no safety.
- Test prompt/code interfaces as contracts, including malformed, incomplete, and adversarial model output.
- Pin dependencies and Python runtime expectations from the first nontrivial script.

### Verdict

**Established practice — High confidence.**

The policy is a disciplined application of workflow-versus-agent separation and standard shell-language guidance. Python-first is a sound project convention, not a novel architecture.

## P6. The earned-automation ladder

### Closest existing art — READ

Google SRE describes an automation evolution from no automation, through local task-specific scripts and generalized external automation, to integrated and autonomous systems. It also warns that infrequent automation can decay and that automation must be applied judiciously. [Automation at Google](https://sre.google/sre-book/automation-at-google/).

Google’s newer AI-operations guidance defines levels from manual through assisted and human-approved operation to bounded and full autonomy. Advancement depends on evidence, confidence, safe pathways, and reliability; it recommends dry runs, circuit breakers, zero-trust control planes, dynamic demotion when risk rises, and emergency stop mechanisms. [AI engineering for reliable operations](https://sre.google/resources/practices-and-processes/ai-engineering-reliable-operations/).

HashiCorp likewise presents a maturity progression from manual and semi-automated processes through fully automated, self-service, and continuous operation. [HashiCorp process automation maturity](https://developer.hashicorp.com/well-architected-framework/define-and-automate-processes).

### What validates nedschorus

This is established reliability engineering. Requiring a human to admit each rung based on observed evidence is an appropriate governance rule for a self-modifying development system.

The strongest part is not the three rungs themselves; it is refusing to interpret “we wrote a script” as authorization for unattended execution.

### What to borrow

Define admission and demotion criteria per capability:

- successful manual executions;
- successful dry runs or shadow executions;
- false-action and missed-action rates;
- frequency of human corrections;
- rollback coverage;
- bounded blast radius;
- deterministic preconditions;
- observability and audit completeness;
- time saved net of supervision;
- maximum unattended duration.

Every automated capability should also declare:

- current automation level;
- responsible human;
- allowed scope;
- kill switch;
- rollback path;
- evidence window;
- expiration/revalidation date;
- conditions that automatically demote it.

The ladder should be reversible. Changed environment, elevated risk, or anomalous behavior should move automation downward without treating that as failure.

### Verdict

**Established practice — High confidence.**

Nedschorus’s formulation is compact and sensible, but its substance is standard SRE and progressive-automation governance.

## P7. MD–GHI lifecycle pairs and `boss-review`

### Closest existing art — READ

Kubernetes Enhancement Proposals are durable Markdown design records associated with tracking issues. KEP filenames carry the issue number, while the issue acts as a current-state breadcrumb and coordination surface. KEPs also have structured metadata, reviewers, lifecycle stages, and presubmit validation. [Kubernetes KEP process](https://github.com/kubernetes/enhancements/blob/master/keps/README.md).

Rust RFCs are proposed as Markdown pull requests, gain stable identifiers through repository workflow, and—when accepted—normally obtain a separate tracking issue for implementation. This deliberately distinguishes decision acceptance from implementation completion. [Rust RFC process](https://rust-lang.github.io/rfcs/).

GitHub labels and issue filters are standard mechanisms for turning a label such as `boss-review` into a maintained work queue; GitHub documents label automation as part of issue triage. [GitHub issue labeling automation](https://docs.github.com/en/actions/tutorials/manage-your-work/add-labels-to-issues).

### What validates nedschorus

Pairing durable design material with a live issue is proven practice:

- Markdown carries structured, reviewable substance;
- the issue carries ownership, discussion, current status, and scheduling;
- a stable numeric identity joins the two;
- ordinary repository and hosting tools remain sufficient.

Using a label as the human review queue is preferable to inventing another queue format because it remains searchable, assignable, timestamped, and automatable.

### What to borrow

- Prefix or front-matter every paired document with the issue ID, state, owners, created date, and canonical issue URL.
- Add CI that rejects missing or inconsistent pair links.
- Distinguish document lifecycle from implementation lifecycle where necessary. Rust’s separate implementation issue avoids forcing one owner or closure event to represent two different lifetimes. [Rust RFC process](https://rust-lang.github.io/rfcs/).
- Preserve accepted durable decisions as ADRs/specifications after their working issue closes. Do not delete accepted rationale merely because active work ended.
- For rejected or abandoned documents, retain a tombstone or final disposition pointer; Git history is technically recoverable but operationally undiscoverable.
- Apply the mandatory pair only above a durability threshold. Pairing every incidental Markdown note risks issue inflation and makes the queue less informative.
- Measure `boss-review` age and oldest-item latency, not only queue size.
- Require an explicit disposition on issue closure: `promoted`, `superseded`, `rejected`, or `deleted`.

### Verdict

**Known-but-rare — High confidence.**

Document/issue pairing and label-based review queues are established. The unusual aspect is imposing a one-to-one lifecycle pair on every durable working document and disposing or promoting it at closure.

## P8. Frozen predecessor as quarry with an entry manifest

### Closest existing art — READ

The Strangler Fig pattern incrementally replaces legacy capabilities while allowing old and new systems to coexist during transition. [Martin Fowler’s Strangler Fig](https://martinfowler.com/bliki/StranglerFigApplication.html), [AWS strangler guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/modernization-aspnet-web-services/fig-pattern.html).

Branch by Abstraction and Parallel Change create seams that allow old and new implementations to coexist, be compared, and be replaced incrementally. [Branch by Abstraction](https://martinfowler.com/bliki/BranchByAbstraction.html), [Parallel Change](https://martinfowler.com/bliki/ParallelChange.html).

Google’s Copybara moves and transforms code between repositories while preserving an authoritative source, recording source revisions, and supporting repeatable migrations through versioned configuration. [Google Copybara](https://github.com/google/copybara).

SLSA provenance describes machine-readable identification of source and build inputs. [SLSA provenance](https://slsa.dev/spec/v1.2/provenance).

SPDX package metadata includes version, supplier/origin, source location, checksums, licensing, and external references—the supply-chain analogue of a richer import manifest. [SPDX package information](https://spdx.github.io/spdx-spec/v2.3/package-information/).

### What validates nedschorus

Gradual displacement and source provenance are established. Freezing the predecessor prevents the successor effort from becoming an endless dual-maintenance migration, while per-component admission controls accidental wholesale inheritance.

However, nedschorus is not a conventional Strangler Fig unless old and new implementations remain live behind routing seams. It is closer to a greenfield successor with selective, provenance-recorded vendoring from a frozen corpus.

### What existing art does better

The current `entry-manifest.md` records source commit, imported artifact, purpose, and date. That establishes origin but not reproducibility or completeness. Add:

- stable import ID;
- quarry repository URL and exact commit;
- source path and content digest;
- destination paths and digests;
- importing issue and authoring agent;
- transformation recipe;
- semantic changes from source;
- dependency-closure analysis;
- license and attribution status;
- validation/characterization tests;
- supersedes/reimport relationship;
- reason to copy rather than redesign;
- whether future quarry changes are intentionally ignored.

A Python import command should copy or transform the artifact, compute digests, update the manifest, and reject undeclared quarry-origin paths in one transaction. That is stronger than asking an agent to remember the manifest.

For behavioral components, capture characterization tests before import and differential-test quarry versus successor behavior where feasible. Branch by Abstraction provides the conceptual basis even without production-time dual routing. [Branch by Abstraction](https://martinfowler.com/bliki/BranchByAbstraction.html).

Copybara is likely excessive initially, but its central lesson is valuable: migration provenance should be generated by the transfer mechanism, not reconstructed manually afterward. [Google Copybara](https://github.com/google/copybara).

### Verdict

**Genuinely novel as an exact composition — Medium confidence.**

Selective migration, frozen legacies, provenance ledgers, vendoring, strangler migrations, and code-copy tooling all exist. I found no reputable named pattern matching “freeze predecessor read-only; treat it explicitly as a quarry; import one component at a time through a same-commit entry checkpoint; require each imported component to earn admission into a deliberately minimal successor.”

Searches included: `frozen read-only legacy repository successor import manifest`, `software quarry migration pattern`, `selective code import provenance manifest`, `strangler code repository frozen predecessor`, `Copybara migration source revision`, and `legacy code extraction ledger`.

Confidence would rise with broader searches of monorepo extraction tooling, safety-critical software reuse records, and open-source rewrite projects’ migration documentation.

## P9. Cross-runtime pairing through two append-only logs

### Closest existing art — READ

Anthropic’s multi-agent research system has a lead agent delegate independent parallel research trajectories and synthesize the results. Anthropic reports benefits from parallel search, but also substantially higher token consumption and weaker applicability where tasks are tightly coupled; it specifically notes that coding is often less naturally parallelizable than breadth-first research. [Anthropic multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system).

AutoGen team patterns coordinate multiple agents through shared conversational context and manager/selection policies. [AutoGen teams](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/teams.html).

Aider’s architect/editor mode deliberately combines two model roles: one reasons about the change and another performs editing. It is sequential rather than two independent same-task clones, but it validates heterogeneous role composition. [Aider architect mode](https://aider.chat/docs/usage/modes.html).

Mixture-of-Agents uses outputs from multiple heterogeneous models as inputs to an aggregator. [Mixture-of-Agents paper](https://arxiv.org/abs/2406.04692), [reference implementation](https://github.com/togethercomputer/moa).

LLM-Blender similarly ranks and fuses outputs from multiple models rather than trusting one model or simple voting. [LLM-Blender, ACL 2023](https://aclanthology.org/2023.acl-long.792/).

A very recent unreviewed preprint, ESAA-Conversational, describes heterogeneous coding agents coordinating through append-only local artifacts rather than direct agent messaging. Its evidence is a single self-referential case study, so it is prior-art evidence but weak validation. [ESAA-Conversational](https://arxiv.org/abs/2606.23752).

The append-only coordination substrate itself resembles event sourcing: durable events form the authoritative record and consumers derive state by replaying them. [Martin Fowler on Event Sourcing](https://www.martinfowler.com/eaaDev/EventSourcing.html).

### Local-spec discrepancy — READ

The current [comms-bridge-spec.md](/Users/el/Projects/nedschorus/docs/cross-project/comms-bridge-spec.md) describes an old/new-project bridge and the founding plan explicitly calls that specification stale and requiring re-derivation. It therefore does not yet constitute a settled Claude/Codex protocol.

There is also a topology issue to resolve: if Claude and Codex operate in separate clones and each clone contains a gitignored `bridge/` directory, they do not share the same files. The design needs one explicitly shared filesystem location or a synchronization transport. A file protocol is sufficient; a message broker is not required.

### What validates nedschorus

Independent heterogeneous generation followed by synthesis is supported by multi-agent and ensemble work. Separate clones provide isolation and make provenance comprehensible. A single writer eliminates merge authority ambiguity.

Two single-writer append-only logs are also a rational minimal protocol: each producer owns one file, so most write contention disappears, and the exchange remains inspectable by the human.

### What to borrow

- Preserve independence before synthesis:
  1. Claude and Codex make blind first passes.
  2. Each inspects the other’s artifact.
  3. Each records critique/disagreement.
  4. The choirmaster synthesizes and records why alternatives were accepted or rejected.
  
  Immediate chatter risks correlated convergence and destroys much of the ensemble benefit.

- Give each log record a minimal machine-readable envelope:
  - protocol version;
  - message ID;
  - task/issue ID;
  - UTC timestamp;
  - author/runtime/model;
  - message type;
  - base SHA;
  - artifact path and digest;
  - `reply_to`;
  - acknowledgement/cursor state.
- Use one atomic append per record under a lock and flush it before announcing availability. Plain multi-write Markdown appends can expose partial records.
- Maintain per-consumer cursors so “read” has precise semantics.
- Add compaction/checkpoint records; indefinitely replaying both logs will eventually reproduce the context problem the system is intended to solve.
- State the durability boundary accurately. A gitignored local log survives a process death, but not necessarily disk loss, clone deletion, or machine replacement.
- Keep durable decisions outside the chatter logs, linked back by message IDs.
- Require base SHA and artifact digest in every promotion request.
- Evaluate cross-runtime pairing by task class. Use it where model disagreement or independent search improves outcomes; avoid paying twice for tightly coupled mechanical work. Anthropic’s multi-agent results make this selectivity important. [Anthropic multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system).
- Compare synthesis methods—human selection, model selection, rubric scoring, tests, and fusion—rather than assuming “best of both” happens automatically. LLM-Blender demonstrates that explicit ranking and fusion are substantive components, not clerical steps. [LLM-Blender](https://aclanthology.org/2023.acl-long.792/).

### Verdict

**Known-but-rare — Medium confidence.**

Heterogeneous model ensembles, parallel agents, manager synthesis, separate working directories, append-only coordination, and a single integrator all exist. I found no mature maintained system with the exact nedschorus combination of Claude and Codex doing blind same-task work in separate clones, communicating through two directional append-only files, and landing only through one human-controlled writer.

The recent ESAA preprint makes “heterogeneous coding agents coordinated by append-only local state” unsafe to call wholly novel. Nedschorus’s exact composition and operational discipline may still be original.

Confidence would rise with searches across emerging local-agent orchestration repositories and empirical comparison against shared-chat, shared-blackboard, and no-communication baselines.

# Ranked shortlist: five highest-value borrowings

1. **Move the single-writer throat from cooperative local convention to technical remote enforcement.** Use a bot/App as the only main writer, validate an exact proposal SHA against current main, and update by compare-and-swap; this closes the largest gap between the stated invariant and the actual security boundary. Sources: [GitHub protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches), [GitHub merge queues](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/merging-a-pull-request-with-a-merge-queue), [SLSA source requirements](https://slsa.dev/spec/v1.2/source-requirements).

2. **Run a controlled handoff-method experiment before cementing the transcript protocol.** Compare self-summary, fresh transcript draft, fresh draft plus correction, raw transcript, and repository-only takeover using objective pickup metrics; this determines whether P2’s genuinely unusual extra agent earns its cost. Sources: [Anthropic long-running harness](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents), [Handoff Debt](https://arxiv.org/abs/2606.02875).

3. **Turn boot testing into a versioned document-evaluation suite.** Add no-document baselines, negative cases, several fresh readers, cross-model runs, coexistence tests, and retained failures; this converts P3 from a good ritual into regression-tested infrastructure. Sources: [Anthropic Agent Skills best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices), [enterprise skill evaluation](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/enterprise).

4. **Make quarry import provenance executable rather than documentary.** A Python importer should perform the copy/transformation, compute source and destination digests, update a richer manifest, and run characterization checks in one operation; this eliminates the current undeclared-import and irreproducibility residual. Sources: [Google Copybara](https://github.com/google/copybara), [SLSA provenance](https://slsa.dev/spec/v1.2/provenance), [SPDX package information](https://spdx.github.io/spdx-spec/v2.3/package-information/).

5. **Harden the two-log protocol while preserving independent first passes.** Establish a genuinely shared path, atomic records, IDs, base SHAs, digests, cursors, acknowledgements, and explicit synthesis decisions; then measure which task classes benefit enough to justify double execution. Sources: [Anthropic multi-agent research](https://www.anthropic.com/engineering/multi-agent-research-system), [LLM-Blender](https://aclanthology.org/2023.acl-long.792/), [Event Sourcing](https://www.martinfowler.com/eaaDev/EventSourcing.html).

---

# SECOND PASS — adversarial verification (same day)

## Founding-context note (new-vp, 2026-07-21)

Adversarial second pass by Codex gpt-5.6-sol (xhigh, web search, read-only), prompted to overturn the first pass's three Medium-confidence verdicts using the first pass's own suggested search vectors. Report admitted verbatim below. Headline: all four re-examined verdicts DOWNGRADED — P2's fresh-reader clause found in the wild (Acai); P8 is vendoring/PDS governance applied inward; P9 is emerging standard practice; P1 has established names (cold-start, no-memory baseline, context ablation). The residual novelty is the governance bundles, not the mechanisms. Shortlist re-ranked; four net-new controls found.

# Adversarial second pass

I read `docs/issues/5-prior-art-cross-check.md` in full before searching, then read `README.md`. I treated the first pass as the baseline and searched specifically for its declared weak points.

Evidence labels:

- **READ** — I fetched and inspected the linked source.
- **INFER** — synthesis from multiple inspected sources; not an explicit source claim.
- **UNVERIFIED** — surfaced but could not be inspected or independently confirmed.

Searches were run on 2026-07-21 through the integrated web-search index, direct GitHub repository/file pages, GitHub Code Search URLs, arXiv, ACL Anthology, medRxiv, AHRQ, FAA, NASA, EASA, Mozilla, Google Open Source, and Chromium source. Unauthenticated GitHub Code Search and Semantic Scholar were intermittently unavailable; those failures are identified below.

## 1. P2 — fresh transcript reader authors the handoff

### Exact searches

Web/GitHub index:

```text
site:github.com ".claude/agents" (handoff OR handover) transcript summarizer Claude Code
site:github.com Claude Code "session handoff" transcript agent
site:github.com ("context handoff" OR "handoff agent") (Cline OR aider OR OpenHands OR SWE-agent OR AutoGPT)
site:github.com Claude Code plugin handoff continuity transcript summary
site:github.com/mattpocock/skills handoff skill transcript fresh agent
site:github.com "cs-handoff-author"
site:github.com "handoff-author" ".claude/agents"
site:github.com "session scribe" Claude Code transcript handoff
site:github.com/hesreallyhim/awesome-claude-code "handoff"
site:github.com "subagent" "transcript" "handoff.md" Claude
site:github.com "summarizer agent" "session handoff" coding
site:github.com "scribe agent" "session handoff" LLM
".acai/handoffs" "handoffPrompt"
github acai-ts commands handoff generateHandoffFilename
site:github.com/travisennis acai handoff command
"This handoff file can be used to continue the work using the /pickup command"
"handoffPrompt(purpose)" coding agent
"generateHandoffSlug" coding agent
"detailed handoff summaries for coding agents" github
"/pickup" ".acai/handoffs"
"creating detailed handoff summaries for coding agents"
"conversationText" "handoffPrompt" "generateText" handoff
Cline Memory Bank official documentation session reset memory files workflow
site:github.com/cline/cline "Memory Bank"
site:docs.cline.bot memory bank context continuity
site:github.com/GreatScottyMac/roo-code-memory-bank handoff session
```

Direct GitHub Code Search:

```text
"transcript_path" "handoff"
"fresh agent" "handoff"
"handoff" "SubagentStop"
```

These Code Search pages did not return inspectable results without authentication. **UNVERIFIED surface limitation**, not negative evidence.

Scholarly/operational literature:

```text
"Handoff Debt" LLM agent citations related papers
site:arxiv.org LLM agent conversation summarization continuity handoff memory transcript
site:aclanthology.org conversation summarization long-term dialogue memory recursive summary LLM agent
("clinical handoff" OR "aviation handover") "LLM agent" continuity
site:ahrq.gov handoff communication I-PASS SBAR receiver synthesis readback
site:faa.gov shift turnover handoff maintenance checklist communication
site:pubmed.ncbi.nlm.nih.gov I-PASS handoff bundle error reduction NEJM
scholar LLM agent handoff clinical aviation shift handover summarization
```

I also attempted a direct Semantic Scholar lookup for arXiv `2606.02875`; the response was unavailable. Exact-title searches found the paper and mirrors, but no independently verified citing papers.

### Findings

**READ — Acai contains the central mechanism the first pass failed to find.** A preserved Acai development session includes an implementation that serializes `messageHistory`, supplies that conversation to a separate `generateText` call whose system role is to create a detailed coding-agent handoff, and writes the generated result under `.acai/handoffs/` for later `/pickup`. That is substantively a stateless/fresh transcript reader authoring the handoff, even though it may reuse the configured model rather than launch a named subagent. [Acai session and implementation excerpt](https://gist.github.com/travisennis/77e39e0bfdc2ea5ba4b8bfaf35e98db8)

Important qualification: this is a public GitHub Gist containing a session and code excerpt, not a release artifact whose repository lineage and production use I could independently verify. It therefore has lower evidentiary weight than a maintained repository, but it is direct contrary evidence against novelty of the *fresh transcript reader* clause.

**READ — durable, chronological coding-agent transition corpora already exist.** The Claude Code Toolkit, now superseded by a cross-agent toolkit, persists timestamped transition documents under `.claude/transitions/`, supports `handoff`/`continue`, and describes them as cold-startable transitions that either Claude or Codex can resume. It is self-authored rather than independently drafted, but it weakens the “permanent chronological handoff corpus” part of P2. [Claude Code Toolkit](https://github.com/stefan-jansen/claude-code-toolkit)

**READ — Cline Memory Bank is self-maintained continuity, not independent authorship.** It uses structured Markdown read at the beginning of fresh tasks; `/newtask` distills decisions, file changes, and progress into a clean-context task. Its own instructions explicitly say that after a reset Cline relies entirely on the Memory Bank. The outgoing/current agent remains the documenter, however. [Cline Memory Bank](https://www.mintlify.com/cline/cline/features/memory-bank)

**READ — Handoff Debt establishes the right experimental comparison but not P2’s drafting protocol.** It freezes repositories at deterministic interruption points and compares repository-only, raw-trace, summary-note, and structured-note takeover. Across 181 handoff-point tasks and 724 takeover runs per successor model, context-bearing handoffs reduced median events by 20–59% and cumulative prompt tokens by 42–63%, while solved-rate effects were smaller and model-dependent. It does not assign summary authorship to a fresh reader or use sender correction as a protocol stage. [Handoff Debt](https://arxiv.org/abs/2606.02875)

**READ — clinical handoff practice independently validates receiver-authored reconstruction.** AHRQ’s I-PASS ends with **Synthesis by Receiver**, and TeamSTEPPS also defines a check-back as the recipient confirming that the message was understood as the source intended. This is very close to the epistemic rationale of “fresh reader drafts; informed sender corrects”: comprehension is tested by forcing the receiver to reconstruct state, then closing the loop. [AHRQ TeamSTEPPS/I-PASS](https://www.ahrq.gov/teamstepps-program/curriculum/communication/teach/two-day.html)

**READ — PAUSE-Agents is a close domain analogue.** This July 2026 medRxiv preprint routes ICU records through a scribe extractor, six role-specialized agents, conflict surfacing, deterministic safety checks, and synthesis to produce a source-attributed first draft that a clinician edits rather than an autonomous final note. In its small single-center evaluation, 98.8% of adjudicable claims were verified and 88% of briefs had no pertinent omission. It is clinical-data-to-handoff, not agent-transcript-to-handoff, and it lacks the numbered committed transcript corpus. [PAUSE-Agents](https://www.medrxiv.org/content/10.64898/2026.07.10.26357759v1)

**READ — conversation-memory research supplies evaluation warnings, not the exact workflow.** RMM prospectively summarizes dialogue at utterance, turn, and session levels and refines retrieval retrospectively; LongMemEval shows that summary-based memory can lose information relative to raw observations on some question classes. [RMM](https://aclanthology.org/2025.acl-long.413/), [LongMemEval](https://aclanthology.org/2024.acl-long.747/)

**UNVERIFIED — Handoff Debt citation lineage.** I found no verified paper citing Handoff Debt as of 2026-07-21. Its inspected bibliography did not expose a clinical- or aviation-handoff lineage. Given its June 2026 publication date, this absence has little inferential force.

### Verdict update

**DOWNGRADED — Medium-High confidence.**

Reclassification: **known constituent mechanism; still-unmatched exact governance bundle**.

The first pass’s strongest novelty premise—“the handoff is authored by a fresh transcript reader”—is refuted by the Acai implementation excerpt. Timestamped/durable coding-agent transition archives are also established. What remains unmatched is the complete conjunction:

1. fresh reader is the mandatory first author;
2. ending agent is restricted to correction rather than free rewriting;
3. correction is preserved as an auditable delta;
4. numbered handoff and denoised transcript are committed together;
5. the sequence is treated as a permanent learning corpus.

**Single strongest contrary evidence:** the [Acai handoff implementation](https://gist.github.com/travisennis/77e39e0bfdc2ea5ba4b8bfaf35e98db8).

### Worth borrowing

- Implement P2 explicitly as an **I-PASS-style receiver synthesis/check-back**: fresh agent drafts; predecessor marks omissions, false inferences, and priority errors; both versions and the correction diff remain available.
- Require source anchors in every handoff claim: transcript event/turn ID, commit SHA, file path, test result, or explicit `UNSUPPORTED`.
- Add PAUSE-style conflict surfacing: contradictory decisions, stale task states, differing SHAs, and unresolved ownership become structured warnings rather than silently reconciled prose.
- Evaluate at least five conditions: repository-only, raw transcript, predecessor self-summary, fresh-reader draft, and fresh-reader draft plus predecessor correction.
- Score successor task success, rediscovery events, prompt tokens, incorrect inherited assumptions, omitted blockers, and correction-diff size. Summary similarity is not a sufficient metric.

## 2. P8 — frozen predecessor quarry plus entry manifest

### Exact searches

```text
site:chromium.googlesource.com "README.chromium" Revision Date License Security Critical
site:firefox-source-docs.mozilla.org vendoring moz.yaml origin revision release license tracking
site:docs.yoctoproject.org SRCREV LIC_FILES_CHKSUM provenance recipe source revision
site:buildroot.org manual package source version license hash provenance
site:faa.gov DO-178C previously developed software reuse data configuration traceability
site:easa.europa.eu DO-178C previously developed software PDS reuse records
DO-178C section 12.1.4 previously developed software reuse objectives source code traceability configuration index
site:nasa.gov software reuse provenance legacy code migration record
monorepo extraction tool source commit mapping migration ledger repository split provenance
site:github.com monorepo split "source commit" manifest migration
large rewrite port "migration ledger" component by component source revision
selective import legacy repository source commit manifest component migration
Python 2 to 3 port component migration tracking document ledger repository
GCC to LLVM migration component by component compatibility tracking source code import
BoringSSL OpenSSL fork import upstream commit tracking README migration
Firefox Quantum rewrite migration component tracking legacy source import
site:android.googlesource.com METADATA third_party url version last_upgrade_date license revision
site:opensource.google/documentation/reference/thirdparty metadata source provenance fields
site:source.android.com third party METADATA file provenance version URL license
Google third_party METADATA file last_upgrade_date version URL
"frozen legacy" repository "port" component
"read-only" legacy repository successor "import" code
"archived repository" "selectively port" features successor
"legacy repository" "source of truth" "port" new repository
```

### Findings

**READ — Google’s third-party admission procedure is nearly the entry-checkpoint manifest.** Every package directory requires `METADATA`; normal package records include name, description, source URL, exact version, and `last_upgrade_date`. Google further requires the **first changelist** to contain the code plus `OWNERS`, `BUILD`, `LICENSE`, and `METADATA`, and requires only one new package per changelist. This is component-scoped, same-change provenance admission with an explicit date and purpose/description. [Google METADATA](https://opensource.google/documentation/reference/thirdparty/metadata), [Google code-retrieval and first-CL policy](https://opensource.google/documentation/reference/thirdparty/retrieving)

**READ — Mozilla’s vendoring system is an executable provenance manifest.** Each `moz.yaml` records the source location, release, exact commit revision, description, license, optional local patches, include/exclude rules, and ordered update/post-patch transformations. `mach vendor` imports a specified revision through that manifest. This is stronger than a prose ledger because the provenance record is also the executable import recipe. [Mozilla vendoring documentation](https://firefox-source-docs.mozilla.org/mozbuild/vendor/index.html)

**READ — Chromium records hard-fork status explicitly.** `README.chromium` requires source URL, exact revision for Git upstreams, update mechanism, license, shipment/security status, description, and local modifications. Valid update mechanisms include `Static.HardFork`, and automated uprev processes must update the recorded revision. [Chromium `README.chromium` template](https://chromium.googlesource.com/chromium/src/%2B/main/third_party/README.chromium.template)

**READ — Mozilla also has same-patch component migration recipes.** When part of Firefox’s UI is migrated to Fluent, the migration recipe should be attached to the same patch that introduces the new strings. Recipes name source and target files and encode transformations from legacy identifiers. This is domain-limited to localization, but it demonstrates one-slice-at-a-time migration with the transformation record admitted alongside the destination change. [Mozilla Fluent migration lifecycle](https://firefox-source-docs.mozilla.org/l10n/migrations/overview.html)

**READ — retaining the predecessor read-only as a quarry is established migration advice.** Atlassian’s Perforce-to-Git “start over” option imports a clean tip snapshot and recommends retaining the old Perforce server read-only so engineers can investigate historical code. It lacks P8’s per-component entry ledger but directly matches the frozen-reference half. [Atlassian Perforce-to-Git migration](https://www.atlassian.com/git/tutorials/perforce-git-migration)

**READ — safety-critical reuse imposes deeper evidence than P8 currently proposes.** NASA requires reused/legacy software, associated requirements, architecture, tests, defects, maintenance history, and configuration-controlled records to be gathered and retained. FAA guidance treats reuse as reuse of approved lifecycle data and expects traceability through requirements, design, source, executable object code, tests/results, and Software Configuration Index records. EASA guidance similarly requires change-impact analysis and reverification evidence for legacy baseline upgrades. [NASA SWE-027](https://swehb.nasa.gov/spaces/7150/pages/16449873/SWE-027%2B-%2BUse%2Bof%2BCommercial%2BGovernment%2Band%2BLegacy%2BSoftware), [FAA Order 8110.49](https://www.faa.gov/documentLibrary/media/Order/FAA_Order_8110_49_w-chg_2.pdf), [EASA legacy-software guidance](https://www.easa.europa.eu/en/document-library/easy-access-rules/online-publications/easy-access-rules-acceptable-means?page=22)

**READ — ecosystem provenance controls add integrity checks.** Buildroot stores hashes for downloaded sources and license files, making unexpected source or licensing changes fail validation. This is not a migration ledger, but it supplies the missing content-integrity dimension. [Buildroot manual](https://buildroot.org/downloads/manual/manual.html)

**UNVERIFIED negative result — named large rewrites.** Searches for Python 2→3, GCC→LLVM, OpenSSL→BoringSSL, Firefox Quantum, and healthcare/banking rewrite ledgers did not produce a reputable public artifact combining a frozen source repository with a per-component source-commit/purpose/date admission ledger. BoringSSL’s public history explains its origin in Google’s OpenSSL patch stack, but I found no corresponding selective-import manifest. [BoringSSL README](https://boringssl.googlesource.com/boringssl.git/%2B/34b51faf3a58fe36e3ab1db99a2a441d0f69c754/README.md)

### Verdict update

**DOWNGRADED — High confidence.**

Reclassification: **established software-admission pattern applied to an unusual source category**.

P8’s controls are not genuinely novel. Google already requires one-component-per-change admission with code and provenance metadata in the same first change. Mozilla already has executable component manifests with exact revisions and transformations. Retaining a legacy system read-only for historical excavation is also established.

The residual distinction is organizational: nedschorus treats its own predecessor as if it were an untrusted third-party/hard-fork source whose components must earn admission. That is a sharp doctrine, but the underlying mechanism is a direct adaptation of mature vendoring and previously-developed-software governance.

**Single strongest contrary evidence:** Google’s [first-CL and one-package-per-CL policy](https://opensource.google/documentation/reference/thirdparty/retrieving), combined with its mandatory [METADATA schema](https://opensource.google/documentation/reference/thirdparty/metadata).

### Worth borrowing

Make the manifest both declarative and executable. Minimum record:

```text
component_id
destination_paths
source_repository
source_revision
source_paths
source_content_digest
admission_date
purpose / capability supplied
reason existing successor code is insufficient
import_method
include / exclude rules
transformations and local patches
characterization tests
known inherited defects
license / security status
owner
reviewer
```

Enforce:

- one component per admission change;
- manifest, imported code, tests, and transformation recipe in the same commit;
- exact revision, never branch name;
- digest verification;
- explicit `static-hard-fork`/`no-upstream-sync` status;
- CI rejection when imported paths lack a manifest or the manifest revision/digest disagrees with the content.

## 3. P9 — heterogeneous dual agents, isolated workspaces, logs, synthesis

### Exact searches

```text
GitHub multi CLI coding agent coordinator Claude Code Codex tmux worktree filesystem mailbox
site:github.com Claude Codex "agent inbox" "outbox" coding
site:github.com multi-agent coding tmux worktree append-only log mailbox
site:github.com Claude Code Codex same task parallel synthesis separate worktrees
site:github.com LLM agent filesystem mailbox worktree tmux agent mail coding
site:github.com multi-agent coding append-only JSONL mailbox worktrees Claude Codex
site:github.com blackboard architecture LLM multi agent shared memory message board
site:github.com mcp-agent-mail agents mailbox git worktree
blackboard architecture multi-agent systems Hayes-Roth 1985 PDF
LLM multi-agent blackboard architecture paper shared blackboard 2024 2025
"ESAA-Conversational" citations follow-up
arXiv 2606.23752 ESAA-Conversational code repository
"ESAA-Conversational: An Event-Sourced Memory Layer" -arxiv
"2606.23752" citations
"Event-Sourcing Agent Architecture" ESAA GitHub
site:github.com "activity.jsonl" "handoff.md" "ESAA"
```

### Findings

**READ — Crystal directly implements the core dual-runtime experiment.** Crystal is a completed desktop application for managing Claude Code and Codex instances against one project using isolated Git worktrees. Its project documentation explicitly says it runs parallel assistant sessions with different approaches to the same problem, persists sessions in SQLite, visualizes diffs, and supports squash/rebase integration. Worktrees are not literally independent clones, but they provide the intended source-tree isolation. [Crystal](https://github.com/stravu/crystal/blob/main/CLAUDE.md)

**READ — dmux makes heterogeneous worktree parallelism routine.** One prompt can launch a selected combination of Claude Code, Codex, Gemini, Cline, and other CLIs; each task/agent receives a separate tmux pane, worktree, and branch, with merge or PR integration afterward. It does not prescribe mutual communication or single-writer synthesis. [dmux](https://github.com/standardagents/dmux)

**READ — heterogeneous analysis/consolidation/review pipelines already exist.** The `claude-codex` plugin runs parallel Claude analyses, has an orchestrator consolidate their outputs, and uses Codex as a validation/review gate before implementation. It lacks separate clones and bidirectional append-only logs, but it covers heterogeneous models, independent analysis, controlled consolidation, and a designated integration path. [claude-codex](https://github.com/Z-M-Huang/claude-codex)

**READ — filesystem-backed agent mail is substantially more developed than two directional log files.** MCP Agent Mail supports Claude, Codex, Gemini, and other coding agents with identities, inbox/outbox semantics, threaded messages, acknowledgements, advisory file leases, Git-backed human-auditable artifacts, and SQLite indexing. Its canonical messages are durable records rather than two unstructured transcript files. [MCP Agent Mail](https://github.com/Dicklesworthstone/mcp_agent_mail)

**READ — ESAA-Conversational nearly subsumes the log substrate.** It normalizes heterogeneous agents’ native logs into append-only `activity.jsonl`, then deterministically projects `handoff.md`, `state.md`, `decisions.md`, and `tasks.json`. It includes workspace isolation and a write-path lockfile. It addresses continuity rather than deliberately assigning the same task to two agents, but its event model is a stronger version of P9’s filesystem bridge. [ESAA-Conversational](https://arxiv.org/abs/2606.23752)

**READ — blackboard coordination is old and has explicit LLM revivals.** Hayes-Roth’s 1985 blackboard control architecture separates shared domain state from control knowledge; a 2025 LLM implementation places role agents around a shared board, repeatedly selecting contributors until consensus. Thus “agents coordinate indirectly through a shared artifact” is canonical architecture, not a new agent pattern. [Hayes-Roth 1985](https://www.sciencedirect.com/science/article/pii/0004370285900633), [LLM blackboard system](https://arxiv.org/abs/2507.01701)

**UNVERIFIED — ESAA follow-ups/citations.** Exact-title and arXiv-ID searches found the paper and indexing mirrors, but no verified follow-up or citing work. The linked GitHub repository surfaced through social/indexing results as unavailable. This does not undermine the paper’s inspected design, but I could not audit its claimed public implementation repository.

**INFER — the two-file bridge is not the valuable novelty.** Two direction-specific append-only files are a minimal mailbox/event-log encoding. Crystal supplies the heterogeneous same-task/worktree topology; Agent Mail supplies the mailbox; ESAA supplies append-only normalization and projections; orchestrator pipelines supply consolidation. P9 combines known mechanisms but does not introduce a new coordination abstraction.

### Verdict update

**DOWNGRADED — High confidence.**

Reclassification: **emerging established practice; locally distinctive minimal encoding**.

The first pass’s “known-but-rare” label was reasonable at the abstract level, but current tooling shows heterogeneous coding agents in parallel worktrees becoming an ordinary supported workflow. The precise combination of *two* append-only files and a single synthesizer remains unmatched, but that is an implementation choice rather than meaningful prior-art novelty.

**Single strongest contrary evidence:** [Crystal](https://github.com/stravu/crystal/blob/main/CLAUDE.md), because it explicitly supports Claude and Codex taking different approaches to the same problem in isolated worktrees.

### Worth borrowing

Do not merely harden two prose logs. Replace them with a minimal event envelope:

```text
event_id
schema_version
timestamp
writer_identity
runtime / model
task_id
workspace / branch
base_sha
current_sha
event_type
caused_by
reply_to
payload
payload_digest
ack_required
```

Then add:

- atomic append or a single append service;
- per-reader cursors and acknowledgements;
- deterministic projections for current state, open questions, decisions, and synthesis inputs;
- replay/verification from the immutable event stream;
- independent first-pass outputs hidden from the other agent until both are complete;
- a named synthesizer with sole write authority to the integration branch;
- explicit attribution when synthesis selects, rejects, or combines agent conclusions.

## 4. P1 — empty context as a test instrument

### Exact searches

```text
LLM agent evaluation "no-memory baseline" context ablation
LLM agent "cold-start" evaluation fresh context
LLM "context isolation" evaluation agent memory
LLM "epistemic contamination" context agent
machine teaching teaching dimension minimal teaching set survey primary paper
machine teaching evaluation learner from instructions document fresh learner
LLM documentation evaluation fresh agent no context instructions test
agent memory benchmark no-memory baseline LongMemEval MemoryAgentBench
```

### Findings

**READ — “cold-start” is now an explicit controlled agent-evaluation condition.** SODA controls the number of ordinary agentic tasks preceding a safety test from zero to twenty. Across seven models, safety reportedly improves by 9–52% from depth zero to depth twenty; the authors name the zero/early-history failure mode the **cold-start safety gap**. This is direct evidence that absence of conversational history is being deliberately manipulated as an independent variable. [Cold-Start Safety Gap/SODA](https://arxiv.org/abs/2606.07867)

**READ — “no-memory baseline” is explicit benchmark practice.** Microsoft’s STATE-Bench instructs evaluators to run a no-memory baseline, then plug in a memory system and compare reliability, turns, latency, and user experience across a reproducible environment. [STATE-Bench](https://opensource.microsoft.com/blog/2026/05/19/introducing-state-bench-a-benchmark-for-ai-agent-memory/)

**READ — context isolation and contamination are measurable experimental variables.** DACS evaluates per-agent context isolation against flat shared context and reports wrong-agent contamination; the mechanism defines exactly which agent context is present during steering. [Dynamic Attentional Context Scoping](https://arxiv.org/abs/2604.07911)

**READ — “epistemic blinding” is an adjacent, more rigorous contamination control.** It anonymizes entity identities, compares blinded and unblinded inference, and measures how much the answer depends on supplied evidence versus model priors. That addresses a limitation P1’s empty transcript cannot solve: a fresh agent still carries parametric training knowledge. [Epistemic Blinding](https://arxiv.org/abs/2604.06013)

**READ — agent-memory literature routinely includes empty/no-memory controls.** MemoryAgentBench evaluates retrieval, test-time learning, long-range understanding, and selective forgetting; newer systems report explicit no-memory baselines and component ablations. [MemoryAgentBench](https://arxiv.org/abs/2507.05257), [LongMemEval-V2](https://arxiv.org/abs/2605.12493)

**READ/INFER — machine teaching gives the theoretical analogy, not the operational name.** Teaching dimension is the minimum teaching set needed for a specified learner to identify a target concept. Treating a repository document as a teaching set and a fresh agent as the learner is a legitimate framing, but I found no reputable source using “teaching dimension” for coding-agent documentation acceptance. [Teaching dimension for modern learners](https://arxiv.org/abs/1512.02181)

There is therefore no single canonical name for P1’s full operation. The established vocabulary is:

- **cold-start / zero-depth condition** — no preceding interaction;
- **no-memory baseline** — memory mechanism absent;
- **context ablation** — selected context removed;
- **context isolation** — unrelated context prevented from entering;
- **epistemic blinding** — identity/prior cues removed to measure evidence dependence.

“Cold start” alone is ambiguous because systems literature also uses it for container, cache, and model startup latency.

### Verdict update

**DOWNGRADED — High confidence.**

Reclassification: **established evaluation method; unusual documentation-acceptance application**.

Empty context as a deliberate test instrument already has both names and practice. What remains uncommon is using a **document-only zero-history agent run as a repository governance gate**: the document is accepted only if a controlled fresh agent reconstructs and applies the intended system correctly.

**Single strongest contrary evidence:** [SODA](https://arxiv.org/abs/2606.07867), because it experimentally controls conversational depth with zero as the deliberate baseline condition.

### Worth borrowing

Name the nedschorus procedure precisely: **zero-history, document-only acceptance evaluation**.

Record the full context contract:

```text
model and runtime version
system/developer instructions
conversation depth = 0
memory enabled/disabled
exact supplied files and revisions
tool/network permissions
repository SHA
task prompt
random seed or repeated-run count
termination rule
grader and scoring rubric
```

Use a small factorial design:

1. zero-history + target document only;
2. zero-history + document + repository;
3. no document + repository only;
4. ordinary accumulated context;
5. oracle context containing the intended interpretation.

Repeat runs to separate document defects from sampling variance. For claims vulnerable to model priors, add blinded identifiers or synthetic names.

## SHORTLIST RE-RANK

1. **Remote-enforce the single-writer throat — unchanged at #1.** Nothing in this pass weakens the integrity value of making synthesis authority technically enforceable rather than conventional.

2. **Run the controlled handoff experiment — unchanged at #2, but expand it.** Acai and I-PASS make fresh-reader authorship less novel, while Handoff Debt supplies a strong takeover protocol; add predecessor-correction deltas, source anchors, and conflict scoring.

3. **Executable quarry provenance — move from #4 to #3.** Google and Mozilla provide mature schemas and enforcement patterns, so this can be implemented with much less design uncertainty than the first pass implied.

4. **Versioned document-evaluation suite — move from #3 to #4.** It remains valuable, but the second pass shows that its core experimental method is standard no-memory/context-ablation practice rather than an unresolved research design.

5. **Replace “harden the two-log bridge” with “adopt a replayable event/mail substrate.”** Two prose files should not be polished into a bespoke protocol when Agent Mail and ESAA demonstrate IDs, acknowledgements, locking, immutable events, indexing, and deterministic projections.

## NET-NEW ART

I found no convincing tenth founding pattern across P1–P9. I did find four significant controls the first pass missed:

1. **Receiver synthesis/check-back as the governing handoff principle.** I-PASS provides a stronger justification for P2 than generic summarization literature: the recipient must demonstrate its reconstruction, and the source must close the loop.

2. **Epistemic blinding.** Fresh context removes conversational contamination but not parametric prior knowledge. Anonymized entities plus blinded/unblinded comparison would make P1-style probes capable of distinguishing “learned from this document” from “already knew or guessed.”

3. **Raw evidence should remain first-class because consolidation can be harmful.** A 2026 agent-memory study reports that repeatedly consolidated LLM memories can degrade below a no-memory baseline and recommends preserving raw episodes while gating consolidation. This materially supports P2’s decision to retain transcripts, but argues that denoised summaries must never replace them as the evidentiary source. [Useful Memories Become Faulty When Continuously Updated by LLMs](https://arxiv.org/abs/2605.12978)

4. **Source attribution and conflict surfacing belong before synthesis.** PAUSE-Agents’ source-attributed claims, explicit conflicts, and deterministic safety flags are directly transferable to handoffs and multi-agent synthesis. The useful abstraction is not “another summarizer”; it is a draft whose claims remain traceable and whose inconsistencies are represented rather than silently resolved.

Net result: none of the four exact compositions was completely overturned by a single verified predecessor, but all four first-pass novelty assessments should be narrowed. P2 retains a distinctive correction-and-corpus governance bundle; P8 is vendor-admission governance applied inward; P9 is an increasingly standard heterogeneous-worktree workflow with an unusually minimal transport; and P1 is a standard context-control experiment repurposed as documentation acceptance.