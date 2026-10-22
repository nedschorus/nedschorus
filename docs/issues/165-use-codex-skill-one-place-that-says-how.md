---
issue: "[use-codex skill: one place that says how this project invokes Codex headlessly](https://github.com/nedschorus/nedschorus/issues/165)"
---

# use-codex skill: one place that says how this project invokes Codex headlessly

## Problem

This project invokes Codex (the `codex` CLI, `codex exec`) as a second model family for reviews and audits, and does it often. Every launch has to get the same things right, and when this issue was filed the knowledge of what those things are lived only inside three scripts. An agent that needs a Codex read for anything else — a research question, a source read, a one-off review — reproduces the flags by hand from those scripts, or gets them wrong. On 2026-08-25 the MD-skills seat did exactly that (a read of the openai/codex source for what Codex parses from markdown frontmatter): it copied the flags out of `scripts/code-review-codex-cell.py`, and that copying is the sign the skill is missing. The user directed the issue the same day: "We need to invoke codex regularly."

## What exists (verified on main, 2026-10-21)

Four programs launch `codex exec` themselves:

- `scripts/run-codex-task-from-brief.py` — the one program an agent uses to hand Codex a task: it reads the prompt from a brief file, closes Codex's stdin, writes a run log, stops Codex at a deadline, and runs it under a permission profile that denies credential files, with Codex's memory store off; options widen network access, writable folders and web search, and model and effort are options too. PR [Run Codex tasks through one program, with network, writable folders and web search; refuse a hand-typed codex exec](https://github.com/nedschorus/nedschorus/pull/1246) added it, merged as f3a170c5, together with `scripts/hand-typed-codex-exec-redirect-hook.py`, which refuses a `codex exec` typed into a Bash command and points the agent at `run-codex-task-from-brief.py`.
- `nc-systems/cold-read/cold-read-codex-cell.py` — the cold-read grid's Codex cells, formerly `scripts/md-review-codex-cell.py`, renamed when md-review became cold-read; tiers `deep` = `gpt-6.1-sol`, `second-strongest-model` = `gpt-6-luna`, both at reasoning effort `xhigh`. Its shared code, which `run-codex-task-from-brief.py` also loads, is `nc-systems/cold-read/cold-read-cell-common.py`, formerly `scripts/md-review-cell-common.py`.
- `scripts/code-review-codex-cell.py` — `codex exec review` for the merge lane, which runs it through `scripts/merge-lane-code-review-codex-cell-run-on-pull-request-head.py`; `CODEX_MODEL = "gpt-6.1-sol"`, `REASONING_EFFORT = "xhigh"` (effort user-picked 2026-08-03; xhigh "OK for codex" the same day). Its docstring is the fullest record of why each flag is there.
- `scripts/sanity-check-adversarial-prompts.py` — the /sanity-check skill's Codex runtime, formerly `scripts/sanity-check-attacks.py`; same model and effort.

The facts they share: a read-only sandbox, today a permission profile extending Codex's `:read-only` that also denies every credential file, built by `codex_credential_denying_permission_profile_arguments` in `cold-read-cell-common.py`; `--disable memories` so a cell is naive and carries no earlier session's reviews; the prompt from stdin (`-`) or a file, never typed on the command line; the answer taken out through `--output-last-message <path>`, the path cleared before the run so that a file present afterwards is provably this run's and an absent file is read as failure; stderr captured, not discarded, because on failure its tail is the only explanation; a timeout.

One fact none of them states, measured 2026-08-25 at launch: Codex loads `~/.codex/AGENTS.md` (296 words on this Mac, an OpenAI-docs preamble) and lists `~/.codex/skills/` at startup, so a "naive" cell is not fully naive — it carries whatever the machine's Codex home injects. A skill has to say what Codex reads at start and how a launcher keeps a cell clean, or state that it cannot.

GHI [run-agent: one CLI to invoke a Claude or Codex agent headlessly from any caller (Python, shell, either runtime)](https://github.com/nedschorus/nedschorus/issues/41) designs the CLI primitive (`run-agent`, one command for either runtime) these sites would collapse onto; it has stood unbuilt since 2026-08-03, and GHI [Deferred: pr-merge-decision-codex — machine merge-decision review; revisit after code-review-codex-cell accrues lane experience](https://github.com/nedschorus/nedschorus/issues/105) records the 2026-08-19 ruling that `code-review-codex-cell.py` was built small and separate rather than on it. This issue is the instruction text, not the CLI: what an agent needs to know to invoke Codex correctly today, and which primitive to call once GHI [run-agent: one CLI to invoke a Claude or Codex agent headlessly from any caller (Python, shell, either runtime)](https://github.com/nedschorus/nedschorus/issues/41) exists.

## What the skill says

A `use-codex` skill (name provisional; collision-checked 2026-08-25: no skill or script under `.claude/skills/`, `~/.codex/skills/` (which has an unrelated `codex-primary-runtime`), or `scripts/` carries the name, and ghi-info found no issue proposing the skill) at `.claude/skills/use-codex/SKILL.md`, and its Codex-side twin under `~/.codex/skills/` if Codex agents also launch Codex:

1. When to buy a Codex read: a second model family for a review or audit (the standing cross-runtime pattern, GHI [run-agent: one CLI to invoke a Claude or Codex agent headlessly from any caller (Python, shell, either runtime)](https://github.com/nedschorus/nedschorus/issues/41)'s problem statement), a read of OpenAI-side source or docs, or a task the user names Codex for.
2. The pinned model and effort per tier, in one place the scripts and the skill both cite (today the constant is repeated in three files).
3. The launch: the flags above, the prompt-on-stdin form, the output file, absence-as-failure, the stderr tail, the timeout — as a command an agent can copy, and as the script to call where one exists.
4. What Codex reads at startup on this machine, and what that means for a naive cell.
5. How the result is checked before it is used: the file exists, is one complete answer, and carries a provenance stamp (the md-review cells' `<!-- provenance: ... -->` line is the pattern).

The skill goes through a cold read before it lands.

## Next action

Draft the skill from the four programs' docstrings and the 2026-08-25 measurement; md-review it; land it on main by the interim lane (a fresh branch from main, this one topic). Then update GHI [run-agent: one CLI to invoke a Claude or Codex agent headlessly from any caller (Python, shell, either runtime)](https://github.com/nedschorus/nedschorus/issues/41) to name this skill as the instruction layer over the primitive it will build.

## Relations

- GHI [run-agent: one CLI to invoke a Claude or Codex agent headlessly from any caller (Python, shell, either runtime)](https://github.com/nedschorus/nedschorus/issues/41) — the CLI primitive; this skill is its instruction text and its first consumer once built.
- GHI [Deferred: pr-merge-decision-codex — machine merge-decision review; revisit after code-review-codex-cell accrues lane experience](https://github.com/nedschorus/nedschorus/issues/105) — the ruling that per-script wrappers stay small; GHI 105 is closed as not planned. `scripts/run-codex-task-from-brief.py` is now the one program for a Codex task an agent hands off; the three cell scripts still launch Codex themselves, and this skill documents all four, it does not consolidate them.
- GHI [md-review-grid reports eight reviews saved when eight cells produced nothing](https://github.com/nedschorus/nedschorus/issues/164) — the md-review empty-report defect; the absence-as-failure rule this skill carries is the fix's shape.

## Provisional additions (not yet vetted by the user)

- cold-read-research, 2026-10-14: a draft /codex skill exists. It describes `scripts/run-codex-task-from-brief.py`, the one program that runs a Codex task, which PR [Run Codex tasks through one program, with network, writable folders and web search; refuse a hand-typed codex exec](https://github.com/nedschorus/nedschorus/pull/1246) added (merged as f3a170c5). The draft has had its cold-read-full-run, cold-read-record SKILL-codex-skill-2026-10-13-2, and its 14-item approval-walk is prepared in the cold-read-research agent-seat, waiting to be presented to the user.
