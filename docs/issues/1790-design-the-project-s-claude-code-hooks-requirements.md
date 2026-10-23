---
issue: "[Design the project's Claude Code hooks: requirements drawn from the existing hooks, then keep, fix, merge, rewrite or remove each one](https://github.com/nedschorus/nedschorus/issues/1790)"
---

# Design the project's Claude Code hooks: requirements drawn from the existing hooks, then keep, fix, merge, rewrite or remove each one

## Why

Claude Code runs a hook, a program registered in `.claude/settings.json`, at fixed moments: before or after a tool call, when the user sends a prompt, when an agent stops. A hook can refuse an action, block an agent from stopping, or add a reminder to the agent's context. The project's hooks grew one at a time, each for its own failure, and no design covers them as a whole.

`.claude/settings.json` registers 31 handlers that run 27 programs. One ordinary Write of a `.py` file starts 12 handlers; one `git push` starts 10. In the seven days from 2026-10-13, across 2,778 transcripts from ned-box and the Mac, hooks sent about 7,700 reminders, refused 119 actions and blocked 91 attempts by an agent to stop.

The refusals are worth keeping: each protects something a later review cannot undo, such as a protected instruction file or a pull request's reviewed head. The reminders vary. Of 10 sampled, agents acted on 7; the 3 they ignored arrived during unrelated work or concerned a file the agent did not own. Five hooks never fired in the seven days.

The user asked whether the hooks need a refactor or a redesign, and said: "They are important so it might be a good idea to extract out the requirements, design for that and reimplement."

## State

Deferred by the user on 2026-10-21. Work starts after the repeated and failing reminders of `.claude/hooks/guarded-file-unapproved-change-afterward-backup-and-ask-hook.py`, the backup-and-ask hook, are fixed; ask ghi-info, with `scripts/ghi-info-ask.py`, which GHI or pull request carries that fix. That one hook sent 63% of the week's reminders, so fixing it first shows how much noise the other hooks make on their own.

## Inputs

- `.claude/settings.json`, and each hook program it registers.
- `docs/nedschorus-wiki/nedschorus-enforcement-ladder.md`, which orders the ways to enforce a rule: impossible, default, block, remind, detect-and-reverse, text.
- GHI [Trigger-first instruction delivery (moved from nedlern#1972): delivery timing as a property of every instruction — step-2 CLAUDE.md design input + carried design and scan](https://github.com/nedschorus/nedschorus/issues/30) and its design, `docs/issues/30-trigger-first-instruction-delivery-design.md`.
- The firing survey: `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/ned-box-helper/hook-overuse-and-design-check-survey-2026-10-20.md`. It counts each hook's reminders, refusals and stop blocks, and samples what agents did next.
- Codex's hook review: `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/ned-box-helper/hook-overuse-review-codex-2026-10-20.md`. It lists every handler and what it tells the agent, gathers published guidance, and recommends a change per hook, such as running the push citation checks instead of reminding the agent to run them.
- Related open GHIs: [One Claude Code hook starts slow work early and a later hook adds the result, and a wiki page on hook techniques for controlling and instructing agents](https://github.com/nedschorus/nedschorus/issues/1515), and [Every refusal and warning a program hands an agent says why and what to do instead](https://github.com/nedschorus/nedschorus/issues/956).

## Method

1. Write the design with the system-design skill. GHI [Type definitions for the project's kinds of markdown: what each contains, leaves out, and how long it runs](https://github.com/nedschorus/nedschorus/issues/1080) is where the user's approval of that skill, on 2026-10-20, is being written; until the skill exists, follow that GHI-MD's definition of a design. The design goes beside this GHI-MD, as `docs/issues/<this issue's number>-claude-code-hook-system-design.md`.
2. State the requirements each hook serves: what failure it prevents, at what moment, and which rung of the enforcement ladder it uses. Ask too whether the requirement belongs on a rung no hook provides, such as making the action impossible or the safe choice the default.
3. Measure each hook's run time and the words it adds to the agent's context before deciding to remove or merge it.
4. Before removing a hook that never fired, find out why: the failure it guards against may simply not have recurred, and a hook guarding against a costly failure can stay though it rarely fires.
5. The design decides, hook by hook, whether to keep, fix, merge, rewrite or remove it, and the user rules on each hook's disposition in an approval-walk.

## Next action

After the backup-and-ask hook's fixes merge, count each hook's firings in the seven days after the merge, by the method in section 1 of the firing survey, then draft the design as the Method says.
