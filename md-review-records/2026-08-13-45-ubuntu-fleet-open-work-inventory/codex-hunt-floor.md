<!-- provenance: runtime=codex model=gpt-5.6-luna effort=xhigh cell=defect-hunt tier=floor target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/issues/queue/45-ubuntu-fleet-open-work-inventory.md -->

1. “the thread map and the context-file paths stay useful.”  
   This overstates durability: line 62 directs deletion of a referenced transcript, and handoff/transcript files can be removed or rotated. A future agent may follow a dead path. Confidence: sure.

2. “every document written that day was stamped `2026-08-14` ... and is now corrected to `2026-08-13`”  
   “That day” and the set of documents are undefined; literally, this dated document could be included, contradicting its `2026-08-13` snapshot date. Confidence: unsure, because the sentence may refer to an unnamed narrower batch.

3. “Still owed: a second-pass review ... starting with `seat-first-prompt.md`, `agent-seat-model.md` and `gatekeeper-instructions.md`.”  
   “Starting with” gives no complete document set or stopping point, so the required review cannot be known to be finished. Confidence: sure.

4. “md-review delivers piecemeal under a Monitor”  
   `Monitor` is undefined, and “piecemeal” does not identify the delivery mechanism, owner, or completion condition. Confidence: sure.

5. “fast-handoff sanity-check findings applied, design doc gutted”  
   The design document is unnamed and unpathed, and “gutted” is not an operationally checkable state. Confidence: sure.

6. The PR rows for #51–#53 label the owner stream “`choirmaster`”, while §7 assigns those same PRs to “`reviewer`”. The file does not say whether the first label is historical or whether ownership transferred. A future agent cannot determine the current owner. Confidence: sure.

7. The #55 row says it is open, and the file says “All five are open”, but `docs/agents/gatekeeper-instructions.md` says “PR #55 ... merged 2026-08-13”. These states conflict. Confidence: sure.

8. “machine-named launchers + Mac twin, fleet paths reference, supervisor branch sync, session riders”  
   “fleet paths reference” and “session riders” are unexplained names, so the row does not identify the work carried by PR #57. Confidence: sure.

9. “They do not conflict: different files, different branches.”  
   Separate branches do not establish non-conflict: two branches can change the same logical behavior through different files, or one can rename a file the other edits. This can cause unsafe parallel ownership. Confidence: sure.

10. “The gatekeeper's remaining road, all user-gated ... then the credential work.”  
    The referenced gatekeeper instructions state that non-org-owner credential preparation can proceed in parallel and only the GitHub portion waits for the user. This wording incorrectly blocks all credential work. Confidence: sure.

11. “The gatekeeper spec's ‘when a test suite exists, the tests run here’”  
    “The gatekeeper spec” is not identified by path, and several gatekeeper documents exist. A future agent cannot know which source to verify. Confidence: unsure, because the surrounding repository contains a likely canonical specification.

12. “No gate-edits-the-gate guard.”  
    This coined mechanism name does not say what “gate” covers or what constitutes an edit. The referenced scorecard gives one interpretation, but the inventory entry itself is not independently actionable. Confidence: unsure.

13. “A writer-stamps-the-pin proposal”  
    `writer` and `pin` are undefined: it is unclear whether the writer is an agent, program, or repository process, and whether the pin is a commit, repository/HEAD pair, or something else. Confidence: unsure, because the scorecard supplies a likely interpretation.

14. “The wedged-but-light session: stalls below the recycle threshold with no watchdog.”  
    “Recycle threshold” is not defined or quantified, so an agent cannot determine which session state qualifies or how to verify the finding. Confidence: unsure, because related seat documents likely define recycle behavior.

15. “Twenty-four open.”  
    The listed groups contain 30 issue numbers: 6 fleet, 11 review/skills, 4 GHI/tooling, and 9 doctrine/research. The stated total contradicts the inventory. Confidence: sure.

16. “#32 (what NC preserves)”  
    `NC` is undefined and not self-documenting. A future agent cannot know whether it means nedschorus, a system, or a document. Confidence: sure.

17. “`~/.claude/projects/-home-nedlern-agents-choirmaster/d9eda3ec-*.jsonl`”  
    This is a glob, not a unique context path. If it matches zero or multiple files, §6 gives no selection rule for the file to pass to a new session. Confidence: unsure, because it may have matched exactly one file at snapshot time.

18. “`login session` ... `3d8bf995` ... `delete`”  
    The target is a wildcard path with no deletion procedure or exact stopping condition. “Delete” could refer to the transcript, session, state, or all matching files. Confidence: sure.

19. “duplicate of the choirmaster stream; resolve against `ea663864`”  
    “Resolve against” has no defined operation or completion condition; it could mean compare, merge, archive, or delete. Confidence: sure.

20. “Everything else is accounted for ... none needing an owner”  
    Reading transcript titles cannot establish that no unfinished work exists. An ordinary counterexample is a maintenance transcript whose title does not reveal an outstanding task. Confidence: sure.

21. “`--first-prompt-file <path>` ... seeds a session”  
    The procedure omits reachable cases: an existing handoff can take precedence, a running session may be attached instead of seeded, and the path can be missing or unreadable. The agent cannot predict which context will actually load. Confidence: sure.

22. “`cp ~/.claude/handoffs/<old>-handoff.md ~/.claude/handoffs/<new>-handoff.md`”  
    The command can overwrite an existing destination handoff, including a live or newer one, with no stated handling for that case. Confidence: sure.

23. “a handoff written by a forked session describes that session's state when it wrote the handoff, not the fork point.”  
    The absolute “not the fork point” is false when the forked session writes immediately without changing state. Confidence: unsure, because the sentence may be intended as a provenance distinction rather than a claim that the contents must differ.

24. “status line present (which is the tell that project settings loaded, and therefore that the recycle hook and the instruction-file guard loaded too)”  
    A status line does not prove that unrelated hooks are present or functioning. A configuration can load the status component while omitting or failing the hooks. Confidence: sure.

25. “What was done instead, and what to undo once #58 merges:”  
    The following steps describe setup, not an undo operation. The later text says fast-forwarding may require no action, but does not resolve what “undo” means if cleanup is required. Confidence: sure.

26. “The Mac twin runs locally on the box and is mechanically identical to the Ubuntu launcher minus the SSH hop”  
    The two scripts differ in checkout discovery, environment variables, path handling, and remote preparation; they are not mechanically identical except for SSH. Confidence: sure.

27. “Once #58 merges, those branches become strictly behind and fast-forward normally ... the branch fast-forwards on its own.”  
    This assumes a merge preserving the PR’s original commits. A squash, rebase, or cherry-pick merge produces equivalent content without the same ancestry, leaving the seat branch divergent rather than strictly behind. Confidence: sure.

28. “If a seat must be cleaned before that, relaunch it from the PR branch rather than resetting to main.”  
    The launcher reuses an existing checkout and branch; relaunching does not select a different branch or recreate the worktree. No executable operation is specified for this case. Confidence: sure.

29. “Three seats, chosen so no two touch the same files or branches”  
    The file lists issues and PRs, not file-level boundaries, so the claimed isolation cannot be checked or enforced from this context. Confidence: sure.

30. The proposed ownership gives `gatekeeper` fleet/session issues and gives `reviewer` the sanity-checker and skill work, while the seat model assigns those areas to `fleet`, `sanity-checker`, and `skill-builder`. The file does not describe retirement, renaming, or transfer of the existing seats, so launching the proposal can create duplicate or competing owners. Confidence: sure.

31. “`reviewer`”  
    This generic name does not identify what is reviewed and is likely to produce ambiguous search results across the repository. Confidence: unsure, because the seat model explicitly allows one-word seat names as address labels.

32. “Context: the ghi design documents already in the repo.”  
    No document paths or names are given, and `ghi` is not expanded here. A future agent cannot determine the required reading set or distinguish the design from related drafts. Confidence: sure.

33. “Each seat gets its own agent home and therefore its own branch, which is what keeps them from colliding.”  
    This is false as a general isolation claim: separate branches defer same-file conflicts to merge, and shared handoffs, locks, scratch directories, and tmux state remain outside git. Confidence: sure.

34. “Start with two if three is too many at once; the third can wait.”  
    “Too many” has no criterion, and the file does not say which two of the three should start or what condition releases the third. Confidence: sure.

clean sections: none
