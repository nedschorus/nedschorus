# Commit pins are hand-written and never machine-checked — and #42 does not know the drift lint exists

Queued for [nedschorus#42](https://github.com/nedschorus/nedschorus/issues/42) (reference-integrity checker: links resolve and cited revision-paths exist). Owned by the `ghi` seat (`docs/agents/ghi-instructions.md`).

Surfaced by the attack-split validation experiment of 2026-08-12 (`md-review-records/2026-08-12-attack-split-experiment/scorecard.md`, § Novel findings, "Pin-stamp"), where both runtimes independently proposed that whatever writes a record stamp the repository and HEAD mechanically, because a model-recalled commit id is a hallucination channel. Verified against the repository as it stands on 2026-08-13 by the `sanity-checker` seat. **The finding as originally worded does not survive verification; a narrower one does, and it lands inside this issue's existing scope rather than beside it.**

## What the original wording claimed, and what is actually there

The finding was recorded as "agents hand-write 40-character commit ids into records, and mistype them."

**No 40-character commit id appears in any committed markdown.** Search receipt: `grep -rEo "\b[0-9a-f]{40}\b" --exclude-dir=.git .` over the whole checkout returns two hits, both inside `md-review-records/2026-08-09-git-gatekeeper-design/*.stderr.log` — machine-generated Codex logs, not text an agent wrote. The 40-character half of the claim is false.

What agents actually write is short ids, 7 to 8 hex characters. Of eleven hand-written ids sampled across `docs/`, `nc-queue/` and the machine-local handoffs, nine resolve to real commits in this repository. Two do not:

- `docs/cross-project/nedschorus-founding-plan.md:43` (file retired 2026-09-03; `git show 615a230:docs/cross-project/nedschorus-founding-plan.md`) — "the founding documents (migrated here from the legacy system, frozen there at `78ed90f0`)". This is a pin into the *legacy* repository, so it is not expected to resolve here. It cannot be resolved anywhere on `ned-box` either: `CLAUDE.md` names the legacy system as `~/Projects/nedlern`, and that directory does not exist on this machine (`ls ~/Projects` returns only `nedschorus`). Whether that is a stale `CLAUDE.md` path or a checkout never made on the box is a separate question, flagged to the user 2026-08-13.
- `nc-queue/2026-07-28-sdlc-skill-set-coverage-and-app-skill-pile.md:80` — "Section merged from the Mac-app session's branch copy (final at `f7cc0ef`)". Not in this repository's object store; `git rev-parse --verify f7cc0ef` fails, and the branch it names is gone.

**Neither is demonstrably a typo.** That is the actual finding, and it is sharper than the original: *nothing can tell a mistyped pin from a pruned branch or a cross-repository reference*, because pins are written by hand and no mechanism ever resolves them. A dangling pin and a wrong pin are indistinguishable to every reader, forever.

## Why this belongs in #42 and not in a new issue

Issue #42 already specifies exactly this check: "every cited `<revision>:<path>` form exists at that revision (`git ls-tree` per citation)". This material is a confirmed instance with evidence, not new scope. It adds three things #42 does not yet state:

1. **Two live instances**, above, to test any implementation against — including the awkward one, a legitimate cross-repository pin that a naive checker would report as a defect. A checker that cannot distinguish "pins another repository" from "pins nothing" will be turned off within a week.
2. **The manual path is instructed, not accidental.** `.claude/skills/handoff/SKILL.md:10` tells every agent writing a handoff: "If your prompt references a file, include its path and commit SHA." `docs/cross-project/fast-handoff-design.md:34` makes it a design rule — "every pointer carries a pin (path + commit SHA, repository + issue number)". So the project deliberately generates hand-transcribed pins at every session boundary. The mechanical alternative is cheap: the writer stamps `git rev-parse HEAD` rather than recalling it. No script in `scripts/` does this today (`grep -rln "rev-parse HEAD" scripts/` is empty).
3. **The overlap below**, which is the part worth reading before any code is written.

## The overlap: half of #42 is already built, under another name

`scripts/md-drift-lint.py` exists and runs today. Its docstring calls it "the lint half of the sanity-check", built under a grid-seat ruling walked with the user 2026-08-12 and recorded in `docs/drafts/sanity-checker-prompt-draft.md`. It checks, per file: that repo paths named in backticks or markdown links exist on disk; that markdown link targets resolve; that `YYYY-MM-DD` tokens are real calendar dates; that a backticked command naming a project script names only flags that script actually accepts; and, for JSON, that no key is duplicated at any nesting depth. It reports and never edits. It has its own suite, `scripts/md-drift-lint-test.py`.

That is #42's "every relative link resolves to a real file" half, already shipped. #42's body does not mention it, and #42's build-timing note still reads "gatekeeper era — a natural early check-battery addition, not founding work." **Two seats are one step from building the same checker twice.**

**Next action for the `ghi` seat.** Before writing any code for #42, settle with the user whether the reference-integrity checker *is* `scripts/md-drift-lint.py` grown by one check, or a separate program with a different consumer — #42 frames itself as a review check and the drift lint as a sanity-check lint, which may or may not be a real distinction. Then edit #42's body to record whichever answer, since the body currently describes unbuilt work that is partly built. If the answer is "grow the drift lint", the commit-pin check is roughly a `git rev-parse --verify` per cited id plus a rule for cross-repository pins, and it lands in a file the `sanity-checker` seat also touches — worth one message to the user about who writes it.
