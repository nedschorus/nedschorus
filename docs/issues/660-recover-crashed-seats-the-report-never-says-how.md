---
issue: "[recover-crashed-seats: the report never says how to reach the recovered seat, which lives on its own tmux socket](https://github.com/nedschorus/nedschorus/issues/660)"
---

# recover-crashed-seats: the report never says how to reach the recovered seat, which lives on its own tmux socket

When `scripts/recover-crashed-seats.py` brings a seat back, its report says the seat was relaunched but never says how to reach it. Every seat lives on its own tmux socket (`tmux -L <seat>`), so the obvious `tmux attach -t <seat>` finds nothing. The operator is left to work out the socket, or to know that re-running the launcher attaches.

## Reproduction

Measured 2026-09-22 on both machines at main as of that day, the merge commit of PR [The task viewer's refusal names only the machines it read](https://github.com/nedschorus/nedschorus/pull/656), in scratch state only. The setup was a scratch `HOME` with a stub `claude` on `PATH`, scratch agents, handoff and projects roots, and a scratch seat `item4reprocanary`. The recovery was a real run, not a dry run.

ned-box:

```
recover-crashed-seats: item4reprocanary: relaunched fresh (nothing to resume, no extract to read)
--- plain tmux attach target on the default socket:
can't find session: item4reprocanary
(exit 1)
--- the seat's own socket:
(exit 0)
```

The two checks were `tmux has-session -t =item4reprocanary`, which is where a plain `tmux attach` looks, and `tmux -L item4reprocanary has-session -t =item4reprocanary`. The Mac gave the same report line, `relaunched fresh (nothing to resume, no extract to read)`. On the Mac the launcher puts the seat on the same per-seat socket ([`scripts/launch-claude-mac` line 300](https://github.com/nedschorus/nedschorus/blob/d838a59fc21c38349a6e5533e5ab303ab5028936/scripts/launch-claude-mac#L300), `SEAT_TMUX_SOCKET="$AGENT_NAME"`).

Every success line in the program is composed without a way to reach the seat. Search receipt: `grep -n attach scripts/recover-crashed-seats.py` on main finds no report string that names an attach command or the launcher's attach form. The lines are [1578](https://github.com/nedschorus/nedschorus/blob/d838a59fc21c38349a6e5533e5ab303ab5028936/scripts/recover-crashed-seats.py#L1578), [1626](https://github.com/nedschorus/nedschorus/blob/d838a59fc21c38349a6e5533e5ab303ab5028936/scripts/recover-crashed-seats.py#L1626), [1648](https://github.com/nedschorus/nedschorus/blob/d838a59fc21c38349a6e5533e5ab303ab5028936/scripts/recover-crashed-seats.py#L1648), [1665](https://github.com/nedschorus/nedschorus/blob/d838a59fc21c38349a6e5533e5ab303ab5028936/scripts/recover-crashed-seats.py#L1665) and [1684](https://github.com/nedschorus/nedschorus/blob/d838a59fc21c38349a6e5533e5ab303ab5028936/scripts/recover-crashed-seats.py#L1684). The sharpest case is [line 1521](https://github.com/nedschorus/nedschorus/blob/d838a59fc21c38349a6e5533e5ab303ab5028936/scripts/recover-crashed-seats.py#L1521). There, a seat whose handoff asks to be consulted is relaunched at the operator's word, and the report ends "answer it in the seat's tmux session". The seat's supervisor is waiting on a question in a detached session, and the report does not say how to get to it.

## Why it matters

The launchers already hold the answer and print it in their own refusal: `(attach with: launch-claude-mac $AGENT_NAME)`, at [`scripts/launch-claude-mac` line 447](https://github.com/nedschorus/nedschorus/blob/d838a59fc21c38349a6e5533e5ab303ab5028936/scripts/launch-claude-mac#L447), and the twin at [`scripts/launch-claude-ubuntu` line 424](https://github.com/nedschorus/nedschorus/blob/d838a59fc21c38349a6e5533e5ab303ab5028936/scripts/launch-claude-ubuntu#L424). Recovery's own launches are detached: on the Mac unless `--open-iterm-window-per-seat` is passed, and on ned-box always. So after an ordinary recovery the seat runs where nobody can see it, and the report is the operator's only pointer to it. Recovery on ned-box is normally run over ssh, and there the reach is `launch-claude-ubuntu <seat>` from the Mac, or `tmux -L <seat> attach -t <seat>` on the box. Neither appears.

## Next action

Add one reach clause to every report line in which a seat is left running, and cover it in `scripts/recover-crashed-seats-test.py`. On the Mac the clause names `launch-claude-mac <seat>`, the launcher's attach-or-create form. Elsewhere it names `launch-claude-ubuntu <seat>`, run on the Mac, or `tmux -L <seat> attach -t <seat>` on the box. The user decides which of the two ned-box forms the line names, or both. The recovery log records the report line, so the clause lands there as well.

## Outcome

Built by PR [recover-crashed-seats: every line that leaves a seat running says how to reach it](https://github.com/nedschorus/nedschorus/pull/969), merged on 2026-10-03 as commit 2e6ddc48. Every report line in `scripts/recover-crashed-seats.py` that leaves a seat running now ends with a reach clause. That includes the resume, fresh, ignite and plain-relaunch lines, the line for a seat restarted after its supervisor recorded the exit, and the line for a seat that asked to be consulted. On the Mac the clause names `launch-claude-mac <seat>`. For a ned-box seat it names both forms, the Mac form first: `launch-claude-ubuntu <seat>` from the Mac, or `tmux -L <seat> attach -t <seat>` on ned-box. The user chose both forms ("969 - both", 2026-10-03). `scripts/recover-crashed-seats-test.py` covers the clause on each path.

## Relations

- GHI [recover-crashed-seats.py: the six changes ruled 2026-09-02 — exit record, process-identity liveness, parking marker, verified restart, by-hand resume, window](https://github.com/nedschorus/nedschorus/issues/242): this program's owning issue. Its change 6, `--open-iterm-window-per-seat`, makes a recovered Mac seat visible when asked for, but does not change the report of a default recovery.
- GHI [Run named agents on the Ubuntu box, reachable from iTerm2 by name: launch-claude with tmux attach-or-create, and the migration it requires](https://github.com/nedschorus/nedschorus/issues/45): the attach-or-create launchers whose form the report should name.
- Search receipt: ghi-info ask, 2026-09-22, including closed issues. It found no issue covering the report's reach command. Also `gh issue list --repo nedschorus/nedschorus --search recover --state all`.

Found in the 2026-09-17 backlog walk. Reproduced and filed by an agent on 2026-09-22, as approved by the user at superwalk item 4.
