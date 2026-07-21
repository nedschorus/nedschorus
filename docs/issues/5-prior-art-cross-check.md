Issue: https://github.com/nedlern/nedschorus/issues/5

## Founding-context note (new-vp, 2026-07-21)

Research by Codex gpt-5.6-sol (xhigh, web search, this repository read-only at HEAD 188ee38). Report admitted verbatim below. Verdicts feed the README/principles update; borrowings feed the borrow-list; the bridge topology defect routes to the bridge re-derivation. Dispose (delete or promote) in the commit that closes issue 5.

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