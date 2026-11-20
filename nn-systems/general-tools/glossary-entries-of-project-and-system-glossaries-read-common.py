#!/usr/bin/env python3
"""Read the entries of the project glossary and of every system glossary.

The glossaries are the project glossary,
docs/nedschorus-wiki/nedschorus-glossary.md, and each system glossary it names
above its entries; scripts/system-glossaries-listed-on-the-project-glossary-test.py
holds that list to every `*-glossary.md` file git tracks. No git command
runs, so the glossaries are read in a checkout whose git cannot answer. An entry is a line beginning
`- **term**`. One entry line can name several terms: `- **a**, **b** — ...`
names a and b, and `- **code-prompt-code (aka CPC)** — ...` names
code-prompt-code and CPC. Only bold names before the entry's first ` — `
are terms; bold words in the definition are not.

glossary_entries_of_checkout raises GlossaryFilesUnreadable when the project
glossary, or a system glossary it names, cannot be read, so a caller never
takes "no glossary was read" for "the glossaries list nothing".

Load it by path, under the snake_case form of its file name:

    spec = importlib.util.spec_from_file_location(
        "glossary_entries_of_project_and_system_glossaries_read_common", <path>)
"""

import posixpath
import re
import typing
from pathlib import Path

GLOSSARY_FILE_SUFFIX = "-glossary.md"
PROJECT_GLOSSARY_PATH = "docs/nedschorus-wiki/nedschorus-glossary.md"
PROJECT_GLOSSARY_DIRECTORY = posixpath.dirname(PROJECT_GLOSSARY_PATH)
GLOSSARY_PATH_PATTERN = re.compile(r"[\w./-]+" + re.escape(GLOSSARY_FILE_SUFFIX))
GLOSSARY_ENTRY_PATTERN = re.compile(r"^- \*\*([^*]+)\*\*", re.M)
GLOSSARY_ENTRY_LINE_PATTERN = re.compile(r"^- \*\*.*$", re.M)
BOLD_NAME_PATTERN = re.compile(r"\*\*([^*]+)\*\*")
ALSO_KNOWN_AS_PATTERN = re.compile(r"^(.*?)\s*\(aka\s+([^)]+)\)\s*$")
ENTRY_HEAD_END = " — "


class GlossaryEntry(typing.NamedTuple):
    """One term a glossary lists, the glossary's repository path, and its whole entry line."""

    term: str
    glossary_path: str
    entry_line: str


class GlossaryFilesUnreadable(Exception):
    """The project glossary, or a system glossary it names, could not be read."""


def glossary_terms(text):
    """The first bold name of each entry in text."""
    return {match.group(1).strip() for match in GLOSSARY_ENTRY_PATTERN.finditer(text)}


def glossary_entries_in_text(text, glossary_path):
    """Every term each entry line of text names, as GlossaryEntry tuples, in page order."""
    entries = []
    for line_match in GLOSSARY_ENTRY_LINE_PATTERN.finditer(text):
        line = line_match.group(0).rstrip()
        head = line.split(ENTRY_HEAD_END, 1)[0]
        for bold in BOLD_NAME_PATTERN.findall(head):
            also_known_as = ALSO_KNOWN_AS_PATTERN.match(bold.strip())
            names = ([also_known_as.group(1), also_known_as.group(2)] if also_known_as
                     else [bold])
            entries += [GlossaryEntry(name.strip(), glossary_path, line)
                        for name in names if name.strip()]
    return entries


def system_glossary_paths_named_on_project_glossary(project_glossary_text):
    """The repository paths of the `*-glossary.md` files the project glossary names above its entries."""
    first_entry = GLOSSARY_ENTRY_LINE_PATTERN.search(project_glossary_text)
    head = project_glossary_text[:first_entry.start() if first_entry else len(project_glossary_text)]
    paths = []
    for written in GLOSSARY_PATH_PATTERN.findall(head):
        path = (posixpath.normpath(posixpath.join(PROJECT_GLOSSARY_DIRECTORY, written))
                if written.startswith("../") else written.lstrip("/"))
        if path != PROJECT_GLOSSARY_PATH and path not in paths:
            paths.append(path)
    return paths


def glossary_entries_of_checkout(checkout):
    """Every GlossaryEntry of the project glossary and of each system glossary it names."""
    checkout = Path(checkout)
    try:
        project_text = (checkout / PROJECT_GLOSSARY_PATH).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise GlossaryFilesUnreadable(
            f"could not read the project glossary {checkout / PROJECT_GLOSSARY_PATH}: {error}")
    entries = glossary_entries_in_text(project_text, PROJECT_GLOSSARY_PATH)
    for path in system_glossary_paths_named_on_project_glossary(project_text):
        try:
            text = (checkout / path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            raise GlossaryFilesUnreadable(
                f"could not read {checkout / path}, a system glossary the project glossary "
                f"names: {error}")
        entries += glossary_entries_in_text(text, path)
    return entries
