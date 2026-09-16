#!/usr/bin/env python3
"""Section 3.3's diagram of the design-to-main state-machine design is what
design-to-main-state-diagram-generator.py writes from TRANSITION_TABLE.

User-ruled 2026-09-16, the eleventh design walk
(design-state-tables-source-of-truth-and-checker), item 4: the Mermaid
block is generated from TRANSITION_TABLE, and a test fails when the block
in the design is not what the script would write. An agent that changes a
row runs the script before committing:

    python3 scripts/design-to-main/design-to-main-state-diagram-generator.py

It reads the design from the checkout it runs in. It checks the diagram
against the table, not the table against the prose: that is the pairing
test's (design-to-main-design-rows-pair-with-state-tables-test.py), and
neither catches a mechanism described in prose with no row behind it, nor
a section 7 ceiling number that disagrees with COUNTER_TABLE.

Run: python3 scripts/design-to-main/tests/design-to-main-state-diagram-generator-test.py
"""

import dataclasses
import importlib.util
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

MACHINE_DIRECTORY = pathlib.Path(__file__).resolve().parent.parent
GENERATOR_PATH = MACHINE_DIRECTORY / "design-to-main-state-diagram-generator.py"

_generator_spec = importlib.util.spec_from_file_location(
    "design_to_main_state_diagram_generator", GENERATOR_PATH)
generator = importlib.util.module_from_spec(_generator_spec)
_generator_spec.loader.exec_module(generator)

T = generator.T


def run_generator(*arguments):
    return subprocess.run([sys.executable, str(GENERATOR_PATH)] + list(arguments),
                          capture_output=True, text=True)


def replace_transition_row(number, **changes):
    return tuple(dataclasses.replace(row, **changes) if row.row == number else row
                 for row in T.TRANSITION_TABLE)


class TheDesignsDiagramIsGenerated(unittest.TestCase):

    def test_the_design_s_diagram_is_what_the_generator_writes(self):
        result = run_generator("--check")
        self.assertEqual(result.returncode, 0,
                         "section 3.3 differs from the generated diagram; run "
                         "design-to-main-state-diagram-generator.py\n" + result.stdout + result.stderr)


class TheCheckHasTeeth(unittest.TestCase):
    """--check against copies of the design in a temporary directory."""

    def setUp(self):
        self.directory = pathlib.Path(tempfile.mkdtemp(prefix="design-to-main-diagram-test-"))
        self.copy = self.directory / "design.md"
        shutil.copyfile(generator.DESIGN_PATH, self.copy)

    def tearDown(self):
        shutil.rmtree(self.directory, ignore_errors=True)

    def test_check_fails_on_a_diagram_with_one_edge_changed_and_writes_nothing(self):
        text = self.copy.read_text()
        edge = "    test_suite_executing --> submit_to_PR_gate: pass\n"
        self.assertIn(edge, text)
        altered = text.replace(edge, "    test_suite_executing --> ended: pass\n")
        self.copy.write_text(altered)
        result = run_generator("--check", "--design-file", str(self.copy))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("test_suite_executing --> ended: pass", result.stdout)
        self.assertEqual(self.copy.read_text(), altered)

    def test_writing_replaces_the_block_and_nothing_else(self):
        text = self.copy.read_text()
        start, end = generator.section_3_3_block_span(text)
        self.copy.write_text(text[:start] + "stateDiagram-v2\n    [*] --> ended\n" + text[end:])
        result = run_generator("--design-file", str(self.copy))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        rewritten = self.copy.read_text()
        new_start, new_end = generator.section_3_3_block_span(rewritten)
        self.assertEqual(rewritten[:new_start], text[:start])
        self.assertEqual(rewritten[new_end:], text[end:])
        self.assertEqual(run_generator("--check", "--design-file", str(self.copy)).returncode, 0)

    def test_a_design_with_no_diagram_block_is_an_error_not_a_pass(self):
        text = self.copy.read_text()
        self.copy.write_text(text.replace("```mermaid\n", "```text\n"))
        self.assertNotEqual(run_generator("--check", "--design-file", str(self.copy)).returncode, 0)


class WhatTheGeneratorDraws(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.lines = generator.state_diagram_mermaid_lines()
        cls.text = "\n".join(cls.lines)

    def composite_block(self, state):
        start = self.lines.index("    state %s {" % generator.mermaid_identifier(state))
        end = self.lines.index("    }", start)
        return self.lines[start + 1:end]

    def test_a_changed_row_changes_the_diagram(self):
        changed = generator.state_diagram_mermaid_lines(
            replace_transition_row("56", to_state=T.ENDED))
        self.assertIn("    test_suite_executing --> ended: pass", changed)
        self.assertNotIn("    test_suite_executing --> submit_to_PR_gate: pass", changed)

    def test_a_destination_the_generator_does_not_know_is_an_error(self):
        with self.assertRaises(generator.StateDiagramCannotBeDrawn):
            generator.state_diagram_mermaid_lines(
                replace_transition_row("56", to_state="somewhere new"))

    def test_every_destination_in_the_table_is_drawn_or_named_as_not_drawn(self):
        states = {row.name for row in T.STATE_TABLE} | set(T.COMPOSITE_STATE_OF_SUB_STATE)
        known_markers = (set(generator.DRAWN_STATES_OF_DESTINATION_MARKER)
                         | set(generator.DESTINATION_MARKERS_NOT_DRAWN)
                         | set(generator.DESTINATION_MARKERS_DRAWN_BY_RULE))
        for row in T.TRANSITION_TABLE:
            self.assertTrue(row.to_state in states or row.to_state in known_markers,
                            "row %s: %r" % (row.row, row.to_state))

    def test_what_section_3_3_says_is_not_drawn_is_not_drawn(self):
        # The retry loops (rows 58 and 76), the user's discuss returns, and
        # the arbitrator's advance from a reviewer's ceiling (row 60).
        for line in self.lines:
            if " --> " in line:
                from_name, rest = line.strip().split(" --> ")
                self.assertNotEqual(from_name, rest.split(":")[0], line)
        self.assertNotIn("discuss", self.text)
        self.assertNotIn("test_suite_arbitrating --> test_suite_arbitrating", self.text)
        self.assertFalse(any(line.startswith("    test_suite_arbitrating -->") and "advance" in line
                             for line in self.lines))

    def test_removing_a_state_s_rows_removes_its_edges(self):
        # Nothing is drawn that no row gives.
        without_submit_rows = tuple(row for row in T.TRANSITION_TABLE
                                    if T.SUBMIT_TO_PR_GATE not in row.from_states)
        lines = generator.state_diagram_mermaid_lines(without_submit_rows)
        self.assertFalse(any(line.startswith("    submit_to_PR_gate -->") for line in lines))

    def test_the_composite_states_hold_their_sub_states_edges(self):
        self.assertEqual(self.composite_block(T.CONTRACT_REVIEWING), [
            "        contract_acceptance_by_program --> contract_acceptance_by_agent: advance",
            "        contract_acceptance_by_agent --> contract_acceptance_by_user: reject contract",
        ])
        self.assertEqual(self.composite_block(T.TEST_DESIGN_REVIEWING), [
            "        test_design_acceptance_by_agent --> test_design_acceptance_by_user: "
            "advance / reject test-design",
        ])

    def test_hyphens_become_underscores_and_nothing_else_changes(self):
        self.assertEqual(generator.mermaid_identifier(T.SUBMIT_TO_PR_GATE), "submit_to_PR_gate")
        for line in self.lines:
            if " --> " in line:
                edge = line.split(":")[0]
                self.assertNotIn("-", edge.replace("-->", ""), line)

    def test_an_input_quick_check_failed_carries_the_input_its_guard_names(self):
        self.assertIn("    test_writing --> test_design_writing: input-quick-check-failed (test-design)",
                      self.lines)
        self.assertIn("    implementation_writing --> investigate_workflow: "
                      "input-quick-check-failed (design)", self.lines)


if __name__ == "__main__":
    unittest.main(verbosity=2)
