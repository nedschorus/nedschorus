---
issue: "[The transcript search's ripgrep prefilter skips a transcript whose matching letter is written as a JSON \\u escape, such as the letter İ written as \\u0130](https://github.com/nedschorus/nedschorus/issues/2315)"
---

# The transcript search's ripgrep prefilter skips a transcript whose matching letter is written as a JSON \u escape, such as the letter İ written as \u0130

Filed by merge-lane-2 on 2026-10-31. Codex's review cell raised the defect while reviewing another pull request; a subagent of merge-lane-2 reproduced it on ned-box the same day. Line numbers are on main at `a6bdac066`.

## Reproduction

Before Python reads any transcript, `scripts/search-user-messages-in-transcripts.py` and `scripts/log-store-past-discussions-regex-search-newest-first.py` ask ripgrep which transcript files contain the search pattern, and skip the rest. The ripgrep pattern comes from `claude_code_session_transcript_raw_json_ripgrep_prefilter_pattern_from_search_text_or_none_when_not_plain_text` in `scripts/claude-code-session-transcript-lookup-and-text-search-common.py:99-118`, from [PR 2213](https://github.com/nedschorus/nedschorus/pull/2213). For plain ASCII text, that function turns each of the letters i, k and s into a class that also holds the non-ASCII letters Python's case-insensitive matching accepts for that letter, taken from the table `ASCII_LETTERS_THAT_PYTHON_IGNORECASE_FOLDS_ONTO_NON_ASCII_LETTERS` (`scripts/claude-code-session-transcript-lookup-and-text-search-common.py:125-131`); so `item` becomes `[iIİı]tem`. ripgrep searches the raw JSON line, though, and a JSON writer may store the letter İ as the six ASCII characters backslash, `u`, `0`, `1`, `3`, `0`, written `\u0130`, which `[iIİı]` does not match. Python's search, which reads the decoded message, would have matched.

Reproduced on ned-box with two one-line transcripts, each holding the user message "please fix the İtem list": `escaped.jsonl`, written by Python's `json.dumps` with its default `ensure_ascii=True`, so the letter İ is stored as `\u0130`; and `raw.jsonl`, written with `ensure_ascii=False`, so the letter İ is stored as itself. A third transcript, `b.jsonl`, holds "hello item". The files are in `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-2/ghi-reproductions/transcript-prefilter-json-escape-2026-10-31/projects/`, written here as `$P`. In a checkout of main on ned-box, this command:

```
python3 scripts/search-user-messages-in-transcripts.py --projects-dir $P item
```

found `raw.jsonl` and `b.jsonl` and printed "ripgrep found none of the search pattern(s) in 1 of them, so only the other 2 were opened"; `escaped.jsonl` was skipped. The pattern `it.m`, which gets no prefilter because `.` is a regex metacharacter, found all three:

```
python3 scripts/search-user-messages-in-transcripts.py --projects-dir $P 'it.m'
```

Judged from reading the code, not run: `scripts/log-store-past-discussions-regex-search-newest-first.py:852` builds its prefilter with the same function, so it skips the same transcripts.

## Why it matters, and how often

A search that skips a matching transcript reports fewer results than exist, and nothing in its output says a match was lost.

Today the defect loses a result only for a transcript written by a JSON writer other than Claude Code. Claude Code writes non-ASCII letters as raw UTF-8. A search of real transcripts found no line holding a JSON escape of İ (`\u0130`), ı (`\u0131`), the Kelvin sign K (`\u212a`) or ſ (`\u017f`): 0 lines in 7.3 GB of `~/.claude/projects` on ned-box, and 0 in 5.4 GB of the Mac transcript mirror under `/home/nedlern/nedschorus-logs/agent-session-files-by-machine/mac/projects/`. The search used the regular expression in `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-2/ghi-reproductions/transcript-prefilter-json-escape-2026-10-31/check.py`, which counts a backslash, `u` and one of those four code points in either hex case, and skips a backslash that is itself escaped; a line that only quotes the escape as text, as this GHI-MD does, stores two backslashes and is not counted.

## Next action

For reboot-test, the agent-seat that wrote PR 2213: decide whether to fix the prefilter or close this GHI as not planned, given that no real transcript holds such an escape today.

A fix of the prefilter could generate, from the same table, an alternative for each non-ASCII letter's JSON escape in either hex case, so that `item` becomes a pattern like `(?:[iIİı]|\\u0130|\\u0131)tem` matched with ripgrep's `--ignore-case`; the Kelvin sign and ſ then get their escapes too, and so does any letter added to the table later. Two limits to weigh:
- When ripgrep is not installed, the module falls back to `grep -E`, and searches no transcript at all when a prefilter pattern holds a non-ASCII letter (`scripts/claude-code-session-transcript-lookup-and-text-search-common.py:69-76`); `grep -E` also does not read `(?:`. The fallback would need its own answer.
- A JSON writer may escape an ASCII letter too, such as `i` written as `\u0069`. Python's `json.dumps` does not, but a fix that aims to cover every JSON writer would have to.

The other fix, giving no prefilter to any pattern holding i, k or s, is simple but drops the prefilter for most searches, since most search words hold one of those letters.

A fix comes with a test that loops over every non-ASCII letter in the table, writes a one-line transcript with `json.dumps(..., ensure_ascii=True)` for each, and expects both `scripts/search-user-messages-in-transcripts.py` and `scripts/log-store-past-discussions-regex-search-newest-first.py` to find the match.
