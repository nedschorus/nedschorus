# Notes on using the Codex and Gemini (Antigravity) agents from an agent-seat

This page tells an agent-seat how to run Codex and Gemini, and what to expect from them. Facts about an installed program say which machine and date they were checked on, because the programs update often. Measurements the cold-read-research agent-seat made from 2026-09-03 to 2026-09-07 are in their own section near the end, and the campaign's data is in the record `nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/2026-09-03-cold-read-tier-roster-campaign/`. Claude Code, the program the agent-seats themselves run in, is covered elsewhere; it appears here only where it was measured beside the other two or where it broke their runs.

## Run them through the project's programs

- To give Codex a task, run `scripts/run-codex-task-from-brief.py -C <checkout> --brief <file> -o <report>`. Never type `codex exec` by hand: without that program, Codex waits forever on stdin, nothing stops a run that hangs, and nothing keeps Codex out of credential files. The program's own options cover what a task needs: `--sandbox`, which takes `read-only` (the default) or `workspace-write` to let Codex edit, `-m <model>`, `--effort <effort>`, `--outside-git-checkout` for a folder that is not a git checkout, `--network` and `--web-search` to let Codex reach the web, and `--deadline-minutes` (default 60). Run it with `--help` for the rest.
- To run one reviewer on a document, use the cold-read-cell launchers: `nc-systems/cold-read/cold-read-claude-cell.py`, `nc-systems/cold-read/cold-read-codex-cell.py` and `nc-systems/cold-read/cold-read-agy-cell.py`. Each takes `--cell`, which names the reviewer prompt under `.claude/skills/cold-read/prompts/` (`restate`, `defect-hunt`, `fast-clarify` or `terminology`), `--tier`, `--target` and `--report`. The Claude and Codex launchers take `--tier deep` or `second-strongest-model`, and the Gemini launcher only `--tier fast`. To use a prompt of your own, add `--prompt-file <path>`; `--cell` is then a label of your choosing, lowercase letters and digits joined by single hyphens, recorded in the report's provenance stamp.
- Never run `agy` outside the Gemini launcher, `nc-systems/cold-read/cold-read-agy-cell.py`; the project has no program for giving Gemini other tasks. With the permissions a headless run needs, `agy` reads credential files, and its own `--sandbox` switch does not stop it; the launcher runs it inside `bwrap` on Linux or `sandbox-exec` on macOS, and refuses to run without one.

## Codex (`codex`, OpenAI)

**Install and update.** Codex is installed through npm, not Homebrew: on ned-box `/usr/local/bin/codex` is a symlink into `/usr/local/lib/node_modules/@openai/codex`, and on the Mac `/opt/homebrew/bin/codex` is a symlink into npm's `node_modules/@openai/codex`, so `brew upgrade codex` fails. Update with `codex update`, which runs `npm install -g @openai/codex`, and check with `codex --version` (codex-cli 0.159.3 on ned-box on 2026-10-17). Every agent-seat on a machine shares the one binary, so before you update, check with `pgrep -af codex` that no Codex run is in progress; if one is, wait for it to finish. Running Codex tasks side by side is fine; only the update must wait.

**Model ids.** The CLI has no command that lists models. It caches the list it knows in `~/.codex/models_cache.json`, refreshed on each run; the ids are the `slug` fields. A model appears there only once the CLI is new enough for it: the Codex launcher's `gpt-6.1-sol` needs codex-cli 0.159.1 or later. A model id the CLI does not know makes the run hang instead of failing (measured: eight minutes with no output, then killed), so take the id from the cache; `scripts/run-codex-task-from-brief.py` stops such a run at its deadline. The model cannot tell you its own id.

**Effort.** Effort is set per run, with `--effort`, not in the model id.

**At capacity.** When a run on `gpt-6-astra` prints "Selected model is at capacity. Please try a different model.", which means OpenAI has no room on that model at that moment rather than that the user's plan is used up, run the task again with `-m gpt-6.1-sol --effort xhigh`.

**Project rules.** Codex reads the repository's `AGENTS.md`, which tells it to read `CLAUDE.md` and follow it. Measured with a canary on 2026-08-22 and 2026-09-04: Codex reads `CLAUDE.md` when it may read files.

## Gemini via Antigravity (`agy`, Google)

**What it is.** Gemini runs through the Antigravity CLI, `agy`, the agent behind the Antigravity IDE; there is no `gemini` command. On ned-box `agy` is `~/.local/bin/agy` and its configuration is under `~/.gemini/antigravity-cli/` (version 1.4.0 on 2026-10-17). `agy update` updates it and `agy --version` reports it.

**Model ids carry the effort.** `agy models` lists them: `gemini-3.8-flash-high`, `gemini-3.8-flash-medium`, `gemini-3.8-flash-low`, `gemini-4-argon-high`, `gemini-4-argon-medium` and `gemini-4-argon-low` (ned-box, 2026-10-17). The cold-read-fast-read runs on `gemini-3.8-flash-medium`.

**What a new runner must handle.** The launcher handles all of these; they matter only to someone changing it.

1. The prompt is the value of `--print`. In `agy --print --model X "prompt"`, agy takes `--model` as the prompt and ignores yours. Put every other option first and `--print` last, with the prompt as its value.
2. Pass the repository with `--add-dir <repo>`, or nothing from the repository loads, `AGENTS.md` included.
3. A headless run denies every tool permission unless it has `--dangerously-skip-permissions`; a run that needed one ends with "no output produced — a tool required the X permission that headless mode cannot prompt for". That flag is why agy must run inside the operating system's sandbox.
4. Gemini sometimes writes the whole review as its answer instead of into the report file. The launcher then takes the answer as the report when it is at least 120 words; a shorter answer with no report file counts as a failed run.
5. `--print-timeout` defaults to `0s`, no limit; the launcher sets `30m`, so a run that hangs is stopped.

**Its own documentation.** On ned-box, agy's customization guide is `~/.gemini/antigravity-cli/builtin/skills/agy-customizations/SKILL.md`, with the rule-loading details in `~/.gemini/antigravity-cli/builtin/skills/agy-customizations/docs/rules.md`. Read it before asking agy about itself: asked about itself, agy may spend its whole run on experiments and time out.

## Measured from 2026-09-03 to 2026-09-07

These are the cold-read-research agent-seat's results, on the models and CLI versions of those days; the campaign record above holds the data for all but the result of 2026-09-07.

- A Codex run at `max` effort on a document of 1,500 to 2,300 words took 13 to 32 minutes (`gpt-6-astra` and `gpt-5.6-sol`).
- Codex hit no account limit in the campaign; Claude hit its limit three times in one day.
- `gemini-3.8-flash-low` read a 700 to 1,500-word skill in 21 to 31 seconds, found as many of the known defects as `gpt-5.6-terra` at low effort in a quarter of the time, and found no defect that no other reviewer found. Measured on 2026-09-07, as `nc-systems/cold-read/cold-read-agy-cell.py` records: on one defect list, `gemini-3.8-flash-medium` found 42% and low 19%, which is why the cold-read-fast-read runs on medium.

## Things that went wrong once and will again

- In a scratch directory several agents shared, one agent ran another's script because both used a generic name, `build_clusters.py`. Put the name of the document you are working on and your agent-seat's name in a scratch file's name.
- Give a shared file one writer. Each run writes its own record file, and one program builds any summary from the records; for a log, use one writer process that the others send to, as Python's `logging` documents.
- `/login` in an agent-seat's terminal kills that agent-seat's running subagents and its background `claude -p` runs with an authentication error. A Claude login once expired overnight and left a run hanging for six hours. Give a long batch of runs a deadline per run, and make it able to start again without redoing the runs whose reports are complete.
