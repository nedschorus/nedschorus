# md-review dispositions — .claude/skills/ghi-write/SKILL.md, 2026-08-12

Eight reviews in this directory (4 restate, 4 defect-hunt; claude opus/sonnet, codex terra/sol). ~35 raw findings collapse into the clusters below. Verified against the checkout during triage: `gh issue close --reason` accepts {completed | not planned | duplicate}; `md-write` is a commissioned founding skill defined in docs/cross-project/nedschorus-founding-plan.md § Project organization (not yet built); CLAUDE.md does not expand "GHI"; the founding plan still carries the pre-2026-08-12 three-event comment catalog.

## Walk order (opened 2026-08-12, new-vp session cd0d8c04)

1. Purpose and the bar the findings are judged by
   *processed 2026-08-12 → accepted (purpose item; no capture)*
2. Trigger scope: description vs When Used diverge (all four hunts, sure) — align the description's second sentence to "home not yet decided"
   *processed 2026-08-12 → revised beyond the drafted proposal: the user rejected "any project artifact ... home not yet decided" as still reading broad — GHI machinery fires only when a GHI is being weighed. Both statements now name the same two conditions: a write touching a GitHub issue, or deciding whether material should become an issue. Supersedes the same-day skill-walk item-3 acceptance of the "home not yet decided" When Used wording. The register ruling is untouched.*
3. The queue bullet: "with no GHI" vs the `draft`-label queue contradiction, plus the queue-choice circularity — rewrite the bullet
   *processed 2026-08-12 → revised as proposed: the bullet now says fate-undecided material queues instead of getting an issue, keys the queue choice on the material's kind (wiki-bound, pair-bound, candidate issue), and names the `draft` label as the issue world's queue membership — the deliberate exception "with no GHI" contradicted. Supersedes the same-day skill-walk acceptance of this bullet within the "other three stand" ruling.*
4. The pair bullet: the 500-word test and the substantial-material test cross; "land it" undefined — rewrite ("land it on main"; crossing resolved)
   *processed 2026-08-12 → revised as proposed: substance now decides the form (pair when substantial material rides, issue-only otherwise), the plain 500 bounds every body — matching what the write tool enforces — with the crossing case answered ("a body that cannot is carrying pair material"), and "land it" becomes "land it on main". The same-day plain-500 ruling is preserved; this adds only the precedence and the definition it didn't cover.*
5. The comment line in the pre-#46 gap: only path names an unbuilt tool, deny claim not yet true, no fallback — add the interim path
   *processed 2026-08-12 → revised as proposed: "resubmit" → "submit"; the deny stated as the write path's rule; and an explicit interim sentence — plain gh issue comment naming the event kind until nedschorus#46 builds the tool. Rider for the post-push close-out batch: note in #46's body that the build deletes the interim sentence from the skill.*
6. Comment catalog clarity: gloss "instance outcome"; align the founding plan's stale three-event catalog with today's completion ruling
   *processed 2026-08-12 → revised as proposed: both events glossed in step 3 (instance outcome = one run of a recurring process while the issue stays open; ruling anchored to "the issue records"), drawing the instance-vs-completion line three hunters could not find; and the founding plan's revision-convention catalog surgically updated to the two-event form with the dated collapse note — the third durable home of the completion ruling, missed this morning.*
7. One fallback ladder, stated once: step 1 defers command detail to How-to; mirror rung gets "when present"
   *processed 2026-08-12 → revised as proposed: step 1 keeps the behavior (ask first, read what returns, edit-over-file, a failed ask never blocks) and points at How to do it for the command and ladder; the How-to's three-rung ladder is now the only statement of it, ending the two-vs-three rung drift; the mirror rung reads "when present" so an absent directory falls through instead of reading as an error.*
8. Unresolvable names: drop the md-write analogy clause and generalize the edit sentence; expand GHI at first use; gloss ghi-info; one cite line to the design doc
   *processed 2026-08-12 → revised as proposed, five changes: ghi-info glossed ("the project's issue-knowledge agent"); md-write analogy deleted and the edit sentence generalized ("revision is the default disposition"); step 1's forward reference to pair documents dropped ("the documents they cite"); GHI expanded at first body use; and a final How-to bullet cites the design doc for the machinery and the founding plan § Project organization for the routing doctrine — the path answer to the undefined-doctrine and undefined-home findings declined at item 11.*
9. "Every artifact is either final at its home…" — reviewers misread "final"; propose dropping the word (doctrine meaning preserved)
   *processed 2026-08-12 → revised as proposed: the skill's lead-in reads "either at its home or in a named queue with a drain" — the address meaning of the founding plan's artifact-lifecycle rule, minus the word all four hunts read as content-finality (which made an open issue look excluded by the binary). The founding plan's fuller verbatim sentence stays untouched.*
10. Factual micro-fixes: backtick claim overbroad; `--limit` on the gh search rung; `duplicate` close reason; "before filing" → "before submitting"; "from the issue alone" gets "(the body plus what it cites)" — capture of the 2026-08-12 walk-item-7 ruling that lives only in a commit message
    *processed 2026-08-12 → revised, all five applied as proposed.*
11.–17. Formerly one batch-decline item; re-planned 2026-08-12 at the user's instruction ("ignoring criticism is a mistake — usually we can find a better way to word things") into one item per group, each presented with a candidate rewording:
11. The never-blocks absolutes (failed ask; ambiguity)
    *processed 2026-08-12 → revised: "never blocks" → "does not block" in step 1; the discriminator's trailing "; ambiguity never blocks the write" maxim deleted as restatement. User's reasoning recorded: CLAUDE.md counsels against absolutes and neither of us sees benefit in them except extraordinary cases — the reviewers were echoing the project's own rule.*
12. The second-issue rule's missing boundary
    *processed 2026-08-12 → revised: "Where an edit to the existing issue is sufficient, no second issue is filed; work that needs its own lifecycle — its own next action and its own closure — is a new issue, not an edit." The user struck the drafted "serves" as saying nothing ("say what you mean — an edit is sufficient"); the lifecycle clause defines insufficiency, ending the circularity; the "never" is gone; the edit-history parenthetical stands.*
13. Generic section headings (What to do / How to do it)
    *processed 2026-08-12 → rejected, no change: the headings are the checklist template's fixed slots for the three questions every project skill answers; uniformity across skills outweighs per-file heading greppability, and skills are found by name and description. Side ruling, user-confirmed: the CLAUDE.md naming rule is not overreaching — its "likely to be grepped" qualifier already separates identity-bearing names from structural slots, and its use-the-existing-name clause endorses the template headings; no CLAUDE.md edit, revisit only if reviewer over-application recurs on the record.*
14. Zero-context tests vs CLAUDE.md's broader "usable"
    *processed 2026-08-12 → rejected, no change, verified by a minimal-context subagent dispatched at the user's instruction (its verdict: no defect, no rewording): step 4's gate governs issue writes only ("before submitting", "from the issue alone"); the no-next-action class routes to a bare MD at step 2 and never reaches the gate; every write reaching it carries a next action by construction, including the completion body-edit whose next action is the close-with-reason; the third test is CLAUDE.md's "usable" operationalized for issues, not a second rule to reconcile.*
15. Judgment terms without tests (covers the subject; substantial; reading stopping point)
    *processed 2026-08-12 → revised beyond the drafted proposal: the user flagged "existing artifact" as unbounded (any file grep can find) — the edit-over-file sentence now names the classes ("an existing issue or pair document") and carries the same-matter gloss; his follow-up question surfaced the same error at step 2's lead-in, now bounded ("Every artifact this skill routes"), adopting the terra-6/sol-8 findings declined at triage. "Substantial" stands (item 4's crossing sentence is its floor); the reading stopping point stays declined (ghi-info's reading list is the bound).*
16. Unbuilt machinery — a permanent-truth pointer to the #46 build
    *processed 2026-08-12 → revised: the machinery bullet gains "and built under nedschorus#46" — true before, during, and after the build, so an agent hitting a missing script resolves expected-gap vs breakage in one hop; an in-file "unbuilt" note stays rejected as staleness-bound. Items 5 and 7 already carry the gap's behavior (interim comment path; fall-through ladder).*
17. Remainder: reader's-seat, body-file housekeeping (doctrine/home already resolved by item 8's cite line)

## Finding-to-item map

- Item 2: opus-hunt 1, sonnet-hunt 1, terra-hunt 1, sol-hunt 2
- Item 3: opus-hunt 12/13/14, sonnet-hunt 6, terra-hunt 7, sol-hunt 9/10; restate splits (opus-restate item 7 vs codex-restate-good item 29)
- Item 4: opus-hunt 16/17, sonnet-hunt 8, terra-hunt 9/10, sol-hunt 12/13
- Item 5: opus-hunt 32, sonnet-hunt 11/12, terra-hunt 17/18, sol-hunt 28/29
- Item 6: opus-hunt 20/21, sonnet-hunt 9, sol-hunt 16/17; founding-plan drift found in triage
- Item 7: opus-hunt 2/10, sonnet-hunt 3, sol-hunt 25 (missing-dir case), opus-hunt 29/30
- Item 8: opus-hunt 4/7/8/13, sonnet-hunt 2/4/7, terra-hunt 2/3/4/8, sol-hunt 3/4/5/6; "pair documents" pre-definition opus-hunt 6b, sol-hunt 4
- Item 9: opus-hunt 11, sonnet-hunt 5, terra-hunt 6, sol-hunt 8; claude-restate-floor item 21
- Item 10: opus-hunt 24/33, terra-hunt 16/19, sol-hunt 27/30, terra-hunt 14, sol-hunt 24
- Item 11: opus-hunt 3/6a/9/15/18/19(second half)/22/23/25/26/27/34, terra-hunt 5/11/12/13/15, sol-hunt 1/7/11/14/15/18/19/20/21/22/23/26, sonnet-hunt 10, opus-hunt 5/28/30/31/35 partial (missing-script class beyond item 5's fix; opus-15/18 answered by item 8's cite line)
