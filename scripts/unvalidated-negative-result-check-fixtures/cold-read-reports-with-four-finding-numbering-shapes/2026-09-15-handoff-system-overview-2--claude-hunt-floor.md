**1. (i) Line 3 — "The handoff-system is the subsystem that reincarnates agent-sessions." — and the role names used through the page: "the ledger" (line 3), "th
**2. (d) Line 3 — "reincarnates agent-sessions"; line 7 — "Every successor is a fresh process with a new session id"; line 29 — "its session name".**
**3. (b)(g) Line 3 — "It is not a substitute for reading the code: each script's docstring says what it does and why" together with "where this page and the led
**4. (a) Line 3 — "Thresholds, file formats and flag defaults are not repeated here; they live in the scripts."**
**5. (b)(f) Line 3 — "The design of record, a ledger of dated rulings and their reasons, is `docs/cross-project/fast-handoff-design.md`; where this page and the
**6. (d) Line 7 — "with nobody typing into each pane".**
**7. (a)(b) Line 7 — "and `claude --continue` or `--resume`, which restore the context being shed."**
**8. (f) Line 7 — "Every successor is a fresh process with a new session id, CLAUDE.md and hooks reloaded from disk."**
**9. (f) Line 11 — "Every file the system writes is under `~/.claude/handoffs/` on the agent-seat's machine, named for the agent-seat."**
**10. (d) Line 11 — "on the agent-seat's machine" — together with line 18's "`launch-claude-mac`" and line 27's "the same name on the Mac and on ned-box is two 
**11. (b) Line 13 — "Holds the session-handoff while a subagent or a young background task is in flight" — and the term "session-handoff" through the page.**
**12. (d) Line 13 — "a young background task".**
**13. (g) Line 13 — "at a threshold, tells the agent to run the /handoff skill. ... at a higher ceiling it fires regardless."**
**14. (c)(f) Line 14 — "The agent writes one thing, its successor's first action" — and line 25, "The agent writes only the next step; the writer computes every
**15. (a)(c)(g) Line 14 — "and runs the writer with no `--agent`: the name defaults to the working directory's name, the agent-seat's name."**
**16. (e)(g) Line 15 — "If none is, it says so: keep working, and the user runs `resupervise-seat.py`."**
**17. (a)(d)(g) Line 15 — "If none is, it says so: keep working" — against line 29, "Closed by [PR #394](https://github.com/nedschorus/nedschorus/pull/394), a r
**18. (d) Line 16 — "Watches the session-handoff's restart counter".**
**19. (g) Line 16 — "kills the agent-session, extracts its dialog, launches the successor with the session-handoff as its first prompt."**
**20. (c) Line 16 — "launches the successor with the session-handoff as its first prompt".**
**21. (b)(g) Line 16 — "stamps a heartbeat into `<seat>-supervisor-state.json`" — with line 28, "A handoff-supervisor is judged by its process, not its heartbea
**22. (b)(d) Line 17 — "Writes the tail of the dialog to `<seat>-dialog-NNNN.md`" — and line 26, "so it gets the dialog verbatim: the last turns clearing a word
**23. (c)(d) Line 19 — "`resupervise-seat.py` re-seats a handoff-supervisor on an unwatched agent-session".**
**24. (b) Line 19 — "`recover-crashed-seats.py` resumes an agent-seat whose agent-session died with no session-handoff acted on".**
**25. (f) Line 23 — "an agent cannot exit itself. `/clear` and `/exit` are unavailable to it, and a self-sent SIGTERM trips the safety classifier (measured 2026
**26. (b) Line 24 — "a detached one's console is a log file, so every successor died at its first need for input".**
**27. (c) Line 24 — "Removed 2026-08-14 after its second failure".**
**28. (c) Line 25 — "The next step travels as a file because a shell mangles backticks, quotes and newlines inside an argument."**
**29. (b) Line 27 — "Nothing protects across machines: the same name on the Mac and on ned-box is two unrelated agent-seats."**
**30. (g) Line 27 — "One handoff-supervisor per agent-seat, enforced by the lock."**
**31. (f) Line 28 — "The heartbeat reads fresh for a minute after a handoff-supervisor dies, and the login restart runs inside that minute, so it refused every 
**32. (d) Line 28 — "The process must be running this script with this agent-seat's name."**
**33. (b) Line 29 — "Reported by merge-lane-51 on 2026-09-15: its agent-session ran the writer with `--agent merge-lane-51`, its session name".**
**34. (a)(b) Line 29 — "A live handoff-supervisor says nothing about whether the session-handoff will be seen."**
**35. (c) Line 29 — "[PR #395](https://github.com/nedschorus/nedschorus/pull/395), which removed the name from the skill's steps."**
**36. (b) Line 30 — "the hook holds the session-handoff while one is in flight, up to the ceiling, because waiting on a subagent that never finishes runs the ag
**37. (d) Line 30 — "So a brief for a job longer than one step says how work survives a kill: commit after each step, and rewrite the report file as you go."**
**38. (g) Line 30 — "Reincarnating kills the agent-session's subagents with it ... The session-handoff records the subagents still working".**
**39. (h) — nothing on the page qualifies. Nearest candidate, line 31: "Git is the record; the session-handoff is not".**
**40. (i) Line 33 — "the subagent roster field".**
