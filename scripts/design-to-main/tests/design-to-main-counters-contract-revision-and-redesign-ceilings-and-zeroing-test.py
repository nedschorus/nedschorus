#!/usr/bin/env python3
"""Section 7 of the design-to-main state-machine design: the counters,
driven through the machine — the contract-revisions and redesigns
ceilings and what happens there, and what a redesign, a resume and the
user-ruling `zero-all-run-counters-including-redesigns` zero.

The counters cases are split over two files,
design-to-main-counters-*-test.py, so that the suite runner runs them at
the same time.

Run: python3 scripts/design-to-main/tests/design-to-main-counters-contract-revision-and-redesign-ceilings-and-zeroing-test.py
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


class ContractRevisionsRedesignsAndZeroingAllRunCountersDrivenThroughTheMachine(
        fixture.EachTestDrivesTheMachineOverItsOwnThrowawayRepository, unittest.TestCase):
    """The contract-revisions and redesigns ceilings reached by a scripted
    run, and what the machine does there; and what a redesign, a resume
    and the user-ruling zero-all-run-counters-including-redesigns zero."""

    def test_contract_revisions_the_user_sees_the_contract_before_a_second_revision(self):
        script = fixture.prefix_to_design_approved() + [
            fixture.implementation_write(),
            (T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_REJECT_CONTRACT, {}),  # revision 1
            (T.CONTRACT_REVISING, T.V_EMITTED, {}),
            (T.CONTRACT_ACCEPTANCE_BY_PROGRAM, T.V_ADVANCE, {}),
            (T.CONTRACT_ACCEPTANCE_BY_AGENT, T.V_REJECT_CONTRACT, {}),        # row 8: at the ceiling
        ]
        machine, run, _ = self.drive(script)
        self.assertEqual(run.counters.value("contract-revisions"), 1)
        self.assertEqual(run.current_state, T.CONTRACT_ACCEPTANCE_BY_USER)
        self.assertEqual(machine.routed[-1][0].row, "8")

    def test_the_user_s_discuss_on_the_contract_is_not_counted(self):
        script = fixture.prefix_to_design_approved() + [
            fixture.implementation_write(),
            (T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_REJECT_CONTRACT, {}),
            (T.CONTRACT_REVISING, T.V_EMITTED, {}),
            (T.CONTRACT_ACCEPTANCE_BY_PROGRAM, T.V_ADVANCE, {}),
            (T.CONTRACT_ACCEPTANCE_BY_AGENT, T.V_REJECT_CONTRACT, {}),
            (T.CONTRACT_ACCEPTANCE_BY_USER, T.V_DISCUSS, {}),                 # row 10
        ]
        machine, run, _ = self.drive(script)
        self.assertEqual(run.current_state, T.CONTRACT_REVISING)
        self.assertEqual(run.counters.value("contract-revisions"), 1)

    def contract_reaches_the_user(self):
        return fixture.prefix_to_design_approved() + [
            fixture.implementation_write(),
            (T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_REJECT_CONTRACT, {}),  # row 29
            (T.CONTRACT_REVISING, T.V_EMITTED, {}),
            (T.CONTRACT_ACCEPTANCE_BY_PROGRAM, T.V_ADVANCE, {}),
            (T.CONTRACT_ACCEPTANCE_BY_AGENT, T.V_REJECT_CONTRACT, {}),        # row 8
        ]

    def test_row_11_redesign_ordered_by_user_after_contract_failed_twice_opens_the_redesign_through_the_investigation(self):
        script = self.contract_reaches_the_user() + [
            (T.CONTRACT_ACCEPTANCE_BY_USER,
             T.V_REDESIGN_ORDERED_BY_USER_AFTER_CONTRACT_FAILED_TWICE, {}),  # row 11
        ]
        machine, run, _ = self.drive(script)
        self.assertEqual(machine.routed[-1][0].row, "11")
        self.assertEqual(run.current_state, T.INVESTIGATE_WORKFLOW)
        self.assertEqual(run.investigation_focus, T.FOCUS_CONTRACT)
        self.assertEqual(run.investigation_opened_by_row, "11")
        self.assertEqual(run.counters.value("redesigns"), 0)                   # counted on entry, not here
        # A plain resume applies the destination the ruling held:
        # design-writing as a redesign, not the contract check it left.
        machine.launcher.script += [(T.INVESTIGATE_WORKFLOW, T.V_RESUME, {})]
        fixture.drive(machine, run)
        self.assertEqual(machine.routed[-1][0].row, "72")
        self.assertEqual(run.current_state, T.DESIGN_WRITING)
        self.assertEqual(run.design_version, 2)
        self.assertEqual(run.counters.value("redesigns"), 1)
        self.assertEqual(run.counters.value("contract-revisions"), 0)
        self.assertEqual(
            sum(1 for p in machine.launcher.launched if p["state"] == T.CONTRACT_ACCEPTANCE_BY_USER), 1)

    def test_row_11_at_the_redesigns_ceiling_the_resume_ends_the_run_failed(self):
        script = self.contract_reaches_the_user() + [
            (T.CONTRACT_ACCEPTANCE_BY_USER, T.V_REDESIGN_ORDERED_BY_USER_AFTER_CONTRACT_FAILED_TWICE, {}),
            (T.INVESTIGATE_WORKFLOW, T.V_RESUME, {}),
        ]
        machine, run, _ = self.drive(script)
        self.assertEqual(run.current_state, T.DESIGN_WRITING)
        run.counters.values["redesigns"] = 2        # as after two redesigns
        machine.launcher.script += self.contract_reaches_the_user()[1:] + [
            (T.CONTRACT_ACCEPTANCE_BY_USER, T.V_REDESIGN_ORDERED_BY_USER_AFTER_CONTRACT_FAILED_TWICE, {}),
            (T.INVESTIGATE_WORKFLOW, T.V_RESUME, {}),                          # row 73
        ]
        fixture.drive(machine, run)
        self.assertEqual(machine.routed[-1][0].row, "73")
        self.assertEqual(run.current_state, T.ENDED)
        self.assertEqual(run.outcome, T.OUTCOME_FAILED)

    def test_redesigns_reset_the_version_and_keep_the_redesigns_counter(self):
        script = fixture.prefix_to_tests_begun() + [
            (T.TEST_DESIGN_WRITING, T.V_INPUT_QUICK_CHECK_FAILED, {"input_named": T.INPUT_DESIGN}),  # row 34
            (T.INVESTIGATE_WORKFLOW, T.V_RESUME, {"destination": T.DESIGN_WRITING}),               # row 72
        ]
        machine, run, _ = self.drive(script)
        self.assertEqual(run.current_state, T.DESIGN_WRITING)
        self.assertEqual(run.design_version, 2)
        self.assertEqual(run.counters.value("redesigns"), 1)
        self.assertEqual(run.counters.value("implementation-writes"), 0)
        self.assertFalse(run.tests_begun)
        self.assertFalse(run.design_approved)
        self.assertIsNone(run.implementation_work_stream_position)
        self.assertIsNone(run.test_work_stream_position)

    def test_a_redesign_resets_all_six_per_version_counters_the_approvals_the_positions_and_the_entry_reasons(self):
        # Section 3.2, "A redesign resets the version", as the seventh walk
        # worded it: the six per-version counters by name, tests-begun,
        # both positions, the approvals, and every state's entry reason;
        # the redesigns counter does not reset.
        script = fixture.prefix_to_test_writing() + [
            fixture.test_write(),
            (T.TEST_ACCEPTANCE_BY_AGENT, T.V_REJECT_DESIGN, {}),                  # row 54
        ]
        machine, run, _ = self.drive(script)
        run.counters.values.update({
            "design-revisions": 1, "implementation-writes": 2, "test-writes": 1,
            "contract-revisions": 1, "test-design-corrections": 1, "arbitrator-rulings": 1})
        self.assertTrue(run.design_approved and run.test_design_approved and run.tests_begun)
        self.assertEqual(set(run.writing_state_entry_reason),
                         {T.IMPLEMENTATION_WRITING, T.TEST_DESIGN_WRITING, T.TEST_WRITING})
        machine.launcher.script += [(T.INVESTIGATE_WORKFLOW, T.V_RESUME, {"destination": T.DESIGN_WRITING})]
        fixture.drive(machine, run)
        self.assertEqual(run.design_version, 2)
        self.assertEqual(run.counters.as_dict(), {
            "redesigns": 1, "design-revisions": 0, "implementation-writes": 0, "test-writes": 0,
            "arbitrator-rulings": 0, "contract-revisions": 0, "test-design-corrections": 0})
        self.assertFalse(run.tests_begun)
        self.assertFalse(run.design_approved)
        self.assertFalse(run.test_design_approved)
        self.assertIsNone(run.implementation_work_stream_position)
        self.assertIsNone(run.test_work_stream_position)
        self.assertEqual(run.writing_state_entry_reason, {})
        self.assertEqual(run.writes_emitted_per_version, {})

    def test_a_resume_zeroes_the_six_per_version_counters_and_never_the_redesigns_counter(self):
        # Section 7 and row 72 after the eighth walk (user-ruled
        # 2026-09-09, "if I intervene all the agents get their chance
        # again"): every resume zeroes the six per-version counters, as a
        # redesign does; the redesigns counter still needs the user-ruling
        # zero-all-run-counters-including-redesigns. The resume's commit trailer shows the zeroed
        # counters.
        script = fixture.prefix_to_test_writing() + [
            fixture.test_write(),
            (T.TEST_ACCEPTANCE_BY_AGENT, T.V_REJECT_DESIGN, {}),                  # row 54
        ]
        machine, run, record = self.drive(script)
        self.assertEqual(run.current_state, T.INVESTIGATE_WORKFLOW)
        run.counters.values.update({
            "redesigns": 1, "design-revisions": 1, "implementation-writes": 2, "test-writes": 1,
            "contract-revisions": 1, "test-design-corrections": 1, "arbitrator-rulings": 1})
        machine.launcher.script.append((T.INVESTIGATE_WORKFLOW, T.V_RESUME, {}))   # row 72
        fixture.drive(machine, run)
        self.assertEqual(machine.routed[-1][0].row, "72")
        self.assertEqual(run.current_state, T.TEST_REVIEWING)        # the paused state, re-run
        self.assertEqual(run.design_version, 1)
        self.assertEqual(run.counters.as_dict(), {
            "redesigns": 1, "design-revisions": 0, "implementation-writes": 0, "test-writes": 0,
            "arbitrator-rulings": 0, "contract-revisions": 0, "test-design-corrections": 0})
        trailer = fixture.git_record_module.parse_state_exit_trailer(record.commit_message("HEAD"))
        self.assertEqual(trailer["Exit"], T.V_RESUME)
        self.assertEqual(trailer["Counter-redesigns"], "1")
        for name in T.COUNTER_NAMES:
            if name != "redesigns":
                self.assertEqual(trailer["Counter-%s" % name], "0", name)

    def test_a_refused_resume_zeroes_nothing(self):
        # Refused whole (section 9): the counters stand as they were.
        script = fixture.prefix_to_test_writing() + [
            fixture.test_write(),
            (T.TEST_ACCEPTANCE_BY_AGENT, T.V_REJECT_DESIGN, {}),                  # row 54
            (T.INVESTIGATE_WORKFLOW, T.V_RESUME, {"destination": T.ENDED}),        # refused
        ]
        machine, run, record = self.drive(script)
        self.assertEqual(len(machine.machine_errors), 1)
        self.assertEqual(run.counters.value("test-writes"), 1)

    def test_redesigns_at_the_ceiling_a_third_is_refused_and_the_run_fails(self):
        redesign_round = [
            (T.DESIGN_WRITING, T.V_EMITTED, {}),
            (T.CONTRACT_ACCEPTANCE_BY_PROGRAM, T.V_ADVANCE, {}),
            (T.DESIGN_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {}),
            (T.DESIGN_ACCEPTANCE_BY_USER, T.V_ADVANCE, {}),
            (T.IMPLEMENTATION_WRITING, T.V_INPUT_QUICK_CHECK_FAILED, {"input_named": T.INPUT_DESIGN}),
            (T.INVESTIGATE_WORKFLOW, T.V_RESUME, {"destination": T.DESIGN_WRITING}),
        ]
        script = [(T.INITIATE_DESIGN_TO_MAIN, T.V_INVOKED, {})] + redesign_round * 3
        machine, run, _ = self.drive(script)
        self.assertEqual(run.counters.value("redesigns"), 2)
        self.assertEqual(run.current_state, T.ENDED)
        self.assertEqual(run.outcome, T.OUTCOME_FAILED)
        self.assertEqual(machine.routed[-1][0].row, "73")

    def test_zero_all_run_counters_including_redesigns_lifts_the_redesigns_ceiling_and_is_recorded_as_a_ruling(self):
        redesign_round = [
            (T.DESIGN_WRITING, T.V_EMITTED, {}),
            (T.CONTRACT_ACCEPTANCE_BY_PROGRAM, T.V_ADVANCE, {}),
            (T.DESIGN_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {}),
            (T.DESIGN_ACCEPTANCE_BY_USER, T.V_ADVANCE, {}),
            (T.IMPLEMENTATION_WRITING, T.V_INPUT_QUICK_CHECK_FAILED, {"input_named": T.INPUT_DESIGN}),
            (T.INVESTIGATE_WORKFLOW, T.V_RESUME, {"destination": T.DESIGN_WRITING}),
        ]
        script = [(T.INITIATE_DESIGN_TO_MAIN, T.V_INVOKED, {})] + redesign_round * 2
        script += redesign_round[:-1] + [
            (T.INVESTIGATE_WORKFLOW, T.V_RESUME,
             {"destination": T.DESIGN_WRITING,
              "rulings": (T.RULING_ZERO_ALL_RUN_COUNTERS_INCLUDING_REDESIGNS,)}),
        ]
        machine, run, record = self.drive(script)
        self.assertEqual(run.current_state, T.DESIGN_WRITING)
        self.assertEqual(run.design_version, 4)
        self.assertEqual(run.counters.value("redesigns"), 1)   # zeroed, then this redesign
        rulings = record.absolute(record.user_rulings_path).read_text()
        self.assertIn("- %s (user-ruled 2026-09-08)" % T.RULING_ZERO_ALL_RUN_COUNTERS_INCLUDING_REDESIGNS,
                      rulings)

    def test_contract_revisions_a_second_reject_from_any_state_goes_to_the_user_by_row_66(self):
        # Rows 22, 29, 33, 38, 45, 53 and 66 send a reject of the contract
        # to contract-revising only below the ceiling; at the ceiling the
        # reject goes to contract-acceptance-by-user by row 67, whichever
        # state rejects — here the implementation's reviewer, then the
        # test-design's writer — and no second revision is written.
        reject_contract_round = [
            (T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_REJECT_CONTRACT, {}),   # row 29
            (T.CONTRACT_REVISING, T.V_EMITTED, {}),
            (T.CONTRACT_ACCEPTANCE_BY_PROGRAM, T.V_ADVANCE, {}),
            (T.CONTRACT_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {}),                 # row 9
            fixture.implementation_write(),
        ]
        script = fixture.prefix_to_design_approved() + [fixture.implementation_write()]
        script += reject_contract_round
        script += [(T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_REJECT_CONTRACT, {})]  # row 67
        machine, run, _ = self.drive(script)
        self.assertEqual(run.counters.value("contract-revisions"), 1)
        self.assertEqual(run.current_state, T.CONTRACT_ACCEPTANCE_BY_USER)
        self.assertEqual(machine.routed[-1][0].row, "67")
        self.assertEqual(machine.machine_errors, [])
        # The user advances the revision as it stands (row 9): both
        # work-streams re-enter, and the run goes on.
        machine.launcher.script += [(T.CONTRACT_ACCEPTANCE_BY_USER, T.V_ADVANCE, {})]
        fixture.drive(machine, run)
        self.assertEqual(machine.routed[-1][0].row, "9")
        self.assertEqual(run.current_state, T.IMPLEMENTATION_WRITING)

        script = fixture.prefix_to_tests_begun() + [
            (T.TEST_DESIGN_WRITING, T.V_INPUT_QUICK_CHECK_FAILED,
             {"input_named": T.INPUT_DESIGN_CONTRACT}),                    # row 33
            (T.CONTRACT_REVISING, T.V_EMITTED, {}),
            (T.CONTRACT_ACCEPTANCE_BY_PROGRAM, T.V_ADVANCE, {}),
            (T.CONTRACT_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {}),                 # row 9
            fixture.implementation_write(),
            (T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {}),           # row 26: holds
            (T.TEST_DESIGN_WRITING, T.V_INPUT_QUICK_CHECK_FAILED,
             {"input_named": T.INPUT_DESIGN_CONTRACT}),                    # row 67
        ]
        self.repository.remove()
        self.repository = fixture.ThrowawayRepository()
        machine, run, _ = self.drive(script)
        self.assertEqual(run.counters.value("contract-revisions"), 1)
        self.assertEqual(run.current_state, T.CONTRACT_ACCEPTANCE_BY_USER)
        self.assertEqual(machine.routed[-1][0].row, "67")


if __name__ == "__main__":
    unittest.main(verbosity=2)
