#!/usr/bin/env python3
"""The project glossary says its terms are "in alphabetical order, skills
first", and this test is what holds the page to that.

docs/nedschorus-wiki/nedschorus-glossary.md makes the claim in its opening
line. By 2026-09-21 one pair had drifted -- `SDLC-term` below `seat-branch`
-- and nothing noticed until a cold-read-full-run read the page; PR
"Glossary: two entries return to the alphabetical order the page claims" put
it back. That pull request also moved `walked-approval` above `walk-minutes`,
on the letter-by-letter reading since ruled against (THE COLLATION, below).
The page gained eleven entries that same day, so the drift recurs wherever
entries are added. Built on the user's approval of item 5 of the walk "what
this seat needs from you", 2026-09-21.

THE COLLATION IS WORD BY WORD, IGNORING CASE: the user's ruling of
2026-09-21, and the whole rule is "ignore case". A hyphen is not removed. It
ends a word, and `-` sorts below every letter, so `walk-minutes` comes before
`walked-approval` the way "walk" comes before "walked". This test was first
written to sort letter by letter, casefolding and removing hyphens, which
puts `walked-approval` first; the user rejected that, for three reasons.
  - He asked whether ignoring hyphens was an exception to alphabetization.
    Both conventions are standard. Word by word needs no rule beyond
    ignoring case; letter by letter adds one.
  - The letter-by-letter key had been "measured from the page", and that
    evidence was circular. Only one pair on the page tells the two
    conventions apart, `walked-approval` / `walk-minutes`, and PR
    "Glossary: two entries return to the alphabetical order the page
    claims" had placed it on a cold-read-full-run reviewer's
    letter-by-letter reading. Before that pull request the pair stood in
    word-by-word order, so of the two pairs it moved only `SDLC-term` /
    `seat-branch` was a real drift under the ruled convention.
  - docs/design-to-main/design-to-main-glossary.md, which no one told how to
    sort, has 0 faults word by word and 2 letter by letter
    (`gate-rejection` / `gatekeeper-refusal`, `test-write` / `tests-begun`).
Measured 2026-09-21, counting pairs of adjacent entries out of order. The
page on main after PR "GHI terms are named for what they act on", 68
entries: a byte sort reports 5, four false because it puts every capitalised
term (`C-numbers`, `GHI`, `NC`, `SDLC-term`) ahead of every lower-case one,
and one real, `walked-approval` / `walk-minutes`; word by word reports only
that real one; letter by letter reports 0. The page just before PR
"Glossary: two entries return to the alphabetical order the page claims", 62
entries: word by word reports 1, `seat-branch` / `SDLC-term`; letter by
letter reports 2, that pair and `walk-minutes` / `walked-approval`. The
design-to-main glossary, 45 entries: byte 0, word by word 0, letter by
letter 2.

THE HYPHEN PAIR DECIDES WHETHER THIS TEST MEASURES ANYTHING. `walk-minutes`
and `walked-approval` were, on 2026-09-21, the one pair on the page where
word by word and letter by letter disagree. A fixture exercising only case,
or only plain letters, passes under the wrong key as readily as the right
one. So the fixture holds `walk-minutes` above `walked-approval`, a mutation
case swaps them and requires the swapped order to be faulted, and a case
asserts that a letter-by-letter key would call the swapped order correct --
the proof that the fixture exercises the rule in dispute, the hyphen as a
word end, not merely that the check is able to fail.

SKILLS FIRST HAS ITS OWN RULE. A skill's entry begins `/`, which also sorts
below every letter, so the key alone happens to keep skills first. The test
does not leave the page's second claim to that accident: a skill following a
term is faulted by its own rule, with its own instruction, and a case pins
that it is that rule and not the sort that fires.

A PAGE THE CHECK CANNOT READ IS A FAILURE, NOT A PASS. An entry is a line
beginning `- **term**`. Were that format to change, the check would read no
entries and find nothing out of order; it reports reading none instead.

Only the project glossary is checked. The design-to-main glossary is cited
above as evidence for the collation, not checked: it is the design-to-main
system's own glossary and makes no ordering claim.

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
    return term.casefold()


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
                          f"order, word by word, ignoring case.")
    return faults


found = ordering_faults(GLOSSARY.read_text(encoding="utf-8"))
check("the glossary is in alphabetical order, skills first",
      not found, "\n  " + "\n  ".join(found))

# --- The rules, pinned on a fixture ----------------------------------------
# The fixture carries the two pairs that PR "Glossary: two entries return to
# the alphabetical order the page claims" moved, in the order the user's
# ruling of 2026-09-21 gives them, so these cases keep testing the comparison
# even after the real page's terms are renamed.

FIXTURE = """# A glossary

Prose that is not an entry.

- **/ghi-write** — a skill.
- **/handoff** — a skill.
- **agent-seat** — a term.
- **C-numbers** — capitalised, after a lower-case term.
- **SDLC-term** — capitalised, before a lower-case term.
- **seat-branch** — a term.
- **walk-minutes** — first, because a hyphen ends a word.
- **walked-approval** — first only if hyphens were ignored.
"""


def swapped(page, first, second):
    """The page with the entries for two terms exchanged."""
    lines = page.splitlines()
    a, b = (next(i for i, line in enumerate(lines)
                 if line.startswith(f"- **{term}**"))
            for term in (first, second))
    lines[a], lines[b] = lines[b], lines[a]
    return "\n".join(lines)


check("the fixture is in order: a byte sort and a letter-by-letter sort are "
      "not in use",
      not ordering_faults(FIXTURE), "\n  " + "\n  ".join(ordering_faults(FIXTURE)))

check("a letter-by-letter key calls the swapped hyphen pair correct, so the "
      "next case exercises the hyphen as a word end",
      "walked-approval".casefold().replace("-", "")
      < "walk-minutes".casefold().replace("-", ""),
      "the fixture no longer tells the two keys apart; choose a pair that does")

check("walked-approval above walk-minutes is faulted",
      ordering_faults(swapped(FIXTURE, "walk-minutes", "walked-approval")),
      "the hyphen went unread as a word end")

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
