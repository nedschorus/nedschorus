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
        try:
            completed = subprocess.run(
                [grep_program, "-r", "-l", "-i", "-E", "--include=*.jsonl",
                 # grep -E has no \d.
                 *[argument for pattern in patterns for argument in ("-e", pattern.replace(r"\d", "[0-9]"))],
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


def pattern_without_anchors(pattern):
    """The pattern with its line and text anchors removed, for ripgrep to pick transcripts by.

    ripgrep reads a transcript's raw JSON records, where a message is one quoted string inside
    a longer line, so an anchor such as ^ or $ would miss it. Without its anchors the pattern
    matches wherever it matched before, and the user's messages are then matched with them.
    """
    kept = []
    in_class = False
    index = 0
    while index < len(pattern):
        character = pattern[index]
        if character == "\\" and index + 1 < len(pattern):
            if in_class or pattern[index + 1] not in "AzZ":
                kept.append(pattern[index:index + 2])
            index += 2
            continue
        if in_class:
            closing = pattern.find(":]", index + 2)
            if pattern.startswith("[:", index) and closing != -1:
                kept.append(pattern[index:closing + 2])
                index = closing + 2
                continue
            if character == "]":
                in_class = False
        elif character == "[":
            in_class = True
            kept.append("[")
            index += 1
            # A ] first in a class, or right after its ^, is a literal ].
            for opening in "^]":
                if pattern[index:index + 1] == opening:
                    kept.append(opening)
                    index += 1
            continue
        elif character in "^$":
            index += 1
            continue
        kept.append(character)
        index += 1
    return "".join(kept)


def claude_code_session_transcript_raw_json_prefilter_pattern(pattern):
    """The pattern for ripgrep to pick transcripts by, or None when every transcript must be read.

    ripgrep reads a transcript's raw JSON, where a line break, a tab, a quote mark, a backslash
    and other control characters are each written as an escape of two or more characters. A
    pattern that could match one of those characters in a message could fail to match its
    escape, so it gets no prefilter. Anchors are dropped first, since in the JSON a message is
    one string inside a longer line.
    """
    pattern = pattern_without_anchors(pattern)
    index = 0
    while index < len(pattern):
        character = pattern[index]
        if character == "\\":
            following = pattern[index + 1:index + 2]
            # \w and \d match only characters JSON writes as themselves; every other escaped
            # letter or digit (\s, \S, \W, \D, \b, \n, \t, \x, \u, \p, back-references) may not.
            if following in ("\\", '"') or (following.isalnum() and following not in "wd"):
                return None
            index += 2
            continue
        if character in '.["' or ord(character) < 0x20:
            return None
        index += 1
    return pattern
