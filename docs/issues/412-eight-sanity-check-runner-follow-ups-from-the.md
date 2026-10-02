---
issue: "[Build sanity-checker](https://github.com/nedschorus/nedschorus/issues/412)"
---

# Build sanity-checker

## What this is

Eight small changes to `scripts/sanity-check-attacks.py` that the cells of the /sanity-check skill's own first sanity-check proposed, on 2026-09-15 and 16. None of the eight changes the skill's text. The user ruled at item 13 of that run's triage walk (cold-read-research seat) to file them as one draft issue, for the queue drain (GHI [Queue drain procedure — the review process that empties wiki/queue, the pair queue, and the draft-label issue queue](https://github.com/nedschorus/nedschorus/issues/24)) to split, build, or close.

The two changes from the same run that are being built now are on GHI [A Stop hook's report inside a claude -p review cell displaces the cell's report: two of three claude cells lost tonight](https://github.com/nedschorus/nedschorus/issues/397): keeping the project's hooks out of claude cells, and refusing a saved text that lacks its prompt's required sections.

Records, on the Mac in the cold-read-research seat's checkout: `sanity-check-records/2026-09-15-sanity-check-skill-draft/` (run 1) and `-2/` (the rerun of cut and mechanization). Report names below are `<attack>-<runtime>`.

## Why it matters

Each removes a step an agent must remember or a signal an agent must discount by hand. The project's criteria put mechanical guarantees over trained habit. Evidence is from those two runs; where a change has no observed miss, the entry says so.

## The eight

1. **Cells run in a detached temporary worktree of the reviewed commit.** Contains stray writes, makes the reviewed text exact, ends the rule that the requester changes nothing while cells run. Proposed by run 1 mechanization-codex F1, run 2 mechanization-codex F1, and both fresh-eyes cells. Opposed by run 2 mechanization-claude, citing the runner's own comment "containment over prevention, the house doctrine" and that observed cell writes have been strays (GHI [Sanity-check write detector never inspects the worktree after claude agents, and one wrote a file during a live run](https://github.com/nedschorus/nedschorus/issues/161)). Needs a user ruling before any build.
2. **The runner freezes the target's bytes and the request into the record at launch, and checks the target at the end.** The cold-read grid already does this for its targets (`nc-systems/cold-read/cold-read-grid.py`, user-ruled 2026-09-07 there). Removes the skill's "copy the request into the record" step. Run 2 mechanization-claude F2, run 1 mechanization-codex F2, run 2 cut-claude F4.
3. **The runner saves its own output into the record** as `sanity-check-run.log`. Today the warnings exist only in a background task's output; both records hold a log only because an agent copied it. Run 2 mechanization-claude F5, run 1 fresh-eyes-codex, fresh-eyes-claude.
4. **The quote scan folds typographic characters before matching.** Run 2 mechanization-claude replayed the scan over run 1's codex reports: 16 of 24 "quote found in no tracked file" warnings were a curly apostrophe against the draft's straight one. `normalized_for_quote_match` is the same rule as `scripts/md-drift-lint.py`'s, so both change together (GHI [Sort the 60 standing md-drift-lint findings into forward references and stale citations, then fix the stale ones](https://github.com/nedschorus/nedschorus/issues/572) holds that lint's backlog; the closed issue that used to hold it was GHI [md-drift-lint.py is tested and invoked by nothing](https://github.com/nedschorus/nedschorus/issues/336)). Same finding also adds `--target` and `--context` paths to the corpus, so an untracked target does not warn on every quote.
5. **A codex cell that returns an empty last message saves a provenance-only report.** `run_codex` returns the last-message file with no emptiness check; the claude chain checks (`exited 0 but produced no review`). Verified in the code 2026-09-15; no observed miss. Run 1 fresh-eyes-codex. Done: PR [Sanity-check runner: keep project hooks out of claude cells, refuse a saved text that is not a report](https://github.com/nedschorus/nedschorus/pull/417), merged 2026-09-16, refuses an empty text on both runtimes through its required-phrase check. No separate work.
6. **A `LEAK-WARNING` line names the line it matched.** Run 1 printed 22, each naming only the coined name and the file, so telling expected off-limits-path hits from real leaks means searching the request by hand. Run 2 mechanization-claude F6.
7. **A record for a skill is always `<date>-SKILL`**, because every skill's file is `SKILL.md`; two skills checked on one day differ only by `-2`. Include the parent directory when the stem is `SKILL`. Fresh-eyes-claude, hard part 10. Run 1 of this check landed under a different stem only because the target was a queue draft.
8. **A `--runtime` flag, so a rerun repeats only the failed runtime.** Today `--attack` reruns both, and the 2026-09-15 rerun re-ran two healthy codex cells at full cost. Run 2 cut-claude Q3, run 1 mechanization-codex F3.

## Outcome

Built, and merged on 2026-10-02 (UTC) by PR [Sanity-check cells read a copy of the reviewed commit](https://github.com/nedschorus/nedschorus/pull/885), merge commit c011ed47.

The user ruled the build in three steps:
- On 2026-09-30, at item 18 of the queue-drain's approval-walk queue-and-drafts-drain-2026-09-22 (minutes: `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/queue-and-drafts-drain-2026-09-22-minutes.md`), "1 - approved": this issue stays open as the tracker for making the runner ready, under his title "Build sanity-checker".
- On 2026-09-30, at item 2 of the walk open-questions-concerns-and-recommendations-2026-09-30 (minutes: `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/open-questions-concerns-and-recommendations-2026-09-30-minutes.md`), "Y": item 1 is built, so every cell reads a copy of the repository at the reviewed commit and the runner removes the copy when the run ends. On 2026-10-01 he confirmed the copy is a `git clone --local` ("y").
- On 2026-09-30, at item 3 of the same walk, "y": the remaining fixes go as one pull request, not one each. Item 2's freeze of the target is not needed, because the copy holds the reviewed bytes, and the request is read once at launch by cells that start together; only a copy of the request in the record was missing.

What PR 885 built, by entry above:
- Item 1: the review copy, and a target or context document with uncommitted changes is refused before any cell starts.
- Item 2: only its remaining half, a copy of the request saved into the record as `sanity-check-request.md`.
- Item 3: the run's output saved into the record as `sanity-check-run.log`.
- Item 4: quote matching folds curly and straight quotes. The untracked-target warnings are gone with item 1, since an untracked target is refused. `scripts/md-drift-lint.py` has no quote-matching rule on main today (`grep -i quote` finds only comments), so nothing there needed the same change.
- Item 6: a `LEAK-WARNING:` line names the line it matched.
- Item 7: a skill's record directory is named for the skill's directory.
- Item 8: `--runtime` selects `claude` or `codex`.

Item 5 was done earlier, by PR [Sanity-check runner: keep project hooks out of claude cells, refuse a saved text that is not a report](https://github.com/nedschorus/nedschorus/pull/417). PR 885 also added a relaunch of a cell that saves no report, unless only the user can clear the cause, and a `FAILED:` line that tells the requesting agent what to do next.

Next action: none. The issue closes as completed. Two follow-ups are on the cold-read-research seat's task list, not on this issue: adding "Leave it; the next sanity-check run removes it." to the line `WARNING: the review copy could not be removed: <path>`, which the user approved on 2026-10-01, and one approval-walk of the 35 cold-read findings on /sanity-check skill text that PR 885 did not write.

## Notes

Search: ghi-info ask 2026-09-16 for each of the eight, open and closed: none has an issue; item 1 appears only as a candidate on GHI [A Stop hook's report inside a claude -p review cell displaces the cell's report: two of three claude cells lost tonight](https://github.com/nedschorus/nedschorus/issues/397). Related: GHI [Ship sanity-check records to the log-store: scripts/sanity-check-record-ship.py, and the runner says ship, not delete](https://github.com/nedschorus/nedschorus/issues/392) (the record shipper and the runner's delete line), GHI [sanity-check skill: wrap the sanity-checker instrument so any agent can run it on a design (the glossary lists it; user-asked 2026-09-06)](https://github.com/nedschorus/nedschorus/issues/263) (the skill, which wraps the runner and does not redesign it).
