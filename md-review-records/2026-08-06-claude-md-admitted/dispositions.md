# Dispositions — md-review of claude-md-admitted.md (grid's first full run, 2026-08-06)

Eight cells ran clean (first complete grid run; no cell failures; Codex auth held). Restates: no confident misreadings — all four read the five lines as intended; their divergence notes match the hunts' ambiguity findings. Hunts: 48 raw findings folding to seven distinct defects. Walk order below, most important first; the user rules each.

## Walk order

1. The repository-path sentence and the "(NC)" alias — defined, never used, not searchable, false in other checkouts (all four hunts). Proposal: cut the first sentence entirely; the line opens at the legacy system.
   *ruled 2026-08-06 → CUT entirely, no replacement, on canary evidence: a cold agent in a worktree needs no main-checkout path (git resolves it; worktree mechanics training-covered, branch-exclusivity volunteered unprompted). Standing framing recorded (user, this walk): CLAUDE.md is an extension of the system prompts, not a standalone MD — every reader works in a worktree of a larger, partly-unbuilt system; behavioral canaries, not textual review, are its validation instrument. Walk re-planned five items → four (the two judgment-demand piles merge into one decline item).*
2. "NOT: write, commit, or run anything there" — "run" supports incompatible readings, one of which forbids the reading the same sentence permits (all four hunts). Proposal: reword the prohibition to name execution of legacy code.
   *ruled 2026-08-06 → approved: the line now ends "NOT: modify anything there or execute its code." Same exchange, SCOPE RULING (user, refined in the same walk): CLAUDE.md and AGENTS.md are dropped from the skill's named targets — they are system-prompt extensions validated behaviorally — but NOT excluded: a manual run on them stays available; the skill text only omits them from its example lists. This run stands as the grid's deploy validation and a record; its judgment-demand findings fall under the scope ruling.*
3. The absolutes warning's addressee — "use them cautiously" reads as write-guidance or as license to treat this file's own NOT as defeasible (three hunts). Proposal: scope it to writing instructions.
   *ruled 2026-08-06 → approved: the line now opens "When writing instructions, …"; the defeasible-reader interpretation is closed.*
*Re-plan 2026-08-06 (user: "just because naive agents are naive doesn't mean we should ignore them" — the decline-as-a-class proposal REJECTED; each remaining finding walks individually). Walk is now 11 items; 1–3 ruled above; remaining order:*

4. "Use standard SDLC terms" — no glossary or authority cited (all four hunts). User's stated lean: agents can produce a good SDLC term list with certainty; the vocabulary is in training.
   *ruled 2026-08-06 → DECLINED: the rule binds against training-supplied vocabulary — the glossary the cells demand exists in every reader; no text change.*
5. "Durable artifact" — no boundary (which outputs count: commit messages, scratch files, docs?). User's stated lean: the artifact classes can be enumerated by us.
   *ruled 2026-08-06 → approved: enumeration inline — "committed files, issue bodies, commit messages"; each class observable at write time.*
6. "Actionable without the conversation" — impossible for record-type artifacts (logs, glossaries, decision records); forces invented next steps (both good-tier hunts).
7. Naming — "parts" has no counting rule (camelCase, hyphens, extensions).
8. Naming — multi-part baseline vs the 3-or-4-parts escalation: is a 2-part name ever acceptable?
9. Naming — the check's mechanics: search scope (NC only? nedlern? ignored files?), no ambiguity test, no termination when the replacement also collides.
10. The existing-name rule taken literally forbids rename/migration tasks.
11. Scope over-breadth — "globals, functions, etc." read as covering local variables and loop indices.

## Dispositions

(marked per item as the walk proceeds)
