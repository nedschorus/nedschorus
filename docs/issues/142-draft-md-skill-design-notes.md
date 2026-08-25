# draft-md skill — design notes from the 2026-08-22 rulings ([nedschorus#142](https://github.com/nedschorus/nedschorus/issues/142))

Working material for whoever builds the skill. Each section marks what the user ruled (binding) and what is open (settle at build, walked like any skill text).

## What draft-md is (ruled 2026-08-22)

The drafting stage for durable MDs, run before the cold read. The name is ruled: the user prefers `draft-md` because "md-write sounds like a final product." The stages stay deliberately separate — draft-md produces the draft, the cold read checks it, and the user walks near-final MDs before they land. draft-md plus the cold read together are what "writing an MD" means in this project.

Boundary against the founding plan's `md-write` commission (its still-unbuilt sibling skill): md-write keeps the disposition machinery — search existing pairs, choose NEW / REVISE / REPLACE / REMOVE, route ambiguity to the draft queue — deciding *which file* text lands in. draft-md governs *how the prose is written* once there is prose to write. Open: the founding plan embedded the zero-context-reader rule in md-write's commission; under this split it belongs to draft-md — the migration is settled at whichever skill builds first.

## The register draft-md operationalizes (ruled; homes already landed)

- The CLAUDE.md drafting bullet (landed 2026-08-22): identify the question the text exists to answer; answer it as if a colleague asked — one concrete case first; keep the sentences you would say; the answer, not the question, becomes the text.
- The zero-context read before the user sees proposed text, with the revise-toward-the-restatement rule (landed in walk-me-through 2026-08-22: where the fresh reader's restatement is clearer, the draft is revised toward it).
- The project's writing bars (CLAUDE.md): standard SDLC terms, no invented vocabulary, plain precise language; short, dense text is hard to read and easy to misunderstand — never compress to fit a word count.
- No hard line wraps inside a paragraph (ruled 2026-08-22): write each paragraph as one line and let the viewer wrap it. Agents habitually hard-wrap MDs at 80–100 characters; in a rendering editor (the user edits in Typora) the embedded newlines are junk whitespace that makes the text ugly and hard to edit. Line breaks belong only where markdown means them: between paragraphs, list items, headings, code-fence lines. This document complies with its own rule.

## Scope on edits: the diff defines the governed text (ruled in direction; mechanism open)

The user's worry, verbatim in substance: applying draft-md to a whole existing file would churn paragraphs that are already vetted — walked, ruled — and a ruling silently rewritten is a ruling destroyed. The scope rule: **draft-md governs only the text being composed** — a new file's whole text, or exactly what an edit adds or changes. Untouched text is out of bounds regardless of its vetting history. A drafting agent that suspects a neighboring untouched paragraph is wrong raises it as a question (or routes it to a cold read), never silently improves it. Mechanical edits — paths, dates, renames — are exempt from the register entirely.

The user's mechanism (2026-08-22): determine the governed text with a diff at **sentence or paragraph granularity, not line granularity** — prose reflows, and a line-based diff shows a rewrapped paragraph as wholly changed, which would wrongly pull vetted text into scope. The no-hard-wrap rule above makes this automatic, but only for files written under it or converted to it (user-confirmed 2026-08-22): in a compliant file one paragraph is one line, so git's ordinary line diff is a paragraph diff and the governed text falls out of `git diff` with no custom tooling; `git diff --word-diff` refines within a paragraph if the build wants sentence granularity. Existing hard-wrapped files need a one-time mechanical unwrap before their line diffs are clean — verifiably whitespace-only (collapse all whitespace in both versions; the text must be byte-identical), so it is a mechanical edit outside the register, at the cost of one whitespace commit in each file's history. Open at build: whether paragraph granularity suffices or word-diff refinement is wanted, and when the bulk unwrap runs.

## Existing MDs: inventory, then the standing review instrument (direction ruled; script open)

Not every existing MD was ever vetted, by human or review. The plan:

1. A vetting-evidence inventory script, git history first: this project stamps rulings into commits ("user-ruled", "user-walked"), cold-read dispositions, and sanity-check records, so `git log --follow` per actionable MD scores vetting evidence cheaply. A model pass classifies only the ambiguous files; mining session transcripts (the user's jsonl idea) is the fallback for anything predating commit discipline. Output is computed on demand — no stored per-file markers to go stale.
2. The unvetted actionable MDs then go through **a cold read** — the retrofit tool this project already has — findings walked to the user as usual. draft-md is never the retrofit tool; it is the composition-time register.

## Steps always emit their answer (user-ruled 2026-08-23; routed here by his instruction, relayed from the git-infra seat)

The user's words, verbatim: "Do not ask an agent to emit an answer only if true, or only if false, or only if certain tags, states or return codes. Ask agents to always emit the answer, either true or false, of at least one tag state or code. Make sure that if a no-op return code is needed, then return the no-op code. This enables the next step in the process to verify that the previous step completed its work. If sometimes returns are emitted and sometimes not, the next step can not verify if the previous step ran."

Routing, his words: "This statement really should be in the draft-md or md-write skill we've been working on in some session." Under the ruled scope split it lands in draft-md, as a bar on drafted prose that defines steps. The defect class is on record at [nedschorus PR #111](https://github.com/nedschorus/nedschorus/pull/111) (an error silenced, the result then trusted). Cautions surviving two prior zero-context reads of earlier renderings: gloss "tag" at first use; never use "code" for both a program and a status code in one breath; the matched-nothing clause is a must, not a description; terminal steps — output read by a human, no next step — are covered too. The skill-section wording is working material until walked; his verbatim statement above is the authority.

## Scrub what is not instruction (user-ruled 2026-08-23)

Three things earn a place in a durable MD: the instruction, the explanation an instruction needs to be judged rightly, and a clean example of it. Everything else is clutter a naive agent must read, check, and work around. The user's words: quoted provenance and references to when decisions were made are "extraneous clutter and just noise that has to be checked. Agents expect instructions, not references to when decisions were made."

Scrubbing is relocation, not deletion (user-ruled 2026-08-23, on his worry that cutting forward-looking material loses it): each class moves to the home that holds it better. Provenance — commit ids, issue and pull-request numbers, dates, who decided and when — moves to the commit message, the issue, and the pair document. Intentions about later work move to an issue or the queue that owns them, and are never cut without one; an intention living only in a document nobody treats as a work list is already lost, and cutting it homeless finishes the job. Historical narrative is already in git. Cross-references that force a second document to be read for no gain get resolved in place or replaced by naming that document as the authority. Only two classes are simply deleted: commentary about the document itself, and hedges that change no action.

Kept: the reason a rule exists, which is what lets an agent judge an unanticipated case — the cut is decision history, not reasons. The pattern already exists here: the audit prompts hold their rulings and recovery pointers in a maintainer header that the runner splits off, so the reviewing agent receives instruction only.

Settled 2026-08-23 by the genre-suffix ruling ([nedschorus#152](https://github.com/nedschorus/nedschorus/issues/152)): a document that only reports what happened carries a genre suffix — `-log`, `-report`, or `-capture` — which takes it out of the review path entirely, so it keeps its ruling stamps as content and draft-md never touches it. The drafting rules need no exception clause; the filename decides. This also preserves the detector those stamps feed: reviewers hunt "ruled"/"RULED" annotations to flag collisions with settled decisions instead of silently re-litigating them, and the documents carrying those stamps are exactly the ones the suffix protects.

## A referring phrase names what it refers to (user-directed 2026-08-23, relayed from the git-infra seat)

His diagnosis, verbatim: an "interesting failure mode ... sounds like a bad or ambiguous english prompt or instruction which needs to be cleaned up."

The specimen: a normative document stated that a restriction was "proven, not merely configured" — a term of art in that document separating a settings read from a demonstrated refusal — and named the restriction only as "the restriction", relying on the sentence one line above it. About six hundred words were later inserted between the two. The sentence did not change, and it silently began asserting that a different restriction, enabled after the experiment ran and never tested, had been proven by controlled test. The false claim landed on the phrase a reader trusts most, and nothing in the sentence looked wrong afterward.

The bar: a referring phrase names its referent. "The restriction", "this check", "that experiment", "the same rule" are safe only while the referent is adjacent, and adjacency does not survive editing — any later insertion moves it. The cost is asymmetric: naming costs three words, while the failure produces a confident false statement in a document others act on. This pairs with the every-step-answers bar; both concern text that cannot tell its reader when it has stopped being true. Wording is working material until walked.

## Externalities in durable prose (user-directed 2026-08-24; the genre split is open)

His words, ruling on the draft's opening paragraph: "why mention externalities - it just confuses the reviewers. This document is about what this does, not the rest of the world." Applied at once — the draft had disclaimed which file placement belongs to by naming the unbuilt `md-write` skill, and both outward references came out. The opening now reads: "This skill governs how that prose gets drafted, not where it lands." The boundary survives as a bound on this skill; the account of another component's responsibilities is gone.

The class this names has no home yet. draft-md's scrub list cuts provenance, historical narrative, document commentary, action-neutral hedges, future intentions, and unearned cross-references. None of those covers a sentence that describes what some other component is responsible for. It belongs on that list, and at composition time rather than at review, because the scrub list is already the list of what earns no place.

Open, and his question: whether the rule can be flat. His words: "that also may need to be part of a md-review or md-write that applies to designs as opposed to readme's or overviews or non designs of all sorts." It cannot be flat. A design document's subject often is the rest of the world — what it sits beside, what it replaces, which interface it consumes. An overview is almost nothing else. Instruction prose is the genre where an externality is pure noise. So the rule needs a genre to key on, and the project's genre vocabulary today is the suffix convention of [nedschorus#152](https://github.com/nedschorus/nedschorus/issues/152), which names only `-log`, `-report`, and `-capture` and is commissioned but unbuilt. Extending that vocabulary to mark designs and overviews is where the split belongs; putting the taxonomy inside draft-md would give it something it does not own, which is the same shape of defect as the reference just cut.

Not yet routed: whether this becomes an addition to nedschorus#152 or a separate issue runs through the ghi-write skill, after the draft-md review walk closes.

## Genre, and why mandatory fields exist (user-directed 2026-08-24; all three open)

Three directions from one message, recorded because each changes something the skill says.

**What the drafting register is for, and what it can skip.** His words: "if it's not intened to be read as english, we dont need it to be clear english." That is a cleaner basis for the report-genre exclusion than the draft's own. A `-log`, `-report`, or `-capture` file is read as a record, not as prose, so the discipline that makes prose clear has nothing to do for it. It reaches the same exclusion the genre-suffix ruling reached, by a reason a reader can apply to a file the suffix convention never anticipated.

**How a drafting agent learns the genre: ask, do not infer.** His words: "if the md file is intended to be a spec or design, one simple approach is to ask the user if it's intended to be a spec or design, which has more rules than just prompts or instructions or whatever. And this maybe particularly relevent to designs or specs (or some prompts or instrucitons that execute them)." This is a lighter mechanism than growing the suffix vocabulary of [nedschorus#152](https://github.com/nedschorus/nedschorus/issues/152), and the two are not exclusive: the suffix names the genre after the fact, the question settles it before drafting starts. Open: which of the two draft-md relies on, and what the larger rule set for a spec or design actually contains.

**Why tags and mandatory fields exist at all.** His words: "A lot of our tags or manditory fields are designed to enable us to use state machines, that is if X do Y, if no X do Z, or stuff like that. Understanding how state machines pervade our designs and prompts should help us not forget why we need specific fields or tags."

This is the reason underneath the steps-always-emit bar, and it is stronger than the reason the draft currently gives. The draft says an unconditional answer "lets the consumer verify the step ran at all" — true, but that is auditing. The state-machine reading says something harder: the consumer is a branch, `if X do Y, if no X do Z`, and a step that stays silent on one outcome leaves that branch with no defined transition. The consumer is not merely unable to audit; it has no rule to follow. It also supplies the boundary the bar has been missing. The counterexample four reviewers raised — a monitor or alert that speaks only on its condition — is not a step whose result something else branches on, so the bar was never about it.

## Build path

Per the skill-authoring checklist (`docs/wiki/queue/skill-authoring-checklist.md`); the skill text itself gets a zero-context read and a walk before adoption. Timing user-ruled: end of the clarity-registers walk ([nedschorus#138](https://github.com/nedschorus/nedschorus/issues/138)) or soon after.
