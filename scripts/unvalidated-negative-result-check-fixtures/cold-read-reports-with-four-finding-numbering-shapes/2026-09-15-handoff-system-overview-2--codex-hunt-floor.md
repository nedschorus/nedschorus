1. Quote: “It is not a substitute for reading the code: each script's docstring says what it does and why, and its `…-test.py` says what must keep passing. Thre
2. Quote: “The design of record, a ledger of dated rulings and their reasons, is `docs/cross-project/fast-handoff-design.md`; where this page and the ledger dis
3. Quote: “This page says ... the reasons behind its shape that the code cannot state” and “each script's docstring says what it does and why.”
4. Quote: “Two alternatives were rejected ... `claude --continue` or `--resume`, which restore the context being shed.”
5. Quote: “Every successor is a fresh process with a new session id, CLAUDE.md and hooks reloaded from disk.”
6. Quote: “Every file the system writes is under `~/.claude/handoffs/` on the agent-seat's machine, named for the agent-seat.”
7. Quote: “The agent writes one thing, its successor's first action, into a next-step file at the path the skill gives.”
8. Quote: “writes the session-handoff, `<seat>-handoff.md`”
9. Quote: “Watches the session-handoff's restart counter, kills the agent-session, extracts its dialog, launches the successor with the session-handoff as its f
10. Quote: “The handoff-supervisor keeps two generations.”
11. Quote: “a second launch attaches instead of duplicating.”
12. Quote: “`restart-live-seats-at-login.py` brings back at login the agent-seats running when the machine stopped.”
13. Quote: “`/clear` and `/exit` are unavailable to it.”
14. Quote: “Only a handoff-supervisor that owns the pane can reincarnate.”
15. Quote: “a detached one's console is a log file, so every successor died at its first need for input.”
16. Quote: “The ledger's ‘self-registration’ ruling predates this.”
17. Quote: “The agent writes only the next step; the writer computes everything else.”
18. Quote: “The next step travels as a file because a shell mangles backticks, quotes and newlines inside an argument.”
19. Quote: “the last turns clearing a word floor, extended back to a user prompt.”
20. Quote: “One handoff-supervisor per agent-seat, enforced by the lock.”
21. Quote: “Nothing protects across machines: the same name on the Mac and on ned-box is two unrelated agent-seats.”
22. Quote: “A handoff-supervisor is judged by its process, not its heartbeat.”
23. Quote: “a session-handoff addressed to any other name is a letter nobody reads.”
24. Quote: “The session-handoff records the subagents still working, so the successor can start fresh ones on the same jobs.”
25. Quote: “a brief for a job longer than one step says how work survives a kill: commit after each step, and rewrite the report file as you go.”
