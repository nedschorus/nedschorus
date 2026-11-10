#!/usr/bin/env python3
"""Define shared cold-read-record names and paths, and the one rewrite both cold reads apply to the copy a reviewer reads."""

import datetime
import importlib.util
import json
import os
import pathlib
import re

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
# Records are temporary checkout logs for shipping to ned-box; never commit them.
RECORDS_DIRECTORY_NAME = "cold-read-records"
RECORDS_DIR = REPO_ROOT / RECORDS_DIRECTORY_NAME
FROZEN_TARGET_DIRECTORY_NAME = "target"
RECORD_DATE_PATTERN = r"\d{4}-\d{2}-\d{2}"
# The files a cold-read-record holds under these names. A record written
# before they took the cold-read- prefix holds them under the name each maps
# to in COLD_READ_RECORD_FILE_NAME_TO_ITS_NAME_BEFORE_COLD_READ_PREFIX; readers find either with
# cold_read_record_file_path_prefixed_name_else_name_before_prefix.
COLD_READ_FAST_READ_REPORT_FILE_NAME = "cold-read-fast-read.md"
COLD_READ_TRIAGE_FILE_NAME = "cold-read-triage.md"
COLD_READ_REFERENCE_CHECK_REPORT_FILE_NAME = "cold-read-reference-check.md"
COLD_READ_RECORD_FILE_NAME_TO_ITS_NAME_BEFORE_COLD_READ_PREFIX = {
    COLD_READ_FAST_READ_REPORT_FILE_NAME: "fast-read.md",
    COLD_READ_TRIAGE_FILE_NAME: "triage.md",
    COLD_READ_REFERENCE_CHECK_REPORT_FILE_NAME: "reference-check.md",
}
# A finished read leaves one of these at the top of its record; a read that
# failed after freezing its target leaves target/ and no report. Older records
# prefix each report with "<record name>--", and older fast reads named the
# report "<name>-fast-read.md" or "fast-read.md".
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
COLD_READ_FAST_READ_REPORT_AGENT_SESSION_ID_FILE_SUFFIX = ".agent-session.json"
AGENT_SESSION_ID_ENVIRONMENT_VARIABLE = "CLAUDE_CODE_SESSION_ID"


def cold_read_record_file_name_prefixed_name_else_name_before_prefix(
    record_dir: pathlib.Path, name: str,
) -> str:
    """The name record_dir holds the file called name under: name itself, or
    its name before the cold-read- prefix when only that file is there."""
    old_name = COLD_READ_RECORD_FILE_NAME_TO_ITS_NAME_BEFORE_COLD_READ_PREFIX[name]
    if not (record_dir / name).is_file() and (record_dir / old_name).is_file():
        return old_name
    return name


def cold_read_record_file_path_prefixed_name_else_name_before_prefix(
    record_dir: pathlib.Path, name: str,
) -> pathlib.Path:
    """record_dir's file called name, under whichever of its two names it holds; name when it holds neither."""
    return record_dir / cold_read_record_file_name_prefixed_name_else_name_before_prefix(record_dir, name)


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


def cold_read_fast_read_report_agent_session_id_file_path(report: pathlib.Path) -> pathlib.Path:
    """The file beside a finished fast read's report naming the agent-session that ran it."""
    return report.with_name(report.name + COLD_READ_FAST_READ_REPORT_AGENT_SESSION_ID_FILE_SUFFIX)


def cold_read_fast_read_report_agent_session_id_file_write_or_remove(report: pathlib.Path, target: pathlib.Path, session_id) -> None:
    """Record which agent-session read target, an absolute resolved path, into report.

    Without a session ID the file is removed instead: a walk draft's
    suggestions file is rewritten in place, and the file beside it must not
    go on naming the agent-session of an earlier read.
    """
    if not session_id:
        cold_read_fast_read_report_agent_session_id_file_path(report).unlink(missing_ok=True)
        return
    cold_read_fast_read_report_agent_session_id_file_path(report).write_text(json.dumps(
        {"agent_session_id": session_id, "target": str(target)}) + "\n",
        encoding="utf-8")


def cold_read_fast_read_target_path_if_run_by_given_agent_session(report: pathlib.Path, session_id):
    """The resolved target report's fast read was of, when agent-session session_id ran it; else None.

    A report with no agent-session file, as older reads and reads run without
    the variable leave, returns None. A file that is not the JSON object
    cold_read_fast_read_report_agent_session_id_file_write_or_remove writes raises ValueError, and one that
    cannot be read raises OSError, for the caller to report.
    """
    path = cold_read_fast_read_report_agent_session_id_file_path(report)
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return None
    try:
        recorded = json.loads(data.decode("utf-8"))
    except ValueError:
        recorded = None
    if (not isinstance(recorded, dict) or not isinstance(recorded.get("agent_session_id"), str)
            or not isinstance(recorded.get("target"), str)):
        raise ValueError(f"{path} is not an agent-session record")
    if recorded["agent_session_id"] != session_id:
        return None
    return pathlib.Path(recorded["target"])


def record_directory_name_for_target(
    target: pathlib.Path, now: datetime.datetime,
) -> str:
    return f"{record_name_for_target(target)}-{now.strftime('%Y-%m-%d')}"


def fresh_record_directory(base: pathlib.Path, names_taken_in_log_store) -> pathlib.Path:
    """Return the first of base, base-2, base-3 ... that is neither a path on
    disk, a symlink included, nor one of names_taken_in_log_store, the record directory names the
    log-store holds, without creating the directory."""
    # Each read needs its own directory so a same-day rerun cannot overwrite earlier reports.
    # A name free only on disk can be another checkout's record in the store,
    # and shipping would then put two reads in one record.
    record_directory = base
    suffix = 2
    # lexists, not exists: a dangling symlink or a symlink loop is false for exists(), and mkdir on it fails.
    while os.path.lexists(record_directory) or record_directory.name in names_taken_in_log_store:
        record_directory = base.with_name(f"{base.name}-{suffix}")
        suffix += 1
    return record_directory


def cold_read_record_directory_at_first_free_name_created_atomically(base: pathlib.Path, names_taken_in_log_store) -> pathlib.Path:
    """Create and return the directory fresh_record_directory names; when
    another run creates that name first, take the next free one, so two runs
    started at once never share a record directory."""
    # Choosing a free name and creating it later lets two runs choose the same
    # name; mkdir without exist_ok is the atomic claim.
    base.parent.mkdir(parents=True, exist_ok=True)
    while True:
        record_directory = fresh_record_directory(base, names_taken_in_log_store)
        try:
            record_directory.mkdir()
        except FileExistsError:
            continue
        return record_directory


_ned_box_home_spec = importlib.util.spec_from_file_location(
    "ned_box_home_directory_and_its_mac_mount_point_path_constants_common",
    REPO_ROOT / "nc-systems" / "general-tools"
    / "ned-box-home-directory-and-its-mac-mount-point-path-constants-common.py")
_ned_box_home = importlib.util.module_from_spec(_ned_box_home_spec)
_ned_box_home_spec.loader.exec_module(_ned_box_home)
MAC_MOUNT_OF_NED_BOX_HOME_DIRECTORY = _ned_box_home.MAC_MOUNT_OF_NED_BOX_HOME
MAC_MOUNT_OF_NED_BOX_HOME_LINK_PREFIX = f"file://{MAC_MOUNT_OF_NED_BOX_HOME_DIRECTORY}/"
NED_BOX_HOME_PATH_PREFIX = f"{_ned_box_home.NED_BOX_HOME}/"
# Names the directory probed in place of MAC_MOUNT_OF_NED_BOX_HOME_DIRECTORY,
# so a test can run either machine's case on either machine.
MAC_MOUNT_OF_NED_BOX_HOME_OVERRIDE_VARIABLE = (
    "COLD_READ_MAC_MOUNT_OF_NED_BOX_HOME_OVERRIDE")


def record_directory_being_written_lock_pass_fds_for_child_writers(record_dir: pathlib.Path) -> tuple:
    """The pass_fds for subprocess.Popen of a child that writes into record_dir: every descriptor this
    process has open on record_dir, the lock it took or the one it was passed by the writer that started
    it. The child then holds the being-written lock too, so the lock stays held until every writer down
    the chain has exited. Empty when this process has no descriptor open on record_dir."""
    record = os.stat(record_dir)
    descriptors = []
    # /dev/fd lists this process's open descriptors on Linux and on macOS alike.
    for name in os.listdir("/dev/fd"):
        try:
            opened = os.fstat(int(name))
        except OSError:
            continue  # the descriptor listdir itself used, closed by now
        if (opened.st_dev, opened.st_ino) == (record.st_dev, record.st_ino):
            descriptors.append(int(name))
    return tuple(sorted(descriptors))


def text_with_mac_mount_of_ned_box_home_file_links_rewritten_as_ned_box_home_paths(text: str) -> str:
    """Return text with each file:///Volumes/nedhome/ link prefix replaced by /home/nedlern/.

    A bare /Volumes/nedhome/ path without file:// is left alone. This is the
    rewrite on every machine; a program that compares a frozen copy with its
    document applies it whichever machine made the copy.
    """
    return text.replace(MAC_MOUNT_OF_NED_BOX_HOME_LINK_PREFIX, NED_BOX_HOME_PATH_PREFIX)


def cold_read_reviewer_copy_text_with_mac_mount_of_ned_box_home_file_links_rewritten_as_ned_box_home_paths_where_mac_mount_absent(
        text: str) -> str:
    """Return the text a reviewer on this machine reads, for a cold read run here.

    Reviewers run on the machine that runs the cold read. Where the Mac's mount
    of ned-box's home is not a directory, as on ned-box, a file:///Volumes/nedhome/
    link does not open, so it is rewritten to the /home/nedlern/ path that does;
    where the mount is a directory, as on the Mac, the text is returned unchanged.
    Apply it only to the copy a reviewer reads, never to the user's document.
    """
    mount = (os.environ.get(MAC_MOUNT_OF_NED_BOX_HOME_OVERRIDE_VARIABLE)
             or MAC_MOUNT_OF_NED_BOX_HOME_DIRECTORY)
    if pathlib.Path(mount).is_dir():
        return text
    return text_with_mac_mount_of_ned_box_home_file_links_rewritten_as_ned_box_home_paths(text)
