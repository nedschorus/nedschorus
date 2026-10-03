---
issue: "[A small service on ned-box keeps one record of every agent-seat on both machines](https://github.com/nedschorus/nedschorus/issues/972)"
---

# A small service on ned-box keeps one record of every agent-seat on both machines

This is a design. It proposes a small HTTP service on ned-box, in front of one SQLite database, that keeps one record of every agent-seat on both machines: which agent-seats exist, when each handoff-supervisor began and ended, how each agent-session ended where that was observed, which session-handoffs were written and consumed, and which restarts were attempted. Today four programs each answer part of that question from their own subset of about ten files, by their own rules. Nothing is installed or built yet: the next action is the approval-walk on this design's six-reviewer cold read, then the user-rulings on the open questions at the end, which include the order of the build-slices.

## The problem

An agent-seat's state is spread over about ten records, written by several programs, some writing more than one. Every line number below is on main at [2ba7cc17](https://github.com/nedschorus/nedschorus/tree/2ba7cc17765e6f03033311d1efd09c94fb63b5d1).

| Record | Written by | Read by |
|---|---|---|
| `~/.claude/handoffs/<seat>-supervisor-state.json`: consumed counter, launched session, generation, heartbeat `last_poll_at`, and the exit record | the handoff-supervisor, every 10 seconds ([`handoff-supervisor.py` line 167](https://github.com/nedschorus/nedschorus/blob/2ba7cc17765e6f03033311d1efd09c94fb63b5d1/nc-systems/handoff/handoff-supervisor.py#L167), [line 317](https://github.com/nedschorus/nedschorus/blob/2ba7cc17765e6f03033311d1efd09c94fb63b5d1/nc-systems/handoff/handoff-supervisor.py#L317)) | the handoff-supervisor; recovery, `scripts/recover-crashed-seats.py`; the login restart, `scripts/restart-live-seats-at-login.py`; `scripts/resupervise-seat.py`, which puts a handoff-supervisor back on a running agent-seat; and the handoff writer, `nc-systems/handoff/handoff-write-and-check-supervisor.py` |
| `~/.claude/handoffs/<seat>-supervisor.lock`: the handoff-supervisor's process ID | the handoff-supervisor ([line 1187](https://github.com/nedschorus/nedschorus/blob/2ba7cc17765e6f03033311d1efd09c94fb63b5d1/nc-systems/handoff/handoff-supervisor.py#L1187)) | every liveness check, which then asks `ps` whether that process is that agent-seat's handoff-supervisor, and assumes it is when `ps` cannot run ([line 494](https://github.com/nedschorus/nedschorus/blob/2ba7cc17765e6f03033311d1efd09c94fb63b5d1/nc-systems/handoff/handoff-supervisor.py#L494)) |
| `~/.claude/handoffs/<seat>-handoff.md`, the session-handoff, and its restart counter; the archived session-handoffs and the dialog extracts, `<seat>-dialog-NNNN.md` | the handoff writer ([`handoff-write-and-check-supervisor.py` line 135](https://github.com/nedschorus/nedschorus/blob/2ba7cc17765e6f03033311d1efd09c94fb63b5d1/nc-systems/handoff/handoff-write-and-check-supervisor.py#L135)) and the handoff-supervisor | the handoff-supervisor, recovery, `scripts/resupervise-seat.py` |
| the transcripts under `~/.claude/projects/` | Claude Code | the handoff-supervisor and recovery, which pick an agent-session to resume by file date |
| the task lists under `~/.claude/tasks/` | Claude Code's task tools | the task viewer, `scripts/seat-task-list-read.py`, which reads ned-box's lists over ssh |
| `~/.claude/handoffs/restart-live-seats-at-login-log.txt` | the login restart ([`restart-live-seats-at-login.py` line 225](https://github.com/nedschorus/nedschorus/blob/2ba7cc17765e6f03033311d1efd09c94fb63b5d1/scripts/restart-live-seats-at-login.py#L225)) | the login restart's next run in the same boot, which reads back the stop it recorded: a log a program also decides from |
| `~/.claude/handoffs/recover-crashed-seats-log.txt` | recovery ([`recover-crashed-seats.py` line 1131](https://github.com/nedschorus/nedschorus/blob/2ba7cc17765e6f03033311d1efd09c94fb63b5d1/scripts/recover-crashed-seats.py#L1131)) | people |
| the per-seat tmux sockets, each agent-seat's worktree under `~/agents/`, and the running processes | the launchers, `scripts/launch-claude-mac` and `scripts/launch-claude-ubuntu`, and the kernel | recovery, which proves an agent-seat's worktree empty with `lsof` ([line 259](https://github.com/nedschorus/nedschorus/blob/2ba7cc17765e6f03033311d1efd09c94fb63b5d1/scripts/recover-crashed-seats.py#L259)) and classifies a leftover shell ([line 316](https://github.com/nedschorus/nedschorus/blob/2ba7cc17765e6f03033311d1efd09c94fb63b5d1/scripts/recover-crashed-seats.py#L316)) |

Four programs each answer part of "which agent-seats exist, and in what state" from these records, by their own rules:

- **The login restart** estimates when the machine stopped: from its own run log when an earlier run in the same boot recorded the stop ([`read_earlier_run_for_this_boot`, line 174](https://github.com/nedschorus/nedschorus/blob/2ba7cc17765e6f03033311d1efd09c94fb63b5d1/scripts/restart-live-seats-at-login.py#L174)), and otherwise from the newest heartbeat written before the boot, reading a state file's modification time when its heartbeat is unreadable. It picks the agent-seats whose heartbeats fall within two heartbeat intervals, 20 seconds, of that stop ([line 114](https://github.com/nedschorus/nedschorus/blob/2ba7cc17765e6f03033311d1efd09c94fb63b5d1/scripts/restart-live-seats-at-login.py#L114)), and only offers, rather than restarts, those whose files were written since the boot ([`select_seats_live_at_the_stop`, line 255](https://github.com/nedschorus/nedschorus/blob/2ba7cc17765e6f03033311d1efd09c94fb63b5d1/scripts/restart-live-seats-at-login.py#L255)).
- **Recovery** combines the agent-seat's worktree, the agent-seat's own tmux socket and the default one older launches used, the lock's process identity and `lsof` ([`assess_seat`, line 667](https://github.com/nedschorus/nedschorus/blob/2ba7cc17765e6f03033311d1efd09c94fb63b5d1/scripts/recover-crashed-seats.py#L667)).
- **The handoff-supervisor** answers for its own agent-seat only: with no session-handoff and no exit record, it searches transcripts by date for an agent-session to resume, skipping small ones that this machinery started and that never did work.
- **The task viewer** names agent-seats from their task lists' directory names, removing the prefix `nedschorus-` and the suffix `-tasks` ([`seat_of`, line 211](https://github.com/nedschorus/nedschorus/blob/2ba7cc17765e6f03033311d1efd09c94fb63b5d1/scripts/seat-task-list-read.py#L211)); it lists task lists, not agent-seats' states.

Rules of this kind have failed. GHI [recover-crashed-seats.py: the six changes ruled 2026-09-02](https://github.com/nedschorus/nedschorus/issues/242) records that the heartbeat rule then in use would have taken a dead handoff-supervisor, whose heartbeat was 31 seconds old, for alive ([its GHI-MD, line 13](https://github.com/nedschorus/nedschorus/blob/2ba7cc17765e6f03033311d1efd09c94fb63b5d1/docs/issues/242-recover-crashed-seats-py-the-six-changes-ruled.md#L13)); that rule was replaced by the process check. The same GHI-MD records leftover shells taken for running agent-seats. GHI [The handoff-supervisor resumes a session that died without a handoff, instead of stopping the seat](https://github.com/nedschorus/nedschorus/issues/613) records an agent-seat that stayed dark until the user noticed. No single place answers "show me every agent-seat on both machines, and why each one that is down is down, where that is known".

## The design

One service, `agent-seat-database-service`, runs on ned-box and owns one SQLite database file, `~/.local/state/nedschorus/agent-seat-database.sqlite3` (a proposed path), with file permissions that let only `nedlern` read or write it. Every program that starts, supervises, hands off, restarts or recovers an agent-seat, on either machine, sends each **event** to the service. Once build-slice 4 lands, the programs that answer "which agent-seats exist" ask the service first, and read the files only when the service does not answer. Callers never see the database's tables; only the service program, its tests and the backup job open the database file.

### The service

- **Standard library only.** The service is one Python program using `http.server` with `ThreadingHTTPServer`, and `sqlite3` with write-ahead logging, a bounded busy timeout and short transactions. ned-box's Python is 3.14, with SQLite 3.46.1. Nothing is installed with `pip`.
- **A narrow JSON API of named operations**, never SQL. Each request names an operation: record agent-seat created; record agent-seat retired or paused (the glossary's retire-seat, and pausing, which the glossary keeps distinct from retiring); record machine booted, with the estimated stop of the boot before; record agent-seat started; record handoff-supervisor began; record handoff-supervisor ended; record agent-session ended, with its exit code; record session-handoff written; record session-handoff consumed; record restart attempted and its result; list agent-seats; get one agent-seat. A caller never sends SQL, so the schema can change inside the service without touching a caller.
- **Callers use `urllib`**, from Python's standard library, which works in every interpreter that runs these programs. The launchers are shell scripts, so they call a small Python helper rather than the service directly. The interpreters are Homebrew's Python on the Mac, whose LaunchAgent runs `/opt/homebrew/bin/python3` ([`install-restart-live-seats-at-login-launch-agent.py` line 52](https://github.com/nedschorus/nedschorus/blob/2ba7cc17765e6f03033311d1efd09c94fb63b5d1/scripts/install-restart-live-seats-at-login-launch-agent.py#L52)), `/usr/bin/python3` on ned-box ([`install-restart-live-seats-at-login-systemd-unit.py` line 63](https://github.com/nedschorus/nedschorus/blob/2ba7cc17765e6f03033311d1efd09c94fb63b5d1/scripts/install-restart-live-seats-at-login-systemd-unit.py#L63)), and Apple's Python 3.9, which some tests run under.

### Conditions the design keeps

1. **An agent-seat keeps working when ned-box cannot be reached.** No handoff-supervisor or launcher waits on the service (pending ruling 1). The 10-second heartbeat does not go to the service: it stays in the local state file (whether it also stays for good is pending ruling 4). Only events go to the service. A program that cannot reach the service, or gets a 5xx answer, appends the event to the machine's queue file, `~/.local/state/nedschorus/agent-seat-database-event-queue.jsonl` (a proposed path), under an exclusive `flock`; the next program run that reaches the service sends the queued events and empties the file under the same lock. Each event carries the time it happened and a unique event ID, so a replayed event is stored at its own time, a sent-twice event is stored once, and a late event never overwrites a newer one. A 4xx answer, such as a refused token or a malformed event, is not queued: the program prints the service's reason and goes on, because sending it again would fail again. Callers wait at most a few seconds for an answer, which conflicts with the sentence above until pending ruling 1 settles it. The reason: a Mac agent-seat must not stop because ned-box is rebooting.
2. **Access stays on the LAN.** The service listens on ned-box's LAN address, 10.0.1.106, and on localhost, and nowhere else. Each machine has its own token in `~/.config/nedschorus/agent-seat-database-service.token` with mode 600, sent in every request's `Authorization: Bearer` header; the service refuses a request without a known token with status 401. The reason: the record is the operating history of every agent-seat, and the LAN is the only network both machines share. Requests travel as plain HTTP; the design treats the LAN as trusted, since the project's failures come from accidents between cooperative agents, not from attackers.
3. **It starts at boot without `sudo`.** The service runs as a systemd user service of `nedlern`; lingering is already on for that user (`loginctl show-user nedlern -p Linger` printed `Linger=yes` on 2026-10-02), so the service starts at boot with nobody logged in.
4. **A nightly backup.** A scheduled job in the repository's table, `nc-systems/general-tools/scheduled-jobs-on-each-machine.json`, copies the database each night into the log-store at `nedlern@ned-box:/home/nedlern/nedschorus-logs/agent-seat-database-backups/`, through SQLite's online backup (Python's `sqlite3.Connection.backup`), never a plain file copy, which can catch the file mid-write. ned-box has no `sqlite3` command-line program installed, so the backup uses Python's.
5. **The process check stays the proof of what is running.** The process check is the one recovery uses today: whether the process ID in the agent-seat's lock is that agent-seat's handoff-supervisor, by `ps`. The database records what happened; only the process check shows what runs now. A record that a handoff-supervisor began in the machine's current boot, with none that it ended, is a question for the process check; one from an earlier boot is certainly not running.

### Alternatives considered

- **PostgreSQL on ned-box.** Mature, and built for writers on several machines. Set aside because the write volume is a few events per agent-seat per hour, and because it is a server to install, back up and upgrade, with a Python driver outside the standard library for the service, or `psql`. The service's API means PostgreSQL can replace SQLite later without touching any caller.
- **One SQLite file on each machine**, each machine reading the other's with a query program over ssh. No service to run. Set aside because it splits the record of every agent-seat in two, so every reader on either machine would join two databases, one of them over ssh. A live SQLite database is never opened over a network share, such as the Mac's mount of ned-box's home, because its file locking is unreliable there.

### Schema

This is a first guess, which pending ruling 2 reshapes and build-slice 2 settles. The table names live only inside the service; `agent_seat` and `agent_session` are also substrings of identifiers already on main, such as `agent_seat_working_directory`.

| Table, key | Columns |
|---|---|
| `agent_seat`, key `(machine, seat)` | seat directory, task-list name, created at, retired at, desired state and its reason |
| `supervisor_run`, key `run_id`: one handoff-supervisor process | machine, seat, boot ID, process ID and its start time, launched session ID, generation, began at, ended at, agent exit code |
| `agent_session`, key `(machine, session_id)` | seat, transcript path, predecessor session, launched at |
| `handoff_event`, key `(machine, seat, restart_counter)` | writer session, written at, next-step text, `dont-restart` reason, consumed by run, consumed at |
| `machine_boot`, key `(machine, boot_id)` | booted at, previous boot, stop estimated at and how the estimate was made |
| `restart_attempt`, key `attempt_id` | machine, boot, seat, why it was picked, action, began at, ended at, result, the handoff-supervisor it started |

### What stays a file

- The session-handoff file stays the session-handoff: the handoff-supervisor reads it locally, so a session-handoff works with ned-box down. The service records that it was written and consumed.
- Transcripts and task lists belong to Claude Code and stay its files; the database holds pointers to them.
- The files of an approval-walk, cold-read-records, test logs and GHI-MDs stay files: people read them whole.
- Test-run history, the daily memory-review marks and the daily overview-refresh reminder marks are later candidates, outside this design.
- Agent-seats of other runtimes, such as Codex, are outside this design; none runs today.

## The build-slices

Each build-slice is one pull request that leaves main working, followed where named by install steps the user runs or approves on ned-box.

1. **A shared reader over today's files.** One module holds the four rules above as named functions, reading the files as they are, and the four programs call those functions instead of their own copies. No behaviour changes: each program keeps its own rule, now in one place. The tests pin each rule's existing cases, which today's test suites for those programs already list.
2. **The service.** The pull request holds the service program, its schema, the systemd user unit file, the caller module with its local event queue, and the nightly backup job, with tests. The install steps, run after the merge: create the two tokens, enable the unit, and open the port if a firewall runs. No program sends events yet.
3. **Events sent.** The launchers, the handoff-supervisor, the handoff writer, the login restart, recovery and `scripts/resupervise-seat.py` send their events, queueing them when the service cannot be reached. The files still decide; the service only listens. How the agent-seats that already exist get into the service is pending ruling 3.
4. **Readers switch.** The shared reader from build-slice 1 asks the service, and reads the files when the service gives no valid answer; the program's report names which it used. When the switch is safe is pending ruling 3. The process check stays.
5. **The whole-fleet view.** One command lists every agent-seat on both machines from the service, how to reach each, and why each one that is down is down where that was recorded, with any open tasks. What the view can show from each machine is pending ruling 5.
6. **Remove what nothing reads.** Any record no program reads any more is removed. The files the build-slice 4 fallback reads stay, the login restart's run log and the heartbeat among them (pending ruling 4).

## Pending rulings from the cold read

The six-reviewer cold read of this design found six gaps that need the user's ruling, each brought to him as one item of the approval-walk named after the cold-read-record `agent-seat-database-on-ned-box-design-2026-10-02-3`. Each line below names the gap; the walk item carries the proposed remedy, and his ruling is written into this design.

1. **Event delivery.** Condition 1 says no handoff-supervisor or launcher waits on the service, yet callers wait a few seconds; a sent-twice event needs a stored set of event IDs; wall-clock time cannot order events across a clock correction; replay holds the queue lock across network calls; a partial replay, a damaged queue line and an idle agent-seat whose queue never drains are not handled; and some 4xx answers, such as 401, 408 and 429, are not permanent.
2. **The schema.** One handoff-supervisor runs many agent-sessions, so an agent-session needs its own end and exit code; a retired name can be reused, so `(machine, seat)` cannot be the key; a restart counter can repeat; and a restart attempt has no way to learn the handoff-supervisor it started.
3. **Starting the record, and when readers may trust it.** Events sent from build-slice 3 on never record the agent-seats and handoff-supervisors that already exist, and a handoff-supervisor already running keeps its old code; and a service that answers can still lack events queued on the other machine.
4. **The heartbeat and the run log stay.** The login restart's file rule, which build-slice 4 keeps as the fallback, needs both; condition 1 and build-slice 6 had left their future open.
5. **The whole-fleet view.** The only ssh route is Mac to ned-box, so a view run on ned-box cannot run the Mac's process check or read the Mac's task lists; and the cause of a stop is often unknown.
6. **Operations.** How the service learns the accepted tokens; that the bind to 10.0.1.106 can fail at boot before the LAN address exists; how a Mac caller names ned-box; the backups' retention, restore and location, since the log-store holds byproducts of the work and a backup on ned-box is lost with ned-box.

## Open questions for the user

1. **Boot ID:** the login restart needs to know which boot an event belongs to. ned-box has `/proc/sys/kernel/random/boot_id`; the Mac has no such file, so its boot would be identified by its boot time from `sysctl kern.boottime`, which a clock correction can shift: the login restart already matches boot times within 5 seconds for this reason. Is a boot time matched within 5 seconds acceptable as the Mac's boot ID?
2. **Pausing and retirement:** when an agent-seat is paused on purpose, or retired, who records it, and with what command? GHI [recover-crashed-seats.py: the six changes ruled 2026-09-02](https://github.com/nedschorus/nedschorus/issues/242) change 3 plans a durable parking marker for the paused state.
3. **Order:** build-slice 1 first as listed, or the service, build-slice 2, first?
4. **The port and the firewall:** which port the service listens on, and whether ned-box runs a firewall that build-slice 2's install steps must open for the LAN subnet only.

## Relations

- GHI [Fleet survives a machine restart without losing seat context](https://github.com/nedschorus/nedschorus/issues/116): the login restart, whose seat selection reads the service from build-slice 4.
- GHI [recover-crashed-seats.py: the six changes ruled 2026-09-02](https://github.com/nedschorus/nedschorus/issues/242): recovery's verdicts about an agent-seat.
- GHI [Seat mailboxes across machines and runtimes](https://github.com/nedschorus/nedschorus/issues/749): the nearest design whose parts run on both machines.
- GHI [recover-crashed-seats: the report never says how to reach the recovered seat, which lives on its own tmux socket](https://github.com/nedschorus/nedschorus/issues/660) and GHI [Relaunch stopped agent-seats with open tasks daily](https://github.com/nedschorus/nedschorus/issues/936): narrower work the build-slice 5 view would serve.
- Search receipt: ghi-info, 2026-10-02, open and closed issues: no issue proposes a database of agent-seats.
- Supporting document: the Codex survey of every seat record, `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/fleet-restart-at-login/agent-seat-records-survey-2026-10-02.md`.
