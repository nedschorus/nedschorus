# cold-read-reviewer-test-cases

**Measured data. Do not edit a file here to improve it.** Every number this project has published about reviewer quality is measured against these files. An agent that tidies a row, fixes a typo in a draft, or clarifies a sentence silently re-tunes every score ever taken, and nothing anywhere says so. If something here is wrong, say so and re-score; do not correct it in place.

## What this is, and why it is in the repository

A reviewer test case is a **trio**: the first draft of a document, the perfected version of that same document, and the list of defects between them. Point a reviewer at the first draft and its findings can be scored, because the defect list says what was actually wrong.

The rest of the cold-read machinery's output is a log and lives in the log-store, never here: reviewer reports, placement tables, run results. Those are byproducts of a run, deleted or archived when the work they served lands, exactly as `.gitignore` says of `cold-read-records/`.

**A trio is not a byproduct.** It is the instrument the byproducts are measured with, it is meant to outlive every run, and it has to be versioned, reviewed and restorable by a checkout. That is why it is committed and the records are not. User-ruled 2026-09-10.

## What is here

| Trio | Status |
|---|---|
| `ghi-write-trio/` | Complete and scrubbed by the user. The only usable trio today. |

`ghi-write-trio/` holds:

- `ghi-write-first-draft-6a098f4.md` — the draft as first written, 658 words, byte-identical to git object 6a098f4 (2026-08-06).
- `ghi-write-perfected-2026-09-08.md` — the skill at main 78ceb75, which the user walked and accepted, plus the six fixes his scrub accepted and the two fixes of 2026-09-09. 916 words.
- `ghi-write-defect-list-2026-09-07.md` — 33 rows, one per defect, each quoting the draft exactly and saying what is wrong. Scrubbed by the user 2026-09-07 and 09-08. Carries the severity weights adopted 2026-09-08.

## The defect list is the ruler, and it has weights

Recall is not rows over 33. Row 22 was ruled not a defect, so 32 rows score, and each carries a weight of 1 to 8 in the list's own "Severity weights" section. Recall is the weight of the rows a reviewer found over 102, the total.

The weight means **consequence if the draft is obeyed as written**, not how likely a reader is to misread. One row misled all four restaters and still rates 3, because the misreading changes no write.

`scripts/cold-read-reviewer-score.py` reads the weights out of the list rather than holding a copy, so the list is the single source of the ruler.

**One number differs from the records published before 2026-09-10, deliberately.** Those reported flat recall over 33 rows, because they predate the ruling that row 22 is not a defect. This program divides by the 32 scored rows, so its flat recall reads one to three points higher for the same reviewer. **Every weighted figure is unchanged**, and the weighted figure is the one to read. The per-reviewer weights, the best four-reviewer union at 100 of 102, and the single unfound row are all pinned by `scripts/cold-read-reviewer-score-test.py` against what those records published, so the scoring math cannot drift under them unnoticed.

## The citations here are frozen, and every checker must skip this directory

The three files cite paths, name scripts and quote sentences as they stood when each file was written, and several of those targets have since been retired, renamed or revised on main. Those citations are correct as data: they record what the documents said at the time, and bringing one up to date would change the text the scores were measured against, which is exactly the edit the header forbids. So every mechanical reference or drift check must exclude this directory rather than report it: the existing drift lint, `scripts/md-drift-lint.py`, and the reference-integrity checker to be built under [nedschorus#42](https://github.com/nedschorus/nedschorus/issues/42), which carries the exclusion as a requirement.

Measured 2026-09-11: the drift lint run over the three trio files produces nine findings, and every one is a frozen citation — a retired doctrine path, a renamed script, a quotation checked against today's copy of a design. None is a defect. A triager who fixes a finding here silently re-tunes every published score.

## What makes a pair worth turning into a trio

Measured 2026-09-10 over the six draft-and-landed pairs then held. A defect row exists only where the landed text FIXES something the draft got wrong, so a pair is usable only when the landed version REVISED the draft rather than replacing or expanding it. Two numbers separate the shapes:

| Shape | Survival of the draft's prose | Size ratio | Rows it yields |
|---|---|---|---|
| Revision | high | near 1 | many — this is the candidate zone |
| Expansion | high | large | few; the diff is additions, which are not defects |
| Rewrite | low | any | none; nothing in the landed text fixes the draft |

ghi-write is the calibration point at 73 % survival and 1.39x. Of the other five pairs, two kept none of their draft, one kept 14 %, one grew 3.76x while discarding four fifths, and one kept 98 % but nearly tripled. None was worth a scrub. The record is `nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/2026-09-10-trio-candidate-screen/RESULT.md`.

## Where new trios come from

From documents the project perfects in its normal course, not from anyone sitting down to perfect old drafts (user-ruled 2026-09-10). The perfected half can always be read off main. **The first draft is the perishable half** — once a document is revised in place it survives only if someone kept a copy. Capturing it is a requirement on the unbuilt `draft-md` skill, [nedschorus#142](https://github.com/nedschorus/nedschorus/issues/142), which also carries the `<document>-first-draft` naming the user ruled on 2026-09-10 and the two consequences it brings.

The queue directories are NOT the place to catch a draft: nothing enters a queue until it has been scrubbed several times, so what sits there is not a draft.

## Crosswalk from the machine-local names

These files were machine-local under `cold-read-records/2026-09-05-perfect-test-cases/` until 2026-09-10, and records shipped before that date cite them by their old paths. Those citations were never resolvable from the other machine anyway, which is the defect class filed on [nedschorus#42](https://github.com/nedschorus/nedschorus/issues/42).

| Cited as | Now |
|---|---|
| `ghi-write-first-6a098f4.md` | `ghi-write-trio/ghi-write-first-draft-6a098f4.md` |
| `ghi-write-trio-perfect-2026-09-08.md` | `ghi-write-trio/ghi-write-perfected-2026-09-08.md` |
| `ghi-write-candidate-defect-list-2026-09-07.md` | `ghi-write-trio/ghi-write-defect-list-2026-09-07.md` |

Material that did NOT move, and why: the unscrubbed defect lists for walk-me-through and the manufactured ghi-write draft are working material rather than instruments; the four nedlern candidate drafts are off the path by the user's ruling of 2026-09-10; the transcript mining directory is 14 MB of raw input to that abandoned line. All of it stays machine-local, and the parts worth keeping are shipped to this seat's area of the log-store.
