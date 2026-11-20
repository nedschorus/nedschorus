---
issue: "[Pause and resume scheduled jobs during an emergency stop with pause-job and resume-job commands of the emergency-stop stop-file program](https://github.com/nedschorus/nedschorus/issues/3075)"
---

# Pause and resume scheduled jobs during an emergency stop with pause-job and resume-job commands of the emergency-stop stop-file program

## Why

During an emergency stop, the scheduled jobs keep running. The user ruled on 2026-10-30 that they are "listed for pausing by hand" ([GHI 2161, "Build the emergency-stop skill, which writes one stop file in the log-store that every agent-session is shown until the user lifts the stop"](https://github.com/nedschorus/nedschorus/issues/2161), item 9.1.2.1 part 1). On 2026-11-08 he approved item 31 of approval-walk ghi-783-ghi-md-picks-and-renames-approval-walk-2026-11-05, which writes that pausing out as English steps in step 2 of "Coordinating the repair" in `.claude/skills/emergency-stop/SKILL.md`, in [PR 2731](https://github.com/nedschorus/nedschorus/pull/2731): the coordinator comments out a crontab line or runs `launchctl bootout gui/$(id -u)/<label>`, and lists each paused job in the repair brief; whoever lifts the stop reads that brief and turns each job back on.

Those steps need no judgment, so code-prompt-code puts them in code. On 2026-11-10 the user approved item 38 of the same walk, "Pause and resume scheduled jobs with code, in a follow-up", answering "A" to its recommendation: "keep item 31's steps in PR 2731, and file a follow-up GHI for `pause-job` and `resume-job` commands, built on the scheduled-jobs installer, which replace those steps when they land." The walk-document is `docs/walk/ghi-783-ghi-md-picks-and-renames-approval-walk-2026-11-05.md`. This GHI is that follow-up.

Until it lands, the paused jobs are listed only in a free-text brief, and whoever lifts the stop may not be whoever paused them, so a job nobody turns back on stays paused.

## What to build

1. Add two subcommands to the stop-file program `nc-systems/skills/emergency-stop/emergency-stop-file-write-start-append-and-stop-lift.py`, which is on PR 2731's branch until that pull request merges:
   - `pause-job <name>`, run while a stop is in force, records the scheduled job `<name>`, with this machine's name, in the emergency-stop file in force, then takes the job off this machine, then checks with the installer that it is no longer installed. Run when no stop is in force, it prints FAILED and changes nothing. Given a name the table does not place on this machine, it prints FAILED, names the machines the table does place the job on, and changes nothing. When the table places the job on the other machine as well, it says so, so that the coordinator has it paused there too.
   - `resume-job <name>` puts the job back on this machine and records that.
2. Both reuse `nc-systems/general-tools/install-scheduled-jobs-on-this-machine.py` and its table `nc-systems/general-tools/scheduled-jobs-on-each-machine.json`. The table names the machines, `mac` and `ned-box`, and gives each job's scheduler, cron or launchd, on each; the installer finds which of them it runs on from the table, and the new subcommands use those names when they record a machine. The installer already takes named jobs off with `--remove --job <name>` and puts them back with `--install --job <name>`; the new subcommands drive it rather than editing crontab lines or launchd jobs themselves. Resuming turns the schedule back on and does not run the job now, so the installer's `--start-once` is not used.
3. `lift` resumes every job the stop file records as paused on this machine and not yet resumed, and lists those recorded on the other machine, so that the coordinator asks an agent-seat there to run `resume-job` for each. ned-box cannot reach the Mac's launchd, so `lift` cannot resume a Mac job from ned-box. A job that fails to resume does not stop the lift: `lift` tries every job, appends the lift line, prints a FAILED line for each job it could not resume, and exits nonzero.
4. Replace item 31's English steps for pausing and resuming in `.claude/skills/emergency-stop/SKILL.md` with a line telling the coordinator to run `pause-job <name>`, on the machine the job runs on, for each job whose run would harm the repair, and with a line saying what to do with the jobs `lift` lists for the other machine and the ones it reports FAILED.

## Design points to carry

- The hook `nc-systems/skills/emergency-stop/emergency-stop-file-shown-and-push-and-merge-refusal-hook.py` and the `status` subcommand read the stop file through `nc-systems/skills/emergency-stop/emergency-stop-file-in-force-read-common.py`. A new record line must not change what they read, such as by making the file read as Unreadable.
- That reader counts a stop as lifted only when the lift line is the stop file's last line. So `lift` writes its resume records before it appends the lift line; a record written after the lift line would put the stop back in force.
- A `resume-job` run on the other machine after the lift must not put the stop back in force. Its record therefore cannot be a line appended to the lifted stop file; the build chooses where it goes, such as a file beside the stop file, and the reader must still find it.
- After a lift, a job recorded as paused and not yet resumed would otherwise be forgotten, since the hook no longer shows a lifted stop. So `status`, and the hook on each machine, keep naming the jobs recorded as paused on that machine and not yet resumed, until `resume-job` records each one.
- A pause or a resume that fails prints a line opening FAILED that names the job and the machine, and exits nonzero. A pause that took the job off but whose record could not be written also prints FAILED, saying the job is paused and not recorded, so that no job is paused without either a record or a FAILED line.
- Tests cause each failure the code handles, such as the installer failing to take a job off or to put it back.

## When

This waits on PR 2731 merging, because the program and the SKILL.md this GHI changes are on that pull request's branch.

## Next action

After PR 2731 merges, prime-intellect, the agent-seat on ned-box that wrote the emergency-stop skill in PR 2731, builds the four steps above in one pull request, with tests.
