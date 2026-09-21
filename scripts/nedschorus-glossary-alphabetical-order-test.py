#!/usr/bin/env python3
"""The project glossary says its terms are "in alphabetical order, skills
first", and this test is what holds the page to that.

docs/nedschorus-wiki/nedschorus-glossary.md makes the claim in its opening
line. By 2026-09-21 two pairs had drifted -- `SDLC-term` below `seat-branch`,
`walked-approval` below `walk-minutes` -- and nothing noticed until a
cold-read-full-run read the page; PR "Glossary: two entries return to the
alphabetical order the page claims" put them back. The page gained four
project-terms that same day, so the drift recurs wherever entries are added.
Built on the user's approval of item 5 of the walk "what this seat needs from
you", 2026-09-21.

THE COLLATION IS THE PAGE'S, MEASURED, NOT ASSUMED. Four keys were run over
the page's 68 entries on 2026-09-21. A byte sort reports five out-of-order
pairs, all false: it puts every capitalised term (`C-numbers`, `GHI`, `NC`,
`SDLC-term`) ahead of every lower-case one. Casefolding alone reports one,
also false: `-` sorts below every letter, so it puts `walk-minutes` ahead of
`walked-approval`. Casefolding with hyphens removed reports none. That is the
key below, and the page as it stood is the evidence for it.

THE HYPHEN PAIR DECIDES WHETHER THIS TEST MEASURES ANYTHING. `walked-approval`
and `walk-minutes` are the one pair on the page where casefolding alone and
casefolding without hyphens disagree. A fixture exercising only case, or only
plain letters, passes under the wrong key as readily as the right one. So the
mutation cases swap that pair, and a case asserts that a casefold-only key
would call the swapped order correct -- the proof that the fixture exercises
the rule in dispute, not merely that the check is able to fail.

SKILLS FIRST HAS ITS OWN RULE. A skill's entry begins `/`, which also sorts
below every letter, so the key alone happens to keep skills first. The test
does not leave the page's second claim to that accident: a skill following a
term is faulted by its own rule, with its own instruction, and a case pins
that it is that rule and not the sort that fires.

A PAGE THE CHECK CANNOT READ IS A FAILURE, NOT A PASS. An entry is a line
beginning `- **term**`. Were that format to change, the check would read no
entries and find nothing out of order; it reports reading none instead.

Only the project glossary is checked. The design-to-main glossary,
docs/design-to-main/design-to-main-glossary.md, is a system-glossary and
makes no ordering claim.

Run: python3 scripts/nedschorus-glossary-alphabetical-order-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GLOSSARY = REPO_ROOT / "docs" / "nedschorus-wiki" / "nedschorus-glossary.md"
ENTRY_LINE = re.compile(r"- \*\*(.+?)\*\*")

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def collation_key(term):
    return term.casefold().replace("-", "")


def ordering_faults(page):
    """One instruction per entry out of place, naming its line."""
    entries = [(number, match.group(1))
               for number, line in enumerate(page.splitlines(), start=1)
               if (match := ENTRY_LINE.match(line))]
    if not entries:
        return ["Write each glossary entry as a line beginning `- **term**`; "
                "this check read no entries."]
    faults = []
    for (_, earlier), (number, later) in zip(entries, entries[1:]):
        if later.startswith("/") and not earlier.startswith("/"):
            faults.append(f"line {number}: move the skill {later!r} above "
                          f"every term; skills come first.")
        elif collation_key(later) < collation_key(earlier):
            faults.append(f"line {number}: {later!r} sorts before {earlier!r} "
                          f"on the entry above; move it into alphabetical "
                          f"order, comparing without case or hyphens.")
    return faults


found = ordering_faults(GLOSSARY.read_text(encoding="utf-8"))
check("the glossary is in alphabetical order, skills first",
      not found, "\n  " + "\n  ".join(found))

# --- The rules, pinned on a fixture ----------------------------------------
# The fixture carries the two pairs that drifted on 2026-09-21, so these cases
# keep testing the comparison even after the real page's terms are renamed.

FIXTURE = """# A glossary

Prose that is not an entry.

- **/ghi-write** — a skill.
- **/handoff** — a skill.
- **agent-seat** — a term.
- **C-numbers** — capitalised, after a lower-case term.
- **SDLC-term** — capitalised, before a lower-case term.
- **seat-branch** — a term.
- **walked-approval** — first only once hyphens are ignored.
- **walk-minutes** — a term.
"""


def swapped(page, first, second):
    """The page with the entries for two terms exchanged."""
    lines = page.splitlines()
    a, b = (next(i for i, line in enumerate(lines)
                 if line.startswith(f"- **{term}**"))
            for term in (first, second))
    lines[a], lines[b] = lines[b], lines[a]
    return "\n".join(lines)


check("the fixture is in order: a byte sort and a casefold-only sort are not "
      "in use",
      not ordering_faults(FIXTURE), "\n  " + "\n  ".join(ordering_faults(FIXTURE)))

check("a casefold-only key calls the swapped hyphen pair correct, so the next "
      "case exercises the hyphen rule",
      "walk-minutes".casefold() < "walked-approval".casefold(),
      "the fixture no longer tells the two keys apart; choose a pair that does")

check("walk-minutes above walked-approval is faulted",
      ordering_faults(swapped(FIXTURE, "walked-approval", "walk-minutes")),
      "the hyphen rule went unenforced")

check("seat-branch above SDLC-term is faulted",
      ordering_faults(swapped(FIXTURE, "SDLC-term", "seat-branch")),
      "the case rule went unenforced")

check("skills out of order among themselves are faulted",
      ordering_faults(swapped(FIXTURE, "/ghi-write", "/handoff")),
      "the skills block went unsorted")

skill_after_term = ordering_faults(swapped(FIXTURE, "/handoff", "agent-seat"))
check("a skill after a term is faulted by the skills-first rule",
      any("skills come first" in fault for fault in skill_after_term),
      f"got {skill_after_term!r}")

unreadable = ordering_faults(FIXTURE.replace("- **", "* **"))
check("a page with no readable entries is a failure, not a pass",
      any("read no entries" in fault for fault in unreadable),
      f"got {unreadable!r}")

sys.exit(1 if failures else 0)
