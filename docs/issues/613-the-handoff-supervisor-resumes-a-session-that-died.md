---
issue: "[The handoff-supervisor resumes a session that died without a handoff, instead of stopping the seat](https://github.com/nedschorus/nedschorus/issues/613)"
---

# The handoff-supervisor resumes a session that died without a handoff, instead of stopping the seat

The handoff-supervisor stops when its session dies without writing a handoff. The seat then stays dark until a person notices. This issue carries the user's ruling of 2026-09-21 that the supervisor should resume the session itself, choosing by how the session died, under a bounded retry budget.

## Outcome

Done by PR [The handoff-supervisor resumes a session that died without a handoff](https://github.com/nedschorus/nedschorus/pull/651), merged 2026-09-22 as that pull request's merge commit [aff81ae4](https://github.com/nedschorus/nedschorus/commit/aff81ae4a60d275087e773722a5a5f1a27bd199f).

The budget it built is 1, not the 2 this issue asks for below: `CONSECUTIVE_RESUMES_WITHOUT_NEW_WORK_BUDGET = 1` in `nc-systems/handoff/handoff-supervisor.py`. The user ruled on 2026-09-22: "If resume doesn't work, then dont try again".

Closed 2026-09-29 by the user's "y" at walk open-items-this-seat-holds-2026-09-24, item 13.

## What happens today

`nc-systems/handoff/handoff-supervisor.py` line 1702, reached when `wait_for_handoff` returns `None`: the supervisor records the child's exit code and time in its state file, prints `session ended without a handoff; supervisor stopping`, and returns 0.

That is deliberate. The exit record is the signal that lets `scripts/recover-crashed-seats.py` tell "stopped under supervision" from "crashed" — a seat carrying a record is offered, one without is resumed. The gap is not in that distinction; it is that **nothing fires automatically**. Recovery runs only when a person or the login-time program invokes a launch.

## The behaviour that prompted it

On 2026-09-21 the MD-skills seat's session `77249333-f8e7-4597-bd9b-4a917bc20b86` finished a turn cleanly at 21:49:00Z — its stop-hook record shows `hookErrors: []`, `preventedContinuation: False`, and the context-threshold hook producing no output, so context was not the trigger. It then sat idle for 4 minutes 41 seconds and was terminated at ~21:53:47Z with exit code **143**. The supervisor's last heartbeat was 21:53:41Z, so it was alive and watching throughout.

The supervisor wrote the exit record and stopped, exactly as designed. The seat had an intact 6.4 MB transcript, five sibling seats were running normally, and this one stayed dark until the user happened to look.

## What the supervisor can and cannot know at that moment

This bounds what any rule here can discriminate on, so it is stated before the rule.

**Knowable:**

- `process.returncode` — separates a clean exit (`0`) from a signal death (`143`/`-15` SIGTERM, `137`/`-9` SIGKILL) from a non-zero error status. Already captured; simply not acted on.
- Whether the session died mid-turn or idle after a completed turn, by reading the transcript tail. The supervisor already imports the transcript reader.
- How long the session ran, and whether a handoff exists.

**Not knowable, and no code recovers it:**

- **Who sent the signal.** POSIX does not tell a parent.
- **The CLI's own error output.** `subprocess.Popen` at line 1254 passes no `stdout=`/`stderr=`, so the child inherits the console and its dying words go to the terminal, never to the supervisor. Capturing them is not free: the session is interactive and needs that terminal.

So the supervisor can know the *manner* of death and never the *agent* of it. The rule below discriminates on manner alone.

## The ruling (user-ruled 2026-09-21)

| exit code | meaning | action |
|---|---|---|
| `0` | clean exit — `/exit`, or a headless turn ending | **stop.** A clean exit is a decision, not a crash |
| `143` / `-15` | SIGTERM | **resume** |
| `137` / `-9` | SIGKILL — OOM or `kill -9` | **resume** |
| other non-zero | the CLI exited with an error status | **resume** |
| `None` | an adopted session, whose returncode this supervisor never owned | **stop** |

Two gates apply to every resume:

1. **A budget of 2 consecutive resumes that produce no new work.** The reset signal is the transcript growing: `launch_agent_session`'s docstring records that `--resume` reuses the session id in place, confirmed live 2026-08-21, so a resumed session's transcript grows under the same id. A session that dies again without writing a single record is looping and does not get a third launch. This is the gate that matters — an unattended resume loop spends money.
2. **The existing no-terminal refusal stays.** A resumed session needs a seat exactly as a successor does.

The exit record is still written on every stopping path, so `scripts/recover-crashed-seats.py` remains the fallback and its offer-versus-resume behaviour is unchanged.

## Why this is cheap

Most of the machinery exists. `RESUME_PROMPT_WHEN_A_SESSION_ENDED_WITHOUT_A_HANDOFF` is defined at line 87 and already used at lines 1533 and 1650 — but only on the **startup** path, when a launch lands on an already-dead seat. This wires the same, already-exercised mechanism into the in-loop death path.

The budget is the only genuinely new concept. Search receipt for that claim: `grep -n "attempt\|retry\|consecutive\|RESTART_\|MAX_" nc-systems/handoff/handoff-supervisor.py` returns **0 matches** on main at `4ed4e49`. There is no retry or attempt counter anywhere in the file.

## Next action

None. The issue is closed; see Outcome.

## Related

- GHI [recover-crashed-seats.py: the six changes ruled 2026-09-02 — exit record, process-identity liveness, parking marker, verified restart, by-hand resume, window](https://github.com/nedschorus/nedschorus/issues/242) — the direct sibling and attachment point. It built the exit record this rule reads, and its change 5 made a **by-hand** launch auto-resume a crashed seat. This issue is the supervisor doing it unprompted, which that issue does not cover.
- GHI [Crash recovery for seats that died without a handoff: find the last live transcript, resume it supervised](https://github.com/nedschorus/nedschorus/issues/120) — closed 2026-09-03, the original build of the resume mechanism reused here.
- GHI [Fleet survives a machine restart without losing seat context](https://github.com/nedschorus/nedschorus/issues/116) — the nearest "comes back without asking" precedent, but scoped to a machine reboot rather than a mid-session child death.
- GHI [Run named agents on the Ubuntu box](https://github.com/nedschorus/nedschorus/issues/45) — carries the supervisor/child definition and the note that live adoption of an orphaned session is built but deliberately unreached.
