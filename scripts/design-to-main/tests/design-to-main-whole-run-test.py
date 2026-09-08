#!/usr/bin/env python3
"""One whole run of the design-to-main machine through the stub launcher,
from initiate-design-to-main to ended with outcome passed; one that ends
failed at the redesigns ceiling; and section 9's record — the topic
branch, one commit per state-exit with its trailer, run-state.json, the
user-rulings file, recovery from the last commit, and no push.

Run: python3 scripts/design-to-main/tests/design-to-main-whole-run-test.py
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
G = fixture.git_record_module
RunStateRecord = fixture.run_state_module.RunStateRecord


class WholeRunThatPasses(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.repository = fixture.ThrowawayRepository()
        cls.machine, cls.run_state, cls.record, _ = fixture.make_machine(
            fixture.whole_run_to_passed(), cls.repository)
        cls.outcome = cls.machine.run_until_ended(cls.run_state)

    @classmethod
    def tearDownClass(cls):
        cls.repository.remove()

    def test_the_run_ends_passed(self):
        self.assertEqual(self.outcome, T.OUTCOME_PASSED)
        self.assertEqual(self.run_state.current_state, T.ENDED)

    def test_the_states_were_visited_in_the_design_s_order(self):
        visited = [state_exit.state for _, state_exit, _ in self.machine.routed]
        self.assertEqual(visited, [
            T.INITIATE_DESIGN_TO_MAIN, T.DESIGN_WRITING, T.CONTRACT_ACCEPTANCE_BY_PROGRAM,
            T.DESIGN_ACCEPTANCE_BY_AGENT, T.DESIGN_ACCEPTANCE_BY_USER,
            T.IMPLEMENTATION_WRITING, T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT,
            T.TEST_DESIGN_WRITING, T.TEST_DESIGN_ACCEPTANCE_BY_AGENT, T.TEST_DESIGN_ACCEPTANCE_BY_USER,
            T.TEST_WRITING, T.TEST_ACCEPTANCE_BY_AGENT,
            T.TEST_SUITE_EXECUTING, T.SUBMIT_TO_PR_GATE,
        ])
        rows = [row.row for row, _, _ in self.machine.routed]
        self.assertEqual(rows, ["1", "2", "5", "3.1-a", "15", "18", "21", "29", "3.1-c", "36",
                                "37", "42", "51", "66"])

    def test_the_machine_cut_the_topic_branch_from_origin_main_named_for_the_component(self):
        self.assertEqual(self.record.current_branch(), fixture.COMPONENT)
        first_commit = self.machine.routed[0][2]
        parent = self.record.git("rev-parse", first_commit + "^").stdout.strip()
        origin_main = self.record.git("rev-parse", "origin/main").stdout.strip()
        self.assertEqual(parent, origin_main)

    def test_every_state_exit_is_one_commit_with_the_trailer_of_section_9(self):
        commits = self.record.commits_on_branch(since="origin/main")
        self.assertEqual(len(commits), len(self.machine.routed))
        for row, state_exit, commit in self.machine.routed:
            trailer = G.parse_state_exit_trailer(self.record.commit_message(commit))
            self.assertEqual(trailer["State"], state_exit.state)
            self.assertEqual(trailer["Exit"], state_exit.verdict)
            self.assertEqual(trailer["Package-commit"], state_exit.package_commit)
            for name in T.COUNTER_NAMES:
                self.assertIn("Counter-%s" % name, trailer)

    def test_the_write_number_rides_on_writes_only(self):
        for row, state_exit, commit in self.machine.routed:
            trailer = G.parse_state_exit_trailer(self.record.commit_message(commit))
            if state_exit.state in (T.IMPLEMENTATION_WRITING, T.TEST_WRITING):
                self.assertEqual(trailer["Write"], "1")
            else:
                self.assertNotIn("Write", trailer)

    def test_the_trailer_text_is_composed_as_section_9_lists_it(self):
        counters = {name: 0 for name in T.COUNTER_NAMES}
        counters["implementation-writes"] = 1
        text = G.compose_state_exit_trailer(
            T.IMPLEMENTATION_WRITING, T.V_EMITTED, "a" * 40, counters, write_number=1)
        self.assertEqual(text.splitlines()[:4], [
            "State: implementation-writing", "Exit: emitted", "Package-commit: " + "a" * 40, "Write: 1"])
        self.assertIn("Counter-implementation-writes: 1", text)
        self.assertIn("Counter-redesigns: 0", text)

    def test_each_package_commit_was_the_branch_head_when_the_state_was_launched(self):
        heads = ["origin/main"] + [commit for _, _, commit in self.machine.routed]
        for (row, state_exit, commit), head_before in zip(self.machine.routed, heads):
            self.assertEqual(state_exit.package_commit,
                             self.record.git("rev-parse", head_before).stdout.strip())

    def test_run_state_json_records_the_run_and_reads_back(self):
        path = self.record.absolute(self.record.run_state_path)
        self.assertTrue(path.exists())
        read_back = RunStateRecord.read_from(path)
        self.assertEqual(read_back.as_dict(), self.run_state.as_dict())
        self.assertEqual(read_back.outcome, T.OUTCOME_PASSED)
        self.assertEqual(read_back.design_version, 1)
        self.assertTrue(read_back.tests_begun)
        self.assertTrue(read_back.design_approved)
        self.assertTrue(read_back.test_design_approved)
        self.assertEqual(read_back.implementation_work_stream_position, T.READY_FOR_TEST_SUITE)
        self.assertEqual(read_back.test_work_stream_position, T.READY_FOR_TEST_SUITE)
        self.assertEqual(read_back.counters.as_dict(), {
            "redesigns": 0, "design-revisions": 0, "implementation-writes": 1, "test-writes": 1,
            "arbitrator-rulings": 0, "contract-revisions": 0, "test-design-corrections": 0})

    def test_the_machine_never_pushed(self):
        self.assertEqual(self.repository.origin_refs(), self.repository.origin_refs_at_start)
        for name in ("design-to-main-git-record.py", "design-to-main-state-machine.py"):
            self.assertNotIn('"push"', (fixture.MACHINE_DIR / name).read_text(), name)

    def test_the_state_package_names_what_section_3_1_lists(self):
        launched = {p["state"]: p for p in self.machine.launcher.launched}
        self.assertEqual(launched[T.TEST_SUITE_EXECUTING]["beyond-the-standard-package"],
                         "the implementation; the tests; the test-design")
        self.assertIn(str(self.record.user_rulings_path),
                      launched[T.IMPLEMENTATION_WRITING]["standard-package"])


class TwoWorkStreams(unittest.TestCase):
    """The revised-contract invalidation rule (section 3.2) with tests
    begun: both work-streams re-enter their writing states, the
    implementation-work-stream holds at ready-for-test-suite while the
    test-work-stream catches up, and they meet at test-suite-executing."""

    def test_a_contract_revision_after_tests_began_re_enters_both_and_they_meet_again(self):
        repository = fixture.ThrowawayRepository()
        try:
            script = fixture.prefix_to_test_writing() + [
                fixture.test_write(),
                (T.TEST_ACCEPTANCE_BY_AGENT, T.V_REJECT_CONTRACT, {}),            # row 48
                (T.CONTRACT_REVISING, T.V_EMITTED, {}),                            # row 16
                (T.CONTRACT_ACCEPTANCE_BY_PROGRAM, T.V_ADVANCE, {}),               # row 6
                (T.CONTRACT_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {}),                 # row 9
                fixture.implementation_write(),                                   # forced, uncharged
                (T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {}),           # row 23: holds
                (T.TEST_DESIGN_WRITING, T.V_EMITTED, {}),                          # row 29
                (T.TEST_DESIGN_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {}),
                (T.TEST_DESIGN_ACCEPTANCE_BY_USER, T.V_ADVANCE, {}),               # row 36
                fixture.test_write(),                                             # forced, uncharged
                (T.TEST_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {}),                     # row 42
                (T.TEST_SUITE_EXECUTING, T.V_PASS, {}),
                (T.SUBMIT_TO_PR_GATE, T.V_ACCEPTED, {}),
            ]
            machine, run, record, _ = fixture.make_machine(script, repository)
            self.assertEqual(machine.run_until_ended(run), T.OUTCOME_PASSED)
            rows = [row.row for row, _, _ in machine.routed]
            self.assertEqual(rows[-13:], ["48", "16", "6", "9", "18", "23", "29", "3.1-c", "36",
                                          "37", "42", "51", "66"])
            self.assertEqual(run.counters.value("contract-revisions"), 1)
            self.assertEqual(run.counters.value("implementation-writes"), 1)
            self.assertEqual(run.counters.value("test-writes"), 1)
            self.assertEqual(run.writes_emitted_per_version, {
                T.IMPLEMENTATION_WRITING: 2, T.TEST_WRITING: 2})
            self.assertEqual(run.writing_state_entry_reason[T.TEST_WRITING],
                             T.ENTRY_REASON_CONTRACT_REVISION)
        finally:
            repository.remove()


class WholeRunThatFailsAtTheRedesignsCeiling(unittest.TestCase):

    def test_three_redesigns_asked_for_the_run_ends_failed(self):
        repository = fixture.ThrowawayRepository()
        try:
            redesign_round = [
                (T.DESIGN_WRITING, T.V_EMITTED, {}),
                (T.CONTRACT_ACCEPTANCE_BY_PROGRAM, T.V_ADVANCE, {}),
                (T.DESIGN_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {}),
                (T.DESIGN_ACCEPTANCE_BY_USER, T.V_ADVANCE, {}),
                fixture.implementation_write(),
                (T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_REJECT_DESIGN, {}),    # row 27
                (T.INVESTIGATE_WORKFLOW, T.V_RESUME, {"destination": T.DESIGN_WRITING}),
            ]
            script = [(T.INITIATE_DESIGN_TO_MAIN, T.V_INVOKED, {})] + redesign_round * 3
            machine, run, record, _ = fixture.make_machine(script, repository)
            outcome = machine.run_until_ended(run)
            self.assertEqual(outcome, T.OUTCOME_FAILED)
            self.assertEqual(run.counters.value("redesigns"), 2)
            self.assertEqual(run.design_version, 3)
            self.assertEqual([r.row for r, _, _ in machine.routed][-3:], ["18", "27", "65"])
            trailer = G.parse_state_exit_trailer(record.commit_message("HEAD"))
            self.assertEqual(trailer["Counter-redesigns"], "2")
            self.assertEqual(RunStateRecord.read_from(
                record.absolute(record.run_state_path)).outcome, T.OUTCOME_FAILED)
            self.assertEqual(repository.origin_refs(), repository.origin_refs_at_start)
        finally:
            repository.remove()


class ResumingAnInvestigation(unittest.TestCase):

    def setUp(self):
        self.repository = fixture.ThrowawayRepository()

    def tearDown(self):
        self.repository.remove()

    def open_investigation(self):
        script = fixture.prefix_to_tests_begun() + [
            (T.TEST_DESIGN_WRITING, T.V_ESCALATE_TO_USER, {"investigation_focus": T.FOCUS_DESIGN}),
        ]
        machine, run, record, _ = fixture.make_machine(script, self.repository)
        fixture.drive(machine, run)
        self.assertEqual(run.current_state, T.INVESTIGATE_WORKFLOW)
        self.assertEqual(run.paused_state, T.TEST_DESIGN_WRITING)
        return machine, run, record

    def test_nothing_edited_resumes_the_state_that_was_paused(self):
        machine, run, record = self.open_investigation()
        machine.launcher.script.append((T.INVESTIGATE_WORKFLOW, T.V_RESUME, {}))
        fixture.drive(machine, run)
        self.assertEqual(run.current_state, T.TEST_DESIGN_WRITING)
        self.assertEqual(run.design_version, 1)

    def test_the_design_edited_resumes_as_a_redesign(self):
        machine, run, record = self.open_investigation()
        design = record.absolute(T.design_path_while_no_code_exists(fixture.COMPONENT))
        design.parent.mkdir(parents=True, exist_ok=True)
        design.write_text("# the design, edited by the user\n")
        machine.launcher.script.append((T.INVESTIGATE_WORKFLOW, T.V_RESUME, {}))
        fixture.drive(machine, run)
        self.assertEqual(run.current_state, T.DESIGN_WRITING)
        self.assertEqual(run.design_version, 2)
        self.assertEqual(run.counters.value("redesigns"), 1)

    def test_the_tests_edited_resumes_at_test_reviewing(self):
        machine, run, record = self.open_investigation()
        test_file = record.absolute(fixture.COMPONENT_DIRECTORY + "/tests/a-test.py")
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("# edited\n")
        machine.launcher.script.append((T.INVESTIGATE_WORKFLOW, T.V_RESUME, {}))
        fixture.drive(machine, run)
        self.assertEqual(run.current_state, T.TEST_REVIEWING)
        self.assertEqual(run.test_work_stream_position, T.TEST_REVIEWING)

    def test_stop_ends_the_run_stopped_by_user(self):
        machine, run, record = self.open_investigation()
        machine.launcher.script.append((T.INVESTIGATE_WORKFLOW, T.V_STOP, {}))
        self.assertEqual(machine.run_until_ended(run), T.OUTCOME_STOPPED_BY_USER)

    def test_a_ruling_given_in_the_dialog_is_appended_to_the_user_rulings_file(self):
        machine, run, record = self.open_investigation()
        machine.launcher.script.append(
            (T.INVESTIGATE_WORKFLOW, T.V_RESUME, {"rulings": ("the exit status of a refusal is 3",)}))
        fixture.drive(machine, run)
        self.assertEqual(record.absolute(record.user_rulings_path).read_text(),
                         "- the exit status of a refusal is 3 (user-ruled 2026-09-08)\n")


class RecoveryFromTheLastCommit(unittest.TestCase):

    def test_a_process_that_dies_before_committing_re_runs_the_state(self):
        repository = fixture.ThrowawayRepository()
        try:
            script = fixture.prefix_to_design_approved()
            machine, run, record, _ = fixture.make_machine(script, repository)
            fixture.drive(machine, run)
            self.assertEqual(run.current_state, T.IMPLEMENTATION_WRITING)
            # The writer's uncommitted files, then the process dies.
            stray = record.absolute(fixture.COMPONENT_DIRECTORY + "/half-written.py")
            stray.parent.mkdir(parents=True, exist_ok=True)
            stray.write_text("half\n")
            successor = M.DesignToMainStateMachineFlow(
                record, M.ScriptedStateExitLauncher([fixture.implementation_write()]),
                today=lambda: "2026-09-08")
            recovered = successor.recover()
            self.assertFalse(stray.exists())
            self.assertEqual(recovered.current_state, T.IMPLEMENTATION_WRITING)
            self.assertEqual(recovered.as_dict(), run.as_dict())
            fixture.drive(successor, recovered)
            self.assertEqual(recovered.current_state, T.IMPLEMENTATION_REVIEWING)
            self.assertEqual(recovered.counters.value("implementation-writes"), 1)
        finally:
            repository.remove()


if __name__ == "__main__":
    unittest.main(verbosity=2)
