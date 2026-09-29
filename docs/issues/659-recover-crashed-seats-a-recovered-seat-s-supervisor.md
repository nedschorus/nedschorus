---
issue: "[recover-crashed-seats: a recovered seat's supervisor runs from whichever checkout the recovery was run from, and stops at its next handoff once that checkout is removed](https://github.com/nedschorus/nedschorus/issues/659)"
---

# recover-crashed-seats: a recovered seat's supervisor runs from whichever checkout the recovery was run from, and stops at its next handoff once that checkout is removed

A seat that `scripts/recover-crashed-seats.py` brings back runs its handoff-supervisor from whichever checkout the recovery program was run from: a seat's own worktree, a topic worktree, anything. That supervisor then runs that checkout's code for the rest of its life, and it stops the seat at its next handoff if that checkout is later removed.

## Outcome

The user ruled on 2026-09-29, at walk open-items-this-seat-holds-2026-09-24, item 12. He answered "y" to: "always run the supervisor from the machine's reference clone, `~/Projects/nedschorus`, as the login restart already does".

PR [A recovered seat's supervisor runs from the reference clone, not from the checkout the recovery ran from](https://github.com/nedschorus/nedschorus/pull/778) built it. It merged at 2026-09-29T18:19:07Z as merge commit [Merge pull request #778 from nedschorus/recovered-seat-supervisor-runs-from-reference-clone](https://github.com/nedschorus/nedschorus/commit/45a77f90738d946792e1029d7a40919274cb754c), which closed this issue.

Both launch paths now take the supervisor from the durable checkout, `--checkout`, default `~/Projects/nedschorus`, whichever checkout the recovery runs from: on the Mac through that checkout's `launch-claude-mac`, and off macOS through a tmux command that names that checkout's supervisor. When the file a launch needs is missing there, nothing is launched and the seat is reported REFUSED, which counts as not recovered.

The reviews left one question open: `scripts/restart-live-seats-at-login.py` passes no `--checkout`, so a login restart installed with `--checkout` naming another checkout would still launch its seats from `~/Projects/nedschorus`; no install does that today, since on 2026-09-29 the Mac's launch agent and ned-box's systemd unit both name `~/Projects/nedschorus`.

## Reproduction

Measured 2026-09-22 on both machines at main as of that day, the merge commit of PR [The task viewer's refusal names only the machines it read](https://github.com/nedschorus/nedschorus/pull/656), in scratch state only: two copies of the program (`git archive` of that commit) at two different paths, a scratch `HOME` with a stub `claude` on `PATH`, scratch agents, handoff and projects roots, and a scratch seat `item4reprocanary` on its own tmux socket. The recovery was a real run, not a dry run. It ran once from copy A; then the scratch seat's tmux server was killed and the recovery ran again from copy B.

Mac (drives `launch-claude-mac`):

```
=== recovery run from .../item4-recovery-repro/mac/copyA
recover-crashed-seats: item4reprocanary: relaunched fresh (nothing to resume, no extract to read)
57113 .../Python .../item4-recovery-repro/mac/copyA/nc-systems/handoff/handoff-supervisor.py --agent item4reprocanary
=== recovery run from .../item4-recovery-repro/mac/copyB
recover-crashed-seats: item4reprocanary: relaunched fresh (nothing to resume, no extract to read)
57179 .../Python .../item4-recovery-repro/mac/copyB/nc-systems/handoff/handoff-supervisor.py --agent item4reprocanary
```

ned-box (the box branch composes the tmux command itself):

```
=== recovery run from /tmp/item4-recovery-repro-20260922172316/copyA
recover-crashed-seats: item4reprocanary: relaunched fresh (nothing to resume, no extract to read)
 605140 python3 /tmp/item4-recovery-repro-20260922172316/copyA/nc-systems/handoff/handoff-supervisor.py --agent item4reprocanary
=== recovery run from /tmp/item4-recovery-repro-20260922172316/copyB
recover-crashed-seats: item4reprocanary: relaunched fresh (nothing to resume, no extract to read)
 606943 python3 /tmp/item4-recovery-repro-20260922172316/copyB/nc-systems/handoff/handoff-supervisor.py --agent item4reprocanary
```

What happens once that checkout is gone was shown on the Mac. The copy-B supervisor module was loaded, copy B was deleted, and the module's `extract_dialog` was called. The call returned `False`, and python printed `can't open file '.../copyB/scripts/handoff-extract-conversation.py': [Errno 2] No such file or directory`. At a handoff, `False` from that call makes the supervisor print `extraction failed; not relaunching` and stop the seat.

## Why it happens

- [`scripts/recover-crashed-seats.py` line 713](https://github.com/nedschorus/nedschorus/blob/d838a59fc21c38349a6e5533e5ab303ab5028936/scripts/recover-crashed-seats.py#L713): on the Mac the launcher is `Path(__file__).resolve().with_name("launch-claude-mac")`, the one in the recovery program's own checkout.
- [`scripts/launch-claude-mac` lines 75–77](https://github.com/nedschorus/nedschorus/blob/d838a59fc21c38349a6e5533e5ab303ab5028936/scripts/launch-claude-mac#L75-L77): that launcher takes its supervisor from its own checkout. Its comment calls this deliberate for a launcher someone types: "wherever this script was run from IS the checkout it belongs to".
- [`scripts/recover-crashed-seats.py` lines 131 and 814](https://github.com/nedschorus/nedschorus/blob/d838a59fc21c38349a6e5533e5ab303ab5028936/scripts/recover-crashed-seats.py#L131): off macOS the tmux command is `python3 {SUPERVISOR_SCRIPT}`, and `SUPERVISOR_SCRIPT` is resolved from `__file__`.
- [`nc-systems/handoff/handoff-supervisor.py` lines 97, 149 and 162](https://github.com/nedschorus/nedschorus/blob/d838a59fc21c38349a6e5533e5ab303ab5028936/nc-systems/handoff/handoff-supervisor.py#L97): the supervisor derives the conversation extractor and the appended-system-prompt file from its own `__file__`. It runs the extractor at every handoff ([line 1720](https://github.com/nedschorus/nedschorus/blob/d838a59fc21c38349a6e5533e5ab303ab5028936/nc-systems/handoff/handoff-supervisor.py#L1720)) and stops the seat when extraction fails. It reads the prompt file at every launch and launches without it when the file is missing ([line 1307](https://github.com/nedschorus/nedschorus/blob/d838a59fc21c38349a6e5533e5ab303ab5028936/nc-systems/handoff/handoff-supervisor.py#L1307)). The comment at lines 146–148 already records the hazard: "a supervisor resolves this path at import, so a running one would lose it the moment the file moved."

## Why it matters

A by-hand recovery runs from whatever checkout it is invoked in; an agent that runs `scripts/recover-crashed-seats.py` from its own directory invokes its seat's worktree copy. The login restart runs from the reference clone: its launch agent and its systemd unit both name `~/Projects/nedschorus/scripts/restart-live-seats-at-login.py`. So its recoveries are unaffected, and by-hand recoveries are exposed. A seat recovered by hand from another seat's worktree has two problems:

- It runs whatever that worktree has checked out: an unmerged topic branch, or a branch far behind main. It keeps that code for every reincarnation after, because a running supervisor keeps its code until it restarts.
- Its next handoff fails if that worktree is removed: a seat retired, or a session worktree under `.claude/worktrees/` reaped by `clean-worktrees.py --remove`. Extraction fails and the seat stops, with no crash to recover from.

A seat's own worktree carries the same risk in a milder form. On this Mac on 2026-09-22, every live supervisor ran from `/Users/el/Projects/nedschorus` except the merge-lane seat's, which ran from `/Users/el/agents/merge-lane/nc-systems/handoff/handoff-supervisor.py` (from `ps`). That one was launched by hand from its worktree, not by a recovery.

## Next action

None. The issue is closed; see Outcome.

## Relations

- GHI [recover-crashed-seats.py: the six changes ruled 2026-09-02 — exit record, process-identity liveness, parking marker, verified restart, by-hand resume, window](https://github.com/nedschorus/nedschorus/issues/242): this program's owning issue. None of its six changes covers this.
- GHI [Run named agents on the Ubuntu box, reachable from iTerm2 by name: launch-claude with tmux attach-or-create, and the migration it requires](https://github.com/nedschorus/nedschorus/issues/45): records the same class of problem for `launch-claude-ubuntu` and `clean-worktrees.py`, where a fixed-location copy ran stale code.
- Search receipt: ghi-info ask, 2026-09-22, including closed issues. It found no issue covering which checkout the recovered seat's supervisor runs from. Also `gh issue list --repo nedschorus/nedschorus --search recover --state all`.

Found in the 2026-09-17 backlog walk. Reproduced and filed by an agent on 2026-09-22, as approved by the user at superwalk item 4.
