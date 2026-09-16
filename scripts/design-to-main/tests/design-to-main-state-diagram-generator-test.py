#!/usr/bin/env python3
"""Section 3.3's four diagram views of the design-to-main state-machine
design are what design-to-main-state-diagram-generator.py writes from
TRANSITION_TABLE.

User-ruled 2026-09-16, the eleventh design walk
(design-state-tables-source-of-truth-and-checker), item 4: the Mermaid
diagram is generated from TRANSITION_TABLE, and a test fails when the design
is not what the script would write. User-ruled 2026-09-16, the walk
design-tables-checker-findings-from-pr-409, items 3 to 5: an edge is
labelled `verdict [guard]`; section 3.3 is four views of the one table, each
row the diagram draws in exactly one, by the row's `view`, and this test
fails on a row with no view or an unknown one; a row entered from many
states is drawn once, from a box around them. An agent that changes a row
runs the script before committing:

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

ALL_VIEWS = T.DIAGRAM_VIEWS_DRAWN

# The rows a run routes when every state advances (the whole-run test's
# WholeRunThatPasses), less row 16, which is drawn inside the reviewing
# states.
ROWS_OF_THE_RUN_WHERE_EVERYTHING_ADVANCES = (
    "1", "2", "5", "18", "21", "24", "32", "41", "42", "47", "56", "74")

# Section 3.3's rows not drawn: the retry loops, the user's discuss
# returns, and the arbitrator's advance from a reviewer's ceiling.
ROWS_SECTION_3_3_DOES_NOT_DRAW = ("10", "17", "31", "40", "55", "58", "60", "76")


def run_generator(*arguments):
    return subprocess.run([sys.executable, str(GENERATOR_PATH)] + list(arguments),
                          capture_output=True, text=True)


def replace_transition_row(number, **changes):
    return tuple(dataclasses.replace(row, **changes) if row.row == number else row
                 for row in T.TRANSITION_TABLE)


def edge_lines(lines):
    return [line for line in lines if " --> " in line and "[*]" not in line]


class TheDesignsDiagramsAreGenerated(unittest.TestCase):

    def test_the_design_s_four_views_are_what_the_generator_writes(self):
        result = run_generator("--check")
        self.assertEqual(result.returncode, 0,
                         "section 3.3 differs from the generated views; run "
                         "design-to-main-state-diagram-generator.py\n" + result.stdout + result.stderr)


class TheCheckHasTeeth(unittest.TestCase):
    """--check against copies of the design in a temporary directory."""

    def setUp(self):
        self.directory = pathlib.Path(tempfile.mkdtemp(prefix="design-to-main-diagram-test-"))
        self.copy = self.directory / "design.md"
        shutil.copyfile(generator.DESIGN_PATH, self.copy)

    def tearDown(self):
        shutil.rmtree(self.directory, ignore_errors=True)

    def test_check_fails_on_any_one_view_with_one_edge_changed_and_writes_nothing(self):
        text = self.copy.read_text()
        spans = generator.section_3_3_view_block_spans(text)
        self.assertEqual(list(spans), list(ALL_VIEWS))
        for view, (start, end) in spans.items():
            first_edge = edge_lines(text[start:end].splitlines())[0]
            altered_edge = first_edge + " changed by hand"
            altered = text[:start] + text[start:end].replace(first_edge, altered_edge, 1) + text[end:]
            self.copy.write_text(altered)
            result = run_generator("--check", "--design-file", str(self.copy))
            self.assertEqual(result.returncode, 1, view + "\n" + result.stdout + result.stderr)
            self.assertIn(altered_edge, result.stdout, view)
            self.assertEqual(self.copy.read_text(), altered, view)

    def test_writing_replaces_the_four_blocks_and_nothing_else(self):
        text = self.copy.read_text()
        spans = generator.section_3_3_view_block_spans(text)
        emptied = text
        for start, end in sorted(spans.values(), reverse=True):
            emptied = emptied[:start] + "stateDiagram-v2\n" + emptied[end:]
        self.copy.write_text(emptied)
        result = run_generator("--design-file", str(self.copy))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        rewritten = self.copy.read_text()
        self.assertEqual(rewritten, text)
        self.assertEqual(run_generator("--check", "--design-file", str(self.copy)).returncode, 0)

    def test_a_view_with_no_block_under_its_subheading_is_an_error_not_a_pass(self):
        text = self.copy.read_text()
        start, _ = generator.section_3_3_view_block_spans(text)[T.DIAGRAM_VIEW_INVESTIGATION]
        fence = text.rindex("```mermaid\n", 0, start)
        self.copy.write_text(text[:fence] + "```text\n" + text[fence + len("```mermaid\n"):])
        self.assertNotEqual(run_generator("--check", "--design-file", str(self.copy)).returncode, 0)

    def test_a_view_s_subheading_missing_is_an_error_not_a_pass(self):
        text = self.copy.read_text()
        subheading = generator.SECTION_3_3_VIEW_SUBHEADING_LINES[T.DIAGRAM_VIEW_INVESTIGATION]
        self.assertEqual(text.count("\n" + subheading + "\n"), 1)
        self.copy.write_text(text.replace("\n" + subheading + "\n", "\n"))
        self.assertNotEqual(run_generator("--check", "--design-file", str(self.copy)).returncode, 0)

    def test_a_block_left_in_section_3_3_beside_the_four_is_an_error_not_a_pass(self):
        # The single diagram section 3.3 held before the views, left behind.
        text = self.copy.read_text()
        first_subheading = generator.SECTION_3_3_VIEW_SUBHEADING_LINES[T.DIAGRAM_VIEW_MAIN_PATH]
        self.copy.write_text(text.replace(
            "\n" + first_subheading + "\n",
            "\n```mermaid\nstateDiagram-v2\n    [*] --> ended\n```\n\n" + first_subheading + "\n"))
        self.assertNotEqual(run_generator("--check", "--design-file", str(self.copy)).returncode, 0)


class EveryDrawnRowIsInExactlyOneView(unittest.TestCase):

    def test_every_row_has_a_view_the_generator_knows(self):
        known = T.DIAGRAM_VIEWS_DRAWN + (T.DIAGRAM_VIEW_NOT_DRAWN,)
        for row in T.TRANSITION_TABLE:
            self.assertIn(row.view, known, "row %s" % row.row)

    def test_a_row_with_no_view_or_an_unknown_view_is_an_error(self):
        for view in (None, "somewhere else"):
            table = replace_transition_row("56", view=view)
            for drawn_view in ALL_VIEWS:
                with self.assertRaises(generator.StateDiagramCannotBeDrawn, msg=(view, drawn_view)):
                    generator.state_diagram_view_mermaid_lines(drawn_view, table)

    def test_the_rows_not_drawn_are_the_ones_section_3_3_says(self):
        self.assertEqual(
            tuple(row.row for row in T.TRANSITION_TABLE if row.view == T.DIAGRAM_VIEW_NOT_DRAWN),
            ROWS_SECTION_3_3_DOES_NOT_DRAW)

    def test_a_drawable_row_marked_not_drawn_is_an_error_and_so_is_the_reverse(self):
        with self.assertRaises(generator.StateDiagramCannotBeDrawn):
            generator.state_diagram_view_mermaid_lines(
                T.DIAGRAM_VIEW_MAIN_PATH, replace_transition_row("56", view=T.DIAGRAM_VIEW_NOT_DRAWN))
        for row_not_drawn in ("58", "31", "60"):
            with self.assertRaises(generator.StateDiagramCannotBeDrawn, msg=row_not_drawn):
                generator.state_diagram_view_mermaid_lines(
                    T.DIAGRAM_VIEW_MAIN_PATH,
                    replace_transition_row(row_not_drawn, view=T.DIAGRAM_VIEW_MAIN_PATH))

    def test_each_view_draws_its_own_rows_and_no_others(self):
        for view in ALL_VIEWS:
            drawing = generator.state_diagram_view_drawing(view)
            self.assertEqual(
                drawing.rows_drawn(),
                {row.row for row in T.TRANSITION_TABLE if row.view == view}, view)

    def test_the_main_path_is_the_run_where_everything_advances(self):
        self.assertEqual(
            tuple(row.row for row in T.TRANSITION_TABLE if row.view == T.DIAGRAM_VIEW_MAIN_PATH),
            ROWS_OF_THE_RUN_WHERE_EVERYTHING_ADVANCES)
        self.assertEqual(len(edge_lines(
            generator.state_diagram_view_mermaid_lines(T.DIAGRAM_VIEW_MAIN_PATH))), 12)


class WhatEachViewDraws(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.lines = {view: generator.state_diagram_view_mermaid_lines(view) for view in ALL_VIEWS}
        cls.all_lines = [line for view in ALL_VIEWS for line in cls.lines[view]]

    def block(self, view, opening_line):
        lines = self.lines[view]
        start = lines.index(opening_line)
        indent = opening_line[:len(opening_line) - len(opening_line.lstrip())]
        end = lines.index(indent + "}", start)
        return lines[start + 1:end]

    def test_an_edge_is_labelled_with_its_verdict_and_in_brackets_its_guard(self):
        # The walk's own example, row 24; its "from the last acceptance-check"
        # is not drawn.
        self.assertIn("    implementation_reviewing --> test_design_writing: advance [tests not yet begun]",
                      self.lines[T.DIAGRAM_VIEW_MAIN_PATH])

    def test_several_guards_share_one_bracket_comma_separated(self):
        self.assertIn(
            "    implementation_reviewing --> test_suite_executing: "
            "advance [tests begun, the test-work-stream at ready-for-test-suite] / "
            "advance [tests begun, the test-work-stream not yet there]",
            self.lines[T.DIAGRAM_VIEW_REWORK_AND_ARBITRATION])

    def test_an_edge_with_no_guard_has_no_brackets(self):
        self.assertIn("    test_suite_executing --> submit_to_PR_gate: pass",
                      self.lines[T.DIAGRAM_VIEW_MAIN_PATH])

    def test_a_row_with_no_verdict_is_labelled_with_its_guard_alone(self):
        self.assertIn(
            "    test_suite_arbitrating --> investigate_workflow: "
            "[entered for the third time in the design version] / "
            "escalate-to-user [no investigation-focus named by the agent]",
            self.lines[T.DIAGRAM_VIEW_INVESTIGATION])

    def test_the_guards_left_off_the_label_are_the_counter_guards_and_the_from_guards(self):
        self.assertTrue(generator.guard_is_left_off_the_label(T.counter_below_ceiling("contract-revisions")))
        self.assertTrue(generator.guard_is_left_off_the_label(T.counter_at_ceiling("design-revisions")))
        self.assertTrue(generator.guard_is_left_off_the_label(
            T.counter_at_or_above_ceiling("implementation-writes")))
        self.assertTrue(generator.guard_is_left_off_the_label(T.G_WRITERS_COUNTER_AT_OR_ABOVE_CEILING))
        self.assertTrue(generator.guard_is_left_off_the_label(
            T.G_RESUME_TO_DESIGN_WRITING_AT_REDESIGNS_CEILING))
        self.assertTrue(generator.guard_is_left_off_the_label(T.G_FROM_THE_LAST_ACCEPTANCE_CHECK))
        self.assertTrue(generator.guard_is_left_off_the_label(T.G_FROM_PROGRAM_CHECK))
        self.assertTrue(generator.guard_is_left_off_the_label(T.G_FROM_AN_ACCEPTANCE_CHECK_BY_AGENT))
        self.assertFalse(generator.guard_is_left_off_the_label(T.G_TESTS_NOT_YET_BEGUN))
        self.assertFalse(generator.guard_is_left_off_the_label(
            T.G_ENTERED_FOR_THE_THIRD_TIME_IN_THE_DESIGN_VERSION))
        self.assertIn("    implementation_reviewing --> implementation_writing: reject implementation",
                      self.lines[T.DIAGRAM_VIEW_REWORK_AND_ARBITRATION])
        for line in edge_lines(self.all_lines):
            label = line.split(": ", 1)[1]
            self.assertNotIn("counter", label, line)
            self.assertNotIn("[from ", label, line)
            self.assertNotIn(", from ", label, line)

    def test_a_row_entered_from_many_states_is_drawn_once_from_a_box_around_them(self):
        view = T.DIAGRAM_VIEW_INVESTIGATION
        self.assertEqual(self.block(view, '    state "row 69\'s from-states" as row_69_from_states {'), [
            "        contract_reviewing", "        design_reviewing", "        contract_revising",
            "        implementation_reviewing", "        test_design_writing",
            "        test_design_reviewing", "        test_reviewing", "        test_suite_arbitrating",
        ])
        self.assertIn(
            "    row_69_from_states --> investigate_workflow: "
            "escalate-to-user [investigation-focus design or test-design as the agent names it]",
            self.lines[view])
        self.assertIn(
            "    row_67_from_states --> contract_acceptance_by_user: "
            "reject contract, input-quick-check-failed "
            "[a reject of, or a failed check against, the component-contract]",
            self.lines[T.DIAGRAM_VIEW_INSIDE_THE_REVIEWING_STATES])
        for line in edge_lines(self.all_lines):
            if "[investigation-focus design or test-design" in line:
                self.assertTrue(line.startswith("    row_69_from_states -->"), line)
            if "[a reject of, or a failed check against" in line:
                self.assertTrue(line.startswith("    row_67_from_states -->"), line)

    def test_a_state_in_two_boxes_in_one_view_is_an_error(self):
        # Rows 67 and 69 share five from-states; Mermaid holds a state in
        # one composite only.
        with self.assertRaises(generator.StateDiagramCannotBeDrawn):
            generator.state_diagram_view_mermaid_lines(
                T.DIAGRAM_VIEW_INVESTIGATION,
                replace_transition_row("67", view=T.DIAGRAM_VIEW_INVESTIGATION))

    def test_the_reviewing_states_are_opened_only_in_the_view_inside_them(self):
        for view in (T.DIAGRAM_VIEW_MAIN_PATH, T.DIAGRAM_VIEW_REWORK_AND_ARBITRATION,
                     T.DIAGRAM_VIEW_INVESTIGATION):
            for line in self.lines[view]:
                if line.lstrip().startswith("state "):
                    self.assertIn("_from_states {", line, view)
        view = T.DIAGRAM_VIEW_INSIDE_THE_REVIEWING_STATES
        self.assertEqual(self.block(view, "    state contract_reviewing {"), [
            "        contract_acceptance_by_program --> contract_acceptance_by_agent: "
            "advance [on a contract-revision]",
            "        contract_acceptance_by_agent --> contract_acceptance_by_user: reject contract",
        ])
        self.assertEqual(self.block(view, "        state test_design_reviewing {"), [
            "            test_design_acceptance_by_agent --> test_design_acceptance_by_user: "
            "advance / reject test-design [after the test-design's approval]",
        ])
        for state in T.STATE_TABLE:
            if state.sub_states:
                self.assertEqual(
                    sum(1 for line in self.lines[view]
                        if line.strip() == "state %s {" % generator.mermaid_identifier(state.name)),
                    1, state.name)

    def test_an_input_quick_check_failed_carries_its_guard(self):
        self.assertIn("    test_writing --> test_design_writing: input-quick-check-failed [against the test-design]",
                      self.lines[T.DIAGRAM_VIEW_REWORK_AND_ARBITRATION])
        self.assertIn("    implementation_writing --> investigate_workflow: "
                      "input-quick-check-failed [against the design]",
                      self.lines[T.DIAGRAM_VIEW_INVESTIGATION])

    def test_a_resume_is_drawn_to_each_state_an_edited_document_resumes_at(self):
        for document, state in T.RESUME_DESTINATION_BY_EDITED_DOCUMENT:
            self.assertIn("    investigate_workflow --> %s: resume [%s edited]"
                          % (generator.mermaid_identifier(state), document),
                          self.lines[T.DIAGRAM_VIEW_INVESTIGATION])

    def test_a_semicolon_in_a_guard_is_written_as_mermaid_s_entity(self):
        # Mermaid ends a statement at a raw semicolon (row 77's guard).
        self.assertTrue(any("the fifth attempt#59; or an integration or scope refusal" in line
                            for line in self.lines[T.DIAGRAM_VIEW_INVESTIGATION]))
        for line in self.all_lines:
            self.assertNotIn(";", line.replace("#59;", ""), line)

    def test_a_changed_row_changes_the_diagram(self):
        changed = generator.state_diagram_view_mermaid_lines(
            T.DIAGRAM_VIEW_MAIN_PATH, replace_transition_row("56", to_state=T.ENDED))
        self.assertIn("    test_suite_executing --> ended: pass", changed)
        self.assertNotIn("    test_suite_executing --> submit_to_PR_gate: pass", changed)

    def test_a_destination_the_generator_does_not_know_is_an_error(self):
        with self.assertRaises(generator.StateDiagramCannotBeDrawn):
            generator.state_diagram_view_mermaid_lines(
                T.DIAGRAM_VIEW_MAIN_PATH, replace_transition_row("56", to_state="somewhere new"))

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
        for line in edge_lines(self.all_lines):
            from_name, rest = line.strip().split(" --> ")
            self.assertNotEqual(from_name, rest.split(":")[0], line)
        self.assertNotIn("discuss", "\n".join(self.all_lines))
        self.assertFalse(any(line.startswith("    test_suite_arbitrating -->") and "advance" in line
                             for line in self.all_lines))

    def test_removing_a_state_s_rows_removes_its_edges(self):
        # Nothing is drawn that no row gives.
        without_submit_rows = tuple(row for row in T.TRANSITION_TABLE
                                    if T.SUBMIT_TO_PR_GATE not in row.from_states)
        for view in ALL_VIEWS:
            lines = generator.state_diagram_view_mermaid_lines(view, without_submit_rows)
            self.assertFalse(any(line.startswith("    submit_to_PR_gate -->") for line in lines), view)

    def test_hyphens_become_underscores_and_nothing_else_changes(self):
        self.assertEqual(generator.mermaid_identifier(T.SUBMIT_TO_PR_GATE), "submit_to_PR_gate")
        for line in edge_lines(self.all_lines):
            edge = line.split(":")[0]
            self.assertNotIn("-", edge.replace("-->", ""), line)

    def test_the_start_and_the_end_are_marked_where_their_states_are_drawn(self):
        main_path = self.lines[T.DIAGRAM_VIEW_MAIN_PATH]
        self.assertEqual(main_path[:2], ["stateDiagram-v2", "    [*] --> initiate_design_to_main"])
        self.assertEqual(main_path[-1], "    ended --> [*]")
        self.assertEqual(self.lines[T.DIAGRAM_VIEW_INVESTIGATION][-1], "    ended --> [*]")
        self.assertNotIn("    ended --> [*]", self.lines[T.DIAGRAM_VIEW_INSIDE_THE_REVIEWING_STATES])


if __name__ == "__main__":
    unittest.main(verbosity=2)
