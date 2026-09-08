#!/usr/bin/env python3
"""Section 3.2 of the design-to-main state-machine design: every row as a
legality case, so the table and the code cannot drift apart silently.

Each case builds a run-state, a state-exit, and names the row it expects;
the last test asserts that the cases hit every row of the design's table.
A few cases assert what the table forbids.

Run: python3 scripts/design-to-main/tests/design-to-main-transitions-test.py
"""

import importlib.util
import pathlib
import unittest

_fixture_spec = importlib.util.spec_from_file_location(
    "design_to_main_test_fixture",
    pathlib.Path(__file__).with_name("design-to-main-test-fixture.py"))
fixture = importlib.util.module_from_spec(_fixture_spec)
_fixture_spec.loader.exec_module(fixture)

T = fixture.tables
M = fixture.machine_module
RunStateRecord = fixture.run_state_module.RunStateRecord

COMMIT = "0" * 40


def run_with(counters=None, **fields):
    run = RunStateRecord("widget-counter")
    for name, value in (counters or {}).items():
        run.counters.values[name] = value
    for name, value in fields.items():
        if not hasattr(run, name):
            raise AttributeError(name)
        setattr(run, name, value)
    return run


def exit_from(state, verdict, **fields):
    return M.StateExitRecord(state=state, verdict=verdict, package_commit=COMMIT, **fields)


APPROVED = dict(design_approved=True)
IMPL_IS_SCRIPT = dict(design_approved=True, implementation_coverage_type="script")
IMPL_IS_PROMPT = dict(design_approved=True, implementation_coverage_type="prompt")
TESTS_ARE_SCRIPT = dict(design_approved=True, tests_coverage_type="script", tests_begun=True)
TESTS_ARE_PROMPT = dict(design_approved=True, tests_coverage_type="prompt", tests_begun=True)

# (expected row, run-state fields, state-exit) — one or more per row.
LEGALITY_CASES = [
    ("1", {}, exit_from(T.INITIATE_DESIGN_TO_MAIN, T.V_INVOKED)),
    ("2", {}, exit_from(T.DESIGN_WRITING, T.V_EMITTED)),
    ("3", {}, exit_from(T.CONTRACT_ACCEPTANCE_BY_PROGRAM, T.V_REJECT_CONTRACT)),
    ("4", dict(consecutive_contract_program_check_failures=1),
     exit_from(T.CONTRACT_ACCEPTANCE_BY_PROGRAM, T.V_REJECT_CONTRACT)),
    ("5", {}, exit_from(T.CONTRACT_ACCEPTANCE_BY_PROGRAM, T.V_ADVANCE)),
    ("6", APPROVED, exit_from(T.CONTRACT_ACCEPTANCE_BY_PROGRAM, T.V_ADVANCE)),
    ("7", APPROVED, exit_from(T.CONTRACT_ACCEPTANCE_BY_AGENT, T.V_REJECT_CONTRACT)),
    ("8", dict(APPROVED, counters={"contract-revisions": 1}),
     exit_from(T.CONTRACT_ACCEPTANCE_BY_AGENT, T.V_REJECT_CONTRACT)),
    ("9", APPROVED, exit_from(T.CONTRACT_ACCEPTANCE_BY_AGENT, T.V_ADVANCE)),
    ("9", dict(APPROVED, counters={"contract-revisions": 1}),
     exit_from(T.CONTRACT_ACCEPTANCE_BY_USER, T.V_ADVANCE)),
    ("10", dict(APPROVED, counters={"contract-revisions": 1}),
     exit_from(T.CONTRACT_ACCEPTANCE_BY_USER, T.V_DISCUSS)),
    ("12", {}, exit_from(T.DESIGN_ACCEPTANCE_BY_AGENT, T.V_REJECT_DESIGN)),
    ("13", dict(counters={"design-revisions": 2}),
     exit_from(T.DESIGN_ACCEPTANCE_BY_AGENT, T.V_REJECT_DESIGN)),
    ("14", {}, exit_from(T.DESIGN_ACCEPTANCE_BY_AGENT, T.V_REJECT_CONTRACT)),
    ("15", dict(counters={"design-revisions": 2}),
     exit_from(T.DESIGN_ACCEPTANCE_BY_AGENT, T.V_REJECT_CONTRACT)),
    ("17", {}, exit_from(T.DESIGN_ACCEPTANCE_BY_USER, T.V_DISCUSS)),
    ("18", {}, exit_from(T.DESIGN_ACCEPTANCE_BY_USER, T.V_ADVANCE)),
    ("19", APPROVED, exit_from(T.CONTRACT_REVISING, T.V_EMITTED)),
    ("20", APPROVED, exit_from(T.CONTRACT_REVISING, T.V_INPUT_QUICK_CHECK_FAILED,
                               input_named=T.INPUT_DESIGN)),
    ("21", APPROVED, exit_from(T.IMPLEMENTATION_WRITING, T.V_EMITTED, coverage_type="script")),
    ("22", APPROVED, exit_from(T.IMPLEMENTATION_WRITING, T.V_INPUT_QUICK_CHECK_FAILED,
                               input_named=T.INPUT_COMPONENT_CONTRACT)),
    ("23", APPROVED, exit_from(T.IMPLEMENTATION_WRITING, T.V_INPUT_QUICK_CHECK_FAILED,
                               input_named=T.INPUT_DESIGN)),
    ("24", IMPL_IS_SCRIPT, exit_from(T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_ADVANCE)),
    ("24", IMPL_IS_PROMPT, exit_from(T.IMPLEMENTATION_ACCEPTANCE_BY_USER, T.V_ADVANCE)),
    ("25", dict(IMPL_IS_SCRIPT, tests_begun=True,
                test_work_stream_position=T.READY_FOR_TEST_SUITE),
     exit_from(T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_ADVANCE)),
    ("26", dict(IMPL_IS_SCRIPT, tests_begun=True, test_work_stream_position=T.TEST_WRITING),
     exit_from(T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_ADVANCE)),
    ("27", IMPL_IS_SCRIPT, exit_from(T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_REJECT_IMPLEMENTATION)),
    ("28", dict(IMPL_IS_SCRIPT, counters={"implementation-writes": 3}),
     exit_from(T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_REJECT_IMPLEMENTATION)),
    ("29", IMPL_IS_SCRIPT, exit_from(T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_REJECT_CONTRACT)),
    ("30", IMPL_IS_SCRIPT, exit_from(T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_REJECT_DESIGN)),
    ("31", IMPL_IS_PROMPT, exit_from(T.IMPLEMENTATION_ACCEPTANCE_BY_USER, T.V_DISCUSS)),
    ("32", APPROVED, exit_from(T.TEST_DESIGN_WRITING, T.V_EMITTED)),
    ("33", APPROVED, exit_from(T.TEST_DESIGN_WRITING, T.V_INPUT_QUICK_CHECK_FAILED,
                               input_named=T.INPUT_COMPONENT_CONTRACT)),
    ("34", APPROVED, exit_from(T.TEST_DESIGN_WRITING, T.V_INPUT_QUICK_CHECK_FAILED,
                               input_named=T.INPUT_DESIGN)),
    ("35", APPROVED, exit_from(T.TEST_DESIGN_ACCEPTANCE_BY_AGENT, T.V_REJECT_TEST_DESIGN)),
    ("36", APPROVED, exit_from(T.TEST_DESIGN_ACCEPTANCE_BY_AGENT, T.V_REJECT_CONTRACT)),
    ("37", APPROVED, exit_from(T.TEST_DESIGN_ACCEPTANCE_BY_USER, T.V_REJECT_DESIGN)),
    ("38", APPROVED, exit_from(T.TEST_DESIGN_ACCEPTANCE_BY_USER, T.V_DISCUSS)),
    ("39", APPROVED, exit_from(T.TEST_DESIGN_ACCEPTANCE_BY_USER, T.V_ADVANCE)),
    ("40", APPROVED, exit_from(T.TEST_WRITING, T.V_EMITTED, coverage_type="prompt")),
    ("41", APPROVED, exit_from(T.TEST_WRITING, T.V_INPUT_QUICK_CHECK_FAILED,
                               input_named=T.INPUT_TEST_DESIGN)),
    ("42", dict(APPROVED, counters={"test-design-corrections": 1}),
     exit_from(T.TEST_WRITING, T.V_INPUT_QUICK_CHECK_FAILED, input_named=T.INPUT_TEST_DESIGN)),
    ("43", APPROVED, exit_from(T.TEST_WRITING, T.V_INPUT_QUICK_CHECK_FAILED,
                               input_named=T.INPUT_COMPONENT_CONTRACT)),
    ("44", APPROVED, exit_from(T.TEST_WRITING, T.V_INPUT_QUICK_CHECK_FAILED,
                               input_named=T.INPUT_DESIGN)),
    ("45", dict(TESTS_ARE_SCRIPT, implementation_work_stream_position=T.READY_FOR_TEST_SUITE),
     exit_from(T.TEST_ACCEPTANCE_BY_AGENT, T.V_ADVANCE)),
    ("45", dict(TESTS_ARE_PROMPT, implementation_work_stream_position=T.READY_FOR_TEST_SUITE),
     exit_from(T.TEST_ACCEPTANCE_BY_USER, T.V_ADVANCE)),
    ("46", dict(TESTS_ARE_SCRIPT, implementation_work_stream_position=T.IMPLEMENTATION_WRITING),
     exit_from(T.TEST_ACCEPTANCE_BY_AGENT, T.V_ADVANCE)),
    ("47", TESTS_ARE_SCRIPT, exit_from(T.TEST_ACCEPTANCE_BY_AGENT, T.V_REJECT_TESTS)),
    ("48", dict(TESTS_ARE_SCRIPT, counters={"test-writes": 3}),
     exit_from(T.TEST_ACCEPTANCE_BY_AGENT, T.V_REJECT_TESTS)),
    ("49", TESTS_ARE_SCRIPT, exit_from(T.TEST_ACCEPTANCE_BY_AGENT, T.V_REJECT_TEST_DESIGN)),
    ("50", dict(TESTS_ARE_SCRIPT, counters={"test-design-corrections": 1}),
     exit_from(T.TEST_ACCEPTANCE_BY_AGENT, T.V_REJECT_TEST_DESIGN)),
    ("51", TESTS_ARE_SCRIPT, exit_from(T.TEST_ACCEPTANCE_BY_AGENT, T.V_REJECT_CONTRACT)),
    ("52", TESTS_ARE_SCRIPT, exit_from(T.TEST_ACCEPTANCE_BY_AGENT, T.V_REJECT_DESIGN)),
    ("53", TESTS_ARE_PROMPT, exit_from(T.TEST_ACCEPTANCE_BY_USER, T.V_DISCUSS)),
    ("54", {}, exit_from(T.TEST_SUITE_EXECUTING, T.V_PASS)),
    ("55", {}, exit_from(T.TEST_SUITE_EXECUTING, T.V_FAIL)),
    ("56", {}, exit_from(T.TEST_SUITE_EXECUTING, T.V_COULD_NOT_RUN)),
    ("57", dict(consecutive_could_not_run_count=1), exit_from(T.TEST_SUITE_EXECUTING, T.V_COULD_NOT_RUN)),
    ("58", {}, exit_from(T.TEST_SUITE_ARBITRATING, T.V_ADVANCE)),
    ("59", dict(counters={"implementation-writes": 2}),
     exit_from(T.TEST_SUITE_ARBITRATING, T.V_REJECT_IMPLEMENTATION)),
    ("60", dict(counters={"test-writes": 2}), exit_from(T.TEST_SUITE_ARBITRATING, T.V_REJECT_TESTS)),
    ("60", dict(counters={"test-writes": 2}), exit_from(T.TEST_SUITE_ARBITRATING, T.V_FLAKY_TEST)),
    ("61", dict(counters={"implementation-writes": 3}),
     exit_from(T.TEST_SUITE_ARBITRATING, T.V_REJECT_IMPLEMENTATION)),
    ("61", dict(counters={"test-writes": 3}), exit_from(T.TEST_SUITE_ARBITRATING, T.V_REJECT_TESTS)),
    ("61", dict(counters={"test-writes": 3}), exit_from(T.TEST_SUITE_ARBITRATING, T.V_FLAKY_TEST)),
    ("64", {}, exit_from(T.TEST_SUITE_ARBITRATING, T.V_REJECT_CONTRACT)),
    ("66", {}, exit_from(T.TEST_SUITE_ARBITRATING, T.V_ESCALATE_TO_USER)),
    ("66", {}, exit_from(T.TEST_SUITE_ARBITRATING, T.V_ESCALATE_TO_USER,
                         investigation_focus=T.FOCUS_UNKNOWN)),
    ("67", {}, exit_from(T.TEST_SUITE_ARBITRATING, T.V_ESCALATE_TO_USER,
                         investigation_focus=T.FOCUS_DESIGN)),
    ("67", {}, exit_from(T.DESIGN_ACCEPTANCE_BY_AGENT, T.V_ESCALATE_TO_USER,
                         investigation_focus=T.FOCUS_DESIGN)),
    ("67", APPROVED, exit_from(T.CONTRACT_ACCEPTANCE_BY_AGENT, T.V_ESCALATE_TO_USER,
                               investigation_focus=T.FOCUS_DESIGN)),
    ("67", IMPL_IS_SCRIPT, exit_from(T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_ESCALATE_TO_USER,
                                     investigation_focus=T.FOCUS_DESIGN)),
    ("67", APPROVED, exit_from(T.TEST_DESIGN_ACCEPTANCE_BY_AGENT, T.V_ESCALATE_TO_USER,
                               investigation_focus=T.FOCUS_TEST_DESIGN)),
    ("67", TESTS_ARE_SCRIPT, exit_from(T.TEST_ACCEPTANCE_BY_AGENT, T.V_ESCALATE_TO_USER,
                                       investigation_focus=T.FOCUS_TEST_DESIGN)),
    ("67", APPROVED, exit_from(T.CONTRACT_REVISING, T.V_ESCALATE_TO_USER,
                               investigation_focus=T.FOCUS_DESIGN)),
    ("67", APPROVED, exit_from(T.TEST_DESIGN_WRITING, T.V_ESCALATE_TO_USER,
                               investigation_focus=T.FOCUS_TEST_DESIGN)),
    ("68", {}, exit_from(T.INVESTIGATE_WORKFLOW, T.V_STOP)),
    ("69", {}, exit_from(T.INVESTIGATE_WORKFLOW, T.V_SUBMIT_TO_PR_GATE)),
    ("72", {}, exit_from(T.SUBMIT_TO_PR_GATE, T.V_ACCEPTED)),
    ("73", {}, exit_from(T.SUBMIT_TO_PR_GATE, T.V_GATE_REJECTION)),
    ("74", {}, exit_from(T.SUBMIT_TO_PR_GATE, T.V_GATEKEEPER_REFUSAL,
                         refusal_class=T.REFUSAL_INFRASTRUCTURE)),
    ("74", dict(submit_retry_count=3), exit_from(T.SUBMIT_TO_PR_GATE, T.V_GATEKEEPER_REFUSAL,
                                                refusal_class=T.REFUSAL_INFRASTRUCTURE)),
    ("75", dict(submit_retry_count=4), exit_from(T.SUBMIT_TO_PR_GATE, T.V_GATEKEEPER_REFUSAL,
                                                refusal_class=T.REFUSAL_INFRASTRUCTURE)),
    ("75", {}, exit_from(T.SUBMIT_TO_PR_GATE, T.V_GATEKEEPER_REFUSAL, refusal_class=T.REFUSAL_INTEGRATION)),
    ("75", {}, exit_from(T.SUBMIT_TO_PR_GATE, T.V_GATEKEEPER_REFUSAL, refusal_class=T.REFUSAL_SCOPE)),
    ("76", {}, exit_from(T.SUBMIT_TO_PR_GATE, T.V_GATEKEEPER_REFUSAL, refusal_class=T.REFUSAL_FORM)),
    # Section 3.1's order of sub-states.
    ("3.1-a", {}, exit_from(T.DESIGN_ACCEPTANCE_BY_AGENT, T.V_ADVANCE)),
    ("3.1-b", IMPL_IS_PROMPT, exit_from(T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_ADVANCE)),
    ("3.1-c", APPROVED, exit_from(T.TEST_DESIGN_ACCEPTANCE_BY_AGENT, T.V_ADVANCE)),
    ("3.1-d", dict(TESTS_ARE_PROMPT, implementation_work_stream_position=T.READY_FOR_TEST_SUITE),
     exit_from(T.TEST_ACCEPTANCE_BY_AGENT, T.V_ADVANCE)),
]

# The resume rows take the resolved destination.
RESUME_CASES = [
    ("70", {}, exit_from(T.INVESTIGATE_WORKFLOW, T.V_RESUME), T.IMPLEMENTATION_REVIEWING),
    ("70", dict(counters={"redesigns": 1}), exit_from(T.INVESTIGATE_WORKFLOW, T.V_RESUME), T.DESIGN_WRITING),
    ("70", dict(counters={"redesigns": 2}), exit_from(T.INVESTIGATE_WORKFLOW, T.V_RESUME), T.TEST_REVIEWING),
    ("71", dict(counters={"redesigns": 2}),
     exit_from(T.INVESTIGATE_WORKFLOW, T.V_RESUME, destination=T.DESIGN_WRITING), T.DESIGN_WRITING),
]

ILLEGAL_CASES = [
    ("a reviewer rejecting an artifact it does not review",
     IMPL_IS_SCRIPT, exit_from(T.DESIGN_ACCEPTANCE_BY_AGENT, T.V_REJECT_IMPLEMENTATION)),
    ("the user's check escalating: only agents escalate",
     {}, exit_from(T.DESIGN_ACCEPTANCE_BY_USER, T.V_ESCALATE_TO_USER, investigation_focus=T.FOCUS_DESIGN)),
    ("implementation-writing escalating: writers of code never do",
     APPROVED, exit_from(T.IMPLEMENTATION_WRITING, T.V_ESCALATE_TO_USER, investigation_focus=T.FOCUS_DESIGN)),
    ("an input-quick-check-failed naming no input",
     APPROVED, exit_from(T.IMPLEMENTATION_WRITING, T.V_INPUT_QUICK_CHECK_FAILED)),
    ("the contract's program check advancing straight to the agent check before approval",
     {}, exit_from(T.CONTRACT_ACCEPTANCE_BY_PROGRAM, T.V_ADVANCE, destination=T.CONTRACT_ACCEPTANCE_BY_AGENT)),
    ("a destination that is not the row's",
     {}, exit_from(T.TEST_SUITE_EXECUTING, T.V_PASS, destination=T.ENDED)),
    ("a verdict no state has",
     {}, exit_from(T.TEST_SUITE_EXECUTING, "green")),
    ("the terminal state emitting anything",
     {}, exit_from(T.ENDED, T.V_ADVANCE)),
]


class EveryRowOfSection32(unittest.TestCase):

    def test_each_legality_case_finds_its_row(self):
        for expected_row, fields, state_exit in LEGALITY_CASES:
            with self.subTest(row=expected_row, state=state_exit.state, verdict=state_exit.verdict):
                row = M.find_legal_transition_row(run_with(**fields), state_exit)
                self.assertEqual(row.row, expected_row)

    def test_the_resume_rows(self):
        for expected_row, fields, state_exit, destination in RESUME_CASES:
            with self.subTest(row=expected_row, destination=destination):
                row = M.find_legal_transition_row(run_with(**fields), state_exit, destination)
                self.assertEqual(row.row, expected_row)

    def test_what_the_table_forbids(self):
        for name, fields, state_exit in ILLEGAL_CASES:
            with self.subTest(case=name):
                with self.assertRaises(M.IllegalStateExit):
                    M.find_legal_transition_row(run_with(**fields), state_exit)

    def test_a_named_destination_that_is_the_row_s_is_accepted(self):
        state_exit = exit_from(T.TEST_SUITE_EXECUTING, T.V_PASS, destination=T.SUBMIT_TO_PR_GATE)
        self.assertEqual(M.find_legal_transition_row(run_with(), state_exit).row, "54")

    def test_the_cases_cover_every_row_of_the_design_s_table(self):
        hit = {row for row, _, _ in LEGALITY_CASES} | {row for row, _, _, _ in RESUME_CASES}
        design_rows = set(T.DESIGN_TRANSITION_ROWS)
        self.assertEqual(design_rows - hit, set(), "rows of section 3.2 with no legality case")
        self.assertEqual(hit - set(T.TRANSITION_TABLE_BY_ROW), set(), "cases naming no row")

    def test_the_rows_are_numbered_in_the_design_s_order(self):
        numbers = [r.row for r in T.TRANSITION_TABLE if r.source == "3.2"]
        self.assertEqual(numbers[0], "1")
        self.assertEqual(numbers[-1], "76")
        self.assertEqual(numbers, sorted(numbers, key=int))

    def test_every_guard_named_in_the_table_has_a_predicate(self):
        for row in T.TRANSITION_TABLE:
            for guard in row.guards:
                self.assertIn(guard, M.GUARD_PREDICATES, "row %s" % row.row)

    def test_every_verdict_in_the_transition_table_is_one_the_state_lists(self):
        for row in T.TRANSITION_TABLE:
            for from_state in row.from_states:
                listed = set(T.STATE_TABLE_BY_NAME[from_state].verdicts)
                if from_state in (T.CONTRACT_REVISING, T.TEST_DESIGN_WRITING,
                                  T.TEST_SUITE_ARBITRATING) or T.STATE_TABLE_BY_NAME[from_state].work == "composite":
                    listed.add(T.V_ESCALATE_TO_USER)
                for verdict in row.verdicts:
                    self.assertIn(verdict, listed, "row %s, %s" % (row.row, from_state))

    def test_the_counters_the_rows_charge_are_section_7_s(self):
        charged = {row.counter for row in T.TRANSITION_TABLE if row.counter}
        charged |= set(T.COUNTER_CHARGED_ON_ENTRY.values())
        self.assertEqual(charged, set(T.COUNTER_NAMES))


class WithinTheMachine(unittest.TestCase):
    """The check as the machine applies it: a stale state-exit is discarded
    and the state re-run; an illegal one is a machine error that pauses
    the run in investigate-workflow."""

    def setUp(self):
        self.repository = fixture.ThrowawayRepository()

    def tearDown(self):
        self.repository.remove()

    def test_a_stale_state_exit_is_discarded_and_the_state_re_run(self):
        script = fixture.prefix_to_design_approved() + [
            (T.IMPLEMENTATION_WRITING, T.V_EMITTED,
             {"coverage_type": "script", "package_commit": "f" * 40}),
            fixture.implementation_write(),
        ]
        machine, run, _, _ = fixture.make_machine(script, self.repository)
        fixture.drive(machine, run)
        self.assertEqual(len(machine.discarded), 1)
        self.assertEqual(run.current_state, T.IMPLEMENTATION_REVIEWING)
        self.assertEqual(run.counters.value("implementation-writes"), 1)
        self.assertEqual(
            sum(1 for p in machine.launcher.launched if p["state"] == T.IMPLEMENTATION_WRITING), 2)

    def test_an_illegal_state_exit_pauses_the_run_in_investigate_workflow(self):
        script = fixture.prefix_to_design_approved() + [
            (T.IMPLEMENTATION_WRITING, T.V_ESCALATE_TO_USER, {"investigation_focus": T.FOCUS_DESIGN}),
        ]
        machine, run, record, _ = fixture.make_machine(script, self.repository)
        fixture.drive(machine, run)
        self.assertEqual(run.current_state, T.INVESTIGATE_WORKFLOW)
        self.assertEqual(run.investigation_focus, T.FOCUS_UNKNOWN)
        self.assertEqual(run.paused_state, T.IMPLEMENTATION_WRITING)
        self.assertEqual(len(machine.machine_errors), 1)
        # The illegal state-exit is committed like any other (section 9).
        trailer = fixture.git_record_module.parse_state_exit_trailer(
            record.commit_message("HEAD"))
        self.assertEqual(trailer["State"], T.IMPLEMENTATION_WRITING)
        self.assertEqual(trailer["Exit"], T.V_ESCALATE_TO_USER)


if __name__ == "__main__":
    unittest.main(verbosity=2)
