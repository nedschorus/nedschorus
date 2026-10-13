# Failures no agent is watching go first to an agent, which opens a window on the user's Mac only when it needs him

This is a design, not built. It replaces the draft "messages for the user queue" of 2026-10-13, which the user set aside in the same conversation. Nothing here is on main. Version 2: rewritten after a Claude review and a Codex review found that version 1's agent could not end its own agent-session; the review records are listed at the end.

## The problem

Programs that run with no agent watching, chiefly the scheduled jobs in `nc-systems/general-tools/scheduled-jobs-on-each-machine.json`, report their failures into log files that nobody reads. On origin/main at c2723d96 that file declares six jobs: `transcript-mirror-to-log-store` (both machines, every minute), `log-store-session-dialogs-refresh` (ned-box, every 10 minutes), `daily-full-test-run-of-main` (both, 03:30), `daily-clean-worktrees` (both, 06:30), `handoff-agent-seat-died-without-session-handoff-restart-watcher` (ned-box, every minute) and `weekly-uncommitted-work-snapshot-hook-real-claude-session-owner-check` (both, weekly). Each appends its output to a log under `~/.claude/` and nothing more.

- `scripts/daily-full-test-run-of-main.py`, when it cannot write its record (around lines 479 to 497), prints "Tell the user what the line above says" and exits nonzero. It runs from cron and launchd, so no agent reads that instruction, and neither does the user.
- `scripts/clean-worktrees.py` exits 1 when anything failed. `/home/nedlern/.claude/daily-clean-worktrees.log` on ned-box held eight FAILED lines on 2026-10-13 that nobody had seen: six were worktrees locked by a running subagent, which is routine, and two were one branch that git would not delete, on two days.
- `scripts/transcript-mirror-to-log-store.py --failures-only` prints only FAILED lines, into a log nobody reads.
- The daily maintenance step of GHI [Daily maintenance in one daily step, starting with a daily check of every wiki page](https://github.com/nedschorus/nedschorus/issues/1058) and the nightly test report of GHI [The daily full test runs tell the user about failures and about test cases that run nowhere or lack a tool, and every test suite prints a skipped test case in one format](https://github.com/nedschorus/nedschorus/issues/1206) are designed with no working route to the user.
- Nothing tells the user when Claude is logged out or out of tokens on a machine, or when ned-box cannot be reached, except an agent that happens to notice.
- The crash restart watcher is the one program with a route: it opens a notice window on the user's Mac with `scripts/open-mac-window-from-ned-box.py` when it cannot restart an agent-seat.

A survey of the eight live agent-seats on both machines on 2026-10-13 found no other route.

## What the user asked for

The user, on 2026-10-13, in the fleet-restart-at-login agent-seat: "when things go wrong I really want an agent to be the first line of defense, not me personally." "Right now when HW is down or can't log in, or run out of tokens I need to know, and I may want to work with some agent to do some investigation if what's wrong isn't obviious." "a -p agent can easily be wrapped to have a discussion with it, if it's still around to resume or continue." "I don't want to see the escalation agent unless it's needed because it will take screen space that's not needed 99% of the time. So I'd like to be able to close it in iterm2, and have it pop up when necessary."

## The design in one paragraph

A program that fails with no agent watching writes an incident file; it does nothing else. A scheduled job, the escalation drainer, runs every minute on each machine, takes one lock, and for each incident that is waiting runs one headless `claude -p` agent-session in the escalation agent's home directory, whose `CLAUDE.local.md` holds the escalation policy. That agent investigates, fixes what the policy lets it fix or files a task or a pull request, and ends its answer with one verdict line: handled, or the user is needed. A `claude -p` agent-session ends by itself when its answer is done. Only for "the user is needed" does the drainer open a window on the user's Mac, running `claude --resume <session id>` in the same directory, so he lands in a conversation with the agent that did the groundwork. Closing that window ends the resumed conversation; the same command reopens it. Two health checks cover what no agent can handle: Claude logged out or out of tokens, and ned-box unreachable; they open a plain window once per outage.

## The escalation policy

| Case | Detected by | First responder | What the agent may do itself | When the user's window opens | What the window shows |
|---|---|---|---|---|---|
| A scheduled job fails | the wrapper for scheduled jobs, from the job's exit code | escalation agent | read the job's full output and log; rerun the job once; clear what the job's own documentation says is safe to clear; file a task for the agent-seat that owns the job; open a pull request for a code defect | the cause is unknown, the fix needs a decision only the user makes, or the failure returns after a fix it recorded | the agent's summary, then the resumed conversation with that agent |
| The crash restart watcher cannot restart an agent-seat | the watcher | see Deferred-decision 3 | | | |
| Claude is logged out on a machine | the Claude health check on that machine | none: no agent can run | nothing | at once, once per outage | "Claude is logged out on <machine>", the command to log in on that machine, and how many incidents wait |
| Claude is out of tokens or at a usage limit | the Claude health check | none | nothing | at once, once per outage | what Claude printed, including when the limit resets, and how many incidents wait |
| ned-box cannot be reached from the Mac | the ned-box reachability check on the Mac | none | nothing | after three failed checks in a row, once per outage | "ned-box has not answered ssh since <time>", and what to check |

## The pieces

- **Incident file.** One file per incident, holding the reporting program's name, the machine, the exit code, the failing run's whole output (not a tail), each repeat's time, a state, and, once handled, the outcome and the `claude -p` session id. On ned-box the files live in a directory in the log-store; on the Mac, in a directory on the Mac (see Deferred-decision 4).
- **Incident key and states.** An incident's key is the reporting program's name. The states are waiting, being handled, handled, user needed, fix pending and waiting for Claude. A failure whose key has an incident in any state but handled only appends its time to that incident. Fix pending carries the task or pull request the agent recorded and a time; the incident goes back to waiting when that time passes and the job still fails, so a job that fails every minute makes one incident and one handling, not one per minute. Waiting for Claude goes back to waiting when the Claude health check passes again.
- **The report script**, the one thing a failing program calls: it writes or appends to the incident file and exits. It starts nothing, so a report can never be lost between an agent's last look and its exit; the next drainer run finds it.
- **The wrapper for scheduled jobs.** `nc-systems/general-tools/install-scheduled-jobs-on-this-machine.py` writes each job's cron line or launchd entry to run the job through the wrapper, which runs the job, appends its output to the job's log as now, and calls the report script when the job exits nonzero, with the whole output of that run. The crash restart watcher is left out of the wrapper, because it already reports its own failures to the user. Two jobs exit nonzero when nothing failed, and are changed to exit 0 instead, since a nonzero exit must mean a failure: the transcript mirror and the session-dialogs refresh return `EXIT_LOCKED = 3` when the previous run still holds their lock, and `clean-worktrees.py` returns 1 for a worktree that a running subagent has locked.
- **The escalation drainer**, a scheduled job every minute on each machine. It takes a lock and exits at once if another drainer holds it. Before running any agent it runs the Claude health check; on failure it marks waiting incidents as waiting for Claude and stops. Otherwise it handles each waiting incident in turn: it marks it being handled, runs `claude -p` in the escalation agent's home with the incident file as the prompt's subject, with the tools the policy needs, reads the verdict line, and records the outcome and session id. An incident left being handled by a drainer that died is taken up again after a time limit.
- **The escalation agent's home**, one directory per machine, such as `~/agents/<name>` on ned-box, whose `CLAUDE.local.md` holds the policy: what the agent may fix itself, what it must bring to the user, how it writes the outcome into the incident file, and the verdict line it must end with. It is not an agent-seat: no handoff-supervisor, no tmux session, nothing running between incidents. The crash restart watcher and the Mac's login restart therefore never see it, and need no change.
- **The user's window.** For a "user needed" verdict, the drainer opens a window on the Mac: on ned-box with `scripts/open-mac-window-from-ned-box.py` running a small script on ned-box that prints the incident's summary and runs `claude --resume <session id>` in the escalation agent's home; on the Mac with `scripts/open-iterm-window-running-command`. The window opens once per incident. When the Mac cannot be reached (ssh exit 255), the incident keeps a "window not yet opened" mark and the next drainer run tries again, as the crash restart watcher does for its notices. The agent writes the outcome into the incident file when the user and it are done; until then the incident stays user needed.
- **The Claude health check**, a scheduled job every hour on each machine, runs one short `claude -p` request on the cheapest model. Its failure opens the plain window once per outage, recorded in a state file on that machine; its success after a failure clears the outage and turns incidents waiting for Claude back to waiting. The drainer runs the same check before each batch.
- **The ned-box reachability check**, a scheduled job on the Mac every five minutes, runs `ssh` to ned-box with a short time limit. After three failures in a row it opens a plain window on the Mac once per outage, recorded in a state file on the Mac, and says when ned-box answers again.

## Where it is written down

- The scheduled-jobs file's header and the installer's docstring say that every job's failure goes to the escalation agent through the wrapper, and that a nonzero exit must mean a failure.
- A program outside the scheduled jobs that runs unattended calls the report script itself; the wiki page on writing agent-facing-messages gets one sentence saying so, in its bullet on agent-sessions no user attends.
- The rule a job's author already follows stays as it is (CLAUDE.md: print what failed and exit nonzero).

## Build-slices

1. The two jobs that exit nonzero when nothing failed are changed to exit 0 in those cases, with tests.
2. The report script, the incident file and its states, and the escalation drainer, on ned-box; the escalation agent's home with its `CLAUDE.local.md`, approved by the user word for word; tests with a stand-in for `claude` and for the Mac window script, including a report arriving while a drainer runs and a repeat while fix pending.
3. The wrapper for scheduled jobs and the installer change on ned-box; a live trial with a made-up failing job.
4. The Claude health check on both machines, and the ned-box reachability check on the Mac.
5. The Mac's own drainer and wrapper, by Deferred-decision 4.
6. GHI 1058's daily step and GHI 1206's nightly report reporting through the report script, if Deferred-decision 5 says so; edits to their GHI-MDs.

Each slice is one pull request with its tests, except the `CLAUDE.local.md`, which the user approves.

## Deferred-decisions

1. **Names and new project-terms.** A check on 2026-10-13 against `docs/nedschorus-wiki/nedschorus-how-to-choose-a-name-for-files-code-and-glossary-terms.md` judged "escalation" alone too vague and proposed the system name `unattended-failure-escalation`, with its files named under `nc-systems/unattended-failure-escalation/`; it passed `/home/nedlern/nedschorus-logs/escalation-incidents/`. "Escalation agent", "escalation drainer" and "incident file" are new project-terms. Recommend the system name `unattended-failure-escalation` and that the user approves the terms before any file uses them.
2. **What the agent may fix without asking.** Recommend starting narrow, as the table says, and widening it as incidents show what is safe.
3. **Crash restart failures.** The watcher's notice today asks the user to ask an agent to investigate. Recommend the watcher calls the report script instead when Claude works, so an agent looks first, and keeps its own notice for when Claude does not.
4. **The Mac's own failures.** An agent on ned-box cannot investigate the Mac: ned-box's key to the Mac only opens windows. Recommend the Mac run the same drainer for its own jobs, with its incidents in a directory on the Mac, so a Mac failure is investigated on the Mac and ned-box being down does not stop it.
5. **Daily maintenance.** Recommend that GHI 1058's due jobs that need the user go through the report script as incidents, so one route reaches the user; the reviewers judged this unnecessary for the user's goals, so it is a later slice, not a first one.
6. **An incident that needs the user, which he ignores.** Recommend the window opens once, and a daily line in the incident's state reopens it once a day while it still needs the user.

## Verified, and not verified

- Verified on ned-box on 2026-10-13: a `claude -p` agent-session can be continued with `claude -p --resume <session id>` and remembers its first prompt. Not verified: that an interactive `claude --resume <session id>` opens that same agent-session started with `claude -p` in a window; the build checks it first.
- Verified on origin/main c2723d96: the weekly owner check already runs `claude -p` from cron with `--allowedTools Bash`, so cron's `claude` can log in. Not verified: which tool permissions the escalation agent needs; the build decides with the policy.
- Not verified: Claude Code's exact messages for a lapsed login and for a usage limit in a `claude -p` run, which the health check must tell apart.

## Review records

- Claude review (`claude -p`, Opus) and Codex review: `review-claude.md` and `review-codex.err` beside this file in the session scratchpad, shipped with the design to the log-store. Both found that an interactive agent cannot end its own agent-session (`nc-systems/handoff/handoff-supervisor.py` lines 6 to 8) and that a `dont-restart` handoff waits on `restart? y/n` in a terminal (lines 1803 to 1809), so version 1's agent would hold its seat forever; both found that a report could be lost between the agent's last look and its exit, that nonzero exits are not always failures, and that the user's health cases were deferred. Version 2 takes the Claude reviewer's simpler shape. The Codex reviewer's alternative, one agent-seat that always runs with explicit delivery, was declined because a seat that always runs still needs a delivery mechanism and still runs when nothing has failed.
