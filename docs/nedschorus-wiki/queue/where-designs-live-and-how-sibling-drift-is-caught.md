---
status: queued for the drain — placement ruled 2026-09-18 and 2026-09-20, the rest not decided
---

# Where designs live, and how drift between a design and its siblings is caught

## Ruled 2026-09-20: a test-design lives beside the design and the contract

The user ruled where the third document goes: **a test-design is written beside its design and its component-contract, and the three move together into the component's directory when code starts.** One rule for all three documents rather than two and an exception.

What it settles. `docs/design-to-main/design-to-main-state-machine-design.md` says the design, the component-contract and the test-design are all durable prose that land with the component, so the test-design's final home was already stated. Its home before that was not, and a search of `docs/design-to-main/` and `docs/agents/queue/design-to-main-*` for a path convention returned nothing. The gap bites because the test-design is written by the test-work-stream, after the design is approved, so its author is a different agent from the design's and needs a stated path.

A second ruling of the same walk, recorded on [Rationalize the repository layout](https://github.com/nedschorus/nedschorus/issues/224) rather than here: each system's directory carries a `docs/` subdirectory beside its `tests/`, which is where these three documents land once code starts.

Minutes: `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/where-test-designs-and-per-system-docs-live-minutes.md`.

## Ruled 2026-09-18

The user ruled where a design lives: "A design is written in its issue's GHI-MD and refined in place; design-to-main adds the component-contract beside it, and both move into the component's directory when code starts." There are no phase names for design material, and `docs/designs/queue/` is not created. This settles the placement question below, and the contradiction between the queued design-to-main agent-instructions and the designs under `docs/issues/`. Still open: a design that more than one issue cites, and how design-to-main takes an existing GHI-MD as its design instead of writing one from scratch.

Queued 2026-09-17 from a conversation between the user and the MD-skills agent-seat. The
conversation started from a finding — `docs/designs/` does not exist on main, while a landed
design names `docs/designs/queue/` as where a component's design and contract go before code —
and widened into where each document of a piece of work lives.

Queued rather than filed as an issue, because most of it is already covered and the rest is not
yet ruled.

## Already covered — do not re-file

The ask to ghi-info that preceded this note returned three issues that own most of the subject.

- **Placement.** [Rationalize the repository layout](https://github.com/nedschorus/nedschorus/issues/224)
  already carries the rule the conversation was circling: a design before code lives in
  `docs/designs/queue/` and moves into its system's directory when code starts.
- **The lifecycle from a GHI to a design.** [ghi-write follow-ups from PR #332](https://github.com/nedschorus/nedschorus/issues/345)
  already records the user's own words for it: "lengthy GHIs get turned into MDs which are the
  start of the design process." A GHI reaching its word cap is the signal that its subject became
  design work. That answers, and supersedes, the question this conversation asked as "if we start
  refining the ghi-pair MD into a design that we want to start implementing things get strange".
- **Drift between a design and its siblings.** [built-in-process-planned documents](https://github.com/nedschorus/nedschorus/issues/219)
  is the live mechanism: a design converts at first landing into a three-state pointer map —
  built, in-process, planned — with a mechanical verify step that checks whether the built items'
  paths resolve on main. It supersedes the dated `design-as-of:` claim that came from
  [Adversarial whole-package review](https://github.com/nedschorus/nedschorus/issues/8), and it
  supersedes the proposal this conversation reached independently, which was to give the existing
  `status:` frontmatter a fixed vocabulary. The pointer map is the better instrument: it is
  checked per item rather than asserted per document.

## What this conversation adds, and what is not decided

**Evidence that the drift is real, not anticipated.** Issue 142 carries three documents:
`docs/issues/142-draft-md-prompt-research-report.md`,
`docs/issues/142-draft-md-skill-design-notes.md` and
`docs/issues/142-draft-md-skill-design.md`. The research report opens by disowning itself — the
three-pass design it was written against was superseded, and the report tells the reader to read
its own table as naming cells that no longer exist. So the drift happened, was noticed, and was
handled by adding a paragraph of apology to the stale document rather than by changing a status.
That is the failure the pointer map of issue 219 is meant to prevent, and it is the concrete case
to test that mechanism against.

**A gap in when a skill is in the loop.** `/ghi-write` triggers on writes that touch a GitHub
issue — filing, editing a body, commenting, promoting queue material. Editing
`docs/issues/142-draft-md-skill-design.md` touches no issue, so no skill is invoked when a design
is written or revised, and nothing asks what else is paired to that issue number. The cheap check
that would have caught issue 142: when a design is written or revised, list `docs/issues/<n>-*`
and confirm each sibling still says something true. Whether that belongs in a widened `/ghi-write`
or elsewhere is open. This is a `/ghi-write` follow-up, so issue 345 is its likely home.

**Not decided: a design that more than one GHI cites.** The conversation agreed such a design
needs a name of its own rather than one issue's number, and agreed that collapsing several GHIs
into one to avoid the problem is the wrong trade — issue 3 is what that produces, four documents
under one number that cannot be closed independently. Nobody has written that rule down, and no
design in the tree needs it yet: eight designs exist and each serves one issue.

**Not decided: not every GHI needs a design.** Stated by the user, consistent with the tree, not
written anywhere.

**Decided 2026-09-20: where a test-design lives.** Beside its design and its
component-contract, the three moving together. See the section at the head of this note. This
note had not listed the question: the gap was found while revising the ghi-info design, when
nothing in `docs/design-to-main/` or the queued design-to-main agent-instructions turned out to
place a test-design before it lands with its component.

**A contradiction to settle at the drain, not before.**
`docs/agents/queue/design-to-main-design-writing-agent-instructions.md`, itself queued, tells its
agent that the design and the component-contract sit in `docs/designs/queue/` before code. Eight
of the tree's designs instead sit at `docs/issues/<n>-<name>-design.md`, including the one that
landed on 2026-09-17. Harmless while that node is queued; a real contradiction the day
design-to-main first runs. Whoever drains either queue should settle it rather than discover it.

**A skill that does not need writing yet.** The user asked whether a make-design or write-design
skill is wanted. `docs/agents/queue/design-to-main-design-writing-agent-instructions.md` is
already a full draft of that capability, in the form his 2026-09-06 rule prescribes — a
design-to-main node's agent-instructions rather than a skill. What is genuinely open is narrower:
whether a design written outside design-to-main reuses those instructions or needs its own route.

**Design exploration is separate from design-to-main, and the handover between them is undefined.**
The user ruled on 2026-09-17 that the decision to commit to building something stays manual and
outside the state machine: invoking design-to-main is the act of committing, and before that a
design is ordinary prose work — written by hand, cold-read, walked with the user, then merged or
dropped. Two things make that the right line, both in
`docs/design-to-main/design-to-main-state-machine-design.md`. Its unit of work is a component, "one
design, one component, one run", and early design is often asking whether there is a component at
all, or one rather than three. And its design-writing state writes the component-contract in the
same breath as the design: the queued agent-instructions at
`docs/agents/queue/design-to-main-design-writing-agent-instructions.md` tell that agent to settle
intent and, with it, "the component-contract's details — exit statuses, refusals, what a
component-consumer gets back — because those details are decisions and this is where they are
made". A contract is a commitment artifact, so the machine's first writing state already presumes
the commitment. This is not because the machine cannot abandon a design: transition row 70 takes
`stop` from `investigate-workflow` to `ended` with outcome `stopped-by-user`, a first-class outcome
beside `passed` and `failed`, and that argues against the conclusion.

The gap is the handover. When exploration concludes that the thing should be built,
design-to-main's `design-writing` agent writes the design from scratch in its own conversation, so
a hand-written, cold-read, user-walked design is either adopted by hand or written again, and
writing it again throws the exploration away. Those instructions already come close to allowing
adoption, in the redesign case: the agent receives "the investigation report with the design and
the component-contract as they stand". Making the invocation able to carry an existing design is
one sentence, not a new state. Nobody has written that sentence, and it is the sharper form of the
question the entry above leaves open.

## Also recorded here

The user said on 2026-09-17 that `docs/cross-project/` is a one-off used to bootstrap this
project and should be retired soon. Two design documents live there today. This bears on the
file naming and location standards wiki page, which currently presents that directory as a
standing home.
