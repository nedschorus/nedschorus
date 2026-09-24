1. **“This page says what it is for, what its parts are, and the reasons behind its shape that the code cannot state. It is not a substitute for reading the cod
2. **“each script's docstring says what it does and why, and its `…-test.py` says what must keep passing”**
3. **“The design of record, a ledger of dated rulings and their reasons, is `docs/cross-project/fast-handoff-design.md`; where this page and the ledger disagree
4. **“the work is mostly sequential, so old turns are disposable”**
5. **“Two alternatives were rejected … `claude --continue` or `--resume`, which restore the context being shed. Every successor is a fresh process with a new se
6. **“Every file the system writes is under `~/.claude/handoffs/` on the agent-seat's machine, named for the agent-seat.”**
7. **“Holds the session-handoff while a subagent or a young background task is in flight”** and **“the hook holds the session-handoff while one is in flight”**
8. **“while a subagent or a young background task is in flight; at a higher ceiling it fires regardless”**
9. **“The agent writes one thing, its successor's first action”** and **“The agent writes only the next step; the writer computes everything else”**
10. **“`handoff-write-and-check-supervisor.py`, the writer”**, **“`handoff-extract-conversation.py`, the extractor”**, and **“`launch-claude-mac` and `launch-cl
11. **“If none is, it says so: keep working, and the user runs `resupervise-seat.py`.”**
12. **“Watches the session-handoff's restart counter, kills the agent-session, extracts its dialog, launches the successor with the session-handoff as its first
13. **“Writes the tail of the dialog to `<seat>-dialog-NNNN.md`, numbered in sequence … The handoff-supervisor keeps two generations.”**
14. **“a second launch attaches instead of duplicating”**
15. **“`restart-live-seats-at-login.py` brings back at login the agent-seats running when the machine stopped.”**
16. **“The next step travels as a file because a shell mangles backticks, quotes and newlines inside an argument.”**
17. **“The successor is not dumber than the predecessor, so it gets the dialog verbatim: the last turns clearing a word floor, extended back to a user prompt. N
18. **“Nothing protects across machines: the same name on the Mac and on ned-box is two unrelated agent-seats.”**
19. **“The heartbeat reads fresh for a minute after a handoff-supervisor dies, and the login restart runs inside that minute, so it refused every agent-seat it 
20. **“a session-handoff addressed to any other name is a letter nobody reads”**
21. **“A live handoff-supervisor says nothing about whether the session-handoff will be seen.”**
22. **“The session-handoff records the subagents still working, so the successor can start fresh ones on the same jobs”**
23. **“So a brief for a job longer than one step says how work survives a kill”**
24. **“a brief for a job longer than one step says how work survives a kill: commit after each step, and rewrite the report file as you go.”**
25. **“Git is the record; the session-handoff is not … Work survives by commit-as-you-go; the session-handoff carries the thread.”**
