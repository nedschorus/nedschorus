<!-- provenance: runtime=claude model=claude-sonnet-5 effort=high cell=defect-hunt tier=floor target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/agents/skill-builder-instructions.md -->

Note: the file changed on disk mid-review (working tree differs from HEAD — `git diff` shows an in-progress edit). I reviewed the current working-tree content, which is what's actually on disk now.

## Findings

**1. Line 5 / heading "## The queue" (line 11) / line 23 — "queue" contradicts the "pile" definition it inherits.**
> "Your pile is **the queue of proposed skills**: seven of them, each filed as an issue, plus the procedure that drains the project's queues."
> "## The queue"
> "[#24]... is the **queue-drain procedure**"

This file tells the reader (line 3) that `agent-seat-model.md` "defines the words used here," and that document defines **Pile** as: "the body of related work a seat owns. A subject area with shared context, **not an ordered queue**: the tasks in it are named by the seat's brief, not enumerated as a list to work through in order." This file then names its own pile "the queue of proposed skills," titles the item-listing section "The queue," and calls the governing issue the "queue-drain procedure" — repeatedly applying the exact word the referenced definition says does *not* describe a pile. A reader who takes the referenced definition seriously has to reconcile "not an ordered queue" with a section literally titled "The queue" containing an ordered table. Sure.

**2. Line 9 — "Your work is done when" supports two incompatible scopes.**
> "**Your work is done when** each issue below is either built and landed, ruled out with the reason recorded in the issue, or left with a stated blocker. You will not finish all seven in one series — build one, hand off, and let the next session take the next."

The completion condition is stated over "each issue below" — all seven table rows — which reads as the criterion for the whole pile being done. But the very next sentence says a single series will *not* reach that state ("you will not finish all seven in one series"), so if "your work is done when" is read as this session's stopping condition, it describes a state the agent is explicitly told it won't reach today. The paragraph never explicitly states the per-session stopping condition (e.g., "this session is done once one issue reaches one of these three states") — it only implies it via "build one, hand off." A reader has to infer which of the two readings ("your work" = the seat's total mission vs. "your work" = today's series) is intended, and the two readings conflict about what ends today's session. Unsure — the intent is recoverable, but the literal wording is genuinely ambiguous, which is the failure mode this checks for.

**3. Line 9 — "left with a stated blocker" doesn't say where the blocker must be recorded.**
> "...ruled out with the reason recorded in the issue, or left with a stated blocker."

The "ruled out" branch names a durable location ("recorded in the issue"). The "left with a stated blocker" branch names no location at all. `agent-seat-model.md`, which this file tells the reader to treat as authoritative, states as a general principle: "Nothing that matters is left only in a session. Work belongs in commits and pushes; decisions belong in the governing documents and issues" — and the handoff is explicitly machine-local and never committed. Without a stated location for "left with a stated blocker," an agent could satisfy this clause by writing the blocker only into the (uncommitted, machine-local) handoff, which the project's own durability principle treats as equivalent to not recording it at all. Unsure — plausible that "stated" was meant to imply "in the issue" by parallelism with the clause before it, but the sentence doesn't say so.

**4. Lines 5, 9, 23 — the queue-drain procedure (#24) is part of "your pile" but excluded from the stated completion criterion.**
> Line 5: "Your pile is the queue of proposed skills: seven of them... **plus the procedure that drains the project's queues**."
> Line 9: "each **issue below** is either built and landed, ruled out..., or left with a stated blocker."
> Line 23: "[#24]... **governs** how this pile is worked, so read it before picking a skill."

Line 5 states the pile has eight members: the seven skills plus #24. But the completion criterion in line 9 is scoped to "each issue below" — the table, which lists only the seven skills; #24 sits outside the table, after it. Line 23 additionally frames #24 purely as something to *read* and be *governed by*, never as something to *build, rule out, or blocker-flag*. So it's unclear whether #24 is a deliverable this seat must eventually resolve (per line 5's "plus") or purely a standing reference document (per line 23 and the line-9 criterion's silent exclusion of it) — and if it is a deliverable, no stopping point for it is ever stated anywhere in the file. Unsure — this same ambiguity exists in the source `agent-seat-model.md` row for this seat, so it may be an inherited framing rather than a fresh error, but it is still unresolved in this file.

**5. Line 23 — "wiki queue," "pair queue," and "draft-labelled issue queue" are unexplained.**
> "how the project empties its wiki queue, its pair queue, and its `draft`-labelled issue queue"

None of these three terms is defined in this file, in `agent-seat-model.md` (the one document this file names as the source of its vocabulary), or in `CLAUDE.md`. "Draft-labelled issue queue" is at least parseable (GitHub issues carrying a `draft` label). "Wiki queue" and especially "pair queue" are not self-explanatory from this file's context alone — a reader with only the declared context (CLAUDE.md, this file, and its explicit-path references) cannot tell what a "pair" is in this project or what makes something belong to the "pair queue." Sure.

**6. Line 27 — the skill-authoring checklist is referenced without a path.**
> "Find the project's **skill-authoring checklist** under `docs/` and follow it..."

Every other document this file points to is given as an explicit path or link (the seat model, the riders files, the issue URLs, the hook script, the grid script). This one instead says "under `docs/`," which is not a path — `docs/` contains many subdirectories, and the actual file lives at `docs/wiki/queue/skill-authoring-checklist.md`, nested under a `wiki/queue/` path that doesn't obviously correspond to "skill-authoring." A reader following only this file's stated references cannot locate it without an open-ended search. Sure this is inconsistent with how every other reference in the file is given; sure the file itself doesn't supply the path.

**7. Lines 29, 31, 33 — the described build sequence appears to require a second, unaddressed walked approval.**
> Line 29: "A skill is instruction-class, so it lands only through the user's walked approval, enforced by `.claude/hooks/instruction-file-guard.py`."
> Line 33: "...walk it with the user item by item, md-review the settled draft, apply what the review finds, then commit and push..."

`agent-seat-model.md` describes the walked-approval mechanism as: the `.walk-approved` marker is "consumed by **the one write it approves**" (single write, singular). The build sequence in line 33 is explicitly ordered: walk (which produces the approved write) → md-review the now-settled draft → **apply what the review finds** → commit and push. "Apply what the review finds" is necessarily a second edit to the same instruction-class file, made *after* the walked-approval marker has already been consumed by the first write — and the file states elsewhere (via the referenced instruction-class definition) that such files "change only with walked approval," with no stated exception for post-review fixes. The sequence as written doesn't say a second walk/approval happens before that edit, or that the marker is regenerated. Unsure — this depends on exactly when in the sequence the guarded "write" is understood to occur (e.g., if "draft" and "walk" both happen purely in conversation and nothing touches disk until after fixes are applied, there may be only one write after all), and the file doesn't specify that timing precisely enough to rule the conflict out.

**8. Line 31 — unclear antecedent for "which."**
> "A settled draft gets an md-review before it lands, which is `scripts/md-review-grid.py`."

"Which is `scripts/md-review-grid.py`" is grammatically closest to "it lands," but a review process being *identical to* an act of landing doesn't make sense; the intended antecedent is almost certainly "an md-review," several words earlier, across an intervening clause ("before it lands"). A reader can parse this correctly with effort, but the sentence as written supports a nonsensical literal reading. Sure this is loosely worded; unsure whether it rises to genuine misreading risk given the antecedent is recoverable from context.

clean sections: Boundaries, First action

