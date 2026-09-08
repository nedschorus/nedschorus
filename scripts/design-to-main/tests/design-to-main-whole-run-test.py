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

    def test_a_stream_paused_in_a_reviewing_state_resumes_there_not_at_its_last_writing_state(self):
        # Row 49 opens an investigation with the test-work-stream in
        # test-reviewing; the user edits only the implementation and
        # resumes. Row 64 resumes at implementation-reviewing, its reviewer
        # advances, and row 23 holds the implementation and sends the run to
        # the test-work-stream's position: test-reviewing, not the
        # test-writing it was in before the tests were reviewed. No test
        # write is forced, and the test-writes counter does not move.
        repository = fixture.ThrowawayRepository()
        try:
            script = fixture.prefix_to_test_writing() + [
                fixture.test_write(),
                (T.TEST_ACCEPTANCE_BY_AGENT, T.V_REJECT_DESIGN, {}),              # row 49
            ]
            machine, run, record, _ = fixture.make_machine(script, repository)
            fixture.drive(machine, run)
            self.assertEqual(run.current_state, T.INVESTIGATE_WORKFLOW)
            self.assertEqual(run.paused_state, T.TEST_REVIEWING)
            implementation = record.absolute(fixture.COMPONENT_DIRECTORY + "/widget_counter.py")
            implementation.parent.mkdir(parents=True, exist_ok=True)
            implementation.write_text("# the implementation, edited by the user\n")
            machine.launcher.script += [
                (T.INVESTIGATE_WORKFLOW, T.V_RESUME, {}),                          # row 64
                (T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {}),           # row 23: holds
            ]
            fixture.drive(machine, run)
            self.assertEqual([row.row for row, _, _ in machine.routed][-3:], ["49", "64", "23"])
            self.assertEqual(run.current_state, T.TEST_REVIEWING)
            self.assertEqual(run.test_work_stream_position, T.TEST_REVIEWING)
            self.assertEqual(run.implementation_work_stream_position, T.READY_FOR_TEST_SUITE)
            self.assertEqual(run.counters.value("test-writes"), 1)
            self.assertEqual(run.writes_emitted_per_version[T.TEST_WRITING], 1)
            self.assertEqual(
                sum(1 for p in machine.launcher.launched if p["state"] == T.TEST_WRITING), 1)
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


class OpeningAnInvestigationDiscardsThePausedAgentsWork(unittest.TestCase):
    """Section 6.6: an investigation pauses the run — whatever agent was
    working is ended, its uncommitted work discarded, and its state re-run
    on resume. The opening commit carries the state-exit and the record,
    nothing the paused agent half-wrote; the resume diff therefore sees
    the user's edits and only those."""

    TEST_DESIGN = fixture.COMPONENT_DIRECTORY + "/widget-counter-test-design.md"
    IMPLEMENTATION = fixture.COMPONENT_DIRECTORY + "/widget_counter.py"

    def setUp(self):
        self.repository = fixture.ThrowawayRepository()

    def tearDown(self):
        self.repository.remove()

    def paths_in_commit_outside_the_record(self, record, commit):
        names = record.git("show", "--name-only", "--format=", commit).stdout.split()
        return [p for p in names if not p.startswith(str(record.record_directory) + "/")]

    def open_investigation_from_test_design_writing(self):
        """test-design-writing writes its draft and touches a tracked file,
        then escalates (row 61, focus design)."""
        script = fixture.prefix_to_tests_begun() + [
            (T.TEST_DESIGN_WRITING, T.V_ESCALATE_TO_USER, {
                "investigation_focus": T.FOCUS_DESIGN,
                fixture.FILES_WRITTEN_BEFORE_EMITTING: {
                    self.TEST_DESIGN: "# a half-written test-design\n",
                    "README.md": "main, touched by the writer\n",
                }}),
        ]
        machine, run, record, _ = fixture.make_machine(script, self.repository)
        fixture.drive(machine, run)
        self.assertEqual(run.current_state, T.INVESTIGATE_WORKFLOW)
        self.assertEqual(run.paused_state, T.TEST_DESIGN_WRITING)
        self.assertEqual(run.investigation_focus, T.FOCUS_DESIGN)
        return machine, run, record

    def test_the_opening_commit_carries_nothing_the_paused_agent_wrote(self):
        machine, run, record = self.open_investigation_from_test_design_writing()
        opening_commit = machine.routed[-1][2]
        self.assertEqual(self.paths_in_commit_outside_the_record(record, opening_commit), [])
        self.assertFalse(record.absolute(self.TEST_DESIGN).exists())
        self.assertEqual(record.absolute("README.md").read_text(), "main\n")
        self.assertEqual(record.git("status", "--porcelain").stdout, "")

    def test_nothing_edited_resumes_the_state_that_wrote_before_it_opened(self):
        machine, run, record = self.open_investigation_from_test_design_writing()
        machine.launcher.script.append((T.INVESTIGATE_WORKFLOW, T.V_RESUME, {}))
        fixture.drive(machine, run)
        self.assertEqual([row.row for row, _, _ in machine.routed][-2:], ["61", "64"])
        self.assertEqual(run.current_state, T.TEST_DESIGN_WRITING)
        self.assertEqual(run.design_version, 1)

    def test_the_design_edited_resumes_as_a_redesign_without_the_discarded_draft(self):
        machine, run, record = self.open_investigation_from_test_design_writing()
        design = record.absolute(T.design_path_while_no_code_exists(fixture.COMPONENT))
        design.parent.mkdir(parents=True, exist_ok=True)
        design.write_text("# the design, edited by the user\n")
        machine.launcher.script.append((T.INVESTIGATE_WORKFLOW, T.V_RESUME, {}))
        fixture.drive(machine, run)
        self.assertEqual(run.current_state, T.DESIGN_WRITING)
        self.assertEqual(run.design_version, 2)
        self.assertEqual(run.counters.value("redesigns"), 1)
        self.assertFalse(record.absolute(self.TEST_DESIGN).exists())
        self.assertEqual(record.git("ls-files", self.TEST_DESIGN).stdout, "")

    def test_row_20_a_partial_implementation_never_emitted_is_not_sent_to_review(self):
        # implementation-writing writes part of the implementation, then
        # finds the design wanting (row 20); the user edits nothing and
        # resumes: implementation-writing again, not implementation-
        # reviewing of a file its writer never emitted.
        script = fixture.prefix_to_design_approved() + [
            (T.IMPLEMENTATION_WRITING, T.V_INPUT_QUICK_CHECK_FAILED, {
                "input_named": T.INPUT_DESIGN,
                fixture.FILES_WRITTEN_BEFORE_EMITTING: {
                    self.IMPLEMENTATION: "# half an implementation\n"}}),
            (T.INVESTIGATE_WORKFLOW, T.V_RESUME, {}),
        ]
        machine, run, record, _ = fixture.make_machine(script, self.repository)
        fixture.drive(machine, run)
        self.assertEqual([row.row for row, _, _ in machine.routed][-2:], ["20", "64"])
        self.assertEqual(run.current_state, T.IMPLEMENTATION_WRITING)
        self.assertEqual(run.implementation_work_stream_position, T.IMPLEMENTATION_WRITING)
        self.assertFalse(record.absolute(self.IMPLEMENTATION).exists())
        self.assertEqual(run.counters.value("implementation-writes"), 0)


class AStrayVerdictFromWithinAnInvestigation(unittest.TestCase):
    """A state-exit from investigate-workflow outside stop, submit-to-PR-
    gate and resume is a machine error (section 3.2), but not a new
    investigation: the run stays paused where it was, with the focus and
    the opening commit it had, and the stray exit is committed like any
    other state-exit (section 9)."""

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

    def stray_verdict_then_check_the_pause_is_unchanged(self, machine, run, record,
                                                        verdict="continue", fields=None):
        opened_at = run.investigation_opened_at_commit
        opening_commit = machine.routed[-1][2]
        machine.launcher.script.append((T.INVESTIGATE_WORKFLOW, verdict, fields or {}))
        fixture.drive(machine, run)
        self.assertEqual(len(machine.machine_errors), 1)
        self.assertEqual(run.current_state, T.INVESTIGATE_WORKFLOW)
        self.assertEqual(run.paused_state, T.TEST_DESIGN_WRITING)
        self.assertEqual(run.investigation_focus, T.FOCUS_DESIGN)
        self.assertEqual(run.investigation_opened_at_commit, opened_at)
        self.assertEqual(record.commits_on_branch(since=opening_commit), [machine.routed[-1][2]])
        trailer = G.parse_state_exit_trailer(record.commit_message("HEAD"))
        self.assertEqual(trailer["State"], T.INVESTIGATE_WORKFLOW)
        self.assertEqual(trailer["Exit"], verdict)

    def test_a_stray_verdict_leaves_the_run_paused_where_it_was_and_a_plain_resume_returns_there(self):
        machine, run, record = self.open_investigation()
        self.stray_verdict_then_check_the_pause_is_unchanged(machine, run, record)
        machine.launcher.script.append((T.INVESTIGATE_WORKFLOW, T.V_RESUME, {}))
        fixture.drive(machine, run)
        self.assertEqual(machine.routed[-1][0].row, "64")
        self.assertIsNone(machine.routed[-2][0])   # the stray exit: a machine error, no row
        self.assertEqual(run.current_state, T.TEST_DESIGN_WRITING)
        self.assertEqual(run.design_version, 1)

    def test_the_users_edit_before_a_stray_verdict_is_still_seen_on_resume(self):
        machine, run, record = self.open_investigation()
        design = record.absolute(T.design_path_while_no_code_exists(fixture.COMPONENT))
        design.parent.mkdir(parents=True, exist_ok=True)
        design.write_text("# the design, edited by the user before the stray verdict\n")
        self.stray_verdict_then_check_the_pause_is_unchanged(machine, run, record)
        self.assertEqual(design.read_text(),
                         "# the design, edited by the user before the stray verdict\n")
        machine.launcher.script.append((T.INVESTIGATE_WORKFLOW, T.V_RESUME, {}))
        fixture.drive(machine, run)
        self.assertEqual(run.current_state, T.DESIGN_WRITING)
        self.assertEqual(run.design_version, 2)
        self.assertEqual(run.counters.value("redesigns"), 1)

    def test_a_resume_to_a_mistyped_destination_is_a_machine_error_not_a_crash(self):
        # The dialog is where a human types a state name. A destination
        # that names no state is a machine error like any illegal
        # state-exit (section 3.2, "any other state-exit"): committed,
        # the run left paused where it was, and the next resume routed.
        machine, run, record = self.open_investigation()
        self.stray_verdict_then_check_the_pause_is_unchanged(
            machine, run, record, verdict=T.V_RESUME, fields={"destination": "desgin-writing"})
        self.assertIn("desgin-writing", run.machine_error)
        machine.launcher.script.append(
            (T.INVESTIGATE_WORKFLOW, T.V_RESUME, {"destination": T.DESIGN_WRITING}))
        fixture.drive(machine, run)
        self.assertEqual(machine.routed[-1][0].row, "64")
        self.assertEqual(run.current_state, T.DESIGN_WRITING)
        self.assertEqual(run.design_version, 2)
        self.assertEqual(run.counters.value("redesigns"), 1)


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

    def test_a_process_that_dies_after_staging_leaves_nothing_staged_for_the_next_state_exit(self):
        # The window is the record's own: every state-exit is `add -A` then
        # `commit` as two subprocesses, and on a resume paths_changed_since
        # stages the whole checkout well before the commit. A process that
        # dies inside that window leaves its files STAGED; recovery puts
        # the index back to HEAD as well as the working tree, so the next
        # state-exit's `add -A` does not commit the dead process's
        # leftovers as that state's work.
        repository = fixture.ThrowawayRepository()
        try:
            script = fixture.prefix_to_design_approved()
            machine, run, record, _ = fixture.make_machine(script, repository)
            fixture.drive(machine, run)
            self.assertEqual(run.current_state, T.IMPLEMENTATION_WRITING)
            head_before = record.head_commit()
            half_written = fixture.COMPONENT_DIRECTORY + "/half-written.py"
            stray = record.absolute(half_written)
            stray.parent.mkdir(parents=True, exist_ok=True)
            stray.write_text("half\n")
            readme = record.absolute("README.md")
            readme.write_text("main, edited by the dead process\n")
            record.git("add", "-A")   # as commit_state_exit would have, then the process dies
            self.assertEqual(sorted(record.git("status", "--porcelain").stdout.splitlines()),
                             ["A  " + half_written, "M  README.md"])
            successor = M.DesignToMainStateMachineFlow(
                record, M.ScriptedStateExitLauncher([fixture.implementation_write()]),
                today=lambda: "2026-09-08")
            recovered = successor.recover()
            self.assertFalse(stray.exists())
            self.assertEqual(readme.read_text(), "main\n")
            self.assertEqual(record.git("status", "--porcelain").stdout, "")
            self.assertEqual(record.head_commit(), head_before)
            fixture.drive(successor, recovered)
            self.assertEqual(recovered.current_state, T.IMPLEMENTATION_REVIEWING)
            emitted_commit = successor.routed[-1][2]
            files_in_commit = record.git("show", "--name-only", "--format=", emitted_commit).stdout.split()
            self.assertNotIn(half_written, files_in_commit)
            self.assertNotIn("README.md", files_in_commit)
            self.assertIn(str(record.run_state_path), files_in_commit)
            self.assertFalse(stray.exists())
        finally:
            repository.remove()

    def test_the_commit_of_a_resume_into_design_writing_already_carries_the_redesign(self):
        # Entry-charged counters (redesigns, arbitrator-rulings) are applied
        # before the state-exit that enters the state is committed, so a
        # process that dies right after that commit recovers the charge.
        repository = fixture.ThrowawayRepository()
        try:
            script = fixture.prefix_to_design_approved() + [
                (T.IMPLEMENTATION_WRITING, T.V_INPUT_QUICK_CHECK_FAILED, {"input_named": T.INPUT_DESIGN}),
                (T.INVESTIGATE_WORKFLOW, T.V_RESUME, {"destination": T.DESIGN_WRITING}),
            ]
            machine, run, record, _ = fixture.make_machine(script, repository)
            fixture.drive(machine, run)
            self.assertEqual(run.current_state, T.DESIGN_WRITING)
            trailer = G.parse_state_exit_trailer(record.commit_message("HEAD"))
            self.assertEqual(trailer["Counter-redesigns"], "1")
            recovered = M.DesignToMainStateMachineFlow(
                record, M.ScriptedStateExitLauncher([]), today=lambda: "2026-09-08").recover()
            self.assertEqual(recovered.as_dict(), run.as_dict())
            self.assertEqual(recovered.design_version, 2)
            self.assertEqual(recovered.counters.value("redesigns"), 1)
        finally:
            repository.remove()

    def test_the_commit_of_a_reject_at_the_ceiling_already_carries_the_arbitrator_s_entry(self):
        repository = fixture.ThrowawayRepository()
        try:
            script = fixture.prefix_to_design_approved()
            for _ in range(3):
                script += [fixture.implementation_write(),
                           (T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_REJECT_IMPLEMENTATION, {})]
            machine, run, record, _ = fixture.make_machine(script, repository)
            fixture.drive(machine, run)
            self.assertEqual(run.current_state, T.TEST_SUITE_ARBITRATING)
            trailer = G.parse_state_exit_trailer(record.commit_message("HEAD"))
            self.assertEqual(trailer["Counter-arbitrator-rulings"], "1")
            recovered = RunStateRecord.read_from(record.absolute(record.run_state_path))
            self.assertEqual(recovered.current_state, T.TEST_SUITE_ARBITRATING)
            self.assertEqual(recovered.counters.value("arbitrator-rulings"), 1)
        finally:
            repository.remove()

    def test_a_process_that_dies_during_an_investigation_recovers_the_commit_it_opened_at(self):
        # The commit at which the investigation opened (section 6.6) is in
        # run-state.json on the branch for the whole pause, so a successor
        # that recovers from investigate-workflow still diffs the branch
        # on resume: the design edited resumes as a redesign, not at the
        # state that was paused in design version 1.
        repository = fixture.ThrowawayRepository()
        try:
            script = fixture.prefix_to_tests_begun() + [
                (T.TEST_DESIGN_WRITING, T.V_ESCALATE_TO_USER, {"investigation_focus": T.FOCUS_DESIGN}),
            ]
            machine, run, record, _ = fixture.make_machine(script, repository)
            fixture.drive(machine, run)
            self.assertEqual(run.current_state, T.INVESTIGATE_WORKFLOW)
            self.assertEqual(run.paused_state, T.TEST_DESIGN_WRITING)
            on_the_branch = RunStateRecord.read_from(record.absolute(record.run_state_path))
            self.assertIsNotNone(on_the_branch.investigation_opened_at_commit)
            self.assertEqual(on_the_branch.as_dict(), run.as_dict())
            # The process dies; a successor recovers, then the user edits
            # the design and resumes without naming a destination.
            successor = M.DesignToMainStateMachineFlow(
                record, M.ScriptedStateExitLauncher([(T.INVESTIGATE_WORKFLOW, T.V_RESUME, {})]),
                today=lambda: "2026-09-08")
            recovered = successor.recover()
            self.assertEqual(recovered.current_state, T.INVESTIGATE_WORKFLOW)
            self.assertEqual(recovered.investigation_opened_at_commit,
                             run.investigation_opened_at_commit)
            design = record.absolute(T.design_path_while_no_code_exists(fixture.COMPONENT))
            design.parent.mkdir(parents=True, exist_ok=True)
            design.write_text("# the design, edited by the user during the investigation\n")
            fixture.drive(successor, recovered)
            self.assertEqual([row.row for row, _, _ in successor.routed], ["64"])
            self.assertEqual(recovered.current_state, T.DESIGN_WRITING)
            self.assertEqual(recovered.design_version, 2)
            self.assertEqual(recovered.counters.value("redesigns"), 1)
        finally:
            repository.remove()


class TopicBranchRefusedAtRow1(unittest.TestCase):
    """Section 6.6: the machine cuts the topic branch and, if the name is
    refused, says so in the invoking conversation and the run does not
    start. A re-invocation for a component whose branch already exists is
    the case: nothing is committed, and the checkout is as it was."""

    def test_a_branch_that_already_exists_is_reported_as_a_refusal_and_the_run_does_not_start(self):
        repository = fixture.ThrowawayRepository()
        try:
            fixture.git(repository.checkout, "branch", fixture.COMPONENT, "origin/main")
            branch_before = fixture.git(repository.checkout, "rev-parse", "--abbrev-ref", "HEAD")
            head_before = fixture.git(repository.checkout, "rev-parse", "HEAD")
            # The invocation carries a ruling: a refused invocation must
            # leave no file behind, the user-rulings file included.
            script = [(T.INITIATE_DESIGN_TO_MAIN, T.V_INVOKED,
                       {"rulings": ("a ruling given at the invocation",)})]
            machine, run, record, _ = fixture.make_machine(script, repository)
            with self.assertRaises(M.TopicBranchCutRefused) as refused:
                machine.run_until_ended(run)
            self.assertIn(fixture.COMPONENT, str(refused.exception))
            self.assertIn("already exists", str(refused.exception))
            self.assertEqual(run.current_state, T.INITIATE_DESIGN_TO_MAIN)
            self.assertFalse(run.topic_branch_cut)
            self.assertEqual(machine.routed, [])
            self.assertEqual(fixture.git(repository.checkout, "rev-parse", "--abbrev-ref", "HEAD"),
                             branch_before)
            self.assertEqual(fixture.git(repository.checkout, "rev-parse", "HEAD"), head_before)
            self.assertEqual(fixture.git(repository.checkout, "status", "--porcelain"), "")
            self.assertFalse(record.absolute(record.run_state_path).exists())
            self.assertFalse(record.absolute(record.user_rulings_path).exists())
            self.assertFalse(record.absolute(record.record_directory).exists())
        finally:
            repository.remove()


class AStrayVerdictBeforeTheTopicBranchIsCut(unittest.TestCase):
    """Before row 1 has cut the topic branch the machine owns nothing: the
    checkout is the invoking conversation's, standing on whatever branch
    it stood on, with whatever uncommitted work it had. A verdict from
    initiate-design-to-main other than `invoked` is a machine error, but
    it cannot open an investigation there — the opening discard and commit
    would run against the invoker's checkout. It is refused the way a
    refused branch name is (section 6.6): reported to the invoking
    conversation, the run does not start, the checkout is as it was. What
    decides is the run's own record of row 1's cut, not the branch the
    checkout stands on (AReInvocationFromAFinishedRunsCheckout, below)."""

    def setUp(self):
        self.repository = fixture.ThrowawayRepository()
        checkout = self.repository.checkout
        (checkout / "seat-notes.md").write_text("untracked notes on main\n")
        (checkout / "README.md").write_text("main, edited but not committed\n")
        self.status_before = fixture.git(checkout, "status", "--porcelain")
        self.assertEqual(sorted(self.status_before.splitlines()),
                         [" M README.md", "?? seat-notes.md"])
        self.branch_before = fixture.git(checkout, "rev-parse", "--abbrev-ref", "HEAD")
        self.head_before = fixture.git(checkout, "rev-parse", "HEAD")
        self.assertEqual(self.branch_before.strip(), "main")

    def tearDown(self):
        self.repository.remove()

    def check_the_checkout_is_as_it_was(self, record):
        checkout = self.repository.checkout
        self.assertEqual((checkout / "seat-notes.md").read_text(), "untracked notes on main\n")
        self.assertEqual((checkout / "README.md").read_text(), "main, edited but not committed\n")
        self.assertEqual(fixture.git(checkout, "status", "--porcelain"), self.status_before)
        self.assertEqual(fixture.git(checkout, "rev-parse", "--abbrev-ref", "HEAD"), self.branch_before)
        self.assertEqual(fixture.git(checkout, "rev-parse", "HEAD"), self.head_before)
        self.assertFalse(record.absolute(record.run_state_path).exists())
        self.assertFalse(record.absolute(record.record_directory).exists())

    def test_a_stray_verdict_from_initiate_design_to_main_is_refused_and_the_run_does_not_start(self):
        script = [(T.INITIATE_DESIGN_TO_MAIN, "started", {})]
        machine, run, record, _ = fixture.make_machine(script, self.repository)
        with self.assertRaises(M.RefusedBeforeTopicBranchCut) as refused:
            machine.run_until_ended(run)
        self.assertIn("started", str(refused.exception))
        self.assertIn(T.INITIATE_DESIGN_TO_MAIN, str(refused.exception))
        self.assertEqual(run.current_state, T.INITIATE_DESIGN_TO_MAIN)
        self.assertIsNone(run.paused_state)
        self.assertEqual(machine.routed, [])
        self.check_the_checkout_is_as_it_was(record)

    def test_a_stray_verdict_carrying_a_ruling_is_refused_and_writes_no_rulings_file(self):
        # The ruling rides on the refused invocation: it is not written,
        # because a refused invocation leaves no file behind.
        script = [(T.INITIATE_DESIGN_TO_MAIN, "started",
                   {"rulings": ("a ruling given at the invocation",)})]
        machine, run, record, _ = fixture.make_machine(script, self.repository)
        with self.assertRaises(M.RefusedBeforeTopicBranchCut):
            machine.run_until_ended(run)
        self.assertEqual(run.current_state, T.INITIATE_DESIGN_TO_MAIN)
        self.assertEqual(machine.routed, [])
        self.assertFalse(record.absolute(record.user_rulings_path).exists())
        self.check_the_checkout_is_as_it_was(record)

    def test_the_record_itself_refuses_to_discard_or_commit_before_row_1_cut_the_branch(self):
        # The structural guard: whatever performs a discard or a commit
        # takes the run and refuses while row 1 has not cut its topic
        # branch, so a future row that skips the cut cannot reach the
        # invoker's checkout, whatever branch it stands on.
        machine, run, record, _ = fixture.make_machine([], self.repository)
        self.assertFalse(run.topic_branch_cut)
        self.assertFalse(record.topic_branch_is_checked_out())
        with self.assertRaises(M.RefusedBeforeTopicBranchCut):
            record.discard_uncommitted_work_outside_the_record(run)
        with self.assertRaises(M.RefusedBeforeTopicBranchCut):
            record.discard_all_uncommitted_work_for_recovery(run)
        with self.assertRaises(M.RefusedBeforeTopicBranchCut):
            record.commit_state_exit(run, "widget-counter: a commit before the cut", "State: x\n")
        with self.assertRaises(M.RefusedBeforeTopicBranchCut):
            machine.commit_state_exit(run, M.StateExitRecord(
                state=T.INITIATE_DESIGN_TO_MAIN, verdict="started", package_commit="x"), None)
        with self.assertRaises(M.RefusedBeforeTopicBranchCut):
            machine.recover()
        self.check_the_checkout_is_as_it_was(record)

    def test_the_record_refuses_a_run_not_yet_cut_even_with_the_checkout_on_the_topic_branch(self):
        # The branch name alone cannot tell a fresh run from a finished
        # run's leftover checkout; the run's own flag decides. Here the
        # checkout stands on the component's branch and the run has not
        # been routed by row 1: refused, nothing discarded, nothing committed.
        checkout = self.repository.checkout
        fixture.git(checkout, "checkout", "-q", "-b", fixture.COMPONENT)
        machine, run, record, _ = fixture.make_machine([], self.repository)
        self.assertTrue(record.topic_branch_is_checked_out())
        self.assertFalse(run.topic_branch_cut)
        head_before = fixture.git(checkout, "rev-parse", "HEAD")
        with self.assertRaises(M.RefusedBeforeTopicBranchCut):
            record.discard_uncommitted_work_outside_the_record(run)
        with self.assertRaises(M.RefusedBeforeTopicBranchCut):
            record.discard_all_uncommitted_work_for_recovery(run)
        with self.assertRaises(M.RefusedBeforeTopicBranchCut):
            record.commit_state_exit(run, "widget-counter: a commit before the cut", "State: x\n")
        with self.assertRaises(M.RefusedBeforeTopicBranchCut):
            machine.commit_state_exit(run, M.StateExitRecord(
                state=T.INITIATE_DESIGN_TO_MAIN, verdict="started", package_commit="x"), None)
        with self.assertRaises(M.RefusedBeforeTopicBranchCut):
            machine.recover()   # no state-exit is committed at HEAD: nothing to recover
        self.assertEqual((checkout / "seat-notes.md").read_text(), "untracked notes on main\n")
        self.assertEqual((checkout / "README.md").read_text(), "main, edited but not committed\n")
        self.assertEqual(fixture.git(checkout, "status", "--porcelain"), self.status_before)
        self.assertEqual(fixture.git(checkout, "rev-parse", "HEAD"), head_before)
        self.assertFalse(record.absolute(record.record_directory).exists())


class AReInvocationFromAFinishedRunsCheckout(unittest.TestCase):
    """This slice's only branch switch is row 1's `checkout -b`, so every
    finished run leaves the checkout on its topic branch. A re-invocation
    for the same component from there is a fresh run that row 1 has not
    yet routed: the branch's name says nothing about it, and a stray
    verdict from initiate-design-to-main must be refused exactly as it is
    from `main` — the invoker's uncommitted work kept, the finished run's
    branch head and its run-state.json untouched."""

    def setUp(self):
        self.repository = fixture.ThrowawayRepository()

    def tearDown(self):
        self.repository.remove()

    def test_a_stray_verdict_after_a_finished_run_does_not_touch_the_finished_runs_branch(self):
        machine, run, record, _ = fixture.make_machine(
            fixture.whole_run_to_passed(), self.repository)
        self.assertEqual(machine.run_until_ended(run), T.OUTCOME_PASSED)
        checkout = self.repository.checkout
        self.assertEqual(record.current_branch(), fixture.COMPONENT)
        run_state_path = record.absolute(record.run_state_path)
        run_state_before = run_state_path.read_text()
        head_before = fixture.git(checkout, "rev-parse", "HEAD")
        # The invoker's uncommitted work, where the finished run left the checkout.
        (checkout / "seat-notes.md").write_text("untracked notes after the run\n")
        (checkout / "README.md").write_text("main, edited but not committed\n")
        status_before = fixture.git(checkout, "status", "--porcelain")
        self.assertEqual(sorted(status_before.splitlines()),
                         [" M README.md", "?? seat-notes.md"])

        second_machine, second_run, second_record, _ = fixture.make_machine(
            [(T.INITIATE_DESIGN_TO_MAIN, "started", {})], self.repository)
        with self.assertRaises(M.RefusedBeforeTopicBranchCut) as refused:
            second_machine.run_until_ended(second_run)
        self.assertIn("started", str(refused.exception))
        self.assertEqual(second_run.current_state, T.INITIATE_DESIGN_TO_MAIN)
        self.assertFalse(second_run.topic_branch_cut)
        self.assertEqual(second_machine.routed, [])

        self.assertEqual((checkout / "seat-notes.md").read_text(), "untracked notes after the run\n")
        self.assertEqual((checkout / "README.md").read_text(), "main, edited but not committed\n")
        self.assertEqual(fixture.git(checkout, "status", "--porcelain"), status_before)
        self.assertEqual(fixture.git(checkout, "rev-parse", "--abbrev-ref", "HEAD").strip(),
                         fixture.COMPONENT)
        self.assertEqual(fixture.git(checkout, "rev-parse", "HEAD"), head_before)
        self.assertEqual(run_state_path.read_text(), run_state_before)
        self.assertEqual(RunStateRecord.read_from(run_state_path).outcome, T.OUTCOME_PASSED)
        self.assertEqual(fixture.git(checkout, "show", "HEAD:" + str(record.run_state_path)),
                         run_state_before)

    def test_recovery_from_a_finished_runs_checkout_discards_nothing(self):
        # A run at `ended` has no state to re-run, so the discard that
        # recovery does for a dead process has no purpose there: the
        # uncommitted work in the checkout is the invoker's, kept. What
        # recover() should return or refuse on a finished run is the
        # user's to rule; this pins only that nothing is discarded.
        machine, run, record, _ = fixture.make_machine(
            fixture.whole_run_to_passed(), self.repository)
        self.assertEqual(machine.run_until_ended(run), T.OUTCOME_PASSED)
        checkout = self.repository.checkout
        (checkout / "seat-notes.md").write_text("untracked notes after the run\n")
        (checkout / "README.md").write_text("main, edited but not committed\n")
        status_before = fixture.git(checkout, "status", "--porcelain")
        head_before = fixture.git(checkout, "rev-parse", "HEAD")
        successor = M.DesignToMainStateMachineFlow(
            record, M.ScriptedStateExitLauncher([]), today=lambda: "2026-09-08")
        successor.recover()
        self.assertEqual((checkout / "seat-notes.md").read_text(), "untracked notes after the run\n")
        self.assertEqual((checkout / "README.md").read_text(), "main, edited but not committed\n")
        self.assertEqual(fixture.git(checkout, "status", "--porcelain"), status_before)
        self.assertEqual(fixture.git(checkout, "rev-parse", "HEAD"), head_before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
