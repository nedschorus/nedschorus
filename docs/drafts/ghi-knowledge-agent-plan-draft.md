---
status: draft for the user's walk
design-as-of: 2026-08-07
---

# ghi-knowledge-agent — plan for the user's walk

*(The name is provisional and is walk item 2. The user called `ghi-knowledge-agent` "pretty good", 2026-08-07 — not yet a ruling.)*

**This agent is an instance of a class the project already designed.** [26-dynamic-agent-team-model.md](../issues/26-dynamic-agent-team-model.md) (pair of [nedschorus#26](https://github.com/nedschorus/nedschorus/issues/26)) defines **domain-knowledge agents**: long-lived domains, and "the GHIs" is the first domain that document lists; short tasks (answer a question, maintain the domain); lifecycle active / idle / exited, with exited-by-default and on-demand spawn as the fallback until idle-wake is verified; and the ruling that the expert's real asset is *its curated domain files, which a fresh spawn loads in seconds*. This plan is that class's first concrete build, and its decisions should land consistent with that document or explicitly revise it.

**Lifecycle refinement (user, 2026-08-07):** a headless resume-per-question agent has no idle state — it is active only while taking a turn, and otherwise exited: what persists between turns is a session id, its transcript, and its curated files, not a process. "Idle" describes a live process waiting — an interactive session, or a watcher/shadow agent monitoring other agents (who might themselves be idle) — and knowledge agents are probably not that kind. For this class, § 26's exited-by-default fallback is therefore the design, not a fallback. Whether 26-dynamic-agent-team-model.md's lifecycle line is revised to say so lands with this plan. The agent-roster question on [nedschorus#45](https://github.com/nedschorus/nedschorus/issues/45) (open question 3) will want this agent's name and cold-start instructions once ruled.

A dedicated agent that holds this project's GitHub issues in context. Another agent, before filing or editing an issue, asks it which issues they should read, and gets an answer. Replaces the gate direction rejected at [ghi-gatekeeper-plan-draft.md](ghi-gatekeeper-plan-draft.md): nothing is gated, because unmediated access was never the problem. The two problems are that an agent about to write does not know what related issues already exist, and that issues get written carelessly. This plan addresses the first; the second stays with the `ghi-write` skill ([ghi-write-skill-draft.md](ghi-write-skill-draft.md)).

## Walk order (opened 2026-08-07, new-vp session 3a11d08f; re-planned same day after the format/extraction/cross-reference discussion settled parts of the original items 1, 3, 4, and 7 — dispositions in the sections below; still 7 items)

1. The answer's form — pointers with reasons, not prose syntheses (the ruling left open from the original item 1; the direction itself — know, don't write; resume per question — is confirmed)
2. The agent's name and where it lives
3. Staying current, the remaining decisions — who builds and maintains the knowledge file, refresh cadence, recycle point (ruled already: MD; the window is spent rather than condensed; two delta feeds — `updated:>` for issues, git log for MDs; no idle state)
4. The invocation — the NM-pattern wrapper for this agent: script, caller, timeouts
5. What `ghi-write`'s search-first step becomes
6. Unavailable, slow, or wrong — what the asking agent does then
7. What this agent does not cover — scope boundary, with the MD-side candidate positions (link integrity joins maintenance; MD content is flag-not-fix) and the lean-bodies routing rule noted as riding to the `ghi-write` walk

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

## Format, extraction, and the cross-reference question (discussion opened 2026-08-07, being walked)

Raised by the user mid-walk, with a scale bound: this project is expected to stay under ~10,000 issues (projects with 100K+ exist; the bigger the issue set, the harder to understand efficiently). Three questions, with the positions taken to the walk:

1. **Best ingestion format — JSON?** Position: curation decides value, format barely does. An agent reads well-structured MD at least as well as JSON, and MD is denser per token; JSON/JSONL earns its place only where a *program* consumes the file (delta bookkeeping, diffing). The real design decision is what each issue's entry keeps — number, title, state, updated time, one-line summary, outbound references — not the syntax around it.
   *processed 2026-08-07 → REVISED then ruled: MD, for human readability and grepability. Condensation is not needed to fit — a 1M-token context holds ~3000 issues with little condensation, and that window is what this design spends (user: "instead of building a vector or graph DB of the GHIs, we're just using a modern agent" — the ruled framing). Summaries, cross-references, and a two-or-three-level information architecture remain helpful as organization, not as compression. Clarified: "big issues" meant MANY issues; complex individual issues are their own difficulty.*
2. **Is extraction faster or more reliable than querying GitHub live?** Position: the extract's value is neither speed nor reliability — it is *whole-set awareness*. Live search only returns what the asker thought to search for; a curated index the agent holds whole is what lets it answer with issues nobody thought to look for. Delta refresh (verified, `updated:>`) keeps the extract cheap. At today's ~45 issues everything fits trivially; near the 10K bound a one-line-per-issue index strains one context, so tiering (open vs closed) is the named growth point, not built now.3. **A GHI graph — and does the job flip from answering queries to maintaining cross-references?** Position: the graph is derivable by a program (parse `#n` references from bodies; GitHub's own cross-reference timeline events are the backlinks — verify the API shape at build). The job does not flip; it doubles, and [26-dynamic-agent-team-model.md](../issues/26-dynamic-agent-team-model.md) already names both tasks for this class: *answer a question, maintain the domain*. Maintenance = keeping cross-references current so the corpus navigates itself from any entry point; answering = the pre-write moment, which link-following cannot serve because the issue being written does not exist yet and has no links. Small, well-linked issues are themselves the scale mitigation the user's 100K observation points at.
   *processed 2026-08-07 → approved: the agent maintains cross-links and answers questions. The user's surrounding model confirmed with it: any agent may create, edit, or close issues — the how is `ghi-write`'s business, nothing is gated — and revisions are body edits, not comments; every GitHub-side change (edit, comment, close) moves the issue's updated time, so the delta feed carries them all to this agent. One build-time verification rides: that close and label changes move `updated` as body edits and comments do.*

## The MD side of the pair — open, raised 2026-08-07

Issues link to MDs (the MD-GHI pair is the project's own convention), and nothing yet keeps that boundary sound. The user named two gaps: linked MDs are not kept up to date when their issue moves, and nothing ensures an MD backlinks the correct GHI(s). One caveat makes this structural: **MD edits are invisible to the issue delta** — they land as git commits and touch no issue's updated time, so the agent needs two delta feeds: `updated:>` for the GitHub side, git log since last run for the MD side. Candidate position for the walk: **link integrity in both directions joins the maintenance task** (GHI→MD references resolve; MD→GHI backlinks exist and are correct), but MD *content* freshness is flag-not-fix — the agent reports "issue #n changed, its pair MD untouched since" rather than rewriting the MD, staying out of authorship the way it stays out of routing.

**Coupling discussion (2026-08-07).** The user leans loosely coupled: the meat is typically in the MD, which goes through many passes irrelevant to the GHI's task-tracking aspect — which is the pair convention's existing split (GHI carries state, MD carries substance, joined by links). Factual state, verified against origin/main after fetch (2026-08-07; a first check against a stale checkout missed `docs/founding/`, landed by the handoff session that day): NC has **one kind of MD file** — repository files under `docs/`, grepable, queue-promotable to the in-repo wiki (`docs/wiki/`); a github.com `blob/main/` URL is the web view of a pushed repo file, not a second store. GitHub's wiki feature is enabled on the repo but unused, and no documents live GitHub-side except **issue bodies and comments** — markdown text, but the convention's state surface, not documents. The blur that does exist: substantial issue-*only* bodies (nedschorus#13's commission is a live specimen — meaty body, no pair MD), which sit past the convention's "issue-only when lean" line. The user's don't-have-both-kinds instinct maps onto a candidate rule for `ghi-write` routing: issue bodies stay lean; when a body grows substantial working material, that is the trigger to split it into a pair MD.
