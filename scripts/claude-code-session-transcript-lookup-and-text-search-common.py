#!/usr/bin/env python3
"""Find Claude Code session transcripts under ~/.claude/projects/: an agent-seat's project directory,
one session's transcript by its id, and the transcripts whose text matches a pattern."""

import re
import subprocess
from pathlib import Path


def project_directory_for_seat(seat_path, projects_root):
    """Return the folder under projects_root that Claude Code names after the seat's resolved path."""
    # The harness replaces every non-ASCII-alphanumeric character, including underscores, with a dash.
    mangled = re.sub(r"[^a-zA-Z0-9]", "-", str(seat_path.resolve()))
    return projects_root / mangled


class ClaudeCodeSessionTranscriptFoundInSeveralProjectDirectoriesError(Exception):
    """A session id names a transcript in more than one project directory; `paths` lists them, sorted."""

    def __init__(self, session_id, paths):
        super().__init__(f"session {session_id} appears in several project directories: "
                         + ", ".join(str(path) for path in paths))
        self.paths = list(paths)


def claude_code_session_transcript_paths_for_session_id_in_working_directory_project_directory_if_present_else_in_every_project_directory(
        session_id, working_directory, projects_root):
    """Return [the keyed path] when the session's transcript is in working_directory's project directory,
    else the session's transcript in every project directory under projects_root, sorted, which may be none."""
    # handoff-extract-conversation.py keeps a copy of this rule as transcript_paths_for_session, because it
    # runs copied beside hooks that lack this module; this module's test fails if the two disagree.
    keyed_path = project_directory_for_seat(Path(working_directory), projects_root) / f"{session_id}.jsonl"
    if keyed_path.is_file():
        return [keyed_path]
    return sorted(projects_root.glob(f"*/{session_id}.jsonl"))


def claude_code_session_transcript_path_found_by_session_id(session_id, working_directory, projects_root):
    """Return the session's one transcript, or None when there is none.

    Raises ClaudeCodeSessionTranscriptFoundInSeveralProjectDirectoriesError when the keyed path is absent
    and the session id is in several project directories, since then no one of them is the session's.
    """
    paths = claude_code_session_transcript_paths_for_session_id_in_working_directory_project_directory_if_present_else_in_every_project_directory(
        session_id, working_directory, projects_root)
    if len(paths) > 1:
        raise ClaudeCodeSessionTranscriptFoundInSeveralProjectDirectoriesError(session_id, paths)
    return paths[0] if paths else None


def claude_code_session_transcripts_matching_any_pattern_ignoring_case(
        roots, patterns, include_subagents, ripgrep_program="rg", grep_program="grep"):
    """Return (paths, problems): the .jsonl files under roots whose raw JSON text matches any of
    patterns, ignoring case, sorted; and one line for each thing the search could not read or do.

    Runs ripgrep, and grep -E when ripgrep is not installed. A pattern is a regular expression both
    read alike, such as one claude_code_session_transcript_raw_json_prefilter_pattern returns.
    Without include_subagents, only <root>/<project directory>/<session>.jsonl files are listed, not
    the subagent transcripts in <session>/subagents/. When problems is not empty, paths may miss files.
    """
    roots = [str(root) for root in roots]
    try:
        completed = subprocess.run(
            [ripgrep_program, "--no-ignore", "--hidden", "--ignore-case", "--files-with-matches",
             *([] if include_subagents else ["--max-depth", "2"]), "--glob", "*.jsonl",
             *[argument for pattern in patterns for argument in ("-e", pattern)], "--", *roots],
            stdin=subprocess.DEVNULL, capture_output=True)
        searcher = "ripgrep"
    except FileNotFoundError:
        untranslatable = [pattern for pattern in patterns
                          if r"\d" in pattern or any(ord(character) > 0x7f for character in pattern)]
        if untranslatable:
            # grep -E has no \d, and how it folds a non-ASCII letter depends on the locale, so it
            # could leave out a transcript that ripgrep or Python would match.
            return [], [f"ripgrep ({ripgrep_program}) is not installed, and grep cannot search for "
                        f"{untranslatable[0]!r} as ripgrep would, so no transcript was searched"]
        try:
            completed = subprocess.run(
                [grep_program, "-r", "-l", "-i", "-E", "--include=*.jsonl",
                 *[argument for pattern in patterns for argument in ("-e", pattern)],
                 "--", *roots],
                stdin=subprocess.DEVNULL, capture_output=True)
        except FileNotFoundError:
            return [], [f"neither ripgrep ({ripgrep_program}) nor grep ({grep_program}) is installed, "
                        f"so no transcript was searched"]
        searcher = "grep"
    problems = [f"{searcher} could not search everything: {line.strip()}"
                for line in completed.stderr.decode("utf-8", "replace").splitlines() if line.strip()]
    if completed.returncode not in (0, 1) and not problems:
        problems.append(f"{searcher} exited {completed.returncode} and said nothing")
    paths = [Path(line) for line in completed.stdout.decode("utf-8", "replace").splitlines() if line]
    if searcher == "grep" and not include_subagents:
        # grep has no --max-depth, so the subagent transcripts it read are dropped here.
        paths = [path for path in paths
                 if any(path.parent.parent == Path(root) for root in roots)]
    return sorted(paths), problems


def claude_code_session_transcript_raw_json_prefilter_pattern(pattern):
    """The pattern for ripgrep to pick transcripts by, or None when every transcript must be read.

    Only plain text gets a prefilter, since Python's re and ripgrep read many escapes and classes
    differently: \\w, for one, matches ½ in Python and not in ripgrep. Plain text here is ASCII
    with no regex metacharacter, no quote mark and no control character, which a transcript's raw
    JSON writes as themselves, after dropping a leading ^ and a trailing $, since in the JSON a
    message is one string inside a longer line.

    Python's re.IGNORECASE folds more than ripgrep's --ignore-case: "item" matches "İtem" in
    Python and not in ripgrep. So each ASCII letter Python folds onto a non-ASCII one becomes a
    class of all of them, and the result is a regular expression rather than fixed text.
    """
    pattern = pattern.removeprefix("^")
    if pattern.endswith("$"):
        pattern = pattern[:-1]
    if any(character in PLAIN_TEXT_EXCLUDED_CHARACTERS or not " " <= character <= "~" for character in pattern):
        return None
    return "".join(ASCII_LETTERS_THAT_PYTHON_IGNORECASE_FOLDS_ONTO_NON_ASCII_LETTERS.get(character, character)
                   for character in pattern)


# Python's and ripgrep's regex metacharacters, and the quote mark, which JSON writes escaped.
PLAIN_TEXT_EXCLUDED_CHARACTERS = set('.^$*+?()[]{}|\\"')


# Each ASCII letter that Python's re.IGNORECASE matches with a non-ASCII letter, as a class of all
# the letters it matches, found by testing every code point.
ASCII_LETTERS_THAT_PYTHON_IGNORECASE_FOLDS_ONTO_NON_ASCII_LETTERS = {
    letter: f"[{lower}{lower.upper()}{others}]"
    for lower, others in (("i", "İı"), ("k", "K"), ("s", "ſ"))
    for letter in (lower, lower.upper())
}
