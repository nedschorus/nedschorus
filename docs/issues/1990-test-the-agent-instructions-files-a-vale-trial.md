---
issue: "[Test the agent-instructions files: a Vale trial for the style-guide word checker, and md-drift-lint findings on changed lines block the merge](https://github.com/nedschorus/nedschorus/issues/1990)"
---

# Test the agent-instructions files: a Vale trial for the style-guide word checker, and md-drift-lint findings on changed lines block the merge

## What is wanted

Agents in this project act on agent-instructions files: `CLAUDE.md`, the skill files under `.claude/skills/`, the prompt files programs load, the seat-briefs, and the glossaries and the style guide those files point to. A wrong or unclear sentence in one of them changes what an agent does, the way a defect in code changes what a program does. Today the project tests the project's Markdown files in three ways: about ten test suites that each test one mechanical rule (two copies of a passage match, the glossary stays in alphabetical order, a design's state names match the code's tables); `scripts/style-guide-word-checker-nbd.py`, which `scripts/style-guide-word-checker-markdown-edit-hook-nbd.py` runs after an agent's Edit or Write of a Markdown file git tracks, and which flags the words the style guide lists; and `scripts/md-drift-lint.py`, which merge-lane-2 runs on the Markdown a pull request changes. Hooks catch some broken rules after the fact, and the cold-read reviewers are scored on fixed test cases under `cold-read-reviewer-test-cases/`.

This GHI asks for two parts:

1. **A Vale trial.** Find out whether the prose linter Vale, configured from the style guide by a program, can replace the Markdown parser in `scripts/style-guide-word-checker-nbd.py`.
2. **`md-drift-lint` findings on changed lines block the merge.** Today they never do.

Part 1 is a trial whose report the user rules on, followed by one pull request only if the user adopts Vale; part 2 is one pull request. The two parts start at once, as the user ruled on 2026-10-24. Part 2 starts by surveying how this project and standard linters already accept a finding that is not a mistake, either with a marker in the line itself, such as Python's `# noqa` or the HTML comments markdownlint and Vale read, or with a list a program reads, as md-drift-lint reads `.gitignore`, and brings the user the survey's pick before building it.

## Why

On 2026-10-14 the user asked whether the project should test its agent-instructions files the way it tests code, and asked Codex and Claude to research how others do it. Both reports are in the log-store: `nedlern@ned-box:/home/nedlern/nedschorus-logs/analysis/prose-and-markdown-that-drives-agents-testing-practices-research-2026-10-14/codex-report.md`, and `claude-report.md` in the same directory. They agree on these points:

- Neither report found a public project that tests the meaning of every sentence in an agent-instructions file. Meaning stays with review: in this project the /cold-read, the /sanity-check and the user.
- Docs-as-code teams lint wording mechanically in CI. GitLab runs Vale and markdownlint on every merge request that changes Markdown, plus its own scripts for what those cannot test ([GitLab documentation testing](https://docs.gitlab.com/development/documentation/testing/)); Datadog keeps its style rules in Vale as the one source for writers' editors and for CI ([Datadog, 2024-02-14](https://www.datadoghq.com/blog/engineering/how-we-use-vale-to-improve-our-documentation-editing-process/)).

The reports differ on Vale. Codex recommends a narrow Vale configuration; Claude recommends none, because a second word list would drift from the style guide. The user answered that a program can generate Vale's configuration from the style guide each time Vale is called, so the two word lists cannot drift; part 1 tests whether Vale earns its place.

## Part 1: a Vale trial

`scripts/style-guide-word-checker-nbd.py` reads the "Words to avoid" table of `docs/nedschorus-wiki/nedschorus-style-guide.md` each time it is called, so the page agents read and the list it flags cannot differ. Its weak point is its Markdown parser. GHI [The style-guide-word-checker misses prose and flags code in six Markdown shapes](https://github.com/nedschorus/nedschorus/issues/1043) reproduces six cases; four of them (its items 1, 2, 5 and 6) are the parser reading code as prose or prose as code. Items 3 and 4 are the hook's: which text an Edit or a Write hands to the checker. The GHI is open with no fix in progress.

Vale ([docs](https://docs.vale.sh/)) ignores code blocks and code spans in Markdown by default. Its rule types include existence (flag a word), substitution (flag a word and name its replacement) and consistency (one spelling throughout a file). Vale is not installed on ned-box today (`which vale` printed nothing, 2026-10-26). The trial downloads Vale's latest release binary to `~/.cache/vale-trial/` on ned-box, records its version in the report, and deletes the folder when it ends, so nothing is installed on either machine until the user adopts Vale.

The trial:

1. A program reads the style guide's table and writes a Vale configuration from it. Each row becomes a rule that flags the row's "Forms flagged" and not its "Forms not flagged": a substitution rule when "Write instead" names one replacement, an existence rule otherwise. Rows that apply to messages only, the pronoun rows and `or`, are skipped, because the style guide says no program checks them. Example: the row for `box` becomes a substitution rule that flags `box`, suggests `ned-box`, and does not flag `ned-box`.
2. Vale, with that configuration, and the checker both read GHI 1043's four parser cases and a sample of 20 Markdown files from main chosen before either runs. The agent running the trial labels each word on which the two disagree as a true or a false finding.
3. The trial's report goes to the log-store and recommends Vale if Vale gets the four cases right and, on the sample's words where the two disagree, has no more false findings than the checker and misses no more true ones; the user rules on the report. Only if the user adopts Vale does a pull request follow, which makes the checker call Vale to find the words in a Markdown file; the checker keeps its hook and the style guide as its source. If the user drops Vale, part 1 ends with the report, and GHI 1043 fixes the checker's parser as its own work. GHI 1043 fixes the hook's two cases either way.

If Vale is adopted, it must be installed on the Mac and on ned-box. When Vale is missing or fails, the hook reports it as it reports its own failures today, and does not refuse the edit. The checker and its hook carry the -nbd suffix, which marks them nice-but-dirty code; a new program, such as the one that writes Vale's configuration, that imports code from either of them carries the suffix too, or does not depend on either.

Left to the builder: what the program does with a malformed row of the table, and how the trial counts a false finding that Vale and the checker both report, since step 2 labels only the words on which they disagree. Measured by the trial rather than configured: whether Vale skips quoted text and paths.

## Part 2: `md-drift-lint` findings on changed lines block the merge

`scripts/md-drift-lint.py` reports, in Markdown, every finding its docstring lists, among them a cited repository path that does not exist, a link target that does not resolve, a date that is not a real date, and a command naming a project script with a flag that script does not have. merge-lane-2 runs it on every Markdown file a pull request adds or changes and reports only findings on the lines the pull request's diff adds or changes. Today, by a user-ruling of 2026-09-17, recorded in merge-lane-2's seat-brief, `~/agents/merge-lane-2/CLAUDE.local.md` on ned-box, "A lint finding never blocks a merge."

Example: a pull request adds to a skill a sentence telling agents to run `scripts/run-all-test-suites.py` with a flag `--changed-only`, written as a command in backticks. The flag does not exist; the lint reports it; the review comment says so; and the pull request merges anyway, so an agent that follows that step runs a command that fails.

The user decided on 2026-10-17, in item 11 of the approval-walk whose minutes are `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/nedschorus-which-changes-are-pre-approved-changes-draft-2026-10-15-minutes.md`, that a finding on a line the pull request's diff adds or changes blocks the merge as a code finding does, even when the mistake is older than the pull request, and the author fixes it in a fix-round. This holds for every kind of finding, including the finding that a GHI an architecture overview lists under "Planned work" is closed or has a different title on GitHub. When the lint does not finish, as when it exits 3 because GitHub could not be queried, the merge waits until it finishes, as it does for a test suite that cannot run. Findings on other lines are not reported, as today; GHI [Sort the 60 standing md-drift-lint findings into forward references and stale citations, then fix the stale ones](https://github.com/nedschorus/nedschorus/issues/572) covers them.

That walk, not this GHI, changes the user-ruling of 2026-09-17, the two rules in merge-lane-2's seat-brief that a problem main already has never blocks, and the review-scope rule. By its item 10, the review-scope bullet of `CLAUDE.md` is due to become a pointer to `docs/agents/pr-reviewer-instructions.md`, and `scripts/pr-reviewer-instructions-copies-test.py` is due to be deleted.

Some findings are not mistakes: a forward reference, a path to a program the project has decided to build but has not built; a wrong command quoted on purpose as an example; and a finding the lint reports in error, such as those GHI 572 lists. Part 2's pull request builds only a way for the lint to accept these; blocking starts once it merges (item 1 of Deferred-decisions).

Left to the builder: what the author of a pull request does when a GHI named on a "Planned work" line the pull request changes has been renamed on GitHub while still open.

## Deferred-decisions

1. How a document marks a finding that is not a mistake so that the lint accepts it. Part 2 first surveys how the project and standard linters already do this, and brings its pick to the user; GHI [Sort the 60 standing md-drift-lint findings into forward references and stale citations, then fix the stale ones](https://github.com/nedschorus/nedschorus/issues/572) asks the same question for forward references.

## Related ground

- GHI [A project style guide: words to avoid, a mechanical checker, and a check on unbacked promises](https://github.com/nedschorus/nedschorus/issues/14) built the word checker part 1 measures Vale against.
- Search receipt: `scripts/ghi-info-ask.py`, 2026-10-14, asked whether a GHI covers a prose linter such as Vale, behaviour evals of `CLAUDE.md` or skills, making md-drift-lint block merges, or shortening `CLAUDE.md` by moving rules into hooks. ghi-info answered that no GHI covers the cluster, that "Vale" appears in no GHI, that no GHI proposes testing whether agents follow `CLAUDE.md` or a skill, and named GHI 14, 572, 1043, 1127 and 1349 as the nearest ground. The receipt is renewed at filing, when `scripts/ghi-issue-write.py create` asks ghi-info again.
