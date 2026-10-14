#!/usr/bin/env python3
"""The design-to-main machine's arbitrator, driven through the stub
launcher: a ruling that rejects both artifacts, an advance that
overrules a reviewer at its ceiling, and the resumes from the
investigation the arbitrator's third entry opens.

The whole-run cases are split over four files,
design-to-main-whole-run-*-test.py, so that the suite runner runs them at
the same time.

Run: python3 scripts/design-to-main/tests/design-to-main-whole-run-arbitrator-test.py
"""

import importlib.util
import json
import pathlib
import unittest

_fixture_spec = importlib.util.spec_from_file_location(
    "design_to_main_test_fixture",
    pathlib.Path(__file__).with_name("design-to-main-test-fixture.py"))
fixture = importlib.util.module_from_spec(_fixture_spec)
_fixture_spec.loader.exec_module(fixture)

T = fixture.tables


class TheArbitratorRejectsBothArtifactsInOneRuling(unittest.TestCase):
    """Row 64: `reject implementation and tests` re-enters both writers,
    fresh, each write the arbitrator's bucket; the implementation-work-
    stream runs first (section 3.1), holds, and the test-work-stream runs;
    they meet again at test-suite-executing."""

    def test_row_63_re_enters_both_writers_the_implementation_first(self):
        repository = fixture.ThrowawayRepository()
        try:
            script = fixture.whole_run_to_passed()[:-2] + [
                (T.TEST_SUITE_EXECUTING, T.V_FAIL, {}),                                  # row 57
                (T.TEST_SUITE_ARBITRATING, T.V_REJECT_IMPLEMENTATION_AND_TESTS, {}),    # row 64
                fixture.implementation_write(),                                         # forced
                (T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {}),                 # row 26: holds
                fixture.test_write(),                                                   # forced
                (T.TEST_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {}),                           # row 47
                (T.TEST_SUITE_EXECUTING, T.V_PASS, {}),
                (T.SUBMIT_TO_PR_GATE, T.V_ACCEPTED, {}),
            ]
            machine, run, record, _ = fixture.make_machine(script, repository)
            self.assertEqual(machine.run_until_ended(run), T.OUTCOME_PASSED)
            rows = [row.row for row, _, _ in machine.routed]
            self.assertEqual(rows[-8:], ["57", "64", "21", "26", "42", "47", "56", "74"])
            self.assertEqual(run.counters.value("arbitrator-rulings"), 1)
            self.assertEqual(run.counters.value("implementation-writes"), 1)
            self.assertEqual(run.counters.value("test-writes"), 1)
            self.assertEqual(run.writes_emitted_per_version, {
                T.IMPLEMENTATION_WRITING: 2, T.TEST_WRITING: 2})
            self.assertEqual(run.writing_state_entry_reason[T.IMPLEMENTATION_WRITING],
                             T.ENTRY_REASON_ARBITRATOR_RULING)
            self.assertEqual(run.writing_state_entry_reason[T.TEST_WRITING],
                             T.ENTRY_REASON_ARBITRATOR_RULING)
        finally:
            repository.remove()


class TheArbitratorOverrulesAReviewer(unittest.TestCase):
    """Row 60 (section 6.5, user-ruled 2026-09-09, the eighth walk, item 4):
    entered from a reviewer's ceiling, the arbitrator's `advance` means the
    reviewer was wrong, and the artifact continues as if that reviewer had
    advanced it — wherever that reviewing state's own advance goes. The
    run-state records what entered test-suite-arbitrating so that the
    machine can tell this entry from a failed suite's, whose advance has
    no row (section 6.5; user-ruled 2026-09-14, the tenth walk, item 16)."""

    def setUp(self):
        self.repository = fixture.ThrowawayRepository()

    def tearDown(self):
        self.repository.remove()

    def three_rejects_of_the_implementation(self, coverage_type="script"):
        script = fixture.prefix_to_design_approved()
        for _ in range(3):
            script += [fixture.implementation_write(coverage_type),
                       (T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_REJECT_IMPLEMENTATION, {})]
        return script

    def test_the_implementation_continues_as_if_its_reviewer_had_advanced_it(self):
        # Three rejects, row 28; the arbitrator advances: the reviewer's own
        # advance with tests not yet begun is row 24, so tests begin.
        script = self.three_rejects_of_the_implementation() + [
            (T.TEST_SUITE_ARBITRATING, T.V_ADVANCE, {}),                          # row 60
        ]
        machine, run, record, _ = fixture.make_machine(script, self.repository)
        fixture.drive(machine, run)
        self.assertEqual([row.row for row, _, _ in machine.routed][-2:], ["28", "60"])
        self.assertEqual(run.test_suite_arbitrating_entered_from, T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT)
        self.assertEqual(run.current_state, T.TEST_DESIGN_WRITING)
        self.assertTrue(run.tests_begun)
        self.assertEqual(run.implementation_work_stream_position, T.READY_FOR_TEST_SUITE)
        self.assertEqual(run.test_work_stream_position, T.TEST_DESIGN_WRITING)
        self.assertEqual(run.counters.value("arbitrator-rulings"), 1)
        self.assertEqual(run.counters.value("implementation-writes"), 3)
        self.assertEqual(machine.machine_errors, [])
        on_disk = json.loads(record.absolute(record.run_state_path).read_text())
        self.assertEqual(on_disk["test-suite-arbitrating-entered-from"], T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT)

    def test_agent_instructions_continue_to_the_users_check(self):
        # The implementation is agent-instructions: the agent check's
        # advance is row 16, to implementation-acceptance-by-user.
        script = self.three_rejects_of_the_implementation(coverage_type="prompt") + [
            (T.TEST_SUITE_ARBITRATING, T.V_ADVANCE, {}),                          # row 60
        ]
        machine, run, record, _ = fixture.make_machine(script, self.repository)
        fixture.drive(machine, run)
        self.assertEqual(machine.routed[-1][0].row, "60")
        self.assertEqual(run.current_state, T.IMPLEMENTATION_ACCEPTANCE_BY_USER)
        self.assertFalse(run.tests_begun)

    def test_a_failed_suite_s_advance_is_a_machine_error_never_the_gate(self):
        # Section 6.5 after the tenth walk (item 16, user-ruled 2026-09-14):
        # a suite that failed is never advanced because a run of it passed.
        # The arbitrator proves before it rules, and a fault in the world
        # goes escalate-to-user; its advance from a failed suite has no
        # row, so it is a machine error, the run paused at the arbitrator.
        script = fixture.whole_run_to_passed()[:-2] + [
            (T.TEST_SUITE_EXECUTING, T.V_FAIL, {}),                                # row 57
            (T.TEST_SUITE_ARBITRATING, T.V_ADVANCE, {}),                           # no row
        ]
        machine, run, record, _ = fixture.make_machine(script, self.repository)
        fixture.drive(machine, run)
        self.assertEqual(run.test_suite_arbitrating_entered_from, T.TEST_SUITE_EXECUTING)
        self.assertEqual(len(machine.machine_errors), 1)
        self.assertIsNone(machine.routed[-1][0])
        self.assertEqual(run.current_state, T.INVESTIGATE_WORKFLOW)
        self.assertEqual(run.paused_state, T.TEST_SUITE_ARBITRATING)
        self.assertEqual(run.investigation_focus, T.FOCUS_UNKNOWN)


class ResumingFromTheArbitratorsThirdEntry(unittest.TestCase):
    """Section 6.6: an investigation the arbitrator's third entry opened
    (row 65), where the paused state is test-suite-arbitrating at its
    ceiling. A resume may name a destination, or apply the ruling the
    arbitrator held in its report — routed through
    test-suite-arbitrating's rows without entering the state — or carry
    neither, which returns to the same arbitrator: the resume has zeroed
    its counter, so the return is the first entry of a fresh budget
    rather than a fourth (user-ruled 2026-09-11, the ninth walk, item
    4)."""

    def setUp(self):
        self.repository = fixture.ThrowawayRepository()

    def tearDown(self):
        self.repository.remove()

    def open_the_third_entry_investigation(self):
        suite_fails_and_arbitrator_sends_tests_back = [
            (T.TEST_SUITE_EXECUTING, T.V_FAIL, {}),
            (T.TEST_SUITE_ARBITRATING, T.V_REJECT_TESTS, {}),
            fixture.test_write(),
            (T.TEST_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {}),
        ]
        script = fixture.whole_run_to_passed()[:-2]
        script += suite_fails_and_arbitrator_sends_tests_back * 2
        script += [(T.TEST_SUITE_EXECUTING, T.V_FAIL, {})]
        machine, run, record, _ = fixture.make_machine(script, self.repository)
        fixture.drive(machine, run)
        self.assertEqual(run.current_state, T.INVESTIGATE_WORKFLOW)
        self.assertEqual(run.investigation_opened_by_row, T.ROW_THE_ARBITRATORS_THIRD_ENTRY)
        self.assertEqual(run.counters.value("arbitrator-rulings"), 2)
        return machine, run, record

    def arbitrator_launches(self, machine):
        return sum(1 for p in machine.launcher.launched if p["state"] == T.TEST_SUITE_ARBITRATING)

    def test_a_plain_resume_returns_to_the_same_arbitrator_on_a_fresh_budget(self):
        # Section 6.6 after the ninth walk (item 4, user-ruled
        # 2026-09-11), dropping the refusal the earlier rule carried: a
        # resume that names no destination and carries no held ruling
        # returns to the state that was paused, the arbitrator, whose
        # counter the resume has zeroed — so the return is the first entry
        # of a fresh budget rather than a fourth, and the third-entry rule
        # does not fire again.
        machine, run, record = self.open_the_third_entry_investigation()
        machine.launcher.script += [
            (T.INVESTIGATE_WORKFLOW, T.V_RESUME, {}),                                # row 72
            (T.TEST_SUITE_ARBITRATING, T.V_REJECT_TESTS, {}),                        # row 62
        ]
        fixture.drive(machine, run)
        self.assertEqual([row.row for row, _, _ in machine.routed][-2:], ["72", "62"])
        self.assertEqual(machine.machine_errors, [])
        self.assertEqual(run.current_state, T.TEST_WRITING)
        self.assertEqual(self.arbitrator_launches(machine), 3)
        self.assertEqual(run.counters.value("arbitrator-rulings"), 1)

    def test_a_resume_applies_the_ruling_the_arbitrator_held_in_its_report(self):
        machine, run, record = self.open_the_third_entry_investigation()
        machine.launcher.script += [
            (T.INVESTIGATE_WORKFLOW, T.V_RESUME, {"held_ruling": T.V_REJECT_TESTS}),
            fixture.test_write(),                                                # forced
        ]
        fixture.drive(machine, run)
        self.assertEqual([row.row for row, _, _ in machine.routed][-2:], ["72", "42"])
        # The resume zeroed the six per-version counters (section 7), so
        # the held ruling routes by row 62; the write it orders is still
        # the arbitrator's bucket, and test-writes stays at zero.
        self.assertEqual(machine.held_rulings_applied[-1][0].row, "62")
        self.assertEqual(self.arbitrator_launches(machine), 2)
        self.assertEqual(run.counters.value("arbitrator-rulings"), 0)
        self.assertEqual(run.counters.value("test-writes"), 0)
        self.assertEqual(run.writing_state_entry_reason[T.TEST_WRITING], T.ENTRY_REASON_ARBITRATOR_RULING)
        self.assertEqual(run.current_state, T.TEST_REVIEWING)
        self.assertEqual(machine.machine_errors, [])

    def test_a_held_escalate_to_user_is_refused_as_a_malformed_resume(self):
        # Section 6.6 after the eighth walk (item 5): the held ruling is
        # one of the arbitrator's six rulings, never escalate-to-user —
        # the arbitrator is already talking to the user, and applying it
        # would open a second investigation whose plain resume returns to
        # the same ceiling. Refused like a resume naming `ended`: a
        # machine error, the pause unchanged, the counters untouched, the
        # next resume routed.
        machine, run, record = self.open_the_third_entry_investigation()
        opened_at = run.investigation_opened_at_commit
        opening_commit = machine.routed[-1][2]
        for held in (T.V_ESCALATE_TO_USER, "reject desgin"):
            with self.subTest(held_ruling=held):
                machine.launcher.script.append(
                    (T.INVESTIGATE_WORKFLOW, T.V_RESUME, {"held_ruling": held}))
                fixture.drive(machine, run)
                self.assertIsNone(machine.routed[-1][0])
                self.assertIn(held, run.machine_error)
                self.assertEqual(run.current_state, T.INVESTIGATE_WORKFLOW)
                self.assertEqual(run.paused_state, T.TEST_SUITE_ARBITRATING)
                self.assertEqual(run.investigation_opened_by_row, T.ROW_THE_ARBITRATORS_THIRD_ENTRY)
                self.assertEqual(run.investigation_opened_at_commit, opened_at)
                self.assertEqual(run.counters.value("arbitrator-rulings"), 2)
                self.assertEqual(self.arbitrator_launches(machine), 2)
        self.assertEqual(len(machine.machine_errors), 2)
        self.assertEqual(len(record.commits_on_branch(since=opening_commit)), 2)
        machine.launcher.script.append(
            (T.INVESTIGATE_WORKFLOW, T.V_RESUME, {"held_ruling": T.V_REJECT_TESTS}))
        fixture.drive(machine, run)
        self.assertEqual(machine.routed[-1][0].row, "72")
        self.assertEqual(run.current_state, T.TEST_WRITING)

    def test_a_resume_naming_a_destination_goes_there(self):
        machine, run, record = self.open_the_third_entry_investigation()
        machine.launcher.script.append(
            (T.INVESTIGATE_WORKFLOW, T.V_RESUME, {"destination": T.IMPLEMENTATION_REVIEWING}))
        fixture.drive(machine, run)
        self.assertEqual(machine.routed[-1][0].row, "72")
        self.assertEqual(run.current_state, T.IMPLEMENTATION_REVIEWING)
        self.assertEqual(self.arbitrator_launches(machine), 2)

    def test_a_resume_naming_the_arbitrator_launches_it_with_a_fresh_budget_and_carries_the_users_edit(self):
        # PR #295, round 2, finding 1 reproduced a resume naming
        # test-suite-arbitrating at the arbitrator's ceiling re-opening the
        # investigation half-way. Since the eighth walk's ruling that every
        # resume zeroes the six per-version counters, that resume finds
        # arbitrator-rulings at zero: the arbitrator is launched a third
        # time on a fresh budget, and nothing re-opens. The resume's
        # commit still carries the user's edit. (The opening is keyed on
        # the openers regardless, so a future row that did open one from
        # a resume would open it whole.)
        machine, run, record = self.open_the_third_entry_investigation()
        edited = record.absolute(fixture.COMPONENT_DIRECTORY + "/widget_counter.py")
        edited.parent.mkdir(parents=True, exist_ok=True)
        edited.write_text("# the implementation, edited by the user in the investigation\n")
        machine.launcher.script += [
            (T.INVESTIGATE_WORKFLOW, T.V_RESUME, {"destination": T.TEST_SUITE_ARBITRATING}),  # row 72
            (T.TEST_SUITE_ARBITRATING, T.V_REJECT_TESTS, {}),                                # row 62
        ]
        fixture.drive(machine, run)
        self.assertEqual([row.row for row, _, _ in machine.routed][-2:], ["72", "62"])
        self.assertEqual(run.current_state, T.TEST_WRITING)
        self.assertEqual(run.counters.value("arbitrator-rulings"), 1)
        self.assertEqual(self.arbitrator_launches(machine), 3)
        self.assertEqual(machine.machine_errors, [])
        resume_commit = machine.routed[-2][2]
        self.assertIn(fixture.COMPONENT_DIRECTORY + "/widget_counter.py",
                      record.git("show", "--name-only", "--format=", resume_commit).stdout.split())
        self.assertEqual(record.git("status", "--porcelain").stdout, "")


    def test_what_entered_the_arbitrator_is_kept_across_the_pause(self):
        # Section 6.5 after the ninth walk (item 5, user-ruled
        # 2026-09-11): the arbitrator returned to from an investigation
        # rules on the failed suite or the reviewer's ceiling that entered
        # it before the pause, and its `advance` means what it meant then.
        # So the resume does not record itself as what entered the state;
        # the failed suite that did is still there afterwards. That
        # `advance` is a machine error either way — a suite that failed is
        # never advanced because a run of it passed (the tenth walk, item
        # 16) — but its rejects route as they always do.
        machine, run, record = self.open_the_third_entry_investigation()
        self.assertEqual(run.test_suite_arbitrating_entered_from, T.TEST_SUITE_EXECUTING)
        machine.launcher.script += [
            (T.INVESTIGATE_WORKFLOW, T.V_RESUME, {"destination": T.TEST_SUITE_ARBITRATING}),  # row 72
            (T.TEST_SUITE_ARBITRATING, T.V_ADVANCE, {}),                                     # no row
        ]
        fixture.drive(machine, run)
        self.assertEqual(run.test_suite_arbitrating_entered_from, T.TEST_SUITE_EXECUTING)
        self.assertEqual(len(machine.machine_errors), 1)
        self.assertIsNone(machine.routed[-1][0])
        self.assertEqual(run.current_state, T.INVESTIGATE_WORKFLOW)
        self.assertEqual(run.paused_state, T.TEST_SUITE_ARBITRATING)
        self.assertEqual(self.arbitrator_launches(machine), 3)

    def test_the_arbitrator_returned_to_still_stands_in_for_the_reviewer_that_entered_it(self):
        # The other entry the pause keeps: a reviewer's ceiling. The
        # arbitrator entered from one, paused by an investigation and
        # returned to by a resume, still advances by row 60 — the reviewer
        # was wrong, and the artifact continues as if that reviewer had
        # advanced it (section 6.5; user-ruled 2026-09-11, the ninth walk,
        # item 5).
        script = fixture.prefix_to_design_approved()
        for _ in range(3):
            script += [fixture.implementation_write(),
                       (T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_REJECT_IMPLEMENTATION, {})]
        script += [
            (T.TEST_SUITE_ARBITRATING, T.V_ESCALATE_TO_USER, {}),                        # row 68
            (T.INVESTIGATE_WORKFLOW, T.V_RESUME, {}),                                    # row 72
            (T.TEST_SUITE_ARBITRATING, T.V_ADVANCE, {}),                                 # row 60
        ]
        machine, run, record, _ = fixture.make_machine(script, self.repository)
        fixture.drive(machine, run)
        self.assertEqual(run.test_suite_arbitrating_entered_from,
                         T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT)
        self.assertEqual([row.row for row, _, _ in machine.routed][-2:], ["72", "60"])
        self.assertEqual(machine.machine_errors, [])
        self.assertEqual(run.current_state, T.TEST_DESIGN_WRITING)

    def test_a_resume_may_name_the_arbitrator_only_from_an_investigation_that_paused_there(self):
        # Section 6.5 (user-ruled 2026-09-11, the ninth walk, item 5):
        # anywhere else there is no suite and no reviewer's ceiling to rule
        # on, so the destination is refused as a malformed resume — a
        # machine error, the pause unchanged, no arbitrator launched.
        script = fixture.prefix_to_design_approved() + [
            (T.IMPLEMENTATION_WRITING, T.V_INPUT_QUICK_CHECK_FAILED,
             {"input_named": T.INPUT_DESIGN}),                                           # row 23
            (T.INVESTIGATE_WORKFLOW, T.V_RESUME, {"destination": T.TEST_SUITE_ARBITRATING}),
        ]
        machine, run, record, _ = fixture.make_machine(script, self.repository)
        fixture.drive(machine, run)
        self.assertEqual(run.paused_state, T.IMPLEMENTATION_WRITING)
        self.assertEqual(len(machine.machine_errors), 1)
        self.assertIn(T.TEST_SUITE_ARBITRATING, run.machine_error)
        self.assertIsNone(machine.routed[-1][0])
        self.assertEqual(run.current_state, T.INVESTIGATE_WORKFLOW)
        self.assertEqual(self.arbitrator_launches(machine), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
