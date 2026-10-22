# Check that words quoted from a file appear in that file

## What goes wrong

Agents quote files to the user: a walk-document shows a design's sentence and asks the user to approve it. Nothing checks that the quoted words are the file's words. On 2026-10-21 the walk-document of the approval-walk on the cold-read design rewrite misquoted twice, and an advisor caught both before the user saw them; no program would have.

1. Item 4. The walk-document's draft, `/home/nedlern/agents/cold-read-improvement-cold-read-design-full-run/docs/walk/cold-read-design-2026-10-15-draft.md` line 41, still reads: Proposed: "A change to a prompt is tested before it lands, on two documents: …". The rewrite it quoted, `docs/drafts/cold-read-design-rewrite-after-cold-read-full-run-2026-10-16.md` line 31 at commit fe0042996^ on branch `cold-read-design-cold-read-full-run-rewrite-topic-branch`, reads "A change to a prompt is tested before it is merged, on two documents: …". The walk-minutes, `docs/walk/cold-read-design-2026-10-15-minutes.md` line 17 in that worktree, record the fix: "walk-document now says "is merged" as the rewrite does".
2. Item 6. The first draft quoted the pin comment "user-picked 2026-08-03; xhigh "OK for codex" same date" as one the cold-read reviewers' model pins once carried. That comment was in `scripts/code-review-codex-cell.py`, the PR reviewer's Codex wrapper, until commit 80454332d; the cold-read Codex reviewer, then named md-review-codex-cell.py and now `nc-systems/cold-read/cold-read-codex-cell.py`, carried a different comment, dropped by commit 096fb43c2. The same walk-minutes, line 24, record the corrected attribution.

The harm: the user approves quoted words, so a misquote is approved text that is not the text that ships. merge-lane-2 then checks the shipped words against the walk-minutes by hand, as it did for PR [PR reviewer instructions and CLAUDE.md: the defect-fix rule rewritten as the reviewer's numbered steps — a case fix or workaround that removing the root cause would make useless blocks, unless a #follow_up link or an outage settles it](https://github.com/nedschorus/nedschorus/pull/1636) and PR [CLAUDE.md: five words the style guide lists to avoid take its replacements (live, harness, gate, head twice)](https://github.com/nedschorus/nedschorus/pull/1642) on 2026-10-22.

## What already exists

Three programs find a citation by its written form alone, without the agent saying it wrote one:

- `scripts/bare-number-citation-in-markdown-and-agent-reply-warning-hook.py`: a pull request or GitHub issue cited by a bare number, or linked under text that is not its title. It runs on Edit and Write of a Markdown file and, at UserPromptSubmit, on the agent's previous reply. It warns; it never blocks.
- `scripts/dangling-path-citation-check.py`: a cited path that does not exist.
- `scripts/stale-code-citation-check.py`: a `path:line` citation whose code file changed after the document's design-as-of date.

The last two run when an agent pushes a change to a Markdown file, reminded by `nc-systems/general-tools/claude-code-bash-git-push-of-markdown-change-citation-checks-reminder-hook.py`. None checks quoted words. `scripts/citation-and-history-marker-tests-date-pattern-common.py`, despite its name, holds only the date patterns that keep dates out of agent-facing text, so it has nothing to reuse here.

## The rule

Anthropic's Citations feature returns each quote with its source: the quoted text, the document, and the place in it. The project borrows that written form, not the API: **words quoted from a file name the file, as a path or `path:line`, in the same sentence.**

## What the check does

A new program, proposed name `scripts/quoted-text-citation-check.py`, reads a Markdown file or a reply and does three things.

1. **A quote that names its file is checked against that file.** The quote must appear in the file, after both sides have their whitespace and Markdown emphasis normalised and straight and curly quotes made equal; "…" or "..." inside a quote stands for cut text, so each piece must appear, in order. With `path:line`, the quote must start within a few lines of that line. A miss is reported with the nearest passage the file does hold.
2. **A quote that names no file is searched for nearby.** The program looks for the quote, a sentence of at least eight words, in the files the same document names and in the Markdown files of the checkout, ignored files included. An exact match passes. A near match, the same words but a few, is reported as a likely misquote with the file and line of the near match. No match passes: the user's own words and newly proposed text match no file. Item 4's misquote is caught this way: its quote named no file, and the rewrite holds a near match.
3. **In a walk-document or a design, a quote introduced as a file's words but naming no file is reported.** The cue is a document named in the sentence, such as "the design says" or "the rewrite keeps the rule, in this sentence:", with no path. This is a warning to add the path, so that check 1 can run.

Item 6's misquote is not caught by any of the three: its quote named no file, and the comment exists only in git history. Had the draft named the file it meant, check 1 would have reported it.

## Where it runs

- **The agent's reply, at UserPromptSubmit**, as the bare-number hook does. Walk-documents live in `docs/walk/`, which `.gitignore` excludes, so a check run only on pushed changes would never see them; the reply is where the user meets the quote.
- **Markdown under `docs/` changed by a push**, as a third program the push reminder names.

Like the bare-number hook, it warns and never blocks. A failure of the program itself, such as an unreadable file, is reported in its output and lets the reply or the push go on.

## Test

The test that reproduces the failure is item 4's: a walk-document line quoting "A change to a prompt is tested before it lands, on two documents" with no path, beside a draft holding "is tested before it is merged, on two documents", must be reported by check 2, and by check 1 when the line names the draft's path. Each check also gets a passing case: an exact quote, a quote with "…", and a quote of the user's words.

## Decisions for the user

1. Check 2 searches files the document did not name. It catches item 4 without any change to how agents write, at the cost of a slower hook and some false warnings when a proposed text is a deliberate small change to a file's sentence.
2. Check 3 depends on a list of cue phrases and will miss some quotes and wrongly flag others.
3. Whether this is its own GHI or a section of GHI [Reference-integrity checker: links resolve and cited revision-paths exist — pure-code review check (and the home for what-else-can-code-check)](https://github.com/nedschorus/nedschorus/issues/42), which collects checks that code can do.

## Next action

The user rules on the three decisions in an approval-walk. Then the GHI is filed, and the program is built in its own pull request, starting with check 1 and the reply site.

## Relations

- GHI [Reference-integrity checker: links resolve and cited revision-paths exist — pure-code review check (and the home for what-else-can-code-check)](https://github.com/nedschorus/nedschorus/issues/42): the same family of checks; it checks that links and paths resolve, not quoted words.
- ghi-info, asked on 2026-10-22 with `--include-closed` whether any issue proposes a quote checker or covers misquotes, found none.
