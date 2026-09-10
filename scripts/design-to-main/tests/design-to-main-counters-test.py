#!/usr/bin/env python3
"""Section 7 of the design-to-main state-machine design: the counters.

Every counter reaching its ceiling and what happens there; the redesign
reset; the user's `reset`; and the three buckets — why a write was thrown
out decides which counter it spends.

Run: python3 scripts/design-to-main/tests/design-to-main-counters-test.py
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
RunCounters = fixture.run_state_module.RunCounters
CounterCeilingExceeded = fixture.run_state_module.CounterCeilingExceeded
write_counter_charged = fixture.run_state_module.write_counter_charged


class CounterCeilingsInIsolation(unittest.TestCase):
    """The counter table alone: ceilings and the at-ceiling guard."""

    def test_the_seven_counters_of_section_7(self):
        self.assertEqual(T.COUNTER_NAMES, (
            "redesigns", "design-revisions", "implementation-writes", "test-writes",
            "arbitrator-rulings", "contract-revisions", "test-design-corrections"))

    def test_every_counter_reaches_its_ceiling_and_refuses_the_next(self):
        for rule in T.COUNTER_TABLE:
            counters = RunCounters()
            for _ in range(rule.ceiling):
                counters.increment(rule.name)
            self.assertEqual(counters.value(rule.name), rule.ceiling, rule.name)
            self.assertTrue(counters.at_ceiling(rule.name), rule.name)
            with self.assertRaises(CounterCeilingExceeded, msg=rule.name):
                counters.increment(rule.name)

    def test_at_ceiling_from_value_follows_each_row_s_own_words(self):
        # "a third entry is refused", "the third write", "the third entry":
        # at the ceiling itself. "the second entry is not made": one below.
        expected = {
            "redesigns": 2, "design-revisions": 2, "implementation-writes": 3,
            "test-writes": 3, "arbitrator-rulings": 2,
            "contract-revisions": 1, "test-design-corrections": 1,
        }
        for name, at in expected.items():
            counters = RunCounters()
            for _ in range(at - 1):
                counters.increment(name)
            self.assertTrue(counters.below_ceiling(name), name)
            counters.increment(name)
            self.assertTrue(counters.at_ceiling(name), name)

    def test_a_redesign_resets_every_per_version_counter_but_not_redesigns(self):
        counters = RunCounters({name: 1 for name in T.COUNTER_NAMES})
        counters.zero_the_six_per_version_counters()
        self.assertEqual(counters.value("redesigns"), 1)
        for name in T.COUNTER_NAMES:
            if name != "redesigns":
                self.assertEqual(counters.value(name), 0, name)

    def test_the_user_s_reset_zeroes_every_counter_including_redesigns(self):
        counters = RunCounters({name: 2 for name in T.COUNTER_NAMES if name != "implementation-writes"})
        counters.reset_by_the_user()
        self.assertEqual(set(counters.as_dict().values()), {0})


class ThreeBuckets(unittest.TestCase):
    """A write that is thrown out is counted by why it was thrown out."""

    def test_the_three_buckets_are_named(self):
        self.assertEqual(set(T.DISCARDED_WRITE_BUCKETS), {
            "failed-review", "arbitrator-ruled", "upstream-document-changed"})

    def test_failed_review_spends_the_writer_s_counter(self):
        for reason in (T.ENTRY_REASON_FIRST_WRITE, T.ENTRY_REASON_REJECT_FROM_REVIEW,
                       T.ENTRY_REASON_DISCUSS_BY_USER):
            self.assertEqual(write_counter_charged(T.IMPLEMENTATION_WRITING, reason),
                             "implementation-writes", reason)
            self.assertEqual(write_counter_charged(T.TEST_WRITING, reason), "test-writes", reason)

    def test_an_arbitrator_s_ruling_spends_the_arbitrator_s_counter_not_the_writer_s(self):
        self.assertIsNone(write_counter_charged(T.IMPLEMENTATION_WRITING,
                                                T.ENTRY_REASON_ARBITRATOR_RULING))
        self.assertIsNone(write_counter_charged(T.TEST_WRITING, T.ENTRY_REASON_ARBITRATOR_RULING))

    def test_an_upstream_change_spends_that_document_s_counter_and_nothing_else(self):
        for reason in (T.ENTRY_REASON_CONTRACT_REVISION, T.ENTRY_REASON_TEST_DESIGN_CORRECTION,
                       T.ENTRY_REASON_REDESIGN):
            self.assertIsNone(write_counter_charged(T.IMPLEMENTATION_WRITING, reason), reason)
            self.assertIsNone(write_counter_charged(T.TEST_WRITING, reason), reason)

    def test_uncounted_writers_charge_nothing(self):
        self.assertIsNone(write_counter_charged(T.CONTRACT_REVISING, T.ENTRY_REASON_REJECT_FROM_REVIEW))
        self.assertIsNone(write_counter_charged(T.TEST_DESIGN_WRITING, T.ENTRY_REASON_REJECT_FROM_REVIEW))


class CountersDrivenThroughTheMachine(unittest.TestCase):
    """Each ceiling reached by a scripted run, and what the machine does
    there."""

    def setUp(self):
        self.repository = fixture.ThrowawayRepository()

    def tearDown(self):
        self.repository.remove()

    def drive(self, script):
        machine, run, record, _ = fixture.make_machine(script, self.repository)
        fixture.drive(machine, run)
        return machine, run, record

    def test_implementation_writes_the_third_write_failing_review_goes_to_the_arbitrator(self):
        script = fixture.prefix_to_design_approved()
        for _ in range(3):
            script += [fixture.implementation_write(),
                       (T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_REJECT_IMPLEMENTATION, {})]
        machine, run, _ = self.drive(script)
        self.assertEqual(run.counters.value("implementation-writes"), 3)
        self.assertEqual(run.current_state, T.TEST_SUITE_ARBITRATING)
        self.assertEqual(machine.routed[-1][0].row, "28")
        # Entered: arbitrator-rulings is charged on entry.
        self.assertEqual(run.counters.value("arbitrator-rulings"), 1)

    def test_test_writes_the_same(self):
        script = fixture.prefix_to_test_writing()
        for _ in range(3):
            script += [fixture.test_write(),
                       (T.TEST_ACCEPTANCE_BY_AGENT, T.V_REJECT_TESTS, {})]
        machine, run, _ = self.drive(script)
        self.assertEqual(run.counters.value("test-writes"), 3)
        self.assertEqual(run.current_state, T.TEST_SUITE_ARBITRATING)
        self.assertEqual(machine.routed[-1][0].row, "48")

    def test_a_write_the_arbitrator_orders_does_not_spend_the_writer_s_counter(self):
        # Two writes fail review (2 of 3); the suite then fails and the
        # arbitrator sends the implementation back: that write is the
        # arbitrator's bucket, and implementation-writes stays at 2.
        script = fixture.prefix_to_design_approved() + [
            fixture.implementation_write(),
            (T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_REJECT_IMPLEMENTATION, {}),
            fixture.implementation_write(),
            (T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {}),     # row 24: tests begin
            (T.TEST_DESIGN_WRITING, T.V_EMITTED, {}),
            (T.TEST_DESIGN_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {}),
            (T.TEST_DESIGN_ACCEPTANCE_BY_USER, T.V_ADVANCE, {}),
            fixture.test_write(),
            (T.TEST_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {}),               # row 45
            (T.TEST_SUITE_EXECUTING, T.V_FAIL, {}),                     # row 55
            (T.TEST_SUITE_ARBITRATING, T.V_REJECT_IMPLEMENTATION, {}),  # row 60
            fixture.implementation_write(),                             # arbitrator's bucket
        ]
        machine, run, _ = self.drive(script)
        self.assertEqual(run.counters.value("implementation-writes"), 2)
        self.assertEqual(run.counters.value("arbitrator-rulings"), 1)
        self.assertEqual(run.writes_emitted_per_version[T.IMPLEMENTATION_WRITING], 3)
        self.assertEqual(run.current_state, T.IMPLEMENTATION_REVIEWING)

    def test_a_write_forced_by_a_contract_revision_does_not_spend_the_writer_s_counter(self):
        script = fixture.prefix_to_design_approved() + [
            fixture.implementation_write(),                                   # write 1, charged
            (T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_REJECT_CONTRACT, {}),  # row 29
            (T.CONTRACT_REVISING, T.V_EMITTED, {}),                            # row 19
            (T.CONTRACT_ACCEPTANCE_BY_PROGRAM, T.V_ADVANCE, {}),               # row 6
            (T.CONTRACT_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {}),                 # row 9
            fixture.implementation_write(),                                   # forced; uncharged
        ]
        machine, run, _ = self.drive(script)
        self.assertEqual(run.counters.value("contract-revisions"), 1)
        self.assertEqual(run.counters.value("implementation-writes"), 1)
        self.assertEqual(run.writes_emitted_per_version[T.IMPLEMENTATION_WRITING], 2)
        self.assertEqual(run.writing_state_entry_reason[T.IMPLEMENTATION_WRITING],
                         T.ENTRY_REASON_CONTRACT_REVISION)

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

    def test_test_design_corrections_the_second_entry_is_not_made(self):
        script = fixture.prefix_to_test_writing() + [
            (T.TEST_WRITING, T.V_INPUT_QUICK_CHECK_FAILED, {"input_named": T.INPUT_TEST_DESIGN}),  # row 41
            (T.TEST_DESIGN_WRITING, T.V_EMITTED, {}),
            (T.TEST_DESIGN_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {}),
            (T.TEST_DESIGN_ACCEPTANCE_BY_USER, T.V_ADVANCE, {}),
            (T.TEST_WRITING, T.V_INPUT_QUICK_CHECK_FAILED, {"input_named": T.INPUT_TEST_DESIGN}),  # row 42
        ]
        machine, run, _ = self.drive(script)
        self.assertEqual(run.counters.value("test-design-corrections"), 1)
        self.assertEqual(run.current_state, T.TEST_DESIGN_ACCEPTANCE_BY_USER)
        self.assertEqual(machine.routed[-1][0].row, "42")

    def test_design_revisions_the_third_rejection_brings_the_user_in(self):
        script = [
            (T.INITIATE_DESIGN_TO_MAIN, T.V_INVOKED, {}),
            (T.DESIGN_WRITING, T.V_EMITTED, {}),
            (T.CONTRACT_ACCEPTANCE_BY_PROGRAM, T.V_ADVANCE, {}),
            (T.DESIGN_ACCEPTANCE_BY_AGENT, T.V_REJECT_DESIGN, {}),      # row 12, counted
            (T.DESIGN_WRITING, T.V_EMITTED, {}),
            (T.CONTRACT_ACCEPTANCE_BY_PROGRAM, T.V_ADVANCE, {}),
            (T.DESIGN_ACCEPTANCE_BY_AGENT, T.V_REJECT_CONTRACT, {}),    # row 13a, counted
            (T.DESIGN_WRITING, T.V_EMITTED, {}),
            (T.CONTRACT_ACCEPTANCE_BY_PROGRAM, T.V_ADVANCE, {}),
            (T.DESIGN_ACCEPTANCE_BY_AGENT, T.V_REJECT_DESIGN, {}),      # row 13, at the ceiling
        ]
        machine, run, _ = self.drive(script)
        self.assertEqual(run.counters.value("design-revisions"), 2)
        self.assertEqual([r.row for r, _, _ in machine.routed if r and r.from_states == (T.DESIGN_REVIEWING,)],
                         ["12", "14", "13"])
        self.assertEqual(run.current_state, T.DESIGN_WRITING)

    def test_arbitrator_rulings_the_third_entry_opens_the_investigation(self):
        suite_fails_and_arbitrator_sends_tests_back = [
            (T.TEST_SUITE_EXECUTING, T.V_FAIL, {}),
            (T.TEST_SUITE_ARBITRATING, T.V_REJECT_TESTS, {}),
            fixture.test_write(),
            (T.TEST_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {}),
        ]
        script = fixture.whole_run_to_passed()[:-2]  # up to the suite
        script += suite_fails_and_arbitrator_sends_tests_back * 2
        script += [(T.TEST_SUITE_EXECUTING, T.V_FAIL, {})]
        machine, run, _ = self.drive(script)
        self.assertEqual(run.counters.value("arbitrator-rulings"), 2)
        self.assertEqual(run.current_state, T.INVESTIGATE_WORKFLOW)
        self.assertEqual(run.investigation_focus, T.FOCUS_UNKNOWN)
        self.assertIn("third entry", run.investigation_opened_by)
        # Row 64 is applied on entry, not on a state-exit: the run records
        # it as the row that opened the investigation, so a resume knows
        # (section 6.6) not to loop back into the arbitrator.
        self.assertEqual(run.investigation_opened_by_row, T.ROW_THE_ARBITRATORS_THIRD_ENTRY)
        self.assertEqual(T.TRANSITION_TABLE_BY_ROW[T.ROW_THE_ARBITRATORS_THIRD_ENTRY].to_state,
                         T.INVESTIGATE_WORKFLOW)
        self.assertEqual(run.paused_state, T.TEST_SUITE_ARBITRATING)
        # The arbitrator was not launched a third time in test-suite-arbitrating.
        self.assertEqual(
            sum(1 for p in machine.launcher.launched if p["state"] == T.TEST_SUITE_ARBITRATING), 2)
        # Its two rulings did not spend test-writes.
        self.assertEqual(run.counters.value("test-writes"), 1)

    def test_row_62_a_reject_whose_writer_is_at_its_ceiling_goes_to_that_writer_bounded_by_the_arbitrator(self):
        # Section 7 after the seventh walk: per version and per work-stream
        # at most three writes by review and two more ordered by the
        # arbitrator, then the user — five, not eight. The writer's counter
        # stops deciding once the arbitrator is in and is not reset; a
        # reviewer's reject of a write the arbitrator ordered returns to
        # the arbitrator (row 28), and its third entry opens the
        # investigation (row 64).
        script = fixture.prefix_to_design_approved()
        for _ in range(3):
            script += [fixture.implementation_write(),
                       (T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_REJECT_IMPLEMENTATION, {})]
        for _ in range(2):
            script += [(T.TEST_SUITE_ARBITRATING, T.V_REJECT_IMPLEMENTATION, {}),      # row 62
                       fixture.implementation_write(),                                # forced
                       (T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_REJECT_IMPLEMENTATION, {})]  # row 28
        machine, run, _ = self.drive(script)
        rows = [r.row for r, _, _ in machine.routed]
        self.assertEqual(rows[-7:], ["28", "62", "21", "28", "62", "21", "28"])
        self.assertEqual(run.counters.value("implementation-writes"), 3)      # not reset, not spent
        self.assertEqual(run.counters.value("arbitrator-rulings"), 2)
        self.assertEqual(run.writes_emitted_per_version[T.IMPLEMENTATION_WRITING], 5)
        self.assertEqual(run.current_state, T.INVESTIGATE_WORKFLOW)
        self.assertEqual(run.investigation_opened_by_row, T.ROW_THE_ARBITRATORS_THIRD_ENTRY)
        self.assertEqual(
            sum(1 for p in machine.launcher.launched if p["state"] == T.TEST_SUITE_ARBITRATING), 2)
        self.assertEqual(
            sum(1 for p in machine.launcher.launched if p["state"] == T.IMPLEMENTATION_WRITING), 5)
        self.assertEqual(run.writing_state_entry_reason[T.IMPLEMENTATION_WRITING],
                         T.ENTRY_REASON_ARBITRATOR_RULING)

    def test_row_62_for_the_tests_the_same(self):
        script = fixture.prefix_to_test_writing()
        for _ in range(3):
            script += [fixture.test_write(),
                       (T.TEST_ACCEPTANCE_BY_AGENT, T.V_REJECT_TESTS, {})]
        script += [(T.TEST_SUITE_ARBITRATING, T.V_REJECT_TESTS, {}),                # row 62
                   fixture.test_write()]                                             # forced
        machine, run, _ = self.drive(script)
        self.assertEqual([r.row for r, _, _ in machine.routed][-3:], ["48", "62", "40"])
        self.assertEqual(run.counters.value("test-writes"), 3)
        self.assertEqual(run.counters.value("arbitrator-rulings"), 1)
        self.assertEqual(run.current_state, T.TEST_REVIEWING)

    def test_past_both_ceilings_the_users_resume_buys_a_whole_automated_budget(self):
        # The eighth walk, item 5 and the side ruling under item 6
        # (user-ruled 2026-09-09), answering PR #295's reviewer: the test
        # writer at its ceiling (3) and arbitrator-rulings at its (2), the
        # third entry opens the investigation (row 64) without a charge.
        # The user's resume zeroes the six per-version counters, so the
        # held `reject tests` routes by row 61, below the ceiling, and the
        # reviewer's next reject is a counted write again: each
        # consultation buys a full automated budget, and the run reaches
        # him next only when a whole one is spent (section 7).
        script = fixture.prefix_to_test_writing()
        for _ in range(3):
            script += [fixture.test_write(),
                       (T.TEST_ACCEPTANCE_BY_AGENT, T.V_REJECT_TESTS, {})]          # row 47, 47, 48
        for _ in range(2):
            script += [(T.TEST_SUITE_ARBITRATING, T.V_REJECT_TESTS, {}),           # row 62
                       fixture.test_write(),                                        # forced
                       (T.TEST_ACCEPTANCE_BY_AGENT, T.V_REJECT_TESTS, {})]          # row 48
        machine, run, _ = self.drive(script)
        self.assertEqual(run.current_state, T.INVESTIGATE_WORKFLOW)
        self.assertEqual(run.investigation_opened_by_row, T.ROW_THE_ARBITRATORS_THIRD_ENTRY)
        self.assertEqual(run.counters.value("test-writes"), 3)
        self.assertEqual(run.counters.value("arbitrator-rulings"), 2)
        self.assertEqual(run.writes_emitted_per_version[T.TEST_WRITING], 5)
        machine.launcher.script += [
            (T.INVESTIGATE_WORKFLOW, T.V_RESUME, {"held_ruling": T.V_REJECT_TESTS}),  # row 71: zeroes
            fixture.test_write(),                                                    # forced
            (T.TEST_ACCEPTANCE_BY_AGENT, T.V_REJECT_TESTS, {}),                      # row 47
            fixture.test_write(),                                                    # counted: 1
        ]
        fixture.drive(machine, run)
        self.assertEqual(machine.held_rulings_applied[-1][0].row, "61")
        self.assertEqual([r.row for r, _, _ in machine.routed][-4:], ["71", "40", "47", "40"])
        self.assertEqual(run.writes_emitted_per_version[T.TEST_WRITING], 7)
        self.assertEqual(run.counters.value("test-writes"), 1)
        self.assertEqual(run.counters.value("arbitrator-rulings"), 0)
        self.assertEqual(run.current_state, T.TEST_REVIEWING)
        self.assertEqual(machine.machine_errors, [])
        self.assertEqual(
            sum(1 for p in machine.launcher.launched if p["state"] == T.TEST_SUITE_ARBITRATING), 2)

    def contract_reaches_the_user(self):
        return fixture.prefix_to_design_approved() + [
            fixture.implementation_write(),
            (T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_REJECT_CONTRACT, {}),  # row 29
            (T.CONTRACT_REVISING, T.V_EMITTED, {}),
            (T.CONTRACT_ACCEPTANCE_BY_PROGRAM, T.V_ADVANCE, {}),
            (T.CONTRACT_ACCEPTANCE_BY_AGENT, T.V_REJECT_CONTRACT, {}),        # row 8
        ]

    def test_row_11_the_user_s_redesign_at_the_contract_check_opens_the_redesign_through_the_investigation(self):
        script = self.contract_reaches_the_user() + [
            (T.CONTRACT_ACCEPTANCE_BY_USER, T.V_REDESIGN, {}),                # row 11
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
        self.assertEqual(machine.routed[-1][0].row, "71")
        self.assertEqual(run.current_state, T.DESIGN_WRITING)
        self.assertEqual(run.design_version, 2)
        self.assertEqual(run.counters.value("redesigns"), 1)
        self.assertEqual(run.counters.value("contract-revisions"), 0)
        self.assertEqual(
            sum(1 for p in machine.launcher.launched if p["state"] == T.CONTRACT_ACCEPTANCE_BY_USER), 1)

    def test_row_11_at_the_redesigns_ceiling_the_resume_ends_the_run_failed(self):
        script = self.contract_reaches_the_user() + [
            (T.CONTRACT_ACCEPTANCE_BY_USER, T.V_REDESIGN, {}),
            (T.INVESTIGATE_WORKFLOW, T.V_RESUME, {}),
        ]
        machine, run, _ = self.drive(script)
        self.assertEqual(run.current_state, T.DESIGN_WRITING)
        run.counters.values["redesigns"] = 2        # as after two redesigns
        machine.launcher.script += self.contract_reaches_the_user()[1:] + [
            (T.CONTRACT_ACCEPTANCE_BY_USER, T.V_REDESIGN, {}),
            (T.INVESTIGATE_WORKFLOW, T.V_RESUME, {}),                          # row 72
        ]
        fixture.drive(machine, run)
        self.assertEqual(machine.routed[-1][0].row, "72")
        self.assertEqual(run.current_state, T.ENDED)
        self.assertEqual(run.outcome, T.OUTCOME_FAILED)

    def test_redesigns_reset_the_version_and_keep_the_redesigns_counter(self):
        script = fixture.prefix_to_tests_begun() + [
            (T.TEST_DESIGN_WRITING, T.V_INPUT_QUICK_CHECK_FAILED, {"input_named": T.INPUT_DESIGN}),  # row 34
            (T.INVESTIGATE_WORKFLOW, T.V_RESUME, {"destination": T.DESIGN_WRITING}),               # row 71
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
            (T.TEST_ACCEPTANCE_BY_AGENT, T.V_REJECT_DESIGN, {}),                  # row 52
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
        # Section 7 and row 71 after the eighth walk (user-ruled
        # 2026-09-09, "if I intervene all the agents get their chance
        # again"): every resume zeroes the six per-version counters, as a
        # redesign does; the redesigns counter still needs the user's
        # explicit reset. The resume's commit trailer shows the zeroed
        # counters.
        script = fixture.prefix_to_test_writing() + [
            fixture.test_write(),
            (T.TEST_ACCEPTANCE_BY_AGENT, T.V_REJECT_DESIGN, {}),                  # row 52
        ]
        machine, run, record = self.drive(script)
        self.assertEqual(run.current_state, T.INVESTIGATE_WORKFLOW)
        run.counters.values.update({
            "redesigns": 1, "design-revisions": 1, "implementation-writes": 2, "test-writes": 1,
            "contract-revisions": 1, "test-design-corrections": 1, "arbitrator-rulings": 1})
        machine.launcher.script.append((T.INVESTIGATE_WORKFLOW, T.V_RESUME, {}))   # row 71
        fixture.drive(machine, run)
        self.assertEqual(machine.routed[-1][0].row, "71")
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
            (T.TEST_ACCEPTANCE_BY_AGENT, T.V_REJECT_DESIGN, {}),                  # row 52
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
        self.assertEqual(machine.routed[-1][0].row, "72")

    def test_the_user_s_reset_lifts_the_redesigns_ceiling_and_is_recorded_as_a_ruling(self):
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
             {"destination": T.DESIGN_WRITING, "rulings": ("reset",)}),
        ]
        machine, run, record = self.drive(script)
        self.assertEqual(run.current_state, T.DESIGN_WRITING)
        self.assertEqual(run.design_version, 4)
        self.assertEqual(run.counters.value("redesigns"), 1)   # zeroed, then this redesign
        rulings = record.absolute(record.user_rulings_path).read_text()
        self.assertIn("- reset (user-ruled 2026-09-08)", rulings)

    def test_contract_revisions_a_second_reject_from_any_state_goes_to_the_user_by_row_66(self):
        # Rows 22, 29, 33, 36, 43, 51 and 65 send a reject of the contract
        # to contract-revising only below the ceiling; at the ceiling the
        # reject goes to contract-acceptance-by-user by row 66, whichever
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
        script += [(T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_REJECT_CONTRACT, {})]  # row 66
        machine, run, _ = self.drive(script)
        self.assertEqual(run.counters.value("contract-revisions"), 1)
        self.assertEqual(run.current_state, T.CONTRACT_ACCEPTANCE_BY_USER)
        self.assertEqual(machine.routed[-1][0].row, "66")
        self.assertEqual(machine.machine_errors, [])
        # The user advances the revision as it stands (row 9): both
        # work-streams re-enter, and the run goes on.
        machine.launcher.script += [(T.CONTRACT_ACCEPTANCE_BY_USER, T.V_ADVANCE, {})]
        fixture.drive(machine, run)
        self.assertEqual(machine.routed[-1][0].row, "9")
        self.assertEqual(run.current_state, T.IMPLEMENTATION_WRITING)

        script = fixture.prefix_to_tests_begun() + [
            (T.TEST_DESIGN_WRITING, T.V_INPUT_QUICK_CHECK_FAILED,
             {"input_named": T.INPUT_COMPONENT_CONTRACT}),                    # row 33
            (T.CONTRACT_REVISING, T.V_EMITTED, {}),
            (T.CONTRACT_ACCEPTANCE_BY_PROGRAM, T.V_ADVANCE, {}),
            (T.CONTRACT_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {}),                 # row 9
            fixture.implementation_write(),
            (T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {}),           # row 26: holds
            (T.TEST_DESIGN_WRITING, T.V_INPUT_QUICK_CHECK_FAILED,
             {"input_named": T.INPUT_COMPONENT_CONTRACT}),                    # row 66
        ]
        self.repository.remove()
        self.repository = fixture.ThrowawayRepository()
        machine, run, _ = self.drive(script)
        self.assertEqual(run.counters.value("contract-revisions"), 1)
        self.assertEqual(run.current_state, T.CONTRACT_ACCEPTANCE_BY_USER)
        self.assertEqual(machine.routed[-1][0].row, "66")

    def test_an_increment_past_a_ceiling_is_a_machine_error_routed_to_the_investigation(self):
        # The one path the table leaves to a counter past its ceiling: the
        # user's discuss at implementation-acceptance-by-user (row 31) with
        # implementation-writes at three — "the write it forces is counted
        # like any other", and a fourth write has no counter to spend.
        script = fixture.prefix_to_design_approved()
        for _ in range(2):
            script += [fixture.implementation_write(coverage_type="prompt"),
                       (T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_REJECT_IMPLEMENTATION, {})]
        script += [fixture.implementation_write(coverage_type="prompt"),
                   (T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {}),      # row 16
                   (T.IMPLEMENTATION_ACCEPTANCE_BY_USER, T.V_DISCUSS, {}),       # row 31
                   fixture.implementation_write(coverage_type="prompt")]         # the fourth
        machine, run, _ = self.drive(script)
        self.assertEqual(run.counters.value("implementation-writes"), 3)
        self.assertEqual(run.current_state, T.INVESTIGATE_WORKFLOW)
        self.assertEqual(len(machine.machine_errors), 1)
        self.assertIn("ceiling", run.machine_error)


if __name__ == "__main__":
    unittest.main(verbosity=2)
