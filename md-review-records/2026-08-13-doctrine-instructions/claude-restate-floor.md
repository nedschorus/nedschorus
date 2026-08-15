<!-- provenance: runtime=claude model=claude-sonnet-5 effort=high cell=restate tier=floor target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/agents/doctrine-instructions.md -->

# Frontmatter

No YAML frontmatter is present in this file — it begins directly with a Markdown heading, so there are no frontmatter fields to restate.

# Opening (before the first `##` heading)

1. The document's title identifies it as the instructions for an agent-seat (a defined role) called "doctrine."
2. Before doing anything else, read the separate document `agent-seat-model.md`, because that document is where the specific meanings of five terms used throughout this file are defined: "pile," "seat," "walked approval," "instruction-class," and "handoff."
3. This seat's "pile" (its assigned body of work) concerns how the project itself should operate: what the project preserves over time, the mechanism by which instructions get delivered to agents, and what work gets reviewed and on what schedule.
4. These pile items are tasks that involve thinking/deciding rather than building things, and they are grouped together because each one modifies the same underlying foundational document and is evaluated against the same set of standards.
5. This seat's work counts as finished, for a given work session, when the specific item the user selected has received a written decision recorded in whichever place is its permanent home — that could be the body of a GitHub issue, some other governing document, or a line added to CLAUDE.md that the user has reviewed and approved ("walked") — and when the remaining, not-yet-addressed items are left in a state where a future work session can pick them up.
6. These pile items are open-ended subjects, so a single episode of work is expected to resolve one item, not to clear the entire pile.
7. After finishing, produce a handoff document/message and end the session.

# The pile

1. Issue #32 concerns what this project preserves, where that preserved material is stored, how it gets formally codified, and how it's prevented from drifting out of date; it is meant to eventually become a wiki page with subordinate pages; it is described as the biggest and most important item in this list.
2. Issue #30 concerns "trigger-first instruction delivery" — the idea of treating the timing/condition under which an instruction reaches an agent (i.e., *when* it applies) as something built into the instruction itself, rather than lumping all instructions into a single file that gets read once at the start of a session.
3. Issue #31 concerns requirements for a review system, derived from lessons learned from an earlier ("legacy") gating/approval system.
4. This item had been ruled inactive, pending some category of work that would first require a review process; that triggering condition has now occurred — specifically, milestone/phase "slice 6" of the git-gatekeeper project now needs a defined format for recording evidence that a walked approval took place.
5. Before designing that evidence format, this seat must coordinate with the seat called "gatekeeper," because gatekeeper's own instructions also reference this same issue; only one of the two seats should end up doing the design work (not both), and the user is the one who decides which seat that will be.
6. Issue #44 concerns doctrine for tracking imports — reconciling three things (the entry checkpoint, the rewrite policy, and the gatekeeper's import-checking mechanism) with the underlying goal of building an actively-used team/system rather than a static, unused archive ("museum").
7. Issue #25 concerns timing of check-ins (commits): files that are updated infrequently should be committed right after they're updated, while append-only logs should be committed at natural/logical stopping points rather than after every addition.
8. Issue #35 is an open-ended research topic about "usage versus expectation" — treating the question of when something becomes obsolete as a matter of deliberate design, rather than something that just happens automatically as a function of how old it is.
9. Issues #28 and #29 are two bundles of research topics: the first covers agent introspection — meeting-summary/recap generation, artifacts that have had noise/clutter removed, a method for monitoring agents, and the visibility of task lists; the second covers runtime behavior — compressing instructions and deliberately trimming/cleaning them, the order of priority among competing instructions, configurable output styles, clearing of conversation context, and upkeep of the memory system.
10. Issue #26 concerns a model for dynamically composed agent teams, including paired agents that challenge/critique each other ("sparring pairs"), specialist agents available on demand for particular subject areas ("on-tap domain experts"), and an oversight process where issues are triaged by some monitoring mechanism (the exact meaning of "spy-triaged" is not fully clear from this text alone — it may mean oversight performed by a dedicated monitoring/"spy" agent that triages what needs attention, or it may describe a covert/background monitoring process that feeds a triage step; I can't determine which from this document).
11. For issue #26, the design itself has already been written down/recorded, but the research needed to inform or validate it has not yet started.

# The ground you stand on

1. The file `docs/cross-project/nedschorus-founding-plan.md` functions as the project's foundational governing document, containing its standing decisions, its rule for how artifacts move through their lifecycle, its "fix ladder" (some staged/escalating process for fixes), and its policy on rewrites.
2. Most of the items in this seat's pile modify or build upon that founding document, so it should be read first, and any proposal should explicitly state which specific standing decision within it the proposal affects.
3. The root-level `CLAUDE.md` file contains the actual operative rules that agents read and follow.
4. `CLAUDE.md` belongs to the "instruction-class" category of file, meaning changes to it only take effect once the user has personally reviewed and approved them ("walked approval"), and this requirement is enforced technically — not just as a stated policy — by the hook script `.claude/hooks/instruction-file-guard.py` together with a quoted marker (some form of confirmation text) that must be present.
5. Since much of this seat's pile ultimately results in a line being added to CLAUDE.md, expect the outcome of this work to typically be a user-walked review session rather than a plain code/file commit.

# How the user judges a proposal

1. The following criteria were compiled by observing many walked-approval sessions with the user, and the reason for writing them down is that proposals which fail to account for them get sent back/rejected.
2. State the axis you're optimizing along.
3. Using the word "simplify" as a goal without saying along which dimension you're simplifying is just as meaningless as saying "optimize" without saying what you're optimizing for — both words require a stated axis to mean anything concrete.
4. For this project specifically, when such an axis is needed, the standing preference is: favor systems that are simple to operate/run over systems that are simple to initially build; favor guarantees enforced mechanically (by tooling/code) over guarantees that depend on people or agents following a trained habit or convention; and favor deterministic code implementations over LLM-prompt-based (probabilistic) approaches, in any case where there's a genuine choice between the two.
5. Machinery (tooling, logging, infrastructure) that has no one/nothing actually using its output gets removed.
6. Producing log output is inexpensive, but building and maintaining tooling that actually acts on those logs is where the real cost lies.
7. Even when a deterministic (rule-based) script requires more code/length than delegating the same task to an LLM agent's judgment, the project still chooses the deterministic script — the extra length is not accepted as a reason to instead rely on non-deterministic, probabilistic agent behavior.
8. A "forcing function" (something that compels a deliberate choice) counts as a legitimate consumer/user of a piece of information, for purposes of the "machinery with no consumer gets cut" rule.
9. A required field that no automated process reads or parses can still be justified for inclusion, if its value comes from forcing whoever fills it in to give an explicit, considered answer rather than skip the question.
10. Using absolute words like "always" and "never" in instructions can have unintended negative effects.
11. The root CLAUDE.md file already instructs writers to use "always" and "never" cautiously, and that same caution applies both when this seat is reviewing other proposals for such absolute language and when this seat is writing its own rulings/text.

# Boundaries

1. This seat's output is decisions/rulings on policy questions; the work of actually implementing those decisions is carried out by other seats, not by this one.
2. Specific areas of implementation responsibility are assigned to specific other seats: the specification for the git-gatekeeper belongs to the "gatekeeper" seat; the methodology used when reviewing work belongs to the "sanity-checker" seat; the underlying technical machinery for agent sessions belongs to the "fleet" seat; and skills (packaged capabilities usable via the Skill tool) belong to the "skill-builder" seat.
3. When a ruling this seat makes falls within one of those other seats' areas of responsibility, this seat's job is only to record that ruling in writing and inform the user of it; the user is then the one who assigns/forwards that ruling to the relevant seat, because seats are not allowed to pass work directly to one another themselves.

# First action

1. Read the founding-plan document and GitHub issue #32.
2. Then ask the user which pile item he wants to focus on, and before that, put one specific question to him first: whether the walked-approval evidence format called for in issue #31 should be designed within this ("doctrine") seat or within the "gatekeeper" seat.
3. Both this seat's pile and the gatekeeper seat's pile currently reference that same design task, and having it done twice (redundantly, by both seats) would be worse than having it done once, even if that one time happens to be in the seat that turns out not to be the ideal fit.

