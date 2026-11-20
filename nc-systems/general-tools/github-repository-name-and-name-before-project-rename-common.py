#!/usr/bin/env python3
"""The project's GitHub repository name, and the name it had before the project rename, for code that reads GitHub links.

GitHub redirects the old name, and text written before the rename still holds it: GHI-MD mirrors, merged pull
request descriptions, transcripts and walk minutes. A reader that compares a repository name it reads from such
text with the project's name compares normalize_repository_name_reading_name_before_project_rename_as_current() of each, or matches links with REPOSITORY_NAME_OR_NAME_BEFORE_PROJECT_RENAME_PATTERN,
so that both names count as this repository.
"""

import re

REPOSITORY = "nedsnodes/nedsnodes"
OLD_REPOSITORY = "nedschorus/nedschorus"
REPOSITORY_NAMES = (REPOSITORY, OLD_REPOSITORY)
# A regular-expression group matching either name, for building link patterns; match it case-insensitively.
REPOSITORY_NAME_OR_NAME_BEFORE_PROJECT_RENAME_PATTERN = "(?:" + "|".join(re.escape(name) for name in REPOSITORY_NAMES) + ")"

_OLD_REPOSITORY_LINK = re.compile(r"(?<=github\.com/)" + re.escape(OLD_REPOSITORY) + r"(?=[/#?)\s\"'>]|$)",
                                  re.IGNORECASE)


def normalize_repository_name_reading_name_before_project_rename_as_current(name):
    """`name`, an "<owner>/<repo>", in lower case, with the old name read as the project's name."""
    lowered = name.lower()
    return REPOSITORY.lower() if lowered == OLD_REPOSITORY.lower() else lowered


def rewrite_github_links_from_repository_name_before_project_rename(text):
    """`text` with each github.com link to the old name rewritten to the project's name."""
    return _OLD_REPOSITORY_LINK.sub(REPOSITORY, text)
