---
issue: "[A script that summarizes, per agent-seat, the time spent waiting on tests, on reviews, on the user and idle, from the agents' JSONL transcripts](https://github.com/nedschorus/nedschorus/issues/2257)"
---

# A script that summarizes, per agent-seat, the time spent waiting on tests, on reviews, on the user and idle, from the agents' JSONL transcripts

## What this GHI asks for

One script that reads the JSONL transcripts Claude Code already writes for each agent-session, under `~/.claude/projects/` on each machine, and prints, for each agent-seat over a period it is given, how much time the agent-seat spent in each of four states: waiting on a test run, waiting on a pull request review, waiting on the user, and idle. The script adds no logging to any agent: it works only from what the transcripts already hold.

This GHI is a placeholder: no design exists yet. The design answers these questions:

- How each of the four states is recognized in a transcript, by rules in code rather than a model's reading, such as which tool calls mark the start and end of a wait on a test run; where "waiting on the user" ends and "idle" begins; which state wins when two overlap, such as a test run in the background while the agent waits on the user; and what bucket holds time that no rule matches.
- Whether the script also reports the time an agent-seat spent working, so that waits can be read as a share of the day.
- How the script counts the time in the period when the agent-seat had no running agent-session, such as between a crash and its recovery.
- How a transcript is attributed to its agent-seat: Claude Code names each transcript's directory under `~/.claude/projects/` after the agent-session's working directory, which is the agent-home or a worktree that may since have been removed.
- How one script reads the transcripts of both machines, the Mac and ned-box, and what it reports for a machine it cannot reach.
- What the script prints, and how the period is given to it.

## Why

The user decided the script on 2026-10-14, as part of point 4 of the approval-walk ned-box-head-test-runs-in-isolated-test-environments-2026-10-14, recorded in GHI [Each test suite on ned-box runs in its own throwaway test environment, and suites start by free CPU and memory instead of waiting for a machine-wide lock](https://github.com/nedschorus/nedschorus/issues/1374), whose GHI-MD is `docs/issues/1374-each-test-suite-on-ned-box-runs-in.md`. Point 4 reads: "Separately, one script summarizes, per agent-seat, the time spent waiting on tests, on reviews, on the user and idle, from the existing JSONL transcripts, with no new logging in the agents." The build of that GHI did not include the script, and that GHI closes with this GHI carrying the work.

The test runner now records how long each test run waited and ran, but nothing says how much of an agent-seat's day those waits take, against waits on reviews and on the user and against idle time, so there is no evidence for which wait to shorten first.

## Related

On 2026-10-30, `scripts/ghi-guide-agent-ask.py --include-closed`, asked for a GHI on this script, found none. The nearest are on other matters: GHI [#972](https://github.com/nedschorus/nedschorus/issues/972), the service that keeps one record of every agent-seat, which a design may use to attribute a transcript to its agent-seat; GHI [#27](https://github.com/nedschorus/nedschorus/issues/27), on detecting an agent-session that is stuck or waiting; and GHI [#1203](https://github.com/nedschorus/nedschorus/issues/1203), which nudges a pull request's author whose review findings have gone unanswered.

## Next action

Write the design in this GHI-MD, answering the questions above; then add the line `kind: design` to the front matter at the top of this GHI-MD, between its `---` lines, and build the script in its own pull request.
