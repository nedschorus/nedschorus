#!/usr/bin/env python3
"""Every system glossary in the checkout is listed on the project glossary,
and every glossary the project glossary lists exists.

The project glossary, docs/nedschorus-wiki/nedschorus-glossary.md, carries a
paragraph above its entries naming each system glossary, so a reader of that
one page sees the whole vocabulary of the project and knows where the rest of
it lives. The user ruled the paragraph on 2026-09-22, at item 3 of the walk
skills-glossary-2026-09-21-2, preferring it to two mechanisms the walk had
reached for first: a clause in six reviewer prompts and skills telling a
reviewer to read the system glossaries, and a rule that every document using
a system-term cite its glossary by path. His words: "I have a simpler
proposal. Include links in the project glossary all the system glossaries. At
least for now, our glossaries are small, and there is some advantage to
seeing all of them."

THIS TEST EXISTS BECAUSE HE ASKED FOR IT, in the same breath: "I think we
need to add something to ensure that future system glossaries get added to
the project glossary." A list nothing checks is right on the day it is
written and wrong the first time a system is added, and this project has one
instance of exactly that: the clause "and any system glossary that page
names" was approved on 2026-09-21 and was still unbuilt a day later, in all
six files, because nothing failed while it was missing.

WHAT COUNTS AS A SYSTEM GLOSSARY: a file whose name ends `-glossary.md`,
anywhere in the checkout, other than the project glossary itself. That is the
naming the two existing ones use -- `.claude/skills/skills-glossary.md` and
`docs/design-to-main/design-to-main-glossary.md`. A system that names its
glossary otherwise is invisible here, which is the known limit of a
name-based rule and the reason the check runs both ways: a listed path that
does not exist fails too, so a rename cannot leave the page pointing at
nothing.

Directories that hold copies rather than sources are skipped: `.git/`,
`cold-read-records/` and `sanity-check-records/` (a frozen cold-read-target
under `target/` is a copy of a document, not a second glossary), and
`docs/walk/` (a walk draft quoting a glossary is not one).
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PROJECT_GLOSSARY = REPO_ROOT / "docs" / "nedschorus-wiki" / "nedschorus-glossary.md"
GLOSSARY_SUFFIX = "-glossary.md"
SKIPPED_DIRECTORIES = (".git", "cold-read-records", "sanity-check-records", "docs/walk")

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def is_skipped(relative_path):
    text = relative_path.as_posix()
    return any(text == d or text.startswith(d + "/") for d in SKIPPED_DIRECTORIES)


def system_glossaries_in(repo_root):
    """Every `*-glossary.md` in the checkout but the project glossary, as
    repository-relative paths, sorted."""
    found = []
    for path in repo_root.rglob("*" + GLOSSARY_SUFFIX):
        relative = path.relative_to(repo_root)
        if is_skipped(relative) or path == PROJECT_GLOSSARY:
            continue
        found.append(relative.as_posix())
    return sorted(found)


def unlisted(page_text, glossary_paths):
    """The glossaries the page does not name."""
    return [path for path in glossary_paths if path not in page_text]


def listed_but_missing(page_text, repo_root, glossary_paths):
    """Paths the page names that are not a glossary in the checkout: a
    rename or a deletion that left the page pointing at nothing."""
    missing = []
    for word in page_text.replace("`", " ").split():
        # Only the trailing punctuation goes: a leading dot is part of the
        # path, as `.claude/skills/skills-glossary.md` is.
        candidate = word.lstrip("([").rstrip(".,;:)]")
        if not candidate.endswith(GLOSSARY_SUFFIX):
            continue
        if candidate in glossary_paths or candidate == PROJECT_GLOSSARY.relative_to(repo_root).as_posix():
            continue
        if "/" not in candidate:
            # A bare file name, not a path: the prose is naming a file it
            # located elsewhere, and there is nothing to resolve.
            continue
        if not (repo_root / candidate).is_file():
            missing.append(candidate)
    return sorted(set(missing))


if __name__ == "__main__":
    page = PROJECT_GLOSSARY.read_text()
    glossaries = system_glossaries_in(REPO_ROOT)

    check("the checkout has at least one system glossary to check",
          glossaries,
          "found none; either they were all removed or the naming changed")

    check("every system glossary is listed on the project glossary",
          not unlisted(page, glossaries),
          f"not listed: {unlisted(page, glossaries)} — add each to the paragraph "
          f"above the entries in {PROJECT_GLOSSARY.relative_to(REPO_ROOT)}")

    check("every glossary path the project glossary names exists",
          not listed_but_missing(page, REPO_ROOT, glossaries),
          f"named but absent: {listed_but_missing(page, REPO_ROOT, glossaries)}")

    # The check's own faults, against text rather than the checkout, so a
    # future edit that weakens it fails here rather than passing silently.
    check("a glossary missing from the page is faulted",
          unlisted("a page naming nothing", ["docs/a/a-glossary.md"]),
          "an unlisted glossary passed")

    check("a page naming a glossary that does not exist is faulted",
          listed_but_missing("see `docs/gone/gone-glossary.md`", REPO_ROOT, []),
          "a dangling glossary path passed")

    # A leading dot is part of the path, not punctuation to strip: the first
    # run of this test read `.claude/skills/skills-glossary.md` as
    # `claude/skills/...` and reported the page's own listing as dangling.
    check("a dotted directory keeps its dot",
          not listed_but_missing("`.claude/skills/skills-glossary.md`", REPO_ROOT,
                                 [".claude/skills/skills-glossary.md"]),
          "a leading dot was stripped, so the path did not resolve")

    sys.exit(1 if failures else 0)
