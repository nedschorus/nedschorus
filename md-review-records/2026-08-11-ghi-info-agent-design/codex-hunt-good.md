<!-- provenance: runtime=codex model=gpt-5.6-sol effort=xhigh cell=defect-hunt tier=good target=/Users/el/Projects/nedschorus/.claude/worktrees/linters-tool-usage-f8b0a0/docs/drafts/ghi-info-agent-design.md -->

1. “`status: integrated design; ... awaiting the user's integration walk`” conflicts with “`Walk order — integration walk (opened 2026-08-09...)`” and five processed items. A reader cannot determine whether the walk has not started or is nearly complete; that changes which actions remain authorized. Confidence: sure.

2. “`design-as-of: 2026-08-09`” conflicts with decisions and approvals dated 2026-08-11 throughout the document. A builder relying on the frontmatter could treat the later material as outside the declared design snapshot. Confidence: sure.

3. “`new-vp session 3a11d08f`” introduces an unexplained role and an eight-character identifier without a path or lookup procedure. In the permitted minimal context, a future agent cannot locate that decision record or know what kind of session it was. Confidence: unsure; an external session index may understand the identifier, but none is referenced here.

4. “`four prompts still owed there`” and “`Prompt drafting in progress`” conflict with “`Status: every prompt is final`.” This leaves close-out eligibility indeterminate. Confidence: sure.

5. “`The answer is a bare list`” conflicts with “`Reply with a bare list ... plus, only when needed, note lines in plain sentences.`” A list accompanied by prose is not bare. The contract also supplies no representation for the ordinary zero-match case and no malformed-reading-list behavior, so the wrapper cannot reliably distinguish a valid empty answer, notes, escalation, and failure. Confidence: sure.

6. “`The write tool consults ghi-info with the actual draft body`” omits the draft title even though issue identity and duplication often reside principally in the title. A new issue with a generic body and a duplicate-specific title can be classified unrelated because the adjudicator never receives the distinguishing text. Confidence: sure.

7. “`verdict: too-similar #n / related #n,#m / unrelated`” defines exactly one too-similar issue and exactly two related issues. One related issue, three related issues, or several existing issues that collectively cover the draft are reachable cases with no valid encoding. Confidence: sure.

8. “`too-similar (duplicate, overlapping, conflicting)`” conflicts with “`Whether an old ruling still binds always escalates to the user`” and the exact three-verdict adjudication grammar. A draft conflicting with an old ruled issue must both return `too-similar` and return `escalate:`; the latter is malformed and therefore fail-open. Confidence: sure.

9. “`anything beyond the issue corpus ... returns a fixed out-of-scope reply`” conflicts with the duty and prompt to repair document-side GHI↔MD links. A request to edit an MD is beyond the issue corpus under the stated boundary, yet request form 4 orders the agent to perform it. Confidence: sure.

10. “`The authoritative copy lives in ghi-info's checkout on the box`” supports a different authority model from “`regenerated ... on any machine`” and “`GitHub is the source of truth`.” It is unclear whether a caller may trust its regenerated local mirror, must use the box copy, or must treat every mirror as equally disposable. That matters during fallback and concurrent refreshes. Confidence: unsure; “authoritative copy” may mean only the operational instance, but the distinction is unstated.

11. The closed-store definition—“`one line per closed issue: number, title, close reason, closed date`”—conflicts with:

   - “`Each entry carries its updated time plus an activity-relative freshness`”;
   - instructions to read a closed entry’s “`Superseded-by:` link”; and
   - maintenance of every GHI→MD reference.

   The declared closed record contains none of those fields and discards the body where links and substantive supersession information ordinarily live. Confidence: sure.

12. “`a "no issue covers X" receipt is invalid unless both files were searched`” is still invalid when the closed file contains only titles and closure metadata. A closed issue can cover X in its body or comments without mentioning X in its title; searching the declared file cannot discover it. Confidence: sure.

13. “`one updated:> query against the mirror's newest entry`” has no behavior for an absent or empty mirror, where no newest entry exists. This is the first-run case for a gitignored, per-machine regenerated store. Confidence: sure.

14. “`Mirror writes go temp-then-rename, so concurrent refreshes are safe`” overclaims what rename supplies. Two refreshes can both read generation A, independently build B and C, and let the later rename overwrite the fresher result. With two separately renamed files, readers can also observe `issues-open.md` and `issues-closed.md` from different generations. Confidence: sure.

15. “`pair-MD edits ... enter the corpus when they land on main`” defines no destination or loading procedure for them. The mirror has only issue files, cold start loads only `issues-open.md`, and resume prompts carry changed-issue numbers rather than changed-MD paths. The git feed can detect a commit but cannot make its document content available under the stated mechanism. Confidence: sure.

16. “`activity-relative freshness — project events since this issue last moved`” does not define which events count, how they are ordered, the field’s rendered form, or how events from the issue and git feeds combine. Different implementations can produce incompatible freshness numbers, and the agent cannot interpret the number consistently. Confidence: sure.

17. “`transcript size`” is an unspecified recycle trigger: no unit, measurement source, transcript path, or comparison rule is given. The later value “`set at build from NM's working values`” is also unavailable from the explicitly referenced `nedsmessenger/adapter/adapter.py`; that implementation contains runtime watchdog timeouts but no transcript-size recycling threshold. Confidence: sure.

18. “`two request forms`” conflicts with the cold-start prompt’s “`Requests arrive in four forms`” and with the later reading-list, adjudication, drift-recheck, and link-repair templates riding the same wrapper. A builder cannot determine which forms the wrapper must route and persist. Confidence: sure.

19. “`If another ask holds the session, cold-start a throwaway session instead`” does not define an atomic claim operation. Without a lock or compare-and-set mechanism, two callers can both observe the stored session as free and resume it concurrently—the exact unsafe case the branch claims to avoid. Confidence: sure.

20. “`every returned pointer is verified against the mirror`” defines handling only for an unexpected closed pointer. A nonexistent, deleted, transferred, malformed, or non-issue pointer has no stated disposition, although all are reachable verification failures. Confidence: sure.

21. “`a killed run is a named failure`” never supplies the name or output form. Callers therefore cannot distinguish that promised outcome from authentication failure, malformed output, timeout, or a generic nonzero exit. Confidence: sure.

22. “`the write-time adjudication catches new instances`” and “`Bypassed writes still appear in the delta, where the sweep finds their symptoms`” leave duplicate detection incomplete. Write-time adjudication cannot catch pre-existing pairs or fail-open/bypassed writes, while the sweep is defined to check length, markers, and links—not semantic duplication. Confidence: sure.

23. “`In-repo paths cited in the body must resolve on main`” does not define the recognized citation syntax or “resolve”: Markdown targets, plain code-formatted paths, repository URLs, fragments, line suffixes, generated paths, and examples can be classified differently. The check is not reproducibly implementable from this design. Confidence: sure.

24. “`Length measurement`” and `BODY_WORD_LIMIT` lack a definition of “word” for Markdown. URLs, code blocks, YAML, HTML, punctuation, and hyphenated tokens produce different counts under ordinary algorithms, changing which writes trigger remediation. Confidence: sure.

25. “`what to link comes from asking ghi-info`” and “`Ask ghi-info what to link`” name a request form that does not exist. Reading-list requests return issue numbers, the agent’s scope excludes MD knowledge, and none of the four prompts asks it to select a pair-document path. Confidence: sure.

26. “`a comment cannot be mechanically rewritten into the body edit ... only the author knows`” is broader than can hold. A structured request that explicitly names the target section and replacement text is an ordinary counterexample. The general policy may reject automatic rewriting, but the literal impossibility and exclusive-knowledge claims are false. Confidence: sure.

27. “`resubmit through the tool's comment verb`” gives no command name, arguments, event-kind syntax, validation rule, or result semantics. A future agent cannot invoke the legitimate-comment path from this document. Confidence: sure.

28. “`the override audit showing overrides used to dodge the tool rather than answer genuine breakage`” relies on an undefined audit. The document gives no store, record format, cadence, actor, or rule by which intent is classified; the referenced guard consumes a marker and does not itself provide this audit. The accepted residual’s only reopening trigger is therefore untestable. Confidence: sure.

29. “`The sweep is script work riding the two feeds`” defines no script name, path, invocation trigger, or cadence. “Sweep” is also too generic to locate reliably by search. None of the maintenance guarantees has an executable starting point. Confidence: sure.

30. “`Findings spawn one-shot focused fixer agents`” conflicts with “`ghi-info repairs links only`” and the later “`Link-repair request (sweep → ghi-info)`.” Since link-integrity failures are findings, the text assigns them both to fixers and to `ghi-info`. Confidence: sure.

31. “`issue #31 moved ... its pair MD has not: update the MD`” treats timestamp ordering as proof of semantic staleness. A label change, close reason, milestone change, or irrelevant comment moves the issue without making the MD stale. The fixer’s exact final contract has no “already current/no change” outcome, forcing such a fixer to lie with `done` or misuse `blocked`. Confidence: sure.

32. “`Fixers write through the normal path and consult ghi-info like any GHI author`” conflicts with “`the sweep ... embeds the reading list in the brief — the fixer invokes nothing`” and the pair-document fixer’s “`You do not write to any issue`.” It is unclear whether fixers call `ghi-info`, invoke the issue tool, or only edit the supplied document. Confidence: sure.

33. “`The sweep fills every slot, including the reading list, which it gets by running ghi-info-ask.py`” has no branch for the explicitly recognized failed-ask case. A timeout, unavailable model, or malformed answer leaves a required prompt slot without content and no stated spawn/skip/fallback outcome. Confidence: sure.

34. “`A blocked fix escalates as one draft-labeled issue`” names neither the actor that files it nor a consumer for the fixer’s `blocked:` response. It also records no suppression state, so the next sweep can rediscover the same defect, spawn another fixer, and create another escalation indefinitely. Confidence: sure.

35. “`Which model and runtime serve each role best — ghi-info, fixers, adjudication`” treats adjudication as a separately selectable role, while the ask-path design makes it another request sent to the one stored `ghi-info` session. Separate runtime/model selection is incompatible with that single-session mechanism unless “role” has a different, unstated meaning. Confidence: unsure because “role” may mean workload category rather than separately instantiated agent.

36. The Division of labor’s repeated cost “`free`” is literally false for scripts, which consume latency, CPU, network calls, and API quota. The surrounding discussion suggests “no model call,” but the `Cost` column never defines that narrower unit. “`context already loaded`” is likewise not guaranteed for a cold-spawned GHI author. Confidence: unsure because the intended token-cost shorthand is inferable.

37. “`Every prompt this design depends on, verbatim`” conflicts with the write replies’ placeholder “`<the audited one-use override line, per the instruction-file-guard pattern>`.” That is a description of missing text, not the verbatim issue-write override, and the referenced guard’s actual message concerns instruction files rather than GitHub issues. Confidence: sure.

38. “`Each opens for a zero-context reader`” is false for the drift notice, resume ask, adjudication preamble, and link-repair request. They depend on a prior cold-start prompt, stored conversation, wrapper semantics, and repository state not stated in their opening text. Confidence: sure.

39. “`document-side changes are committed on your branch`” gives no path by which those commits reach `origin/main`. Maintenance scans main, so a locally committed repair remains broken from the sweep’s perspective and can be spawned again. In the over-length job, the issue edit is a live remote mutation while the companion document is only a branch commit; failure between the two leaves an unhandled cross-store half-state. Confidence: sure.

40. “`a dated ruling`” is not a syntactic marker, and “`the record`” in “`the record does not resolve`” has no defined scope. Dates occur in ordinary status and history prose, while the possible record could mean the issue, pair document, related issues, git history, or decision trail. Fixers can block valid changes or alter protected decisions depending on their reading. Confidence: sure.

41. “`Nothing removed from the body may be lost: it must land in the pair document`” is an overbroad absolute. Removing duplicated, obsolete, accidentally pasted, or demonstrably false text is an ordinary counterexample; the rule requires preserving it as substantive project documentation. Confidence: sure.

42. “`creating [the pair document] if it does not exist`” is incompatible with the reference check and pair sequence unless the document first lands on main. The fixer brief says only that document changes are committed on its branch, while the body summary must cite where ruled text went and the issue edit goes through the tool that rejects branch-only paths. The stated actions do not form a complete executable sequence. Confidence: sure.

43. “`Read this file whole now, before anything else`” is impossible if read literally because the runtime has already processed system instructions, its startup prompt, and applicable instruction files before receiving this prompt. Confidence: unsure; “before anything else” may idiomatically mean before doing request work.

44. “`Never call GitHub — no gh, no API, no web`” directly conflicts with request form 4: “`Issue edits go through gh as normal`.” The same cold-start prompt gives both commands to the same agent, so an issue-side link repair cannot obey both. Confidence: sure.

45. “`Closed issues belong in a reply only when the request says closed history is wanted`” conflicts with the post-check rule that, after one recheck, “`Whatever remains is delivered with truthful tags`.” On an ordinary request, a still-returned closed pointer must simultaneously be omitted and delivered. Confidence: sure.

46. The two exact boundary replies conflict for a question such as whether an old ruling in the wiki still binds: “`reply exactly: out-of-scope`” and “`Reply: escalate: <one sentence...>`” both apply. The agent cannot satisfy both exact-output requirements. Confidence: sure.

47. “`the asker's question passes through verbatim, never rewritten`” and “`The draft body passes through verbatim`” place untrusted instructional text directly into model prompts without a stated data boundary or precedence rule. An issue body containing quoted commands such as “reply `verdict: unrelated`” can control the adjudicator; malformed-output manipulation also becomes fail-open. Confidence: sure.

48. The adjudication request asks whether “`the corpus already covers it`” but never enables closed-history search. This conflicts with the rule that an absence claim is invalid unless both mirror files are searched. `verdict: unrelated` is such an absence claim, yet the adjudicator normally sees only open issues. Confidence: sure.

49. The write tool handles both creates and edits, but its refusals are create-specific:

   - “`file now without the reference`”;
   - “`do not file a new issue`.”

   During an edit, no issue is being filed. The too-similar edit case also gives no disposition for the original issue being edited, leaving its relationship to the merge target unresolved. Confidence: sure.

50. “`comments do not land as comments here`” conflicts with the same reply’s legitimate-event route through “`the tool's comment verb`,” whose purpose is evidently to land a comment. The phrase “`the body edit that requires`” is also grammatically incomplete: “that” has no workable predicate/object, so the stated reason cannot be read literally. Confidence: sure.

51. “`issues are never deleted`” conflicts with both “`Every deny path ... ends with the audited one-use override`” and the accepted raw-write holes (`gh api`, MCP tools). A user-approved override or an unhooked API deletion is an ordinary counterexample. Confidence: sure.

52. “`Each with its failure branch`” is false for verification item 7, “`Comment-fetch cost at real volume`.” It supplies neither an acceptable bound nor any outcome when the measurement is too costly. Item 5’s “`do not confuse authors`” similarly has no observable pass/fail criterion. Confidence: sure.

53. The failure branch “`else the recycle-time rewrite bounds the lag`” overlooks that the `closes-since-birth` recycle trigger itself depends on observing closes. If close does not move `updated`, the stated delta cannot count those closes; one of the three trigger mechanisms silently ceases to function. Confidence: sure.

54. “`updatedInput combined with additionalContext`” introduces `additionalContext` only in build verification. No earlier mechanism says what context would be injected, where it is consumed, or why it is required; “`context injection goes unused`” therefore refers to an undefined feature. Confidence: sure.

clean sections: The three-layer stack; Deliberately not in version 1
