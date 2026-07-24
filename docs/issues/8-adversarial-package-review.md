Issue: https://github.com/nedschorus/nedschorus/issues/8

# Adversarial package review — reviewer instructions

This document is handed verbatim to each reviewer. You are a task-scoped review agent with repository access and no prior conversation history. Your deliverable comes in two rounds: questions first, then findings. The conversation stays open — you will receive answers to your questions before you conclude.

## Mission

Attack this package. Find contradictions, ambiguous terms, hidden dependencies, untestable claims, missing failure modes, and places where an implementation could satisfy the written criteria while still violating the intent.

Additionally hunt these dimensions: unvalidated assumptions; conflation of what EXISTS with what is merely planned; discipline masquerading as enforcement (a rule with no mechanism behind it); complexity the project's own earned-complexity principle does not justify; anything that grows without bound; build-order risk (a step that needs an artifact a later step produces); names that are ambiguous or hard to grep.

## The package (pinned)

Repository `github.com/nedschorus/nedschorus` at the commit named when you were launched:

- `README.md` — the charter.
- `docs/cross-project/nedschorus-founding-plan.md` — the boot-up plan and rulings register.
- `docs/cross-project/fast-handoff-design.md` — the session-handoff specification.
- `docs/cross-project/fast-pr-to-prod-design.md` — the single-writer check-in specification.
- `docs/cross-project/comms-bridge-spec.md` — the two-log coordination channel.
- `docs/issues/4-open-source-publishing-community-strategy.md` — the publishing strategy.
- `entry-manifest.md` — the import ledger (empty is its correct current state).
- Open issues #1, #2, #3, #4, #6, #7 for context on in-flight work.

## Fixed rulings — do not relitigate

The following are boss-ruled and out of scope as findings: the single-writer git-gatekeeper; the earned-complexity ladder; python-liberal/python-light; the zero-context-reader rule; the three committed homes and the ban on `docs/working/`; the legacy-with-entry-checkpoint doctrine; the two-log bridge with no message broker or mailbox substrate; the naked-drafter handoff ceremony with session-agent correction; the two-account layout (machine account sole pusher, human admin with no push path).

If you believe one of these rulings is itself defective, say so in a clearly separated section titled RULING CHALLENGE, with the failure scenario — do not weave it through ordinary findings.

The same bar applies to every `Accepted residual (boss-ruled <date>)` block you encounter inside a package document: it records an objection already raised, ruled on, and accepted, with its reasoning and a reopening trigger. Do not re-file it as an ordinary finding. Attack it only if you hold new evidence matching its stated trigger, and then only in the RULING CHALLENGE section.

## Protocol

1. Read every package document in full.
2. **Questions round:** return every question whose answer could change a finding — ambiguities, suspected missing context, apparent contradictions you want confirmed. You will receive answers in this conversation.
3. **Findings round:** deliver after your questions are answered.

## Findings format

Severity-tagged: BLOCKER (the design fails its purpose) / MAJOR (a real failure mode ships) / MINOR (friction or drift risk) / NIT. Each finding carries: the exact sentence or sentences attacked (file plus quote), the concrete failure scenario (which actor does what, and what breaks or silently degrades), and a proposed mitigation. Absences are findings too — state what is missing and why its absence bites, not only what is written wrongly.

## Per-document checklist

For each package document, report which of these it carries, which are MISSING, and whether each absence matters here: assumptions; non-goals; acceptance criteria; edge cases; observable outcomes; open questions; claims that can become automated tests; claims that require human review. A missing section is not automatically a defect — this project defers test suites to incremental build time by explicit ruling; flag an absence only where it hides risk.

## Independence

Two reviewers run this brief in parallel from different runtimes. You do not see the other reviewer's output, and yours is not shown to them until both have delivered. Do not hedge toward consensus — your value is what only you catch.
