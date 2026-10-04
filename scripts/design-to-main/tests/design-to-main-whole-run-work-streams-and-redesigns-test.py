#!/usr/bin/env python3
"""The design-to-main machine's two work-streams and its redesigns, driven
through the stub launcher: a contract revision re-entering both
work-streams, the coverage-types of a set of tests and their check
against the test-design, the design approved again after a redesign or
without one, and the investigation report a state-package names.

The whole-run cases are split over four files,
design-to-main-whole-run-*-test.py, so that the suite runner runs them at
the same time.

Run: python3 scripts/design-to-main/tests/design-to-main-whole-run-work-streams-and-redesigns-test.py
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
M = fixture.machine_module
RunStateRecord = fixture.run_state_module.RunStateRecord


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
                (T.TEST_ACCEPTANCE_BY_AGENT, T.V_REJECT_CONTRACT, {}),            # row 53
                (T.CONTRACT_REVISING, T.V_EMITTED, {}),                            # row 19
                (T.CONTRACT_ACCEPTANCE_BY_PROGRAM, T.V_ADVANCE, {}),               # row 6
                (T.CONTRACT_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {}),                 # row 9
                fixture.implementation_write(),                                   # forced, uncharged
                (T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {}),           # row 26: holds
                (T.TEST_DESIGN_WRITING, T.V_EMITTED, {}),                          # row 32
                (T.TEST_DESIGN_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {}),
                (T.TEST_DESIGN_ACCEPTANCE_BY_USER, T.V_ADVANCE, {}),               # row 41
                fixture.test_write(),                                             # forced, uncharged
                (T.TEST_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {}),                     # row 47
                (T.TEST_SUITE_EXECUTING, T.V_PASS, {}),
                (T.SUBMIT_TO_PR_GATE, T.V_ACCEPTED, {}),
            ]
            machine, run, record, _ = fixture.make_machine(script, repository)
            self.assertEqual(machine.run_until_ended(run), T.OUTCOME_PASSED)
            rows = [row.row for row, _, _ in machine.routed]
            self.assertEqual(rows[-13:], ["53", "19", "6", "9", "21", "26", "32", "16", "41",
                                          "42", "47", "56", "74"])
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
        # Row 54 opens an investigation with the test-work-stream in
        # test-reviewing; the user edits only the implementation and
        # resumes. Row 72 resumes at implementation-reviewing, its reviewer
        # advances, and row 26 holds the implementation and sends the run to
        # the test-work-stream's position: test-reviewing, not the
        # test-writing it was in before the tests were reviewed. No test
        # write is forced; the resume zeroed test-writes (section 7) and
        # nothing charges it after.
        repository = fixture.ThrowawayRepository()
        try:
            script = fixture.prefix_to_test_writing() + [
                fixture.test_write(),
                (T.TEST_ACCEPTANCE_BY_AGENT, T.V_REJECT_DESIGN, {}),              # row 54
            ]
            machine, run, record, _ = fixture.make_machine(script, repository)
            fixture.drive(machine, run)
            self.assertEqual(run.current_state, T.INVESTIGATE_WORKFLOW)
            self.assertEqual(run.paused_state, T.TEST_REVIEWING)
            implementation = record.absolute(fixture.COMPONENT_DIRECTORY + "/widget_counter.py")
            implementation.parent.mkdir(parents=True, exist_ok=True)
            implementation.write_text("# the implementation, edited by the user\n")
            machine.launcher.script += [
                (T.INVESTIGATE_WORKFLOW, T.V_RESUME, {}),                          # row 72
                (T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {}),           # row 26: holds
            ]
            fixture.drive(machine, run)
            self.assertEqual([row.row for row, _, _ in machine.routed][-3:], ["54", "72", "26"])
            self.assertEqual(run.current_state, T.TEST_REVIEWING)
            self.assertEqual(run.test_work_stream_position, T.TEST_REVIEWING)
            self.assertEqual(run.implementation_work_stream_position, T.READY_FOR_TEST_SUITE)
            self.assertEqual(run.counters.value("test-writes"), 0)
            self.assertEqual(run.writes_emitted_per_version[T.TEST_WRITING], 1)
            self.assertEqual(
                sum(1 for p in machine.launcher.launched if p["state"] == T.TEST_WRITING), 1)
        finally:
            repository.remove()


class TheCoverageTypesOfASetOfTests(unittest.TestCase):
    """The eighth walk, item 8 (user-ruled 2026-09-09; sections 3.1 and
    6.4): test-writing's `emitted` carries every coverage-type present in
    the set — `script, prompt` for nine scripts and one prompt-based-test
    — as a tuple on the state-exit record and a comma-separated string
    in state-exit.json; the machine records the set, and the tests go to
    test-acceptance-by-user when prompt or script-and-prompt is among
    them. An implementation's coverage-type is one thing (section 2)."""

    def setUp(self):
        self.repository = fixture.ThrowawayRepository()

    def tearDown(self):
        self.repository.remove()

    def test_the_set_is_recorded_and_routes_the_tests_to_the_user_when_any_is_agent_instructions(self):
        script = fixture.prefix_to_test_writing("script", "prompt") + [
            fixture.test_write("script", "prompt"),
            (T.TEST_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {}),                          # row 16
        ]
        machine, run, record, _ = fixture.make_machine(script, self.repository)
        fixture.drive(machine, run)
        self.assertEqual(machine.routed[-1][0].row, "16")
        self.assertEqual(run.current_state, T.TEST_ACCEPTANCE_BY_USER)
        self.assertEqual(run.tests_coverage_types, ("script", "prompt"))
        self.assertTrue(run.tests_are_agent_instructions())
        on_disk = json.loads(record.absolute(record.run_state_path).read_text())
        self.assertEqual(on_disk["tests-coverage-types"], ["script", "prompt"])
        self.assertNotIn("tests-coverage-type", on_disk)
        read_back = RunStateRecord.read_from(record.absolute(record.run_state_path))
        self.assertEqual(read_back.tests_coverage_types, ("script", "prompt"))

    def test_scripts_alone_skip_the_users_check(self):
        script = fixture.prefix_to_test_writing() + [
            fixture.test_write("script"),
            (T.TEST_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {}),                          # row 47
        ]
        machine, run, record, _ = fixture.make_machine(script, self.repository)
        fixture.drive(machine, run)
        self.assertEqual(machine.routed[-1][0].row, "47")
        self.assertEqual(run.tests_coverage_types, ("script",))
        self.assertFalse(run.tests_are_agent_instructions())

    def test_the_json_field_is_a_comma_separated_string_and_the_record_a_tuple(self):
        self.assertEqual(M.coverage_types_from_json_field("script, prompt"), ("script", "prompt"))
        self.assertEqual(M.coverage_types_from_json_field("script"), ("script",))
        self.assertEqual(M.coverage_types_from_json_field(" script-and-prompt ,prompt "),
                         ("script-and-prompt", "prompt"))
        self.assertEqual(M.coverage_types_as_json_field(("script", "prompt")), "script, prompt")
        self.assertEqual(M.coverage_types_as_json_field(("script",)), "script")

    def test_an_implementation_emitting_more_than_one_coverage_type_is_a_machine_error(self):
        # Section 2: the coverage-type of an implementation says what kind
        # of thing it is — one of three. Two is not one: a machine error,
        # routed like any illegal state-exit (reported with this slice).
        script = fixture.prefix_to_design_approved() + [
            (T.IMPLEMENTATION_WRITING, T.V_EMITTED, {"coverage_types": ("script", "prompt")}),
        ]
        machine, run, record, _ = fixture.make_machine(script, self.repository)
        fixture.drive(machine, run)
        self.assertEqual(len(machine.machine_errors), 1)
        self.assertEqual(run.current_state, T.INVESTIGATE_WORKFLOW)
        self.assertEqual(run.paused_state, T.IMPLEMENTATION_WRITING)
        self.assertIsNone(run.implementation_coverage_type)
        self.assertEqual(run.counters.value("implementation-writes"), 0)


class TheTestWritersSetAgainstTheTestDesign(unittest.TestCase):
    """Section 6.4 (user-ruled 2026-09-09, the eighth walk, item 8): the
    machine checks the coverage-types the test writer's `emitted` carries
    for the set against the test-design's per-requirement types, which each
    requirement carries on a `coverage-type:` line of its own (user-ruled
    2026-09-11, the ninth walk, item 7). Those types decide whether the
    tests go to test-acceptance-by-user as standing-agent-instructions, so
    a set that is not the test-design's would route the run on a claim
    nothing backs. A `no-tests` requirement runs nothing and counts as
    neither pass nor fail (section 6.4), so it is disregarded here;
    `no-tests` alone is what an empty set carries, never beside a type that
    is present (section 2; the tenth walk, item 6)."""

    def drive_a_test_write(self, test_design_coverage_types, emitted_coverage_types,
                           and_then=()):
        """A run to the test writer's `emitted`, the test-design's
        requirements carrying `test_design_coverage_types` and the writer
        emitting `emitted_coverage_types` for the set. Each call gets its
        own repository: a refused run leaves the topic branch behind."""
        repository = fixture.ThrowawayRepository()
        try:
            script = fixture.prefix_to_test_writing(*test_design_coverage_types) + [
                fixture.test_write(*emitted_coverage_types),
            ] + list(and_then)
            machine, run, record, _ = fixture.make_machine(script, repository)
            fixture.drive(machine, run)
            return machine, run
        finally:
            repository.remove()

    def test_the_set_the_test_design_asks_for_is_read_from_its_coverage_type_lines(self):
        self.assertEqual(
            M.coverage_types_of_the_test_designs_requirements(
                fixture.test_design_text("script", "no-tests", "prompt")),
            ("script", "no-tests", "prompt"))
        # No-tests requirements are disregarded; no-tests alone is what an
        # empty set carries.
        self.assertEqual(
            M.the_set_of_coverage_types_the_test_design_asks_for(
                ("script", "no-tests", "prompt")),
            ("prompt", "script"))
        self.assertEqual(
            M.the_set_of_coverage_types_the_test_design_asks_for(("no-tests", "no-tests")),
            (T.COVERAGE_TYPE_NO_TESTS,))

    def test_a_set_that_is_the_test_designs_advances(self):
        machine, run = self.drive_a_test_write(
            ("script", "no-tests", "prompt"), ("script", "prompt"),
            and_then=[(T.TEST_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {})])
        self.assertEqual(machine.machine_errors, [])
        self.assertEqual(run.tests_coverage_types, ("script", "prompt"))
        self.assertEqual(run.current_state, T.TEST_ACCEPTANCE_BY_USER)

    def test_a_set_that_is_not_the_test_designs_pauses_the_run_in_investigate_workflow(self):
        # The writer under-reports: the test-design asks for a
        # prompt-based-test too, and `script` alone would skip the user's
        # check of standing-agent-instructions.
        machine, run = self.drive_a_test_write(("script", "prompt"), ("script",))
        self.assertEqual(len(machine.machine_errors), 1)
        self.assertIn("test-design", run.machine_error)
        self.assertIsNone(machine.routed[-1][0])
        self.assertEqual(run.current_state, T.INVESTIGATE_WORKFLOW)
        self.assertEqual(run.paused_state, T.TEST_WRITING)
        self.assertEqual(run.tests_coverage_types, ())
        self.assertEqual(run.counters.value("test-writes"), 0)

    def test_a_test_design_that_is_all_no_tests_asks_for_no_tests_alone(self):
        machine, run = self.drive_a_test_write(
            ("no-tests", "no-tests"), (T.COVERAGE_TYPE_NO_TESTS,),
            and_then=[(T.TEST_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {})])
        self.assertEqual(machine.machine_errors, [])
        self.assertEqual(run.tests_coverage_types, (T.COVERAGE_TYPE_NO_TESTS,))
        self.assertFalse(run.tests_are_agent_instructions())
        # `no-tests` beside a type that is present is refused (section 2).
        machine, run = self.drive_a_test_write(("no-tests", "script"),
                                               (T.COVERAGE_TYPE_NO_TESTS, "script"))
        self.assertEqual(len(machine.machine_errors), 1)
        self.assertEqual(run.paused_state, T.TEST_WRITING)

    def test_a_test_design_the_machine_cannot_read_is_not_checked_against(self):
        # Nothing is checked when the file names no requirement the
        # machine can read: the check compares against the test-design's
        # per-requirement types, and there are none. Reading it for more
        # than its `coverage-type:` lines waits on the test-design's
        # syntax, which section 11 leaves to step 1 of the build order.
        M.refuse_a_test_write_that_disagrees_with_the_test_design(
            M.StateExitRecord(state=T.TEST_WRITING, verdict=T.V_EMITTED,
                              package_commit="a" * 40, coverage_types=("script",),
                              named_files=("a-test.py",)),
            "# a test-design with no coverage-type lines\n")
        M.refuse_a_test_write_that_disagrees_with_the_test_design(
            M.StateExitRecord(state=T.TEST_WRITING, verdict=T.V_EMITTED,
                              package_commit="a" * 40, coverage_types=("script",),
                              named_files=("a-test.py",)),
            None)


class TheDesignApprovedAfterARedesignEntersImplementationWritingOnly(unittest.TestCase):
    """Row 18 goes to implementation-writing only, and after a redesign the
    tests begin again by row 24 (user-ruled 2026-09-16, the walk
    design-tables-checker-findings-from-pr-409, item 2). Row 18 once also
    entered test-design-writing when tests had begun in the design version,
    and the clause and its code were deleted. After a redesign it cannot
    hold, since a redesign starts a new version, which resets tests-begun;
    a resume naming design-reviewing keeps the version, and the next class
    pins what row 18 does then. This pins the order the walk's scenario
    showed: tests begun, a reviewer's escalate-to-user with
    investigation-focus design, a resume to design-writing, the new design
    approved, row 18, row 24."""

    def setUp(self):
        self.repository = fixture.ThrowawayRepository()

    def tearDown(self):
        self.repository.remove()

    def test_row_18_enters_implementation_writing_only_and_row_24_begins_the_tests_again(self):
        script = fixture.prefix_to_tests_begun() + [
            fixture.test_design_write(),
            (T.TEST_DESIGN_ACCEPTANCE_BY_AGENT, T.V_ESCALATE_TO_USER,
             {"investigation_focus": T.FOCUS_DESIGN}),                              # row 69
            (T.INVESTIGATE_WORKFLOW, T.V_RESUME, {"destination": T.DESIGN_WRITING}),  # row 72
            (T.DESIGN_WRITING, T.V_EMITTED, {}),                                     # row 2
            (T.CONTRACT_ACCEPTANCE_BY_PROGRAM, T.V_ADVANCE, {}),                     # row 5
            (T.DESIGN_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {}),                         # row 16
            (T.DESIGN_ACCEPTANCE_BY_USER, T.V_ADVANCE, {}),                          # row 18
        ]
        machine, run, record, _ = fixture.make_machine(script, self.repository)
        fixture.drive(machine, run)
        self.assertEqual([row.row for row, _, _ in machine.routed],
                         ["1", "2", "5", "16", "18", "21", "24", "32", "69", "72",
                          "2", "5", "16", "18"])
        self.assertEqual(machine.machine_errors, [])
        self.assertEqual(run.design_version, 2)
        self.assertTrue(run.design_approved)
        self.assertFalse(run.tests_begun)
        self.assertEqual(run.current_state, T.IMPLEMENTATION_WRITING)
        self.assertEqual(run.implementation_work_stream_position, T.IMPLEMENTATION_WRITING)
        self.assertIsNone(run.test_work_stream_position)
        self.assertNotIn(T.TEST_DESIGN_WRITING, run.writing_state_entry_reason)

        machine.launcher.script.extend([
            fixture.implementation_write(),                                          # row 21
            (T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {}),                 # row 24
        ])
        fixture.drive(machine, run)
        self.assertEqual([row.row for row, _, _ in machine.routed][-3:], ["18", "21", "24"])
        self.assertEqual(machine.machine_errors, [])
        self.assertTrue(run.tests_begun)
        self.assertEqual(run.current_state, T.TEST_DESIGN_WRITING)
        self.assertEqual(run.implementation_work_stream_position, T.READY_FOR_TEST_SUITE)
        self.assertEqual(run.test_work_stream_position, T.TEST_DESIGN_WRITING)
        self.assertEqual(run.writing_state_entry_reason[T.TEST_DESIGN_WRITING],
                         T.ENTRY_REASON_FIRST_WRITE)


class TheDesignReapprovedWithoutARedesignReReviewsTheTestDesign(unittest.TestCase):
    """A resume naming design-reviewing after tests began starts no new
    design version, so tests-begun stays set when row 18 approves the
    design again (PR #429's review found the path). Row 18 goes to
    implementation-writing only; the test-work-stream keeps its position,
    so the test-design already written is reviewed again, not rewritten,
    and is rewritten only when its reviewer rejects it (user-ruled
    2026-09-16: "only restart if you have to")."""

    def setUp(self):
        self.repository = fixture.ThrowawayRepository()

    def tearDown(self):
        self.repository.remove()

    def test_row_18_with_tests_begun_holds_the_implementation_and_re_reviews_the_test_design(self):
        script = fixture.prefix_to_tests_begun() + [
            fixture.test_design_write(),
            (T.TEST_DESIGN_ACCEPTANCE_BY_AGENT, T.V_ESCALATE_TO_USER,
             {"investigation_focus": T.FOCUS_DESIGN}),                                  # row 69
            (T.INVESTIGATE_WORKFLOW, T.V_RESUME, {"destination": T.DESIGN_REVIEWING}),  # row 72
            (T.DESIGN_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {}),                             # row 16
            (T.DESIGN_ACCEPTANCE_BY_USER, T.V_ADVANCE, {}),                              # row 18
        ]
        machine, run, record, _ = fixture.make_machine(script, self.repository)
        fixture.drive(machine, run)
        self.assertEqual([row.row for row, _, _ in machine.routed],
                         ["1", "2", "5", "16", "18", "21", "24", "32", "69", "72",
                          "16", "18"])
        self.assertEqual(machine.machine_errors, [])
        self.assertEqual(run.design_version, 1)
        self.assertTrue(run.tests_begun)
        self.assertEqual(run.current_state, T.IMPLEMENTATION_WRITING)
        self.assertEqual(run.test_work_stream_position, T.TEST_DESIGN_REVIEWING)

        machine.launcher.script.extend([
            fixture.implementation_write(),                                              # row 21
            (T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_ADVANCE, {}),                     # row 26
        ])
        fixture.drive(machine, run)
        self.assertEqual([row.row for row, _, _ in machine.routed][-2:], ["21", "26"])
        self.assertEqual(machine.machine_errors, [])
        self.assertEqual(run.current_state, T.TEST_DESIGN_REVIEWING)
        self.assertEqual(run.implementation_work_stream_position, T.READY_FOR_TEST_SUITE)
        self.assertEqual(run.test_work_stream_position, T.TEST_DESIGN_REVIEWING)
        launched = [package["state"] for package in machine.launcher.launched]
        self.assertNotIn(T.TEST_DESIGN_WRITING, launched[launched.index(T.INVESTIGATE_WORKFLOW):])

        machine.launcher.script.append(
            (T.TEST_DESIGN_ACCEPTANCE_BY_AGENT, T.V_REJECT_TEST_DESIGN, {}))              # row 35
        fixture.drive(machine, run)
        self.assertEqual([row.row for row, _, _ in machine.routed][-1:], ["35"])
        self.assertEqual(run.current_state, T.TEST_DESIGN_WRITING)
        self.assertEqual(run.writing_state_entry_reason[T.TEST_DESIGN_WRITING],
                         T.ENTRY_REASON_REJECT_FROM_REVIEW)


class TheInvestigationReportInTheStatePackage(unittest.TestCase):
    """Sections 2 and 9 (user-ruled 2026-09-14, the tenth walk, item 17;
    built as ruled, 2026-09-16, walk design-tables-checker-findings-from-pr-409,
    item 1): the state-package names the investigation report's path as
    `investigation-report`, `reports/investigation-<n>.md` in the record,
    `<n>` the count of the investigate-workflow instance — counted as the
    evidence directory counts a state's instances, since only the machine
    knows it. It rides in investigate-workflow's package, for the report
    the talking agent is about to write (section 6.6), and in
    design-writing's on a redesign, for the report of the investigation
    that opened it (section 3.1); in no other package."""

    def setUp(self):
        self.repository = fixture.ThrowawayRepository()

    def tearDown(self):
        self.repository.remove()

    def escalation_from_test_design_writing(self):
        return (T.TEST_DESIGN_WRITING, T.V_ESCALATE_TO_USER, {"investigation_focus": T.FOCUS_DESIGN})

    def packages_for(self, machine, state):
        return [p for p in machine.launcher.launched if p["state"] == state]

    def report_path(self, record, instance_number):
        return str(record.record_directory / "reports" / ("investigation-%d.md" % instance_number))

    def test_the_first_investigations_package_names_investigation_1(self):
        script = fixture.prefix_to_tests_begun() + [
            self.escalation_from_test_design_writing(),
            (T.INVESTIGATE_WORKFLOW, T.V_RESUME, {}),
        ]
        machine, run, record, _ = fixture.make_machine(script, self.repository)
        fixture.drive(machine, run)
        investigations = self.packages_for(machine, T.INVESTIGATE_WORKFLOW)
        self.assertEqual(len(investigations), 1)
        self.assertTrue(str(investigations[0]["investigation-report"]).endswith(
            "design-to-main-record/reports/investigation-1.md"))
        self.assertEqual(str(investigations[0]["investigation-report"]), self.report_path(record, 1))

    def test_a_second_investigation_in_the_same_run_names_investigation_2(self):
        script = fixture.prefix_to_tests_begun() + [
            self.escalation_from_test_design_writing(),
            (T.INVESTIGATE_WORKFLOW, T.V_RESUME, {}),     # nothing edited: back to test-design-writing
            self.escalation_from_test_design_writing(),
            (T.INVESTIGATE_WORKFLOW, T.V_RESUME, {}),
        ]
        machine, run, record, _ = fixture.make_machine(script, self.repository)
        fixture.drive(machine, run)
        self.assertEqual([str(p["investigation-report"])
                          for p in self.packages_for(machine, T.INVESTIGATE_WORKFLOW)],
                         [self.report_path(record, 1), self.report_path(record, 2)])

    def test_design_writing_entered_as_a_redesign_names_the_investigation_that_opened_it(self):
        script = fixture.prefix_to_tests_begun() + [
            self.escalation_from_test_design_writing(),
            (T.INVESTIGATE_WORKFLOW, T.V_RESUME, {"destination": T.DESIGN_WRITING}),
            (T.DESIGN_WRITING, T.V_EMITTED, {}),
        ]
        machine, run, record, _ = fixture.make_machine(script, self.repository)
        fixture.drive(machine, run)
        self.assertEqual(run.design_version, 2)
        redesign = self.packages_for(machine, T.DESIGN_WRITING)[-1]
        self.assertEqual(redesign["design-version"], 2)
        self.assertEqual(str(redesign["investigation-report"]), self.report_path(record, 1))

    def test_a_redesign_after_two_investigations_names_the_most_recent(self):
        script = fixture.prefix_to_tests_begun() + [
            self.escalation_from_test_design_writing(),
            (T.INVESTIGATE_WORKFLOW, T.V_RESUME, {}),
            self.escalation_from_test_design_writing(),
            (T.INVESTIGATE_WORKFLOW, T.V_RESUME, {"destination": T.DESIGN_WRITING}),
            (T.DESIGN_WRITING, T.V_EMITTED, {}),
        ]
        machine, run, record, _ = fixture.make_machine(script, self.repository)
        fixture.drive(machine, run)
        redesign = self.packages_for(machine, T.DESIGN_WRITING)[-1]
        self.assertEqual(redesign["design-version"], 2)
        self.assertEqual(str(redesign["investigation-report"]), self.report_path(record, 2))

    def test_design_writing_re_entered_within_the_redesigns_version_names_none(self):
        # The initiator lives through the re-entries of its state in the
        # design version (section 1) and already holds the report; the
        # re-entry after the design's agent check rejects it is a
        # design-revision, not a redesign (section 2).
        script = fixture.prefix_to_tests_begun() + [
            self.escalation_from_test_design_writing(),
            (T.INVESTIGATE_WORKFLOW, T.V_RESUME, {"destination": T.DESIGN_WRITING}),
            (T.DESIGN_WRITING, T.V_EMITTED, {}),
            (T.CONTRACT_ACCEPTANCE_BY_PROGRAM, T.V_ADVANCE, {}),
            (T.DESIGN_ACCEPTANCE_BY_AGENT, T.V_REJECT_DESIGN, {}),     # row 12
            (T.DESIGN_WRITING, T.V_EMITTED, {}),
        ]
        machine, run, record, _ = fixture.make_machine(script, self.repository)
        fixture.drive(machine, run)
        design_writings = self.packages_for(machine, T.DESIGN_WRITING)
        self.assertEqual(len(design_writings), 3)
        self.assertEqual([p["design-version"] for p in design_writings], [1, 2, 2])
        self.assertIn("investigation-report", design_writings[1])
        self.assertNotIn("investigation-report", design_writings[2])

    def test_the_first_design_write_and_ordinary_states_name_none(self):
        script = fixture.prefix_to_tests_begun() + [
            self.escalation_from_test_design_writing(),
            (T.INVESTIGATE_WORKFLOW, T.V_RESUME, {}),     # nothing edited: back to test-design-writing
            fixture.test_design_write(),
        ]
        machine, run, record, _ = fixture.make_machine(script, self.repository)
        fixture.drive(machine, run)
        first_design_write = self.packages_for(machine, T.DESIGN_WRITING)[0]
        self.assertEqual(first_design_write["design-version"], 1)
        self.assertNotIn("investigation-report", first_design_write)
        self.assertNotIn("investigation-report", self.packages_for(machine, T.IMPLEMENTATION_WRITING)[0])
        # The state resumed after the investigation is not a redesign either.
        resumed = self.packages_for(machine, T.TEST_DESIGN_WRITING)
        self.assertEqual(len(resumed), 2)
        self.assertNotIn("investigation-report", resumed[-1])
        self.assertEqual(
            [p["state"] for p in machine.launcher.launched if "investigation-report" in p],
            [T.INVESTIGATE_WORKFLOW])


if __name__ == "__main__":
    unittest.main(verbosity=2)
