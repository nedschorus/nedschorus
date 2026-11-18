---
issue: "[The walk-me-through recommendation reader reads an HTML comment inside another HTML block as the item's recommendation](https://github.com/nedschorus/nedschorus/issues/3142)"
---

# The walk-me-through recommendation reader reads an HTML comment inside another HTML block as the item's recommendation

## Reproduction

On ned-box, on main at `8f38e5740`, this was run: `python3 /home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers/ghi-reproductions-2026-11-11/walk-me-through-recommendation-reader-html-comment-inside-html-block-reproduction.py <a checkout of main>`. It loads `nc-systems/skills/walk-me-through/walk-me-through-approval-walk-minutes-and-walk-document-item-finder-common.py` from the checkout and runs `approval_walk_item_recommendation_text(prose_lines(text, markdown_parser()))` on three approval-walk item texts:

```python
for text in ["<div>\n<!-- Recommendation: hidden -->\n</div>\n\nRecommendation: shown.\n",
             "<!-- Recommendation: hidden -->\n\nRecommendation: shown.\n",
             "Recommendation: shown.\n\n<div>\n<!-- Recommendation: hidden -->\n</div>\n"]:
```

It printed:

```
'<div>\n<!-- Recommendation: hidden -->\n</div>\n\nRecommendation: shown.\n' -> shown
'<!-- Recommendation: hidden -->\n\nRecommendation: shown.\n' -> shown
'Recommendation: shown.\n\n<div>\n<!-- Recommendation: hidden -->\n</div>\n' -> hidden -->
```

The first two are right only by luck of order: the visible recommendation comes last. In the third, the item's reader sees only `Recommendation: shown.`, because the browser hides the comment, but the program returns `hidden -->`, the comment's own text, because it is the last recommendation it finds. An item whose only recommendation is such a hidden comment, `<div>\n<!-- Recommendation: hidden -->\n</div>\n`, also returns `hidden -->`, where the reader sees no recommendation at all.

## What is wrong

`prose_lines()` cuts an HTML comment out of the lines only when the comment starts an `html_block` token, or is an `html_inline` child of an `inline` token (the `elif` at line 267 of the finder module). A comment inside another HTML block, such as `<div>…<!-- Recommendation: x -->…</div>`, belongs to an `html_block` whose content starts with `<div>`, so it stays in the lines. `approval_walk_item_recommendation_text()` then finds `Recommendation:` inside it, and because it returns the last recommendation it finds, a hidden one after the visible one wins.

Two programs read an item's recommendation through this function:

- `nc-systems/skills/walk-me-through/walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook.py` (line 623), which expands the user's short answer, such as "yes", into the item's recommendation, so it would expand his answer into a recommendation he never saw;
- `nc-systems/skills/walk-me-through/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py` (line 1569), which quotes the recommendation in its `MOVED_ON_NO_DECISION_REFUSED` refusal and decides with it whether an item needs a decision.

No walk-minutes file holds such a comment yet: on ned-box, `grep -rlE '<(div|details|table|p)[ >]' /home/nedlern/nedschorus-logs/walk/ | xargs -r grep -l '<!--'` found no file there with both an HTML block tag and a comment, on 2026-11-11.

The Codex review cell found the defect while reviewing pull request [3089](https://github.com/nedschorus/nedschorus/pull/3089), and merge-lane-2 graded it fix-next, as finding 2 of its approving review there. That pull request did not cause it; main had it before. Its root cause is close to the first one that pull request's `#root_cause` names, that `prose_lines()` found HTML comments through the parser's `html_block` tokens: it still finds them only through tokens that start with `<!--`, so a comment that starts partway through an HTML block is not found. Finding 1 of the same review, a backquoted `<!--` in a paragraph that also holds a real comment, is a separate fix-next finding and is not covered here.

## What to do

The owner is the agent-seat agent-instructions-editor, whose pull request 3089 wrote the current `prose_lines()`.

1. Make `prose_lines()` cut every HTML comment the reader does not see, wherever it sits in an HTML block, keeping each line's index as it does now.
2. Add a test that runs `approval_walk_item_recommendation_text(prose_lines(…))` directly, so that it covers both programs above, on each item text of the reproduction and on the hidden-only item, and asserts the recommendation the reader sees: `shown` for the three, None for the hidden-only one, and that `prose_lines()` returns as many lines as the text has. The first two cases pass on main and guard against a fix that breaks them; the third and the hidden-only one fail on main. The finder module has no test file of its own (`git ls-files nc-systems/skills/walk-me-through/tests | grep finder` on main finds none); a place for it is `nc-systems/skills/walk-me-through/tests/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close-test.py`.
