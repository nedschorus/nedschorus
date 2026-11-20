---
issue: "[Check a GHI-MD's claims about what code does and what is built against main](https://github.com/nedschorus/nedschorus/issues/3630)"
---

# Check a GHI-MD's claims about what code does and what is built against main

A GHI-MD under `docs/issues/` states what scripts and hooks do and which parts of its work are built. Nothing checks those statements against the code on main, so they go stale when a pull request changes that code without editing the GHI-MD.

## The case that showed it

Pull request [Due-task hook stops reading the old task keys waits_on and due_utc](https://github.com/nedschorus/nedschorus/pull/3255) changed `scripts/agent-seat-due-task-raise-hook.py` so that its idle check no longer names an open task carrying `waits_on` or `due_utc`. The GHI-MD of issue [940](https://github.com/nedschorus/nedschorus/issues/940), `docs/issues/940-tasks-raise-themselves-when-their-due-time-passes.md`, went on saying that the idle check names such a task. Its statements of what was built, such as whether pull request [3336](https://github.com/nedschorus/nedschorus/pull/3336) had merged, also went stale as code merged. Pull request [3466](https://github.com/nedschorus/nedschorus/pull/3466) corrects that GHI-MD by hand, and the `#root_cause_not_fixed` lines of its description link to this issue as their `#follow_up`.

## Why it matters

An agent that reads a stale GHI-MD plans work that is already done, or relies on behavior the code no longer has.

## What to do next

Decide when the check runs and what it judges, then build it. The case above shows that a check run only when a GHI-MD changes is not enough: the pull request that made the GHI-MD stale changed only code, so the check must also run when code a GHI-MD describes changes, or on a schedule.

None of the open issues below checks a GHI-MD's statements against code; ghi-guide-agent, asked on 2026-11-14 whether an open issue covers such a check, named them as the nearest. Read them first, and build the check by extending the one whose machinery fits best rather than as a new mechanism, or record in this file why none fits:

- issue [2532](https://github.com/nedschorus/nedschorus/issues/2532), the claim check that judges an nc-architecture-overview's claims against the files they cite;
- issue [2189](https://github.com/nedschorus/nedschorus/issues/2189), the daily maintenance-job in which an agent rates each changed GHI-MD;
- issue [670](https://github.com/nedschorus/nedschorus/issues/670), which brings a system's design documents into line with its code when the code lands;
- issue [42](https://github.com/nedschorus/nedschorus/issues/42), the reference-integrity checker, which checks that links resolve and cited paths exist.
