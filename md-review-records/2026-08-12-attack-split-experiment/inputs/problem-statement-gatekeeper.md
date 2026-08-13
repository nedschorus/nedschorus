# Problem statement: how changes reach main

<!-- fresh-eyes attack input, written 2026-08-12 for the attack-split validation experiment: the problem and goals behind the git-gatekeeper design, stated without revealing any of that design's decisions. Environment facts an independent designer could learn by probing are included; design choices are not. -->

## The situation

A small fleet of AI coding agents plus one human owner (the boss) work in one GitHub repository. The agents — Claude and Codex CLI sessions on an Ubuntu box, with the boss also working from a Mac — produce most of the changes: code, documents, records. The main branch is the durable record every agent builds on; the boss reviews some work but cannot and does not want to review every change in real time. Agent sessions crash, lose their connections, get recycled mid-task, and sometimes run concurrently in the same repository.

## The problem

Design how a change reaches main safely with near-zero routine human intervention. The dangers, all observed or obviously live: an agent pushing broken or unchecked work to main; an agent committing to the wrong branch silently; two agents landing work concurrently and colliding; push credentials spreading until any agent can bypass any policy; a crashed agent leaving a half-finished landing behind; an agent that lost its connection unable to tell what happened to its request.

## The goals

- **Near-perfect autonomous operation.** Agents recover from their own failures — a crash, a lost reply, a duplicate submission — without a human untangling state.
- **Whatever checks exist run against exactly the content that lands** — never a stale or drifted copy.
- **A machine-readable durable record** of what landed and why, findable later without asking anyone.
- **Failures teach.** When a landing is refused, the requester learns what was wrong and what to do next, in a form an agent can act on directly.
- **Minimal standing infrastructure.** The project strongly prefers deterministic scripts invoked on demand over daemons, services, or prompted-agent intermediaries; git history is the preferred durable record over side files and logs.
- **The boss can always intervene, and is never routinely required.**

## Out of scope

Deploying main anywhere (there is no production system yet). Multi-repository coordination.
