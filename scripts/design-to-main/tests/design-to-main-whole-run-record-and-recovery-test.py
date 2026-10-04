#!/usr/bin/env python3
"""Whole runs of the design-to-main machine through the stub launcher: one
from initiate-design-to-main to ended with outcome passed, and one that
ends failed at the redesigns ceiling; and section 9's record — the topic
branch, one commit per state-exit with its trailer and only the files it
names, run-state.json, the record's layout, the state-exit file, the
user-rulings file, recovery from the last commit, the refusals before
row 1 cuts the topic branch, and no push.

The whole-run cases are split over four files,
design-to-main-whole-run-*-test.py, so that the suite runner runs them at
the same time.

Run: python3 scripts/design-to-main/tests/design-to-main-whole-run-record-and-recovery-test.py
"""

import importlib.util
import json
import pathlib
import shutil
import tempfile
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
        self.assertEqual(rows, ["1", "2", "5", "16", "18", "21", "24", "32", "16", "41",
                                "42", "47", "56", "74"])

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

    def test_run_state_json_carries_the_fields_section_9_lists_under_the_design_s_names(self):
        # Section 9 after the seventh walk: the design version; each
        # work-stream's position; the counters of section 7; tests-begun;
        # whether the design and the test-design are approved; the
        # consecutive could-not-run, program-check-failure and submit-retry
        # counts; why each state was entered; each artifact's
        # coverage-type; the paused state and the commit at which an
        # investigation opened; whether row 1 has cut the topic branch; the
        # outcome once ended.
        on_disk = json.loads(self.record.absolute(self.record.run_state_path).read_text())
        for key in (
                "design-version",
                "implementation-work-stream-position", "test-work-stream-position",
                "counters", "tests-begun", "design-approved", "test-design-approved",
                "consecutive-could-not-run-count", "consecutive-program-check-failure-count",
                "submit-retry-count",
                "writing-state-entry-reason",
                "implementation-coverage-type", "tests-coverage-types",
                "paused-state", "investigation-opened-at-commit",
                "topic-branch-cut", "outcome"):
            self.assertIn(key, on_disk, key)
        self.assertEqual(set(on_disk), set(RunStateRecord.FIELDS))
        self.assertEqual(set(on_disk["counters"]), set(T.COUNTER_NAMES))

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

    def test_the_standard_package_carries_the_design_and_contract_paths(self):
        # Section 2: a state-package is the set of files the machine tells
        # the launched agent to read, and the standard-package is the
        # design, the design-contract and the user-rulings file. Before
        # code exists the design is its issue's GHI-MD, as the invocation
        # names it, and the design-contract sits beside it (section 9;
        # user-ruled 2026-09-18), and that path is no longer derivable from
        # the component's name, so the package carries the path itself,
        # never a placeholder such as "the design".
        launched = {p["state"]: p for p in self.machine.launcher.launched}
        standard_package = launched[T.DESIGN_WRITING]["standard-package"]
        self.assertEqual(
            tuple(standard_package),
            (self.record.design_path,
             T.contract_path_beside_design(self.record.design_path),
             str(self.record.user_rulings_path)))
        self.assertEqual(fixture.DESIGN_PATH, self.record.design_path)

    def test_a_run_with_no_investigation_names_no_investigation_report_in_any_package(self):
        # Sections 2 and 9: only investigate-workflow's package, and
        # design-writing's on a redesign, carry `investigation-report`.
        self.assertEqual(
            [p["state"] for p in self.machine.launcher.launched if "investigation-report" in p], [])


class TheWriteTrailer(unittest.TestCase):
    """Section 9 after the seventh walk: `Write:` counts what the writer's
    counter counts; a write forced by an upstream change or ordered by the
    arbitrator carries `Write: forced` instead of a number."""

    def write_trailers(self, machine, record):
        return [G.parse_state_exit_trailer(record.commit_message(commit)).get("Write")
                for _, state_exit, commit in machine.routed
                if state_exit.state == T.IMPLEMENTATION_WRITING]

    def test_counted_writes_are_numbered_by_the_writer_s_counter_and_forced_writes_say_so(self):
        repository = fixture.ThrowawayRepository()
        try:
            script = fixture.prefix_to_design_approved() + [
                fixture.implementation_write(),                                   # Write: 1
                (T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_REJECT_IMPLEMENTATION, {}),
                fixture.implementation_write(),                                   # Write: 2
                (T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_REJECT_CONTRACT, {}),  # row 29
                (T.CONTRACT_REVISING, T.V_EMITTED, {}),
                (T.CONTRACT_ACCEPTANCE_BY_PROGRAM, T.V_ADVANCE, {}),
                (T.CONTRACT_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {}),                 # row 9
                fixture.implementation_write(),                                   # Write: forced
                (T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_REJECT_IMPLEMENTATION, {}),
                fixture.implementation_write(),                                   # Write: 3
            ]
            machine, run, record, _ = fixture.make_machine(script, repository)
            fixture.drive(machine, run)
            self.assertEqual(self.write_trailers(machine, record), ["1", "2", "forced", "3"])
            self.assertEqual(run.counters.value("implementation-writes"), 3)
            self.assertEqual(run.writes_emitted_per_version[T.IMPLEMENTATION_WRITING], 4)
        finally:
            repository.remove()

    def test_a_write_the_arbitrator_orders_is_forced(self):
        repository = fixture.ThrowawayRepository()
        try:
            script = fixture.whole_run_to_passed()[:-2] + [
                (T.TEST_SUITE_EXECUTING, T.V_FAIL, {}),
                (T.TEST_SUITE_ARBITRATING, T.V_REJECT_IMPLEMENTATION, {}),       # row 61
                fixture.implementation_write(),                                  # Write: forced
            ]
            machine, run, record, _ = fixture.make_machine(script, repository)
            fixture.drive(machine, run)
            self.assertEqual(self.write_trailers(machine, record), ["1", "forced"])
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
                (T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_REJECT_DESIGN, {}),    # row 30
                (T.INVESTIGATE_WORKFLOW, T.V_RESUME, {"destination": T.DESIGN_WRITING}),
            ]
            script = [(T.INITIATE_DESIGN_TO_MAIN, T.V_INVOKED, {})] + redesign_round * 3
            machine, run, record, _ = fixture.make_machine(script, repository)
            outcome = machine.run_until_ended(run)
            self.assertEqual(outcome, T.OUTCOME_FAILED)
            self.assertEqual(run.counters.value("redesigns"), 2)
            self.assertEqual(run.design_version, 3)
            self.assertEqual([r.row for r, _, _ in machine.routed][-3:], ["21", "30", "73"])
            trailer = G.parse_state_exit_trailer(record.commit_message("HEAD"))
            self.assertEqual(trailer["Counter-redesigns"], "2")
            self.assertEqual(RunStateRecord.read_from(
                record.absolute(record.run_state_path)).outcome, T.OUTCOME_FAILED)
            self.assertEqual(repository.origin_refs(), repository.origin_refs_at_start)
        finally:
            repository.remove()


class AStateExitCommitsOnlyTheFilesItNames(unittest.TestCase):
    """Section 9 after the seventh walk: a state-exit's commit carries only
    the files the state-exit names — the artifact, the notes, the record —
    never the whole worktree, so a paused agent's half-written files are
    not committed as anyone's work."""

    IMPLEMENTATION = fixture.COMPONENT_DIRECTORY + "/widget_counter.py"
    STRAY = fixture.COMPONENT_DIRECTORY + "/scratch-notes.txt"

    def test_an_emitted_write_commits_the_files_it_names_and_the_record_nothing_else(self):
        repository = fixture.ThrowawayRepository()
        try:
            script = fixture.prefix_to_design_approved() + [
                (T.IMPLEMENTATION_WRITING, T.V_EMITTED, {
                    "coverage_types": ("script",),
                    "named_files": (self.IMPLEMENTATION,),
                    fixture.FILES_WRITTEN_BEFORE_EMITTING: {
                        self.IMPLEMENTATION: "# the implementation\n",
                        self.STRAY: "a writer's scratch file, not named\n",
                        "README.md": "main, touched by the writer\n",
                    }}),
            ]
            machine, run, record, _ = fixture.make_machine(script, repository)
            fixture.drive(machine, run)
            self.assertEqual(run.current_state, T.IMPLEMENTATION_REVIEWING)
            commit = machine.routed[-1][2]
            files_in_commit = record.git("show", "--name-only", "--format=", commit).stdout.split()
            self.assertEqual(sorted(files_in_commit),
                             sorted([self.IMPLEMENTATION, str(record.run_state_path)]))
            self.assertNotIn(self.STRAY, files_in_commit)
            self.assertNotIn("README.md", files_in_commit)
            self.assertEqual(record.git("ls-files", self.STRAY).stdout, "")
        finally:
            repository.remove()

    def test_after_the_commit_every_other_change_in_the_worktree_is_discarded(self):
        # Section 9 after the eighth walk (item 7, user-ruled 2026-09-09):
        # after committing a state-exit, the machine discards every other
        # change in its worktree — the scratch file the writer left beside
        # the real one, the tracked file it touched — so the next state's
        # worktree holds only what a state-exit claimed.
        repository = fixture.ThrowawayRepository()
        try:
            script = fixture.prefix_to_design_approved() + [
                (T.IMPLEMENTATION_WRITING, T.V_EMITTED, {
                    "coverage_types": ("script",),
                    "named_files": (self.IMPLEMENTATION,),
                    fixture.FILES_WRITTEN_BEFORE_EMITTING: {
                        self.IMPLEMENTATION: "# the implementation\n",
                        self.STRAY: "a writer's scratch file, not named\n",
                        "README.md": "main, touched by the writer\n",
                    }}),
            ]
            machine, run, record, _ = fixture.make_machine(script, repository)
            fixture.drive(machine, run)
            self.assertEqual(run.current_state, T.IMPLEMENTATION_REVIEWING)
            self.assertEqual(record.absolute(self.IMPLEMENTATION).read_text(), "# the implementation\n")
            self.assertFalse(record.absolute(self.STRAY).exists())
            self.assertEqual(record.absolute("README.md").read_text(), "main\n")
            self.assertEqual(record.git("status", "--porcelain").stdout, "")
        finally:
            repository.remove()

    def test_a_state_exit_naming_a_file_that_is_not_there_is_a_machine_error_not_a_crash(self):
        # Section 9 after the eighth walk (item 7): a state-exit naming a
        # file that is not there — neither in the worktree nor tracked at
        # HEAD — is a machine error, routed like any illegal state-exit
        # (section 3.2): committed, the run paused in investigate-workflow
        # at the emitting state, no CalledProcessError from the restricted
        # add. A named deletion of a tracked file is not this: it is a
        # change the commit carries.
        repository = fixture.ThrowawayRepository()
        try:
            script = fixture.prefix_to_design_approved() + [
                (T.IMPLEMENTATION_WRITING, T.V_EMITTED, {
                    "coverage_types": ("script",),
                    "named_files": (self.IMPLEMENTATION, self.STRAY),
                    fixture.FILES_WRITTEN_BEFORE_EMITTING: {
                        self.IMPLEMENTATION: "# the implementation\n"}}),
            ]
            machine, run, record, _ = fixture.make_machine(script, repository)
            fixture.drive(machine, run)
            self.assertEqual(len(machine.machine_errors), 1)
            self.assertIn(self.STRAY, run.machine_error)
            self.assertEqual(run.current_state, T.INVESTIGATE_WORKFLOW)
            self.assertEqual(run.paused_state, T.IMPLEMENTATION_WRITING)
            self.assertEqual(run.counters.value("implementation-writes"), 0)
            trailer = G.parse_state_exit_trailer(record.commit_message("HEAD"))
            self.assertEqual(trailer["State"], T.IMPLEMENTATION_WRITING)
            self.assertEqual(trailer["Exit"], T.V_EMITTED)
            self.assertEqual(record.git("status", "--porcelain").stdout, "")
        finally:
            repository.remove()

    def test_the_record_never_stages_the_whole_worktree(self):
        # A `git add -A` with no pathspec after it stages the whole
        # worktree; the one the record runs is restricted to the record
        # directory and the named files (`"add", "-A", "--", ...`).
        source = (fixture.MACHINE_DIR / "design-to-main-git-record.py").read_text()
        self.assertNotIn('"add", "-A")', source)
        self.assertNotIn('"add", "-A", ".")', source)
        self.assertIn('"add", "-A", "--", str(self.record_directory), *named_files)', source)


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
                record,
                fixture.ScriptedStateExitLauncherWritingFiles(
                    [fixture.implementation_write()], record.repository_dir),
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
        # Every state-exit is `add` of the files it names then `commit`, as
        # two subprocesses; a process that dies between them leaves its
        # files STAGED. Recovery puts the index back to HEAD as well as the
        # working tree, so nothing a dead process staged is committed as
        # the next state's work.
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
                record,
                fixture.ScriptedStateExitLauncherWritingFiles(
                    [fixture.implementation_write()], record.repository_dir),
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

    def test_recovery_during_an_investigation_keeps_the_worktree_as_it_finds_it(self):
        # Section 9 after the seventh walk (item 7): in investigate-workflow
        # the uncommitted files are the user's; recovery keeps the worktree
        # as it finds it and reopens the dialog, and the resume sees the
        # edit the user made before the process died.
        repository = fixture.ThrowawayRepository()
        try:
            script = fixture.prefix_to_tests_begun() + [
                (T.TEST_DESIGN_WRITING, T.V_ESCALATE_TO_USER, {"investigation_focus": T.FOCUS_DESIGN}),
            ]
            machine, run, record, _ = fixture.make_machine(script, repository)
            fixture.drive(machine, run)
            self.assertEqual(run.current_state, T.INVESTIGATE_WORKFLOW)
            design = record.absolute(fixture.DESIGN_PATH)
            design.parent.mkdir(parents=True, exist_ok=True)
            design.write_text("# the design, edited by the user before the process died\n")
            notes = record.absolute("seat-notes.md")
            notes.write_text("the user's notes\n")
            status_before = record.git("status", "--porcelain").stdout
            successor = M.DesignToMainStateMachineFlow(
                record, M.ScriptedStateExitLauncher([(T.INVESTIGATE_WORKFLOW, T.V_RESUME, {})]),
                today=lambda: "2026-09-08")
            recovered = successor.recover()
            self.assertEqual(recovered.current_state, T.INVESTIGATE_WORKFLOW)
            self.assertTrue(design.exists())
            self.assertEqual(design.read_text(), "# the design, edited by the user before the process died\n")
            self.assertEqual(notes.read_text(), "the user's notes\n")
            self.assertEqual(record.git("status", "--porcelain").stdout, status_before)
            fixture.drive(successor, recovered)
            self.assertEqual(successor.launcher.launched[0]["state"], T.INVESTIGATE_WORKFLOW)
            self.assertEqual(recovered.current_state, T.DESIGN_WRITING)
            self.assertEqual(recovered.design_version, 2)
        finally:
            repository.remove()

    def test_recovery_of_an_ended_run_is_keyed_on_the_state_not_the_outcome(self):
        # PR #287's round-6 review: the guard keyed on `outcome is None`
        # let a run at `ended` with no outcome be "recovered" — its
        # checkout's uncommitted work discarded. Keyed on the state.
        repository = fixture.ThrowawayRepository()
        try:
            machine, run, record, _ = fixture.make_machine(fixture.whole_run_to_passed(), repository)
            self.assertEqual(machine.run_until_ended(run), T.OUTCOME_PASSED)
            run.outcome = None
            run.write_to(record.absolute(record.run_state_path))
            record.git("add", "--", str(record.run_state_path))
            record.git("commit", "-q", "-m", "widget-counter: ended with no outcome (a tampered record)")
            checkout = repository.checkout
            (checkout / "seat-notes.md").write_text("untracked notes after the run\n")
            (checkout / "README.md").write_text("main, edited but not committed\n")
            status_before = record.git("status", "--porcelain").stdout
            head_before = record.head_commit()
            recovered = M.DesignToMainStateMachineFlow(
                record, M.ScriptedStateExitLauncher([]), today=lambda: "2026-09-08").recover()
            self.assertEqual(recovered.current_state, T.ENDED)
            self.assertIsNone(recovered.outcome)
            self.assertEqual((checkout / "seat-notes.md").read_text(), "untracked notes after the run\n")
            self.assertEqual((checkout / "README.md").read_text(), "main, edited but not committed\n")
            self.assertEqual(record.git("status", "--porcelain").stdout, status_before)
            self.assertEqual(record.head_commit(), head_before)
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
            design = record.absolute(fixture.DESIGN_PATH)
            design.parent.mkdir(parents=True, exist_ok=True)
            design.write_text("# the design, edited by the user during the investigation\n")
            fixture.drive(successor, recovered)
            self.assertEqual([row.row for row, _, _ in successor.routed], ["72"])
            self.assertEqual(recovered.current_state, T.DESIGN_WRITING)
            self.assertEqual(recovered.design_version, 2)
            self.assertEqual(recovered.counters.value("redesigns"), 1)
        finally:
            repository.remove()


class TheDesignIsItsIssuesGhiMd(unittest.TestCase):
    """Section 9 after the user's ruling of 2026-09-18: before code exists
    the design is the GHI-MD the invocation names, refined in place, and
    the design-contract sits beside it, named like it; there is no
    `docs/designs/queue/`. After code starts both are in the component's
    directory, as before."""

    def test_the_contract_is_named_like_the_design_beside_it(self):
        self.assertEqual(T.contract_path_beside_design("docs/issues/413-grid-failure-design.md"),
                         "docs/issues/413-grid-failure-contract.md")
        self.assertEqual(T.contract_path_beside_design("docs/issues/39-memory-drain.md"),
                         "docs/issues/39-memory-drain-contract.md")

    def test_the_record_knows_the_design_and_its_contract_by_the_named_ghi_md(self):
        repository = fixture.ThrowawayRepository()
        try:
            record = G.TopicBranchGitRecord(
                repository.checkout, fixture.COMPONENT, fixture.COMPONENT_DIRECTORY,
                "docs/issues/413-grid-failure-design.md")
            self.assertEqual(record.document_of_path("docs/issues/413-grid-failure-design.md"),
                             "design")
            self.assertEqual(record.document_of_path("docs/issues/413-grid-failure-contract.md"),
                             "design-contract")
            self.assertEqual(record.document_of_path(
                "%s/%s-design.md" % (fixture.COMPONENT_DIRECTORY, fixture.COMPONENT)), "design")
            self.assertEqual(record.document_of_path(
                "%s/%s-contract.md" % (fixture.COMPONENT_DIRECTORY, fixture.COMPONENT)),
                "design-contract")
            self.assertNotEqual(record.document_of_path(
                "docs/designs/queue/%s-design.md" % fixture.COMPONENT), "design")
        finally:
            repository.remove()


class TheRecordsLayout(unittest.TestCase):
    """Section 9 after the eighth walk (item 3, user-ruled 2026-09-08):
    the component's directory is created by the machine when it cuts the
    topic branch, holding only `design-to-main-record/` until code
    exists; a reviewer's or a writer's notes are `notes.md` and its
    state-exit `state-exit.json` in `evidence/<state or sub-state>-<n>/`,
    for the nth instance of that state or sub-state, counted from 1."""

    def setUp(self):
        self.repository = fixture.ThrowawayRepository()

    def tearDown(self):
        self.repository.remove()

    def test_the_cut_creates_the_components_directory_holding_only_the_record(self):
        machine, run, record, _ = fixture.make_machine([], self.repository)
        record.cut_topic_branch()
        component_directory = record.absolute(record.component_directory)
        self.assertTrue(record.absolute(record.record_directory).is_dir())
        self.assertEqual([p.name for p in component_directory.iterdir()], [T.RECORD_DIRECTORY_NAME])

    def test_after_row_1_the_components_directory_holds_only_the_record(self):
        machine, run, record, _ = fixture.make_machine(
            [(T.INITIATE_DESIGN_TO_MAIN, T.V_INVOKED, {})], self.repository)
        fixture.drive(machine, run)
        self.assertEqual(run.current_state, T.DESIGN_WRITING)
        component_directory = record.absolute(record.component_directory)
        self.assertEqual([p.name for p in component_directory.iterdir()], [T.RECORD_DIRECTORY_NAME])
        self.assertEqual(sorted(p.name for p in record.absolute(record.record_directory).iterdir()),
                         [T.RUN_STATE_FILE_NAME])

    def test_an_instances_evidence_directory_is_named_for_the_state_and_counted_from_1(self):
        machine, run, record, _ = fixture.make_machine([], self.repository)
        self.assertEqual(
            record.evidence_directory_for_instance(T.IMPLEMENTATION_WRITING, 1),
            record.record_directory / "evidence" / "implementation-writing-1")
        self.assertEqual(
            record.evidence_directory_for_instance(T.TEST_ACCEPTANCE_BY_AGENT, 2),
            record.record_directory / "evidence" / "test-acceptance-by-agent-2")
        self.assertEqual(
            record.notes_path_for_instance(T.IMPLEMENTATION_WRITING, 1),
            record.record_directory / "evidence" / "implementation-writing-1" / "notes.md")
        self.assertEqual(
            record.state_exit_path_for_instance(T.IMPLEMENTATION_WRITING, 1),
            record.record_directory / "evidence" / "implementation-writing-1" / "state-exit.json")

    def test_the_next_instance_is_counted_from_the_branchs_state_trailers_and_named_in_the_package(self):
        script = fixture.prefix_to_design_approved() + [
            fixture.implementation_write(),
            (T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_REJECT_IMPLEMENTATION, {}),
            fixture.implementation_write(),
        ]
        machine, run, record, _ = fixture.make_machine(script, self.repository)
        fixture.drive(machine, run)
        self.assertEqual(record.instances_of_state_so_far(T.IMPLEMENTATION_WRITING), 2)
        self.assertEqual(record.instances_of_state_so_far(T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT), 1)
        self.assertEqual(record.instances_of_state_so_far(T.TEST_WRITING), 0)
        self.assertEqual(
            record.evidence_directory_for_the_next_instance(T.IMPLEMENTATION_WRITING),
            record.record_directory / "evidence" / "implementation-writing-3")
        packages = [p for p in machine.launcher.launched if p["state"] == T.IMPLEMENTATION_WRITING]
        self.assertEqual([str(p["evidence-directory"]) for p in packages], [
            str(record.record_directory / "evidence" / "implementation-writing-1"),
            str(record.record_directory / "evidence" / "implementation-writing-2")])
        first = [p for p in machine.launcher.launched if p["state"] == T.INITIATE_DESIGN_TO_MAIN][0]
        self.assertEqual(str(first["evidence-directory"]),
                         str(record.record_directory / "evidence" / "initiate-design-to-main-1"))

    def test_a_merged_runs_trailers_in_mains_history_do_not_count_toward_this_runs_instances(self):
        # GHI #313: instances are counted over this run's commits above
        # the branch's cut from origin/main, not over all of HEAD's
        # ancestry. A design-to-main run that reached main by merge left
        # its State: trailers in main's history; the next run's first
        # instance of each state is still its first.
        checkout = self.repository.checkout
        other_component_file = checkout / "scripts" / "gadget-tally" / "gadget-tally.py"
        other_component_file.parent.mkdir(parents=True)
        other_component_file.write_text("# the other component's implementation\n")
        trailer = G.compose_state_exit_trailer(
            T.IMPLEMENTATION_WRITING, T.V_EMITTED, "0", {name: 0 for name in T.COUNTER_NAMES})
        fixture.git(checkout, "add", "-A")
        fixture.git(checkout, "commit", "-q", "-m",
                    "gadget-tally: implementation-writing emitted\n\n" + trailer)
        fixture.git(checkout, "push", "-q", "origin", "main")
        script = fixture.prefix_to_design_approved() + [fixture.implementation_write()]
        machine, run, record, _ = fixture.make_machine(script, self.repository)
        self.assertEqual(record.instances_of_state_so_far(T.IMPLEMENTATION_WRITING), 0)
        fixture.drive(machine, run)
        self.assertEqual(record.instances_of_state_so_far(T.IMPLEMENTATION_WRITING), 1)
        packages = [p for p in machine.launcher.launched if p["state"] == T.IMPLEMENTATION_WRITING]
        self.assertEqual([str(p["evidence-directory"]) for p in packages],
                         [str(record.record_directory / "evidence" / "implementation-writing-1")])
        first = [p for p in machine.launcher.launched if p["state"] == T.INITIATE_DESIGN_TO_MAIN][0]
        self.assertEqual(str(first["evidence-directory"]),
                         str(record.record_directory / "evidence" / "initiate-design-to-main-1"))


class TheStateExitFile(unittest.TestCase):
    """Section 2: the state-exit is a file, state-exit.json, in the
    instance's evidence directory, its fields spelled with hyphens —
    `state`, `verdict`, `package-commit`, `destination`, `input-named`,
    `investigation-focus`, `coverage-type`, `refusal-class`,
    `held-ruling`, `named-files`, `rulings`. The reader parses it into
    the machine's StateExitRecord."""

    def setUp(self):
        self.directory = pathlib.Path(tempfile.mkdtemp(prefix="design-to-main-state-exit-"))

    def tearDown(self):
        shutil.rmtree(self.directory, ignore_errors=True)

    def write(self, fields):
        path = self.directory / T.STATE_EXIT_FILE_NAME
        path.write_text(json.dumps(fields, indent=2) + "\n")
        return path

    def test_every_field_of_section_2_reads_into_the_record(self):
        path = self.write({
            "state": T.TEST_WRITING, "verdict": T.V_EMITTED, "package-commit": "a" * 40,
            "destination": T.TEST_REVIEWING, "coverage-type": "script, prompt",
            "named-files": ["scripts/widget-counter/tests/a-test.py",
                            "scripts/widget-counter/tests/b-prompt-test.md"],
        })
        record = M.state_exit_record_from_json_file(path)
        self.assertEqual(record, M.StateExitRecord(
            state=T.TEST_WRITING, verdict=T.V_EMITTED, package_commit="a" * 40,
            destination=T.TEST_REVIEWING, coverage_types=("script", "prompt"),
            named_files=("scripts/widget-counter/tests/a-test.py",
                         "scripts/widget-counter/tests/b-prompt-test.md")))
        path = self.write({
            "state": T.INVESTIGATE_WORKFLOW, "verdict": T.V_RESUME, "package-commit": "b" * 40,
            "held-ruling": T.V_REJECT_TESTS, "rulings": ["reset", "the exit status of a refusal is 3"],
            "named-files": [],
        })
        record = M.state_exit_record_from_json_file(path)
        self.assertEqual(record.held_ruling, T.V_REJECT_TESTS)
        self.assertEqual(record.rulings, ("reset", "the exit status of a refusal is 3"))
        self.assertEqual(record.coverage_types, ())
        path = self.write({
            "state": T.IMPLEMENTATION_WRITING, "verdict": T.V_INPUT_QUICK_CHECK_FAILED,
            "package-commit": "c" * 40, "input-named": T.INPUT_DESIGN, "named-files": [],
        })
        self.assertEqual(M.state_exit_record_from_json_file(path).input_named, T.INPUT_DESIGN)
        path = self.write({
            "state": T.TEST_SUITE_ARBITRATING, "verdict": T.V_ESCALATE_TO_USER,
            "package-commit": "d" * 40, "investigation-focus": T.FOCUS_DESIGN, "named-files": [],
        })
        self.assertEqual(M.state_exit_record_from_json_file(path).investigation_focus, T.FOCUS_DESIGN)
        path = self.write({
            "state": T.SUBMIT_TO_PR_GATE, "verdict": T.V_GATEKEEPER_REFUSAL,
            "package-commit": "e" * 40, "refusal-class": T.REFUSAL_FORM, "named-files": [],
        })
        self.assertEqual(M.state_exit_record_from_json_file(path).refusal_class, T.REFUSAL_FORM)

    def test_a_field_the_design_does_not_name_or_a_required_one_missing_is_refused(self):
        # An agent wrote `input_named` (the underscore spelling PR #292's
        # drafts once had) or left out the verdict: refused with the
        # field's name, so that the machine can route it as a malformed
        # state-exit rather than read half a record.
        path = self.write({"state": T.IMPLEMENTATION_WRITING, "verdict": T.V_INPUT_QUICK_CHECK_FAILED,
                           "package-commit": "a" * 40, "input_named": T.INPUT_DESIGN, "named-files": []})
        with self.assertRaises(M.MalformedStateExitFile) as refused:
            M.state_exit_record_from_json_file(path)
        self.assertIn("input_named", str(refused.exception))
        path = self.write({"state": T.IMPLEMENTATION_WRITING, "package-commit": "a" * 40, "named-files": []})
        with self.assertRaises(M.MalformedStateExitFile) as refused:
            M.state_exit_record_from_json_file(path)
        self.assertIn("verdict", str(refused.exception))

    def test_an_absent_named_files_is_refused_the_field_is_always_written(self):
        # Section 2 after the tenth walk (item 3, user-ruled 2026-09-14):
        # `named-files` is always written, an empty list when the agent
        # produced no artifact, so an absent field is a malformed
        # state-exit rather than an empty tuple by default — a reviewer
        # that forgot the field is told apart from one that named nothing.
        path = self.write({"state": T.TEST_ACCEPTANCE_BY_AGENT, "verdict": T.V_ADVANCE,
                           "package-commit": "a" * 40})
        with self.assertRaises(M.MalformedStateExitFile) as refused:
            M.state_exit_record_from_json_file(path)
        self.assertIn("named-files", str(refused.exception))
        self.assertIn("named-files", T.STATE_EXIT_JSON_FIELDS_REQUIRED)
        path = self.write({"state": T.TEST_ACCEPTANCE_BY_AGENT, "verdict": T.V_ADVANCE,
                           "package-commit": "a" * 40, "named-files": []})
        self.assertEqual(M.state_exit_record_from_json_file(path).named_files, ())


class AWriteThatNamedNoFile(unittest.TestCase):
    """Section 2 after the tenth walk (item 3, user-ruled 2026-09-14):
    `named-files` is always written, an empty list when the agent produced
    no artifact — but a writing state's `emitted` that names none is a
    machine error, since a write that named no file did not happen. The
    user pushed past a plain empty list here, wanting a deliberate nothing
    told apart from a bug that produced nothing."""

    def setUp(self):
        self.repository = fixture.ThrowawayRepository()

    def tearDown(self):
        self.repository.remove()

    def test_a_writing_states_emitted_naming_no_file_pauses_the_run_in_investigate_workflow(self):
        script = fixture.prefix_to_design_approved() + [
            (T.IMPLEMENTATION_WRITING, T.V_EMITTED,
             {"coverage_types": ("script",), "named_files": ()}),
        ]
        machine, run, record, _ = fixture.make_machine(script, self.repository)
        fixture.drive(machine, run)
        self.assertEqual(len(machine.machine_errors), 1)
        self.assertIn("names no files", run.machine_error)
        self.assertIsNone(machine.routed[-1][0])
        self.assertEqual(run.current_state, T.INVESTIGATE_WORKFLOW)
        self.assertEqual(run.paused_state, T.IMPLEMENTATION_WRITING)
        self.assertEqual(run.counters.value("implementation-writes"), 0)

    def test_every_writing_state_of_section_4_is_held_to_it_design_writing_included(self):
        for state in T.WRITING_STATES_INCLUDING_DESIGN_WRITING:
            with self.subTest(state=state):
                with self.assertRaises(M.IllegalStateExit) as refused:
                    M.refuse_a_write_that_named_no_file(
                        M.StateExitRecord(state=state, verdict=T.V_EMITTED,
                                          package_commit="a" * 40))
                self.assertIn(state, str(refused.exception))
        self.assertIn(T.DESIGN_WRITING, T.WRITING_STATES_INCLUDING_DESIGN_WRITING)

    def test_an_empty_named_files_is_what_a_state_exit_that_is_not_a_write_carries(self):
        # The empty list itself is legal, and is what every state-exit
        # that produced no artifact carries: only a writing state's
        # `emitted` is refused for it.
        M.refuse_a_write_that_named_no_file(
            M.StateExitRecord(state=T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT,
                              verdict=T.V_ADVANCE, package_commit="a" * 40))
        M.refuse_a_write_that_named_no_file(
            M.StateExitRecord(state=T.IMPLEMENTATION_WRITING,
                              verdict=T.V_INPUT_QUICK_CHECK_FAILED,
                              package_commit="a" * 40, input_named=T.INPUT_DESIGN))


class TopicBranchRefusedAtRow1(unittest.TestCase):
    """Section 6.6: the machine cuts the topic branch and, if the name is
    refused or the checkout has no `origin/main`, says so in the invoking
    conversation and the run does not start. A re-invocation for a
    component whose branch already exists is the first case: nothing is
    committed, and the checkout is as it was."""

    def test_a_checkout_with_no_origin_main_is_refused_before_anything_runs(self):
        # Section 6.6 after the ninth walk (item 10, user-ruled
        # 2026-09-11, on PR #314's reviewers' question): a checkout with
        # no `origin/main` to cut from is refused at the invocation, like
        # a name git refuses. Before this the start point was first read
        # by the count of a state's instances, while
        # initiate-design-to-main's state-package was assembled, and the
        # invocation died with a raw CalledProcessError instead.
        repository = fixture.ThrowawayRepository()
        try:
            fixture.git(repository.checkout, "update-ref", "-d", "refs/remotes/origin/main")
            record = fixture.git_record_module.TopicBranchGitRecord(
                repository.checkout, fixture.COMPONENT, fixture.COMPONENT_DIRECTORY,
                fixture.DESIGN_PATH)
            machine = M.DesignToMainStateMachineFlow(
                record, M.ScriptedStateExitLauncher([]), today=lambda: "2026-09-08")
            with self.assertRaises(M.TopicBranchCutRefused) as refused:
                machine.start(fixture.COMPONENT)
            self.assertIn("origin/main", str(refused.exception))
            self.assertIn(fixture.COMPONENT, str(refused.exception))
            self.assertEqual(machine.launcher.launched, [])
            self.assertEqual(fixture.git(repository.checkout, "status", "--porcelain"), "")
            self.assertFalse(record.absolute(record.record_directory).exists())
        finally:
            repository.remove()

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
            record.discard_every_change_the_commit_did_not_carry(run)
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
            record.discard_every_change_the_commit_did_not_carry(run)
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
