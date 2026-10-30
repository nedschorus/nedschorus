#!/usr/bin/env python3
"""Say whether a file is a log, by its log suffix and its extension.

docs/nedschorus-wiki/nedschorus-file-naming-and-location-standards.md, section
"Filename suffixes", names six log suffixes and two extension lists: a file
whose name ends with a log suffix just before its extension is a log when the
extension is on the first list, and not a log when it is on the second. A
suffixed file whose extension neither list names is unlisted. A file without a
log suffix is not a log. The page's two exceptions, which say where a log may
still be kept in git, are not decided here.

nc-systems/general-tools/tests/log-suffix-and-extension-file-classify-common-test.py
fails when these constants and the page's lists differ.

Load it by path, under the snake_case form of its file name:

    spec = importlib.util.spec_from_file_location(
        "log_suffix_and_extension_file_classify_common", <path>)
"""

from pathlib import PurePosixPath

LOG_SUFFIXES = ("-log", "-report", "-capture", "-draft", "-candidate", "-analysis")
LOG_SUFFIX_LOG_EXTENSIONS = (".md", ".txt", ".log", ".out", ".err", ".json", ".jsonl", ".patch")
LOG_SUFFIX_NOT_A_LOG_EXTENSIONS = (
    ".py", ".sh", ".js", ".mjs", ".cjs", ".ts", ".cts", ".yml", ".yaml", ".toml", ".png", ".svg")

LOG = "log"
NOT_A_LOG = "not a log"
UNLISTED = "unlisted"


def log_suffix_and_extension_file_kind(path):
    """Return LOG, NOT_A_LOG or UNLISTED for `path`, a str or path, by its file name alone.

    The extension is the part from the name's last dot; a name with no dot after
    its first character, such as `run-log` or `.gitignore`, has none, and a
    suffixed name without an extension is UNLISTED. Extensions are compared as
    written, so `.MD` is UNLISTED.
    """
    name = PurePosixPath(path).name
    extension = PurePosixPath(name).suffix
    stem = name[:len(name) - len(extension)]
    if not stem.endswith(LOG_SUFFIXES):
        return NOT_A_LOG
    if extension in LOG_SUFFIX_LOG_EXTENSIONS:
        return LOG
    if extension in LOG_SUFFIX_NOT_A_LOG_EXTENSIONS:
        return NOT_A_LOG
    return UNLISTED
