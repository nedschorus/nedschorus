Issue: https://github.com/nedschorus/nedschorus/issues/9

## Admission note (new-vp, 2026-07-21)

Authored by cops during the boss's skills-and-methods walkthrough, admitted verbatim below (the draft's not-yet-admitted banner replaced by this note; the tail pointer to cops's local publishing file redirected to pair #4, the admitted home of publishing decisions). Deltas from the continuing walkthrough ride this pair as REVISE dispositions. Not a legacy import — fresh authorship, no entry-manifest line.

# Ned's Notes: NedsChorus Engineering Methods and Sources


## Purpose

NedsChorus is a ground-up successor informed by six months of studying,
building, testing, and observing failures in Nedlern. Nedlern is evidence and a
legacy, not a template. Nothing should transfer merely because it already
exists.

This review is limited to software-engineering lifecycle methods that directly
help NedsChorus: defining work, planning bounded projects, technical design,
test planning, implementation, testing, review of plans/tests/code, debugging,
and necessary maintenance.

## Accepted principles

1. Prefer a few small, precise, modular skills over a comprehensive workflow.
2. A candidate must help make a concrete engineering decision or produce
   checkable evidence. General advice is insufficient.
3. Evaluate exact skills and useful methods, not repositories by reputation.
4. Prefer official sources, then maintained primary projects, then carefully
   verified community work. Prompt extractions and leaked mirrors are never
   runtime contracts or dependencies.
5. Every skill needs a narrow trigger, clear inputs and outputs, stopping and
   failure behavior, safe permissions, and a way to test whether it works.
6. Test finalists against false triggering, missing context, conflicting
   instructions, partial failure, and criteria that can pass while violating
   the intent.
7. Preserve observed lessons from Nedlern, but re-decide the mechanism for
   NedsChorus. Compatibility is not automatically desirable.

## Walk-me-through: accepted behavior

The walkthrough presents one item or subitem at a time, most important first,
and advances only when Ned asks it to continue.

### Three hundred words is a comprehension budget

Three hundred words is the maximum size of one understandable cognitive packet,
not a brevity target. Use as much of that allowance as the item needs to stand
on its own. Shorter is not better when it removes context, evidence, reasoning,
examples, distinctions, or important qualifications.

An overly compressed answer can be harder to understand than a fuller answer.
When uncertain, prefer enough relevant context for Ned to understand the point
without reconstructing unstated premises.

If an item cannot be explained adequately within 300 words, divide it into two
or more separately presented items or labeled subitems. Present only one item
or subitem per turn and pause for Ned between them.

### The document changes as the walkthrough changes the decision

A walkthrough is a working review, not merely a paginated presentation of a
fixed report. After each response, determine whether the item was accepted,
rejected, revised, or remains open. Record an actual decision, correction, or
commitment in the durable working document before advancing.

When a decision invalidates or changes later material, revise, remove, or
reorder the remaining items and tell Ned if the item count or sequence changed.
Preserve the original research as evidence, but keep the working document
aligned with the current conclusion. Questions and reactions that do not change
a decision do not require document churn.

This rule was merged for the legacy system's Claude and Codex skills in
[nedlern PR #2158](https://github.com/nedlern/nedlern/pull/2158). It must still
cross the nedschorus entry checkpoint before becoming a NedsChorus skill.

### One behavior contract, with thin runtime wrappers

Claude and Codex should not have independently rewritten definitions of a
walkthrough. Define one canonical behavioral contract covering triggering,
ordering, one independently reactable item per turn, the 300-word comprehension
budget, splitting, user-controlled advancement, decision capture, interruption
recovery, and completion.

Each runtime may have a thin wrapper for its required metadata, invocation
syntax, available tools, and narrowly evidenced runtime-specific cautions.
Require semantic parity rather than byte-for-byte identity.

Test both versions against the same scenarios: an over-compressed explanation,
a complex item requiring subitems, a material walkthrough that should not
re-derive settled rationale, a rejected or revised item, an interruption and
correct resumption, and a response that changes later items.

The NedsChorus skill should preserve this proven interaction pattern and the
decisions recorded here, but its packaging should be rebuilt and reviewed for
NedsChorus rather than copied wholesale from either legacy file.

processed 2026-07-22 → boss-ruled during the founding walk: the legacy system's two
walk skills are being updated NOW with two behaviors from this section — the
walked-document-as-ledger rule (each item's disposition marked in place before
advancing; a walk with no document gets a ledger file first) and the re-plan
rule (a ruling that changes later items revises the remaining walk and reports
the changed count or sequence) — legacy PR link to be edited in here when it
opens. The six scenario tests above are deferred to the NC step-1 walk-me
build, judged per the agent-facing test doctrine in
`nc-queue/2026-07-22-skill-creation-and-improvement-deep-dive.md` § 3.
Recorded by edit per the same-day revision convention (revise the artifact,
never stack additive records); nedschorus#12 was opened for this deferral and
closed as consolidated here.

## Working skill shortlist

These are candidates for careful review, not a boot-set decision.

### 1. `define-work`

Use only when work is ambiguous or substantial. Produce the objective,
assumptions, non-goals, scope boundaries, acceptance evidence, open questions,
and stopping condition.

Sources worth adapting:

- OpenAI [`define-goal`](https://github.com/openai/skills/blob/main/skills/.curated/define-goal/SKILL.md): the best compact official starting point for turning an intention into a bounded objective.
- Anthropic [specification interview](https://code.claude.com/docs/en/best-practices#let-claude-interview-you): useful when important requirements are genuinely missing; it should not force interviews for routine work.

### 2. `plan-rewrite-slice`

This is probably the most NedsChorus-specific candidate. Start with one bounded
end-to-end slice, not "rewrite Nedlern." Classify the legacy features the slice
touches per the rewrite policy's four classes — `preserve-feature`,
`update-feature`, `remove-feature`, `consider-feature` (boss-ruled 2026-07-24,
walk item 13, superseding the earlier MUST PRESERVE / INTENTIONAL CHANGE /
OLD BUG / UNRESOLVED set; policy of record: founding plan § Standing
decisions).

Source worth adapting:

- OpenAI [code-modernization workflow](https://developers.openai.com/cookbook/examples/codex/code_modernization): valuable because it separates current behavior, target design, parity/validation, and the executable plan. It needs stricter protection against blindly preserving old defects.

### 3. `design-change`

Read-only technical design grounded in repository evidence. Recommend one
architecture and cover boundaries, interfaces, data flow, failure behavior,
likely files, implementation order, and validation.

Sources worth adapting:

- Anthropic [`code-architect`](https://github.com/anthropics/claude-code/blob/main/plugins/feature-dev/agents/code-architect.md): the strongest direct official design-agent example found.
- OpenAI [ExecPlans](https://developers.openai.com/cookbook/articles/codex_exec_plans): useful for executable, self-contained plans, but its full form is too large for routine work and should not require explaining everything to a complete novice.

### 4. `write-test-plan`

Build this for NedsChorus. No published skill found so far is strong enough to
adopt. Its compact core should trace:

`requirement or risk -> test level -> setup -> stimulus -> observable oracle -> expected failure -> exact command -> automated or human -> justified exclusion`

Source worth studying:

- Anthropic [`pr-test-analyzer`](https://github.com/anthropics/claude-code/blob/main/plugins/pr-review-toolkit/agents/pr-test-analyzer.md): the best official rubric found, but it evaluates tests after a PR rather than designing a test plan beforehand.

### 5. `attack-artifact`

Use a fresh-context reviewer on a design, plan, or test plan. Find
contradictions, ambiguous terms, hidden dependencies, untestable claims,
missing failure modes, and criteria an implementation could satisfy while
violating the intent.

Sources worth adapting:

- Anthropic [adversarial review guidance](https://code.claude.com/docs/en/best-practices#add-an-adversarial-review-step): the best official statement of the fresh-context review pattern.
- Addy Osmani [`doubt-driven-development`](https://github.com/addyosmani/agent-skills/blob/main/skills/doubt-driven-development/SKILL.md): useful questioning discipline from a respected practitioner, but not an authority or a complete review contract.

### 6. `implement-with-evidence`

For a scoped behavior change: observe the new check fail for the intended
reason, make the smallest relevant implementation, then run the appropriate
regression checks.

Source worth extracting from:

- Superpowers [`test-driven-development`](https://github.com/obra/superpowers/blob/main/skills/test-driven-development/SKILL.md): preserves the valuable red/green evidence contract. Do not import its absolutist or potentially destructive instructions, such as deleting already-written code merely because the test was written second.

### 7. `diagnose-failure`

Preserve evidence, reproduce the failure, trace it across boundaries, state one
hypothesis, test one variable, fix the causal fault, and verify. Distinguish an
emergency mitigation from a demonstrated root-cause correction.

Sources worth adapting:

- Anthropic [context and reproduction guidance](https://code.claude.com/docs/en/best-practices#provide-specific-context-in-your-prompts): authoritative high-level direction.
- Superpowers [`systematic-debugging`](https://github.com/obra/superpowers/blob/main/skills/systematic-debugging/SKILL.md): a useful causal loop, provided it has a finite stopping condition and does not turn "root cause" into endless recursion.

### 8. `review-change`

Read-only, independent review of an exact revision. A finding needs a
demonstrable scenario, affected behavior, file/line evidence, and actionable
severity. The reviewer must be allowed to report a clean result.

Sources worth adapting:

- OpenAI [`review-agent`](https://github.com/openai/codex/blob/main/codex-rs/skills/src/assets/samples/review-agent/SKILL.md): the strongest compact official review skill found.
- Google [What to look for in a code review](https://google.github.io/eng-practices/review/reviewer/looking-for.html): a careful, durable engineering rubric from an experienced organization; use it as review criteria, not as an agent workflow.

### 9. `eval-agent-change`

Use for behavioral prompts, skills, routing, guards, and other agent changes.
Test trigger and anti-trigger cases, baseline versus candidate, real runtime
builds, regressions, and capability improvements.

Sources worth adapting or investigating:

- Anthropic [agent-evaluation method](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents): the best official conceptual source found for evaluating agents rather than merely unit-testing code.
- Anthropic [Claude Code quality postmortem](https://www.anthropic.com/engineering/april-23-postmortem): useful evidence that runtime/version coverage and separate regression metrics matter.
- Microsoft [Waza](https://github.com/microsoft/waza): worth testing as a harness because it supports skill/no-skill baselines and trigger/anti-trigger checks. Investigate the smallest useful method before adopting the platform.

## Sources retained for narrow research only

- [Piebald's versioned Claude Code prompt extraction](https://github.com/Piebald-AI/claude-code-system-prompts): the best focused non-official source found for comparing shipped Claude Code prompt and tool-description changes across versions. Use for version archaeology and hypothesis generation, never as a supported contract or executable dependency.
- [Asgeirtj's cross-vendor prompt archive](https://github.com/asgeirtj/system_prompts_leaks): useful for broad historical comparison. Provenance varies by file, so any derived claim needs the model, surface, version/date, extraction method, and confidence recorded.
- [DonutShinobu Claude Code fork](https://github.com/DonutShinobu/claude-code-fork) and [Tanbiralam Claude Code mirror](https://github.com/tanbiralam/claude-code): duplicate, stale snapshots of the same material — superseded by Piebald's versioned archive for nearly all purposes; kept for the research trail. (Reframed per the public-links policy, boss-ruled 2026-07-24, walk item 14: sources are judged on usefulness and reliability only — the earlier do-not-cite-publicly quarantine framing is retired.)

## Deliberately excluded from the shortlist

- Repository-sized "do everything" development systems.
- Anthropic's full `feature-dev` workflow as a mandatory lifecycle: too many agents and gates, although individual components may be useful.
- Superpowers `brainstorming` and `writing-plans` as universal gates: too ceremonial and too granular for ordinary work.
- Superpowers TDD unchanged: the evidence loop is valuable; the absolutism is not.
- GitHub Awesome Copilot's large breakdown and council playbooks.
- OpenAI Codex's internal all-reviewer orchestration as a default.
- Automatic four-agent simplification passes.
- Numeric quality ratings and arbitrary file-count or line-count thresholds.
- Generic "awesome" lists as recommendations. They are discovery indexes only.

## Still under review

- Boot set — RESOLVED 2026-07-24 (walk item 12, founding-plan open question 8,
  commit fa54e52): the five founding skills only; candidates join one at a
  time when a real task exposes the missing decision (first expected pull:
  write-test-plan, nedschorus#18).
- Rewrite policy — RESOLVED 2026-07-24 (walk item 13; founding-plan open
  question 9; policy of record: founding plan § Standing decisions):
  per-cherry-pick four-class feature classification (preserve-feature /
  update-feature / remove-feature / consider-feature), records in the slice
  plan or entry-manifest line, undecided features to `legacy-feature-queue/`,
  unexamined never preserved.
- Public-vs-internal — RESOLVED 2026-07-24 (walk item 14): the note is public
  as committed, nothing omitted. Links are judged on usefulness and
  reliability only (public-links policy, founding plan § Standing decisions);
  the leaked-source archives stay, treated like every other source.

## Combined walk ledger (pairs #9 + #10) — the walk-state of record

Per the walked-document-as-ledger rule (boss-approved 2026-07-22; legacy PR
[nedlern/nedlern#2162](https://github.com/nedlern/nedlern/pull/2162)). The
anchor after any interruption is the first unmarked item.

Stack state: an INNER walk ("marking conventions and skill-creation") sat on
top of this outer walk — now COMPLETE and popped. Inner item 1 (marking/archive
conventions) — processed 2026-07-21/22 → folded (mark-in-place, nc-queue
archive convention, pair-doc close lifecycle). Inner item 2 (walk-me-through:
update now vs NC step-1) — processed 2026-07-22 → ruled NOW; landed as legacy
PR [nedlern/nedlern#2162](https://github.com/nedlern/nedlern/pull/2162);
scenario tests deferred to NC step-1 (see the processed mark above). Inner
item 3 (criteria-page home) — processed 2026-07-23 → ruled: NO separate page;
this pair's walk-behavior section IS the rulebook's home (substance here,
state on open GHI #9), graduating only at pair close; ruled together with the
three-state artifact rule (queue-MD needs no GHI / pending state gets a GHI /
bare MD only for landed reference), folded to founding plan § Project
organization and [nedschorus#13](https://github.com/nedschorus/nedschorus/issues/13).
THE ANCHOR is now OUTER ITEM 2 (`define-work`); walk inputs: the two candidate-skill
queue notes plus cops's delta packet when it lands.

Outer walk, 17 items:

1. Foundations — processed 2026-07-22 → the seven principles are search
   scaffolding or duplicate doctrine EXCEPT 5 (skill interface contract) and 6
   (five adversarial test classes), which are scoped, not retired: they bind
   agent-facing skills and the agent-side halves of boss-facing skills;
   boss-supervised interaction behavior iterates live. Not landed as doctrine —
   the material rides the skill-creation deep-dive queue note into item 11.
2. `define-work` — processed 2026-07-24 → boss ruled GHI-NOT-BUILD ("at best
   it's worth a GHI in nc"); files with the batch below. RE-PLAN (boss-directed,
   same ruling): items 3–10 collapse from full evidence presentations to
   rapid-fire summary dispositions — GHI-or-cut per item off the summaries MD
   (session ad0a3708, `/tmp/nc-candidate-skills-walk-summaries-2026-07-24.md`;
   durable evidence stays in the two nc-queue files). Approved GHIs file in
   nedschorus in one batch, each pointing at the nc-queue evidence. Filed as nedschorus#15.
3. `plan-rewrite-slice` — processed 2026-07-24 → GHI-not-build (batch approval); nedschorus#16.
4. `design-change` — processed 2026-07-24 → GHI-not-build (batch approval); nedschorus#17.
5. `write-test-plan` — processed 2026-07-24 → GHI-not-build (batch approval); nedschorus#18 — flagged likely FIRST build (cops: leading git-gatekeeper-task dogfood).
6. `attack-artifact` — processed 2026-07-24 → GHI-not-build (batch approval); nedschorus#19, framed as the d-review comparison question.
7. `implement-with-evidence` — processed 2026-07-24 → GHI-not-build (batch approval); nedschorus#20.
8. `diagnose-failure` — processed 2026-07-24 → GHI-not-build (batch approval); nedschorus#21.
9. `review-change` — processed 2026-07-24 → GHI-not-build (batch approval); nedschorus#22.
10. `eval-agent-change` — processed 2026-07-24 → GHI-not-build (batch approval); nedschorus#23.
11. Skill-creator review — processed 2026-07-24 → boss approved
    read-for-ideas-only with two landing amendments he drove: the creation
    doctrine lands NOT in the founding plan but as NC's first landed-reference
    MD, `docs/reference/skill-authoring-checklist.md` (five nuggets + cops's
    four description refinements + agent-facing test rules + the excluded
    eval-machinery's reopening trigger); the founding plan step 1 carries one
    pointer; and every candidate-skill GHI (#15-#23) carries the same pointer
    ("put the reference exactly where it's needed"). Sub-questions resolved:
    (a) explain-why default, NOT/DO reserved for training overrides;
    (b) standalone reference MD, per above; (c) description-tuning machinery
    excluded with its evidence bar recorded in the checklist.
12. Boot-set roll-up (ruling) — processed 2026-07-24 → both parts landed
    (session 23789ca5; re-presented verbatim per the handoff, boss word:
    "approved"). (a) Boot-set rule recorded: boot set = the five founding
    skills only; candidates join one at a time when a real task exposes the
    missing decision; first expected pull = write-test-plan (nedschorus#18)
    at the step-7 git-gatekeeper task. Founding-plan open question 8 RESOLVED
    (commit fa54e52); pair-#9 tracking question 1 marked resolved.
    (b) Artifact-lifecycle ruling APPROVED and executed (commit 4b20892):
    every artifact final-at-home or in a destination-rooted queue with one
    four-outcome drain (promote / edit / demote / drop). Queues created at
    docs/wiki/queue/ + docs/issues/queue/ (destination-rooted under the
    plan's ruled homes — the verbatim proposal's bare `wiki/queue/` spelling
    reconciled to `docs/wiki/queue/`); skill-authoring checklist git mv'd
    there and docs/reference/ removed; step-1 pointer + candidate GHIs
    #15–#23 re-pointed; `boss-review` renamed `draft` doctrine-wide and the
    label created on GitHub; three-state rule superseded by the
    artifact-lifecycle rule (founding plan § Project organization + #13);
    founding-plan open question 5 (gated classes) substantially resolved —
    landing-class residual stays in fast-pr-to-prod-design § Open. Drain
    procedure stays tracked on nedschorus#24 (scrub reporting runs as
    discipline until the NC handoff skill builds it). ANCHOR = item 13.
13. Rewrite policy (ruling) — processed 2026-07-24 → POLICY APPROVED
    (session 23789ca5); text of record: founding plan § Standing decisions;
    open question 9 RESOLVED. The pieces, in ruling order: (a) terminology —
    git-gatekeeper (component class: gatekeeper), legacy (never "quarry"),
    NC is not-a-rebuild (cherry-pick framing) — executed repo-wide at
    2997cc0; (b) boss-simplified classification vocabulary: preserve-feature
    (feature contract, probably not implementation; named + test-pinned) /
    update-feature (divergence recorded) / remove-feature (reason recorded;
    absorbs old-bug) / consider-feature (blocks nothing; re-decided when
    work depends on it); (c) classification is per cherry-pick, never a
    global inventory; records live in the slice plan's classification table
    or the entry-manifest line; (d) consider-features outliving their slice
    go to legacy-feature-queue/ (boss catch reversing my GHI proposal: GHIs
    are for things WANTED; queues hold the not-yet-decided) — one file per
    feature, date-in-filename, standard four-outcome drain where deciding IS
    the drain, no TTL; (e) default: unexamined is never preserved.
    nedschorus#16 re-worded to the new vocabulary; shortlist §2 and
    Still-under-review updated in this doc. ANCHOR = item 14.
14. Public-links ruling — processed 2026-07-24 → boss REVERSED my quarantine
    recommendation (session 23789ca5): links in this public repository are
    judged on usefulness and reliability only; no provenance-based class
    ("treat them like everything else"). The leaked archives stay linked —
    they provide documentation and insight not offered elsewhere; unofficial
    extractions remain never-contracts (a reliability call, accepted
    principle 4). Policy recorded in founding plan § Standing decisions; the
    pair-doc research-sources bullet reframed (do-not-cite-publicly and
    copyright-concern framing retired); Still-under-review and pair question
    3 resolved: the note is public as committed, nothing omitted.
    ANCHOR = item 15.
15. First bounded test task (ruling) — IN PROGRESS 2026-07-24 (session
    23789ca5): boss expanded this item into a careful full-process design
    walk of the git-gatekeeper before confirming it as the first build task
    ("we need to specify what this python program does, its inputs and
    outputs, its state machine, errors"; mission-critical: near-perfect
    autonomous operation). Rulings already banked mid-item, to fold into
    the specification as the walk confirms them: (a) honest singleton
    restatement — branch protection restricts the ACCOUNT, not processes;
    (b) check-ins parallel by default, serialize on conflict (boss);
    (c) CLAUDE.md is documentation, never enforcement — never depend on it
    (boss verbatim: python scripts don't read it; different machines may
    carry different copies); mechanical enforcement = the dedicated
    gatekeeper-identity rung; (d) trivial head movement must not block or
    invalidate a pending check-in — revalidation scoped to what actually
    changed (boss's head-churn concern); (e) callers choose synchronous or
    asynchronous invocation — form errors always refuse synchronously at
    submit; (f) the program is the ONLY gate — every agent invokes it
    directly; choirmaster has no relay/doorman role (boss: "we came up with
    the gatekeeper concept but did not remove the old concept" — the
    single-writer-AGENT concept is retired; the single writer is the
    program + its credential); (g) request identity is a content digest
    (base + file list + content digests) computed by the program — no
    caller-generated ids; submit is idempotent and retry-safe;
    (h) the commit trailer is the SINGLE import record — the
    entry-manifest.md append-a-row rule is retired (a shared append file
    would also make any two parallel imports always conflict); the
    browsable view becomes a derived query; (i) simplicity cuts,
    boss-approved: no review-evidence field or check until a class is
    actually gated; no naming-hygiene check until a real subsystem set
    exists; no separate audit log (session transcripts + git history are
    the records — the invocation is an ordinary tool call; status = a
    history lookup on the request digest; refusals re-derive on resubmit);
    v1 parallelism = simple full-recheck retry, footprint-scoped
    revalidation deferred until checks are slow. Walk RESTARTED 2026-07-24
    with the simplified design, 6 items; anchor = sub-item 1.
    Items 16–17 unchanged behind it.
16. Agent organization / lifecycle roles (capture-only) — open.
17. Operational backlogs (capture-only) — open.

## Related working note

Publishing and community decisions are currently recorded separately in
the admitted publishing pair, [nedschorus#4](https://github.com/nedschorus/nedschorus/issues/4) (`docs/issues/4-open-source-publishing-community-strategy.md`).
They should not dilute this engineering-method shortlist.
