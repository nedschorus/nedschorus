# draft-md skill — design notes from the 2026-08-22 rulings ([nedschorus#142](https://github.com/nedschorus/nedschorus/issues/142))

Working material for whoever builds the skill. Each section marks what the user ruled (binding) and what is open (settle at build, walked like any skill text).

## What draft-md is (ruled 2026-08-22)

The drafting stage for durable MDs, run before md-review. The name is ruled: the user prefers `draft-md` because "md-write sounds like a final product." The stages stay deliberately separate — draft-md produces the draft, md-review checks it, and the user walks near-final MDs before they land. draft-md plus md-review together are what "writing an MD" means in this project.

Boundary against the founding plan's `md-write` commission (its still-unbuilt sibling skill): md-write keeps the disposition machinery — search existing pairs, choose NEW / REVISE / REPLACE / REMOVE, route ambiguity to the draft queue — deciding *which file* text lands in. draft-md governs *how the prose is written* once there is prose to write. Open: the founding plan embedded the zero-context-reader rule in md-write's commission; under this split it belongs to draft-md — the migration is settled at whichever skill builds first.

## The register draft-md operationalizes (ruled; homes already landed)

- The CLAUDE.md drafting bullet (landed 2026-08-22): identify the question the text exists to answer; answer it as if a colleague asked — one concrete case first; keep the sentences you would say; the answer, not the question, becomes the text.
- The zero-context read before the user sees proposed text, with the revise-toward-the-restatement rule (landed in walk-me-through 2026-08-22: where the fresh reader's restatement is clearer, the draft is revised toward it).
- The project's writing bars (CLAUDE.md): standard SDLC terms, no invented vocabulary, plain precise language; short, dense text is hard to read and easy to misunderstand — never compress to fit a word count.
- No hard line wraps inside a paragraph (ruled 2026-08-22): write each paragraph as one line and let the viewer wrap it. Agents habitually hard-wrap MDs at 80–100 characters; in a rendering editor (the user edits in Typora) the embedded newlines are junk whitespace that makes the text ugly and hard to edit. Line breaks belong only where markdown means them: between paragraphs, list items, headings, code-fence lines. This document complies with its own rule.

## Scope on edits: the diff defines the governed text (ruled in direction; mechanism open)

The user's worry, verbatim in substance: applying draft-md to a whole existing file would churn paragraphs that are already vetted — walked, ruled — and a ruling silently rewritten is a ruling destroyed. The scope rule: **draft-md governs only the text being composed** — a new file's whole text, or exactly what an edit adds or changes. Untouched text is out of bounds regardless of its vetting history. A drafting agent that suspects a neighboring untouched paragraph is wrong raises it as a question (or routes it to md-review), never silently improves it. Mechanical edits — paths, dates, renames — are exempt from the register entirely.

The user's mechanism (2026-08-22): determine the governed text with a diff at **sentence or paragraph granularity, not line granularity** — prose reflows, and a line-based diff shows a rewrapped paragraph as wholly changed, which would wrongly pull vetted text into scope. Open at build: the concrete tool (git word-diff, or a small segmenting script) and whether the granularity is sentence, paragraph, or the coarser of the two per hunk. (The no-hard-wrap rule above helps here too: one-line paragraphs make paragraph-level diffs and line-level diffs coincide.)

## Existing MDs: inventory, then the standing review instrument (direction ruled; script open)

Not every existing MD was ever vetted, by human or review. The plan:

1. A vetting-evidence inventory script, git history first: this project stamps rulings into commits ("user-ruled", "user-walked"), md-review dispositions, and sanity-check records, so `git log --follow` per actionable MD scores vetting evidence cheaply. A model pass classifies only the ambiguous files; mining session transcripts (the user's jsonl idea) is the fallback for anything predating commit discipline. Output is computed on demand — no stored per-file markers to go stale.
2. The unvetted actionable MDs then go through **md-review** — the retrofit tool this project already has — findings walked to the user as usual. draft-md is never the retrofit tool; it is the composition-time register.

## Build path

Per the skill-authoring checklist (`docs/wiki/queue/skill-authoring-checklist.md`); the skill text itself gets a zero-context read and a walk before adoption. Timing user-ruled: end of the clarity-registers walk ([nedschorus#138](https://github.com/nedschorus/nedschorus/issues/138)) or soon after.
