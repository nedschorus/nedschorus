---
issue: "[The walk-me-through walk finder cuts HTML comments over raw text, inside code spans and tag attributes included](https://github.com/nedschorus/nedschorus/issues/3229)"
---

# The walk-me-through walk finder cuts HTML comments over raw text, inside code spans and tag attributes included

The walk finder, `nc-systems/skills/walk-me-through/walk-me-through-approval-walk-minutes-and-walk-document-item-finder-common.py`, reads every walk-document and walk-minutes file with its comments cut out, so that a note in a comment is never read as structure, such as a recommendation or a `#new` line. It cuts them with the pattern `HTML_COMMENT = re.compile(r"<!--.*?(?:-->|\Z)", re.S)` ([line 125 on main at 17e72b31](https://github.com/nedschorus/nedschorus/blob/17e72b316c06ddfc587780842dc8a6f426225928/nc-systems/skills/walk-me-through/walk-me-through-approval-walk-minutes-and-walk-document-item-finder-common.py#L125)), which `without_html_comments` ([line 244](https://github.com/nedschorus/nedschorus/blob/17e72b316c06ddfc587780842dc8a6f426225928/nc-systems/skills/walk-me-through/walk-me-through-approval-walk-minutes-and-walk-document-item-finder-common.py#L244)) runs over the raw lines of every HTML block and of every paragraph that holds a comment, as `prose_lines` chooses them ([line 251](https://github.com/nedschorus/nedschorus/blob/17e72b316c06ddfc587780842dc8a6f426225928/nc-systems/skills/walk-me-through/walk-me-through-approval-walk-minutes-and-walk-document-item-finder-common.py#L251)).

## What is wrong

The pattern sees text, not Markdown or HTML, so it opens a comment at every `<!--`, including two kinds that open none for the reader:

- a `<!--` inside a code span, as in `` `<!-- x -->` ``, in a paragraph that also holds a real comment on any of its lines: the code span's text is cut, and the reader sees text the program does not read;
- a `<!--` inside a tag's attribute, as in `<div title="<!--">`: the cut runs from there to the next `-->`, or to the end of the text when none follows, and hides text the reader sees, such as a recommendation.

Either way the program reads an item differently from the user, who sees the rendered walk-document.

## Why it matters

Pull request [3180](https://github.com/nedschorus/nedschorus/pull/3180), not yet merged when this was written, works around both cases in `nc-systems/skills/walk-me-through/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py` instead of fixing the pattern, with two detections:

- check refuses a `#new` or `#new_if_d` line whose text the cut changed (`UNREADABLE_COMMENT_CUT`), because the fast read would not read that line as written;
- `check --moved-on-no-decision` refuses when the item shows no recommendation as the walk finder reads it, but shows one once a `<!--` inside an HTML open tag opens no comment (`MOVED_ON_NO_DECISION_HIDDEN_RECOMMENDATION`).

Each detection sends the agent to rewrite the walk-document. Every other reader of the walk finder's lines, such as the hook that expands the user's short answer to an approval-walk item, `nc-systems/skills/walk-me-through/walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook.py`, still misreads the same text.

## What to do

Do this after pull request 3180 merges, on a branch cut from main.

1. Change the walk finder's comment cut so that it cuts only comments that a reader of the rendered document does not see: no text inside a code span, and nothing from a `<!--` inside a tag. Keep what the cut does now in every other case: it keeps each line's index, it cuts a comment inside an HTML block that opens with another tag, as in `<div><!-- Recommendation: x --></div>`, and it cuts an unclosed `<!--` that opens an HTML block to the end of that block.
2. The walk finder has no test file of its own. Add one, `nc-systems/skills/walk-me-through/tests/walk-me-through-approval-walk-minutes-and-walk-document-item-finder-common-test.py`, with a test for each case above and for a real comment after an unclosed `<`, as in `x<y` followed by `<!-- note -->`, which the cut must still cut.
3. Remove the two detections that pull request 3180 adds to the check program, with their messages and their tests, because nothing is left for them to find. Their tests in `nc-systems/skills/walk-me-through/tests/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close-test.py` fail once the cut is fixed, so the fix cannot merge without this step.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01LcUqXNha1xA1T3SCpiiV1F
