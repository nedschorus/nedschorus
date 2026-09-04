# Split pull request specification (task #98)

Written 2026-09-04 by the merge-lane seat after the AI-native objective walk closed, so a successor session can execute the pull request without re-reading the minutes end to end. The minutes remain the authority on WHY; this file is the executable WHAT. Minutes: `docs/walk/2026-09-03-ai-native-architecture-overview-decisions-minutes.md`.

## What this pull request does

Splits `docs/cross-project/nedschorus-ai-native-software-development.md` into two readable documents on an ALTITUDE axis (user-ruled: both pages carry all relevant subjects in the same order; the objective states each at a level a reader can follow end to end; the notes carry the detail behind it; a subject with no detail yet simply has no notes section).

1. The OBJECTIVE page, high level, into `docs/wiki/queue/` until vetted, then drained to `docs/wiki/` after its cold read and the user's own whole-document review.
2. The NOTES page, the detail, in `docs/cross-project/`.
3. `CLAUDE.md` gains ONE line linking the objective page and carries none of the mission text.
4. The current file is deleted and its citations repointed.

## Measured facts, not assumed

Citations to the current path, measured 2026-09-04 with grep over `*.md`, `*.py`, `*.json`, `*.sh`: FOURTEEN files, of which four are this walk's own documents. The real repoint list is TEN files. The "twenty citations" figure repeated from item 2 onward is wrong and came from restating #248's scope; #248 itself repointed seventeen founding-plan references, a different set.

Files to repoint: `docs/agents/doctrine-instructions.md`, `docs/agents/ghi-instructions.md`, `docs/cross-project/fleet-git-worktree-working-model.md`, `docs/cross-project/git-gatekeeper-design.md`, `docs/drafts/choirmaster-identity-draft.md`, `docs/issues/46-ghi-info-agent-design.md`, `docs/wiki/queue/213-project-vocabulary.md`, `nc-queue/README.md`, `README.md`, `docs/walk/2026-09-02-should-a-pr-reviewer-report-code-design-mismatch-minutes.md`.

NO references exist in `scripts/` or `.claude/`, so no program depends on the path and no test breaks on the delete. Verified by grep over both trees.

The "central rule" item 2 sends to the objective page is line 97 of the current file: "The most important design choice is not the sequence of boxes. It is the refusal to rely on hidden state between them."

## Three drifts to fix before writing, each of which produces wrong text

1. **"Controller" is dead.** Item 3 renamed master to controller for the routing half. Item 6 then killed the controller outright, in the user's words: "there is no global controller in these kinds of terms... there is only the global state machine with nodes." So master becomes the DESIGN-TO-MAIN STATE MACHINE where a sentence means routing, and LIAISON where it means the human channel. Nothing becomes "controller".

2. **Notes section 10 is a restructure, not a rename.** Its title is "The master and the human conversation" and it describes one entity across roughly fifty lines. That entity is now two things (the liaison agent, the state-machine program) plus a third topic that moved into decisions 18 and 19. A find-and-replace leaves a section contradicting itself.

3. **The skill-line target moved.** Item 4's approval pointed the ghi-write skill at `CLAUDE.md § Project organization`. Item 6 then forbade putting any mission text in CLAUDE.md. The real target is the objective page's Project organization section. The `.walk-approved` marker must quote BOTH his item-4 "y" and his item-6 words ("None of this will go into claude.md... This is the objective.md wiki page... Claude should have a simple link to that page"), because the write differs from what the bare "y" approved.

## Governance header, required on the objective page

The page lands in `docs/wiki/queue/` unvetted, but CLAUDE.md links to it and it carries text titled standing decisions. Every agent following that link will apply it. The header must state: the rulings were user-approved 2026-09-03 and 2026-09-04 (link the minutes); the TEXT has not yet had its cold read or the user's whole-document review under decision 19; it drains to `docs/wiki/` after both.

## Where WHAT and WHY go

The objective's standing-decisions section carries what each decision says. The notes carry why: the date, his words, and the objection that fell. Without the why, a later agent re-derives an objection that was already answered — measured today, twice, in the arbitrator and validator-approval exchanges.

## Open before the final text can be written

- The user's Y/N on two amendments: decision 13 restated as his three-tier framing (input rules and output rules, each handled by code, AI or human, with humans scarce and not parallelizable), and the arbitrator decision gaining that an arbitrator looks at everything relevant, not only the two sides it is adjudicating.
- The user's Y/N on a new cold-read decision, in its final sharpened form after the reboot-test exchange of 2026-09-04: "A document is cold-read before work is built from it, and not again unless what it promises changes. Where it enumerates its promises, that is a diff over the enumeration; where it does not, it is a change in the enumerated document downstream of it. The human's review rides the same trigger. This holds where every reader that builds from the document is fresh; where a reader accumulates context across passes, drift accumulates unseen and the document is re-read." The final condition is stated as a condition rather than an exception list, because a carve-out is only as good as what we can imagine today and rots silently, while a condition is checked at the point of use by whoever is about to skip a read. It also states why the rule works: the cold read was always a way to manufacture a fresh reader, and a machine whose readers are fresh by construction needs no such manufacture. The user is the only reader who persists across passes, and he does not build, which is what makes putting his review on the same trigger safe rather than merely cheap. The enumeration clause exists because the trigger must be code-evaluable: the state machine holds no judgement, so "did the promise change" has to be a diff, not a reading. The downstream clause exists because a contract enumerates its promises and a code-design does not.
- The user's Y/N on the consequent repair to DECISION 19 AS APPROVED, which has a defect the reboot-test seat found: its predicate is "all final prose", a property of the document, and "after its cold read" states a sequence rather than a condition. So a revision that correctly skips the cold read still reaches him. Repair, to be added to decision 19: a document that did not earn a fresh cold read has not become final prose again.
- Decision 15's "durable artifacts" needs a replacement noun under the artifact ban. His substitutes are the specific noun, or "a node's output", or "the package an edge carries".

## The cold read must run in the session that writes these pages

User-ruled 2026-09-04, in the reboot-test window: "Cold read has to be coupled to the writer - because only the writer knows what they are trying or need to say, even if they are incompetant at saying it in a way that a cold reader can understand."

That is why the cold read is a sub-node inside a prose-producing node rather than a downstream state, and it binds this pull request directly. Item 1 of the walk ruled that the cold read runs after the split, on the edited text. Coupled to the writer means the session that WRITES the objective and notes pages runs that cold read and acts on its findings, while it still holds the intent behind each sentence. If this seat recycles between writing and reading, the coupling is broken: a successor has this specification, which records what the pages must contain, but not what the writer was reaching for in any particular sentence, which is exactly what a cold-read finding needs in order to be answered rather than merely accommodated.

So: write both pages and run the cold read in one session. If that is not possible, the successor re-drafts the sections it must defend rather than inheriting them, because under this ruling an agent cannot answer a cold read of prose it did not write.

## Review path

This seat authors it, so per CLAUDE.local.md: open as `ned-review-merge`, and a fresh mac-claude reviewer reviews. Note in this seat's own posted review that the project's reviewer rule makes `docs/wiki/` and `docs/cross-project/` prose unreportable, so the independent review covers only the mechanical parts: the repoints, the delete, the CLAUDE.md line, and the guarded writes. The user's prose review happens at drain, under decision 19.

## A third repoint is coming

While the objective page sits in `docs/wiki/queue/`, the CLAUDE.md link and all ten citations point at a queue path. Draining it to `docs/wiki/` repoints them again. Say so in the pull request description so the second move is expected rather than discovered.
