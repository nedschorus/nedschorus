#!/usr/bin/env python3
"""The design-to-main machine's investigations, driven through the stub
launcher: what opening one discards and commits, what a resume commits
and where it returns, and a stray verdict from within one.

The whole-run cases are split over four files,
design-to-main-whole-run-*-test.py, so that the suite runner runs them at
the same time.

Run: python3 scripts/design-to-main/tests/design-to-main-whole-run-investigations-test.py
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
G = fixture.git_record_module


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
        design = record.absolute(fixture.DESIGN_PATH)
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
    on resume. The opening commit carries the state-exit, the files it
    names and the record, nothing the paused agent half-wrote and did not
    name; the discard runs after the commit, as after every commit
    (section 9), and the resume diff therefore sees the user's edits and
    only those."""

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
        then escalates (row 69, focus design)."""
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
        self.assertEqual([row.row for row, _, _ in machine.routed][-2:], ["69", "72"])
        self.assertEqual(run.current_state, T.TEST_DESIGN_WRITING)
        self.assertEqual(run.design_version, 1)

    def test_the_design_edited_resumes_as_a_redesign_without_the_discarded_draft(self):
        machine, run, record = self.open_investigation_from_test_design_writing()
        design = record.absolute(fixture.DESIGN_PATH)
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
        # finds the design wanting (row 23); the user edits nothing and
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
        self.assertEqual([row.row for row, _, _ in machine.routed][-2:], ["23", "72"])
        self.assertEqual(run.current_state, T.IMPLEMENTATION_WRITING)
        self.assertEqual(run.implementation_work_stream_position, T.IMPLEMENTATION_WRITING)
        self.assertFalse(record.absolute(self.IMPLEMENTATION).exists())
        self.assertEqual(run.counters.value("implementation-writes"), 0)


class AnInvestigationOpeningStateExitNamingFilesHasThemCommitted(unittest.TestCase):
    """PR #295, round 2, finding 2, and section 9 after the eighth walk
    (item 7): a writer that stops mid-write names what it has written so
    far, and the next writer receives it. So an investigation-opening
    state-exit that names files has them committed — a modified tracked
    file is not reverted to HEAD, an untracked one does not crash the
    restricted add — and the discard removes only what no state-exit
    named, after the commit. The resume diff runs against the opening
    commit, so the partial a writer named is not mistaken for the user's
    edit."""

    IMPLEMENTATION = fixture.COMPONENT_DIRECTORY + "/widget_counter.py"
    REVIEW_NOTES = fixture.COMPONENT_DIRECTORY + "/review-notes.md"
    V1 = "# the implementation, v1\n"
    PARTIAL = "# the implementation, v2, half-fixed when the writer found the design wanting\n"

    def setUp(self):
        self.repository = fixture.ThrowawayRepository()

    def tearDown(self):
        self.repository.remove()

    def paths_in_commit(self, record, commit):
        return record.git("show", "--name-only", "--format=", commit).stdout.split()

    def test_a_partial_write_named_by_an_input_quick_check_failed_is_in_the_opening_commit(self):
        script = fixture.prefix_to_design_approved() + [
            (T.IMPLEMENTATION_WRITING, T.V_EMITTED, {
                "coverage_types": ("script",),
                "named_files": (self.IMPLEMENTATION,),
                fixture.FILES_WRITTEN_BEFORE_EMITTING: {self.IMPLEMENTATION: self.V1}}),
            (T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_REJECT_IMPLEMENTATION, {}),   # row 27
            (T.IMPLEMENTATION_WRITING, T.V_INPUT_QUICK_CHECK_FAILED, {
                "input_named": T.INPUT_DESIGN,
                "named_files": (self.IMPLEMENTATION,),
                fixture.FILES_WRITTEN_BEFORE_EMITTING: {
                    self.IMPLEMENTATION: self.PARTIAL,
                    "README.md": "main, touched by the writer\n"}}),                # row 23
        ]
        machine, run, record, _ = fixture.make_machine(script, self.repository)
        fixture.drive(machine, run)
        self.assertEqual(machine.routed[-1][0].row, "23")
        self.assertEqual(run.current_state, T.INVESTIGATE_WORKFLOW)
        opening_commit = machine.routed[-1][2]
        self.assertIn(self.IMPLEMENTATION, self.paths_in_commit(record, opening_commit))
        self.assertEqual(record.git("show", "HEAD:" + self.IMPLEMENTATION).stdout, self.PARTIAL)
        self.assertEqual(record.absolute(self.IMPLEMENTATION).read_text(), self.PARTIAL)
        self.assertEqual(record.absolute("README.md").read_text(), "main\n")   # not named: discarded
        self.assertEqual(record.git("status", "--porcelain").stdout, "")
        # Nothing edited: the resume returns to the writer, which receives
        # the partial; the partial is not read as the user's edit.
        machine.launcher.script.append((T.INVESTIGATE_WORKFLOW, T.V_RESUME, {}))
        fixture.drive(machine, run)
        self.assertEqual(machine.routed[-1][0].row, "72")
        self.assertEqual(run.current_state, T.IMPLEMENTATION_WRITING)
        self.assertEqual(record.git("show", "HEAD:" + self.IMPLEMENTATION).stdout, self.PARTIAL)

    def test_an_untracked_file_named_by_a_reject_design_is_committed_not_a_crash(self):
        script = fixture.prefix_to_design_approved() + [
            (T.IMPLEMENTATION_WRITING, T.V_EMITTED, {
                "coverage_types": ("script",),
                "named_files": (self.IMPLEMENTATION,),
                fixture.FILES_WRITTEN_BEFORE_EMITTING: {self.IMPLEMENTATION: self.V1}}),
            (T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_REJECT_DESIGN, {
                "named_files": (self.REVIEW_NOTES,),
                fixture.FILES_WRITTEN_BEFORE_EMITTING: {
                    self.REVIEW_NOTES: "the failure scenario in the design\n"}}),   # row 30
        ]
        machine, run, record, _ = fixture.make_machine(script, self.repository)
        fixture.drive(machine, run)
        self.assertEqual(machine.routed[-1][0].row, "30")
        self.assertEqual(machine.machine_errors, [])
        self.assertEqual(run.current_state, T.INVESTIGATE_WORKFLOW)
        opening_commit = machine.routed[-1][2]
        self.assertIn(self.REVIEW_NOTES, self.paths_in_commit(record, opening_commit))
        self.assertEqual(record.git("show", "HEAD:" + self.REVIEW_NOTES).stdout,
                         "the failure scenario in the design\n")
        self.assertEqual(record.git("status", "--porcelain").stdout, "")
        # On disk the run-state is the committed one: HEAD and the file agree.
        self.assertEqual(record.absolute(record.run_state_path).read_text(),
                         record.git("show", "HEAD:" + str(record.run_state_path)).stdout)
        machine.launcher.script.append((T.INVESTIGATE_WORKFLOW, T.V_RESUME, {}))
        fixture.drive(machine, run)
        self.assertEqual(run.current_state, T.IMPLEMENTATION_REVIEWING)   # the paused state


class AResumeCommitsWhatTheUserChangedInTheInvestigation(unittest.TestCase):
    """Section 6.6: in an investigation the user may edit any file on the
    branch. Section 9: a state-exit's commit carries only the files it
    names — and the resume's, for the user's edits, are the paths the
    machine's own diff found changed since the investigation opened (the
    same paths it routes on), or the next discard erases them and the
    next state's package-commit does not hold them (PR #295, round 1)."""

    IMPLEMENTATION = fixture.COMPONENT_DIRECTORY + "/widget_counter.py"
    A_NEW_FILE = fixture.COMPONENT_DIRECTORY + "/widget_counter_helper.py"
    V1 = "# the implementation, v1\n"
    V2 = "# the implementation, v2, edited by the user in the investigation\n"

    def setUp(self):
        self.repository = fixture.ThrowawayRepository()

    def tearDown(self):
        self.repository.remove()

    def paths_in_commit(self, record, commit):
        return record.git("show", "--name-only", "--format=", commit).stdout.split()

    def open_the_investigation_with_v1_committed(self):
        """The implementation-write commits v1 (named); tests written and
        accepted; the suite fails; the arbitrator escalates (row 68, its
        first entry)."""
        script = fixture.prefix_to_design_approved() + [
            (T.IMPLEMENTATION_WRITING, T.V_EMITTED, {
                "coverage_types": ("script",),
                "named_files": (self.IMPLEMENTATION,),
                fixture.FILES_WRITTEN_BEFORE_EMITTING: {self.IMPLEMENTATION: self.V1}}),
            (T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {}),
            (T.TEST_DESIGN_WRITING, T.V_EMITTED, {}),
            (T.TEST_DESIGN_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {}),
            (T.TEST_DESIGN_ACCEPTANCE_BY_USER, T.V_ADVANCE, {}),
            fixture.test_write(),
            (T.TEST_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {}),
            (T.TEST_SUITE_EXECUTING, T.V_FAIL, {}),
            (T.TEST_SUITE_ARBITRATING, T.V_ESCALATE_TO_USER, {}),
        ]
        machine, run, record, _ = fixture.make_machine(script, self.repository)
        fixture.drive(machine, run)
        self.assertEqual(run.current_state, T.INVESTIGATE_WORKFLOW)
        self.assertEqual(run.paused_state, T.TEST_SUITE_ARBITRATING)
        self.assertEqual(record.git("show", "HEAD:" + self.IMPLEMENTATION).stdout, self.V1)
        return machine, run, record

    def test_the_users_edit_to_a_tracked_file_rides_in_the_resume_commit_and_survives_the_next_discard(self):
        machine, run, record = self.open_the_investigation_with_v1_committed()
        record.absolute(self.IMPLEMENTATION).write_text(self.V2)
        machine.launcher.script += [
            (T.INVESTIGATE_WORKFLOW, T.V_RESUME, {}),
            (T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {}),
            (T.TEST_SUITE_EXECUTING, T.V_FAIL, {}),
            (T.TEST_SUITE_ARBITRATING, T.V_ESCALATE_TO_USER, {}),
        ]
        fixture.drive(machine, run)
        rows = [row.row for row, _, _ in machine.routed]
        self.assertEqual(rows[-4:], ["72", "25", "57", "68"])
        resume_commit = machine.routed[-4][2]
        self.assertEqual(machine.routed[-4][1].verdict, T.V_RESUME)
        self.assertIn(self.IMPLEMENTATION, self.paths_in_commit(record, resume_commit))
        self.assertEqual(record.git("show", "%s:%s" % (resume_commit, self.IMPLEMENTATION)).stdout, self.V2)
        # The next state's package-commit is the resume commit, which holds
        # the edit: an agent in a worktree of the branch sees v2.
        launched_after_the_resume = machine.launcher.launched[-3]
        self.assertEqual(launched_after_the_resume["state"], T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT)
        self.assertEqual(launched_after_the_resume["package-commit"], resume_commit)
        # After the second investigation's discard, worktree and HEAD both read v2.
        self.assertEqual(run.current_state, T.INVESTIGATE_WORKFLOW)
        self.assertEqual(record.absolute(self.IMPLEMENTATION).read_text(), self.V2)
        self.assertEqual(record.git("show", "HEAD:" + self.IMPLEMENTATION).stdout, self.V2)
        self.assertEqual(record.git("status", "--porcelain").stdout, "")

    def test_a_new_file_and_a_deletion_by_the_user_ride_in_the_resume_commit_too(self):
        machine, run, record = self.open_the_investigation_with_v1_committed()
        record.absolute(self.A_NEW_FILE).write_text("# a helper the user added\n")
        record.absolute(self.IMPLEMENTATION).unlink()
        machine.launcher.script.append((T.INVESTIGATE_WORKFLOW, T.V_RESUME, {}))
        fixture.drive(machine, run)
        self.assertEqual(machine.routed[-1][0].row, "72")
        self.assertEqual(run.current_state, T.IMPLEMENTATION_REVIEWING)
        resume_commit = machine.routed[-1][2]
        self.assertEqual(sorted(self.paths_in_commit(record, resume_commit)),
                         sorted([self.IMPLEMENTATION, self.A_NEW_FILE, str(record.run_state_path)]))
        self.assertEqual(record.git("ls-tree", "--name-only", resume_commit, self.IMPLEMENTATION).stdout, "")
        self.assertEqual(record.git("show", "%s:%s" % (resume_commit, self.A_NEW_FILE)).stdout,
                         "# a helper the user added\n")
        self.assertEqual(record.git("status", "--porcelain").stdout, "")

    def test_a_resume_with_nothing_edited_commits_the_record_alone(self):
        machine, run, record = self.open_the_investigation_with_v1_committed()
        machine.launcher.script.append((T.INVESTIGATE_WORKFLOW, T.V_RESUME, {}))
        fixture.drive(machine, run)
        self.assertEqual(run.current_state, T.TEST_SUITE_ARBITRATING)   # the paused state, re-run
        self.assertEqual(self.paths_in_commit(record, machine.routed[-1][2]), [str(record.run_state_path)])


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
        self.assertEqual(machine.routed[-1][0].row, "72")
        self.assertIsNone(machine.routed[-2][0])   # the stray exit: a machine error, no row
        self.assertEqual(run.current_state, T.TEST_DESIGN_WRITING)
        self.assertEqual(run.design_version, 1)

    def test_the_users_edit_before_a_stray_verdict_is_still_seen_on_resume(self):
        machine, run, record = self.open_investigation()
        design = record.absolute(fixture.DESIGN_PATH)
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
        self.assertEqual(machine.routed[-1][0].row, "72")
        self.assertEqual(run.current_state, T.DESIGN_WRITING)
        self.assertEqual(run.design_version, 2)
        self.assertEqual(run.counters.value("redesigns"), 1)


    def test_a_resume_may_not_name_ended_or_initiate_design_to_main(self):
        # Section 6.6 after the seventh walk; PR #287's round-6 review
        # reproduced `ended` ending the run with outcome null and
        # `initiate-design-to-main` crashing after the cut. Both are
        # machine errors with the pause unchanged, and the next resume
        # routes.
        for name in (T.ENDED, T.INITIATE_DESIGN_TO_MAIN):
            with self.subTest(destination=name):
                self.repository.remove()
                self.repository = fixture.ThrowawayRepository()
                machine, run, record = self.open_investigation()
                self.stray_verdict_then_check_the_pause_is_unchanged(
                    machine, run, record, verdict=T.V_RESUME, fields={"destination": name})
                self.assertIsNone(run.outcome)
                self.assertIn(name, run.machine_error)
                machine.launcher.script.append((T.INVESTIGATE_WORKFLOW, T.V_RESUME, {}))
                fixture.drive(machine, run)
                self.assertEqual(machine.routed[-1][0].row, "72")
                self.assertEqual(run.current_state, T.TEST_DESIGN_WRITING)

    def test_zero_all_run_counters_including_redesigns_carried_on_a_malformed_resume_is_refused_with_the_whole_state_exit(self):
        # Section 9 after the seventh walk (item 8): the user-ruling
        # zero-all-run-counters-including-redesigns is neither
        # applied to the counters nor written to the user-rulings file; the
        # user says it again on the correct resume.
        machine, run, record = self.open_investigation()
        run.counters.values["redesigns"] = 2                 # as after two redesigns
        self.stray_verdict_then_check_the_pause_is_unchanged(
            machine, run, record, verdict=T.V_RESUME,
            fields={"destination": "desgin-writing",
                    "rulings": (T.RULING_ZERO_ALL_RUN_COUNTERS_INCLUDING_REDESIGNS,)})
        self.assertEqual(run.counters.value("redesigns"), 2)
        self.assertFalse(record.absolute(record.user_rulings_path).exists())
        # Without the user-ruling a resume to design-writing is row 73; with
        # it, said again on the correct resume, row 72.
        machine.launcher.script.append(
            (T.INVESTIGATE_WORKFLOW, T.V_RESUME,
             {"destination": T.DESIGN_WRITING,
              "rulings": (T.RULING_ZERO_ALL_RUN_COUNTERS_INCLUDING_REDESIGNS,)}))
        fixture.drive(machine, run)
        self.assertEqual(machine.routed[-1][0].row, "72")
        self.assertEqual(run.current_state, T.DESIGN_WRITING)
        self.assertEqual(run.counters.value("redesigns"), 1)
        self.assertEqual(record.absolute(record.user_rulings_path).read_text(),
                         "- %s (user-ruled 2026-09-08)\n"
                         % T.RULING_ZERO_ALL_RUN_COUNTERS_INCLUDING_REDESIGNS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
