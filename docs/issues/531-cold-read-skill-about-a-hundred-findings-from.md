---
issue: "[cold-read skill: about a hundred findings from its 2026-09-19 six-reviewer read await their walk](https://github.com/nedschorus/nedschorus/issues/531)"
---

# cold-read skill: about a hundred findings from its 2026-09-19 six-reviewer read await their walk

## What

The cold-read-full-run of `.claude/skills/cold-read/SKILL.md` on 2026-09-19 (record `nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/SKILL-cold-read-2026-09-18-2/`, six reports, about 140 findings) was triaged for the glossary-awareness change that pull request [Cold-read reviewers read the glossary, and the terminology reviewer proposes key-terms](https://github.com/nedschorus/nedschorus/pull/533) landed. About a hundred findings were on sentences that were on main before that change, so no approval covered them. This issue held them until their walk.

**That walk has now run in part.** The approval-walk `SKILL-cold-read-2026-09-18-2` was reopened on 2026-09-20 for items 4 to 11; every item was approved and landed as pull request [The cold-read skill says what its programs actually do](https://github.com/nedschorus/nedschorus/pull/560), merged 2026-09-20 as 5646854. Twelve of this issue's thirteen finding groups are ruled. The "Smaller" group was never presented, and behind that one heading sit roughly sixty findings no item reached, plus partial remainders on nine that an item reached only in part. **This issue stays open for those.** Rulings are in `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/SKILL-cold-read-2026-09-18-2-dispositions.md`; the sitting's record is the minutes beside it.

## Why

Six fresh-agent reviewers agreed on several of these, and each names a case where a reader of the skill cannot act. What is left is not a tail of nits: four clusters below were each named independently by four or more reviewers, and one of them is a hole in a fix that just landed.

## Ruled and landed 2026-09-20

Words used two ways each; "the walk-me-through MD file" and "designs, a GHI-MD among them"; the Monitor; `AGENT-BINARY DOWN:` and `STRAY WRITE:` described wrongly; step 3's record path and step 4's "all the cold-read-record holds"; a cold-read-cell that hangs; the shipper's `REFUSED:`/`FAILED:` on the cold-read-full-run route and the record shipping before the walk instead of after; a PR description and an issue body not being files; the fast route never saying the full run is still owed; and the three overclaims. See the pull request and the dispositions file for each group's citations.

## What remains

Four clusters, each named independently by four or more reviewers.

1. **The frontmatter description against step 2.** The description's dashed list of documents needing the cold-read-full-run is narrower than step 2's operative list, so an agent routing from the description alone sends a seat-brief or a design-contract to the fast read. "Drafts" in two senses and "wiki page" against "Wiki files" belong here. claude-hunt-floor 1, 3, 8; claude-hunt-good 1, 3, 8, 10, 13; claude-terminology 2, 4; codex-hunt-floor 1; codex-hunt-good 1.
2. **The step 4 / step 9 walk structure.** Two distinct step-4 stops with no resume point; no commit instruction on the cold-read-fast-read route though step 9 says "your committed changes"; nowhere to record a rejected finding on that route; and no continuation for a walk that closes on a rejection. claude-hunt-floor 16, 17, 18; claude-hunt-good 17, 18, 27, 35; codex-hunt-floor 24, 28; codex-hunt-good 26, 27, 28.
3. **The closing text and the `record:` line.** Step 6's marker list omits both, and step 7 depends on the closing text three times. claude-hunt-floor 21, 29; claude-hunt-good 20, 24, 29; claude-terminology 15; codex-hunt-floor 8, 15, 16.
4. **The walk's own outputs.** `<record>` is undefined as a string, "one line per finding" has no grain or format, and whether the dispositions file overlaps the walk-minutes is unsettled. claude-hunt-floor 25, 35; claude-hunt-good 34, 36; claude-terminology 19; codex-hunt-floor 26, 27.

Two specific findings from checking the 2026-09-20 sitting's own work, both put to the user and both deferred here ("wait for the next walk", 2026-09-20):

- **Item 8's shipper sentence reaches one route of two.** Step 9 now names `REFUSED:` and `FAILED:` for the cold-read-record ship. The cold-read-fast-read ships its own record as well: `scripts/cold-read-fast-read.py` line 779 prints `cold-read-fast-read: record: <result>` on stderr, so a refusal there reads `record: REFUSED:`, which does not open with FAILED and so does not match step 3's "If it prints a line opening FAILED, tell the user and stop". The string `record:` appears nowhere in the skill.
- **A finding recorded Applied whose fix was half made.** codex-terminology 3 asked for three changes, one being "change the heading to `# /cold-read`". The prose was resolved a different way at the first sitting (unhyphenated "cold read" in step 2), and the heading is still `# cold-read` at line 6. The finding is listed Applied in the record's `triage.md`.

Also uncovered, outside the four clusters: the one-sentence/mechanical exception in step 2 is not executable (no baseline, no sentence-boundary rule); `triage.md` is used three times before step 8 says where it lives and is given no path rule; keeping the `cold-read-records/` directory sits against CLAUDE.md's "never in the repository"; the `RECOVERED:` tail conflicts with the `RETRYING:` rule; "cold-read-cell" is used for the program around the model as well as for the glossary's one-model unit; and "set" names the six reports where the document already calls them reports (codex-terminology 11). Full list in the dispositions file and the six reports.

## Next action

One approval-walk of the four clusters, cluster by cluster rather than finding by finding — the 2026-09-20 sitting showed that thirteen headings collapse into eight decisions. Present the two specific findings above with cluster 3, which is where they come from. Then land the ruled changes as one pull request on the skill file and record the rulings here.
