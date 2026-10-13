---
issue: "[The absence-claim reminder hook logs an error for every SubagentStop of an agent that Claude Code never writes a transcript for](https://github.com/nedschorus/nedschorus/issues/1290)"
---

# The absence-claim reminder hook logs an error for every SubagentStop of an agent that Claude Code never writes a transcript for

Filed by a subagent of the merge-lane-2 agent-seat on 2026-10-13 (UTC), from a finding it reproduced. The finding was first raised by the reviewer posting as the GitHub account mac-claude, in [its review of the pull request "Report the hard-wrap reminder, obsolete-file warning, post-compaction continue and absence-claim reminder hooks' own failures on stderr"](https://github.com/nedschorus/nedschorus/pull/1287#discussion_r4264750692). The reproduction comes first, then the cause, what the defect causes, and the next action. The hook is `scripts/absence-claim-locator-reminder-hook.py` at main `ab08e234`; Claude Code is version 2.1.296 on ned-box. The hook was built by the ned-box-helper agent-seat: all three commits that touch the hook (`bbdc3617`, `58b6137c`, `206eaa26`) are ned-box-helper's.

## Reproduction

Run on ned-box at 2026-10-13T22:41Z against the hook's fires log, `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/ned-box-helper/absence-claim-locator-reminder-fires-ned-box.jsonl`. The hook writes one line per triggering reply and one per internal error; an error line carries only `time`, `outcome` and `error`. The counts below are the log as it stood at that time. The fix-round of pull request 1287, at head `19991ff9`, makes the hook exit 0 and log nothing for a SubagentStop whose transcript is missing. It merged into main as `dc1cbe74` at 2026-10-13T23:08:15Z, so from then on the log no longer records these errors, and the command below gives the counts as they stood at that merge.

```
python3 -I - /home/nedlern/nedschorus-logs/seats/ned-box-helper/absence-claim-locator-reminder-fires-ned-box.jsonl <<'EOF'
import json, sys, re, os, glob, collections
counts = collections.Counter(); paths = set(); present = 0
for line in open(sys.argv[1]):
    record = json.loads(line)
    counts[(record.get("event"), record["outcome"])] += 1
    if record["outcome"] == "error":
        match = re.search(r"'(/[^']+/subagents/agent-[0-9a-f]+\.jsonl)'", record["error"])
        if match:
            paths.add(match.group(1))
            if os.path.exists(match.group(1)) or os.path.exists(match.group(1)[:-6] + ".meta.json"):
                present += 1
    if record.get("event") == "SubagentStop":
        print("SubagentStop", record["outcome"], record["agent_id"], bool(glob.glob(
            f"/home/nedlern/.claude/projects/*/{record['session_id']}/subagents/agent-{record['agent_id']}.jsonl")))
print(dict(counts)); print("distinct subagent paths in error lines:", len(paths), "of which have a transcript or meta.json now:", present)
EOF
```

Result:

- 9,840 lines, from 2026-10-05 to 2026-10-13. 9,813 are `"outcome": "error"`, every one a `FileNotFoundError`. 9,810 of those name a path of the form `~/.claude/projects/<project>/<session>/subagents/agent-<id>.jsonl`, 9,810 distinct paths, one per agent id.
- None of the 9,810 paths has a transcript, or the `agent-<id>.meta.json` file Claude Code writes beside every subagent transcript, now. The `subagents/` directory of every session named does exist and holds other agents' transcripts: in the 39 sessions with errors, 0 of the logged agent ids is among the agent ids that do have a transcript.
- Errors per day: 227, 22, 190, 725, 1,295, 1,347, 365, 2,342 and 3,297 (2026-10-05 to 2026-10-13).
- The 14 `SubagentStop` lines with outcome `reminded` all name an agent whose transcript exists: in those 14 cases the hook read a subagent's transcript and reminded. No error line names an agent that has a transcript, and none of the 9,810 missing transcripts appeared later, the oldest after eight days, so the errors are not a transcript written a moment after the hook ran.
- `scripts/locate-file-copies-across-machines.py agent-ae596822e4787c198.jsonl`, one of the logged names, found no copy in the log-store, in ned-box's transcripts or in the log-store's copy of the Mac's transcripts; the only hit was the transcript of the session that printed the name. Local snapshots, Timeshift and Time Machine were not searchable.

The remaining 3 error lines are not about subagents: two `Stop` events on 2026-10-10 naming a missing main transcript in `~/.claude/projects/-home-nedlern-agents-fleet-restart-at-login/`, the directory where Claude Code keeps the transcripts of sessions run in `/home/nedlern/agents/fleet-restart-at-login`, and one naming `/nonexistent.jsonl` on 2026-10-10, which looks like a test run writing to the real log. This issue does not cover those three.

## Cause

- Claude Code builds the SubagentStop payload with a path computed from the agent id, whether or not a transcript is ever written for that agent. In the 2.1.296 binary, `grep -aboF 'agent_transcript_path:lg(h)' ~/.local/share/claude/versions/2.1.296` prints the byte offset of the payload's code, 218545002; the bytes around that offset, read with `dd if=~/.local/share/claude/versions/2.1.296 bs=1 skip=218544700 count=400`, include `agent_id:h,agent_transcript_path:lg(h),agent_type:w??be.agent_type??""`. The JavaScript is minified: `h` is the agent id, as `agent_id:h` shows, and `lg` is the function that turns an agent id into a transcript path; nothing in that expression checks that the file exists.
- Claude Code fires SubagentStop for agents it never writes a transcript for. Which agents these are is not known: the hook's error lines do not record the payload's `agent_type`. In a session where one background subagent runs, the errors come about every 31 seconds; 8,723 of the errors fall inside the lifetime of a subagent that has a transcript, and 1,072 fall outside any.
- `run()` passes the path to `read_turn()`, whose `open()` raises `FileNotFoundError`. `main()` catches the exception, logs an `error` line and exits 0.

## What the defect causes

- The hook's error channel is unusable: 99.7% of the lines in the fires log are these errors, about 3,300 on 2026-10-13, so a real fault of the hook is not found among them. The three other error lines above were found only by filtering these out.
- With the pull request [Report the hard-wrap reminder, obsolete-file warning, post-compaction continue and absence-claim reminder hooks' own failures on stderr](https://github.com/nedschorus/nedschorus/pull/1287) as it stood at its first review, the hook would exit 1 on each of these events, and Claude Code shows the stderr of a hook that exits 1 to the user: about 3,000 hook-failure reports a day.
- The reminder is not lost for subagents that have a transcript: the 14 reminders above show the hook reading such transcripts.

## Next action

- Done: the hook treats a SubagentStop whose `agent_transcript_path` does not exist as nothing to check: it exits 0, prints nothing and logs nothing. The pull request [Report the hard-wrap reminder, obsolete-file warning, post-compaction continue and absence-claim reminder hooks' own failures on stderr](https://github.com/nedschorus/nedschorus/pull/1287) carried this, at head `19991ff9`, and merged into main as `dc1cbe74` at 2026-10-13T23:08:15Z; the check is `scripts/absence-claim-locator-reminder-hook.py` line 323 on main `3f71729d`.
- Next, merge-lane-2 sends this issue to ned-box-helper, the hook's owner, which decides whether these events should stay countable rather than dropped silently, for example as an outcome of their own that records the payload's `agent_type`. Logged that way, the error channel still holds only real faults, and the agents behind these events can be named; dropped silently, nothing records how often Claude Code sends a transcript path that does not exist. Close this issue with that decision as its outcome.
