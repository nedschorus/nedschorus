---
issue: "[Memory: agents write freely, and each reincarnation drains the new entries in a walk with the user](https://github.com/nedschorus/nedschorus/issues/39)"
---

# Memory: agents write freely, and each reincarnation drains the new entries in a walk with the user

The working document is [docs/issues/39-memory-drain-at-reincarnation.md](https://github.com/nedschorus/nedschorus/blob/main/docs/issues/39-memory-drain-at-reincarnation.md), which carries the whole policy and its reasons.

## State

Ruled by the user on 2026-09-17, in the five-seat-briefs walk: agents may write memories without asking; maintenance is a walk with him at each reincarnation; memories are not separate per agent, so one store per machine serves every agent, headless runs included; the cadence is every reincarnation; the scope is nedschorus only; and the walk lists the already-approved entries first, then takes the new ones one at a time.

The document replaces this issue's original plan — two hooks echoing every memory read and write to the console — with that policy, and says why: writes have been gated since 2026-08-11 by the instruction-file guard and CLAUDE.md's approval rule, the two stores hold six entries between them, and what is still invisible is whether an entry is ever read.

## Next action

**Do not build it yet (user-ruled 2026-09-20, walk open-questions-concerns-and-recommendations-2026-09-19, item 4).** The premise this issue was filed on has not arrived: agents are not writing memories freely. Measured that day, this project's store held 3 entries on the user's Mac, in `/Users/el/.claude/projects/-Users-el-Projects-nedschorus/memory/`, and 4 on ned-box, 7 between them, against 6 when the policy was ruled on 2026-09-17. For scale, another project on the same Mac held 58. A walk that drains four entries costs more than it returns. The measurement is recorded here so the next reader sees it rather than repeating it; re-measure before reopening the build, and revisit when the store passes a threshold the user names.

The steps below stand as the design of the build, for whenever it starts. Nothing is built yet. The build needs the user's walk, because each part is instruction text or a hook:

1. `.claude/hooks/instruction-file-guard.py` stops protecting `~/.claude/projects/*/memory`, the index inside it included.
2. CLAUDE.md's memory rule changes from approve-each-write to write-then-drain.
3. A script lists the undrained entries of both stores with their origins, counts the reads in the transcripts changed since the last drain, and writes each store's marker.
4. Every incoming session counts and lists at its start; only a session with the user at the console walks the list and writes the markers.

The `fleet` seat owns the hook and the session machinery. The wider research question — memory maintenance as a topic — stays in GHI [Runtime-behavior research bundle: instruction compression + deliberate scrub, instruction precedence, output styles, context clearing, names reviewer, memory maintenance](https://github.com/nedschorus/nedschorus/issues/29).
