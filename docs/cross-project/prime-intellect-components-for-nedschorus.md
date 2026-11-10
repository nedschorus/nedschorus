# Prime Intellect components for NedsChorus

Research for Claude, 9 October 2026; revised 10 November 2026 to the verdict of the deep dive that replaced the planned trial.

## Verdict

Prime Intellect's software is not a base for NedsChorus, and no Prime Agent trial will run. The 9 October version of this document recommended using Prime Agent for one real NedsChorus correction, then a week of further Prime work; that plan, the "provisional selection" of Prime, and the recommendations to pause NedsChorus GHIs [41](https://github.com/nedschorus/nedschorus/issues/41), [972](https://github.com/nedschorus/nedschorus/issues/972), [749](https://github.com/nedschorus/nedschorus/issues/749), [940](https://github.com/nedschorus/nedschorus/issues/940), [754](https://github.com/nedschorus/nedschorus/issues/754), [1129](https://github.com/nedschorus/nedschorus/issues/1129), [1125](https://github.com/nedschorus/nedschorus/issues/1125) and [282](https://github.com/nedschorus/nedschorus/issues/282) while Prime was compared are all withdrawn, because each rested on the trial. This document no longer asks anyone to pause those GHIs. Git history keeps the 9 October version, at commit e640a2cf5.

On 2026-10-10 at 04:00:33Z the user replaced the trial with a deep dive into Prime Intellect and its competitors (agent-session de2b59d6 of the agent-seat prime-intellect). That was the evening of 9 October by ned-box's clock, so the log-store directories below are dated 2026-10-09. The deep dive reported to him at 04:59:51Z that Prime "isn't a base for NedsChorus" and recommended building a benchmark first; at 05:02:50Z he approved the benchmark as the first piece of work, whose first step is GHI [1505](https://github.com/nedschorus/nedschorus/issues/1505), a pilot of three past bug fixes redone by agents. The verdict is the deep dive's; the user did not dispute it, and he has decided nothing about the GHIs the earlier version proposed to pause.

## Evidence

Nothing was installed, built or run. Each statement in the first list was read in source, prime-agent at commit 56408e2 (v0.10.0-14); each in the second comes from documentation or from inference and was not checked against running software.

Read in source:

- [Prime Agent](https://github.com/PrimeIntellect-ai/prime-agent) replaces Claude Code rather than running around it. It runs its own agent loop around one model tool, a persistent Python interpreter, and reads no Claude Code hooks, skills or `CLAUDE.local.md`; it prefers `AGENTS.md` to `CLAUDE.md`.
- Prime Agent reaches a Claude subscription only by presenting itself to Anthropic as Claude Code: a Claude Code user agent, beta header, identity line and tool names. Its own login screen warns, in [`crates/pa-cli/src/provider_login.rs`](https://github.com/PrimeIntellect-ai/prime-agent/blob/56408e2a83af8b84983e83670f1e485d71d71f3d/crates/pa-cli/src/provider_login.rs): "Prime Agent identifies as Claude Code and this may violate Anthropic's terms — your account can be restricted or banned." Every agent-seat runs on one subscription, so a ban would stop all of them. The other way in is an Anthropic API key, billed per token.
- Prime Agent's daemon listens only on a local Unix socket, so nothing passes between the Mac and ned-box.
- A schedule runs inside its agent's worker process and is not re-armed after a daemon or machine restart until someone resumes that agent, and nothing installs the daemon as a service that starts at boot.
- A child agent started with Prime Agent's `rlm.spawn` function works in its parent's directory; nothing gives it its own git worktree.
- The first stable Rust release, v0.10.0, was published on 2026-10-09, the day the 9 October version was written.

From documentation or inference, not checked:

- Anthropic's published policy, as the survey read it, forbids a third-party application that runs its own agent loop from using a Claude subscription login; applying that policy to Prime Agent is the survey's inference. Whether Anthropic enforces that policy was not established.
- The [prime-agent README](https://github.com/PrimeIntellect-ai/prime-agent/blob/56408e2a83af8b84983e83670f1e485d71d71f3d/README.md) describes background agents, agent-to-agent messages, schedules, persistent goals and a bounded autonomous mode. Claude Code now documents its own background agents, cross-session messaging, scheduled tasks and worktree isolation, all on the subscription, so for agent-seats that already run Claude Code those Prime features would duplicate what Claude Code provides.

## Designs worth copying from Prime Intellect

These are designs to copy into NedsChorus code, not software to depend on:

- the [verifiers](https://github.com/PrimeIntellect-ai/verifiers) library's structure for benchmarks, a set of tasks, the program that runs an agent on each task, and a rubric that scores the result;
- verifiers' design of sending every tool call an agent makes to one policy program that can refuse it;
- the rule in the judge prompt of [prime-envs](https://github.com/PrimeIntellect-ai/prime-envs), Prime Intellect's set of benchmark tasks, "verify by running; unverified is not solved";
- the file safety of [prime-rl](https://github.com/PrimeIntellect-ai/prime-rl), Prime Intellect's training program: write to a temporary file then rename, and resume from an append-only log that reruns only unfinished work.

## Closest alternatives

The deep dive's survey of about 50 projects concluded, as inference rather than tested fact, that Claude Code's own background agents, cross-session messaging, scheduled tasks and hooks cover most of the agent invocation, agent registry and cross-machine messaging that NedsChorus had planned to build, on the subscription the agent-seats already use; Claude Code's messages reach the other machine through Anthropic's Remote Control service. It named two open-source projects as design references for what Claude Code does not cover, such as replacing an agent-seat's conversation while keeping its identity and queued work, and a merge queue: [OpenRig](https://github.com/mvschwarz/openrig), and [Gas City](https://github.com/gastownhall/gascity) with the merge queue of [Gas Town](https://github.com/gastownhall/gastown). [Pi Durable](https://github.com/earendil-works/pi/blob/main/packages/durable/README.md), the alternative the 9 October version ranked first, is a close runner-up for its design of resuming an interrupted agent, but it runs its own agent loop on an API key, as Prime Agent does.

The work the deep dive recommended, in order: a benchmark built from NedsChorus's own history, which the user approved; a hook that refuses a claim that work is done or tests pass when no test has run since the last edit; and a glossary that code can read, so that new names are checked against it.

## Sources

All in the log-store on ned-box:

- `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/prime-intellect/deep-dive-2026-10-09/deep-dive-synthesis-2026-10-09.md`, the deep dive's summary and recommended order;
- `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/prime-intellect/deep-dive-2026-10-09/reports/prime-intellect-source-code-read.md`, the source read of 13 Prime Intellect repositories, with file and line for each claim;
- `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/prime-intellect/deep-dive-2026-10-09/reports/competitors-and-alternatives.md`, the survey of alternatives, which marks each claim verified, reported or inference.
