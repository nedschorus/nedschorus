---
issue: "[Sort the 60 standing md-drift-lint findings into forward references and stale citations, then fix the stale ones](https://github.com/nedschorus/nedschorus/issues/572)"
---

# Sort the 60 standing md-drift-lint findings into forward references and stale citations, then fix the stale ones

`scripts/md-drift-lint.py` reports a cited path that does not resolve. Run over every tracked Markdown file it prints **61 lines carrying 60 distinct findings**, measured in a clean worktree at [main on 2026-09-21](https://github.com/nedschorus/nedschorus/commit/17c9ee8). Nothing owns them.

The count was **66** when this issue was filed, at [main on 2026-09-20](https://github.com/nedschorus/nedschorus/commit/b9b86d2). Five of those were a lint mis-parse, fixed since; see the mis-parse section below. The sixty-first line is a duplicate: `docs/cross-project/nc-python-toolchain-plan.md:39` cites `quality/runs.jsonl` twice on one line, once as the ledger and once in the sentence refusing a check-in that declares it, so the lint reports it twice. That is the document's wording, not a lint defect, and it is one finding to act on.

Reproduce with `python3 scripts/md-drift-lint.py $(git ls-files '*.md')`, which exits 1 when it finds anything. **Measure in a CLEAN worktree.** A working seat's checkout holds gitignored files, and a citation that resolves against one of those is not reported, so a seat sees fewer findings than the repository has.

That caveat has already cost one wrong number. The walk that filed this issue counted 62, measured in a seat's own checkout. Measured clean the same day the count is 66, and it is 66 at every commit on main between 15:27 and 18:13 — the four missing findings were never fixed, they were hidden by the measuring seat's own untracked files.

## Why this has no home

GHI [md-drift-lint.py is tested and invoked by nothing: wire it into merge-lane's review, scoped to a pull request's changed lines](https://github.com/nedschorus/nedschorus/issues/336) closed 2026-09-17 when the lint was wired in. GHI [Sweep the 96 standing md-drift-lint findings in the repository's Markdown, noisiest document first](https://github.com/nedschorus/nedschorus/issues/456) closed the same day, having swept that generation.

Since then the lint's live coverage is scoped to a pull request's changed lines only. Nothing re-sweeps the whole tree, so standing drift has no reader.

## What the 60 are

They are not one kind of thing, which is why sorting comes before fixing.

| Class | Count | What it is |
|---|---|---|
| Candidate stale citation | 30 | The document claims something about this repository that stopped being true. The real subject of the sweep. |
| Forward reference to decided-but-unbuilt work | 24 | Prose about a program the project has decided to build. 25 output lines, one of them the duplicate above. |
| In `docs/drafts/` | 5 | Excluded: the user ruled 2026-09-20 that `docs/drafts/` stays out of the citation sweep. |
| The one number check | 1 | A backticked number its source file does not contain. |
| Lint mis-parse of a template placeholder | 0 | Was 5. A lint defect rather than prose drift, and fixed; see below. |

**The 24 forward references** (25 output lines) name programs with owning issues: eight cite `scripts/ghi-issue-write.py` and two `.claude/hooks/ghi-issue-write-redirect.py`, both built by GHI [Build ghi-info — the GHI knowledge agent](https://github.com/nedschorus/nedschorus/issues/46); twelve cite `quality/*` files and one `src/nc/runtime/retry.py`, which the nc-python-toolchain architecture proposes; two cite `scripts/start-topic-branch.py` and its test, from GHI [Topic-branch base enforcement: a branch-creation script and a gh pr create check that refuses an undeclared carry of another PR's commits](https://github.com/nedschorus/nedschorus/issues/238). Fixing one of these would make correct prose wrong, so long as its owning issue still stands.

**The 5 mis-parses are a defect in the lint, found while classifying.** The line

    | `<component's directory>/design-to-main-record/user-rulings.md` | every ruling the user has given ... |

is a backticked placeholder path whose variable contains a space. The lint splits on that space and reports the tail as a real path, `directory>/design-to-main-record/user-rulings.md`. It fires at `docs/design-to-main/design-to-main-state-machine-design.md:521` and `:522` and in three `docs/agents/queue/design-to-main-*` files. A reader sorting this backlog without knowing would "fix" correct template text.

**This needed no ruling, and the first filing of this issue was wrong to say it did.** `<` is already in the lint's `SKIP_MARKERS`, so a `<placeholder>` was already meant to be unchecked; the marker is tested per word and the span is split on whitespace first, so a placeholder containing a space lost its `<` to the split. The fix collapses each `<...>` span to one marker-bearing word before the split, restoring the reach of a rule the lint already states: PR [md-drift-lint: a placeholder containing a space is no longer read as a path](https://github.com/nedschorus/nedschorus/pull/574). Measured there: 66 before, 61 after, the five removed being exactly these five.

**That pull request has merged, and this class is now zero** — confirmed by measurement at main 17c9ee8: no finding anywhere in the corpus carries a `directory>/` tail. It shipped a regression of its own, that any pair of angle brackets was treated as a placeholder, which silently stopped checking paths inside a shell redirect and inside an HTML comment; that is fixed in PR [md-drift-lint: a placeholder's brackets must hug their content, so a redirect keeps its path](https://github.com/nedschorus/nedschorus/pull/583) and PR [md-drift-lint: the closing-tag exclusion comes out, and its case can now fail](https://github.com/nedschorus/nedschorus/pull/584), both merged. The counts above are measured after all three.

## First action

Sort the 60 into the classes above, then fix only the candidate stale ones. The classification above is a starting partition computed by target path, not a judgment on each finding — a forward reference is only correct prose if the project has actually decided to build the thing, and that is checked per citation, against an issue.

The noisiest citing documents among the candidates are `docs/issues/10-working-ideas-and-research-backlog.md`, `docs/issues/3-main-gatekeeper-build-slice-plan.md` and `docs/issues/archived/43-step-2-claude-md-inputs.md`, three each.

A finding is not automatically a defect in the document. Each is a claim that no longer matches the repository, and the fix is whichever it turns out to be: correct the path, or delete a sentence about something that no longer exists. Some are drift in the other direction — the document is right and the repository moved — and those want the repository's own issue, not a Markdown edit.

## The question this issue carries

**A surviving forward reference keeps being reported on every run, for as long as its program is unbuilt.** Twenty-four of 60 are that today. Either the lint learns to skip a citation whose target an open issue has committed to build, or the noise is accepted and read past. Deciding this is part of the work here, not a precondition for starting it.

## Open scope question

Seven of the 60 sit in queue directories — `docs/issues/queue/` (4), `docs/nedschorus-wiki/queue/` (1) and `nc-queue/` (2). It was ten: the three in `docs/agents/queue/` were mis-parses, and the placeholder fix removed them. Queue material is not-yet-decided by definition and is emptied by GHI [Queue drain procedure — the review process that empties wiki/queue, the pair queue, and the draft-label issue queue](https://github.com/nedschorus/nedschorus/issues/24). The same argument that put `docs/drafts/` out of scope may put these there too. Not ruled; whoever takes this issue should settle it with the user before editing a queue file.

## Related, and not this issue

GHI [Reference-integrity checker: links resolve and cited revision-paths exist — pure-code review check (and the home for what-else-can-code-check)](https://github.com/nedschorus/nedschorus/issues/42) is the open home for building a general reference-integrity instrument. This issue is a backlog of one existing lint's findings, not a build.

One stale pointer worth repairing when this issue has a number: GHI [Eight sanity-check runner follow-ups from the /sanity-check skill's first sanity-check, for the drain to split](https://github.com/nedschorus/nedschorus/issues/412) cites GHI [md-drift-lint.py is tested and invoked by nothing](https://github.com/nedschorus/nedschorus/issues/336) as the place that "holds that lint's backlog". That issue is closed; this one is that place now.

Filed on the user's ruling of 2026-09-20, walk `four-questions-after-the-dangling-path-check-2026-09-20`, item 3: one GHI for the backlog, which sorts before it fixes, and which carries the forward-reference noise question. Minutes: `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/four-questions-after-the-dangling-path-check-2026-09-20-minutes.md`.
