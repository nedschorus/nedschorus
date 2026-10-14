---
name: start-new-agent-seat-on-ned-box
description: Use when the user asks for a new named Claude agent, agent-seat or seat on ned-box (the Ubuntu machine). Covers choosing the name, the CLAUDE.local.md he approves, and the launch command. Runs from an agent-session on either machine.
---

# Start a new agent-seat on ned-box

Run these steps from an agent-session on either machine. The launcher reaches ned-box over SSH, from the Mac or from ned-box itself.

1. **Name.** Choose a multi-part name by CLAUDE.md's naming rule, using only letters, digits, `-` and `_`, which is all the launcher accepts. The name also names the agent-seat's git branch on ned-box and its Remote Control address, the name other agent-sessions send messages to, so it must be unused on both machines. Check: the ListAgents tool, which lists the agent-sessions running on both machines; `ssh nedlern@ned-box 'ls ~/agents/'`; `ssh nedlern@ned-box 'git -C ~/Projects/nedschorus branch --list <name>'`, which must print nothing, because the launcher reuses an existing branch of that name as it stands; and, on the Mac, `ls ~/agents/`. An agent-session on ned-box cannot list the Mac's directories, so it relies on ListAgents for the Mac.
2. **CLAUDE.local.md.** Write the text the agent-seat's `CLAUDE.local.md` will hold: what the agent-seat owns, its first job, where its work goes (pull requests, the log-store), and what the user asked for, in his words where a paraphrase would lose his meaning, without dates or attributions. Show the user the text word for word and wait for his approval; the file tells the agent-seat how to behave.
3. **First prompt.** Write two files on ned-box. On ned-box, write them directly; on the Mac, write them locally, then copy both with `scp`, which keeps quotes, `$` and backticks intact:
   - `/home/nedlern/<name>-first-prompt.md`: this instruction, then the approved text: "Save the text below, unchanged, as `CLAUDE.local.md` in your working directory. Before you save it, copy the user's approval words from `/home/nedlern/<name>-approval.txt` into `.walk-approved` in your working directory, which is the root of your checkout. Then do the first job the text names."
   - `/home/nedlern/<name>-approval.txt`: the user's exact approval words, which the instruction-file guard requires in `.walk-approved` before it lets the agent-seat write its `CLAUDE.local.md`.
4. **Launch.** On the Mac:

   ```
   /Users/el/Projects/nedschorus/scripts/launch-claude-ubuntu <name> --no-attach --first-prompt-file /home/nedlern/<name>-first-prompt.md
   ```

   On ned-box, set the box's address first, because the launcher's default address `ned` resolves only on the Mac:

   ```
   NEDSCHORUS_AGENT_BOX=nedlern@ned-box ~/Projects/nedschorus/scripts/launch-claude-ubuntu <name> --no-attach --first-prompt-file /home/nedlern/<name>-first-prompt.md
   ```

   The launcher updates Claude Code, creates the agent-seat's agent-home `~/agents/<name>` on ned-box as a worktree on the branch `<name>` cut from `origin/main`, and starts the agent-seat's handoff-supervisor inside the agent-seat's own tmux server, `tmux -L <name>`. Because of `--no-attach`, the tmux session closes when the handoff-supervisor exits, with no shell left in it; running the launcher again brings the agent-seat back. If the launcher prints that the worktree could not be created, stop and tell the user what it printed.
5. **Check** that it started. The agent-session writes its `CLAUDE.local.md` a minute or more after the launcher returns, so wait for the file:

   ```
   ssh nedlern@ned-box 'tmux -L <name> ls && for i in $(seq 1 60); do [ -f ~/agents/<name>/CLAUDE.local.md ] && break; sleep 5; done; cat ~/agents/<name>/CLAUDE.local.md'
   ```

   Compare the printed file with the approved text. If the file never appears, show the user the last lines of `ssh nedlern@ned-box 'tmux -L <name> capture-pane -p'`. When it appears, move both files from step 3 into `/home/nedlern/nedschorus-logs/seats/<name>/` and tell the user the agent-seat is running and that `launch-claude-ubuntu <name>`, typed in a terminal on his Mac, attaches that terminal to the agent-seat's session.
