Title: Idle sweep slice 2: headless judge, wake messages, log, user-alerts and the scheduled-job entry

This pull request replaces [PR 2594, "Idle sweep slice 2: headless judge, wake messages, log, user-alerts and the scheduled-job entry"](https://github.com/nedschorus/nedschorus/pull/2594), which merge-lane-2 closed at its round limit. It carries that pull request's work as of its nc-head-commit 5714c7369, merged with main, one commit that fixes the seven findings of round 3's review (https://github.com/nedschorus/nedschorus/pull/2594#pullrequestreview-5791610921), and the two commits listed below. It is to be reviewed from round 1.

What it builds is unchanged from that pull request: `scripts/agent-seat-idle-sweep-headless-judge-wake-messages-send-and-user-alerts-write.py`, run every minute by cron on ned-box from `nc-systems/general-tools/scheduled-jobs-on-each-machine.json`, finds each idle agent-seat with something to do and wakes it with a cross-session message, as GHI-MD `docs/issues/940-tasks-raise-themselves-when-their-due-time-passes.md` § The idle sweep designs it.

The four headless prompts (SENDER_PROMPT, NOTICE_SENDER_PROMPT, IDLE_JUDGE_PROMPT, SENTENCES_JUDGE_PROMPT, with the shared FIND_THE_ENTRY paragraph) are unchanged from that pull request, except the one sentence below, and the user approved them word for word on 2026-11-05, at item 9.5 of ned-box-helper's approval-walk ned-box-helper-push-program-design-points-2026-11-03.

The fixes, each with a case that failed before them:

1. A wait's resets and its due step are worked out first, on their own, and only then is the rule 2 message sent. Before, a promise raised on a wait past tell_user never escalated, and a fresh promise at every invocation kept a wait from reaching its escalation.
2. The delivery check counts only a `user` record or a `queued_command` attachment, not Claude Code's `queue-operation` record, which is written before the model has the message.
3. Every headless agent-session runs with `--strict-mcp-config` and `--permission-mode dontAsk`, so it loads no claude.ai connector and bypasses no permission.
4. A rule 5 judge's failed SendMessage is a failure, whatever the judge answers.
5. Each event carries the time it was written: the invocation's time plus the whole seconds the invocation has taken.
6. A user-alert already written still fails the invocation that finds its cause again, so a persisting read failure exits 1 at every invocation.
7. A case whose fake claude starts a child that holds its output open kills mutant M14 (`os.killpg` replaced with `process.kill`).

Two further commits:

- A promise or a hold may now be backed by any open task of the agent-seat that carries `prerequisites` or `blockedBy`, however old, and the judge's facts carry those tasks in a new field, `open_tasks_with_prerequisites_or_blocked_by`. One sentence of SENTENCES_JUDGE_PROMPT changes, word for word as the user approved it at item 9.5 of that approval-walk on 2026-11-05: "The tool calls the agent-seat made from the earliest sentence's turn on are in the JSON below, with the tasks they created or updated and the files they changed; so are its open tasks that have prerequisites or blockedBy, whenever they were created, and what is running." GHI-MD 940 § Promises and announced actions says the same.
- run_headless starts its command line from main's shared function, claude_code_headless_print_mode_command_line_prefix_build, which the test `nc-systems/general-tools/tests/claude-code-headless-print-mode-every-launch-uses-common-command-line-prefix-test.py` requires of every `claude -p` launch.

#root_cause handle_seat let one function, wait_step, decide both a wait's next step and whether a rule's message was sent, and rule 2 returned before reaching it; the wait's steps are now worked out apart from any rule's message.
#root_cause message_in_transcript skipped only assistant records, so it took any other record holding the text, including the queue-operation record written before delivery, as delivery.
#root_cause run_headless named the tools a headless agent-session may use but not the permission mode or MCP servers, so it inherited the user's settings.
#root_cause judge_idle_seat checked only the judge's answer and its successful sends, never a send that failed.
#root_cause Sweep stamped every event with the time the invocation started, not the time the event was written.
#root_cause alert() returned for a key already alerted before it marked the invocation failed.
#root_cause no case stopped a headless agent-session that had started a child process, so nothing showed the whole process group is killed.
#root_cause code_reading_of_sentence counted as a backing candidate only a task call made in or after the sentence's turn, so an open task created earlier, which the idle check raises all the same, never reached the judge.

Tests: `python3 scripts/run-all-test-suites.py --only-suites-whose-recorded-inputs-changed-since origin/main` and the quick mutation pass of `scripts/mutation-testing-changed-lines-quick-or-full-pass-survivors.py`; results are in the push's record.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01GmqXa5B7BVAJeKGABHZPzm
