#!/usr/bin/env python3
"""Tests for claude-code-session-transcript-lookup-and-text-search-common.py.

Run: python3 scripts/claude-code-session-transcript-lookup-and-text-search-common-test.py
Prints one line per case and exits non-zero if any case fails.

The three mangle cases expect hard-coded literal folder names, not ones
derived from the function under test, so a mangling bug cannot be mirrored
into the expectation; their seat paths are rooted at a directory that
exists on no machine, so resolve() passes them through unchanged. The
symlink case builds a real link in a temporary directory, because Claude
Code names the folder after the resolved path the session runs in. That
directory's path is known only at run time, so the case computes its
expected name with its own character test, independent of the function
under test.

The callers case loads every program that names a seat's transcript folder
and checks each against the same hard-coded name, so a caller that keeps a
rule of its own (the handoff-supervisor and the conversation extractor once
kept "_") fails here instead of searching a folder that does not exist. It
then compares each caller with the shared function over paths holding every
character class the rule treats, and over a symlinked seat path, so a copy
of the rule that drifts on any of them fails too.

The lookup cases build project directories in a temporary projects root and
check the shared lookup by session id, and the copy of its rule that
handoff-extract-conversation.py keeps, against the same expected paths. The
text search cases run the real ripgrep and grep over a temporary tree, and
name a program that does not exist, or a script that exits silently with an
error status, to stand in for a missing or failing searcher.
"""

import importlib.util
import os
import shutil
import sys
import tempfile
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "claude_code_session_transcript_lookup_and_text_search_common",
    Path(__file__).with_name("claude-code-session-transcript-lookup-and-text-search-common.py"))
claude_code_session_transcript_lookup_and_text_search_common = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(claude_code_session_transcript_lookup_and_text_search_common)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def mangled_name(seat):
    return claude_code_session_transcript_lookup_and_text_search_common.project_directory_for_seat(
        Path(seat), Path("/proj")).name


def load(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
FOLDER_NAMING_CALLERS = [
    ("handoff_supervisor_for_folder_name_test",
     REPOSITORY_ROOT / "nc-systems" / "handoff" / "handoff-supervisor.py"),
    ("handoff_extract_conversation_for_folder_name_test",
     REPOSITORY_ROOT / "scripts" / "handoff-extract-conversation.py"),
]


def run_callers_case():
    seat = Path("/mangle-probe-root/agents/mangle_probe")
    for name, path in FOLDER_NAMING_CALLERS:
        found = load(name, path).project_directory_for_working_directory(seat).name
        check(f"{path.name} names an underscore seat's folder as Claude Code does (hard-coded)",
              found == "-mangle-probe-root-agents-mangle-probe", found)

    # One path per character class the rule treats: letters of both cases,
    # digits, "-", "_", ".", "/", space, and non-ASCII letters and symbols.
    character_class_seats = [
        "/mangle-probe-root/agents/MixedCase",
        "/mangle-probe-root/agents/seat2026",
        "/mangle-probe-root/agents/dashed-seat",
        "/mangle-probe-root/agents/under_score",
        "/mangle-probe-root/.claude/dotted.seat",
        "/mangle-probe-root/a/b/c/d",
        "/mangle-probe-root/agents/spaced seat",
        "/mangle-probe-root/agents/caf\u00e9-\u00df\u00f1",
        "/mangle-probe-root/agents/\u65e5\u672c\u8a9e\u2603+@~",
    ]
    with tempfile.TemporaryDirectory() as scratch:
        real_seat = Path(scratch).resolve() / "real" / "seat"
        real_seat.mkdir(parents=True)
        linked_seat = Path(scratch) / "link-to-seat"
        linked_seat.symlink_to(real_seat)
        seats = [Path(seat) for seat in character_class_seats] + [linked_seat]
        for name, path in FOLDER_NAMING_CALLERS:
            caller = load(name, path)
            disagreements = [
                (str(seat), caller.project_directory_for_working_directory(seat).name,
                 claude_code_session_transcript_lookup_and_text_search_common.project_directory_for_seat(seat, Path("/proj")).name)
                for seat in seats
                if caller.project_directory_for_working_directory(seat).name
                != claude_code_session_transcript_lookup_and_text_search_common.project_directory_for_seat(seat, Path("/proj")).name]
            check(f"{path.name} names every character class and a symlinked seat as the shared function does",
                  not disagreements, disagreements)


def run_all_cases():
    # Claude Code v2.1.233, probed with a real session: [^a-zA-Z0-9] becomes "-", underscores included.
    check("mangle: underscore becomes dash (hard-coded, harness v2.1.233)",
          mangled_name("/mangle-probe-root/agents/mangle_probe")
          == "-mangle-probe-root-agents-mangle-probe",
          mangled_name("/mangle-probe-root/agents/mangle_probe"))
    check("mangle: plain dashed path (hard-coded)",
          mangled_name("/mangle-probe-root/agents/plain-seat")
          == "-mangle-probe-root-agents-plain-seat",
          mangled_name("/mangle-probe-root/agents/plain-seat"))
    check("mangle: dot becomes dash (hard-coded)",
          mangled_name("/mangle-probe-root/.claude/b")
          == "-mangle-probe-root--claude-b",
          mangled_name("/mangle-probe-root/.claude/b"))
    projects_root = Path("/proj")
    check("the folder sits directly under the projects root",
          claude_code_session_transcript_lookup_and_text_search_common.project_directory_for_seat(
              Path("/mangle-probe-root/agents/x"), projects_root).parent == projects_root,
          claude_code_session_transcript_lookup_and_text_search_common.project_directory_for_seat(
              Path("/mangle-probe-root/agents/x"), projects_root))

    with tempfile.TemporaryDirectory() as scratch:
        real_seat = Path(scratch).resolve() / "real" / "seat"
        real_seat.mkdir(parents=True)
        linked_seat = Path(scratch) / "link-to-seat"
        linked_seat.symlink_to(real_seat)
        expected = "".join(c if c.isascii() and c.isalnum() else "-" for c in str(real_seat))
        found = claude_code_session_transcript_lookup_and_text_search_common.project_directory_for_seat(
            linked_seat, projects_root).name
        check("a seat path reached through a symlink is named after the folder the link points to",
              found == expected and "link-to-seat" not in found, (found, expected))


SESSION_ID = "11111111-2222-4333-8444-555555555555"


def write(path, text="{}\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def run_lookup_cases():
    extractor = load("handoff_extract_conversation_for_lookup_test",
                     REPOSITORY_ROOT / "scripts" / "handoff-extract-conversation.py")
    found_in_several = claude_code_session_transcript_lookup_and_text_search_common.ClaudeCodeSessionTranscriptFoundInSeveralProjectDirectoriesError
    with tempfile.TemporaryDirectory() as scratch:
        projects_root = Path(scratch) / "projects"
        seat = Path(scratch).resolve() / "seat"
        seat.mkdir()
        original_root = extractor.PROJECTS_ROOT
        extractor.PROJECTS_ROOT = projects_root
        try:
            def both(session_id):
                shared = claude_code_session_transcript_lookup_and_text_search_common.claude_code_session_transcript_paths_for_session_id_in_working_directory_project_directory_if_present_else_in_every_project_directory(
                    session_id, seat, projects_root)
                return shared, extractor.transcript_paths_for_session(session_id, seat)

            shared, copied = both(SESSION_ID)
            check("lookup: no transcript anywhere gives no paths, in the shared rule and the extractor's copy",
                  shared == [] and copied == [], (shared, copied))
            check("lookup: no transcript anywhere is None, not an error",
                  claude_code_session_transcript_lookup_and_text_search_common.claude_code_session_transcript_path_found_by_session_id(
                      SESSION_ID, seat, projects_root) is None)

            first = write(projects_root / "-elsewhere-one" / f"{SESSION_ID}.jsonl")
            shared, copied = both(SESSION_ID)
            check("lookup: a transcript in one other project directory is found, in both",
                  shared == [first] and copied == [first], (shared, copied))
            check("lookup: the one transcript is the session's",
                  claude_code_session_transcript_lookup_and_text_search_common.claude_code_session_transcript_path_found_by_session_id(
                      SESSION_ID, seat, projects_root) == first)

            second = write(projects_root / "-elsewhere-two" / f"{SESSION_ID}.jsonl")
            shared, copied = both(SESSION_ID)
            check("lookup: a transcript in two project directories gives both, sorted, in both",
                  shared == [first, second] and copied == [first, second], (shared, copied))
            try:
                claude_code_session_transcript_lookup_and_text_search_common.claude_code_session_transcript_path_found_by_session_id(
                    SESSION_ID, seat, projects_root)
                check("lookup: two project directories raise, with the paths as data", False, "no error raised")
            except found_in_several as error:
                check("lookup: two project directories raise, with the paths as data",
                      error.paths == [first, second] and str(first) in str(error), (error.paths, str(error)))

            keyed = write(claude_code_session_transcript_lookup_and_text_search_common.project_directory_for_seat(seat, projects_root)
                          / f"{SESSION_ID}.jsonl")
            shared, copied = both(SESSION_ID)
            check("lookup: the keyed path, when it exists, is the only path, in both",
                  shared == [keyed] and copied == [keyed], (shared, copied))
            check("lookup: the keyed path wins over copies in other project directories",
                  claude_code_session_transcript_lookup_and_text_search_common.claude_code_session_transcript_path_found_by_session_id(
                      SESSION_ID, seat, projects_root) == keyed)
        finally:
            extractor.PROJECTS_ROOT = original_root


def run_text_search_cases():
    search = claude_code_session_transcript_lookup_and_text_search_common.claude_code_session_transcripts_matching_any_pattern_ignoring_case
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch) / "projects"
        top = write(root / "-seat" / "a.jsonl", '{"text":"Kingfisher 2026"}\n')
        other = write(root / "-seat" / "b.jsonl", '{"text":"heron"}\n')
        write(root / "-seat" / "notes.txt", '{"text":"kingfisher"}\n')
        subagent = write(root / "-seat" / "a" / "subagents" / "agent-1.jsonl", '{"text":"kingfisher"}\n')
        missing_program = str(Path(scratch) / "no-such-program")
        silent_failure = write(Path(scratch) / "silent-failure", "#!/bin/sh\nexit 3\n")
        silent_failure.chmod(0o755)

        for label, ripgrep in (("ripgrep", "rg"), ("grep, ripgrep missing", missing_program)):
            if label == "ripgrep" and shutil.which("rg") is None:
                check("text search: ripgrep is installed for these cases", False, "rg is not on PATH")
                continue
            paths, problems = search([root], ["KINGFISHER"], include_subagents=False, ripgrep_program=ripgrep)
            check(f"text search ({label}): ignores case and skips subagent transcripts and other files",
                  paths == [top] and problems == [], (paths, problems))
            paths, problems = search([root], ["kingfisher"], include_subagents=True, ripgrep_program=ripgrep)
            check(f"text search ({label}): include_subagents lists subagent transcripts too",
                  paths == sorted([top, subagent]) and problems == [], (paths, problems))
            paths, problems = search([root], [r"kingfisher \w+", "heron"], include_subagents=False,
                                     ripgrep_program=ripgrep)
            check(f"text search ({label}): any pattern matches",
                  paths == sorted([top, other]) and problems == [], (paths, problems))
            paths, problems = search([root], ["osprey"], include_subagents=True, ripgrep_program=ripgrep)
            check(f"text search ({label}): no match is no paths and no problem",
                  paths == [] and problems == [], (paths, problems))
            if os.geteuid() != 0:
                unreadable = write(root / "-seat" / "unreadable.jsonl", "kingfisher\n")
                unreadable.chmod(0)
                try:
                    paths, problems = search([root], ["kingfisher"], include_subagents=False,
                                             ripgrep_program=ripgrep)
                finally:
                    unreadable.chmod(0o600)
                    unreadable.unlink()
                check(f"text search ({label}): an unreadable transcript is a problem that names it",
                      paths == [top] and len(problems) == 1 and "unreadable.jsonl" in problems[0],
                      (paths, problems))

        if shutil.which("rg") is not None:
            paths, problems = search([root], [r"kingfisher \d+"], include_subagents=False)
            check("text search (ripgrep): a backslash-d is read as a number",
                  paths == [top] and problems == [], (paths, problems))
        arabic_digits = write(root / "-seat" / "c.jsonl", '{"text":"count ١٢٣"}\n')
        for pattern in (r"count \d+", "count ١"):
            paths, problems = search([root], [pattern], include_subagents=False, ripgrep_program=missing_program)
            check(f"text search (grep, ripgrep missing): {pattern!r}, which grep could read otherwise than "
                  f"ripgrep, is a problem that names it, not an empty success",
                  paths == [] and len(problems) == 1 and repr(pattern) in problems[0]
                  and "no transcript was searched" in problems[0], (paths, problems))
        arabic_digits.unlink()

        paths, problems = search([root], ["kingfisher"], include_subagents=False,
                                 ripgrep_program=missing_program, grep_program=missing_program)
        check("text search: neither ripgrep nor grep installed is a problem, not an empty success",
              paths == [] and len(problems) == 1 and "no transcript was searched" in problems[0],
              (paths, problems))
        paths, problems = search([root], ["kingfisher"], include_subagents=False,
                                 ripgrep_program=str(silent_failure))
        check("text search: a searcher that fails and says nothing is a problem",
              problems == ["ripgrep exited 3 and said nothing"], (paths, problems))


def run_raw_json_prefilter_cases():
    prefilter = claude_code_session_transcript_lookup_and_text_search_common.claude_code_session_transcript_raw_json_prefilter_pattern
    for pattern, expected in (("^approve$", "approve"), ("^approve it$", "approve [iI\u0130\u0131]t"),
                              ("Kelvin", "[kK\u212a]elv[iI\u0130\u0131]n"), ("yes", "ye[sS\u017f]"),
                              ("a-b, c/d: e#f", "a-b, c/d: e#f"),
                              (r"by x\w", None), (r"walk \d+", None), ("walk|item", None), ("a+", None),
                              ("\u0130tem", None), ("(?i)approve", None), ("tab\there", None),
                              ("a.b", None), (r"line\nbreak", None), ('say "yes"', None), ("[ab]c", None)):
        check(f"raw JSON prefilter: {pattern!r} gives {expected!r}", prefilter(pattern) == expected,
              prefilter(pattern))


if __name__ == "__main__":
    run_all_cases()
    run_callers_case()
    run_lookup_cases()
    run_text_search_cases()
    run_raw_json_prefilter_cases()
    print()
    if failures:
        print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
        sys.exit(1)
    print("all cases passed")
