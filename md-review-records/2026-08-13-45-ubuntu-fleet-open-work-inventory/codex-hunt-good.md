<!-- provenance: runtime=codex model=gpt-5.6-sol effort=xhigh cell=defect-hunt tier=good target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/issues/queue/45-ubuntu-fleet-open-work-inventory.md -->

1. “the thread map and the context-file paths stay useful.” This is an unbounded durability claim about machine-local files. Transcripts can be pruned, renamed, or moved with the agent homes, and the map already omits the two active seat transcripts. A future reader may rely on a path that no longer identifies the current context. Confidence: unsure, because “stay useful” might only mean “age more slowly than PR status,” but that limit is unstated.

2. “Every seat document has been md-reviewed, twelve in all, and each review's findings applied to the document it reviewed.” Only nine files exist under `docs/agents/`, so “seat document” does not identify the alleged set of twelve. More importantly, repository history shows review corrections still landing after this 22:33 snapshot, including the doctrine correction at 22:40, while several grids remained queued. The sentence therefore supplies neither a reproducible set nor a true completion state. An agent may skip unfinished first-pass work. Confidence: sure.

3. “the briefs used *pile*, *walked approval*, *instruction-class*, *slice* and the C-numbers as if established, and none was defined anywhere. The seat model now defines them once.” “None was defined anywhere” is too broad: slice and the C-number rulings already had definitions in the gatekeeper documents. “Defines them once” also supports incompatible readings because `seat-first-prompt.md` and individual briefs repeat some definitions. This matters when deciding which text is authoritative. Confidence: sure about the overbroad first claim; unsure whether “once” means once inside the seat model or once across the checkout.

4. “every document written that day was stamped `2026-08-14`” has no stated domain for “every document.” Ordinary counterexamples are unrelated documents or commits written that day with the correct date. If it means only the twelve reviewed documents, that set is not named. Confidence: unsure because the intended local scope is inferable but not expressed.

5. “the branch-already-exists path that any relaunched seat takes.” Section 6a later says the launcher skips worktree creation when the seat home is already a checkout. A normal relaunch therefore does not take the branch-creation path at all; another relaunch may occur after the branch was removed. This overstatement can send diagnosis toward a path the launcher never exercised. Confidence: sure.

6. “Still owed: a second-pass review … starting with `seat-first-prompt.md`, `agent-seat-model.md` and `gatekeeper-instructions.md`.” “Starting with” establishes no complete work set or stopping point. The file does not name every document changed after review or provide a way to determine that set, so an agent cannot know when the stated debt is discharged. Confidence: sure.

7. “a third stream” is not an identifiable owner name. It supplies no agent, job ID, transcript, branch-independent label, or mapping elsewhere in the file, and searching that generic phrase cannot reliably find an owner. Work associated with PR #55 cannot be routed from this row. Confidence: sure.

8. The PR #55 and PR #57 rows under “Open pull requests,” together with “All five are open,” were already false at the snapshot. The checkout records PR #57 merged at 21:28 and PR #55 merged at 22:04, before this document’s 22:33 commit. This is stale-at-creation state, not later staleness of an otherwise valid snapshot. It causes already-landed work to be reviewed or assigned again. Confidence: sure.

9. “## 1. Open pull requests” and “All five are open” present the table as exhaustive, but the same file says corrections are in PR #58 and repeatedly says #58 has not merged. Thus the file itself establishes at least one omitted open PR. Confidence: sure.

10. “They do not conflict: different files, different branches.” Separate branches do not prevent either textual conflicts at merge or semantic conflicts across different files. An ordinary counterexample is one PR changing a supervisor and another changing the contract or instructions consumed by that supervisor. The offered grounds establish isolation, not compatibility. Confidence: sure.

11. “The sanity-checker grid seat” overloads “seat.” Elsewhere a seat is a running named agent such as `sanity-checker`; here it can mean either that agent or one or three reviewer slots in the md-review grid. The two readings assign different things to the grid and make “joins … as three stance attacks” unclear. Confidence: sure.

12. “Which comes first — that grid-seat walk, or triage of the novel findings below. This is the question `ea663864` asked and never got answered.” Section 0 already says the sanity-checker “is triaging its four findings,” so the ordering has been acted on. Its explicit brief also directs triage before the walk. Leaving this under decisions waiting on the user can stall or reopen work whose order is already settled operationally. Confidence: sure.

13. “The gatekeeper's remaining road, all user-gated: the walked-approval evidence format, then build slice 6 … then the credential work.” “All user-gated” can mean either that the user must perform all of it or merely that there are user checkpoints. The referenced gatekeeper brief says the agent builds slice 6 and can prepare the Unix-user portion of credential work in parallel; only specified GitHub acts require the user. The strict sequence and blanket gate can make the agent wait instead of doing available preparation. Confidence: sure.

14. “## 3. Un-triaged novel findings” presents the four bullets as the untriaged inventory, but the cited scorecard lists many more novel findings in its “Novel findings” and “Fresh-eyes yield” sections. This file gives no disposition explaining why those other findings are triaged, rejected, out of scope, or deliberately discarded. A reader cannot know whether the inventory is selective or incomplete. Confidence: unsure because an unstated prior selection may have occurred.

15. “never presented” omits the recipient and is false literally: the findings are presented in the cited scorecard and again immediately below. If it means “never presented to the user for a ruling,” that narrower state matters operationally but is not stated. Confidence: unsure because that narrower meaning is likely.

16. “the cells read archived snapshots” is false for all four findings. The gate-edits-the-gate and wedged-session findings came from fresh-eyes cells that received problem statements in scratch directories, not archived code snapshots. This gives the wrong provenance and therefore the wrong reason and procedure for verification. Confidence: sure.

17. “each needing verification against current code” conflicts with the bullets’ confident current-tense claims: “the suite now exists,” “the gate runs no checks today,” “No gate-edits-the-gate guard,” and “stalls below the recycle threshold with no watchdog.” The text simultaneously marks these as unverified and states them as established facts. A skimming agent can carry the claims into a walk without performing the required verification. Confidence: sure.

18. “No gate-edits-the-gate guard.” The coined phrase supports several materially different readings: the executing program can modify itself, a candidate can change gatekeeper source, or candidate-supplied checks can weaken themselves. It also fails to connect the concern to slice 6, already named in the preceding section as a review-evidence check. The agent cannot tell which residual is novel. Confidence: sure.

19. “A writer-stamps-the-pin proposal” leaves both nouns unbound: it does not identify the writer, record, pin, repository, or producing mechanism. The coined label differs from the scorecard’s searchable name, “Pin-stamp.” This prevents a future reader from locating the exact proposal or deciding which code and owner to inspect. Confidence: sure.

20. “Twenty-four open.” The four grouped rows enumerate 30 distinct issue numbers: 6 fleet, 11 review, 4 tooling, and 9 doctrine/research. Either the total is wrong or six listed items are not open, but the file does not distinguish those cases. Confidence: sure.

21. “GHI and tooling” introduces an unexplained project acronym. “GHI” can mean GitHub Issues, a named subsystem, or something else; `ghi-info` does not resolve that ambiguity by itself. This matters when choosing the owning context and documents. Confidence: unsure because the issue number and repository search may reveal the intended expansion.

22. “#32 (what NC preserves)” introduces the two-letter name “NC” without expansion or path. It is not self-documenting and produces noisy searches across a repository. A zero-context reader cannot tell whether it names nedschorus, another system, or a specific tool. Confidence: sure.

23. “Transcripts are the durable context. A new session can be pointed at any of these” and “point the new session at … the transcript instead” leave a critical size limit ambiguous. If “pointed at” means supplying the transcript itself through `--first-prompt-file`, the supervisor reads the whole file and passes it as one process argument; the listed 3.6 MB and 8.7 MB transcripts exceed this host’s 2 MB argument limit before model context limits are considered. If it means giving the agent a small prompt containing the path, the file never says that. Confidence: unsure because the latter reading is executable.

24. The “Thread map — where each thread's context lives” omits the two running seats’ actual current contexts. The gatekeeper row points to the authoring `gatekeeper-walk-fork` stream, not the active `~/agents/gatekeeper` session; the only sanity-checker row is explicitly retired. Both active transcript directories and files existed at the snapshot. A successor following the map resumes the wrong or retired thread. Confidence: sure.

25. “live; PR #57 open” repeats the false PR #57 status after its merge had already occurred. Here it additionally corrupts the thread-state column, making a live session appear to have outstanding PR work it no longer has. Confidence: sure.

26. “live, blocked on the ruling above” does not identify which ruling. The preceding section associates `ea663864` both with the grid-adoption ruling and with the unanswered ordering question. A resuming agent cannot tell which question actually blocks the stream. Confidence: sure.

27. “duplicate of the choirmaster stream; resolve against `ea663864`” does not define “resolve”: compare transcripts, merge context, retire one, delete one, or verify equivalence. It names no output or stopping condition. The instruction therefore cannot be completed deterministically. Confidence: sure.

28. “All 35 transcripts over 30 KB were read for their titles” does not support “Everything else is accounted for” or “none needing an owner.” Titles alone cannot establish that a predecessor or maintenance session contains no unhanded open work, and the size floor excludes an ordinary counterexample: a complete task in a 29 KB transcript. The absolute conclusion is broader than the sweep described. Confidence: sure.

29. “`--first-prompt-file <path>` … reads that file as the new session's first prompt and then reverts to ordinary ignition.” The mechanism does not cover an already-running name: the launcher attaches, creates no new session, and the option has no effect. “Ordinary ignition” is also undefined, so the reader cannot tell what replaces the first prompt or when. These reachable cases matter because several names in this file are live or resumable. Confidence: sure.

30. “`cp ~/.claude/handoffs/<old>-handoff.md ~/.claude/handoffs/<new>-handoff.md` before launching `<new>`; its supervisor picks it up as if it were its own.” Plain `cp` overwrites an existing destination handoff, potentially destroying a paused seat’s only current context. The copied content can also contain old-seat paths and branch instructions, and an existing supervisor state may regard its counter as consumed. None of those reachable cases is stated or excluded. Confidence: sure.

31. “a handoff written by a forked session describes that session's state when it wrote the handoff, not the fork point.” This is categorical about file content that the mechanism cannot guarantee. A handoff may deliberately describe the fork point, or it may be written immediately after forking while the two states are identical. Treating the distinction as guaranteed can make an agent discard the appropriate artifact. Confidence: unsure because this may describe a local writing convention rather than a mechanical guarantee.

32. “status line present (which is the tell that project settings loaded, and therefore that the recycle hook and the instruction-file guard loaded too).” A visible status line proves neither hook is configured or operational. Ordinary counterexamples include a status line inherited from user settings, a missing hook script, or a settings file containing the status line but not one hook. This can falsely certify a seat that cannot recycle or protect instruction files. Confidence: sure.

33. “What was done instead, and what to undo once #58 merges” conflicts with “No action is needed” and “the reset is then unnecessary.” The section never identifies anything that actually must be undone. A reader cannot distinguish an expiring workaround from a required cleanup. Confidence: sure.

34. “The Mac twin runs locally on the box and is mechanically identical to the Ubuntu launcher minus the SSH hop.” The referenced scripts are not mechanically identical: the local launcher performs different prerequisite checks, derives repository and supervisor paths differently, and has different preparation and quoting behavior. Its own header also explicitly describes it as the Mac launcher and directs box work to the Ubuntu launcher. Assuming equivalence can hide platform-specific failures. Confidence: sure.

35. “Once #58 merges, those branches become strictly behind and fast-forward normally. No action is needed unless #58 is changed substantially before merging.” This only follows if #58 is merged with the seat commits preserved as ancestors and the seats add no divergent commits. A squash/rebase merge or ordinary seat work creates divergence even when #58’s content is unchanged. The branch-sync mechanism then refuses to fast-forward. Confidence: sure.

36. “the seats should be relaunched from the merged main” and “relaunch it from the PR branch” are not executable with the procedure given. The launcher explicitly skips worktree creation when the existing seat home is already a checkout, so merely relaunching preserves its current branch and ancestry. The file supplies no operation that makes either stated source take effect. Confidence: sure.

37. “Three seats, chosen so no two touch the same files or branches” is already contradicted by the proposed `reviewer`: it receives the grid decision and novel-findings triage that Section 0 says the running `sanity-checker` is doing. The proposal does not say the existing seat is retired or that the split is superseded. Following both sections creates duplicate ownership immediately. Confidence: sure.

38. “`reviewer`” is not a defined seat and has no `docs/agents/reviewer-instructions.md`. The documented first prompt requires that exact brief and tells an agent to stop if it is absent. Thus the proposed split cannot be launched through this file’s own seat procedure. Confidence: sure.

39. The `gatekeeper` assignment “plus PR #55 and PR #57” assigns already-merged PRs as remaining work. The same bullet also gives it fleet/session issues, while the reviewed seat model and briefs assign those to `fleet`; the `reviewer` bullet similarly takes #17–#23 from `skill-builder` and the grid work from `sanity-checker`. The file does not mark this older split as superseded or authoritative, so routing from it conflicts with the context it says the launched seats are reading. Confidence: sure.

40. “Context: the ghi design documents already in the repo.” No documents or paths are named, and “the ghi design documents” is not a defined set. A cold agent cannot know which files form required context or when it has finished reading them. Confidence: sure.

41. “Each seat gets its own agent home and therefore its own branch, which is what keeps them from colliding.” Separate branches isolate working trees and pushes; they do not prevent two seats editing the same file or colliding at merge, and they protect no shared machine-local state. This also contradicts the referenced seat model’s explicit statement that branches are a check, not a guarantee. Confidence: sure.

42. “Start with two if three is too many at once; the third can wait.” The file already says two different seats are running, and it does not say whether they count toward this proposed trio, which proposed seats to start, or what happens to `sanity-checker`. The instruction therefore cannot select an executable two-seat state. Confidence: sure.

clean sections: none
