#!/usr/bin/env python3
"""The scenario runner (design-to-main-scenario-runner.py; user-ruled
2026-09-16, the eleventh walk, item 6): the shipped scenarios play through
the real machine and their traces say what the machine did — the happy
path ends passed naming every state in the design's order; the walk's
example scenario carries the counters and stands where row 62 sends it;
the ceiling scenario pauses at the arbitrator's third entry; a malformed
scenario is refused with its line.

Run: python3 scripts/design-to-main/tests/design-to-main-scenario-runner-test.py
"""

import importlib.util
import pathlib
import subprocess
import sys
import tempfile
import unittest

TESTS_DIR = pathlib.Path(__file__).resolve().parent
RUNNER_PATH = TESTS_DIR.parent / "design-to-main-scenario-runner.py"
SCENARIOS_DIR = TESTS_DIR.parent / "scenarios"

_runner_spec = importlib.util.spec_from_file_location("design_to_main_scenario_runner", RUNNER_PATH)
runner = importlib.util.module_from_spec(_runner_spec)
_runner_spec.loader.exec_module(runner)

T = runner.tables

HAPPY_PATH_SCENARIO = SCENARIOS_DIR / "happy-path-every-state-advances-to-passed.yaml"
EXAMPLE_SCENARIO = SCENARIOS_DIR / (
    "implementation-rejected-twice-then-suite-fails-and-arbitrator-calls-flaky.yaml")
CEILING_SCENARIO = SCENARIOS_DIR / (
    "implementation-rejected-at-its-ceiling-until-the-arbitrators-third-entry-pauses.yaml")


def play_file(path):
    return runner.play_scenario(runner.parse_scenario_text(pathlib.Path(path).read_text()))


class TheHappyPathScenario(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.played = play_file(HAPPY_PATH_SCENARIO)
        cls.text = runner.format_trace(cls.played)

    def test_the_run_ends_passed(self):
        self.assertEqual(self.played.ending, "ENDED passed")
        self.assertEqual(self.played.run.outcome, T.OUTCOME_PASSED)
        self.assertTrue(self.text.endswith("\nENDED passed"))

    def test_the_trace_names_every_state_in_the_design_s_order(self):
        self.assertEqual([line.from_state for line in self.played.trace], [
            T.INITIATE_DESIGN_TO_MAIN, T.DESIGN_WRITING, T.CONTRACT_ACCEPTANCE_BY_PROGRAM,
            T.DESIGN_ACCEPTANCE_BY_AGENT, T.DESIGN_ACCEPTANCE_BY_USER,
            T.IMPLEMENTATION_WRITING, T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT,
            T.TEST_DESIGN_WRITING, T.TEST_DESIGN_ACCEPTANCE_BY_AGENT, T.TEST_DESIGN_ACCEPTANCE_BY_USER,
            T.TEST_WRITING, T.TEST_ACCEPTANCE_BY_AGENT,
            T.TEST_SUITE_EXECUTING, T.SUBMIT_TO_PR_GATE,
        ])
        self.assertEqual([line.to_state for line in self.played.trace][-1], T.ENDED)
        self.assertEqual([line.row for line in self.played.trace],
                         ["1", "2", "5", "16", "18", "21", "24", "32", "16", "41",
                          "42", "47", "56", "74"])

    def test_the_trace_is_one_numbered_line_per_routed_state_exit_with_the_row(self):
        lines = self.text.splitlines()
        self.assertEqual(lines[0], "scenario: the happy path, every state advancing, ending passed")
        self.assertTrue(lines[1].startswith("step 1 "), lines[1])
        self.assertIn("initiate-design-to-main → design-writing", lines[1])
        self.assertIn("row 1", lines[1])
        self.assertIn("implementation-writes 1 of 3", lines[6])
        self.assertIn("(next acceptance-check)", lines[4])
        self.assertEqual(len(lines), 1 + 14 + 1)
        self.assertNotIn("PAUSED", self.text)


class TheWalksExampleScenario(unittest.TestCase):
    """The scenario the walk named: the implementation rejected twice, the
    suite failing, the arbitrator calling it flaky. Rows 27, 27, 57 and
    62: after `flaky-test` the writer's counter (test-writes, 1) is below
    its ceiling, so row 62 sends the run to test-writing, and there the
    scenario's steps are spent — no pause; the pause of the arbitrator's
    ceiling is the next class's scenario."""

    @classmethod
    def setUpClass(cls):
        cls.played = play_file(EXAMPLE_SCENARIO)
        cls.text = runner.format_trace(cls.played)

    def test_the_named_steps_take_the_rows_the_design_gives_them(self):
        by_number = {line.number: line for line in self.played.trace}
        self.assertEqual((by_number[7].verdict, by_number[7].row, by_number[7].to_state),
                         (T.V_REJECT_IMPLEMENTATION, "27", T.IMPLEMENTATION_WRITING))
        self.assertEqual((by_number[9].verdict, by_number[9].row), (T.V_REJECT_IMPLEMENTATION, "27"))
        self.assertEqual((by_number[17].verdict, by_number[17].row, by_number[17].to_state),
                         (T.V_FAIL, "57", T.TEST_SUITE_ARBITRATING))
        self.assertEqual((by_number[18].verdict, by_number[18].row, by_number[18].to_state),
                         (T.V_FLAKY_TEST, "62", T.TEST_WRITING))

    def test_the_trace_carries_the_counters_as_they_change(self):
        by_number = {line.number: line for line in self.played.trace}
        self.assertEqual(by_number[8].counters_changed, [("implementation-writes", 2, 3)])
        self.assertEqual(by_number[10].counters_changed, [("implementation-writes", 3, 3)])
        self.assertEqual(by_number[17].counters_changed, [("arbitrator-rulings", 1, 2)])
        self.assertEqual(by_number[7].counters_changed, [])
        self.assertIn("implementation-writes 3 of 3", self.text)
        self.assertIn("arbitrator-rulings 1 of 2", self.text)

    def test_the_run_stands_where_the_steps_leave_it(self):
        self.assertEqual(self.played.run.current_state, T.TEST_WRITING)
        self.assertTrue(self.played.ending.startswith("STOPPED at test-writing:"), self.played.ending)
        self.assertNotIn("PAUSED", self.text)
        self.assertIsNone(self.played.never_reached)


class TheArbitratorsThirdEntryScenario(unittest.TestCase):
    """Reject every implementation: the third write's reject goes to the
    arbitrator (row 28), whose ruling sends the writer back (row 63); the
    arbitrator's third entry in the design version opens the
    investigation (row 65, applied on entry) — the user is called."""

    @classmethod
    def setUpClass(cls):
        cls.played = play_file(CEILING_SCENARIO)
        cls.text = runner.format_trace(cls.played)

    def test_the_run_pauses_at_the_arbitrator_s_third_entry(self):
        last = self.played.trace[-1]
        self.assertEqual((last.from_state, last.verdict, last.row, last.to_state),
                         (T.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, T.V_REJECT_IMPLEMENTATION, "28",
                          T.INVESTIGATE_WORKFLOW))
        self.assertEqual(last.qualifier, "row 65 on entry")
        self.assertIn("the arbitrator's third entry in design version 1 (row 65)", last.pause)
        self.assertEqual(self.played.run.paused_state, T.TEST_SUITE_ARBITRATING)
        self.assertIn("PAUSED at investigate-workflow (paused state test-suite-arbitrating, "
                      "investigation-focus unknown: the arbitrator's third entry", self.text)
        self.assertTrue(self.played.ending.startswith("STOPPED at investigate-workflow:"))

    def test_the_counters_climb_to_their_ceilings_in_the_trace(self):
        rows = [line.row for line in self.played.trace]
        self.assertEqual(rows[5:], ["21", "27", "21", "27", "21", "28", "63", "21", "28", "63", "21", "28"])
        changed = [line.counters_changed for line in self.played.trace if line.counters_changed]
        self.assertEqual(changed, [
            [("implementation-writes", 1, 3)], [("implementation-writes", 2, 3)],
            [("implementation-writes", 3, 3)], [("arbitrator-rulings", 1, 2)],
            [("arbitrator-rulings", 2, 2)]])
        self.assertIn("(that writer anyway, fresh)", self.text)


class AScenarioTheMachineCallsAMachineError(unittest.TestCase):
    """A verdict the state has but no row allows in context is not
    malformed: the machine routes it as a machine error, and the trace
    shows the pause — which is the game."""

    def test_the_trace_shows_no_row_and_the_pause(self):
        played = runner.play_scenario(runner.parse_scenario_text(
            "scenario: a discuss from the program check\nsteps:\n"
            "  - contract-acceptance-by-program: discuss\n"))
        last = played.trace[-1]
        self.assertEqual((last.row, last.qualifier, last.to_state),
                         ("—", "machine error", T.INVESTIGATE_WORKFLOW))
        self.assertIn("no row of section 3.2 allows 'discuss' from contract-reviewing", last.pause)


class TwoCoverageTypesInEitherSpellingPlayAsTheMachineReadsThem(unittest.TestCase):
    """Review 2026-09-16 by mac-claude on PR #407, the blocking finding:
    `coverage-type: script, prompt`, section 2's comma form, is split as
    the machine splits state-exit.json (coverage_types_from_json_field),
    so an implementation claiming two coverage-types is the machine error
    in this spelling as in the flow list `[script, prompt]`."""

    COMMA_FORM = ("scenario: the implementation writer claims two coverage-types\n"
                  "steps:\n"
                  "  - state: implementation-writing\n"
                  "    verdict: emitted\n"
                  "    fields:\n"
                  "      coverage-type: script, prompt\n"
                  "  - implementation-acceptance-by-agent: advance\n")
    FLOW_LIST_FORM = COMMA_FORM.replace("coverage-type: script, prompt",
                                        "coverage-type: [script, prompt]")

    def test_both_field_names_split_the_comma_form(self):
        for spelling in ("coverage-type: script, prompt", "coverage_types: script, prompt",
                         "coverage-type: [script, prompt]"):
            scenario = runner.parse_scenario_text(
                self.COMMA_FORM.replace("coverage-type: script, prompt", spelling))
            self.assertEqual(scenario.steps[0].fields, {"coverage_types": ("script", "prompt")}, spelling)

    def test_the_comma_form_is_the_machine_error_and_plays_as_the_flow_list(self):
        comma = play_scenario_text(self.COMMA_FORM)
        flow_list = play_scenario_text(self.FLOW_LIST_FORM)
        last = comma.trace[-1]
        self.assertEqual((last.from_state, last.verdict, last.row, last.qualifier, last.to_state),
                         (T.IMPLEMENTATION_WRITING, T.V_EMITTED, "—", "machine error",
                          T.INVESTIGATE_WORKFLOW))
        self.assertIn("an implementation has one", last.pause)
        self.assertEqual(comma.never_reached.step.line, 7)
        self.assertEqual(comma.trace, flow_list.trace)
        self.assertEqual(comma.ending, flow_list.ending)
        self.assertEqual(runner.format_trace(comma), runner.format_trace(flow_list))


class TheScenarioFile(unittest.TestCase):

    def test_the_mapping_form_carries_fields_and_the_design_s_field_names(self):
        scenario = runner.parse_scenario_text(
            "# a comment\n"
            "scenario: fields\n"
            "steps:\n"
            "  - test-suite-executing: fail   # the suite fails\n"
            "  - state: test-suite-arbitrating\n"
            "    verdict: escalate-to-user\n"
            "    fields:\n"
            "      investigation-focus: design\n"
            "      coverage_types: [script, prompt]\n"
            "      rulings: reset\n")
        self.assertEqual(scenario.name, "fields")
        self.assertEqual([(s.state, s.verdict, s.line) for s in scenario.steps],
                         [(T.TEST_SUITE_EXECUTING, T.V_FAIL, 4), (T.TEST_SUITE_ARBITRATING, T.V_ESCALATE_TO_USER, 5)])
        self.assertEqual(scenario.steps[1].fields, {
            "investigation_focus": "design", "coverage_types": ("script", "prompt"), "rulings": ("reset",)})

    def test_an_unknown_verdict_is_refused_with_its_line(self):
        with self.assertRaises(runner.MalformedScenario) as refused:
            play_scenario_text("scenario: x\nsteps:\n"
                               "  - implementation-acceptance-by-agent: reject implementation\n"
                               "  - test-suite-executing: flaky-test\n")
        self.assertEqual(refused.exception.line, 4)
        self.assertIn("test-suite-executing has no verdict 'flaky-test'", str(refused.exception))

    def test_the_refusal_at_the_arbitrator_names_escalate_to_user_once(self):
        # Review 2026-09-16 by mac-claude on PR #407: its row of section 3.1
        # already lists escalate-to-user, which was appended a second time.
        self.assertEqual(runner.verdicts_a_state_may_emit(T.TEST_SUITE_ARBITRATING).count(
            T.V_ESCALATE_TO_USER), 1)
        with self.assertRaises(runner.MalformedScenario) as refused:
            play_scenario_text("scenario: x\nsteps:\n  - test-suite-arbitrating: pass\n")
        self.assertIn("test-suite-arbitrating has no verdict 'pass'", str(refused.exception))
        self.assertEqual(str(refused.exception).count(T.V_ESCALATE_TO_USER), 1, str(refused.exception))

    def test_an_unknown_state_and_a_composite_state_are_refused_with_their_lines(self):
        with self.assertRaises(runner.MalformedScenario) as refused:
            play_scenario_text("scenario: x\nsteps:\n  - test-suite-executing: fail\n  - suite: fail\n")
        self.assertEqual(refused.exception.line, 4)
        self.assertIn("unknown state 'suite'", str(refused.exception))
        with self.assertRaises(runner.MalformedScenario) as refused:
            play_scenario_text("scenario: x\nsteps:\n  - implementation-reviewing: advance\n")
        self.assertEqual(refused.exception.line, 3)
        self.assertIn("name one of its acceptance-checks", str(refused.exception))

    def test_a_step_the_happy_path_never_reaches_is_reported_with_its_line(self):
        played = play_scenario_text("scenario: x\nsteps:\n  - contract-acceptance-by-user: discuss\n")
        self.assertEqual(played.never_reached.step.line, 3)
        self.assertEqual(played.ending, "ENDED passed")
        played = play_scenario_text(
            "scenario: x\nsteps:\n"
            "  - implementation-acceptance-by-agent: reject contract\n"
            "  - test-suite-executing: fail\n")
        self.assertEqual(played.never_reached.step.line, 4)
        self.assertEqual(played.never_reached.standing_at, T.CONTRACT_REVISING)
        self.assertIn("give contract-revising its verdict first", str(played.never_reached))


def play_scenario_text(text):
    return runner.play_scenario(runner.parse_scenario_text(text))


class TheCommandLine(unittest.TestCase):

    def run_runner(self, path):
        return subprocess.run([sys.executable, str(RUNNER_PATH), str(path)],
                              capture_output=True, text=True)

    def test_a_played_scenario_exits_zero_with_the_trace_on_stdout(self):
        result = self.run_runner(HAPPY_PATH_SCENARIO)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.rstrip().endswith("ENDED passed"), result.stdout)
        self.assertEqual(result.stderr, "")

    def test_a_malformed_scenario_exits_two_naming_the_line(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "unknown-verdict.yaml"
            path.write_text("scenario: x\nsteps:\n  - test-suite-executing: flaky-test\n")
            result = self.run_runner(path)
        self.assertEqual(result.returncode, runner.EXIT_MALFORMED_SCENARIO)
        self.assertIn("line 3:", result.stderr)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
