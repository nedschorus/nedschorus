<!-- provenance: runtime=codex model=gpt-5.6-terra effort=xhigh cell=defect-hunt tier=floor target=/Users/el/Projects/nedschorus/.claude/worktrees/linters-tool-usage-f8b0a0/docs/drafts/ghi-info-agent-design.md -->

1. `status: integrated design; ... awaiting the user's integration walk` and `design-as-of: 2026-08-09` conflict with the walk being “opened 2026-08-09” and recording 2026-08-11 rulings applied to this document. A future reader cannot tell whether the walk is pending, active, or reflected in this version. Confidence: sure.

2. `four prompts still owed there` conflicts with `Status: every prompt is final`. Both are presented as current status, with no stated transition between them. This makes the close-out gate indeterminate. Confidence: sure.

3. `The answer is a bare list` conflicts with the cold-start contract: `Reply with a bare list ... plus, only when needed, note lines in plain sentences.` The output is either list-only or list-plus-notes; “when needed” and the resulting format are not defined, so callers cannot reliably parse or present it. Confidence: sure.

4. ``verdict: related #n,#m`` permits exactly two related issues. A draft can be related to three or more issues, but no valid verdict represents that case; silently selecting two changes the promised reading guidance. Confidence: sure.

5. `The authoritative copy lives in ghi-info's checkout on the box. GitHub is the source of truth; the mirror is derived data.` “Authoritative copy” can mean the cache governs reads, while “source of truth” says it cannot. This produces incompatible recovery and freshness readings. Confidence: unsure, because “authoritative copy” may have meant only the designated cache location.

6. `issues-closed.md — one line per closed issue: number, title, close reason, closed date` conflicts with the drift instruction to read that entry `including any Superseded-by: link`. The declared closed-entry schema contains no such link, so the required redo may lack the decisive successor information. Confidence: sure.

7. `one updated:> query against the mirror's newest entry` has no defined first-run behavior. A fresh gitignored mirror has no newest entry, while the full fetch is only tied to a session recycle; a cold start with no stored session is not stated to be a recycle. Confidence: sure.

8. `Mirror writes go temp-then-rename, so concurrent refreshes are safe.` Rename prevents a torn file, not a lost update. A slower refresh based on an older GitHub response can rename after a newer refresh and replace it with stale contents. Confidence: sure.

9. `the refresh fetches origin and reads git log origin/main — pair-MD edits ... enter the corpus` gives neither a commit cursor nor a rule for mapping a changed MD to a mirror entry or sweep action. The claimed second feed therefore has no executable ingestion behavior. Confidence: sure.

10. `activity-relative freshness — project events since this issue last moved` defines a stored field without defining “project event,” its unit, its calculation, or any consumer. Different implementations can produce incompatible freshness values. Confidence: sure.

11. `<checkout>/ghi-mirror/` and `Seat: the Ubuntu box, ~/agents/ghi-info` never identify the box-side checkout. The referenced launcher creates and runs an agent directory, not a repository checkout, so the mirror path, repo reads, and hook context do not have a determined location. Confidence: sure.

12. ``scripts/ghi-info-ask.py`, run by any agent` provides no invocation contract: no question argument or input channel, result/error format, remote transport, or stated exit behavior. `--include-closed` alone is insufficient for an agent with only this document to run it. Confidence: unsure, because an implementation could choose its own CLI shape, but the document claims it is a callable shared path.

13. `two request forms` conflicts with the cold-start prompt’s `Requests arrive in four forms`, and the later link-repair request also says it rides the same wrapper. The wrapper’s supported request set is therefore unclear. Confidence: sure.

14. `If another ask holds the session, cold-start a throwaway session instead — nothing waits, nothing shares a transcript.` No atomic ownership/reservation protocol is stated. Two callers can both observe the stored session as free and resume it concurrently, violating the claimed non-sharing guarantee. Confidence: sure.

15. `every returned pointer is verified against the mirror` specifies recovery only for an unexpected *closed* pointer. A hallucinated, deleted, transferred, malformed, or otherwise absent issue number is also a failed verification, but has no defined result. Confidence: sure.

16. `Whatever remains is delivered with truthful tags ("#31 (closed 2026-08-08)")` conflicts with `Closed issues belong in a reply only when the request says closed history is wanted.` An ordinary ask that returns a newly closed pointer has two incompatible delivery rules. Confidence: sure.

17. `the agent reads only mirror files and never calls GitHub` conflicts with the same agent’s link-repair request: `Issue edits go through gh as normal.` The prompt gives no mode boundary that makes both commands legal. Confidence: sure.

18. `a killed run is a named failure` never names the failure or says what callers receive. This matters because the fallback ladder depends on recognizing an ask failure rather than treating partial output as a reading list. Confidence: sure.

19. `In-repo paths cited in the body must resolve on main ... land the MD first` applies to every in-repo path, not only MDs. An unlanded script, test, or other repository file makes the first stated branch literally wrong for the cited object. Confidence: sure.

20. `resubmit through the tool's comment verb naming an event kind` defines an allowed mechanism without defining its invocation, body input, target-issue input, output, or even a corresponding prompt form. The taught recovery path is therefore not executable from this document. Confidence: sure.

21. `Every deny path carries the audited one-use override` is not supported by the referenced `instruction-file-guard.py` pattern. That hook accepts any nonempty marker and deletes it; it neither validates that the text approves this operation nor records the approval, operation, or consumption for the claimed audit. The reopening trigger depending on an “override audit” is consequently unobservable. Confidence: sure.

22. `Bypassed writes still appear in the delta, where the sweep finds their symptoms.` The specified sweep checks length, supersession markers, links, and one-direction pair staleness. A concise raw write that creates a duplicate or conflict without a bad link or marker has no listed symptom, so the sweep does not find it. Confidence: sure.

23. `Issue #<n> changed ... Update the document to match the issue's current state` lacks a no-change completion case. An issue comment, label, or other state change may have no legitimate pair-document consequence; the brief nevertheless requires a document change and a `done` message naming changed files. Confidence: sure.

24. `fable, opus, sonnet` introduces `fable` without identifying whether it is a model, runtime, tier, provider, or project term. It is generic enough to be difficult to locate by search. Confidence: sure.

25. `is an open question, settled empirically` supplies no experiment, comparison basis, metric, decision owner, or stopping condition. A future agent cannot determine when that open question is settled. Confidence: sure.

26. `The body edit goes through gh as normal. Document changes are committed on your branch` omits the ordering required when Template B creates a pair document and the body must cite where ruled text moved. A body-first edit can fail the main-resolution check; a branch-only document is not on main. Confidence: sure.

27. `<the audited one-use override line, per the instruction-file-guard pattern>` is an unfilled dependency in every refusal template, despite `Every prompt this design depends on, verbatim` and the prompt status being final. The referenced hook contains a multi-sentence denial message, not a defined one-line slot value. Confidence: sure.

28. `issues are never deleted — the record is append-forward` is broader than this design can guarantee. The document explicitly accepts unhooked `gh api`, MCP, and quoting paths; a repository administrator using a non-hooked deletion surface is an ordinary counterexample. Confidence: sure.

29. `Retrieval quality measurably degrades`, `The closed-file treatment no longer suffices`, and `The single timeout proves too blunt` are grow-back triggers with no metric, baseline, test, or decision endpoint. They require future work but do not state when it is complete. Confidence: sure.

30. `Each with its failure branch:` is false for `Comment-fetch cost at real volume (measured once: 0.42 s for one issue with comments).` That verification has neither a passing bound nor a failure branch. Confidence: sure.

31. `the sweep checks validity and flags expiry before it bites` adds credential monitoring, but the sweep definition and division-of-labor table contain no such check, owner, cadence, or handling for either the `gh` credential or the Claude token. Confidence: sure.

32. `stale-match 2 in the last 10 answers` leaves “answers” undefined once the wrapper handles reading lists, adjudications, drift redos, and link repairs. Counting all replies can suppress recycling during write-heavy traffic; counting only reading lists yields a different trigger. Confidence: sure.

33. `transcript threshold set at build from NM's working values` cites a source that has no transcript-size or session-recycling threshold: the referenced `ask_claude` implementation has watchdog timeouts but keeps its session. The proposed value therefore has no stated source or build-time stopping point. Confidence: sure.

clean sections: The three-layer stack; Division of labor; Resume ask prompt.
