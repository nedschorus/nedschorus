Issue: https://github.com/nedschorus/nedschorus/issues/10

## Admission note (new-vp, 2026-07-22)

- Boss-directed capture artifact, cops-reconstructed 2026-07-22 from the 2026-07-21 discussion and Ned's Google-Doc notes (the cleaned version had remained in chat); admitted through the single-admitter gate as pair #10. Capture ≠ commitment: nothing here is scheduled work, and the boss's walk rules which candidates advance.
- The "Related detailed documents" links name cops-local filenames; in this repository that material is [pair #4](4-open-source-publishing-community-strategy.md) (publishing strategy) and [pair #9](9-neds-notes.md) (engineering methods).
- The 2026-07-22 admission redacted the two raw mirror URLs under "Raw Claude Code mirrors" per that subsection's own retain-privately instruction. REVERSED 2026-07-24 by the public-links ruling (walk item 14: links in this public repository are judged on usefulness and reliability only — no provenance-based quarantine): the URLs are restored below, matching pair #9's research-sources section.
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
- **Draft** means captured wording awaiting review and adoption; it is not
  doctrine. (Relabeled from "candidate" by boss ruling 2026-07-26 — a
  candidate is not a draft, and draft is the status word the artifact
  lifecycle actually uses.)
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
- Nedlern is a legacy reference and evidence source, not a template.
- Nothing crosses from Nedlern merely because it already exists.
- Useful behavior must be identified, understood, reviewed, and deliberately
  re-admitted.

### Open source and publishing

- Open-source NedsChorus (decided).
- Publishing strategy, channels, and mechanics live in
  [pair #4](4-open-source-publishing-community-strategy.md); this backlog no
  longer duplicates them.

Scrubbed 2026-07-26 (boss-ruled): the marketing and self-promotion material
formerly here — channel lists, adaptation workflow, article titles — removed
as too speculative. Recoverable from git history.

### Durable Markdown and GitHub issues

The founding work has resolved the original artifact-placement questions. The
authority is the founding plan § Project organization (the artifact-lifecycle
rule); this is the summary, updated 2026-07-26 to the ruled state:

- A request for a durable Markdown document creates an MD-GitHub-issue pair.
- Working documents live at `docs/issues/<number>-<slug>.md`.
- Permanent truth graduates to `docs/wiki/`.
- Session continuity lives under `handoff/`.
- Cross-project founding material lives under `docs/cross-project/`.
- Every artifact is either FINAL at its home or sitting in a NAMED QUEUE that
  states its destination, and every queue drains by one four-outcome process
  (promote / edit / demote / drop): `docs/wiki/queue/` for wiki-bound
  doctrine, `docs/issues/queue/` for pair-bound documents, `nc-queue/` for
  boss-requested notes awaiting their first walk, `legacy-feature-queue/` for
  consider-features outliving their slice
  ([nedschorus#24](https://github.com/nedschorus/nedschorus/issues/24) tracks
  the drain procedure).
- Draft GitHub issues carry the **`draft` label** — the issue-world's queue
  membership (renamed from `boss-review`, 2026-07-24).
- Provenance: Markdown provenance lives in git commit history; GitHub-issue
  provenance is a footer line in the body or a revision comment; frontmatter
  fields exist only where a named consumer uses them.
- Repository control is the git-gatekeeper program holding the one push
  credential — every agent invokes it directly. The single-admitting-AGENT
  concept is retired (walk item 15 ruling; the earlier line here saying "one
  admitting agent" predated it).

The original open questions about whether an artifact should be a GitHub issue,
a Markdown document, or both should not be reopened without new evidence.

### Walkthroughs and comprehensibility

Retired as a section 2026-07-26 (boss-ruled): the walk behavior is specified
by the walk-me-through skill itself — its frontmatter and code are the
documentation, and a separate prose description would only drift. Cross-runtime
scenario tests are deferred to NC step-1 (inner-walk item 2 ruling, pair #9
ledger). The bullets formerly here are recoverable from git history.

## Candidate publishing modules

Removed 2026-07-26 (boss-ruled useless): the module sketches formerly here
added nothing beyond pair #4's publishing strategy. Recoverable from git
history.

## Draft document and directory structure

Two concerns, framed by boss ruling 2026-07-27 (walk item 17 cluster 5):
**where things go** (the placement rules below), and **the many-parts
overview** — "A system with many parts needs one current overview that
links them together — its code, its MDs (design, test plan), its GHIs,
and its tests." A one-file system owes no overview; a stale overview is
worse than none.

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

Draft review mechanics:

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

## Draft engineering rules

These are draft rules — captured wording awaiting review and adoption, with
overbroad wording narrowed where the later discussion identified a problem.
(Relabeled from "candidate" by boss ruling 2026-07-26.)

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

### Draft testing practices

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

## Draft design-document standard

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

Removed 2026-07-26 (boss-ruled obsolete): the lifecycle-role sketches and
organization questions formerly here are superseded by the dynamic agent-team
model — substance and state at [pair #26](26-dynamic-agent-team-model.md)
([nedschorus#26](https://github.com/nedschorus/nedschorus/issues/26)).
Recoverable from git history.

## Communications backlog

DISPERSED 2026-07-25 (walk item 17 cluster 1, boss-ruled). Five entries were
already landed doctrine and are recorded as such: durable walkthrough
decisions (the walk-ledger rule), self-contained end-of-turn messages and
contextful recommendations (the zero-context-reader rule), no bare
issue-numbers/filenames/references (clickable handles), no fake choices
(the menu-ban), and explain-material-subtleties-completely in design
reviews. One entry cut as superseded: "maintain a concise, current
communications-fix plan" (a standing fix-plan document is the stateless-pile
class the artifact-lifecycle rule retired). The four open decisions moved to
GHIs:

- Boss-notification mechanism (popup / markdown artifact / direct message /
  other) → rides the spy design on
  [nedschorus#26](https://github.com/nedschorus/nedschorus/issues/26).
- API-vs-MCP per communication type, and agent-level vs task-level
  addressing → bridge-design inputs on
  [nedschorus#1](https://github.com/nedschorus/nedschorus/issues/1) +
  comms-bridge-spec § Open.
- Safe console text-insertion + stuck/waiting-state detection →
  [nedschorus#27](https://github.com/nedschorus/nedschorus/issues/27) (new).
- The former "minimize unnecessary console communication without removing
  required context" standing direction is RETIRED (boss-ruled 2026-07-26):
  minimize is the wrong verb. The standard is consistent CLEAR AND COMPLETE
  console communication — completeness is never traded for word count.

## Status, monitoring, and introspection backlog

DISPERSED 2026-07-25 (walk item 17 cluster 2, boss-ruled; doc-only capture
retired — docs are not attention surfaces, task-shaped items get GHIs):

- The spy's design inputs (versioned-adapter session reading; the operator
  question "which agent needs attention, and why"; candidate status fields;
  the no-large-dashboard principle) and the idle-time-as-safe-catch-up
  direction → recorded on
  [nedschorus#26](https://github.com/nedschorus/nedschorus/issues/26).
- The announce-then-idle second-wake investigation and the
  verify-supported-session-state-first step → recorded on
  [nedschorus#27](https://github.com/nedschorus/nedschorus/issues/27).
- The research bundle (recaps customizable; small introspection tools;
  denoised artifact vs raw logs; controlled-test-project tuning method;
  task-list visibility for the boss) →
  [nedschorus#28](https://github.com/nedschorus/nedschorus/issues/28) (new).

## Claude and Codex runtime research

DISPERSED 2026-07-26 (walk item 17 cluster 3, boss-ruled):

- Nine research entries — instruction-compression experiments (fresh-agent
  behavior is the measure; feeds the step-2 `CLAUDE.md` rewrite), the
  deliberate-scrub-not-repeated-squeeze method, instruction-file precedence
  conflicts, the output-styles investigation (a worker-customization lever for
  [pair #26](26-dynamic-agent-team-model.md)), context clearing and backward
  resumption, recovery of messages lost to backward resumption, the small
  conflicting-names reviewer candidate, memory-maintenance tooling, and
  memory-entries-pointing-at-exact-wiki-pages — moved to the runtime-behavior
  research bundle, [nedschorus#29](https://github.com/nedschorus/nedschorus/issues/29).
- The bad-words entry's two unknowns (production source; fixture change
  observed without restart) → appended to
  [nedschorus#14](https://github.com/nedschorus/nedschorus/issues/14).
- The grep-before-naming line rides the bundle to the step-2 `CLAUDE.md`
  rewrite as a one-line write-time discipline (its explicit-name half is
  already legacy doctrine; the grep-first half was written nowhere).
- CUT (boss-ruled 2026-07-26): the "Claude demotion / why 10" entry — nobody,
  the boss included, could say what it refers to. It returns only if it
  resurfaces with a real trigger.

## Ways to run prompts in code

Removed 2026-07-26 (boss-ruled: a bad summary, useless). Recoverable from git
history.

## Turn and hook order to verify

Removed 2026-07-26 (boss-ruled: another bad summary of documentation).
Recoverable from git history. This shrinks walk item 17 cluster 6.

## Git, GitHub, and review backlog

DISPERSED 2026-07-27 (walk item 17 cluster 4, boss-ruled per entry; marks in
place below). Net result: two sentences captured (the one-coherent-change-set
workflow rule on [nedschorus#3](https://github.com/nedschorus/nedschorus/issues/3);
the reply-incapable-sender terminal-state requirement on
[nedschorus#1](https://github.com/nedschorus/nedschorus/issues/1)); one entry
answered directly by ruling (check-in composition — lifecycle bundling is
unrealistic); three recognized as already ruled or landed; four cut. The
recurring deferral trigger across this cluster: review machinery questions
wake when the boss gates an artifact class (the item-15 grow-back trigger).

- Keep PRs atomic and independently mergeable.
  — processed 2026-07-27 → sentence on
  [nedschorus#3](https://github.com/nedschorus/nedschorus/issues/3): the
  gatekeeper's CLAUDE.md workflow lines teach one coherent change set per
  check-in (NC has no pull requests).
- Decide by change type whether code, tests, design, and test plans should be checked
  in together.
  — processed 2026-07-27 → answered by boss ruling: the premise is
  unrealistic — a lifecycle's artifacts arrive at different phases and are
  never bundled. Artifacts check in when produced
  ([nedschorus#25](https://github.com/nedschorus/nedschorus/issues/25));
  within one phase the one-coherent-change-set rule governs, and a code
  change's coherent set includes the tests that pin it. No new capture.
- Define the phases of review and the evidence each phase supplies.
  — processed 2026-07-27 → already ruled (item 15 simplicity cut): no
  review-evidence machinery until the boss gates an artifact class; the
  gatekeeper spec's cut table carries the row and its grow-back trigger.
  Nothing filed.
- Determine how GitHub Actions-based review with Codex actually behaves.
  — processed 2026-07-27 → CUT: its only consumer is a review system, which
  NC defers until the boss gates an artifact class (the item-15 grow-back
  trigger). The question re-arises with that trigger; the legacy mechanism's
  behavior stays recoverable from its workflow files and wiki in git
  history. Nothing filed.
- Build or adopt a GitHub-issue tool only if it can inspect issues, return
  structured data, and fit the admitting-agent model.
  — processed 2026-07-27 → CUT: the admitting-agent model is retired
  (item-15 gatekeeper ruling), no such tool is proposed, `gh` already
  returns structured JSON, and adopt-on-demonstrated-need is standing
  simplicity doctrine. Nothing filed.
- Remember that review trailers may not appear in `gh pr view --json reviews`.
  — processed 2026-07-27 → landed legacy doctrine (trailer mechanics + the
  review-status tooling exist because of it); moot for NC until the
  gate-a-class trigger, where the lesson rides the legacy documentation.
  Nothing filed.
- Use the repository's real review-status mechanism or inspect pinned review
  comments.
  — processed 2026-07-27 → landed legacy doctrine (the interim control:
  measure with the merge gate, never a proxy); moot for NC until the
  gate-a-class trigger. Nothing filed.
- Review the design and behavior of automatic mutual-review routing.
  — processed 2026-07-27 → CUT: the legacy routers' real defect (author
  exclusion keyed on laundered worktree identity) is already recorded in
  the legacy repair queue, and nedlern is decommissioning; NC routing
  presupposes a review system and defers to the gate-a-class trigger.
  Nothing filed.
- Investigate repeated postal injection when the sender is not reply-capable.
  — processed 2026-07-27 → sentence on
  [nedschorus#1](https://github.com/nedschorus/nedschorus/issues/1): the
  bridge design must give every message a recipient-reachable terminal
  state even when the sender is reply-incapable; the legacy repeated
  injection is the motivating defect.
- Prefer an existing supported communications API where the work is already
  tracked.
  — processed 2026-07-27 → CUT (boss-ruled): a truism — all it says is "if
  it ain't broke don't fix it"; not a useful design input. Nothing filed.

## Wiki and memory backlog

- Move durable, current design material into the wiki at the proper lifecycle
  transition.
  — processed 2026-07-27 → landed: the artifact-lifecycle rule's promote
  path (wiki-bound doctrine queues in docs/wiki/queue/; the drain's
  git-mv promote IS the transition), with entry gated by the boss's
  review ruling and the step-3 wiki walk. Nothing filed.
- Link wiki pages to associated skill definitions when that relationship is
  useful.
  — processed 2026-07-27 → CUT: a page-linking standard for a wiki that
  barely exists; re-arises at the step-3 wiki walk where NC page standards
  get set under the boss's review (legacy precedent: implementation-
  reference tables). Nothing filed.
- Maintain an architecture overview.
  — processed 2026-07-27 → folded into § Draft document and directory
  structure (boss's two-concern frame: placement rules + the many-parts
  overview rule). Duplicate; nothing filed. Same mark applies to the
  three sibling overview bullets below.
- Give every major system a useful overview, including any agent-organization
  system that actually exists.
  — processed 2026-07-27 → folded (see the mark above).
- A possible organizing ideal is one system, one accountable steward, and one
  current overview; do not turn that ideal into exclusive control.
- Link system overviews to design, test plan, implementation, and evidence.
  — processed 2026-07-27 → folded (see the mark on the first overview
  bullet above).
- Record project-specific technical concepts in the appropriate overview.
  — processed 2026-07-27 → folded (see the mark on the first overview
  bullet above).
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

- <https://github.com/DonutShinobu/claude-code-fork>
- <https://github.com/tanbiralam/claude-code>

- **Disposition:** duplicate, stale snapshots of the same material —
  superseded by Piebald's versioned archive for nearly all purposes; kept for
  the research trail. (URLs restored to this public copy 2026-07-24 under the
  public-links policy, walk item 14.)
- **Limit:** stale duplicates; verify any derived claim against the versioned
  archive or experimentally.

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

- Boot set — RESOLVED 2026-07-24 (walk item 12; founding-plan open question
  8): the five founding skills only; candidates join one at a time when a
  real task exposes the missing decision (first expected pull:
  write-test-plan, nedschorus#18).
- Legacy behaviors — RESOLVED 2026-07-24 (walk item 13, the rewrite policy;
  founding plan § Standing decisions): per-cherry-pick four-class feature
  classification (preserve-feature / update-feature / remove-feature /
  consider-feature); records in the slice plan or entry-manifest line;
  undecided features to `legacy-feature-queue/`; unexamined is never
  preserved.
- Public-vs-internal links — RESOLVED 2026-07-24 (walk item 14, the
  public-links policy): links are judged on usefulness and reliability only;
  nothing is omitted from public artifacts on provenance grounds.
- First bounded task — RESOLVED 2026-07-25 (walk item 15): the
  git-gatekeeper build slice (git-gatekeeper-design.md § Build slice), boot
  test first. Bounded, code-heavy, tests the founding skills and workflow end
  to end, imports no predecessor subsystem (the gatekeeper is authored
  natively; legacy contact is read-only reference under the rewrite policy).

These questions should be resolved through bounded work, evidence, and Ned's
review—not by expanding this capture document into a master implementation
plan.
