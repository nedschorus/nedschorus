---
issue: "[The style-guide-word-checker misses prose and flags code in six Markdown shapes](https://github.com/nedschorus/nedschorus/issues/1043)"
---

# The style-guide-word-checker misses prose and flags code in six Markdown shapes

Filed without the user's sign-off by the agent-seat merge-lane-2 on 2026-10-04. The user ruled on 2026-08-23 that a reproduced finding whose consequence is at least wrong behavior in operation is filed that way; the ruling is recorded in merge-lane-2's `CLAUDE.local.md` on ned-box. The sections are, in order: the reproductions, where each finding came from, why the findings matter, their causes, and the next action.

The programs are `scripts/style-guide-word-checker.py` (the checker) and `scripts/style-guide-word-checker-markdown-edit-hook.py` (the PostToolUse hook that runs the checker after an agent's Edit or Write of a Markdown file), as they are on main at commit `07fbc10e`. Line numbers below are at that commit. The style guide page, `docs/nedschorus-wiki/nedschorus-style-guide.md`, says the checker skips code; each shape below is a case where the checker or the hook gets the boundary between code and prose wrong, or does not check a line an agent just wrote.

## Reproductions

Every command below ran on ned-box on 2026-10-04 in a detached worktree of `07fbc10e`.

### How the checker reproductions were run

Items 1, 2, 5 and 6 call the checker's `find_style_guide_word_hits_in_markdown` directly on a small Markdown file, through this helper, saved as `run_checker.py`:

```python
import importlib.util, sys
spec = importlib.util.spec_from_file_location("c", sys.argv[1])
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
text = open(sys.argv[2], encoding="utf-8").read()
starts = not (len(sys.argv) > 3 and sys.argv[3] == "fragment")
print([(h.line_number, h.form) for h in m.find_style_guide_word_hits_in_markdown(text, m.APPLIES_TO_FILES, text_starts_document=starts)])
```

The command is `python3 run_checker.py scripts/style-guide-word-checker.py <input>.md`, with `fragment` added as a third argument to scan the input the way the hook scans an Edit's `new_string` (`text_starts_document=False`). The output is the list of hits as (line number, word). The word used in every input is "seat", a word the style guide lists.

### 1. A line holding a list marker before three backticks closes a fenced code block

Input, `item1.md`:

````
```
- ```
git switch seat
```

The seat is free.
````

Output: `[(3, 'seat')]`.

Expected: `[(6, 'seat')]`. In CommonMark, a closing fence is a run of backticks indented at most three spaces, with nothing before the run; inside a fenced block, the line `- ```` is content. So lines 2 to 4 are code and line 6 is prose. The checker closes the fence at line 2, reports the word in the code on line 3, then reads line 4 as a new opening fence and stays inside it to the end of the file, so the prose on line 6 is never checked.

### 2. A double-backtick code span wrapped across two lines, holding a single backtick, is read as prose on its second line

Input, `item2.md`:

```
Run ``a ` b
seat c`` now.
```

Output: `[(2, 'seat')]`.

Expected: `[]`. In CommonMark, the code span opens with two backticks on line 1 and closes with the two backticks on line 2; the single backtick inside it is content. So "seat" is inside the code span.

### Setting up the scratch repository for the hook reproductions

Items 3 and 4 run the hook itself, which checks only files Git would track in the checkout named by the payload's `cwd`. Each used a scratch repository made with `git init` in an empty directory, the item's files written there, then `git add .` and `git -c user.email=a@b -c user.name=a commit -m files`. The hook was run as `python3 <checkout of 07fbc10e>/scripts/style-guide-word-checker-markdown-edit-hook.py < payload.json`.

### 3. An Edit whose new text starts inside a code span that the Edit does not include reports a word inside the code span

Set up a scratch Git repository and commit `notes.md`:

```
Run `git switch
seat --force` now.
```

Then pipe this payload to `python3 scripts/style-guide-word-checker-markdown-edit-hook.py` (`<repository>` stands for the scratch repository's absolute path):

```json
{"tool_name": "Edit", "cwd": "<repository>", "tool_input": {"file_path": "<repository>/notes.md", "old_string": "seat --force` now.", "new_string": "seat --force` today."}}
```

Output (exit 0): a report whose hit line is `` notes.md, in "seat --force` today.": "seat": agent-seat for the identity; ... ``.

Expected: no report. "seat" is inside the code span that opens on line 1 of the file. A Write of the same two lines to a new tracked file, `` Run `git switch\nseat --force` today.\n ``, gives no report (exit 0), so the two tools give different answers about the same text.

This shape differs from the wording of the original finding. The original finding was made against an earlier version of the hook, which chose which lines of an Edit to check from the Edit's patch; on main, the hook scans the Edit's `new_string` alone (line 100), so the same class of error now shows up as the case above. The hook's module docstring already records the related limitation for fences, at line 7: "Edit scans new_string alone, so an enclosing code fence may be invisible to the checker."

### 4. A Write does not check a line whose text the committed file already holds, wherever that line now stands

Set up a scratch Git repository and commit two files. `moved.md`:

````
```
The seat is free.
```
````

and `dup.md`:

```
The seat is free.
```

Case 4a, a line moved from code into prose. Pipe this payload to the hook:

```json
{"tool_name": "Write", "cwd": "<repository>", "tool_input": {"file_path": "<repository>/moved.md", "content": "The seat is free.\n"}}
```

Output: nothing (exit 0). Expected: a report of "seat" on line 1, because line 1 is now prose; the committed copy of that text was inside a fenced code block, where the checker would not report the word.

Case 4b, a second copy of a committed line. Pipe this payload to the hook:

```json
{"tool_name": "Write", "cwd": "<repository>", "tool_input": {"file_path": "<repository>/dup.md", "content": "The seat is free.\n\nThe seat is free.\n"}}
```

Output: nothing (exit 0). Expected: a report of "seat" on line 3, the copy the Write added.

Control: the same Write content as case 4a, written to an untracked new file `fresh.md` in the same repository, reports `fresh.md:1: "seat": ...` (exit 0).

merge-lane-2's [review 5394540218](https://github.com/nedschorus/nedschorus/pull/934#pullrequestreview-5394540218), where this was first recorded, notes that the hook's author has said comparing the Write's lines against the set of committed lines is intended. Case 4a shows the comparison misjudging a line whose text is unchanged but whose context changed from code to prose, which is a case that design answer did not address.

### 5. A heading after a list item, then an indented line of three tildes, hides all later prose

Input, `item5.md`:

````
- item
# Heading

    ~~~

The seat is free.
````

Output: `[]`.

Expected: `[(6, 'seat')]`. In CommonMark, the unindented heading on line 2 ends the list, so line 4, after a blank line and indented four spaces, is an indented code block holding the text `~~~`, and line 6 is prose. The checker still treats the list as open at line 4, so it does not read line 4 as indented code; it reads line 4 as an opening fence, and no closing fence follows, so nothing after line 4 is checked.

### 6. An Edit fragment holding an indented line of three tildes hides all later prose in the fragment

Input, `item6.md`:

````
Prose.

    ~~~

The seat is free.
````

Output with `fragment` (how the hook scans an Edit's `new_string`): `[]`. Output without `fragment` (how the hook scans a Write): `[(5, 'seat')]`.

Expected: `[(5, 'seat')]` in both. A fragment does not show whether line 3 is an indented code block or a fence inside a list item, but under either reading line 5, unindented after a blank line, is prose: an unindented line after a blank ends a list item and any fence opened inside the list item. The checker reads line 3 as an opening fence, no closing fence follows, and so nothing after line 3 is checked.

## Provenance

Items 1 to 4 were found by the Codex review cell, `scripts/code-review-codex-cell.py`, on PR [style-guide-word-checker: the project word list, its scanner, and a PostToolUse hook on markdown writes](https://github.com/nedschorus/nedschorus/pull/934), and recorded for a follow-up GHI in merge-lane-2's [review 5394540218](https://github.com/nedschorus/nedschorus/pull/934#pullrequestreview-5394540218) of that pull request. A fifth finding in that review, an indented code block read as prose, was fixed by PR [style-guide-word-checker: an indented code block is code, and a capitalised form is looked up](https://github.com/nedschorus/nedschorus/pull/1003) and is not part of this GHI. Items 5 and 6 were found by the Codex review cell on the second review round of that same PR 1003 and recorded in merge-lane-2's [review 5408173384](https://github.com/nedschorus/nedschorus/pull/1003#pullrequestreview-5408173384), which ran both inputs through main's checker and found main silent on both before PR 1003 merged.

## Why this matters

Each shape is wrong behavior in operation, in one of two directions:

- A false report (items 2 and 3, and item 1's report of line 3) tells the author to change a word inside code, such as a command or a path. An author who follows the report breaks the code; an author who learns that reports can be wrong starts ignoring the hook's reports, the true ones included.
- A silence (items 4, 5 and 6, and item 1's missed line 6) lets a listed word in prose merge unreported, which is what the checker exists to prevent. Items 1, 5 and 6 are the worst case: a single misread line turns off checking for the whole rest of the file or of the Edit.

## Causes

All line numbers are in `scripts/style-guide-word-checker.py` at `07fbc10e` unless the hook is named.

- Item 1: `FENCE_PATTERN` (line 117) accepts any indentation and an optional list marker before the fence characters. That is right for an opening fence that starts a list item, but `find_style_guide_word_hits_in_markdown` uses the same match to close an open fence (lines 263 to 269), where CommonMark allows at most three spaces of indentation and no list marker.
- Item 2: `INLINE_CODE_SPAN_PATTERN` (line 124), `` (`+).+?\1 ``, can match a backtick run shorter than the run that opens the span, because the regular expression backtracks into the opening run. On line 1 of the input the pattern takes `` `a ` `` as a span of single backticks, so no span is left open to carry to line 2. CommonMark requires the closing run to have the same length as the opening run, with no backtick on either side of either run.
- Item 3: the hook passes the Edit's `new_string` alone to the checker (hook line 100). Text before the start of `new_string` is not seen, so a closing backtick whose opener lies before the Edit is read as an unmatched backtick, and the code before the backtick is read as prose.
- Item 4: `hits_in_write` in the hook (hook lines 111 to 126) builds the set of the committed file's lines and checks only lines whose text is not in that set. A line that moved, or a second copy of a line, has text already in the set.
- Item 5: the list tracking (lines 244 to 258) ends a list only at an unindented line after a blank line; a heading straight after a list item leaves the list open. With the list open, the indented `~~~` on line 4 is not read as indented code, and `FENCE_PATTERN`, accepting any indentation, opens a fence that never closes.
- Item 6: with `text_starts_document=False` the indentation tracking is skipped entirely (line 244), so the indented `~~~` reaches `FENCE_PATTERN`, which accepts any indentation and opens a fence that never closes.

## Next action

Fix the six shapes in the checker and the hook, adding one case per item to `scripts/style-guide-word-checker-markdown-edit-hook-test.py`, built from the inputs above. Each case fails on main at `07fbc10e` and passes after the fix.

- Items 1, 5 and 6: accept a closing fence only at zero to three spaces of indentation with nothing before the run, as CommonMark does. End list tracking at a heading as well as at an unindented line after a blank. Decide how a fence that never closes is treated; one choice is to treat an indented opening fence whose closing fence never comes as not a fence, so that a misread line cannot hide the rest of the text.
- Item 2: match a code span's closing run only when the closing run has exactly the opening run's length, with no backtick next to either run; `backtick_run_closing` (line 192) already matches runs that way and can serve as the model.
- Item 3, and the fence limitation the hook's docstring records: the hook runs after the Edit, so the file on disk holds the edited text. One choice is to find `new_string` in the file and scan the whole file with `line_numbers` set to the lines `new_string` covers, as the Write path already does. The other is to keep scanning `new_string` alone and state in the hook's docstring that an Edit starting inside a code span can be misreported. Whoever fixes this chooses, and gives the reason in the pull request.
- Item 4: one choice is to number the Write's added lines from a line diff against the committed file, such as `difflib.SequenceMatcher`, so that a moved line or a second copy counts as added, and so that a line whose surrounding code fence was removed is checked. The other is to keep the set comparison and state in the hook's docstring that a Write does not check a line whose text the committed file already holds. Whoever fixes this chooses, and gives the reason in the pull request.
