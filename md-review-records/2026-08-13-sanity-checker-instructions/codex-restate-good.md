<!-- provenance: runtime=codex model=gpt-5.6-sol effort=xhigh cell=restate tier=good target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/agents/sanity-checker-instructions.md -->

# `sanity-checker` — seat instructions

1. The responsibility assigned to this seat—called its “pile”—is to examine how the project conducts reviews and to judge how effective that review process is.
2. More specifically, this responsibility covers the sanity-checker reviewer itself, the multi-cell or multi-reviewer `md-review` grid that sanity-checker might become part of, and the skill-level rules controlling how review results are presented or handed over.
3. Read `agent-seat-model.md` to understand what a “seat” is and how seats operate; treat the present file as the concrete assignment brief for this particular seat.

## The decision waiting on the user

1. The unresolved question is whether sanity-checker should become part of the `md-review` grid by running three separately focused adversarial review stances—“cut,” “mechanization,” and “fresh-eyes”—with every stance run using both Fable and `gpt-5.6-sol` at the `xhigh` reasoning setting. I understand this as six stance/runtime combinations in total. “Cut” appears to seek things that can be removed, “mechanization” appears to seek behavior that should be enforced mechanically, and “fresh-eyes” appears to mean reviewing without relying on prior assumptions; this sentence does not define those terms more precisely.
2. The attack-split experiment was designed specifically to provide evidence for that choice, but the user has not yet made the choice, and it has remained unresolved since August 13, 2026.
3. The supporting evidence is recorded in `md-review-records/2026-08-12-attack-split-experiment/scorecard.md` and also appears in pull request 53. According to that evidence, dividing the review into separate attacks performed better than the unsplit comparison review: for gatekeeper, four of five proposed cuts that fell within the experiment’s intended scope were accepted, compared with the unsplit baseline’s best result of three accepted cuts out of six; for fast-handoff, the split review matched all seven expected findings and also produced additional findings; across eight evaluated reviewer/runtime cells, no false positive escaped without being identified as such, although this does not necessarily mean that no false positives were produced at all; and each runtime found valid cuts that the other runtime failed to find.
4. Decisions about the operating details—what the review covers, what causes it to run, the order of its parts, which models it uses, whether results arrive incrementally, and who owns the later triage—have already been discussed step by step with the user and settled. Those decisions are documented in the header of `docs/drafts/sanity-checker-prompt-draft.md`.
5. Because the project requires any change to a skill to be reviewed interactively with the user before being incorporated, the current activity should be a walkthrough of the proposed change, not an edit that applies the change.

## The un-triaged novel findings

1. The experiment produced four findings that were not included in either of the two sets of expected or ground-truth findings.
2. None of those findings has been shown to the user or assessed for validity and disposition. In addition, each finding was based on a historical archived snapshot rather than necessarily on the present repository state, so every quoted passage or factual basis used to support a finding must be checked against the current code before anyone proposes acting on it.
3. The gatekeeper specification says that, when a test suite exists, tests are supposed to run at the relevant gate step. That behavior was never activated, even though a test suite now exists, so the gatekeeper currently performs no checks.
4. There is no protective rule or mechanism preventing the gatekeeper from editing, or allowing an ordinary gated change to alter, the gatekeeper mechanism itself. The phrase “gate-edits-the-gate” does not make clear which of those closely related cases is intended.
5. One proposal is to make the component or writer responsible for producing the pinned reference also record the pin automatically, so agents do not manually type full 40-character Git commit SHAs. I take “writer-stamps-the-pin” to mean that the producing mechanism records the authoritative commit identifier itself, but the sentence does not define exactly which writer or artifact is involved.
6. Another finding concerns a “wedged-but-light” session: a session can become stalled or nonfunctional while remaining below the size or resource threshold that would cause it to be recycled, and there is no watchdog mechanism to detect that condition.
7. Findings 1 and 2 belong to the gatekeeper seat’s area, while finding 4 belongs to the fleet seat’s area. They should first be assessed for validity and usefulness in the present sanity-checker work; any that remain valid and actionable should then be handed to the corresponding specialist seats instead of being implemented by sanity-checker. The sentence does not assign finding 3 to a seat, and “them” may refer only to findings 1, 2, and 4 rather than to all four findings.

## Background you will need

1. `docs/drafts/sanity-checker-prompt-draft.md` contains the agreed sanity-checker prompt. It was reviewed again from the beginning after an earlier draft was rejected because it attempted to give the ordinary word “simple” a project-specific redefinition.
2. `md-review-records/2026-08-09-git-gatekeeper-design/subtract-cell-prompt-lessons.md` records the requirements learned from the defective first subtraction review, including the user’s exact wording about the criterion or “axis” reviewers should use.
3. The calibration procedure in that requirements record is an active prerequisite: a prospective grid seat must pass it before being used as part of the grid.
4. `md-review-records/2026-08-11-sanity-checker-prompt-draft/` contains the artifacts from the `md-review` performed on the sanity-checker prompt draft.
5. The relevant `md-review` implementation consists of the `.claude/skills/md-review/` skill files, the `scripts/md-review-grid.py` script, and the individual cells used for each runtime.
6. As of August 13, 2026, the lowest Codex model tier used by this machinery changed from Terra to Luna, with that change appearing in pull request 57. I take “floor tier” to mean the minimum or least expensive Codex tier the system permits or uses.
7. This seat is responsible for guiding pull requests 51 and 53 through their remaining review and decision process. In pull request 51, items raised during the walkthrough are proposals for the user to choose among rather than already approved changes, and `md-review` results are delivered incrementally while something called a “Monitor” oversees the process; the sentence does not define whether “Monitor” is a person, agent role, or mechanism. Pull request 53 contains the attack-split experiment.
8. Pull request 52, which applies the fast-handoff findings, is related but not directly owned by this seat; if it needs additional work, coordinate that work with the `fleet` seat.

## An unowned thread worth claiming

1. Session `29d66917`, whose recorded size is 3.67 MB and whose last activity was August 13, 2026, drafted a code-review prompt intended to improve reliability in the `~/agents/choirmaster` repository.
2. No currently running session owns that work, no handoff document mentions it, and its subject clearly falls within this seat’s responsibility for review quality.
3. The session’s transcript is stored at `~/.claude/projects/-home-nedlern-agents-choirmaster/29d66917-9767-47cb-a221-d4876d8014cd.jsonl`.
4. Before beginning any work on a code-review prompt, read that transcript, because substantial work on the same problem has already been done and should not be unknowingly recreated.

## The user’s standing bar for reviewers

1. During stage S6 of the August 10, 2026 walkthrough, the user said that merely asking someone to simplify something is as underspecified as asking them to optimize it without explaining the relevant circumstances or objective.
2. A reviewer must explicitly name the criterion, direction, or tradeoff—the “axis”—according to which it is recommending simplification or another improvement.
3. For this project, that axis has four parts: favor systems that are easier to operate over systems that are merely easier to construct; favor guarantees enforced by mechanisms over behavior that depends on agents or people being trained to remember a habit; regard a detector that has no person or system consuming and acting on its output as an ongoing cost that produces no value; and never replace a deterministic scripted behavior with behavior that depends on the probabilistic judgment or compliance of an agent.

## First action

1. First read the experiment scorecard and the header of the prompt draft; then check each of the four new findings against the repository’s current code; after that, invite the user to walk through and decide whether sanity-checker should occupy the proposed grid seat, because reaching that decision is the central purpose of this responsibility.
2. The user was previously asked whether the grid-seat walkthrough or the triage of the four findings should happen first, but did not answer. Ask the same choice again in direct language and allow the user to select the order.
