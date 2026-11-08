#!/usr/bin/env python3
"""A term has an entry in at most one of the project's glossaries.

CLAUDE.md says a project-term or a system-term has one definition, in its
glossary, and the project glossary says each term has one entry, in the
glossary of the widest scope that uses it. This suite fails when one term has
entries in two or more glossaries, and names the term and each glossary.

The glossaries checked are the project glossary and every system glossary
its listing paragraph names, read with the functions of
scripts/system-glossaries-listed-on-the-project-glossary-test.py, so the two
suites agree on which glossaries exist.

An entry is a line that begins `- **term**`. One entry may define several
terms, as `- **code-based-test**, **prompt-based-test** — ...` does, and a
term may carry an alias, as `**code-prompt-code (aka CPC)**` does; each such
name counts as a term of that entry. Two spellings are the same term when
they match after case is ignored and runs of spaces, hyphens and underscores
are read as one hyphen, so `instruction-file guard` and
`Instruction-File-Guard` are one term. A leading `/` or `-` is kept, because
it marks a skill or a filename suffix. Plurals are not matched.

A term repeated inside one glossary is not this suite's concern. A listed
glossary whose file is missing, and a glossary from which no entry can be
read, fail, because a check that reads nothing must never pass.

Run: python3 scripts/glossary-term-has-entries-in-only-one-glossary-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import re
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_listed_spec = importlib.util.spec_from_file_location(
    "system_glossaries_listed_on_the_project_glossary_test",
    REPO_ROOT / "scripts" / "system-glossaries-listed-on-the-project-glossary-test.py")
GLOSSARIES_LISTED = importlib.util.module_from_spec(_listed_spec)
_listed_spec.loader.exec_module(GLOSSARIES_LISTED)
RULE_FAILURE_LINES = GLOSSARIES_LISTED.RULE_FAILURE_LINES
PROJECT_GLOSSARY_RELATIVE_PATH = GLOSSARIES_LISTED.PROJECT_GLOSSARY_RELATIVE_PATH

ENTRY_HEAD = re.compile(r"- (\*\*[^*\n]+\*\*(?:\s*,\s*\*\*[^*\n]+\*\*)*)")
BOLD = re.compile(r"\*\*([^*\n]+)\*\*")
ALIAS = re.compile(r"^(.*?)\s*\(aka\s+([^)]+)\)\s*$")
SEPARATOR_RUN = re.compile(r"[\s_-]+")

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def normalized_term(spelling):
    stripped = spelling.strip()
    lead = stripped[0] if stripped[:1] in ("/", "-") else ""
    return lead + SEPARATOR_RUN.sub("-", stripped[len(lead):].casefold()).strip("-")


def entry_terms(glossary_text):
    """Every term spelling the glossary's entries define, in page order."""
    terms = []
    for line in glossary_text.splitlines():
        head = ENTRY_HEAD.match(line)
        if not head:
            continue
        for bold in BOLD.findall(head.group(1)):
            alias = ALIAS.match(bold)
            terms.extend([alias.group(1), alias.group(2)] if alias else [bold])
    return terms


def listed_glossary_paths(repo_root):
    """The project glossary, then each system glossary its listing paragraph
    names, as repository-relative paths; the paths the paragraph names that
    lead to no file; and the fault when the paragraph cannot be located."""
    page = (repo_root / PROJECT_GLOSSARY_RELATIVE_PATH).read_text(encoding="utf-8")
    paragraph, fault = GLOSSARIES_LISTED.system_glossary_paragraph(page)
    if paragraph is None:
        return [PROJECT_GLOSSARY_RELATIVE_PATH], [], fault
    paths, missing = [PROJECT_GLOSSARY_RELATIVE_PATH], []
    for written, readings in GLOSSARIES_LISTED.glossary_paths_named_in(paragraph):
        found = next((reading for reading in readings
                      if (repo_root / reading).is_file()), None)
        if found is None:
            # A bare file name names a file located elsewhere, as the
            # listing suite also reads it, so only a path can be missing.
            if "/" in written and written not in missing:
                missing.append(written)
        elif found not in paths:
            paths.append(found)
    return paths, missing, ""


def terms_in_more_than_one_glossary(glossary_texts):
    """{normalized term: [(glossary path, spelling there), ...]} for each term
    with entries in two or more of the glossaries given as {path: text}."""
    holders = {}
    for path, text in glossary_texts.items():
        for spelling in entry_terms(text):
            per_glossary = holders.setdefault(normalized_term(spelling), {})
            per_glossary.setdefault(path, spelling)
    return {term: list(per_glossary.items())
            for term, per_glossary in sorted(holders.items())
            if len(per_glossary) > 1}


def duplicate_failure_detail(duplicates):
    lines = ["a term has an entry in more than one glossary, and CLAUDE.md gives each term "
             "one definition:"]
    for holders in duplicates.values():
        lines.append("  " + "; ".join(f"{spelling!r} in {path}" for path, spelling in holders))
    lines += [
        f"If a term is used by more than one system, keep its entry in "
        f"{PROJECT_GLOSSARY_RELATIVE_PATH} and delete it from each system glossary.",
        "If a term is used by one system alone, keep its entry in that system's glossary and "
        "delete it from the others.",
        "If two entries name different things that happen to share a spelling, rename one; "
        "a new name for a term is put to the user before it is used.",
        RULE_FAILURE_LINES.FAILURE_MAY_COME_FROM_MAIN_NOT_YOUR_CHANGE_REPORT_IT_CLOSING_LINE]
    return "\n".join(lines)


if __name__ == "__main__":
    # --- the rule, against the checkout this file is in ----------------------
    paths, missing, paragraph_fault = listed_glossary_paths(REPO_ROOT)
    check("the project glossary's paragraph listing the system glossaries is located",
          not paragraph_fault, paragraph_fault)
    check("every glossary the project glossary lists has a file", not missing,
          f"no file at {missing}; run "
          f"scripts/system-glossaries-listed-on-the-project-glossary-test.py and fix what it "
          f"reports")
    check("the project glossary lists at least one system glossary that exists",
          len(paths) > 1,
          f"found only {paths}; run "
          f"scripts/system-glossaries-listed-on-the-project-glossary-test.py and fix what it "
          f"reports")
    texts = {path: (REPO_ROOT / path).read_text(encoding="utf-8") for path in paths}
    unreadable = [path for path, text in texts.items() if not entry_terms(text)]
    check("an entry is read from every glossary", not unreadable,
          f"no line beginning `- **term**` was read from {unreadable}; write each glossary "
          f"entry as a line beginning `- **term**`, or change ENTRY_HEAD in "
          f"scripts/{Path(__file__).name} to the format the glossaries now use")
    duplicates = terms_in_more_than_one_glossary(texts)
    check("no term has an entry in more than one glossary", not duplicates,
          duplicate_failure_detail(duplicates))

    # --- the parsing and matching, against fixtures --------------------------
    check("an entry's aliases and every term of a several-term entry are read",
          entry_terms("intro **not-an-entry** here\n"
                      "- **code-prompt-code (aka CPC)** — a program.\n"
                      "- **code-based-test**, **user-based-test** — kinds of test, "
                      "not **body-term**.\n"
                      "  - **nested** — not an entry.\n")
          == ["code-prompt-code", "CPC", "code-based-test", "user-based-test"],
          "entry_terms read the wrong terms")
    check("case, spaces, hyphens and underscores do not tell two spellings apart",
          normalized_term("Instruction-File guard") == normalized_term("instruction_file-Guard"),
          "normalized_term tells them apart")
    check("a leading slash or hyphen tells two spellings apart",
          len({normalized_term(s) for s in ("/handoff", "handoff", "-draft", "draft")}) == 4,
          "normalized_term drops a leading / or -")
    fixture = {
        "a-glossary.md": "- **agent-seat** — a seat.\n- **CPC** — an alias here.\n"
                         "- **only-here** — once.\n- **only-here** — twice, one glossary.\n",
        "b-glossary.md": "- **Agent seat** — the same term.\n"
                         "- **code-prompt-code (aka cpc)** — a program.\n",
        "c-glossary.md": "- **agent_seat** — a third.\n",
    }
    found = terms_in_more_than_one_glossary(fixture)
    check("a term in two or more glossaries is reported with each glossary and spelling",
          found == {"agent-seat": [("a-glossary.md", "agent-seat"),
                                   ("b-glossary.md", "Agent seat"),
                                   ("c-glossary.md", "agent_seat")],
                    "cpc": [("a-glossary.md", "CPC"), ("b-glossary.md", "cpc")]},
          f"found {found}")
    detail = duplicate_failure_detail(found)
    check("the failure message names each term's glossaries",
          "'Agent seat' in b-glossary.md" in detail and "'cpc' in b-glossary.md" in detail,
          detail)

    real_page = (REPO_ROOT / PROJECT_GLOSSARY_RELATIVE_PATH).read_text(encoding="utf-8")
    real_listing, _ = GLOSSARIES_LISTED.system_glossary_paragraph(real_page)
    first_written = next((written for written, _ in
                          GLOSSARIES_LISTED.glossary_paths_named_in(real_listing or "")
                          if "/" in written), None)
    # A link whose label and target are both paths writes one glossary twice.
    linked_page = real_page if first_written is None else real_page.replace(
        f"`{first_written}`", f"[{first_written}](../../{first_written})", 1)
    for case, page in (("as written", real_page), ("with a glossary written as a link", linked_page)):
        with tempfile.TemporaryDirectory() as scratch:
            scratch_root = Path(scratch)
            project_glossary = scratch_root / PROJECT_GLOSSARY_RELATIVE_PATH
            project_glossary.parent.mkdir(parents=True)
            project_glossary.write_text(page, encoding="utf-8")
            _, scratch_missing, scratch_fault = listed_glossary_paths(scratch_root)
            listing, _ = GLOSSARIES_LISTED.system_glossary_paragraph(page)
            written_paths = set() if listing is None else {
                written for written, _ in GLOSSARIES_LISTED.glossary_paths_named_in(listing)
                if "/" in written}
            check(f"a listed glossary whose file is missing is reported, not dropped ({case})",
                  not scratch_fault and bool(written_paths)
                  and set(scratch_missing) == written_paths,
                  f"with no system glossary in the checkout, {scratch_missing} were reported "
                  f"missing, not the paths the project glossary lists, {sorted(written_paths)}"
                  + (f"; {scratch_fault}" if scratch_fault else ""))

    sys.exit(1 if failures else 0)
