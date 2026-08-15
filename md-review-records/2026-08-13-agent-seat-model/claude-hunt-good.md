<!-- provenance: runtime=claude model=claude-opus-5 effort=high cell=defect-hunt tier=good target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/agents/agent-seat-model.md -->

Read both files. Findings below, in document order. No YAML frontmatter is present in `agent-seat-model.md`.

---

**1. Line 3 — "Ruled by the user 2026-08-14 after a day in which parallel sessions accumulated faster than anyone tracked them."**

The date is in the future relative to the session date this review runs in (2026-08-13); the same 2026-08-14 stamp recurs at lines 32, 38, 40, and 56 ("verified 2026-08-14"). A reader who trusts these stamps will believe a ruling and a verification have already happened when the file's own containing checkout predates them. Harm: a future agent resolving a conflict between this file and an older document will use the date to decide which is newer, and will pick wrong; and "verified 2026-08-14" asserts a test result for a day that has not occurred. *Unsure* — this could be a deliberate forward-date or a project convention I cannot see from the file alone, but the whole cluster of five stamps sharing one future date is worth the author's check.

**2. Line 3 — "The per-seat briefs live beside this file as `<seat>-instructions.md`."**

"Brief" is never defined in this file, and nothing else in the file tells an agent to read its brief, when to read it, what a brief contains, or how it relates to the first-prompt file. It also sits in unresolved tension with line 55, which states the single generic first-prompt file "tells a zero-context agent everything." Harm: an arriving agent that follows only the launch mechanics in "Mechanics every seat shares" never learns that a per-seat brief exists, because that section is the one place a booting agent would look and it does not mention briefs. Conversely, an agent that reads this line does not know whether the brief supersedes, extends, or duplicates the first prompt. *Sure.*

**3. Line 12 — "**Idle agents are free.** There is no cost to a seat nobody is using, so never merge two unrelated piles to keep a seat busy."**

The absolute "no cost" is contradicted by this file's own later text. Line 38 says an idle-but-unretired seat holds `~/agents/<seat>` and a branch, that a live-but-idle stream "keeps writing handoffs," and that freeing the name requires `git worktree move`/`remove` plus an archive step. Those are real, enumerable costs: disk, a held branch, a handoff file that must later be archived, and a retirement procedure. The ordinary counterexample is exactly the `choirmaster` case at line 40 — a seat nobody was using still required an archive operation and a name-reuse decision. Harm: a reader takes "free" literally and spawns seats liberally, then discovers each one carries a mandatory teardown. *Sure.*

**4. Line 12 — "never merge two unrelated piles to keep a seat busy."**

This absolute conflicts with the `sidebar` seat defined at line 28, "the spare — off-topic questions, so they never pollute a topic seat." `sidebar` is by construction a seat holding mutually unrelated piles — that is its whole purpose. The rule as written forbids the design the same file prescribes. (Project CLAUDE.md also cautions: "absolute imperatives like 'always' or 'never' can backfire in unforeseen conditions. Use them cautiously.") Harm: an agent filing work per line 44 into `sidebar` cannot tell whether it is obeying the model or violating the grouping rule. *Sure.*

**5. Line 13 — "The natural unit of work is a *series of related tasks*, then handoff-and-clear before the next series."**

"handoff-and-clear" is an invented compound naming a procedure that this file never defines: it does not say who performs it, what "clear" clears (the session? the handoff file? the worktree?), or how it relates to the archive step at line 36 or to exiting a seat at line 18. It is also not self-documenting and would be hard to find by search, since the file's other language for the same territory is "recycle" (line 55) and "exited" (lines 18, 36). Harm: an agent told to complete a series has no executable definition of the terminating action, and cannot tell whether "clear" destroys the handoff that line 18 says must remain. *Sure.*

**6. Line 14 — "Seats are resumed weeks later, so **names must be recognisable in a session list** without opening anything."**

Two problems. First, "a session list" is an undefined artifact — the file never says what command or surface produces it (tmux? the launcher? the Claude session picker?), so an agent cannot check a proposed name against the stated criterion. Second, this states a naming constraint for future seats but gives no rule to satisfy it, while the existing names it is meant to justify (`ghi`, `fleet`, `doctrine`) are the least self-explanatory in the table. Harm: at line 44, when the user seeds a new pile, the agent proposing a name has a requirement it cannot evaluate. *Sure* on the undefined "session list"; *unsure* whether the naming-rule gap was meant to be filled by project CLAUDE.md's multi-part-name rule, which this line does not cite.

**7. Line 18 — "Seven seats are defined; **two or three run at a time**, five is the user's maximum."**

The sentence gives two incompatible limits in one breath. "Two or three run at a time" reads as a rule; "five is the user's maximum" reads as a different rule. Nothing says whether four is permitted, whether "two or three" is a description of typical practice and five the actual bound, or whether five is a hard ceiling that "two or three" narrows. Line 32 then leans on the narrow reading — "while the user is the one choosing which two or three seats run" — as load-bearing justification for having no master agent, which the five-seat maximum weakens. Harm: an agent asked to launch a fourth seat cannot decide whether to do it or to stop and ask. *Sure.*

**8. Line 18 — "A seat whose group is finished is simply exited; its name and handoff remain"** vs **line 36 — "A seat is retired by exiting it — but its **handoff file outlives it** ... So retiring a name has one required step: archive ..."**

Both sections use "exited" as the terminating action, but attach opposite consequences: here exiting is complete in itself and deliberately preserves the handoff, there exiting is retirement and carries a mandatory archive step. The file never distinguishes "finished for now, resumable" from "retired, name freed," yet the same verb triggers both. Harm: an agent finishing a group must decide whether to archive the handoff; archiving wrongly destroys the resumability line 18 promises, and not archiving wrongly leaves a stale handoff that line 36 says will boot the next agent of that name into a dead thread. *Sure.*

**9. Lines 20–28, the seat table — the names `ghi`, `fleet`, `doctrine`, `sidebar`, `gatekeeper`.**

These are one-word names for things the project will grep for. `ghi` is an unexpanded abbreviation whose meaning is only inferable from its own row, and as a search string it matches inside ordinary words. `fleet`, `doctrine`, and `sidebar` are common nouns that will match unrelated prose. Project CLAUDE.md is explicit on this point: "When creating or inventing names, for directories, file names ... and other names likely to be grepped, use explicit, clear and precise multi-part names ... If these checks return collisions or ambiguity, choose a more explicit name, with 3 or 4 parts, not 1 or 2." These names become directory names (`~/agents/<seat>`) and file names (`<seat>-instructions.md`, `<seat>-handoff.md`), so they are exactly the category the rule covers. Harm: an agent searching for material about the `doctrine` seat cannot separate hits from ordinary uses of the word. *Sure.*

**10. Line 22 — "`gatekeeper` | the credential road to activating the git-gatekeeper"**

The seat name `gatekeeper` collides with the program the project already names. Project CLAUDE.md: "the git-gatekeeper (`scripts/git-gatekeeper.py check-in` — specification: `docs/cross-project/git-gatekeeper-design.md`) is the permanent path." This file: a seat named `gatekeeper`. A search for "gatekeeper" now returns both an agent seat and a check-in program, and `~/agents/gatekeeper` reads as the program's home rather than an agent's. Separately, "the credential road" is a metaphor, not a standard SDLC term (CLAUDE.md: "Use standard SDLC terms"), and is undefined here — the file never says what the credential work is or where its remaining steps are tracked. Harm: an agent booting into the `gatekeeper` seat with only this file cannot tell what its pile actually contains. *Sure* on the collision; *sure* on the undefined "credential road."

**11. Lines 23–27 — "the sanity-checker reviewer and the md-review grid", "the candidate-skill queue and the queue-drain procedure", "preservation, instruction delivery, research"**

Every one of these is a bare reference with no path, no definition, and no pointer. "The md-review grid," "the candidate-skill queue," "the queue-drain procedure," and "preservation" are terms this file introduces and does not explain; "the sanity-checker reviewer" defines the seat in terms of its own name. Harm: this table is the only thing that tells an arriving agent what its seat owns, and for four of the seven seats it hands over a phrase the agent cannot resolve without going and asking someone — which is precisely the zero-context failure the file is written to prevent. *Sure.*

**12. Line 32 — "today's evidence is that `choirmaster`, created as a directing seat, drifted into being an ordinary topic thread."**

"Today" is a relative date in a durable document. Read a month from now, it points at nothing. Harm: a future agent evaluating whether to revisit the no-master-agent decision cannot tell how old the evidence is, which is the only thing that would make the decision worth reopening. *Sure.*

**13. Lines 30–32 and 40 — `choirmaster`'s status is left in two readings.**

Line 18 says "Seven seats are defined" and the table lists seven, none of them `choirmaster`. Line 40 then says "`choirmaster` is the live example: the founding seat's work is being redistributed into the topic seats above" — present-progressive, implying an eighth seat still exists and still holds unredistributed work — while the same sentence's second half says its handoff was archived "so a future `choirmaster` starts fresh rather than resuming a stream that no longer exists," implying it is already gone. "Live example" also collides with line 38's "A live stream keeps writing handoffs," where "live" means *currently running*. Harm: an agent that finds a `choirmaster` session or a `~/agents/choirmaster` directory cannot tell whether it is a leftover to clean up, an active eighth seat, or a name reserved for a future coordinator; and per line 38 the archive at line 40 was unsafe if the stream was still running. *Sure.*

**14. Line 36 — "archive `~/.claude/handoffs/<seat>-handoff.md` (rename it `<seat>-handoff-retired-<date>.md`, do not delete ...)"**

The mechanism has two unstated cases. The `<date>` format is never given — the file uses `2026-08-14` in prose, but an agent could as easily write `20260814` or `08-14`, and once several archives exist inconsistently they no longer sort or grep as a set. And retiring the same seat name twice on one day produces a filename that already exists; the file says "do not delete" but does not say what to do on collision, so the literal instruction (rename onto the existing path) silently destroys the earlier archive. Harm: the one artifact the procedure exists to preserve is the one it can overwrite. *Sure* on both.

**15. Line 36 — "A launch that finds no handoff starts clean on the ordinary ignition prompt, which is what a reused name should do."**

"The ordinary ignition prompt" is an undefined term appearing exactly once, and it conflicts with the launch mechanics at lines 48–55, where the first prompt is not ordinary or built in at all: it must be passed explicitly as `--first-prompt-file /home/nedlern/Projects/nedschorus/docs/agents/seat-first-prompt.md`. Either the launcher has a default prompt that lines 48–55 omit, or it does not and this sentence is wrong. "Ignition" is also a third name for the thing called "first prompt" elsewhere in the file and "boot" two clauses earlier, so a search for the concept finds only fragments. Harm: an agent relaunching a reused name does not know whether to pass `--first-prompt-file` or to rely on a default that may not exist. *Sure.*

**16. Line 38 — "supervisor", "stream", "recycle"**

Three load-bearing terms, none defined in this file: "archiving while its **supervisor** is still running," "A live **stream** keeps writing handoffs," "only clears the file until the next **recycle**." "Supervisor" recurs at lines 55 and 57 as the actor that reads the handoff; "recycle" recurs at line 55. The file never says what a supervisor is relative to the agent, what distinguishes a stream from a seat or a session, or what triggers a recycle. Harm: the safety rule here — "retire the stream first and archive second" — is un-executable, because an agent cannot perform "retire the stream" without knowing what a stream is or where its off switch lives. This is the one rule in the section whose violation the file says causes data loss. *Sure.*

**17. Line 38 — "**the agent home is a git worktree on the seat's branch**"** vs **line 56 — "The launcher creates that home as an **empty directory, not a checkout**"**

Direct contradiction as stated absolutely. Between launch and the agent's first run — and permanently, if the seat is exited before the first prompt completes — `~/agents/<seat>` is an empty directory with no worktree and no branch. Harm: the retirement procedure that follows ("via `git worktree move` or `git worktree remove`, not `rm`") is then wrong on its face: both commands fail on a path git does not know about, and the file's explicit prohibition on `rm` leaves the agent with no working option for the ordinary case of a seat launched but never used. *Sure.*

**18. Line 38 — "freeing a name for reuse also means dealing with `~/agents/<seat>` and the branch it holds, via `git worktree move` or `git worktree remove`, not `rm`."**

Three problems in one clause. (a) "Dealing with" states no completion condition — the agent is told to act but not what state ends the task. (b) No criterion is given for choosing `move` over `remove`, and the two have opposite outcomes for whether the seat's work remains checked out anywhere. (c) Taken literally the instruction cannot achieve what it claims: neither `git worktree move` nor `git worktree remove` disposes of "the branch it holds" — `remove` deletes the working tree and leaves the branch, `move` leaves both. So an agent that runs exactly what is prescribed, and stops, has not freed the branch, and the next agent of that name may collide with it. Harm: name reuse silently half-completes, and the failure only surfaces at the next launch. *Sure.*

**19. Line 44 — "or it is the seed of a seventh pile, which is a decision for the user rather than a default."**

Contradicts line 18 and the table: seven seats already exist, so a new pile is the eighth. Harm beyond the arithmetic: the phrasing is a fixed ordinal where the intent is evidently "a new pile," so the sentence will be wrong again after every seat addition, and a careful reader will instead suspect the table is missing a row or that `choirmaster` (finding 13) was meant to be excluded from the count — sending them to reconcile a discrepancy that is only a typo. *Sure.*

**20. Line 48 — "**Launch,** from the Mac, in one line" followed by a two-line command with a `\` continuation.**

Wrong when taken literally: the block shown is two lines. Harm is small on its own but compounds with finding 21 — a reader who takes "one line" seriously may retype the command without the continuation and split it into two shell invocations. *Sure.*

**21. Lines 51–52 — `~/Projects/nedschorus/scripts/launch-claude-ubuntu` run "from the Mac", with the note at line 55 that "The path is a **box-side** path, since the supervisor reads the file on the box."**

The box-side note is scoped to the `--first-prompt-file` argument only ("The path"), which leaves the script path's machine unstated by contrast — the natural reading of "from the Mac" plus a `~`-relative path is the Mac's own `~/Projects/nedschorus`. Whether `launch-claude-ubuntu` is a Mac-side wrapper that reaches the box, or a box-side script that must be reached some other way, decides whether this command works at all, and the file does not say. Harm: `~/Projects/nedschorus` exists on both machines as different clones, so the wrong reading fails confusingly rather than cleanly — or worse, runs a stale Mac-side copy of the launcher. *Sure* that the machine is ambiguous; *unsure* which reading was intended.

**22. Line 55 — "the first-prompt file tells a zero-context agent everything, including how to find out which seat it is"**

"Everything" is an absolute the file itself contradicts twice: line 3 says per-seat briefs live in separate `<seat>-instructions.md` files (finding 2), and line 57 says arrival context may additionally come from a handoff. Harm: an agent that accepts "everything" literally will not look for its brief or its handoff, which is the exact failure mode — starting a seat without its accumulated context — that the whole model is built to avoid. *Sure.*

**23. Lines 55–57 — precedence between a handoff and `--first-prompt-file` is never stated.**

Line 55: "`--first-prompt-file` seeds only the first session; after the first recycle the seat's own handoff takes over." Line 36: a launch that finds a handoff boots "straight into it." Line 57: "To seed a seat from another thread's context, pass `--first-prompt-file <path>` to the launcher, **or** copy that thread's handoff to `~/.claude/handoffs/<seat>-handoff.md` before launching." The reachable and entirely ordinary case — a handoff exists *and* `--first-prompt-file` is passed — is left undefined, yet line 57 presents the two as interchangeable ways to do the same job, which invites doing both. Harm: an agent seeding a seat cannot predict which context the new session actually receives, and the failure is silent — the session starts and looks fine while carrying the wrong history. *Sure.*

**24. Line 55 — "after the first recycle the seat's own handoff takes over."**

The mechanism assumes a handoff exists at recycle time and does not state who writes it, when, or what happens if a session ends without producing one — a reachable case, since a session can be killed, can crash, or can be exited deliberately (line 18 says a finished seat "is simply exited"). Under line 36's rule, a launch finding no handoff "starts clean," so a seat can silently lose its entire accumulated thread on the second launch. Harm: the loss is invisible until an agent resumes weeks later (line 14) and finds an empty seat. *Sure* that the case is unstated; *unsure* whether handoff-writing is meant to be covered by machinery outside this file, which the file does not say.

**25. Line 55 — "Launching is attach-or-create — running the same name again attaches to the live agent rather than starting a second one."**

Two gaps. First, the file never states the inverse operation: nothing here says how to exit or detach from a seat, yet "exited" is the central verb of both line 18 and line 36, and finding 16's "retire the stream first" depends on it. Second, in the attach case the `--first-prompt-file` argument from lines 51–52 is presumably ignored, which is unstated — a user re-running the documented one-line launch expecting a fresh seeded session instead lands in the old session with none of it applied, and gets no signal that the flag was dropped. *Sure.*

**26. Line 56 — "on its own branch — which is what keeps two seats from touching the same files or racing each other's pushes."**

The claim is broader than separate branches can deliver. Ordinary counterexamples this file itself supplies: `~/.claude/handoffs/` is shared machine-local state that every seat writes (line 38) and no branch isolates; sibling worktrees share one underlying repository, so concurrent git operations contend regardless of branch; and two seats on two branches editing the same file collide at merge, which is a deferred race rather than an absent one. Separately, the branch is never named or given a naming rule anywhere in the file, though line 38 later requires an agent to reason about "the branch it holds." Harm: an agent trusts branch separation as complete isolation and writes to shared machine-local paths without coordination. *Sure* on the isolation claim; *sure* that the branch naming is unspecified here.

**27. Line 58 — "point the new seat at the `-dialog-` extract or the raw transcript instead"**

`-dialog-` extract is undefined: the file gives no path, no filename pattern beyond a bare infix, no tool that produces one, and no statement of what it contains. "The raw transcript" is equally unlocated. Harm: this bullet exists to handle the specific case where a fork point matters, and it is the only guidance for that case — an agent that hits the case cannot act on it, and the leading-hyphen fragment `-dialog-` is close to unsearchable. *Sure.*

**28. Line 59 — "**Nothing durable lives in a session.** ... A seat can be exited at any time without loss once its work is pushed."**

The two sentences undercut each other and the surrounding section. "At any time" is immediately conditioned by "once its work is pushed," so the sentence simultaneously grants and withholds the permission. More substantively, the section's own mechanics contradict the heading claim: handoff files at `~/.claude/handoffs/<seat>-handoff.md` are durable, are explicitly "machine-local and not in git" (line 36), are never pushed, and are the thing that makes a seat resumable weeks later (line 14). So durable state does live outside the committed record, and a seat exited "without loss" by this rule can still lose its thread per finding 24. Harm: an agent reads the bold claim as license to exit or discard seats freely and loses the one artifact the model depends on. *Sure.*

---

clean sections: (none) — findings land in the untitled introduction, "The grouping rule", "How many seats exist, and how many run", "Why there is no master agent", "Retiring a seat, and reusing its name", "Filing new work", and "Mechanics every seat shares".

