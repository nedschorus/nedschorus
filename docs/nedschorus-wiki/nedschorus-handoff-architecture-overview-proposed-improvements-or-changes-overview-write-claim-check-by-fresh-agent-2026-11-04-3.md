# Proposed improvements or changes: nedschorus-handoff-architecture-overview.md (overview claim check, 2026-11-04)

Assertions of the overview that the claim check against commit 9ecda8345f6d2062befc44c042236d7e6c6ae6fa found contradicted or unsupported and ranked fix later: loose, incomplete or badly worded, but no agent would act wrongly on them. Its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/5b96d3034b3d4d53955252bbdae1a30276f4b4db-2026-11-04T20-15-27-443521Z.md. Regular maintenance fixes them in the overview.

## E1 — possible problem: an assertion of the overview is contradicted

Claim: At its first launch the handoff-supervisor carries out a waiting session-handoff. Otherwise it starts fresh when an exit is recorded, else resumes the agent-seat's last transcript worth resuming, and it stops when it cannot read the transcript folder or a transcript in it.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> The overview says a first launch always carries out a waiting session-handoff. When the handoff-supervisor is started with --resume-session-id, it instead marks the waiting session-handoff consumed and resumes the named transcript. handoff-supervisor.py:2208-2218 `if next_launch_resumes_the_session and settings.handoff_path.is_file(): ... print("handoff-supervisor: a handoff (counter {stale_counter}) predates this resume; marking it consumed ...") ... state["consumed_counter"] = stale_counter`; :2510-2512 help `"A handoff already on disk is marked consumed rather than starting a fresh agent-session from it ... passing this flag chooses the transcript over any waiting handoff"`. The other parts are supported: :2263-2293 for fresh-or-resume and :2268-2278 for stopping on an OSError. No automatic caller passes the flag while a session-handoff waits (recover-crashed-seats.py:993-995 defers first). The sentence still misses an exception a person running the handoff-supervisor by hand can hit.
State: open

## E2 — possible problem: an assertion of the overview is contradicted

Claim: scripts/handoff-context-threshold-hook.py, a Stop hook: at a set share it tells the agent to run /handoff, once until the next compaction, with a handoff-deferral while a subagent or a recent background Bash task still runs, until the ceiling; after a deferral it tells the agent once that work has finished, even below the first share.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> The overview names only subagents and background Bash tasks as reasons to defer. The hook also defers while a workflow runs, and while the transcript cannot be fully read. handoff-context-threshold-hook.py:414-419 `return WorkInFlight(ids_of(SUBAGENT_TASK_TYPE), [...shell...], ids_of(WORKFLOW_TASK_TYPE),)`; :554-558 `except TranscriptCouldNotBeFullyRead: flight = None; count_is_known = False ... if not count_is_known or flight:` defers. The rest is supported: settings.json:58-63 (Stop); :74 threshold 33; :502 ceiling 65; :537 fired marker; :532-533 deferred marker overrides the threshold.
State: open

## E3 — possible problem: an assertion of the overview is contradicted

Claim: At its first launch with a session-handoff waiting, the handoff-supervisor asks the user in the same way, then runs the extractor and launches the successor, without removing worktrees or restarting itself.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> This holds without --resume-session-id (handoff-supervisor.py:2221-2259; no worktree removal or restart on that path). Started with --resume-session-id, the handoff-supervisor instead marks the waiting session-handoff consumed and resumes the named transcript, with no question and no extractor. handoff-supervisor.py:2208-2218 `if next_launch_resumes_the_session and settings.handoff_path.is_file(): ... "marking it consumed so it cannot kill the resumed session" ... state["consumed_counter"] = stale_counter`. This is the same exception as row 21.
State: open

## E4 — possible problem: an assertion of the overview is contradicted

Claim: A handoff-supervisor that outlives its agent-session records the exit before it exits, so recover-crashed-seats.py and the agent-crash-watcher can tell an agent-seat left down from one that crashed.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> After a death the handoff-supervisor can decide to resume and loop back, then fail to read the transcript of the session it is about to resume. It then exits 5 without an exit record, having just cleared the old one. handoff-supervisor.py:2298-2299 `clear_agent_exit_record_from_supervisor_state(state); write_supervisor_state(...)` then :2339-2342 `except OSError as error: print(transcript_unreadable_stop_message(...)); return 5` (no `record_agent_exit_in_supervisor_state`). The overview's own component paragraph says the exit is recorded "only in the second case". The case needs the transcript to become unreadable between :2373 and :2337. Recovery then treats the seat as crashed and refuses on the unreadable transcript (recover-crashed-seats.py:998-1004), so nobody acts wrongly.
State: open
