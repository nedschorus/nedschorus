# Notes on using the Codex and Gemini (Antigravity) agents from a seat (PROPOSED wiki page — draft for review)

Written 2026-09-04 by the cold-read-research seat after a day of running both as
cold-read cells. Every item here was measured, not read from docs, unless it
says otherwise. Queued for the wiki at the user's word (2026-09-04); the measurements it cites
are in the cold-read-research checkout's machine-local record
`cold-read-records/2026-09-03-cold-read-tier-roster-campaign/`. Claude Code is not covered: it is the runtime the seats run in.

The one rule that saved the most time: **when a runtime's behaviour is not
obvious, ask the runtime itself, with permissions granted, before reading its
docs.** Both CLIs know their own customization systems better than their
changelogs do. Give them permission to run commands or fetch pages first, or
the headless run auto-denies the tool call and returns nothing (Antigravity) or
gives a non-answer (Codex declines to guess its own model ids).

## Codex (`codex`, OpenAI)

**Install and update.** Installed through npm, not brew: `/opt/homebrew/bin/codex`
is a symlink into `node_modules/@openai/codex`. `brew upgrade codex` fails
("Cask 'codex' is not installed") even though a brew formula exists. Use
`codex update` (it runs `npm install -g @openai/codex`). Check with
`codex --version`. No live `codex exec` should be running when you update; the
binary is shared by every seat on the machine.

**Model ids.** The CLI does not list models on the command line. The list it
knows is cached at `~/.codex/models_cache.json`, refreshed on each run; read the
`slug` fields. A new model appears there only after the CLI is new enough:
`gpt-6-astra` was absent at 0.149.1 and present at 0.153.4 on the same account
and day. A model id the CLI does not know hangs the run rather than failing
fast (measured: eight minutes with no output before it was killed). The model
cannot tell you its own id ("not exposed to me") and will not guess a new one.

**Running non-interactively.** `codex exec` with the prompt as the last
positional argument, or on stdin. Flags the cells use:
`--sandbox read-only` (or `workspace-write` when it must write the report),
`--disable memories`, `-C <repo>`, `-m <model>`, `-c model_reasoning_effort=<low|medium|high|xhigh|max>`.
Outside a trusted git checkout it refuses with "Not inside a trusted directory";
add `--skip-git-repo-check` for scratch directories. Its stdout carries a
bracketed trace and a `tokens used` line before and after the answer; the
repo's `scripts/cold-read-codex-cell.py` already strips these, and a direct
runner must (the terminology runner keeps everything after the last
`] codex` banner line).

**Effort.** `max` is accepted by every 5.6 model and by astra; the cell stamp
records what was asked. Effort is per run, in the `-c` override, not in the id.

**Project rules.** Codex injects the repository's `AGENTS.md`. Ours is a pointer
("read CLAUDE.md and follow it"), user-ruled, and codex follows it by reading
the file when it may read files — measured with a canary on 2026-08-22 and
again today. A run told not to read files sees only the pointer and says so.
That is the intended behaviour for a cold-read cell, which is meant to be
context-free.

**Time and quota.** A max-effort run on a 1,500–2,300-word document takes
13–20 minutes. Sol-max is the slowest cell in the campaign (mean 1,339 s).
Codex has never hit an account limit in this campaign; Claude hit it three
times in one day, so when both are queued, the Codex leg is the one that
finishes.

## Gemini via Antigravity (`agy`, Google)

**What it is.** There is no `gemini` CLI on this machine. Gemini runs through
the Antigravity CLI, `agy` (`~/.local/bin/agy`), which is the agent behind the
Antigravity IDE. Its config lives under `~/.gemini/antigravity/`. `agy update`
checks and updates; `agy --version` reports it. The user's Google account
upgrade on 2026-09-04 removed the quota that stopped every Gemini cell in the
08-29 trial ("Individual quota reached ... Resets in 95h").

**Model ids carry the effort.** `agy models` lists them live:
`gemini-3.8-flash-high`, `-medium`, `-low`, the same for 3.7 and 3.6, and
`gemini-3.1-pro-high/low`. Pass the whole id to `--model`; `--effort` exists too
and should agree with the suffix. The list also offers Claude and GPT-OSS ids
through Antigravity, which we do not use.

**Running non-interactively — the three things that bite.**

1. **The prompt is the VALUE of `--print`.** `agy --print --model X "prompt"`
   silently takes `--model` as the prompt and ignores yours, with an error
   only at the end. Put `--model`, `--effort`, `--add-dir` first and `--print`
   last with the prompt as its argument, or use `--print='...'`.
2. **Pass the repository with `--add-dir <repo>`**, or nothing from the
   repository loads: no `AGENTS.md`, no `GEMINI.md`, no `.agents/rules/`.
   Measured both ways with a canary from the repo root; only `--add-dir`
   made the AGENTS.md pointer appear in context. Once it does, the model
   follows the pointer into CLAUDE.md the same way Codex does, and quoted the
   naming rule verbatim.
3. **Headless runs auto-deny every tool permission.** A run that needs to
   write its report, read a URL, or run a command returns "no output produced
   — a tool required the X permission that headless mode cannot prompt for".
   Add `--dangerously-skip-permissions` (or an allow-rule in
   `~/.gemini/settings.json`). With it, the cell writes its own report file
   at the path the prompt names, exactly as the Claude cell does.

Also: `--print-timeout` defaults to 5 minutes; a high-effort read of a
1,500-word document takes 3–3.5 minutes, so set 20–30m for anything larger.
`--output-format text` gives the answer alone. The report the model writes
carries no provenance stamp; the runner prepends one so the campaign's
manifest and scorer treat the record like any other cell's.

**Where its docs are.** The CLI ships its own customization guide as a skill:
`~/.gemini/antigravity/builtin/skills/agy-customizations/SKILL.md` and
`docs/rules.md` beside it. Rules load from `GEMINI.md` or `AGENTS.md` in any
directory from the working directory up to the repository root, and from
`.agents/rules/*.md`; standalone files have no frontmatter and are always on.
None of that fires without `--add-dir` (item 2). Asking agy about itself
works, but only with permissions granted; without them it tries to fetch its
docs, is denied, and returns nothing — and even with them it may time out
running experiments on itself, so read the shipped guide first.

**Speed.** This is the reason to have it. `gemini-3.8-flash-low` reads a
700–1,500-word document in 21–31 seconds and reaches the same recall as
`gpt-5.6-terra` at low effort in a quarter of the time, at better precision
on a design. `gemini-3.8-flash-high` takes about 200 seconds. Neither found a
defect no other cell found, so Gemini is a speed cell for interactive use,
not a seat in the full set.

## Running either as a cold-read cell without a launcher

`scripts/cold-read-claude-cell.py` and `scripts/cold-read-codex-cell.py` take
their prompt only from `.claude/skills/cold-read/prompts/<cell>.md`; there is
no `--prompt-file` flag (as of 2026-09-04; MD-skills has it queued) and no
`agy` launcher at all. For a one-off prompt or runtime, the pattern that works
is a direct invocation that composes the prompt with the same `{TARGET_PATH}` /
`{REPORT_PATH}` substitution and writes the same provenance stamp
(`<!-- provenance: runtime= model= effort= cell= duration_s= target= -->`), so
the existing placement, adjudication and scoring tools take the record
unchanged. Two working examples are in this record's `tools/`:
`run-terminology-cells-direct.py` (claude + codex) and
`run-astra-and-gemini-cells.py` (codex via the launcher, agy direct).

## Things that went wrong once and will again

- A shared scratchpad directory with a generic script name (`build_clusters.py`)
  let one agent run another's script. Name scratch files with the target and
  the seat.
- Two runners writing one `manifest.json` drop each other's entries; run one at
  a time and regenerate the manifest from the records afterwards.
- The Claude account limit resets on a clock; a rerun pass should sleep until
  the reset, then skip records that exist.
- `/login` in a seat's terminal kills that seat's in-flight subagents with an
  auth error, and the background `claude -p` cells with them; the OAuth token
  also expired overnight once and hung a cell for six hours. Anything long
  should be relaunchable with skip-existing.
