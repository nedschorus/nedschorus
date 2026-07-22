Issue: https://github.com/nedschorus/nedschorus/issues/10

## Admission note (new-vp, 2026-07-22)

- Boss-directed capture artifact, cops-reconstructed 2026-07-22 from the 2026-07-21 discussion and Ned's Google-Doc notes (the cleaned version had remained in chat); admitted through the single-admitter gate as pair #10. Capture ≠ commitment: nothing here is scheduled work, and the boss's walk rules which candidates advance.
- The "Related detailed documents" links name cops-local filenames; in this repository that material is [pair #4](4-open-source-publishing-community-strategy.md) (publishing strategy) and [pair #9](9-neds-notes.md) (engineering methods).
- One redaction from the otherwise-verbatim body: the two raw leaked-source mirror URLs under "Raw Claude Code mirrors" are omitted from this public copy, per that subsection's own retain-privately / do-not-cite-publicly instruction; they remain in cops's peer-local original (`tasks/sessions/cops-nedschorus-working-ideas-and-research-backlog-2026-07-22.md`, old-system side). The broader which-links-are-public question is one of the body's own unresolved questions — boss walk pending.
- Revisions ride this pair as ordinary REVISE dispositions.

# NedsChorus Working Ideas and Research Backlog

This document preserves the combined rough notes from Ned's Google Doc and the
2026-07-21 discussion. It captures worthwhile ideas without implying that all
of them should be implemented, researched, or scheduled now.

It was reconstructed from the session transcript on 2026-07-22 because the
original cleaned version remained in chat instead of being saved as a file.

## How to read this document

- **Decided** means Ned or the NedsChorus founding process has explicitly
  accepted the direction.
- **Candidate** means the idea deserves evaluation but is not doctrine.
- **Research** means a bounded question still needs evidence.
- **Reference** means the link may help answer a specific question; inclusion
  is not endorsement.
- Capturing an idea here does not make it current work.

The governing approach is:

1. Concentrate active work on the few most important things.
2. Keep designs and implementations simple and modular.
3. Preserve important future ideas so they are available when needed.
4. Do not convert a brainstorm into doctrine without evidence and review.
5. Build one understandable, bounded module at a time.

## Related detailed documents

- [Open-source publishing and community strategy](cops-nedschorus-open-source-publishing-community-strategy-2026-07-21.md) contains the detailed publishing/channel design.
- [Engineering methods and source research](cops-neds-notes-2026-07-21.md) contains the curated software-engineering skill shortlist, source assessments, rejected alternatives, and accepted `walk-me-through` changes.
- The NedsChorus repository contains the admitted publishing artifact at `/Users/el/Projects/nedschorus/docs/issues/4-open-source-publishing-community-strategy.md`.

## Decided direction

### NedsChorus is a careful new system

- NedsChorus is a ground-up successor informed by six months of study,
  implementation, testing, and failure analysis.
- Nedlern is a quarry and evidence source, not a template.
- Nothing crosses from Nedlern merely because it already exists.
- Useful behavior must be identified, understood, reviewed, and deliberately
  re-admitted.

### Open source and publishing

- Open-source NedsChorus.
- Publish regularly, ideally daily when there is real material.
- Use one strong canonical article and adapt it for multiple channels with
  agent assistance.
- Do not reduce publishing frequency merely because manual adaptation would be
  expensive; improve the adaptation and review workflow instead.
- The intended surfaces include:
  - `nedschorus.com`
  - Substack
  - LinkedIn
  - The project's own subreddit
  - Appropriate programmer communities and social channels
- The broad workflow is:
  1. Write one canonical article.
  2. Produce channel-appropriate versions.
  3. Review each adaptation for accuracy, tone, and platform fit.
  4. Publish broadly.
  5. Record where each version appeared and what happened.
- Possible future article or series title: **Toddlers with Machine Guns**.

The precise channel roles and proposed publishing mechanics are in the linked
publishing strategy. This backlog preserves the underlying direction without
making every channel or cadence an immediate implementation commitment.

### Durable Markdown and GitHub issues

The founding work has resolved the original artifact-placement questions:

- A request for a durable Markdown document creates an MD-GitHub-issue pair.
- Working documents live at `docs/issues/<number>-<slug>.md`.
- Permanent truth graduates to `docs/wiki/`.
- Session continuity lives under `handoff/`.
- Cross-project founding material lives under `docs/cross-project/`.
- Markdown provenance belongs in git commit history.
- GitHub-issue provenance belongs in the issue body or revision comments.
- NedsChorus has one admitting agent controlling changes to the new repository.

The original open questions about whether an artifact should be a GitHub issue,
a Markdown document, or both should not be reopened without new evidence.

### Walkthroughs and comprehensibility

- A walkthrough presents one independently reactable item or subitem per turn.
- The user controls advancement.
- Three hundred words is a maximum comprehensible packet, not a brevity target.
- Shorter is not better when it removes necessary context, evidence, reasoning,
  examples, distinctions, or qualifications.
- Material needing more than 300 words is divided into additional items or
  subitems instead of compressed.
- Decisions are captured as the walkthrough proceeds.
- A decision may revise, remove, or reorder later items.
- Claude and Codex should share one behavioral contract with thin
  runtime-specific wrappers and common scenario tests.

## Candidate publishing modules

These are possible independent skills, not a commitment to build a publishing
framework all at once:

- Draft a canonical article from project evidence.
- Edit the canonical article for clarity and factual support.
- Adapt it to each selected channel without flattening every channel into the
  same generic post.
- Review adaptations against the canonical source.
- Publish to a named channel.
- Record canonical URL, derivative URLs, dates, and observable outcomes.
- Produce and validate social-preview metadata and imagery.

Each module should have one responsibility, explicit inputs, an observable
output, and a clear failure result. The workflow should be exercised manually
before automating consequential external publication.

## Candidate document and directory structure

- Give each subsystem one greppable identity across code, tests,
  documentation, designs, and test plans.
- Create a subsystem subdirectory within a root when multiple related files
  justify it; do not create speculative empty scaffolding.
- Keep temporary artifacts out of durable document locations.
- Give every major system an overview that identifies:
  - Purpose and responsibilities
  - Architecture
  - Accountable steward
  - Important files and interfaces
  - Project-specific technical concepts
  - Links to its design and test plan
- Make designs, test plans, implementation, and evidence mutually searchable.
- Evaluate whether a primary implementation filename should appear in related
  design and test-plan filenames or text.
- Document the safe method for editing and versioning files outside the active
  worktree.
- Configure distinct, attributable GitHub and git identities for agents that
  write to the repository.
- Consider a small, tested recovery tool for files available only in Time
  Machine backups.

## Reusable specification and adversarial-review pattern

For a substantial executable specification, consider including:

- Objective and scope
- Assumptions and supporting evidence
- Non-goals
- Invariants
- Acceptance criteria
- Edge cases
- Failure and recovery behavior
- Security and privacy boundaries
- Migration or compatibility requirements
- Observable outcomes
- Open questions
- Claims that can become automated tests
- Claims that still require human review
- Examples of an implementation satisfying the written criteria while
  violating the intent

These sections are not mandatory boilerplate for every small issue. The test is
whether the omission could let important behavior, risk, or intent go
unexamined.

After the draft, give a fresh reviewer the artifact and governing contract:

> Attack this result. Find contradictions, ambiguous terms, hidden
> dependencies, untestable claims, missing failure modes, and places where an
> implementation could satisfy the written criteria while still violating the
> intent.

Candidate review mechanics:

- Pin the exact revision being reviewed.
- Keep the first pass analysis-only and independent.
- Require file/line evidence when files exist.
- Require a concrete failure scenario for every material finding.
- Require the author to accept, reject with evidence, or supersede every
  finding.
- Rerun review after material changes.

The separate engineering note records that no external `write-test-plan` or
general plan-attack skill met the desired quality bar. Those remain candidates
for small NedsChorus-native skills, not reasons to import a large framework.

## Candidate engineering rules

These statements preserve the original ideas, with overbroad wording narrowed
where the later discussion identified a problem.

### Evidence and change discipline

- Every risk-bearing transition, side effect, and acceptance criterion should
  have appropriate evidence. Routine mechanics do not need ceremonial checks.
- Every meaningful file change should have a stated purpose.
- When production code fails after extensive review, investigate causes deeper
  than insufficient review.
- A fix without a reproducing check may only be masking symptoms.
- When a root cause is suspected, reproduce the failure before changing the
  system when doing so is safe and practical.
- If the proposed check cannot reproduce the failure, the suspected cause may
  be wrong, incomplete, nondeterministic, or inadequately observed.
- Stop root-cause investigation at a verified causal boundary that explains
  the failure and supports a durable correction; do not recurse indefinitely.
- If the same file, subsystem, or complexity area is repeatedly patched, stop
  and reassess the design. "After two patches" remains a candidate warning,
  not a universal numeric rule.

### Review discipline

- Identify inconsistent, malformed, unclear, or unnecessary complexity.
- Verify that implementation behavior satisfies the governing specification,
  not merely that the diff looks plausible.
- Watch for complexity creep through additional lines, states, database
  columns, checks, exceptions, and review rounds that add machinery without
  resolving the defect.
- When a real state machine exists, define its states, events, guards,
  transitions, side effects, and invalid transitions.
- Do not invent additional states or exceptions without demonstrated need.
- Treat new database columns as a design-review signal, not an automatic
  prohibition.
- Protect schema integrity and migration safety.
- Remove dead code when safe instead of preserving it indefinitely.
- Evaluate built-in `/code-review` and `/simplify` capabilities with evidence
  before relying on them.
- Review the review system itself, including GitHub Actions and Codex/Claude
  behavior.
- Preserve independent first passes for important artifacts.
- Long-lived subsystem expertise and fresh-context review are complementary;
  reviewers do not all need to be disposable.
- When one runtime asks another to implement or test, review the design and
  test plan as well as the final code when those artifacts are material.

## Testing, QA, and root-cause research

### Candidate testing practices

- Translate specifications and suspected faults into concrete test plans.
- Give unreliable or unproven systems a bounded end-to-end check.
- A waker must verify that the intended agent actually woke and could receive
  work.
- A backup process needs a restoration or integrity check proving that the
  backup is usable.
- Further changes to a file or behavior should rerun the check that detected,
  or should have detected, the previous failure.
- Improve reproducibility enough to distinguish causal failures from guesses.
- Research practical TDD practices, especially useful conventions rarely
  written in introductory explanations.
- Evaluate whether test-first design should mirror the system's actual roles,
  boundaries, and workflow.

### Failure hypotheses to consider

- Local implementation defect
- Incorrect use of an external API
- Defect or undocumented behavior in an external API
- Bad or changed dependency
- Flawed design assumption
- Race condition or ordering fault
- Incorrect diagnosis of the failing component
- Missing or misleading telemetry

Ask:

- What evidence identifies the causal boundary?
- What else could produce the same symptom?
- What observation would confirm or refute the current hypothesis?
- Is the change correcting the cause, mitigating impact, or masking the
  symptom?

## Candidate design-document standard

Important designs may need completeness rather than aggressive compression.
Use only the elements needed for the system's risk and complexity:

- Important paths, steps, and states
- Mermaid diagrams when they materially clarify relationships
- Transition tables with:
  - From state
  - To state
  - Event
  - Guard
  - Side effects
- Inputs, outputs, failure results, and fallible operations for important
  interfaces
- Exact names of significant files, functions, states, and components
- Clear standard terminology rather than invented shorthand
- Links among overview, design, implementation, test plan, and evidence

Complete function-by-function designs are probably excessive for small changes.
They are more defensible for public interfaces, persistent state, concurrency,
state machines, migrations, and other high-risk behavior.

## Agent organization questions

### Possible lifecycle roles

These roles describe kinds of work, not necessarily permanent agents:

- **Prototyper:** generates and tests many ideas.
- **Builder:** converts a promising prototype into a reliable system.
- **Sweeper:** simplifies code and UI, removes unnecessary behavior, and
  improves performance.
- **Grower:** iterates on an existing product to improve usefulness and fit.
- **Maintainer:** keeps a mature system secure, reliable, efficient, and
  understandable.

### Possible organizational structure

- Boss or consigliere
- Head of product reporting to the boss
- Leads for project management, engineering, QA, documentation, UX,
  operations, and sustainability/maintenance
- Cross-cutting masters or specialists for wiki/documentation, DevOps,
  git/GitHub, communications, Claude, Codex, operating systems, research, and
  general systems

This model is a captured possibility, not an endorsed hierarchy.

### Questions to resolve only when needed

- Should each subsystem have one accountable steward, a pair, or another
  arrangement?
- How do we avoid confusing stewardship with exclusive control?
- Which tasks need long-lived current context?
- Which tasks benefit from zero-context or deliberately minimal-context
  execution?
- What exact context does each task type require?
- When is a fresh reviewer preferable to a persistent specialist?
- How long should temporary agents live, and how are they retired cleanly?
- Could a wiki agent answer bounded questions about documented project truth?
- Could a fast monitor connect working agents with the appropriate specialist?
- When transferring work, should Codex receive selected Claude evidence,
  denoised transcripts, or raw turns?
- Can explicit mentions request independent opinions, or should routing remain
  mechanical?

Current caution: one admitting writer is useful for repository control; one
exclusive intellectual controller per subsystem would create bottlenecks and a
bus factor. Any agent should be able to investigate and criticize, with clear
responsibility for disposition and admission.

## Communications backlog

- Minimize unnecessary console communication without removing required
  context.
- Determine which communications should use a supported API rather than MCP.
- Preserve both agent-level and task-level addressing where both are useful.
- Maintain a concise, current communications-fix plan.
- Decide how Ned should be notified about genuinely important events:
  - Popup
  - Temporary Markdown artifact
  - Direct message
  - Another mechanism
- Evaluate a safe function for inserting text into the correct console.
- Detect interruptions and waiting states that require intervention.
- Make walkthrough decisions durable as they occur.
- Make end-of-turn messages self-contained.
- Avoid bare issue numbers, bare filenames, and unexplained references.
- Give recommendations enough context to remain understandable later.
- Avoid fake choices when only one option is credible.
- When reviewing designs, explain material subtleties completely.

## Status, monitoring, and introspection backlog

Investigate supported session/runtime state before building a monitoring system.
The old notes specifically mention `~/.claude/sessions/<pid>.json` and possible
values such as `idle`, `busy`, `shell`, and `waiting`; these are hypotheses to
verify against the current runtime, not a stable contract.

Possible work:

- Determine whether recaps are customizable.
- Evaluate small agent-introspection tools.
- Document the required JSONL subset and its instability.
- Prefer supported session APIs or a versioned adapter over raw JSONL when
  practical.
- Decide whether a denoised introspection artifact is easier to back up and use
  than raw logs.
- Answer the smallest operational question first: **Which agent needs
  attention, and why?**
- Potentially show:
  - Busy or idle
  - Current task
  - Time on task
  - Waiting or interrupted state
  - Cost and duration of the last turn
  - Current walkthrough position
- Investigate why agents sometimes announce an action, become idle, and need a
  second wake.
- Use a controlled test project to tune monitoring behavior.
- Treat idle time as a possible opportunity for safe repository catch-up, not
  an unconditional instruction to mutate git state.

Do not begin with a large dashboard. Add data only when it supports a real
operator decision.

## Claude and Codex runtime research

These items require sharper definitions before research begins:

- **Claude demotion and "why 10":** identify what demotion means, what value is
  10, where the claim originated, and which decision depends on it.
- **Bad-words list:** separately trace the production source and test whether a
  harmless fixture change is observed without restart.
- **Instruction compression:** experiment with smaller `CLAUDE.md`, `AGENTS.md`,
  and wiki files while measuring whether fresh-agent behavior loses essential
  rules. Fewer words alone is not success.
- Review runtime instruction files for conflict with system-level instructions
  and actual precedence.
- Grep broadly before inventing names; use a more explicit name when collisions
  or ambiguity exist.
- Consider a small reviewer for conflicting or ambiguous names and context.
- Investigate output styles:
  - Whether they can be assigned per agent
  - Whether they materially change action-taking
  - Which visible and hidden instructions they add
- Investigate clearing context and resuming from earlier turns.
- If backward resumption can lose already-consumed messages, determine how to
  recover the relevant evidence from transcript or durable handoff.
- Scrub instruction files deliberately rather than repeatedly squeezing them.
- Evaluate a dedicated memory maintenance program or API.
- Let durable memory entries point to exact wiki pages when that improves
  retrieval.

## Ways to run prompts in code

Captured execution models:

1. Call a prompt synchronously without tool access.
2. Call an agent with tool access.
3. Build a custom provider/API integration.

For asynchronous work, compare detached workers with a simpler queued,
synchronous loop. Detached processes add concurrency, ownership, cancellation,
and recovery problems; use them only when the benefit is demonstrated.

## Turn and hook order to verify

The original hypothesis was:

1. Post-tool hook
2. Assistant text generation using system and style instructions
3. `MessageDisplay` hook
4. Message display
5. Stop hook

Do not treat this sequence as current truth without a runtime probe or official
source.

Possible `MessageDisplay` research:

- Validate references against a schema.
- Check PR, GitHub-issue, and file references for clickability and context.
- Determine where structured outputs help.
- Anthropic structured outputs:
  <https://platform.claude.com/docs/en/build-with-claude/structured-outputs>

## Git, GitHub, and review backlog

- Keep PRs atomic and independently mergeable.
- Decide by change type whether code, tests, design, and test plans should land
  together.
- Define the phases of review and the evidence each phase supplies.
- Determine how GitHub Actions-based review with Codex actually behaves.
- Build or adopt a GitHub-issue tool only if it can inspect issues, return
  structured data, and fit the admitting-agent model.
- Remember that review trailers may not appear in `gh pr view --json reviews`.
- Use the repository's real review-status mechanism or inspect pinned review
  comments.
- Review the design and behavior of automatic mutual-review routing.
- Investigate repeated postal injection when the sender is not reply-capable.
- Prefer an existing supported communications API where the work is already
  tracked.

## Wiki and memory backlog

- Move durable, current design material into the wiki at the proper lifecycle
  transition.
- Link wiki pages to associated skill definitions when that relationship is
  useful.
- Maintain an architecture overview.
- Give every major system a useful overview, including any agent-organization
  system that actually exists.
- A possible organizing ideal is one system, one accountable steward, and one
  current overview; do not turn that ideal into exclusive control.
- Link system overviews to design, test plan, implementation, and evidence.
- Record project-specific technical concepts in the appropriate overview.
- Distinguish organizational rules from artifact-specific rules.
- Review and dispose of accumulated tasks and memories instead of allowing a
  permanent junk drawer.
- Decide whether a memory should point to one general page or a specific system
  page based on retrieval usefulness.

## Research and source notes

The links below were present in the original notes or added during the review.
Their purpose and limitations are recorded so inclusion cannot be mistaken for
endorsement.

### Official and primary sources to keep

#### Claude Agent SDK Python reference

<https://code.claude.com/docs/en/agent-sdk/python>

- **Use:** exact supported Python classes, functions, hooks, permissions,
  interruption, session APIs, and custom tools.
- **Why retained:** primary implementation source.
- **Limit:** an API reference is not the best conceptual introduction and does
  not prove that a proposed architecture is wise.

#### Claude Code tools reference

<https://code.claude.com/docs/en/tools-reference>

- **Use:** verify current built-in tools, permissions, and hook matching before
  recreating capabilities.
- **Why retained:** primary runtime documentation and high priority for
  avoiding duplicate infrastructure.
- **Limit:** supported features still need a controlled test in the installed
  version.

#### Anthropic memory tool

<https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool>

- **Use:** study client-controlled storage, path isolation, explicit failures,
  compaction integration, and multi-session recovery.
- **Why retained:** primary design contract for the Messages API memory tool.
- **Limit:** it is not Claude Code auto-memory or Nedlern memory. Its injected
  behavior could conflict with a required startup order.

#### Anthropic structured outputs

<https://platform.claude.com/docs/en/build-with-claude/structured-outputs>

- **Use:** schema-valid postal envelopes, review findings, issue packages,
  article metadata, publishing packages, and status events.
- **Why retained:** authoritative schema/tool-input behavior.
- **Limit:** schema validity proves shape, not truth or completeness.

### Community sources retained for a narrow purpose

#### Addy Osmani agent-skills guidance

<https://github.com/addyosmani/agent-skills/blob/main/skills/using-agent-skills/SKILL.md>

- **Use:** examples of task-to-skill routing, surfaced assumptions, scope
  control, and concrete disagreement.
- **Why retained:** thoughtful work from a respected practitioner.
- **Limit:** do not adopt its instruction to stop for every ambiguity; safe
  assumptions should often permit progress.

#### Learn Claude Code

<https://github.com/shareAI-lab/learn-claude-code>

- **Use:** runnable progressive lessons about the agent loop, permissions,
  hooks, skills, compaction, memory, errors, tasks, teams, worktrees, and MCP.
- **Why retained:** the strongest community learning source in the original
  list for a ground-up system.
- **Limit:** explicitly educational and simplified; not production doctrine.

#### Claude Code Agent Monitor

<https://github.com/hoangsonww/Claude-Code-Agent-Monitor>

- **Use:** compare status, waiting, interruption, cost, hooks, SQLite,
  WebSockets, and UI ideas with NedsChorus requirements.
- **Why retained:** directly relevant prototype.
- **Limit:** some states are inferred; installation changes hooks and adds
  another service. Study before considering adoption.

#### Post-leak insights collection

<https://github.com/nblintao/awesome-claude-code-postleak-insights>

- **Use:** discover analyses and formulate hypotheses.
- **Why retained:** useful secondary index.
- **Limit:** not primary evidence; verify claims officially or experimentally.

#### Awesome Claude Code Toolkit

<https://github.com/rohitg00/awesome-claude-code-toolkit>

- **Use:** discovery only.
- **Why retained:** may surface a candidate worth inspecting independently.
- **Limit:** never install wholesale or treat inclusion as a quality/security
  signal; avoid uninspected `curl | bash` installation.

### Prompt and internal-behavior research

#### Piebald Claude Code system prompts

<https://github.com/Piebald-AI/claude-code-system-prompts>

- **Use:** compare extracted prompts and built-in tool descriptions across
  exact Claude Code versions.
- **Why retained:** best focused non-official source found for prompt diffs and
  version archaeology.
- **Limit:** incomplete where prompts are dynamically assembled; not a
  supported API contract or executable dependency.

#### Asgeirtj cross-vendor prompt archive

<https://github.com/asgeirtj/system_prompts_leaks/tree/main/Anthropic/raw>

- **Use:** historical and cross-vendor comparison.
- **Why retained:** broader comparison than a Claude-only extraction.
- **Limit:** provenance varies by file. Record model, surface, date, extraction
  method, and confidence for every derived claim.

#### Zep reverse-engineered Claude prompts

<https://github.com/zep-us/claude-system-prompt>

- **Disposition:** archive only.
- **Possible use:** prompt-extraction/security case study.
- **Why weak:** model-elicited content may contain generated errors, is stale,
  and is partly about `claude.ai` rather than current Claude Code.

#### Raw Claude Code mirrors

- (two mirror URLs omitted from this public copy — see the admission note; they remain in the private research trail)

- **Disposition:** retain only in this private research trail so the original
  links are not lost.
- **Why excluded:** apparently duplicative stale leaked-source archives with
  provenance, copyright, security, and supply-chain concerns.
- **Do not:** clone, execute, install, depend on, or cite in public NedsChorus
  material.

### JSONL references and tools

#### Claude-dev.tools JSONL guide

<https://claude-dev.tools/docs/jsonl-format>

- **Use:** human orientation and practical `jq` examples.
- **Why retained:** concise field guide.
- **Limit:** not a formal or stable schema; prefer official session docs for
  supported behavior.

#### Simon Willison transcript converter

<https://github.com/simonw/claude-code-transcripts>

- **Use:** inspect a tested converter and its captured format assumptions.
- **Why retained:** stronger primary-project evidence than a generated
  DeepWiki summary.
- **Limit:** it implements the subset it needs, not the complete Claude Code
  schema.

The older DeepWiki page
<https://deepwiki.com/simonw/claude-code-transcripts/5.1-jsonl-format> should not
be treated as an independent source; it summarizes an older repository state.

#### WithLinda JSONL browser

<https://github.com/withLinda/claude-JSONL-browser>

- **Use:** optional local browsing/export and UI inspiration.
- **Why retained:** may help evaluate transcript usability.
- **Limit:** maintenance status and no formal releases; transcripts can contain
  secrets and private material, so review code and run locally only.

### Curated software-engineering sources

The detailed source-by-source assessment for planning, design, test planning,
implementation, debugging, review, and agent evaluation is in
[the engineering methods note](cops-neds-notes-2026-07-21.md). Its current
conclusions are:

- No repository-scale workflow should be imported wholesale.
- Strong exact components exist in official Anthropic and OpenAI material.
- The main missing packaged capability is a rigorous `write-test-plan` skill.
- A general artifact attack may remain part of `d-review` unless real use
  proves that it deserves a separate skill.
- External TDD and debugging skills contain useful evidence loops but also
  overbroad or destructive doctrine that should not be copied.

## Unresolved high-level questions

- Which small subset of candidate engineering skills belongs in the initial
  NedsChorus boot set?
- Which Nedlern behaviors are genuine compatibility requirements, intentional
  changes, old defects, or unresolved?
- Which ideas in this backlog should eventually become public, and which
  internal/security research links should be omitted from public artifacts?
- What is the first bounded NedsChorus task that can test the chosen skills and
  workflow without importing an entire predecessor subsystem?

These questions should be resolved through bounded work, evidence, and Ned's
review—not by expanding this capture document into a master implementation
plan.
