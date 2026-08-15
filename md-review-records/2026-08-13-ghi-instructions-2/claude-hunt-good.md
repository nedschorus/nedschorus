<!-- provenance: runtime=claude model=claude-opus-5 effort=high cell=defect-hunt tier=good target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/agents/ghi-instructions.md -->

Read both files, plus `docs/agents/agent-seat-model.md` (referenced by explicit path) and verified the other referenced paths exist. The file has no YAML frontmatter.

---

**1.** `"it defines the words used here — pile, seat, walked approval, instruction-class, handoff"` (line 3)

Two of the five words are never used in this file: "walked approval" and "instruction-class" appear nowhere below line 3. The sentence is literally false as a description of this file's vocabulary. Harm: a reader who checks the seat model for these terms and finds them unused concludes either that the list is stale or that some part of this brief was deleted, and cannot tell which. It also does the opposite of the useful thing — "instruction-class" is defined in the seat model as "anything under `.claude/`", which is exactly the category `.claude/skills/ghi-write/` falls into (see finding 24), and this brief never connects them. Sure.

**2.** `"The pieces belong together because they share one doctrine — how the project decides what becomes an issue, what goes in a pair document, and what waits in a queue — and one set of design documents."` (line 5)

Contradicted by the pile's own contents. `#39 memory instrumentation` (line 26) — echoing memory reads and writes to the console, reminder hooks, no context injection — has no relation to what becomes an issue, to pair documents, or to queues. The stated cohesion rationale therefore does not cover an item this file assigns to the seat, and an agent applying the rationale as a test ("does this belong to me?") gets the wrong answer for #39. Separately, "one set of design documents" is never identified: no path, no list, no way to know which set is meant. Sure.

**3.** `"its two companion tools are designed or ruled out"` (line 7)

The section titled "The companions" lists **three** items: #41, #42, #39. The completion criterion counts two. An agent cannot tell whether one of the three is not a "companion tool" (perhaps #39, which is instrumentation rather than a tool), or whether the count is simply stale. Harm: this is a *stopping* criterion — the agent either stops one item early or cannot decide it is finished at all. Sure.

**4.** `"ghi-info has a built first slice or a written reason it should wait"` and `"each issue below carries the current state"` (line 7)

Neither says where. "A written reason it should wait" — written into the issue body, the pair document `docs/issues/46-ghi-info-agent-design.md`, a queue document, or the handoff? "Each issue below carries the current state" — carried in the issue body on GitHub, or in the pair document, or in this brief? The file elsewhere establishes a split ("Issues carry state; pair documents carry substance", line 30) which suggests the issue body, but the criterion does not say so, and the seat's own completion depends on it. Harm: an agent that writes the reason in the wrong artifact believes it is done while the artifact a future reader consults is empty. Sure.

**5.** `"Your work is done when ghi-info has a built first slice or a written reason it should wait"` (line 7) vs. `"Propose; do not start building until he rules."` (line 38)

The completion criterion requires either a built slice or a written reason to wait, but the first action forbids building until the user rules, and the file gives no instruction for the case where he does not rule — no timeout, no default, no "if he has not ruled, write the reason and stop". The waiting branch ("a written reason it should wait") is about ghi-info's readiness, not about an unanswered proposal, so an agent cannot honestly use it to exit. Harm: the seat stalls indefinitely waiting on an event it cannot observe — precisely the failure the seat model's "When a seat's work is done" section says the criteria exist to prevent. Sure.

**6.** `"Read [the seat model](agent-seat-model.md) first"` (line 3), `"Read `docs/issues/46-ghi-info-agent-design.md` first"` (line 11), and `"First action ... Read the ghi-info design and the `ghi-write` skill."` (line 38)

Three instructions each claiming primacy, and they do not agree: two different documents are each named "first", and the section actually titled "First action" lists neither the seat model nor a reading order among the three. Additionally line 20 adds a fourth ordering constraint ("read it before your first issue write"). Harm: minor for a careful agent, but the file offers no way to reconcile them, and an agent that treats line 38 as authoritative skips the seat model — the one document that defines the vocabulary line 3 says is required. Sure.

**7.** `"with the walk scaffolding deliberately stripped so it stands alone"` (line 11)

"Walk scaffolding" is undefined here and is not defined in the seat model, which defines *walked approval* and names the `walk-me-through` skill but never "scaffolding". A reader cannot tell what was stripped, what its absence implies about the design document, or whether anything needs restoring. Harm: the sentence is offered as a reason to trust the document ("so it stands alone") but rests on a term that carries no meaning for the reader, so the reassurance cannot be evaluated. Sure.

**8.** `"designed and awaiting build"` (line 11) and `"The `ghi-write` skill ... is live"` (line 20)

Both assert the current state of things that change without this file changing: an issue's status and a skill's deployment. The file's own completion criterion (line 7) says "each issue below carries the current state", i.e. state is meant to live on the issue, not in the brief. Harm: once #46 is built, or once ghi-write is revised or retired, the brief asserts something false to an agent that has no reason to doubt it and no instruction to verify it — the file never says how to check either claim. Sure that the assertions are unhedged and uncheckable from this file; unsure whether the author intends briefs to carry a state snapshot deliberately.

**9.** `"It lives on the box at `~/agents/ghi-info`, is resumed headlessly for each question, and answers on exit."` (line 13) vs. `"the ask tool does not exist yet"` (line 20)

Line 13 describes ghi-info entirely in the present indicative — lives, is resumed, answers — while line 11 says it is "awaiting build" and line 20 says the ask tool does not exist. Taken literally, line 13 tells an agent it can go run something that has not been written. Harm: an agent acting on line 13 tries to invoke ghi-info, fails, and must guess whether the failure means a broken installation or an unbuilt tool. The tense also makes the design decisions in line 13 (mirror-based answers, SSH access) read as observed facts rather than as design intent that the build must still honour. Sure.

**10.** `"~/agents/ghi-info"` (line 13)

The seat model, which this file directs the reader to as authoritative, defines `~/agents/<seat>` as the home directory of a *seat* — a git worktree on that seat's branch, created by the launcher. ghi-info is not a seat; it is a tool this seat builds. Putting it inside the seat-home namespace means the path `~/agents/ghi-info` is indistinguishable, by shape, from a seat home, and a future seat named `ghi-info` (or a launcher/worktree operation that walks `~/agents/*`, such as the retirement steps `git worktree remove ~/agents/<seat>`) would collide with or destroy it. This file neither notes the reuse nor rules it out. Sure that the namespaces overlap; unsure whether ghi-info is in fact intended to be a seat-shaped worktree, which the file does not say.

**11.** `"Its answers come from a local mirror of issue state rather than live GitHub calls"` (line 13)

A store is introduced with no location, no population mechanism, no refresh policy, and no stated behaviour for the reachable failures: the mirror missing entirely (first run), the mirror stale relative to GitHub, or the mirror containing an issue that has since been closed or edited. Since the whole value of ghi-info is answering "which issues bear on this file", answering from a silently stale mirror produces confidently wrong answers — the failure mode is invisible to the caller. Harm: the agent building the first slice has to invent all of this and will not know whether its invention matches the design document's intent. Sure the cases are unstated here; unsure whether `docs/issues/46-ghi-info-agent-design.md` settles them (the brief does not say it does).

**12.** `"a rule stated by its purpose (it should be cheap and fast to ask) rather than by prohibition"` (line 13)

Two incompatible readings. Reading A: the mirror is how it is built, and the purpose explains why — live calls are still out. Reading B: live GitHub calls are explicitly *not* forbidden, so ghi-info may make them when cheapness is not at stake (e.g. the mirror is missing, or the question is high-stakes). The sentence's construction ("rather than by prohibition") actively invites reading B, while the preceding clause ("rather than live GitHub calls") states A. Harm: the builder of the first slice must decide whether to implement a live-call fallback, and the file supports either choice — combined with finding 11, the missing-mirror case is exactly where the ambiguity bites. Sure.

**13.** `"That plan survives marked SUPERSEDED as the record of the rejected direction — read it before proposing anything gate-shaped"` (line 17)

The plan is never identified: no path, no filename, no issue number, no title. "Read it" cannot be obeyed from this file. This is not hypothetical — the checkout contains two superseded-looking drafts in this subject area, `docs/drafts/ghi-gatekeeper-plan-draft.md` and `docs/drafts/ghi-info-agent-plan-draft.md`, so an agent guessing has a real chance of reading the wrong one and drawing the wrong lesson about what was rejected. Harm: the instruction's entire purpose is to stop the agent re-deriving a settled decision, and it fails exactly when the agent is about to do that. Sure.

**14.** `"The direction was settled against a gate. An earlier plan proposed gating issue reads and writes; the user rejected it in favour of a knowledge agent."` (line 17) vs. `"The `ghi-write` skill ... governs every issue write"` (line 20) and `"Write refusals are soft."` (line 18)

The file says gating writes was rejected, then describes a live skill that governs every write and a refusal mechanism with resubmit rules. Whatever distinguishes the rejected "gate" from the accepted "governs every issue write" plus "write refusals" is never stated — possibly it is reads, possibly it is a hard block versus a soft one, possibly it is who enforces. Harm: line 17 tells the agent to recognise and avoid "anything gate-shaped", but gives it a test it cannot apply, since the currently-live machinery is itself gate-shaped by any plain reading. The agent will either propose something already rejected or refuse to touch something already accepted. Sure.

**15.** `"Write refusals are soft. A refusal's job is to make an agent look twice."` (line 18)

Never says what refuses, or what is being refused. Candidates a reader can construct from this file alone: the `ghi-write` skill refusing an issue write; ghi-info refusing a question; a hook; the user. Nor does it say whether this is existing behaviour or a design constraint for something unbuilt. Harm: this is stated as one of "two rulings to know before touching it" — that is, a constraint the agent must honour in its design work — but the agent cannot tell which component it constrains. Sure.

**16.** `"passes exactly one resubmit by writing its reasoning into a marker file"` (line 18)

The marker file has no name, no path, no format, and no lifecycle. It is also unfindable by search — "marker file" is a generic phrase, so an agent cannot grep the repository to discover the convention, which is the normal recovery from an under-specified reference and is the naming standard `CLAUDE.md` sets for invented names. Harm: the resubmit mechanism cannot be implemented or honoured from this description, and two agents implementing it independently will pick different files. Sure.

**17.** `"An agent still convinced after reconsidering passes exactly one resubmit ... There is no user-approval branch and no forced escalation."` (line 18)

A reachable case is left unstated: the second refusal. If the resubmitted write is refused again and the agent is still convinced, the file rules out both remedies it names (user approval, escalation) and describes no third outcome — not "abandon the write", not "tell the user and stop". Related unstated cases: whether the marker file is cleared after the resubmit is spent (so the *next*, unrelated write starts fresh), and what happens if a marker file is found already present. Harm: the mechanism has no defined terminal state, so an agent can loop resubmitting or can silently drop a write it believed was correct. Sure.

**18.** `"governs every issue write — filing, editing a body, commenting, promoting queue material"` (line 20)

The absolute "every issue write" is broader than the enumeration that follows and broader than the skill's own stated scope. Ordinary counterexamples the four items do not cover: closing or reopening an issue, adding or removing labels, assigning, setting a milestone, linking a PR. Each of those is unambiguously a write to a GitHub issue. Harm: an agent takes "every" literally and does not know whether closing #46 requires the skill; or it takes the enumeration as the definition and closes issues outside the governed path. The file gives no way to resolve which. Sure.

**19.** `"that fallback is the current state of the world, because the ask tool does not exist yet"` (line 20)

"The ask tool" has no antecedent. It could be ghi-info (the thing you ask), run-agent (the mechanism by which you ask it), or a distinct wrapper the skill calls. The three have different owners and different build orders, and the very next sentence — "Building it is your pile" — inherits the ambiguity, so the agent cannot tell what it has just been told to build. Harm: this sentence is the bridge between the live skill and the seat's main build; misreading it mis-scopes the first slice. Sure.

**20.** `"Building it is your pile."` (line 20)

Contradicts line 5, `"Your pile is GitHub-issue knowledge and the tooling around it"`, and the seat model's definition of a pile as "the body of related work a seat owns ... a subject area with shared context". Here "pile" is used to mean a single build task. Harm: small in isolation, but the word is load-bearing — line 38 says an ordering decision "decides the order of your whole pile", which is only meaningful under the line-5 sense. Using it both ways in one file trains the reader to read it loosely. Sure.

**21.** `"one command to invoke a Claude or Codex agent headlessly from any caller, shell or Python, either runtime"` (line 24)

Supports two readings. Reading A: callers are shell or Python; runtimes are Claude or Codex ("either runtime" restating the first clause). Reading B: "either runtime" is a third axis distinct from both, in which case what the two runtimes are is never said. Harm: the scope of #41 is a prerequisite question this brief asks the agent to rule on in its first action (finding 22), and the agent will be estimating a deliverable whose surface it cannot pin down. Unsure — reading A is the more likely intent, but the trailing phrase is redundant under it, which is what makes reading B available.

**22.** `"deciding that ordering is part of your first action"` (line 24) vs. `"Propose; do not start building until he rules."` (line 38)

Line 24 assigns the ordering decision to the agent. Line 38 explicitly withholds it: the agent reports and proposes, the user rules. These cannot both hold. Harm: an agent following line 24 decides the build order and proceeds; an agent following line 38 waits. Since this is the seat's very first action and the file says the answer "decides the order of your whole pile", the disagreement is at the point of maximum cost. Sure.

**23.** `"ghi-info is defined as headlessly invokable, so this may need to exist first"` (line 24) vs. `"its two companion tools are designed or ruled out"` (line 7)

If run-agent must exist before ghi-info can be built, then "designed or ruled out" is not a sufficient completion state for it — the completion criterion also requires ghi-info to have "a built first slice", which by line 24's own reasoning may require run-agent to be *built*, not merely designed. The file does not reconcile the two. Harm: the agent cannot tell whether finishing means shipping run-agent or only designing it, and that is a large difference in scope. Sure.

**24.** `"verifying that links resolve and that cited revision-paths exist"` (line 25)

"Revision-paths" is undefined here and appears nowhere else in this file. It could mean a path plus a git revision (`file@commit`), a path as it existed at some revision, or a path inside a revision-controlled tree. The three imply different checkers. The term is also not self-documenting enough to resolve by search from this file alone. Harm: #42's scope — what the checker must actually verify — turns on it, and the agent is asked to design or rule out that tool. Sure.

**25.** `"the designated home for the broader question of what else code can check instead of an LLM"` (line 25)

Two problems. "Designated" by whom is not stated, so the agent cannot tell whether this is a settled ruling it must honour or an author's suggestion it may revise. And the "broader question" is open-ended with no stopping point: there is no criterion for when enough of "what else code can check" has been enumerated, yet line 7 requires this companion to be "designed or ruled out" before the seat can finish. Harm: the agent either expands #42 indefinitely or declares it done arbitrarily, and the file supports neither choice over the other. Sure.

**26.** `"It serves the project's axis directly: deterministic checks beat asking a model to look."` (line 25)

"The project's axis" is undefined — not in this file, not in `CLAUDE.md`, and not in the seat model. The colon supplies a slogan but not a definition, and the definite article ("*the* project's axis") asserts that a single named thing exists which the reader is expected to already know. Harm: the phrase is used as justification for a design preference the agent is meant to apply to other decisions, and it cannot be applied when its referent is unknown. Sure.

**27.** `"echoing every memory read and write to the console"` (line 26)

"Every" is broader than achievable, and the counterexamples are ordinary rather than exotic: memories surfaced by the harness as recalled context are read without any tool call to intercept; memory files read or written by another session, another seat, or a plain editor happen outside any instrumented path; and "the console" is unidentified — a session that is not running has no console to echo to. Harm: as the scope statement for #39, it sets an acceptance bar that cannot be met, so the agent cannot tell when the item is done or whether a partial hook counts. Sure that "every" overreaches; unsure how much of the scope the linked issue narrows, since this file does not say.

**28.** `"A to-do is a task rather than a memory (user-ruled 2026-08-12)."` (line 30)

This restates a rule the checkout's `CLAUDE.md` already carries, in weaker form. `CLAUDE.md`: *"Before saving or proposing a memory, check whether it is actually a task — something to do, removed when done. If so make it a task, not a memory; memory holds durable facts and every memory write requires the user's approval."* This file: *"A to-do is a task rather than a memory (user-ruled 2026-08-12)."* The duplicate drops two things the original carries — that a task is "removed when done", and that every memory write requires the user's approval — so an agent reading only this brief gets a rule that permits unapproved memory writes for anything that is not a to-do. Harm: divergent copies of a governing rule, with the shorter copy in the document the agent reads daily. Separately, neither version names where a task lives, so "make it a task" has no executable target from this file. Sure about the duplication; the missing task store is a gap in `CLAUDE.md` too, noted only because this file repeats the instruction without supplying it.

**29.** `"comments are for genuinely new events only"` (line 30)

"Genuinely new" is a judgement with no test attached, and "only" makes it exclusive. Ordinary counterexample: someone asks a question in a comment on the issue — replying is not a new event, but editing the issue body in place is plainly the wrong response. Likewise the resubmit reasoning of line 18, which is a deliberation rather than an event. Harm: an agent applying "only" literally has no sanctioned way to respond in-thread, and an agent applying it loosely has no constraint at all; the rule as written distinguishes nothing. Sure.

**30.** `"The launcher and supervisor belong to `fleet`; if run-agent needs changes there, tell the user rather than editing those scripts"` (line 34)

Neither script is named or given a path, so "those scripts" cannot be identified from this file — an agent cannot tell whether a given file it is about to edit is one of them. (The seat model names `scripts/handoff-supervisor.py` and `scripts/launch-claude-ubuntu`, but this sentence does not point there, and the seat model is cited in this file only as the source of five vocabulary words.) Harm: the boundary is unenforceable at the moment it matters — the agent is mid-edit and has to guess whether the file in front of it is fleet's. Sure.

**31.** `"since seats cannot hand work to each other directly"` (line 34)

Stated as an impossibility, but it is a routing policy: nothing prevents this seat from committing a file, filing an issue, or writing into another seat's brief, all of which hand work over — the seat model's own wording is the narrower and accurate one ("a seat's only channel to another seat is through him"). Harm: an agent that reads "cannot" as a physical constraint may conclude a mechanism it *can* use is therefore permitted (filing an issue against fleet's scripts is not "directly" handing work), which is the opposite of the intended restraint. Unsure — the intended meaning is clear enough in context; the flag is that the word chosen states a stronger claim than the rule it encodes.

**32.** `"but `ghi-write` is yours, because it is issue machinery rather than a general skill"` (line 34)

Grants this seat ownership of `.claude/skills/ghi-write/` without mentioning the constraint that governs it. The seat model — the document line 3 sends the reader to — defines **instruction-class** as "files that tell agents how to behave: `CLAUDE.md`, `~/agents/<seat>/CLAUDE.local.md`, anything under `.claude/`. They change only with walked approval." `ghi-write` is under `.claude/`. So "yours" and "changes only with walked approval" both apply, and this file states only the first. Harm: an agent that owns the skill and is told nothing about approval edits it directly, tripping `.claude/hooks/instruction-file-guard.py` at best and bypassing a ruled-on control at worst. This is the concrete place where the unused vocabulary of finding 1 was needed. Sure.

---

clean sections: none — every section (preamble, "The main build: ghi-info", "The companions", "The doctrine you work inside", "Boundaries", "First action") carries at least one finding.

