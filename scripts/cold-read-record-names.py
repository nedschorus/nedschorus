#!/usr/bin/env python3
"""What a cold-read-record is called and where it lives -- defined once.

Four programs create or find cold-read-records: scripts/cold-read-grid.py,
scripts/cold-read-fast-read.py, scripts/cold-read-restater-judge-runner.py
and scripts/cold-read-record-ship.py. Each held its own `RECORDS_DIR`, two
held their own `FROZEN_TARGET_DIRECTORY_NAME`, and two carried
byte-identical copies of the naming and same-day-collision rules. A rename of
the records directory had seven places to find, and nothing failed when it
missed one (user-ruled 2026-09-19, walk
file-naming-and-location-standards-cold-read-findings, item 4: reduce each
repeated name to one definition).

The copies had a stated reason, in scripts/cold-read-fast-read.py: the rule
was "restated here rather than imported because the cold-read-grid is a
program, not a module". That was true of every candidate home, since all four
are programs. This file answers it by being a module and nothing else, the
way scripts/cold-read-cell-common.py already serves the cold-read-cells.

It is imported, never run. A program loads it the way the cold-read-cells
load their shared module:

    _names_spec = importlib.util.spec_from_file_location(
        "cold_read_record_names",
        pathlib.Path(__file__).with_name("cold-read-record-names.py"))
    record_names = importlib.util.module_from_spec(_names_spec)
    _names_spec.loader.exec_module(record_names)

Run scripts/cold-read-record-names-test.py to check that no program has gone
back to keeping its own copy.
"""

import datetime
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
# Where cold-read-records are written in a checkout, before the shipper
# copies them to the log-store on ned-box. Never entered into git
# (user-ruled 2026-09-07: cold-read-records are logs, not system).
RECORDS_DIR = REPO_ROOT / "cold-read-records"
# Where the cold-read-target's bytes are frozen inside the
# cold-read-record: under this name, at the cold-read-target's own
# repository path, so a reader of an old cold-read-record sees both the
# exact text reviewed and where it lived.
FROZEN_TARGET_DIRECTORY_NAME = "target"


def record_name_for_target(target: pathlib.Path) -> str:
    """The cold-read-target's part of a cold-read-record name: its file stem,
    except that a file whose stem is exactly `SKILL` -- every skill in this
    project is `.claude/skills/<name>/SKILL.md` -- is `SKILL-<skill name>`,
    the name being its directory's."""
    if target.stem == "SKILL" and target.parent.name:
        return f"SKILL-{target.parent.name}"
    return target.stem


def record_directory_name_for_target(
    target: pathlib.Path, now: datetime.datetime,
) -> str:
    """`<document part>-<YYYY-MM-DD>`, before any -2, -3 suffix. Only the
    date of the clock reading is used."""
    return f"{record_name_for_target(target)}-{now.strftime('%Y-%m-%d')}"


def fresh_record_directory(base: pathlib.Path) -> pathlib.Path:
    """`base`, or the first of `base-2`, `base-3`, ... that is not taken.

    Nothing is created here, so a caller that only needs a free name can use
    it without leaving a directory behind; the cold-read-grid creates what
    this returns.

    Two frozen cold-read-targets never share a directory (user-ruled
    2026-09-07, with the frozen cold-read-target), so a second read of one
    document on one day takes its own: a cold-read-fast-read after a
    cold-read-full-run on the same cold-read-target that day, or after an
    earlier cold-read-fast-read of a revised draft, each get their own
    record. The cold-read-restater-judge-runner applies the same rule to its
    own date-first names, for the same reason: a restater judged twice in one
    day landed both judgings on one name, and the second deleted the first's
    reports.
    """
    record_directory = base
    suffix = 2
    while record_directory.exists():
        record_directory = base.with_name(f"{base.name}-{suffix}")
        suffix += 1
    return record_directory
