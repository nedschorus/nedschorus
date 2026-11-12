#!/usr/bin/env python3
"""Where an nc-architecture-overview lives, which code it describes, and the commit its last line names.

docs/nedschorus-wiki/nedschorus-how-to-write-an-architecture-overview.md defines
both; programs that find an overview or read its **Checked against:** line
import them from here, so a change to the page is made in one place in code.
"""
import re

PATH_TEMPLATE = "docs/nedschorus-wiki/nedschorus-{system}-architecture-overview.md"

PROJECT_ARCHITECTURE_OVERVIEW_PATH = "docs/nedschorus-wiki/nedschorus-project-architecture-overview.md"

SUBSYSTEM_ARCHITECTURE_OVERVIEW_PATH_TEMPLATE = "docs/nedschorus-wiki/nedschorus-{system}-{subsystem}-architecture-overview.md"

_OVERVIEW_NAME = re.compile(
    re.escape(PATH_TEMPLATE).replace(re.escape("{system}"), r"(?P<name>[^/]+)"))

CHECKED_AGAINST_PREFIX = "**Checked against:** commit ["

CHECKED_AGAINST_LINE_TEMPLATE = (
    CHECKED_AGAINST_PREFIX
    + "{commit}](https://github.com/nedschorus/nedschorus/commit/{commit})")

_CHECKED_AGAINST_COMMIT = re.compile(
    re.escape(CHECKED_AGAINST_PREFIX) + r"([0-9a-f]{7,40})\]")


def checked_against_commit(text: str):
    """Return the commit the overview's last non-blank line names, or None."""
    # Only the last line counts: the page makes it the overview's one commit, and a quoted example elsewhere must not.
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return None
    named = _CHECKED_AGAINST_COMMIT.match(lines[-1])
    return named.group(1) if named else None


def architecture_overview_level_and_described_code_directory_from_path(path: str, is_directory):
    """Return ("project", None), ("system", "nc-systems/<system>") or
    ("subsystem", "nc-systems/<system>/<subsystem>") for a path the page gives an
    overview, or None for any other path.

    is_directory(repository path) says whether that directory exists in the tree
    the caller reads: a system or subsystem name may itself hold hyphens, so only
    the tree tells nedschorus-<system>-<subsystem> from nedschorus-<system>."""
    if path == PROJECT_ARCHITECTURE_OVERVIEW_PATH:
        return ("project", None)
    named = _OVERVIEW_NAME.fullmatch(path)
    # The template alone also matches nedschorus-how-to-write-an-architecture-overview.md.
    if named is None:
        return None
    name = named.group("name")
    if is_directory(f"nc-systems/{name}"):
        return ("system", f"nc-systems/{name}")
    for hyphen in (index for index, character in enumerate(name) if character == "-"):
        directory = f"nc-systems/{name[:hyphen]}/{name[hyphen + 1:]}"
        if is_directory(directory):
            return ("subsystem", directory)
    return None
