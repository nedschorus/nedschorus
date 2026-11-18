---
issue: "[A program that rewrites each Markdown citation of a renamed file to the file's new path, taking the new path from git's rename history](https://github.com/nedschorus/nedschorus/issues/3054)"
---

# A program that rewrites each Markdown citation of a renamed file to the file's new path, taking the new path from git's rename history

## Why

When a pull request renames a file, every Markdown file that cites the old path must be updated in the same pull request. Two programs on main find such citations and only report them: `scripts/md-drift-lint.py` reports repository paths and link targets that do not exist on disk, and `scripts/dangling-path-citation-check.py` reports citations of the paths a change deleted or renamed, taking the old names of renamed files from `git diff --name-status` against the merge base. Neither program changes a file, so the author of the rename updates each citation by hand. For a renamed file, git already knows the one correct replacement: the new path its rename detection records. A program could apply that replacement itself.

The user approved filing this as its own GHI on 2026-10-05, with "y" to item 7 of the approval-walk cold-read-and-ask-the-user-rules-2026-10-05, which proposed: "`scripts/md-drift-lint.py` already finds dead paths and broken links, and only reports them. A companion could apply the one replacement git's rename history gives." The walk-document is `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/cold-read-and-ask-the-user-rules-2026-10-05.md` (item 7, lines 75-78), and its walk-minutes are `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/cold-read-and-ask-the-user-rules-2026-10-05-minutes.md`. That walk-document item came from the proposed rename of the style guide in GHI [A project style guide: words to avoid, a mechanical checker, and a check on unbacked promises](https://github.com/nedschorus/nedschorus/issues/14); the rename is one case, and the program serves every rename.

## What to build

A program, run by the author of a change on its committed commits before pushing, that:

1. reads the change's renames from git as `scripts/dangling-path-citation-check.py` does, with `git diff --name-status` between the merge base and `HEAD`, keeping only the rows git marks as renames. The code that reads those rows moves into a shared `-common.py` module that both programs import, rather than being copied, because a file name with hyphens cannot be imported with a plain `import` statement;
2. finds each citation of an old path in the repository's Markdown files: a path in backticks, or a link target, with or without a line-number suffix such as `:120`;
3. rewrites each such citation to the new path, in the form the citation had: a path from the repository root stays one, and a relative link target is recomputed from the citing file's directory, so a link still resolves after the rename moves the file to another directory; and prints each file and line it changed;
4. leaves alone every other citation that `scripts/dangling-path-citation-check.py` reports: a citation of a deleted file, of a file git did not detect as renamed (git reports a rename below its similarity threshold as a delete and an add), of a directory, a path that is not in backticks, and a citation in a file that is not Markdown. git gives no single replacement for these, so the author fixes them by hand, as today.

A citation with a line number keeps its line number, and the program prints it as one to check, because the cited line may have moved in the rename.

Today the reminder hook `nc-systems/general-tools/claude-code-bash-git-push-of-markdown-change-citation-checks-reminder-hook.py` names `scripts/dangling-path-citation-check.py` when an agent pushes a Markdown change, and the test suite `scripts/branch-leaves-no-citations-of-removed-paths-test.py` fails on a citation of a removed path. Both name the new program too, so that the author, when told about a citation of a renamed path, is given the one command that rewrites it.

## Supporting documents

- Search receipt: `scripts/ghi-guide-agent-ask.py --include-closed`, 2026-11-10, asked for a GHI, open or closed, for a check that applies git's rename detection so that a renamed file's citations in Markdown are found and updated; it found none. The nearest are GHI [Reference-integrity checker: links resolve and cited revision-paths exist — pure-code review check (and the home for what-else-can-code-check)](https://github.com/nedschorus/nedschorus/issues/42), which checks that links resolve and reports, and GHI [Nothing reports Markdown that still cites a constant or function by a name a pull request renamed or removed](https://github.com/nedschorus/nedschorus/issues/2841), which covers renamed code names, not file paths.

## Next action

Read `scripts/dangling-path-citation-check.py` and `scripts/md-drift-lint.py`, decide whether the rewrite is a new mode of `scripts/dangling-path-citation-check.py` or a program of its own, and build it, with the shared `-common.py` module, its test and the two changes to the reminder hook and the test suite, in one pull request.

## Trigger to close

The program is on main with its test, and the reminder hook and the test suite named above name it. The test renames a file in a test fixture repository that cites it by a path from the repository root and by a relative link from another directory, runs the program once, then runs `scripts/dangling-path-citation-check.py --only-citations-of-removed-paths`, and passes when that exits 0.

## Deferred-decisions

- Whether the program also rewrites a line-number suffix when `git diff -M` shows the cited line unchanged at a new line, to be settled when the program is built.
