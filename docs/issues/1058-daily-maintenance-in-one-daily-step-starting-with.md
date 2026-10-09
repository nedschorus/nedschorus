---
issue: "[Daily maintenance in one daily step, starting with a daily check of every wiki page](https://github.com/nedschorus/nedschorus/issues/1058)"
---

# Daily maintenance in one daily step, starting with a daily check of every wiki page

Gather the project's daily maintenance into one daily step, which today is the noon step, and give that step its second job: every day, check every page of the wiki against the things the pages describe, fix the obvious errors, and list the rest for the user. That the wiki check is part of the daily maintenance is decided; how the daily step runs it is open, under What is not decided.

## Why

Wiki pages describe how the fleet works: where files live, which machine runs what, which agent-seat merges. When the fleet changes, nothing re-reads those pages. The machine-paths page, `docs/nedschorus-wiki/nedschorus-fleet-machine-paths-and-checkouts.md`, went on saying that merges to main happen from the Mac after merging had moved to the agent-seat merge-lane-2 on ned-box; the page was corrected by PR [Machine-paths wiki page: merges happen at merge-lane-2 on ned-box, not on the Mac](https://github.com/nedschorus/nedschorus/pull/1049) only because an agent happened to read it while doing other work. An agent that reads a stale page acts on a false description.

The user asked for this on 2026-10-05 (UTC), in the merge-lane-backlog agent-seat: "There is a daily maintence ghi I hope. This is just one other part of daily maintence. We should check the whole wiki every day. It's not that big."

## What exists today

- **The noon step.** From noon Pacific, a Mac handoff-supervisor asks the next agent-session for the day's review of both machines' memory stores: `memory_review_due_lines` in `nc-systems/handoff/handoff-supervisor.py`, built by PR [From noon Pacific, a reincarnated Mac seat is asked for the day's review of both memory stores](https://github.com/nedschorus/nedschorus/pull/823). The line is given at a session-handoff, once per day, and a done mark keeps it from being given again. The noon step has no other job.
- **The ruling that regular maintenance goes there.** GHI [Before a seat is retired, report what still cites the paths the retirement removes](https://github.com/nedschorus/nedschorus/issues/226) records the user's ruling that work needing regular maintenance goes into the noon step rather than onto a weekly schedule, and that "Giving the noon step a second job is a separate change, made when a second job arrives." This GHI is that change.
- **Scheduled jobs.** The file `nc-systems/general-tools/scheduled-jobs-on-each-machine.json` lists each machine's scheduled jobs, and `nc-systems/general-tools/install-scheduled-jobs-on-this-machine.py --install` installs them as crontab and launchd entries. GHI [Relaunch stopped agent-seats with open tasks daily](https://github.com/nedschorus/nedschorus/issues/936) adds a daily relaunch job to that file.
- **The rule for fixing without asking.** Open PR [CLAUDE.md: an agent fixes four kinds of obvious error in guarded files without asking, and tells the user afterwards](https://github.com/nedschorus/nedschorus/pull/1052) lets an agent fix, in the files `.claude/hooks/instruction-file-guard.py` protects (the wiki among them), four kinds of obvious error without asking first: a spelling, grammar or punctuation mistake; a dead link, path, name or flag with one clear replacement; a description of how things are that the repository, the Mac, ned-box or GitHub shows to be false; and a place that a change the user approved in the same agent-session missed. An edit that changes what an agent or a program is told to do, or what a document decides, still goes to the user first.

Search receipt: `scripts/ghi-info-ask.py` on 2026-10-05, asked for an open GHI about daily maintenance, the noon step, or a periodic check of wiki pages for wrong facts, found none. The nearest are GHI [Sort the 60 standing md-drift-lint findings](https://github.com/nedschorus/nedschorus/issues/572), a one-time pass over stale citations, and GHI [Reference-integrity checker: links resolve and cited revision-paths exist — pure-code review check (and the home for what-else-can-code-check)](https://github.com/nedschorus/nedschorus/issues/42), which checks links and paths by code and does not read what a page claims.

## What the second job does

Once a day, an agent-session reads every page under `docs/nedschorus-wiki/`, the pages under `docs/nedschorus-wiki/queue/` excepted, because those wait for the user's approval and change under the queue-drain. It works in a worktree of its own, on a topic branch cut from main, so the work of the agent-seat that runs it is not disturbed. For each statement a page makes about how things are, it checks the statement against the thing the statement describes, not against the page's own citations: a path against the repository on main, a machine's setup against that machine, an account or a rule against GitHub. It uses read-only commands for the checking; when a machine or GitHub cannot be reached, it lists the statements it could not check and says why, and does not work around the failure. Then:

- It fixes every obvious error, as PR 1052's rule defines one, and opens one pull request for the day's fixes, naming in the commit message the source that shows each fact false. On a day with nothing to fix it opens no pull request.
- It lists every other finding for the user: a statement it could not check, a fix with more than one plausible replacement, and any change to what an agent or a program is told to do or to what a document decides.
- It sends the user one short message: how many pages it read; what it fixed, with the pull request's link; and the list of other findings. On a day with nothing found, the message says so in one line.

## One more job for the daily step

The user also put another daily chore into this step, besides the wiki check: report agent-seats far behind main. For every agent-seat on both machines, count the commits its checkout is behind main, and list for the user each agent-seat more than 100 commits behind. A checkout falls behind only when its agent-seat stops reincarnating, so on most days the list is empty and the report says so in one line; on 2026-10-05, every agent-seat on both machines was within 8 commits of main.

## A third job: a pending ned-box reboot or firmware update

Ubuntu's unattended-upgrades installs ned-box's package updates every day by itself, but it neither reboots ned-box nor installs firmware, so a pending reboot or firmware update can wait with nobody told. On 2026-10-08 ned-box had been up 8 days; `/var/run/reboot-required` had said since 2026-10-02 that it needed a reboot, for a new kernel and `gnome-shell`; and `fwupdmgr get-updates` listed a UEFI dbx update, version 20260707. An agent found this only by checking. The user approved adding this job on 2026-10-08, as item 2 of the approval-walk merge-lane-2-waiting-on-user-walk-2026-10-07, whose minutes are at `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/merge-lane-2-waiting-on-user-walk-2026-10-07-minutes.md` once that approval-walk closes.

Each day the daily step checks ned-box for two things, running the commands on ned-box, either directly or over ssh from the Mac; which machine runs the daily step is open question 2 below:

- **A pending reboot:** the file `/var/run/reboot-required` exists. The file's modification time says since when; `/var/run/reboot-required.pkgs`, when present, names the packages that asked for the reboot.
- **A pending firmware update:** `fwupdmgr get-updates` lists one or more updates.

When either is pending, the daily step tells the user, in its message to him like its other jobs, what is pending and since when, and gives him the commands for what is pending, to run from his Mac, where he sits:

- a firmware update: `ssh -t nedlern@ned-box 'sudo fwupdmgr update'`. Installing firmware may itself ask for a reboot, so when both are pending the firmware command comes first.
- a reboot: `ssh -t nedlern@ned-box 'sudo reboot'`. The message also tells him that the reboot ends every agent-session on ned-box, and that `scripts/restart-live-seats-at-login.py`, which runs at ned-box's boot, brings back the agent-seats that were running.

When nothing is pending, the message says so in one line. When the check itself fails, because ned-box cannot be reached or `fwupdmgr` fails, the message says what failed and never says nothing is pending.

## How a daily job is handed to the user and tracked (decided)

The user ruled on this design on 2026-10-05, as item 9 of the approval-walk move-mechanical-agent-chores-into-programs-and-hooks-2026-10-04 in the reboot-test agent-seat, under chore 8 of GHI [Move mechanical agent chores into programs and hooks](https://github.com/nedschorus/nedschorus/issues/1036). He rejected a design in which the handoff-supervisor marks a daily reminder "started" by itself when it hands the reminder out, and approved the design below with "Y - make sure your notes are clear and complete." The walk-minutes, with his words in full, are at `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/move-mechanical-agent-chores-into-programs-and-hooks-2026-10-04-minutes.md` once that approval-walk closes.

His reasons, in his words: "we need a daily reminder. It needs to show up in a way I can see. It should show up in an existing agent or reincarnated agent." "the agent has to actually show it to me and stop, not just show it to me and keep going." "if it's marked completed, then it runs again tomorrow. If it's marked deferred, maybe it runs um, an hour later." "what I don't want to have happen is that I, it pops up some sort of maintenance cycle thing for me, and somehow I get skipped without anybody noticing. In that case, I would have the next reincarnation try again, uh, which means we'll need some sort of state or lock on on the maintenance cycle." On where the state lives: "maybe it's in that database, though I'd prefer something simpler if possible."

The design:

- **One state file per daily job per day.** For example, the memory review on 2026-10-05 has the file `memory-review-2026-10-05.json`. Each daily job the daily step covers, the memory review and the wiki check among them, has its own file for each day.
- **Each file holds one of four states:**
  - **due:** nobody is handling the job.
  - **shown:** the job has been handed to one named agent-session. That agent-session must show the job to the user and stop: it ends its turn and waits for his answer, rather than showing the job and carrying on with other work.
  - **completed:** the user said the job is done. The job is due again the next day.
  - **deferred:** the user said later. The job is due again an hour later, or at the time he names.
- **Only the user's answer moves a job to completed or deferred.** The agent-session records his answer, with his words, and that record is what changes the state. Nothing else marks a job completed or deferred.
- **A job shown to an agent-session that ends without an answer goes back to due.** If the agent-session the job was shown to ends in any other way, by a crash, a reincarnation, or being closed, with no answer recorded, its handoff-supervisor sees this when the agent exits and sets the state back to due. The next reincarnation on any agent-seat then picks the job up. So a job handed out and never answered is never silently lost.
- **Supervisors change a state file only under a file lock.** Two agent-seats restarting at the same moment therefore cannot both take the same job.
- **Storage is a file with a lock.** The state may move into the agent-seat database of GHI [A small service on ned-box keeps one record of every agent-seat on both machines](https://github.com/nedschorus/nedschorus/issues/972) if that database is built.
- **It replaces the current marks.** For every job the daily step covers, this design replaces the "started" and "done" mark scripts used today, `nc-systems/handoff/daily-memory-review-mark.py` and `nc-systems/handoff/daily-overview-refresh-reminder-mark.py`.

## What is not decided

1. **How the daily step runs.** Settled by the ruling above: a handoff-supervisor hands a due job to an agent-session, and the per-job state file with its lock replaces the separate done marks, so two agent-seats handing off at once cannot both take a job. The ruling says the reminder shows up "in an existing agent or reincarnated agent"; how a due job reaches an agent-session that is already running, rather than one starting at a reincarnation, is open. Whether a scheduled job in the scheduled-jobs file also starts an agent-session when none hands off is open.
2. **Which machine and agent-seat.** The noon step today runs on the Mac, because only the Mac can read both machines' memory stores. The wiki describes both machines, so the check needs main, the Mac, ned-box and GitHub; the Mac reaches all four, while ned-box cannot reach the Mac. The ruling above has the next reincarnation on any agent-seat pick up a due job; whether a job that needs the Mac, such as the memory review or the wiki check, is handed only to agent-sessions on the Mac is open.
3. **Cost per day, and a run that stops partway.** One agent-session reading the whole wiki and checking its claims costs a share of the day's model limit. How large a share is to be measured on the first runs. If the share is too large, or a run stops partway, whether the run records the pages it finished so the next run starts after them, or splits the pages across days, is open.
4. **How the user hears.** Partly settled by the ruling above: the agent-session the job is shown to shows it to the user and stops, ending its turn to wait for his answer. Still open: whether a spoken `say` line goes with it, since he often is not reading that agent-session's terminal, and where the wiki check's list of findings goes on a day with no pull request.
5. **The order of building.** The second job's fixes rely on PR 1052's rule. Until that pull request merges, and for good if it does not, every fix in a guarded file needs the user's words first, so the job lists every finding for the user and fixes nothing itself.
6. **Details the state-file ruling leaves open.** The ruling above decides the four states and who may change them; these details are for the build: where the state files live, and how a lock works when supervisors on the Mac and on ned-box both hand out jobs, given that ned-box cannot reach the Mac; whether the agent-session writes the user's answer into the state file itself or into a record a supervisor applies; what moves a job out of shown when the agent-session stays alive but idle without an answer; what turns a deferred job back to due at its time while agent-sessions are already running; how a time the user names for a deferral is recorded; which time zone sets the day, and what happens to a job still due, shown or deferred when the day changes; and the fields of the state file.

## Next action

Settle the six open questions above with the user, then build the second job of the daily step, the report of agent-seats far behind main, and the check for a pending ned-box reboot or firmware update, their tests, and the change to `memory_review_due_lines` or to the scheduled-jobs file that the first question decides.
