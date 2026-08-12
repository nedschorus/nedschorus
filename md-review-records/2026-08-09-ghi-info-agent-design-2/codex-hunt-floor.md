<!-- provenance: runtime=codex model=gpt-5.6-terra effort=xhigh cell=defect-hunt tier=floor target=/Users/el/Projects/nedschorus/.claude/worktrees/shared-conversation-discussion-eb34e2/docs/drafts/ghi-info-agent-design.md -->

1. `status: design awaiting the user's walk (md-review first)` — `md-review` and the remaining “walk” are not defined, located, or given a completion condition. A future agent cannot determine what work remains or when this status may change. Confidence: sure.

2. `# ghi-info — the GHI knowledge agent (design)` conflicts with the checkout’s naming rule. This file defines the new name as two parts (`ghi` + `info`), while `CLAUDE.md` says: “When creating or inventing names … use explicit, clear and precise multi-part names … with 3 or 4 parts, not 1 or 2.” `info` also does not distinguish this agent’s answering, graph-maintenance, and write-adjudication roles. Confidence: sure.

3. `“the corpus fits in its context window.”` — “corpus” includes closed issues, but the session later loads only the open file and admits closed issues only on demand. No context-window size, corpus-size bound, or overflow behavior is stated. This becomes impossible to obey when the open corpus exceeds the runtime’s context capacity. Confidence: sure.

4. `“Mechanical work never spends agent tokens: scripts fetch, format, measure, and filter for free; the agent spends tokens only on judgment.”` — loading the whole open mirror consumes model input/context tokens, and scripts consume compute, storage, API quota, and elapsed time. The absolute accounting claim obscures the capacity and cost that drive the design’s own tiering and recycling decisions. Confidence: sure.

5. `“Pointers fail visibly (a bad one costs one read); prose syntheses fail invisibly …”` — an incorrect but open, readable issue pointer does not fail visibly and can misdirect work; the later post-check filters only closed pointers. Conversely, a synthesis with explicit source references can be checked. The claimed failure distinction is false in ordinary use. Confidence: sure.

6. `“every GHI→MD reference resolves; every pair MD backlinks its correct GHI(s).”` — the document never defines the reference grammar, the universe of MDs that qualify as “pair” MDs, or how correctness is determined when a backlink is absent or points at the wrong issue. The link-integrity mechanism therefore cannot execute its stated checks in those reachable cases. Confidence: sure.

7. `“ghi-info flags and never fixes: the repair belongs to the next agent with authoring context.”` — no flag destination, durable record, recipient, or consumption point is defined. A headless agent can exit after discovering drift, and no later authoring agent is guaranteed to receive the finding. Confidence: sure.

8. `“answers only from the issue corpus — asked about the wiki or the code, it says so rather than guessing.”` conflicts with the required bare-list answer form in the same section and the wrapper’s instruction to “print the bare list.” A refusal/explanation is not a bare issue list; no output contract selects one behavior. Confidence: sure.

9. `“issues-open.md”` and `“issues-closed.md”` are newly defined two-part filenames, conflicting with `CLAUDE.md`’s quoted requirement for newly invented filenames to use “3 or 4 parts, not 1 or 2.” Confidence: sure.

10. `“every open issue near-raw”` and `“one tiered line per closed issue”` do not define the fields, rendering, truncation, escaping, or search semantics. In particular, an absence search cannot be trusted if a closed issue’s substantive terms are omitted from its unspecified “tiered line.” Confidence: sure.

11. `“the closed file joins in exactly two cases”` and `“the path, not an instruction, keeps them out”` — a separate pathname does not prevent an agent or script from reading the file. Other ordinary work, such as investigating an open issue’s closed successor or validating an MD backlink, can also require it. The “exactly” claim is broader than the described mechanism can enforce. Confidence: sure.

12. `“a gitignored conventional path in any checkout”` — no path or discovery rule is provided, so a future agent cannot find, create, or share the mirror. “Any checkout” is also false for an unwritable, ephemeral, or credential-less checkout, and “Derived churn never enters git history” is defeated by an intentional force-add. Confidence: sure.

13. `“updated:> the mirror’s newest entry”` leaves an equality-boundary case unstated. An issue updated after a refresh begins but with the same timestamp as the recorded newest entry can be excluded by the next strict-`>` query. Confidence: unsure — this depends on GitHub’s timestamp precision and uniqueness guarantees, neither of which the document states or verifies.

14. `“A second feed — git log since last run — covers pair-MD edits”` lacks a durable checkpoint definition and a failure/atomicity rule across the GitHub and Git feeds. A partial refresh can advance one view while the other fails, leaving a later run unable to know which MD changes remain unseen. Confidence: sure.

15. `“an activity-relative freshness (how much of the project has moved since this issue last did)”` does not define what counts as project movement, how it is measured, or the numeric result. A script cannot calculate the proposed freshness field consistently. Confidence: sure.

16. `“Supersession is an explicit marker naming the successor, written at change time by the agent that knows”` does not say where the marker lives, which agent has authority to write it, or what happens when a raw write, later discovery, or unavailable agent means it was not written at change time. That makes the marker neither reliably derived nor reliably maintained. Confidence: sure.

17. `“two open issues claiming the same ground with neither naming the other is a mechanically flaggable defect.”` — grep can find an absent marker only after someone has identified that two issues claim the same ground. Semantic overlap is not mechanically defined here, so the claimed mechanical detection is impossible as written. Confidence: sure.

18. `“the Ubuntu box (`~/agents/ghi-info` per the box convention) … Mac-side callers reach it over SSH, the path the launch-claude work built.”` — “the box,” its convention, SSH endpoint, and “launch-claude work” are all unexplained references. A future agent cannot locate or invoke this service from the supplied context. Confidence: sure.

19. `“a session id, transcript, and the mirror persist”` — the session-id store, transcript location, ownership, update behavior, and recovery behavior are not defined. The next section depends on resuming that stored id, so losing or racing this state has no specified outcome. Confidence: sure.

20. `“A cold start loads `issues-open.md` whole”` — no limit, measurement, or behavior for an oversized open file is stated. This leaves a reachable growth case with no executable session policy. Confidence: sure.

21. `“issues loaded while open linger in context after they close, and the agent cannot notice.”` — the wrapper later supplies changed issue numbers on resume, and the agent could inspect the refreshed mirror. “Cannot notice” is an unjustified absolute and conflicts with the described changed-issue signal. Confidence: sure.

22. `“All three are config constants tuned in live use.”` — none of the three constants, units, initial values, stale-match denominator/window, or configuration location is given. A builder cannot decide when any recycle trigger fires. Confidence: sure.

23. `“One wrapper script, run by any agent”` — no command name, location, input contract, session-store transaction, or concurrency behavior is provided. Two callers can concurrently resume the same stored session or update the same mirror/checkpoint, with no defined serialization or recovery. Confidence: sure.

24. `“delta-refresh the mirror (free, so the agent always wakes current)”` conflicts with the recycling section’s admission that stale closed issues remain in resumed context. It is also false during refresh failure or an update racing immediately after the refresh. Confidence: sure.

25. `“a returned pointer to a closed issue is filtered out with a note before the asker sees it”` conflicts with the mirror policy’s explicit closed-issue precedent hunt, where a closed issue may be the required answer. It also conflicts with “print the bare list,” because the note has no allowed output form. Confidence: sure.

26. `“nedsmessenger runs this exact pattern live”` is false relative to its explicitly cited `adapter.py`. That implementation injects first-call channel history and uses separate idle-silence, in-flight-tool-silence, and total-runtime watchdog conditions, while this design specifies one overall timeout. Calling the patterns exact hides a material operational difference. Confidence: sure.

27. `“The fallback ladder: ask → grep the mirror → `gh` search; then proceed under the ordinary rules.”` — “ordinary rules” is undefined here, and the sentence gives no behavior when the mirror and `gh` search are unavailable or inconclusive. This is the failure path most likely to occur alongside the stated box-auth failure. Confidence: sure.

28. `“Agents write issues with `gh` exactly as trained; the machinery makes the right thing happen without asking them to change”` conflicts with the required post-write lean split and the denied-comment retry, both of which explicitly require the writer to take another action. It is also contradicted by the admitted unwrapped write paths. Confidence: sure.

29. `“a PreToolUse hook rewrites … into the project write tool … [which] writes via `gh` internally”` leaves the tool’s own internal `gh issue create`/`edit` invocation unexcluded from the same hook. The reachable result is self-interception and recursion; no bypass condition is stated. Confidence: sure.

30. `“consults ghi-info with the actual draft body”` is not defined for the prescribed `--body-file` write form in the referenced `ghi-write` draft, especially when the body file is local to a Mac-side caller and ghi-info is on the Ubuntu box. The document gives no body-reading or transfer behavior, including unreadable-file failure. Confidence: sure.

31. `“replies in a form that cannot confuse an agent that believes it ran `gh`.”` — this is an absolute guarantee with no defined output compatibility contract, and the document itself lists `gh` output mimicry as unverified at build. An agent expecting normal `gh` output can interpret altered prose as failure or retry a successful write. Confidence: sure.

32. `“Over the limit”` and `“the length limit”` — no threshold, counting unit, or source of truth for the limit is defined. The tool therefore cannot determine whether the required lean-split action applies. Confidence: sure.

33. `“Issue bodies stay lean summaries-plus-links”` is broader than the system can ensure: the document permits one-use overrides and admits raw `gh api`, MCP, and creative-quoting bypasses; it also relies on a writer performing a post-write correction. Those ordinary cases leave a long issue body in place. Confidence: sure.

34. `“a fixed catalog (instance outcome, completion, ruling challenge; growth only by explicit ruling)”` conflicts with `“One catalog detail is open … whether ‘completion’ collapses into close-with-reason.”` The catalog is not fixed while one of its terms and its distinctness remain undecided, so a future agent cannot know whether `completion` is a valid event kind. Confidence: sure.

35. `“resubmit through the tool’s comment verb”` introduces an executable operation with no command, path, accepted input, output, or failure behavior. The referenced skill draft specifies ordinary `gh` comment handling, not this verb. Confidence: sure.

36. `“Delete: denied flat, close instead”` conflicts with `“every deny path carries the audited one-use override.”` A flat denial has no exception; a one-use override is an exception. The document does not select which interpretation governs delete requests. Confidence: sure.

37. `“the audited one-use override”` and `“the audit showing overrides used …”` define an audit-dependent control without an audit record, retention location, identity/attempt semantics, reader, or review cadence. The named hardening trigger cannot be evaluated. Confidence: sure.

38. `“A hard block would make the tool a single point of failure for all issue writes”` conflicts with the next bullet’s admission that `gh api`, MCP tools, and creative quoting bypass the hook. Those paths are ordinary counterexamples to “all issue writes.” Confidence: sure.

39. `“The maintenance sweep catches what slips — an unchecked write still appears in the delta.”` — appearing in a delta does not identify that a write bypassed the tool, nor does the document define a sweep comparison that detects invalid length, references, or duplicate content. A bypassed write can therefore be mirrored without being “caught.” Confidence: sure.

40. `“`ghi-write` (skill) — the up-front layer: fires when an agent is about to file or edit”` treats the skill as an operating trigger, but its explicitly reachable draft remains “for the user’s walk” and leaves its trigger item open. No installed artifact or runtime trigger behavior is identified here. Confidence: sure.

41. `“a missed trigger costs efficiency … never correctness.”` conflicts with the admitted bypass paths and post-write corrections. An unwrapped write can create a duplicate, invalid reference, or overlong body without the backstop making it correct. Confidence: sure.

42. `“Written conventions demonstrably lose to training … instructions that arrive at the moment of action do not.”` — the second clause is an unqualified absolute. An action-time instruction can be ignored, be unavailable, conflict with higher-priority instructions, or be misapplied; the cited recurrence of comment stacking does not establish the universal opposite. Confidence: sure.

43. The Division of labor table repeatedly assigns script work the cost `free`. These repeat the false absolute cost claim from the introduction and hide the API, compute, storage, and context costs that affect the proposed architecture. Confidence: sure.

44. `“Vector or graph database … Grows back when: Never on current evidence.”` — no measurable re-evaluation condition remains despite a bounded-context design. An ordinary counterexample is growth beyond the open-file context capacity or a query need that requires durable relationship traversal; “never” gives a future agent no basis to revisit the cut. Confidence: sure.

45. `“GitHub MCP server as the write surface … Never — the tool is ours.”` — the absolute rule is broader than the stated rationale. An environment where MCP is the credentialed GitHub transport, while the project tool still owns validation and policy, is an ordinary counterexample. Confidence: sure.

46. `“One overall timeout suffices at one-question scale.”` conflicts with the cited precedent’s distinct silence and total-runtime failure modes. A long overall timeout leaves a silently stuck call blocking until expiry; a short one kills a healthy long-running call. No value or behavior distinguishes those cases. Confidence: sure.

47. `“A cross-checkout grep need the per-machine regenerate cannot meet”` is grammatically incomplete and supports incompatible readings of what the unmet “need” is. Because it is the only growth condition for a committed mirror, a future agent cannot reliably decide when this cut reverses. Confidence: sure.

48. The build prerequisites in `“`updatedInput` combined with `additionalContext` …”`, `“Codex-side pre-tool hook equivalents … unverified”`, `“`gh` output mimicry …”`, and `“Whether the box’s `gh` auth … survive unattended operation”` have no stated decision outcome if verification fails. Each can invalidate the hook, cross-runtime coverage, output contract, or service availability; the file gives no completed state for build work in those negative cases. Confidence: sure.

clean sections: none.
