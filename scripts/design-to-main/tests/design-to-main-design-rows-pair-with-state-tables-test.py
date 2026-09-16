#!/usr/bin/env python3
"""Sections 3.1 and 3.2 of the design-to-main state-machine design, read
from the design file in the checkout this test runs in, paired with
STATE_TABLE and TRANSITION_TABLE in design-to-main-state-tables.py.

User-ruled 2026-09-16, the eleventh design walk
(design-state-tables-source-of-truth-and-checker), item 2.2: both copies
stay hand-edited; section 3.2 is the source for what a transition is, the
code for what it does; a checker test binds them, so that drift fails the
suite the day it is written. The join key is section 3.2's Row column
(PR #404): a row number is an identifier, never renumbered, and names the
TRANSITION_TABLE row with the same `row`.

What it checks:
- every prose row number has a code row, and every code row a prose row;
- each pair agrees on from-state, verdict and to-state, read from the
  backticked names of the From, Trigger and To cells (see
  `transition_row_pairing_mismatches` for how each cell is read);
- section 3.1's states are STATE_TABLE's, both directions, and each
  state's sub-states are STATE_TABLE's, in the order section 3.1 lists.

What it does not check:
- guards. The Trigger column's guard words are free text and the code's
  guards are named predicates; the user ruled that comparing them stays a
  person's work.
- a mechanism described in prose with no row behind it, in either copy.
- a section 7 ceiling number that disagrees with COUNTER_TABLE.

Run: python3 scripts/design-to-main/tests/design-to-main-design-rows-pair-with-state-tables-test.py
"""

import dataclasses
import importlib.util
import pathlib
import re
import unittest

MACHINE_DIRECTORY = pathlib.Path(__file__).resolve().parent.parent
REPOSITORY_ROOT = MACHINE_DIRECTORY.parent.parent
DESIGN_PATH = REPOSITORY_ROOT / "docs" / "design-to-main" / "design-to-main-state-machine-design.md"


def load_state_tables_module():
    spec = importlib.util.spec_from_file_location(
        "design_to_main_state_tables", MACHINE_DIRECTORY / "design-to-main-state-tables.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


T = load_state_tables_module()

SECTION_3_1_TABLE_HEADER = (
    "| State | Sub-states | Package beyond the standard-package | State-exit verdicts |")
SECTION_3_2_TABLE_HEADER = "| Row | From | Trigger | To | Counter (§7) |"


class DesignTableMalformed(Exception):
    """A table of the design this test reads is not where or what it expects."""


@dataclasses.dataclass(frozen=True)
class DesignTransitionProseRow:
    """One row of section 3.2, as its cells read."""
    row: str
    from_cell: str
    trigger_cell: str
    to_cell: str


def markdown_table_cells_under_header(design_text, header, cell_count):
    """The body rows of the table whose header line is `header`, each split
    into its cells. A row with another number of cells is malformed."""
    lines = design_text.splitlines()
    if lines.count(header) != 1:
        raise DesignTableMalformed("expected one table headed %r, found %d"
                                   % (header, lines.count(header)))
    start = lines.index(header)
    rows = []
    for line in lines[start + 2:]:
        if not line.startswith("|"):
            break
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != cell_count:
            raise DesignTableMalformed("%d cells, not %d: %s" % (len(cells), cell_count, line))
        rows.append(cells)
    if not rows:
        raise DesignTableMalformed("no rows under %r" % header)
    return rows


def section_3_2_prose_rows(design_text):
    rows = []
    for number, from_cell, trigger_cell, to_cell, _counter in markdown_table_cells_under_header(
            design_text, SECTION_3_2_TABLE_HEADER, 5):
        if not re.fullmatch(r"[1-9][0-9]*", number):
            raise DesignTableMalformed("section 3.2 row number %r is not a number" % number)
        rows.append(DesignTransitionProseRow(number, from_cell, trigger_cell, to_cell))
    return rows


def backticked_tokens(cell):
    return re.findall(r"`([^`]+)`", cell)


# --- How each cell of section 3.2 is read ------------------------------------

# From cells that name a set of states by a phrase rather than a backticked
# name for each. The phrase is read as the set it names, and the cell's
# backticked states are taken out of it or added to it.
#   Row 16: "any reviewing state but `contract-reviewing`, ..." — every
#   reviewing (composite) state of section 3.1 but those named.
#   Row 69: "a reviewing sub-state by agent, `contract-revising`, ..." —
#   every reviewing state (a sub-state's row is keyed by its composite
#   state), and the states named after it.
FROM_CELL_PHRASE_ANY_REVIEWING_STATE_BUT = "any reviewing state but "
FROM_CELL_PHRASE_A_REVIEWING_SUB_STATE_BY_AGENT = "a reviewing sub-state by agent"

# From cells that are prose the matcher cannot read, by row, with the cell
# text they were read as. The text is compared, so that an edit to the
# cell ends the exemption rather than hiding behind it.
FROM_CELLS_THE_MATCHER_CANNOT_READ = {
    # "Any state above" names states by the position of their rows in the
    # table, not by name: which of them can reject, or fail a check
    # against, the component-contract is a person's to compare.
    "67": "any state above",
}

# Trigger cells that name verdicts by a phrase rather than a backticked name.
TRIGGER_CELL_PHRASES_NAMING_VERDICTS = {
    # Row 67: a reviewer's or the arbitrator's `reject contract`, and a
    # writer's `input-quick-check-failed` against the component-contract.
    "a reject of, or a failed check against, the component-contract":
        (T.V_REJECT_CONTRACT, T.V_INPUT_QUICK_CHECK_FAILED),
}

# The code's destinations that are not a state, each with the words the
# design's To cell says it in. A To cell for one of these names no state.
TO_CELL_PHRASE_OF_DESTINATION_MARKER = {
    T.TO_HOLD_READY_FOR_TEST_SUITE: "holds at `ready-for-test-suite`",
    T.TO_BOTH_WORK_STREAMS_RE_ENTER: "both work-streams re-enter their writing states",
    T.TO_THE_NEXT_ACCEPTANCE_CHECK: "the state's next acceptance-check",
    T.TO_WHEREVER_THAT_REVIEWING_STATES_ADVANCE_GOES:
        "wherever that reviewing state's own `advance` goes",
    T.TO_THE_WRITER_THE_VERDICT_NAMES: "that writer anyway, fresh",
    T.TO_BOTH_WRITERS_FRESH: "both writers",
    T.TO_RESUME_DESTINATION: "the earliest state downstream of what the user changed",
}
# The retry marker is read differently: its To cell names the row's own
# from-state, followed by "(retry" (rows 58 and 76), since "the same state"
# is that state.
TO_CELL_RETRY_WORD = "(retry"


def state_and_sub_state_names(state_table):
    return ({row.name for row in state_table}
            | {sub_state for row in state_table for sub_state in row.sub_states})


def verdict_names(transition_table, state_table):
    names = {value for name, value in vars(T).items() if name.startswith("V_")}
    names |= {verdict for row in transition_table for verdict in row.verdicts}
    names |= {verdict for row in state_table for verdict in row.verdicts}
    return names


def from_states_the_prose_names(prose_row, state_names, state_table):
    named = {token for token in backticked_tokens(prose_row.from_cell) if token in state_names}
    reviewing_states = {row.name for row in state_table if row.work == "composite"}
    if prose_row.from_cell.startswith(FROM_CELL_PHRASE_ANY_REVIEWING_STATE_BUT):
        return reviewing_states - named
    if prose_row.from_cell.startswith(FROM_CELL_PHRASE_A_REVIEWING_SUB_STATE_BY_AGENT):
        return reviewing_states | named
    return named


def verdicts_the_prose_names(prose_row, known_verdicts):
    named = {token for token in backticked_tokens(prose_row.trigger_cell) if token in known_verdicts}
    for phrase, verdicts in TRIGGER_CELL_PHRASES_NAMING_VERDICTS.items():
        if phrase in prose_row.trigger_cell:
            named |= set(verdicts)
    return named


def to_state_mismatch(prose_row, code_row, state_names):
    """None when the To cell says the code row's to-state; else why not.

    A to-state that is a state or sub-state must be the FIRST state the To
    cell backticks: later ones are what follows ("then `design-writing` as
    a redesign", "and, if tests have begun, `test-design-writing`"), and a
    to-state that is only among them is wrong."""
    states_in_cell = [token for token in backticked_tokens(prose_row.to_cell)
                      if token in state_names]
    first = states_in_cell[0] if states_in_cell else None
    if code_row.to_state in state_names:
        if first != code_row.to_state:
            return "to-state %r, the To cell's first state %r" % (code_row.to_state, first)
        return None
    if code_row.to_state == T.TO_RETRY_SAME_STATE:
        if len(code_row.from_states) != 1:
            return "a retry from %d states names no one state" % len(code_row.from_states)
        if first != code_row.from_states[0] or TO_CELL_RETRY_WORD not in prose_row.to_cell:
            return "a retry of %r, the To cell %r" % (code_row.from_states[0], prose_row.to_cell)
        return None
    if code_row.to_state in TO_CELL_PHRASE_OF_DESTINATION_MARKER:
        phrase = TO_CELL_PHRASE_OF_DESTINATION_MARKER[code_row.to_state]
        if first is not None or phrase not in prose_row.to_cell:
            return "to-state %r, which the design says as %r; the To cell %r" % (
                code_row.to_state, phrase, prose_row.to_cell)
        return None
    return "to-state %r is neither a state nor a destination this test reads" % code_row.to_state


def transition_row_pairing_mismatches(prose_rows, transition_table, state_table):
    """Every disagreement between section 3.2's rows and TRANSITION_TABLE,
    as sentences naming the row; an empty list when they pair."""
    mismatches = []
    state_names = state_and_sub_state_names(state_table)
    known_verdicts = verdict_names(transition_table, state_table)

    prose_numbers = [row.row for row in prose_rows]
    code_numbers = [row.row for row in transition_table]
    for numbers, where in ((prose_numbers, "section 3.2"), (code_numbers, "TRANSITION_TABLE")):
        for number in sorted({n for n in numbers if numbers.count(n) > 1}, key=int):
            mismatches.append("row %s: numbered more than once in %s" % (number, where))
    code_by_number = {row.row: row for row in transition_table}
    prose_by_number = {row.row: row for row in prose_rows}
    for number in sorted(set(prose_by_number) - set(code_by_number), key=int):
        mismatches.append("row %s: in section 3.2, no TRANSITION_TABLE row" % number)
    for number in sorted(set(code_by_number) - set(prose_by_number), key=int):
        mismatches.append("row %s: in TRANSITION_TABLE, no section 3.2 row" % number)

    for number in sorted(set(prose_by_number) & set(code_by_number), key=int):
        prose_row, code_row = prose_by_number[number], code_by_number[number]
        if number in FROM_CELLS_THE_MATCHER_CANNOT_READ:
            if prose_row.from_cell != FROM_CELLS_THE_MATCHER_CANNOT_READ[number]:
                mismatches.append(
                    "row %s: the From cell the matcher cannot read was %r and is now %r"
                    % (number, FROM_CELLS_THE_MATCHER_CANNOT_READ[number], prose_row.from_cell))
        else:
            prose_from = from_states_the_prose_names(prose_row, state_names, state_table)
            if prose_from != set(code_row.from_states):
                mismatches.append("row %s: from-states %s in the code, %s in the design" % (
                    number, sorted(code_row.from_states), sorted(prose_from)))
        prose_verdicts = verdicts_the_prose_names(prose_row, known_verdicts)
        if prose_verdicts != set(code_row.verdicts):
            mismatches.append("row %s: verdicts %s in the code, %s in the design" % (
                number, sorted(code_row.verdicts), sorted(prose_verdicts)))
        why = to_state_mismatch(prose_row, code_row, state_names)
        if why:
            mismatches.append("row %s: %s" % (number, why))
    return mismatches


def section_3_1_states_and_sub_states(design_text):
    """(state, sub-states in the order listed) for each row of section 3.1."""
    states = []
    for state_cell, sub_states_cell, _package, _verdicts in markdown_table_cells_under_header(
            design_text, SECTION_3_1_TABLE_HEADER, 4):
        names = backticked_tokens(state_cell)
        if len(names) != 1:
            raise DesignTableMalformed("section 3.1 State cell %r names %d states"
                                       % (state_cell, len(names)))
        states.append((names[0], tuple(backticked_tokens(sub_states_cell))))
    return states


def state_pairing_mismatches(section_3_1_states, state_table):
    mismatches = []
    prose_names = [name for name, _ in section_3_1_states]
    code_names = [row.name for row in state_table]
    for name in prose_names:
        if prose_names.count(name) > 1:
            mismatches.append("state %s: listed more than once in section 3.1" % name)
    for name in prose_names:
        if name not in code_names:
            mismatches.append("state %s: in section 3.1, not in STATE_TABLE" % name)
    for name in code_names:
        if name not in prose_names:
            mismatches.append("state %s: in STATE_TABLE, not in section 3.1" % name)
    code_by_name = {row.name: row for row in state_table}
    for name, sub_states in section_3_1_states:
        if name in code_by_name and sub_states != code_by_name[name].sub_states:
            mismatches.append("state %s: sub-states %s in section 3.1, %s in STATE_TABLE" % (
                name, list(sub_states), list(code_by_name[name].sub_states)))
    return mismatches


def replace_transition_row(number, **changes):
    return tuple(dataclasses.replace(row, **changes) if row.row == number else row
                 for row in T.TRANSITION_TABLE)


class DesignRowsPairWithTheCode(unittest.TestCase):
    """The design on disk against the tables as they stand."""

    @classmethod
    def setUpClass(cls):
        cls.design_text = DESIGN_PATH.read_text()
        cls.prose_rows = section_3_2_prose_rows(cls.design_text)

    def test_every_section_3_2_row_pairs_with_its_transition_table_row(self):
        self.assertEqual(
            transition_row_pairing_mismatches(self.prose_rows, T.TRANSITION_TABLE, T.STATE_TABLE), [])

    def test_every_section_3_1_state_is_a_state_table_state_and_back(self):
        self.assertEqual(
            state_pairing_mismatches(section_3_1_states_and_sub_states(self.design_text),
                                     T.STATE_TABLE), [])

    def test_every_phrase_the_matcher_reads_is_in_the_design(self):
        # A phrase the design no longer uses would make its reading dead
        # code that a later row could fall into by accident.
        from_cells = [row.from_cell for row in self.prose_rows]
        trigger_cells = [row.trigger_cell for row in self.prose_rows]
        to_cells = [row.to_cell for row in self.prose_rows]
        for phrase in (FROM_CELL_PHRASE_ANY_REVIEWING_STATE_BUT,
                       FROM_CELL_PHRASE_A_REVIEWING_SUB_STATE_BY_AGENT):
            self.assertTrue(any(cell.startswith(phrase) for cell in from_cells), phrase)
        for phrase in TRIGGER_CELL_PHRASES_NAMING_VERDICTS:
            self.assertTrue(any(phrase in cell for cell in trigger_cells), phrase)
        for marker, phrase in TO_CELL_PHRASE_OF_DESTINATION_MARKER.items():
            self.assertTrue(any(phrase in cell for cell in to_cells), marker)


class TheMatcherFailsOnDrift(unittest.TestCase):
    """Copies of the table or the prose, each with one thing changed, fail."""

    @classmethod
    def setUpClass(cls):
        cls.prose_rows = section_3_2_prose_rows(DESIGN_PATH.read_text())

    def mismatches_with(self, transition_table=None, prose_rows=None, state_table=None):
        return transition_row_pairing_mismatches(
            self.prose_rows if prose_rows is None else prose_rows,
            T.TRANSITION_TABLE if transition_table is None else transition_table,
            T.STATE_TABLE if state_table is None else state_table)

    def assert_one_mismatch_naming(self, mismatches, row_text):
        self.assertEqual(len(mismatches), 1, mismatches)
        self.assertTrue(mismatches[0].startswith(row_text), mismatches)

    def test_a_to_state_changed_in_a_copy_of_the_table_fails(self):
        self.assertEqual(T.TRANSITION_TABLE_BY_ROW["24"].to_state, T.TEST_DESIGN_WRITING)
        self.assert_one_mismatch_naming(
            self.mismatches_with(replace_transition_row("24", to_state=T.TEST_WRITING)), "row 24:")

    def test_a_to_state_that_the_to_cell_names_only_as_what_follows_fails(self):
        # Row 18's To cell: "`implementation-writing`; and, if tests have
        # begun in this design version, `test-design-writing`".
        self.assert_one_mismatch_naming(
            self.mismatches_with(replace_transition_row("18", to_state=T.TEST_DESIGN_WRITING)),
            "row 18:")
        # Row 11's: "`investigate-workflow`, ..., then `design-writing` as a redesign".
        self.assert_one_mismatch_naming(
            self.mismatches_with(replace_transition_row("11", to_state=T.DESIGN_WRITING)),
            "row 11:")

    def test_a_retry_row_sent_elsewhere_fails(self):
        self.assert_one_mismatch_naming(
            self.mismatches_with(replace_transition_row("58", to_state=T.TEST_SUITE_ARBITRATING)),
            "row 58:")
        # The To cell of a retry row names a state that is not the row's own.
        edited = [dataclasses.replace(row, to_cell="`investigate-workflow` (retry, backed off)")
                  if row.row == "76" else row for row in self.prose_rows]
        self.assert_one_mismatch_naming(self.mismatches_with(prose_rows=edited), "row 76:")

    def test_a_destination_marker_swapped_for_another_fails(self):
        self.assert_one_mismatch_naming(
            self.mismatches_with(replace_transition_row("9", to_state=T.TO_BOTH_WRITERS_FRESH)),
            "row 9:")
        self.assert_one_mismatch_naming(
            self.mismatches_with(replace_transition_row("26", to_state=T.TEST_SUITE_EXECUTING)),
            "row 26:")

    def test_a_from_state_changed_or_added_fails(self):
        self.assert_one_mismatch_naming(
            self.mismatches_with(replace_transition_row("27", from_states=(T.TEST_REVIEWING,))),
            "row 27:")
        row_16 = T.TRANSITION_TABLE_BY_ROW["16"]
        self.assert_one_mismatch_naming(
            self.mismatches_with(replace_transition_row(
                "16", from_states=row_16.from_states + (T.CONTRACT_REVIEWING,))),
            "row 16:")
        row_69 = T.TRANSITION_TABLE_BY_ROW["69"]
        self.assert_one_mismatch_naming(
            self.mismatches_with(replace_transition_row("69", from_states=row_69.from_states[1:])),
            "row 69:")

    def test_a_verdict_changed_fails(self):
        self.assert_one_mismatch_naming(
            self.mismatches_with(replace_transition_row("27", verdicts=(T.V_REJECT_TESTS,))),
            "row 27:")
        self.assert_one_mismatch_naming(
            self.mismatches_with(replace_transition_row("67", verdicts=(T.V_REJECT_CONTRACT,))),
            "row 67:")

    def test_a_code_row_with_no_prose_row_fails(self):
        extra = dataclasses.replace(T.TRANSITION_TABLE_BY_ROW["78"], row="79")
        self.assertEqual(self.mismatches_with(T.TRANSITION_TABLE + (extra,)),
                         ["row 79: in TRANSITION_TABLE, no section 3.2 row"])

    def test_a_prose_row_with_no_code_row_fails(self):
        self.assertEqual(self.mismatches_with(transition_table=T.TRANSITION_TABLE[:-1]),
                         ["row 78: in section 3.2, no TRANSITION_TABLE row"])
        self.assertEqual(self.mismatches_with(prose_rows=self.prose_rows[:-1]),
                         ["row 78: in TRANSITION_TABLE, no section 3.2 row"])

    def test_the_from_cell_the_matcher_cannot_read_is_exempt_only_while_it_reads_the_same(self):
        edited = [dataclasses.replace(row, from_cell="`test-reviewing`") if row.row == "67" else row
                  for row in self.prose_rows]
        self.assert_one_mismatch_naming(self.mismatches_with(prose_rows=edited), "row 67:")

    def test_a_state_missing_from_either_side_fails(self):
        section_3_1 = section_3_1_states_and_sub_states(DESIGN_PATH.read_text())
        self.assertEqual(state_pairing_mismatches(section_3_1[:-1], T.STATE_TABLE),
                         ["state ended: in STATE_TABLE, not in section 3.1"])
        self.assertEqual(state_pairing_mismatches(section_3_1, T.STATE_TABLE[:-1]),
                         ["state ended: in section 3.1, not in STATE_TABLE"])
        reordered = tuple(
            dataclasses.replace(row, sub_states=tuple(reversed(row.sub_states)))
            if row.name == T.DESIGN_REVIEWING else row for row in T.STATE_TABLE)
        self.assertEqual(len(state_pairing_mismatches(section_3_1, reordered)), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
