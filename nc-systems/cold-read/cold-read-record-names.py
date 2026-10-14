#!/usr/bin/env python3
"""Define shared cold-read-record names and paths."""

import datetime
import json
import pathlib
import re

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
# Records are temporary checkout logs for shipping to ned-box; never commit them.
RECORDS_DIRECTORY_NAME = "cold-read-records"
RECORDS_DIR = REPO_ROOT / RECORDS_DIRECTORY_NAME
FROZEN_TARGET_DIRECTORY_NAME = "target"
RECORD_DATE_PATTERN = r"\d{4}-\d{2}-\d{2}"
# A finished read leaves one of these at the top of its record; a read that
# failed after freezing its target leaves target/ and no report. Older records
# prefix each report with "<record name>--", and older fast reads named the
# report "<name>-fast-read.md".
COMPLETED_REPORT_NAME_PATTERN = re.compile(
    r"^(?:.*--)?(?:(?:claude|codex|agy|gemini)-.*|(?:.*-)?fast-read)\.md$")
# The marked copy of the cold-read-target that a fast read writes into its
# record before its cell runs; for a target whose stem starts claude-, codex-,
# agy- or gemini-, its name would otherwise match the pattern above.
SENTENCE_ID_MARKED_COPY_SUFFIX = "-with-sentence-ids.md"
GENERATED_INPUT_COPY_SUFFIXES = (SENTENCE_ID_MARKED_COPY_SUFFIX,)
# A finished fast read writes <report name> + this suffix beside its report,
# naming the agent-session that ran it, so a Stop hook can tell its own
# session's reads from other sessions'. Claude Code sets the variable in the
# Bash environment; a subagent's Bash sees its parent's ID.
FAST_READ_AGENT_SESSION_FILE_SUFFIX = ".agent-session.json"
AGENT_SESSION_ID_ENVIRONMENT_VARIABLE = "CLAUDE_CODE_SESSION_ID"


def frozen_target_path(
    target: pathlib.Path, record_dir: pathlib.Path,
) -> pathlib.Path:
    """Return the frozen path under record_dir/target, preserving repository or outside absolute structure."""
    # Resolve symlinks before making paths relative so /tmp and /private/tmp identify the same target.
    resolved = target.resolve()
    try:
        relative = resolved.relative_to(REPO_ROOT)
    except ValueError:
        relative = pathlib.Path(*resolved.parts[1:])
    return record_dir / FROZEN_TARGET_DIRECTORY_NAME / relative


def record_name_for_target(target: pathlib.Path) -> str:
    """Return the target stem, qualifying SKILL with its parent directory name."""
    if target.stem == "SKILL" and target.parent.name:
        return f"SKILL-{target.parent.name}"
    return target.stem


def record_directory_name_pattern_for_target(target: pathlib.Path) -> "re.Pattern[str]":
    """Match every record directory a read of target may have made: the
    current <name>-<date> form, the older <date>-<name> form still in the
    log-store, each with fresh_record_directory's optional -N."""
    name = re.escape(record_name_for_target(target))
    return re.compile(
        rf"^(?:{name}-{RECORD_DATE_PATTERN}|{RECORD_DATE_PATTERN}-{name})(?:-\d+)?$")


def frozen_target_candidate_paths(
    target: pathlib.Path, record_dir: pathlib.Path, checkout_top,
) -> list:
    """The paths frozen_target_path may have frozen target at when the read
    ran from target's own checkout (relative to checkout_top) or from another
    checkout (absolute, without the leading slash)."""
    resolved = target.resolve()
    frozen_directory = record_dir / FROZEN_TARGET_DIRECTORY_NAME
    candidates = []
    if checkout_top is not None:
        try:
            candidates.append(frozen_directory / resolved.relative_to(checkout_top))
        except ValueError:
            pass
    candidates.append(frozen_directory / pathlib.Path(*resolved.parts[1:]))
    return candidates


def record_holds_completed_report(record_dir: pathlib.Path) -> bool:
    """Whether a read finished into record_dir, rather than failing after it froze its target."""
    # An unreadable record directory raises OSError to the caller, which reports it as a fault.
    return any(entry.is_file() and COMPLETED_REPORT_NAME_PATTERN.match(entry.name)
               and not entry.name.endswith(GENERATED_INPUT_COPY_SUFFIXES)
               for entry in record_dir.iterdir())


def fast_read_agent_session_path(report: pathlib.Path) -> pathlib.Path:
    """The file beside a finished fast read's report naming the agent-session that ran it."""
    return report.with_name(report.name + FAST_READ_AGENT_SESSION_FILE_SUFFIX)


def write_fast_read_agent_session(report: pathlib.Path, target: pathlib.Path, session_id) -> None:
    """Record which agent-session read target, an absolute resolved path, into report.

    Without a session ID the file is removed instead: a walk draft's
    suggestions file is rewritten in place, and the file beside it must not
    go on naming the agent-session of an earlier read.
    """
    if not session_id:
        fast_read_agent_session_path(report).unlink(missing_ok=True)
        return
    fast_read_agent_session_path(report).write_text(json.dumps(
        {"agent_session_id": session_id, "target": str(target)}) + "\n",
        encoding="utf-8")


def fast_read_agent_session_read_target(report: pathlib.Path, session_id):
    """The resolved target report's fast read was of, when agent-session session_id ran it; else None.

    A report with no agent-session file, as older reads and reads run without
    the variable leave, returns None. A file that is not the JSON object
    write_fast_read_agent_session writes raises ValueError, and one that
    cannot be read raises OSError, for the caller to report.
    """
    try:
        text = fast_read_agent_session_path(report).read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    recorded = json.loads(text)
    if (not isinstance(recorded, dict) or not isinstance(recorded.get("agent_session_id"), str)
            or not isinstance(recorded.get("target"), str)):
        raise ValueError(f"{fast_read_agent_session_path(report)} is not an agent-session record")
    if recorded["agent_session_id"] != session_id:
        return None
    return pathlib.Path(recorded["target"])


def record_directory_name_for_target(
    target: pathlib.Path, now: datetime.datetime,
) -> str:
    return f"{record_name_for_target(target)}-{now.strftime('%Y-%m-%d')}"


def fresh_record_directory(base: pathlib.Path) -> pathlib.Path:
    """Return an unused base or numbered suffix without creating the directory."""
    # Each read needs its own directory so a same-day rerun cannot overwrite earlier reports.
    record_directory = base
    suffix = 2
    while record_directory.exists():
        record_directory = base.with_name(f"{base.name}-{suffix}")
        suffix += 1
    return record_directory
