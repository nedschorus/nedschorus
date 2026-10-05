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

The user also put a second daily chore into this step: report agent-seats far behind main. For every agent-seat on both machines, count the commits its checkout is behind main, and list for the user each agent-seat more than 100 commits behind. A checkout falls behind only when its agent-seat stops reincarnating, so on most days the list is empty and the report says so in one line; on 2026-10-05, every agent-seat on both machines was within 8 commits of main.

## What is not decided

1. **How the daily step runs.** Two ways. As a second line the Mac handoff-supervisor gives at the noon step: this reaches an agent-session only when one hands off after noon, and needs its own done mark, separate from the memory review's, so that two agent-seats handing off after noon do not both run the check. Or as its own job in the scheduled-jobs file, which launches an agent-session at a set time whether or not any agent-session hands off, but needs a launch with no one at the terminal. If the second way is chosen, the memory review may move with it, so the daily maintenance stays in one step.
2. **Which machine and agent-seat.** The noon step today runs on the Mac, because only the Mac can read both machines' memory stores. The wiki describes both machines, so the check needs main, the Mac, ned-box and GitHub; the Mac reaches all four, while ned-box cannot reach the Mac. Whether the check runs in whichever agent-seat hands off first after noon, or in one named agent-seat, is open.
3. **Cost per day, and a run that stops partway.** One agent-session reading the whole wiki and checking its claims costs a share of the day's model limit. How large a share is to be measured on the first runs. If the share is too large, or a run stops partway, whether the run records the pages it finished so the next run starts after them, or splits the pages across days, is open.
4. **How the user hears.** One message in the agent-session's terminal, which he often is not reading; a spoken `say` line; or the pull request alone, with the list in its description, which needs another channel on a day with no pull request.
5. **The order of building.** The second job's fixes rely on PR 1052's rule. Until that pull request merges, and for good if it does not, every fix in a guarded file needs the user's words first, so the job lists every finding for the user and fixes nothing itself.

## Next action

Settle the five open questions above with the user, then build the second job of the daily step and the report of agent-seats far behind main, their tests, and the change to `memory_review_due_lines` or to the scheduled-jobs file that the first question decides.
