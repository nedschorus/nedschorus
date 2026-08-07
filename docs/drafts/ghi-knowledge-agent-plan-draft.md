---
status: draft for the user's walk
design-as-of: 2026-08-07
---

# ghi-knowledge-agent — plan for the user's walk

*(The name is provisional and is walk item 2. The user called `ghi-knowledge-agent` "pretty good", 2026-08-07 — not yet a ruling.)*

**This agent is an instance of a class the project already designed.** [26-dynamic-agent-team-model.md](../issues/26-dynamic-agent-team-model.md) (pair of [nedschorus#26](https://github.com/nedschorus/nedschorus/issues/26)) defines **domain-knowledge agents**: long-lived domains, and "the GHIs" is the first domain that document lists; short tasks (answer a question, maintain the domain); lifecycle active / idle / exited, with exited-by-default and on-demand spawn as the fallback until idle-wake is verified; and the ruling that the expert's real asset is *its curated domain files, which a fresh spawn loads in seconds*. This plan is that class's first concrete build, and its decisions should land consistent with that document or explicitly revise it.

**Lifecycle refinement (user, 2026-08-07):** a headless resume-per-question agent has no idle state — it is active only while taking a turn, and otherwise exited: what persists between turns is a session id, its transcript, and its curated files, not a process. "Idle" describes a live process waiting — an interactive session, or a watcher/shadow agent monitoring other agents (who might themselves be idle) — and knowledge agents are probably not that kind. For this class, § 26's exited-by-default fallback is therefore the design, not a fallback. Whether 26-dynamic-agent-team-model.md's lifecycle line is revised to say so lands with this plan. The agent-roster question on [nedschorus#45](https://github.com/nedschorus/nedschorus/issues/45) (open question 3) will want this agent's name and cold-start instructions once ruled.

A dedicated agent that holds this project's GitHub issues in context. Another agent, before filing or editing an issue, asks it which issues they should read, and gets an answer. Replaces the gate direction rejected at [ghi-gatekeeper-plan-draft.md](ghi-gatekeeper-plan-draft.md): nothing is gated, because unmediated access was never the problem. The two problems are that an agent about to write does not know what related issues already exist, and that issues get written carelessly. This plan addresses the first; the second stays with the `ghi-write` skill ([ghi-write-skill-draft.md](ghi-write-skill-draft.md)).

## Walk order (opened 2026-08-07, new-vp session 3a11d08f)

1. The shape — what is asked, what comes back
2. The agent's name and where it lives
3. Staying current — context growth across resumes, and issues changing underneath it
4. The invocation and the answer's form
5. What `ghi-write`'s search-first step becomes
6. Unavailable, slow, or wrong — what the asking agent does then
7. What this agent does not cover

## The shape, as understood

Your direction, restated for confirmation at item 1:

- One long-lived agent per project, whose job is knowing the issue set — not writing issues, not deciding routing.
- An asking agent invokes a prompt that resumes it, poses the question, and reads the answer when it exits.
- The answer is a set of issues the asker should read, not a summary that replaces reading them.
- Cheap enough to sit in front of every file-or-edit, since that is where it is meant to fire.

## The verified precedent

NM (`~/Projects/nedsmessenger`) already runs this pattern, and its mechanics are the reference implementation, verified 2026-08-07 at `adapter/adapter.py:379` (`ask_claude`):

- `claude -p <prompt> --output-format stream-json --verbose --permission-mode bypassPermissions --model <model>`, plus `--resume <session-id>` when a session already exists for that conversation.
- One persisted session id per conversation; the first call omits `--resume` and injects history instead.
- The answer is read off the exit stream by the caller.
- Unattended authentication uses a long-lived `CLAUDE_CODE_OAUTH_TOKEN`, because an interactive login expires with no human to refresh it.
- Three watchdogs kill a stuck run — idle silence, a silent in-flight tool call, and a total-runtime backstop — so a hung agent cannot block its caller forever.

## Open questions, each with its item

- **Item 3 is the load-bearing one.** A resumed session's context only grows: every question and answer stays in it, so the agent needs recycling on the same terms as any long-lived session, and its knowledge is only as fresh as its last read of the issue set. "Keeps the issues in context" therefore needs a stated refresh discipline and a stated recycle behavior, or the agent silently answers from a stale picture — the failure that is hardest to notice, because a confident wrong answer looks like a right one. Two mechanisms are on the table (user, 2026-08-07), and they compose rather than compete:
  - **Incremental refresh each run** — possible, verified 2026-08-07: issues are listable by update time (`gh issue list --state all --search "sort:updated-desc" --json number,updatedAt`) and filterable to a window (`--search "updated:>2026-08-06"` returned exactly the one issue touched since). So "read everything that changed since my last look, then answer" is one call. GitHub documents `updated` as moving on body edits and comments alike; that claim is verified at build.
  - **An ingest program** — reads all of a project's issues and produces the best form for a knowledge agent to load (the user suggested JSON). This is the § 26 curated-domain-file ruling made concrete: the durable asset that survives recycling is the file, not the session; a fresh spawn loads it in seconds, and the incremental query is then only the delta since the file was built. Form (JSON vs MD), owner (the agent maintains its own file vs a separate program), and refresh cadence are item 3's decisions.
- Whether the asker passes the issue text it intends to write, or only a subject line — the more the agent sees, the better it can match, and the more it costs.
- Whether "which issues should I read" and "is this a duplicate" are one question or two.
