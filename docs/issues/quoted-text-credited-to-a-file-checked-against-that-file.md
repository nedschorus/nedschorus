# Check that words quoted from a file appear in that file

## What goes wrong

Agents quote files to the user: a walk-document shows a design's sentence and asks the user to approve it. Nothing checks that the quoted words are the file's words. On 2026-10-21 the walk-document of the approval-walk on the cold-read design rewrite misquoted twice. The advisor, a stronger reviewer model the agent calls before presenting an item, caught both before the user saw them; no program would have.

1. Item 4. The walk-document's draft, `/home/nedlern/agents/cold-read-improvement-cold-read-design-full-run/docs/walk/cold-read-design-2026-10-15-draft.md` line 41, still reads: Proposed: "A change to a prompt is tested before it lands, on two documents: …". The file it quoted, the design rewrite `/home/nedlern/agents/cold-read-improvement-cold-read-design-full-run/docs/drafts/cold-read-design-rewrite-after-cold-read-full-run-2026-10-16.md`, read at line 31, at commit fe0042996^ on branch `cold-read-design-cold-read-full-run-rewrite-topic-branch`: "A change to a prompt is tested before it is merged, on two documents: …". The walk-minutes, `docs/walk/cold-read-design-2026-10-15-minutes.md` line 17 in the same worktree, record the fix: "walk-document now says "is merged" as the rewrite does".
2. Item 6. The first draft quoted the pin comment "user-picked 2026-08-03; xhigh "OK for codex" same date" as one the cold-read reviewers' model pins once carried. That comment was in `scripts/code-review-codex-cell.py`, the PR reviewer's Codex wrapper, until commit 80454332d. The cold-read Codex reviewer, now `nc-systems/cold-read/cold-read-codex-cell.py`, carried a different comment, which commit 096fb43c2 dropped. The same walk-minutes, line 24, record the corrected attribution.

The harm: the user approves quoted words, so a misquote is approved text that is not the text that ships. merge-lane-2 then checks the shipped words against the walk-minutes by hand, as it did for PR [PR reviewer instructions and CLAUDE.md: the defect-fix rule rewritten as the reviewer's numbered steps — a case fix or workaround that removing the root cause would make useless blocks, unless a #follow_up link or an outage settles it](https://github.com/nedschorus/nedschorus/pull/1636) and PR [CLAUDE.md: five words the style guide lists to avoid take its replacements (live, harness, gate, head twice)](https://github.com/nedschorus/nedschorus/pull/1642) on 2026-10-22.

## What already exists

Three programs find a citation by its written form alone, without the agent saying it wrote one:

- `scripts/bare-number-citation-in-markdown-and-agent-reply-warning-hook.py`: a pull request or GitHub issue cited by a bare number, or linked under text that is not its title. It runs on Edit and Write of a Markdown file, skipping files git ignores, and, at UserPromptSubmit, on the agent's previous reply. It warns; it never blocks.
- `scripts/dangling-path-citation-check.py`: a cited path that does not exist.
- `scripts/stale-code-citation-check.py`: a `path:line` citation whose code file changed after the document's design-as-of date. It ties a line number to the nearest path before it on the same line.

The last two run when an agent pushes a change to a Markdown file, reminded by `nc-systems/general-tools/claude-code-bash-git-push-of-markdown-change-citation-checks-reminder-hook.py`. None checks quoted words. `scripts/citation-and-history-marker-tests-date-pattern-common.py`, despite its name, holds only the date patterns that keep dates out of agent-facing text, so it has nothing to reuse here.

## The rule

Anthropic's Citations feature returns each quote with its source: the quoted text, the document, and the place in it. The project borrows that written form, not the API: **words quoted from a file name the file, as a path or `path:line`, in the same sentence.**

## What the check does

A new program, proposed name `scripts/quoted-text-citation-check.py`, reads Markdown files named on its command line, or the text of a reply on standard input. A quote is text of at least eight words inside straight or curly double quotes, or a block quote line. Fenced code is skipped. Three checks are described below; the program does checks 1 and 2, and check 3 is not built now.

1. **A quote that names its file is checked against that file.** The quote is paired with the nearest path before it in the sentence, or, failing that, the nearest after it. The quote must appear in the file once whitespace is collapsed and straight and curly quotes are made equal; Markdown emphasis is also removed when the file is Markdown. "…" or "..." inside a quote stands for cut text, so each piece must appear, in order. With `path:line`, the quote must start near that line. A miss is reported with the passage of the file that comes closest.
2. **A quote that names no file is compared with the files near it.** The program searches the files the document or reply names, the text files of the checkout, and `docs/walk/`, which git ignores. An exact match passes: the quote is right, and only its path is missing. A near match is reported, showing the file, the line and the words that differ, as "lands" against "is merged". No match passes: the user's own words and newly written text match no file. Item 4's misquote is caught this way. A near match can also be a deliberate change, when proposed text edits a file's sentence; the report then shows the change, and the agent checks it is the one meant.
3. **In a walk-document or a design, a quote presented as a file's words but naming no file is reported.** A walk-document is a file under `docs/walk/`; a design is a file whose name ends in `-design.md`. The cue is a phrase naming a document, such as "the design says" or "in this sentence:", with no path. This would warn the author to add the path, so that check 1 can run. Check 3 is not built now; it is added only if a misquote turns up that checks 1 and 2 miss.

Item 6's misquote is not caught: its quote named no file, and the comment exists only in git history, which the program does not search. Had the draft named the file it meant, check 1 would have reported it.

## Where it runs

- **Edit and Write of a Markdown file, files under `docs/walk/` included**, as a PostToolUse hook. This is the only site that runs before the user reads the quote: an agent writes an item into the walk-document before presenting it.
- **The agent's reply, at UserPromptSubmit**, as the bare-number hook does. The user has already read that reply; the warning reaches the agent with the user's answer, in time to correct the record before the change is made.
- **Markdown under `docs/` changed by a push**: the program takes the base to diff against, as `scripts/dangling-path-citation-check.py` does, and the push reminder names it as a third program.

The first pull request builds the Edit and Write site; the reply site and the push site come in later pull requests.

Like the bare-number hook, it warns and never blocks. A failure of the program itself, such as an unreadable file, is reported in its output and lets the edit, the reply or the push go on.

## Test

The test that reproduces the failure is item 4's: a walk-document line quoting "A change to a prompt is tested before it lands, on two documents" with no path, beside a draft holding "is tested before it is merged, on two documents", must be reported by check 2, and by check 1 when the line names the draft's path. Each check also gets passing cases: an exact quote, a quote with "…", and a quote of the user's words.

## Decisions

1. **Check 2 is built**, so a misquote is caught with no change to how agents write, at the cost of a slower hook and a report on each deliberate edit of a quoted sentence. (user-ruled 2026-10-22)
2. **Check 3 is left out of the first pull request**, and is added only if a misquote turns up that checks 1 and 2 miss. (user-ruled 2026-10-22)
3. **The work is its own GitHub issue**, not a section of GHI [Reference-integrity checker: links resolve and cited revision-paths exist — pure-code review check (and the home for what-else-can-code-check)](https://github.com/nedschorus/nedschorus/issues/42), which collects checks that code can do; it links to that issue. (user-ruled 2026-10-22)

## Next action

The GHI-MD gets a cold-read-full-run; a finding that would change a decision goes back to the user in a new approval-walk, and the others are fixed in the GHI-MD before it is filed. Then it is filed with `scripts/ghi-issue-write.py create docs/issues/quoted-text-credited-to-a-file-checked-against-that-file.md`. Then the first pull request builds `scripts/quoted-text-citation-check.py` with checks 1 and 2, run as a Claude Code PostToolUse hook on Edit and Write of a Markdown file; the reply site and the push site come in later pull requests.

## Relations

- GHI [Reference-integrity checker: links resolve and cited revision-paths exist — pure-code review check (and the home for what-else-can-code-check)](https://github.com/nedschorus/nedschorus/issues/42): the same family of checks; it checks that links and paths resolve, not quoted words.
- ghi-info, asked on 2026-10-22 with `--include-closed` whether any issue proposes a quote checker or covers misquotes, found none.

## Deferred-decisions

- How near a `path:line` quote must start to its line, to be set from the test cases.
- How many differing words still count as a near match in check 2, to be set from the test cases and from the walk-documents under `docs/walk/` of the agent-seats on ned-box.
