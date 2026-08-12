<!-- provenance: runtime=codex model=gpt-5.6-sol effort=xhigh cell=defect-hunt tier=good target=/Users/el/Projects/nedschorus/.claude/worktrees/shared-conversation-discussion-eb34e2/docs/drafts/ghi-info-agent-design.md -->

1. Quote (frontmatter and line 8): `"status: design awaiting the user's walk (md-review first)"` and `"this file's design decisions were ruled 2026-08-07 (walk anchor with per-item dispositions...)"`

   These give incompatible lifecycle states. “Awaiting the user’s walk” says the decisions remain pending, while “were ruled” says the decision walk is complete. The referenced decision trail also says “WALK COMPLETE,” so a future agent cannot tell whether this document is approved, awaiting review, or awaiting a different undefined “md-review” walk. Work may proceed under decisions the user has not approved, or stop awaiting approval already given. Confidence: sure.

2. Quote (line 10): `"the corpus fits in its context window"`

   This is an unbounded premise for a mechanism that loads `issues-open.md` whole. No maximum corpus size, context-window size, measurement rule, or response to an oversized open corpus is stated. The ordinary counterexample is a growth spike or several unusually long issues and comment histories that make the near-raw open file exceed the selected model’s window. At that point cold start is literally impossible, with no defined transition. Confidence: sure.

3. Quote (line 10 and the cost table): `"Mechanical work never spends agent tokens"`; `"the agent spends tokens only on judgment"`; and the script cost entries marked `"free"`

   These absolutes are false under the document’s own design. Loading, reading, or receiving the script-formatted mirror and grep results consumes model input/context tokens; a grep-on-demand can also require another model/tool round. The table’s unqualified “free” additionally ignores runtime, network use, GitHub quota, and storage. These claims distort capacity and operating-cost decisions precisely when the mirror grows. Confidence: sure.

4. Quote (lines 14 and 20): `"It has three duties"` and `"For MD content that has drifted stale relative to its issue, and for issue bodies grown past the length limit while nobody was writing, ghi-info flags and never fixes"`

   The latter sentence assigns at least two duties not contained in the three-item list. Detecting semantic MD drift and detecting overlength bodies are neither answering asks, maintaining the reference graph, nor adjudicating a pending write. `"Everything else is out of scope"` intensifies the conflict. An implementer following the numbered duties will omit work that later paragraphs assign to the agent. Confidence: sure.

5. Quote (lines 16 and 40): `"The answer is a bare list ... no why-lines, no summaries"`; `"a returned pointer to a closed issue is filtered out with a note before the asker sees it"`; and `"print the bare list"`

   The visible output contract has two incompatible readings: a bare list only, or a list accompanied by a post-check note. The document does not distinguish stdout, stderr, wrapper diagnostics, or agent-visible context. A caller cannot parse the result reliably, particularly when one or all pointers are filtered. Confidence: sure.

6. Quote (lines 16 and 44): `"Pointers fail visibly (a bad one costs one read)"` and `"Bad pointers fail visibly"`

   A pointer to a nonexistent issue fails visibly, but a pointer to the wrong existing issue resolves normally and can misdirect the writer without any visible failure. That ordinary counterexample defeats the categorical claim and matters because the design expressly accepts missing-pointer residual risk on the premise that bad pointers are self-revealing. Confidence: sure.

7. Quote (line 17): `"Maintain the reference graph. Cross-links between issues, and link integrity across the issue–MD boundary in both directions: every GHI→MD reference resolves; every pair MD backlinks its correct GHI(s)."`

   This assigns an ongoing task without defining when it runs, what constitutes a “pair MD,” how the correct GHI set is determined, which references are in scope, or when a sweep is complete. Delta refresh only identifies changed artifacts; it does not establish semantic correctness. The agent can therefore work indefinitely over the corpus or stop while unresolved links remain, with both behaviors conforming to the text. Confidence: sure.

8. Quote (lines 17, 44, and 73): `"Cross-link edits are ghi-info's only write class"`; `"a writer who finds a relation ghi-info missed adds the cross-link while editing"`; and the ownership row `"Cross-link edits | ghi-info"`

   The ownership is contradictory. The prose and table assign cross-link edits to `ghi-info`, while the fallback explicitly assigns one to the writing agent. This matters when a missed relation is found: both agents can regard the other as owner, or both can make competing edits. Confidence: sure.

9. Quote (line 18): `"The write-path tool ... consults ghi-info with the actual draft body before an issue write lands. Verdicts: too similar to an existing GHI ... the write is refused"`

   For an edit, the draft will intentionally be similar to the issue being edited. The text never says that the target issue is passed to `ghi-info` or excluded from duplicate adjudication. Taken literally, a normal body edit can be refused for matching itself. Confidence: unsure because target metadata may have been intended as an implicit part of the consultation, but only the draft body is expressly named.

10. Quote (line 18): `"too similar ... related but compatible ... unrelated"`

    No executable response protocol or boundary among these verdicts is defined. The text does not cover malformed output, multiple candidate issues receiving different classifications, uncertainty, or a refusal mixed with compatible relations. A tool cannot reliably parse or prioritize the model’s judgment from these prose labels, and different implementations can write or refuse the same draft. Confidence: sure.

11. Quote (line 20): `"queue vs GHI vs pair vs bare MD — ghi-write's judgment"`

    “Pair,” “bare MD,” and the routing states are not defined or linked here, and `ghi-write` has no path in this document. Its indirectly linked draft still says its trigger walk is open. Thus a future agent has neither a settled skill nor a direct specification for the judgment that the design delegates outside its machinery. Routing can diverge before the supposedly protective layers run. Confidence: sure.

12. Quote (lines 17 and 20): `"Cross-link edits are ghi-info's only write class"` and `"never writes issue or MD substance"`

    A cross-link edit necessarily changes an issue body or MD file. “Substance” is not defined, so one reading permits those edits as metadata while another prohibits them as content. This ambiguity determines the agent’s write permissions and whether its graph-maintenance duty is executable. Confidence: sure.

13. Quote (line 20): `"For MD content that has drifted stale relative to its issue ... ghi-info flags and never fixes"`

    No criterion establishes semantic staleness. Git timestamps can show that one side changed later, but not whether the change made the other side stale. No destination, durable store, recipient, acknowledgement, or lifetime is defined for a “flag.” A headless session can detect a possible drift, exit, and leave nothing that the unspecified “next agent” will ever see. Confidence: sure.

14. Quote (line 20): `"the repair belongs to the next agent with authoring context"`

    There may be no next agent with the original authoring context, especially for old issues or abandoned work. “Next” is also undefined: next to edit the issue, next to ask `ghi-info`, or next to work anywhere in the domain. This can defer repair indefinitely while the document presents ownership as settled. Confidence: sure.

15. Quote (line 26): `"issues-closed.md — one tiered line per closed issue"`

    “Tiered” is undefined, and the fields retained in the one line are not stated. A one-line record might omit the rejected approach, terminology, links, or rationale needed for the two designated closed-issue searches. Implementers can produce mutually incompatible mirrors that all satisfy this wording. Confidence: sure.

16. Quote (line 26): `"the closed file joins in exactly two cases"` and line 40: `"a returned pointer to a closed issue is filtered out with a note"`

    The categorical “exactly two” wording conflicts with later routine use of the closed file for answer post-checking and stale-match metrics. It could instead mean exactly two kinds of search, but that narrower scope is not expressed. This matters to callers deciding whether the closed file may be opened outside absence and precedent searches. Confidence: unsure because “joins” may have been intended to mean “joins a grep,” although its grammatical scope is broader.

17. Quote (lines 26 and 40): `"an explicit precedent hunt"` and `"a returned pointer to a closed issue is filtered out ... before the asker sees it"`

    A precedent hunt is precisely a case where a closed issue can be the correct answer, yet the universal post-check removes that answer. The same problem applies to a rejected approach discovered during an absence check. The retrieval policy permits closed results while the output policy makes them undeliverable. Confidence: sure.

18. Quote (line 26): `"the path, not an instruction, keeps them out of the other forty-nine"`

    Separate filenames do not cause callers to select one file. `grep issues-*.md`, a repository-wide search, or a caller unaware of the convention reads both; the preceding prose itself is the instruction that establishes the default. Treating layout as enforcement can silently reintroduce closed results into routine checks. Confidence: sure.

19. Quote (lines 26–27): ``"`issues-open.md`"``; ``"`issues-closed.md`"``; and `"a gitignored conventional path in any checkout"`

    The filenames are generic and no directory is supplied. “Conventional path” names no convention, while the later Ubuntu seat uses a different explicit home. Because gitignored files are absent from repository search until generated, a future agent cannot locate the mirror, distinguish among per-checkout copies, or identify the generating script from these names. Confidence: sure.

20. Quote (line 28): `"one gh search call (`updated:>` the mirror's newest entry) re-fetches changed issues"`

    “Newest entry” is not a defined refresh checkpoint and has no value for an empty or corrupt mirror. The command omits result limits/pagination, state selection, timestamp precision, and the behavior when more changes exist than one search response returns. A strict `>` boundary can also miss updates sharing the checkpoint timestamp. These reachable cases can leave the derived store silently incomplete while later logic treats it as current. Confidence: sure.

21. Quote (line 28): `"A second feed — git log since last run — covers pair-MD edits"`

    `git log` covers committed history reachable from a chosen local ref; it does not cover uncommitted edits, commits on an unfetched branch, or work in another checkout. Neither the ref nor the “last run” checkpoint is defined, nor are rename, deletion, partial-update, or history-rewrite cases. Mac-side work can therefore be invisible to the Ubuntu mirror despite the categorical “covers” claim. Confidence: sure.

22. Quote (line 29): `"activity-relative freshness (how much of the project has moved since this issue last did; project activity, not calendar time, is the aging clock)"`

    The defined metric has no unit or event population. Commits, issue updates, closed issues, labels, unique artifacts, and repeated edits yield different numbers, and no branch or time boundary is stated. The value therefore cannot be computed consistently or interpreted by the agent. Confidence: sure.

23. Quote (line 29): `"Supersession is an explicit marker naming the successor, written at change time by the agent that knows; the marker is a grep-able pattern"`

    The marker’s literal syntax and placement are absent, and no described hook detects a direction change or requires the writer to add it. A fresh implementation cannot grep an unnamed pattern. Concurrent changes and raw-write bypasses also create reachable cases where no knowledgeable agent writes the marker. Confidence: sure.

24. Quote (line 29): `"two open issues claiming the same ground with neither naming the other is a mechanically flaggable defect"`

    Determining that two issues “claim the same ground” is semantic similarity judgment—the task assigned elsewhere to `ghi-info`—not something marker grep can establish mechanically. Absence of a link says nothing about whether any particular pair overlaps. The division-of-labor table nevertheless assigns the supersession sweep to a script, so an implementation following that allocation cannot perform the promised check. Confidence: sure.

25. Quote (line 33): `"the Ubuntu box (`~/agents/ghi-info` per the box convention)"` and `"Mac-side callers reach it over SSH, the path the launch-claude work built"`

    The box has no hostname, SSH identity, checkout path, invocation command, or referenced “launch-claude” artifact. `~` depends on an unnamed remote user. These phrases presume private conversation context, so a future caller cannot find or invoke the service from the allowed materials. Confidence: sure.

26. Quote (lines 34 and 40): `"a session id, transcript, and the mirror persist"` and `"resume by stored session id"`

    No state-file path, keying rule, locking rule, or atomicity/recovery behavior is defined. Because the wrapper is run “by any agent,” two callers can concurrently resume the same session, while a corrupt, expired, or missing transcript can leave a valid-looking stored ID. The referenced precedent explicitly serializes per conversation, but this design does not define equivalent serialization. Confidence: sure.

27. Quote (lines 35–36): `"Context policy: 100% open-focused"`; `"closed issues enter a turn only by grep on demand"`; and `"issues loaded while open linger in context after they close"`

    The latter is an expressly reachable way for closed content to remain in a turn without an on-demand grep. The “100%” claim is also incompatible with the permitted precedent and absence searches. Different readers can treat open focus as a preference or a hard context invariant, affecting valid answers and recycle behavior. Confidence: sure.

28. Quote (line 36): `"a closes-since-session-birth counter passing its threshold; the stale-match rate ...; transcript size. All three are config constants tuned in live use."`

    The counters and rates lack definitions: unique closes versus close events, treatment of reopen/close cycles, the stale-rate numerator, denominator and window, zero-match behavior, transcript units, initial values, and reset behavior are all unstated. “Tuned in live use” has no stopping or acceptance criterion. The wrapper therefore cannot make reproducible recycle decisions or know when tuning is complete. Confidence: sure.

29. Quote (line 40): `"delta-refresh the mirror (free, so the agent always wakes current)"`

    The refresh can fail, be partial, miss a timestamp boundary, lag GitHub indexing, or observe only the local git ref. No failure behavior establishes whether the ask stops, proceeds stale, or rebuilds. “Always” converts a best-effort refresh into a false freshness guarantee; an answer can be presented as current immediately after a failed or incomplete refresh. Confidence: sure.

30. Quote (line 40): `"prompt = the question, plus the changed-issue numbers since the last turn on resume"`

    Numbers alone do not convey whether an issue was created, closed, reopened, relabeled, or substantively edited, and the prompt does not instruct the agent to reload those entries. The document also gives no behavior for an invalid resume ID or a change list too large for the prompt. A resumed agent can retain the old body while merely knowing that some numbered issue changed. Confidence: sure.

31. Quote (lines 40 and 94): `"Auth is the box's long-lived token"` and `"Whether the box's gh auth and the long-lived Claude token survive unattended operation"`

    The ask needs Claude authentication while refresh and writes need GitHub authentication, but the operative section uses a singular, unnamed token. The verification section later confirms two distinct credentials and says the box’s authentication has expired before. Provisioning, storage, renewal, and failure classification are therefore not executable from the design. Confidence: sure.

32. Quote (lines 40, 42, and 84): `"One overall timeout"`; `"nedsmessenger runs this exact pattern live ... watchdogs on stuck runs"`; and `"Multi-watchdog process supervision ... [is] deliberately not in version 1"`

    The cited implementation has three distinct watchdog conditions, while this design explicitly cuts them in favor of one overall timeout. Calling it the “exact pattern” is false unless “pattern” is narrowed to headless resume, which the sentence does not do. An implementer may copy the precedent’s three timers or implement the stated single timer. Confidence: sure.

33. Quote (line 44): `"A failed ask never blocks a write"` and `"then proceed under the ordinary rules"`

    “Ordinary rules” are not defined here, and the absolute does not hold when the wrapper, rewrite hook, mirror refresh, authentication, or fallback `gh` call fails in a way that prevents control from returning to the writer. The later fail-open sentence covers only `ghi-info` being unreachable, not all failed-ask paths. This can turn a policy aspiration into an unsafe assumption about availability. Confidence: sure.

34. Quote (line 44): `"Self-correction needs no feedback channel: a writer who finds a relation ghi-info missed adds the cross-link while editing, and the next delta refresh teaches the corpus."`

    The issue edit plus delta refresh is itself a feedback channel. More importantly, the sentence depends on that channel being durable and observed. If the edit fails, is bypassed, lands only in an MD branch, or the writer does not own cross-link edits under the earlier allocation, no correction reaches the corpus. Confidence: sure.

35. Quote (lines 48 and 56): `"Agents write issues with gh exactly as trained; the machinery makes the right thing happen without asking them to change"` and `"gh api, MCP tools, and creative quoting slip past"`

    The first sentence promises transparent correctness for trained behavior, while the accepted holes permit unchecked writes. Comments are also deliberately denied and require a different tool verb plus explicit classification, which is a behavior change. A caller relying on the first sentence can bypass checks or be surprised by a forced retry. Confidence: sure.

36. Quote (line 50): `"the project write tool"`

    The central executable has no name, path, command syntax, input contract, or output contract. It is distinct from the named `ghi-write` skill, but the similar terms invite conflation. The rejected gate document names a superseded program, not this tool. A future agent cannot find, invoke, build, or test the write surface by search. Confidence: sure.

37. Quote (line 50): `"rewrites the gh issue create/edit invocation"` and `"consults ghi-info with the draft body"`

    `gh issue edit` also supports title-, label-, milestone-, and assignee-only edits, which have no draft body. Create can be interactive or use inline text, a file, templates, or web mode. The design provides no disposition for these normal command shapes, compound shell commands, or absent body data, so the rewrite mechanism has reachable inputs it cannot map to the adjudication contract. Confidence: sure.

38. Quote (lines 50–51): `"The tool runs the mechanical checks (body length; openable references), consults ghi-info ... writes via gh internally"` and `"the tool measures the body after the write"`

    The first sentence reads as checks-before-write, while the next expressly puts length measurement after the write. That changes whether an overlength body is prevented or temporarily committed and whether “check” means validation or notification. The ambiguity affects failure handling and what the caller may assume once the command succeeds. Confidence: sure.

39. Quote (line 51): `"Over the limit"` and `"keep a good summary in the body, move the substance to the linked pair MD"`

    No threshold, unit, summary criterion, destination naming rule, pair-identification rule, or completion test is supplied. “Good,” “substance,” and “pair MD” require unstated judgment. If the instructed writer exits, refuses, or cannot identify a pair, the overlength issue remains, and the later flag mechanism has no durable recipient. Confidence: sure.

40. Quote (lines 50 and 93): `"replies in a form that cannot confuse an agent that believes it ran gh"` and `"gh output mimicry: the tool's reply format against what agents expect from gh"` under “Verify at build”

    The first is an absolute guarantee, while the verification list says the format and expectations are still unknown. Different `gh` verbs, output modes, versions, and callers have different expectations, so “cannot confuse” is not presently established and cannot hold universally. A caller may parse the substituted output as a URL, issue number, or ordinary success string and behave incorrectly. Confidence: sure.

41. Quote (line 50): `"consults ghi-info ... [then] writes via gh internally"`

    The model turn creates a check-to-write race. Another agent can edit, close, or supersede the target after adjudication but before the internal `gh` write; an edit can overwrite newer content or a create can become a duplicate during the delay. No version, current-body, or concurrency condition binds the verdict to the eventual write. Confidence: sure.

42. Quote (line 52): `"the fixed catalog (instance outcome, completion, ruling challenge; growth only by explicit ruling)"` and `"whether 'completion' collapses into close-with-reason"`

    The catalog is simultaneously called fixed, allowed to grow, and left with an unresolved member. “Instance outcome” and “ruling challenge” have no definitions or examples, while “explicit ruling” has no authority, record, or update procedure. Two agents can classify the same content differently, and version 1 cannot know whether `completion` is a valid comment kind. Confidence: sure.

43. Quote (lines 18, 52, and 53): `"before an issue write lands"`; `"resubmit through the tool's comment verb"`; and `"Close ... passes the hook untouched"`

    “Issue write” naturally includes comments and state changes, but only create/edit adjudication is described. Comments use the tool without any stated similarity adjudication, and close bypasses it. The term therefore supports incompatible broad and body-write-only readings, changing which operations receive `ghi-info` review. Confidence: sure.

44. Quote (line 53): `"a state change with a reason (completed / not planned) ... passes the hook untouched"`

    Passing raw close commands untouched does not enforce that the caller explicitly supplies or deliberately chooses the reason. The mechanism therefore does not guarantee the requirement stated by the sentence; defaulted or omitted reasons remain reachable. Confidence: sure.

45. Quote (line 55): `"every deny path carries the audited one-use override (the instruction-file guard pattern already live on main)"`

    The override has no command, marker, storage location, consumption rule, identity binding, concurrency behavior, or audit location. “Instruction-file guard pattern” is an unexplained reference with no path and is difficult to find from the permitted context. A supposedly one-use override can be nonfunctional, reusable, consumed by another caller, or unauditable without violating any stated mechanism. Confidence: sure.

46. Quote (line 55): `"a tool bug or an unwrapped gh capability would halt the workflow"` and line 56: `"gh api, MCP tools, and creative quoting slip past"`

    An unwrapped capability that slips past the hook does not halt the workflow; it bypasses the tool. Only a capability caught and redirected to an unsupported tool path would halt. The rationale conflates uncovered and unsupported operations, obscuring whether the hardening problem is availability or enforcement coverage. Confidence: sure.

47. Quote (line 55): `"Hardening trigger, named: the audit showing overrides used to dodge the tool rather than answer genuine breakage."`

    The trigger lacks an audit cadence, evaluator, evidence rule, threshold, and definition of “genuine breakage.” One override, repeated overrides, and a disputed override can all produce different hardening decisions. There is no stopping point for the audit or live tuning process. Confidence: sure.

48. Quote (line 56): `"The maintenance sweep catches what slips — an unchecked write still appears in the delta."`

    The design defines no provenance marker or tool log by which a delta entry can be recognized as unchecked. Delta merely shows that an issue changed. Deletion does not appear as an updated issue at all, and timestamp/query limits can also omit writes. Consequently the sweep cannot provide the asserted universal backstop. Confidence: sure.

49. Quote (lines 60–61): `"so the agent is never blocked into a retry"` and `"a missed trigger costs efficiency ... never correctness"`

    Comments are explicitly blocked into a retry. For file/edit operations, a missed skill trigger can also cause incorrect routing, poor body substance, or an unsplit issue—judgments the hook expressly does not perform. Fail-open, overrides, and enumerated hook holes provide further ordinary correctness counterexamples. Confidence: sure.

50. Quote (line 61): `"the skill description stay firm rather than 'pushy': undertriggering stopped being dangerous, so the pushy register's false-trigger test debt is never incurred"`

    “Firm,” “pushy register,” and “false-trigger test debt” are neither standard terms nor defined mechanisms. The indirectly referenced skill draft still says the trigger walk is open, and the premise that undertriggering is harmless conflicts with the uncaught routing work. A future evaluator cannot determine what wording or tests this sentence authorizes. Confidence: sure.

51. Quote (line 62): `"instructions that arrive at the moment of action do not [lose to training]"`

    This absolute is broader than the evidence cited. An agent can misunderstand the teaching reply, ignore it, invoke the override, or use a bypass; the override audit’s hardening trigger explicitly anticipates deliberate evasion. The claim can lead the design to omit verification of whether the instruction was actually followed. Confidence: sure.

52. Quote (division-of-labor table): `"Freshness numbers, supersession sweep, link-integrity scan | script | free"`

    Freshness is undefined, “same ground” supersession is semantic, and backlink correctness can require deciding which GHI is the correct pair. Those are not all mechanically executable script work under the definitions given. Assigning them to a free script conflicts with the document’s own placement of relatedness and similarity judgment in `ghi-info`. Confidence: sure.

53. Quote (division-of-labor table): `"Which issues bear on a question; similarity verdicts | ghi-info | one model turn"`

    A turn that greps closed issues or inspects changed entries contains a tool call followed by additional model processing; the cited headless implementation can emit multiple assistant/tool/result cycles. Timeout, ambiguity, or a large corpus can also require more than one invocation. “One model turn” is therefore either technically false or an undefined use of “turn,” which corrupts the cost model. Confidence: sure.

54. Quote (lines 80–81): `"Never on current evidence"` and `"Never — the tool is ours"`

    These “Grows back when” entries provide no reachable growth condition. Ordinary counterexamples include the corpus exceeding the model window, retrieval quality degrading, or a future MCP write surface gaining the project’s checks and becoming easier to maintain than the custom tool. “Current evidence” can change, making “never” especially incoherent as a lifecycle trigger. Confidence: sure.

55. Quote (line 85): `"A cross-checkout grep need the per-machine regenerate cannot meet"`

    The phrase is grammatically incomplete and supports several readings: a grep “need,” a need that regeneration cannot meet, or a failed per-machine regeneration. Because this cell is the sole growth trigger for a committed mirror, the missing relationship prevents an implementer from knowing what observed condition activates the cut. Confidence: sure.

56. Quote (lines 28, 53, and 89): `"moves entries between the two files on state change"`; `"the delta feed carries it"`; and `"An issue's updated timestamp moves on close, reopen, and label changes ... (documented; untested here)."`

    The operative design relies on close/reopen/label changes entering the delta, while “Verify at build” admits that prerequisite has not been tested. The earlier 0.82-second query verification does not establish all these event types. Until verified, the mirror can retain an issue in the wrong state file while the document presents movement as settled behavior. Confidence: sure.

57. Quote (line 91): `"Codex-side pre-tool hook equivalents (the runtime has hooks; field names unverified)."`

    The design speaks generically about “agents” and claims transparent interception, but its only concrete rewrite mechanism is Claude Code’s `PreToolUse`. The Codex equivalent’s interface and ability to rewrite a shell invocation remain unverified, so the architecture is not executable for one of its stated runtimes and may have materially different coverage. Confidence: sure.

58. Quote (line 92): `"The cross-reference timeline event as the backlink source for the graph (API shape)."`

    This is the only named backlink-source mechanism, yet its API shape is unresolved and the main design never explains how timeline events map to pair MDs or current references. The earlier promise that every backlink is maintained and scanned therefore rests on an unverified input with no failure behavior. Confidence: sure.

59. Quote (line 94): `"Whether the box's gh auth and the long-lived Claude token survive unattended operation (the box's auth has expired before)."`

    This is a known reachable failure for the supposedly unattended, always-current session, but no degraded state or recovery boundary is defined. Expired GitHub auth breaks refresh and writes; expired Claude auth breaks asks. The design simultaneously treats authentication as settled in the ask section and as an unresolved reliability prerequisite here. Confidence: sure.

clean sections: none
