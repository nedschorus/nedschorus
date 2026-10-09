---
issue: "[Agents reuse what the project has already solved: shared helpers, one page of reusable components, and a reuse check before, during and after the build](https://github.com/nedschorus/nedschorus/issues/1123)"
---

# Agents reuse what the project has already solved: shared helpers, one page of reusable components, and a reuse check before, during and after the build

Agents keep re-solving problems this project has already solved, because they do not know the solution exists or do not look for it. This GHI makes the solutions findable and checks for re-implementation at three moments: when an agent is briefed, when it writes a file, and when its pull request is reviewed.

## Why

- PR [Remind the agent to keep Markdown paragraphs on one line after an Edit or Write](https://github.com/nedschorus/nedschorus/pull/1106) took nine review rounds. For five of them the hook recognised Markdown with hand-written regular expressions, and each fix broke a neighbouring case. The standard parser, markdown-it-py, was installed on ned-box throughout; the rounds stopped once the hook used it.
- PR [Stop hook: tell the agent to fast-read documents it linked that have no cold-read-fast-read since their last change](https://github.com/nedschorus/nedschorus/pull/1109) copied two helpers that already existed, and its reviewers asked for the shared ones.
- Both trawls below found helpers that exist in three or four copies, where only some copies carry later fixes. One example: the list of environment variables that redirect git exists in four copies, and two of them strip only two of the six variables.
- Published work finds the same pattern. Agents "frequently disregard code reuse opportunities", and reviewers judged agents' pull requests more favourably than humans' ([More Code, Less Reuse, MSR 2026](https://arxiv.org/abs/2601.21276)). General advice in an instructions file barely changes what agents do, while a specific instruction such as "use X for Y" is followed ([ETH Zurich, 2026](https://arxiv.org/abs/2602.11988)).

The user asked for this on 2026-10-09 in agent-session fleet-restart-at-login: "we put to gether a wiki page with all these things, then have an agent check PRs to see if any of them should have been used", and asked for the whole project to be trawled for "components that can be and should be (at appropriate times) be reused", techniques included: test coverage tools, working with Codex and Gemini, a simple database instead of tags, and the reincarnation and daily cycles.

## What exists today

- **Two trawls of main**, run 2026-10-09 from one brief, one by Claude and one by Codex, each ranking candidates with paths, the moment to use each, evidence of past re-implementation, and duplicated code: `nedlern@ned-box:/home/nedlern/nedschorus-logs/analysis/reusable-project-components-trawl-2026-10-09/` (`prompt.md`, `claude-report.md`, `codex-report.md`). Both put first: keeping leaked git variables out of git calls, the Markdown parser, the transcript reader, the checkout helpers of the Markdown-edit hooks, the shared runner for model calls, the shell-command tokenizer, cold-read record naming and shipping, the mutation-testing script, and atomic writes of state files.
- **A research note on established practice**, summarised under Why and in the parts below: "paved road" catalogues for discovery, lint rules that ban a hand-rolled pattern and name the replacement (Semgrep, Ruff's banned-api rule), and duplicate-code detectors, which catch copy-paste but not a re-implementation written differently.
- **The mechanism to copy.** `scripts/new-shared-names-reminder-hook.py` runs after each write, lists the shared names the branch newly adds, reports each name once per branch, and tells the agent to send them to `.claude/agents/new-name-propose-and-check-fresh-agent.md`, which checks them against a wiki page. The reuse hook in step 4 works the same way: it runs after each write and reports each match once per branch, with a different trigger and a different page.
- **Neighbours, which this GHI does not repeat.** GHI [Move mechanical agent chores into programs and hooks](https://github.com/nedschorus/nedschorus/issues/1036) turns agent chores into programs; GHI [Daily maintenance in one daily step, starting with a daily check of every wiki page](https://github.com/nedschorus/nedschorus/issues/1058) and GHI [Monthly cold-read-full-run of every important markdown file that has changed since its last one or never had one](https://github.com/nedschorus/nedschorus/issues/1064) run maintenance cycles; GHI [Three mechanical checks agents keep forgetting to run: file-overlap before work starts, exit status through a pipe, and the settled-decision list](https://github.com/nedschorus/nedschorus/issues/216) checks overlapping work, not reuse. Search receipt: `scripts/ghi-info-ask.py` on 2026-10-09, asked for an open GHI on a catalogue of reusable components or a check that pull requests reuse existing helpers, found none.

## What to build, in order

1. **Extract the duplicates first.** Where a helper exists in several copies, make one shared module and move every caller to it, taking the most complete copy's behaviour, with tests that cover each caller's use, so that a caller relying on a narrower copy shows up in the tests rather than on main. Start with the trawls' duplicates list. A page that points at three copies keeps the problem.
2. **One short wiki page of reusable components.** One row per problem, organised by what the agent is about to do ("read Markdown", "read an agent's transcript", "run git from a hook", "call Codex or Gemini", "keep state between runs", "schedule work daily"): the component to use, one example call, and the mistake it prevents. Techniques go on it as well as code: the reincarnation cycle, the daily step, a program-owned record instead of a marker in prose, the test runner's selection, mutation testing. The page stays short, linking to each system's own documentation for detail, so that a reviewer reads it whole.
3. **Before the build: the builder's brief.** Every prompt an agent writes to commission code from a subagent points to the page, as a specific instruction: before writing code that does one of these things, use the listed component.
4. **During the build: a hook.** Modelled on the new-shared-names reminder: after a write, when a changed file does something a page row covers, such as a new script that imports `re` and contains Markdown fence literals, or reads a JSONL transcript without the shared reader, the hook names the row and the component. Narrow mechanical patterns only; each comes from a re-implementation that was caught.
5. **After the build: a reviewer.** merge-lane-2 commissions one more cheap reviewer per pull request, given the page and the diff, with one question: does this change solve a listed problem without the listed component? It must name the existing component and say whether its contract fits. This is the backstop for what the brief and the hook miss, and the only check for techniques, such as the daily step or a program-owned record, which no pattern can detect.
6. **The loop.** Each re-implementation the reviewer catches adds a row to the page, and, where it can be matched mechanically, a pattern to the hook or a test that fails when a helper is defined twice. The page grows from real misses rather than from guesses.
7. **The tools are installed on both machines.** A requirements file, which does not exist today, lists every third-party package a component needs, and a test imports each one, so the nightly full run on each machine fails when one is missing.

## What is not decided

1. The page's location and name, and where shared modules live, given GHI [One documentation tree in place of the wiki and the rest of docs, with Obsidian opened on it](https://github.com/nedschorus/nedschorus/issues/1066).
2. The page's size cap, and who adds and removes rows.
3. Which rows get a mechanical hook pattern, and whether the hook fires per write or once per branch, as the new-shared-names reminder does.
4. The reviewer's cost per pull request; whether it runs on every pull request or only on ones that add code; and whether its findings block the merge, as code findings do, or are advice.
5. Where the instruction for builder briefs lives, so that every agent that commissions code meets it.
6. The requirements file's path and format.
7. Which duplicates to extract first, and whether each extraction is its own pull request.
8. How to measure the result: missed reuse caught, false alarms, review rounds saved.

## Next action

Put the order above and the open questions to the user. Once he has ruled on question 7, start step 1 with the top duplicates both trawls name.
