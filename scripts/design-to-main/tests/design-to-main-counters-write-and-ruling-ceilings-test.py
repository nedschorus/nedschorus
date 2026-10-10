#!/usr/bin/env python3
"""Section 7 of the design-to-main state-machine design: the counters'
table alone — every counter reaching its ceiling, the redesign reset and
the user-ruling `zero-all-run-counters-including-redesigns`; the three buckets — why a write was thrown out
decides which counter it spends; and, driven through the machine, the
ceilings of the writers' counters and of arbitrator-rulings and what
happens there.

The counters cases are split over two files,
design-to-main-counters-*-test.py, so that the suite runner runs them at
the same time.

Run: python3 scripts/design-to-main/tests/design-to-main-counters-write-and-ruling-ceilings-test.py
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

    def test_the_two_write_counters_may_be_taken_past_their_ceiling_by_the_users_discuss_only(self):
        # Section 7 after the eighth walk (item 6, user-ruled 2026-09-09):
        # a write the user's discuss forces may take implementation-writes
        # or test-writes past three, and "at its ceiling" reads at or above.
        # No other counter, and no other cause, goes past a ceiling.
        for name in ("implementation-writes", "test-writes"):
            counters = RunCounters({name: 3})
            self.assertEqual(counters.increment(name, forced_by_the_users_discuss=True), 4)
            self.assertTrue(counters.at_ceiling(name))
            self.assertFalse(counters.below_ceiling(name))
            with self.assertRaises(CounterCeilingExceeded):
                counters.increment(name)
        for name in ("redesigns", "design-revisions", "arbitrator-rulings",
                     "contract-revisions", "test-design-corrections"):
            counters = RunCounters({name: T.COUNTER_TABLE_BY_NAME[name].ceiling})
            with self.assertRaises(CounterCeilingExceeded, msg=name):
                counters.increment(name, forced_by_the_users_discuss=True)

    def test_a_redesign_resets_every_per_version_counter_but_not_redesigns(self):
        counters = RunCounters({name: 1 for name in T.COUNTER_NAMES})
        counters.zero_the_six_per_version_counters()
        self.assertEqual(counters.value("redesigns"), 1)
        for name in T.COUNTER_NAMES:
            if name != "redesigns":
                self.assertEqual(counters.value(name), 0, name)

    def test_zero_all_run_counters_including_redesigns_zeroes_every_counter_including_redesigns(self):
        counters = RunCounters({name: 2 for name in T.COUNTER_NAMES if name != "implementation-writes"})
        counters.zero_all_run_counters_including_redesigns()
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
                       T.ENTRY_REASON_DESIGN_CHANGED_UPSTREAM):
            self.assertIsNone(write_counter_charged(T.IMPLEMENTATION_WRITING, reason), reason)
            self.assertIsNone(write_counter_charged(T.TEST_WRITING, reason), reason)

    def test_uncounted_writers_charge_nothing(self):
        self.assertIsNone(write_counter_charged(T.CONTRACT_REVISING, T.ENTRY_REASON_REJECT_FROM_REVIEW))
        self.assertIsNone(write_counter_charged(T.TEST_DESIGN_WRITING, T.ENTRY_REASON_REJECT_FROM_REVIEW))


class WriteAndRulingCeilingsDrivenThroughTheMachine(
        fixture.EachTestDrivesTheMachineOverItsOwnThrowawayRepository, unittest.TestCase):
    """Each ceiling of implementation-writes, test-writes, design-revisions,
    test-design-corrections and arbitrator-rulings reached by a scripted
    run, and what the machine does there."""

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
        self.assertEqual(machine.routed[-1][0].row, "50")

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
            (T.TEST_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {}),               # row 47
            (T.TEST_SUITE_EXECUTING, T.V_FAIL, {}),                     # row 57
            (T.TEST_SUITE_ARBITRATING, T.V_REJECT_IMPLEMENTATION, {}),  # row 61
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

    def test_test_design_corrections_the_second_entry_is_not_made(self):
        script = fixture.prefix_to_test_writing() + [
            (T.TEST_WRITING, T.V_INPUT_QUICK_CHECK_FAILED, {"input_named": T.INPUT_TEST_DESIGN}),  # row 43
            (T.TEST_DESIGN_WRITING, T.V_EMITTED, {}),
            (T.TEST_DESIGN_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {}),
            (T.TEST_DESIGN_ACCEPTANCE_BY_USER, T.V_ADVANCE, {}),
            (T.TEST_WRITING, T.V_INPUT_QUICK_CHECK_FAILED, {"input_named": T.INPUT_TEST_DESIGN}),  # row 44
        ]
        machine, run, _ = self.drive(script)
        self.assertEqual(run.counters.value("test-design-corrections"), 1)
        self.assertEqual(run.current_state, T.TEST_DESIGN_ACCEPTANCE_BY_USER)
        self.assertEqual(machine.routed[-1][0].row, "44")

    def test_test_design_corrections_a_reject_after_approval_counts_and_at_the_ceiling_the_user_is_called(self):
        # The tenth walk, item 7 (user-ruled 2026-09-14): section 3.2's one
        # `reject test-design` row from the agent check became three, so
        # that a re-write after the test-design's approval is bounded as
        # section 7 always said. Here a contract-revision re-enters the
        # approved test-design's writer (row 9); the agent check's reject
        # of the re-write counts a correction (row 36), and its reject of
        # the correction, at the ceiling, calls the user (row 37).
        script = fixture.prefix_to_test_writing() + [
            fixture.test_write(),
            (T.TEST_ACCEPTANCE_BY_AGENT, T.V_REJECT_CONTRACT, {}),               # row 53
            (T.CONTRACT_REVISING, T.V_EMITTED, {}),
            (T.CONTRACT_ACCEPTANCE_BY_PROGRAM, T.V_ADVANCE, {}),
            (T.CONTRACT_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {}),                   # row 9: both re-enter
            fixture.implementation_write(),                                      # forced
            (T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {}),             # row 26: holds
            (T.TEST_DESIGN_WRITING, T.V_EMITTED, {}),                            # forced; row 32
            (T.TEST_DESIGN_ACCEPTANCE_BY_AGENT, T.V_REJECT_TEST_DESIGN, {}),     # row 36
            (T.TEST_DESIGN_WRITING, T.V_EMITTED, {}),                            # the correction
            (T.TEST_DESIGN_ACCEPTANCE_BY_AGENT, T.V_REJECT_TEST_DESIGN, {}),     # row 37
        ]
        machine, run, _ = self.drive(script)
        self.assertEqual([r.row for r, _, _ in machine.routed][-4:], ["32", "36", "32", "37"])
        self.assertEqual(run.counters.value("test-design-corrections"), 1)
        self.assertEqual(run.writing_state_entry_reason[T.TEST_DESIGN_WRITING],
                         T.ENTRY_REASON_TEST_DESIGN_CORRECTION)
        self.assertEqual(run.current_state, T.TEST_DESIGN_ACCEPTANCE_BY_USER)
        self.assertEqual(machine.machine_errors, [])

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
        # Row 65 is applied on entry, not on a state-exit: the run records
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
        # investigation (row 65).
        script = fixture.prefix_to_design_approved()
        for _ in range(3):
            script += [fixture.implementation_write(),
                       (T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_REJECT_IMPLEMENTATION, {})]
        for _ in range(2):
            script += [(T.TEST_SUITE_ARBITRATING, T.V_REJECT_IMPLEMENTATION, {}),      # row 63
                       fixture.implementation_write(),                                # forced
                       (T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_REJECT_IMPLEMENTATION, {})]  # row 28
        machine, run, _ = self.drive(script)
        rows = [r.row for r, _, _ in machine.routed]
        self.assertEqual(rows[-7:], ["28", "63", "21", "28", "63", "21", "28"])
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
        script += [(T.TEST_SUITE_ARBITRATING, T.V_REJECT_TESTS, {}),                # row 63
                   fixture.test_write()]                                             # forced
        machine, run, _ = self.drive(script)
        self.assertEqual([r.row for r, _, _ in machine.routed][-3:], ["50", "63", "42"])
        self.assertEqual(run.counters.value("test-writes"), 3)
        self.assertEqual(run.counters.value("arbitrator-rulings"), 1)
        self.assertEqual(run.current_state, T.TEST_REVIEWING)

    def test_past_both_ceilings_the_users_resume_buys_a_whole_automated_budget(self):
        # The eighth walk, item 5 and the side ruling under item 6
        # (user-ruled 2026-09-09), answering PR #295's reviewer: the test
        # writer at its ceiling (3) and arbitrator-rulings at its (2), the
        # third entry opens the investigation (row 65) without a charge.
        # The user's resume zeroes the six per-version counters, so the
        # held `reject tests` routes by row 62, below the ceiling, and the
        # reviewer's next reject is a counted write again: each
        # consultation buys a full automated budget, and the run reaches
        # him next only when a whole one is spent (section 7).
        script = fixture.prefix_to_test_writing()
        for _ in range(3):
            script += [fixture.test_write(),
                       (T.TEST_ACCEPTANCE_BY_AGENT, T.V_REJECT_TESTS, {})]          # row 49, 49, 50
        for _ in range(2):
            script += [(T.TEST_SUITE_ARBITRATING, T.V_REJECT_TESTS, {}),           # row 63
                       fixture.test_write(),                                        # forced
                       (T.TEST_ACCEPTANCE_BY_AGENT, T.V_REJECT_TESTS, {})]          # row 50
        machine, run, _ = self.drive(script)
        self.assertEqual(run.current_state, T.INVESTIGATE_WORKFLOW)
        self.assertEqual(run.investigation_opened_by_row, T.ROW_THE_ARBITRATORS_THIRD_ENTRY)
        self.assertEqual(run.counters.value("test-writes"), 3)
        self.assertEqual(run.counters.value("arbitrator-rulings"), 2)
        self.assertEqual(run.writes_emitted_per_version[T.TEST_WRITING], 5)
        machine.launcher.script += [
            (T.INVESTIGATE_WORKFLOW, T.V_RESUME, {"held_ruling": T.V_REJECT_TESTS}),  # row 72: zeroes
            fixture.test_write(),                                                    # forced
            (T.TEST_ACCEPTANCE_BY_AGENT, T.V_REJECT_TESTS, {}),                      # row 49
            fixture.test_write(),                                                    # counted: 1
        ]
        fixture.drive(machine, run)
        self.assertEqual(machine.held_rulings_applied[-1][0].row, "62")
        self.assertEqual([r.row for r, _, _ in machine.routed][-4:], ["72", "42", "49", "42"])
        self.assertEqual(run.writes_emitted_per_version[T.TEST_WRITING], 7)
        self.assertEqual(run.counters.value("test-writes"), 1)
        self.assertEqual(run.counters.value("arbitrator-rulings"), 0)
        self.assertEqual(run.current_state, T.TEST_REVIEWING)
        self.assertEqual(machine.machine_errors, [])
        self.assertEqual(
            sum(1 for p in machine.launcher.launched if p["state"] == T.TEST_SUITE_ARBITRATING), 2)

    def test_a_write_the_users_discuss_forces_past_the_ceiling_is_counted_and_a_reject_of_it_goes_to_the_arbitrator(self):
        # The eighth walk, item 6 (user-ruled 2026-09-09): the user's
        # discuss at implementation-acceptance-by-user (row 31) with
        # implementation-writes at three forces a fourth write, counted
        # like any other (section 6.6), and the counter reads four; a
        # reject of that write goes to the arbitrator by row 28, whose
        # guard reads "at or above its ceiling". (Before the ruling this
        # was a machine error: no counter to spend.)
        script = fixture.prefix_to_design_approved()
        for _ in range(2):
            script += [fixture.implementation_write(coverage_type="prompt"),
                       (T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_REJECT_IMPLEMENTATION, {})]
        script += [fixture.implementation_write(coverage_type="prompt"),
                   (T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {}),      # row 16
                   (T.IMPLEMENTATION_ACCEPTANCE_BY_USER, T.V_DISCUSS, {}),       # row 31
                   fixture.implementation_write(coverage_type="prompt")]         # the fourth: counted
        machine, run, record = self.drive(script)
        self.assertEqual(machine.machine_errors, [])
        self.assertEqual(run.counters.value("implementation-writes"), 4)
        self.assertEqual(run.current_state, T.IMPLEMENTATION_REVIEWING)
        self.assertEqual(run.writing_state_entry_reason[T.IMPLEMENTATION_WRITING],
                         T.ENTRY_REASON_DISCUSS_BY_USER)
        trailer = fixture.git_record_module.parse_state_exit_trailer(record.commit_message("HEAD"))
        self.assertEqual(trailer["Write"], "4")
        self.assertEqual(trailer["Counter-implementation-writes"], "4")
        machine.launcher.script += [
            (T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_REJECT_IMPLEMENTATION, {}),  # row 28
        ]
        fixture.drive(machine, run)
        self.assertEqual(machine.routed[-1][0].row, "28")
        self.assertEqual(run.current_state, T.TEST_SUITE_ARBITRATING)
        self.assertEqual(run.counters.value("arbitrator-rulings"), 1)
        self.assertEqual(machine.machine_errors, [])

    def test_the_same_for_the_tests_at_test_acceptance_by_user(self):
        # The test-design asks for prompt tests, which is what the writer
        # emits for the set: section 6.4 checks the one against the other.
        script = fixture.prefix_to_test_writing("prompt")
        for _ in range(2):
            script += [fixture.test_write("prompt"),
                       (T.TEST_ACCEPTANCE_BY_AGENT, T.V_REJECT_TESTS, {})]
        script += [fixture.test_write("prompt"),
                   (T.TEST_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {}),               # row 16
                   (T.TEST_ACCEPTANCE_BY_USER, T.V_DISCUSS, {}),                # row 55
                   fixture.test_write("prompt"),                  # the fourth: counted
                   (T.TEST_ACCEPTANCE_BY_AGENT, T.V_REJECT_TESTS, {})]          # row 50
        machine, run, record = self.drive(script)
        self.assertEqual(machine.machine_errors, [])
        self.assertEqual(run.counters.value("test-writes"), 4)
        self.assertEqual([r.row for r, _, _ in machine.routed][-3:], ["55", "42", "50"])
        self.assertEqual(run.current_state, T.TEST_SUITE_ARBITRATING)


if __name__ == "__main__":
    unittest.main(verbosity=2)
