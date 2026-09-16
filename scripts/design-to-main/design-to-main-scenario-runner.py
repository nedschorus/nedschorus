#!/usr/bin/env python3
"""Play a scenario through the design-to-main machine and print the trace.

User-ruled 2026-09-16, the eleventh walk
(design-state-tables-source-of-truth-and-checker), item 6 — the user's own
idea: run "simulated design-to-main flows so we can both see if the state
machine does what we want it to do. Like a little game almost."

The machine is the real one (design-to-main-state-machine.py) over a
throwaway repository, built and driven by the test fixture
(tests/design-to-main-test-fixture.py); nothing here routes.

A scenario is a file the user writes — a name and the steps he wants to
play, each `state: verdict`:

    scenario: implementation rejected twice, then the suite fails
    steps:
      - implementation-acceptance-by-agent: reject implementation
      - implementation-acceptance-by-agent: reject implementation
      - test-suite-executing: fail
      - test-suite-arbitrating: flaky-test

A step may instead be a mapping with `state`, `verdict` and `fields` (the
state-exit's optional fields of section 2, `coverage_types: [script]` and
the like) for the rare case that needs them. Every state the machine
launches that the scenario's next step does not name gets the canonical
happy path's verdict for it (the fixture's whole_run_to_passed), before the
first named step and between named steps alike; a step at a state the
happy path never launches must therefore follow a step that leads there.
Once the steps are spent the runner supplies nothing more: it says where
the run stands.

The trace is one line per state-exit the machine routed: the step
number; the state that emitted it and the state the run moved to, with
the qualifier the transition row carries; the verdict; the row of
section 3.2 the machine took; every counter whose value changed, as
`name N of ceiling`. A pause names the state and the reason in the run-
state's words; the end names the outcome.

Run: python3 scripts/design-to-main/design-to-main-scenario-runner.py <scenario.yaml>
Exit 0 whether the run passed, paused or stands mid-way — the trace is the
product; exit 2 for a malformed scenario (an unknown state, a verdict the
state does not have, a step the run never reaches), naming the line.
"""

import dataclasses
import importlib.util
import pathlib
import sys

_fixture_spec = importlib.util.spec_from_file_location(
    "design_to_main_test_fixture",
    pathlib.Path(__file__).resolve().parent / "tests" / "design-to-main-test-fixture.py")
fixture = importlib.util.module_from_spec(_fixture_spec)
_fixture_spec.loader.exec_module(fixture)

tables = fixture.tables
machine_module = fixture.machine_module

EXIT_MALFORMED_SCENARIO = 2


class MalformedScenario(Exception):
    """The scenario file cannot be played; `line` is the line at fault."""

    def __init__(self, line, message):
        super().__init__("line %d: %s" % (line, message))
        self.line = line


@dataclasses.dataclass
class ScenarioStep:
    state: str
    verdict: str
    fields: dict
    line: int


@dataclasses.dataclass
class Scenario:
    name: str
    steps: list


# --- Reading the scenario file ---------------------------------------------
#
# The shape above is a small subset of YAML, read here without a YAML
# library, so the runner needs nothing beyond the standard library, and
# with line numbers kept, which the refusals need and a library would not
# give.

STEP_KEYS = ("state", "verdict", "fields")
STATE_EXIT_FIELD_NAMES = tuple(
    f.name for f in dataclasses.fields(machine_module.StateExitRecord)
    if f.name not in ("state", "verdict", "package_commit"))
# The design's hyphenated field names are accepted too (section 2).
STATE_EXIT_FIELD_BY_DESIGN_NAME = {
    design_name: field_name
    for design_name, field_name in tables.STATE_EXIT_JSON_FIELDS.items()
    if field_name in STATE_EXIT_FIELD_NAMES}
TUPLE_VALUED_FIELDS = ("coverage_types", "named_files", "rulings")


def _split_key_and_value(text, line):
    key, separator, value = text.partition(": ")
    if not separator:
        if text.endswith(":"):
            return text[:-1].strip(), ""
        raise MalformedScenario(line, "expected `key: value`, got %r" % text)
    return key.strip(), _unquote(value.strip())


def _unquote(value):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _field_value(value):
    """A scalar, or a flow list `[a, b]` as a tuple."""
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        return tuple(_unquote(item.strip()) for item in inner.split(",")) if inner else ()
    return value


def _without_comment(raw):
    if raw.lstrip().startswith("#"):
        return ""
    return raw.split(" #", 1)[0]


def parse_scenario_text(text):
    name = None
    steps = []
    in_steps = False
    current = None          # the step mapping being read
    current_indent = None   # the column of its `- `
    fields_indent = None    # the column of its field lines, once seen
    for line, raw in enumerate(text.splitlines(), start=1):
        content = _without_comment(raw).rstrip()
        if not content.strip():
            continue
        indent = len(content) - len(content.lstrip())
        stripped = content.strip()
        if indent == 0:
            key, value = _split_key_and_value(stripped, line)
            if key == "scenario":
                name = value
            elif key == "steps":
                in_steps = True
            else:
                raise MalformedScenario(line, "unknown key %r; the file has `scenario` and `steps`" % key)
            continue
        if not in_steps:
            raise MalformedScenario(line, "an indented line before `steps:`")
        if stripped.startswith("- "):
            key, value = _split_key_and_value(stripped[2:].strip(), line)
            current = {"line": line, "fields": {}}
            current_indent = indent
            fields_indent = None
            if key in STEP_KEYS:
                current["form"] = "mapping"
                if key == "fields":
                    raise MalformedScenario(line, "a step starts with `state`, not `fields`")
                current[key] = value
            else:
                current["form"] = "short"
                current["state"], current["verdict"] = key, value
            steps.append(current)
            continue
        key, value = _split_key_and_value(stripped, line)
        if current is None or current["form"] == "short":
            raise MalformedScenario(line, "a line continues a step that is already complete")
        if indent == current_indent + 2:
            if key not in STEP_KEYS:
                raise MalformedScenario(line, "unknown step key %r; a step has %s" % (
                    key, ", ".join(STEP_KEYS)))
            if key == "fields":
                if value:
                    raise MalformedScenario(line, "`fields:` opens a mapping; its entries go on the lines below")
                fields_indent = "open"
            else:
                current[key] = value
        elif fields_indent is not None and indent > current_indent + 2:
            if fields_indent == "open":
                fields_indent = indent
            if indent != fields_indent:
                raise MalformedScenario(line, "a field line at an unexpected indentation")
            field = STATE_EXIT_FIELD_BY_DESIGN_NAME.get(key, key)
            if field not in STATE_EXIT_FIELD_NAMES:
                raise MalformedScenario(line, "no state-exit field named %r (section 2); the fields are %s" % (
                    key, ", ".join(STATE_EXIT_FIELD_NAMES)))
            parsed = _field_value(value)
            if field in TUPLE_VALUED_FIELDS and not isinstance(parsed, tuple):
                parsed = (parsed,)
            current["fields"][field] = parsed
        else:
            raise MalformedScenario(line, "a line at an unexpected indentation")
    if name is None:
        raise MalformedScenario(1, "no `scenario:` line names the scenario")
    if not in_steps:
        raise MalformedScenario(1, "no `steps:` list")
    return Scenario(name, [_step_from_mapping(mapping) for mapping in steps])


def _step_from_mapping(mapping):
    for key in ("state", "verdict"):
        if not mapping.get(key):
            raise MalformedScenario(mapping["line"], "the step names no %s" % key)
    return ScenarioStep(mapping["state"], mapping["verdict"], mapping["fields"], mapping["line"])


# --- Checking the steps against the tables ----------------------------------

def states_the_machine_launches():
    """Every state or sub-state a state-package is built for: the plain
    states of section 3.1 and the acceptance-checks of the composite
    ones; never a composite state itself, nor `ended`."""
    launched = []
    for row in tables.STATE_TABLE:
        if row.work == "composite":
            launched.extend(row.sub_states)
        elif row.work != "terminal":
            launched.append(row.name)
    return tuple(launched)


def verdicts_a_state_may_emit(state):
    """Section 3.1's verdicts for the state (a sub-state's are its
    composite's), plus `escalate-to-user` where the paragraph after the
    table adds it."""
    composite = tables.COMPOSITE_STATE_OF_SUB_STATE.get(state, state)
    verdicts = list(tables.STATE_TABLE_BY_NAME[composite].verdicts)
    if state in tables.ACCEPTANCE_CHECKS_BY_AGENT or state in tables.STATES_WITH_ESCALATE_TO_USER:
        verdicts.append(tables.V_ESCALATE_TO_USER)
    return tuple(verdicts)


def check_steps_against_the_tables(steps):
    launched = states_the_machine_launches()
    for step in steps:
        if step.state not in launched:
            composite = tables.STATE_TABLE_BY_NAME.get(step.state)
            if composite is not None and composite.work == "composite":
                raise MalformedScenario(step.line, "%s is a reviewing state; name one of its acceptance-checks: %s" % (
                    step.state, ", ".join(composite.sub_states)))
            raise MalformedScenario(step.line, "unknown state %r; the machine launches %s" % (
                step.state, ", ".join(launched)))
        verdicts = verdicts_a_state_may_emit(step.state)
        if step.verdict not in verdicts:
            raise MalformedScenario(step.line, "%s has no verdict %r (section 3.1); it has %s" % (
                step.state, step.verdict, ", ".join(verdicts)))


# --- Playing ----------------------------------------------------------------

class ScenarioStepNeverReached(Exception):
    """The run went past, or stands short of, the state a step names."""

    def __init__(self, step, standing_at, why):
        super().__init__("line %d: the run never reaches %s: %s" % (step.line, step.state, why))
        self.step = step
        self.standing_at = standing_at


class ScenarioStateExitLauncher(fixture.ScriptedStateExitLauncherWritingFiles):
    """The fixture's stub launcher, choosing each state-exit as the state
    is launched: the scenario's next step when it names the launched
    state, else the happy path's verdict for that state, else — the steps
    spent — nothing, so the run stands where it is. A step whose verdict
    is the happy path's for its state inherits that step's fields (a
    write's coverage-type, the test-design's file), so that a bare
    `test-writing: emitted` is the write the fixture would script."""

    def __init__(self, steps, checkout):
        super().__init__([], checkout)
        self.steps = list(steps)
        self.happy_path = {state: (verdict, fields)
                           for state, verdict, fields in fixture.whole_run_to_passed()}

    def launch(self, state_package):
        state = state_package["state"]
        if self.steps and self.steps[0].state == state:
            step = self.steps.pop(0)
            verdict = step.verdict
            fields = {}
            if state in self.happy_path and self.happy_path[state][0] == verdict:
                fields.update(self.happy_path[state][1])
            fields.update(step.fields)
        elif self.steps:
            if state not in self.happy_path:
                raise ScenarioStepNeverReached(
                    self.steps[0], state,
                    "the run stands at %s, which the happy path does not cross; "
                    "give %s its verdict first" % (state, state))
            verdict, fields = self.happy_path[state]
        else:
            self.launched.append(state_package)   # asked for, as the base class records it
            raise machine_module.ScriptedStateExitLauncherExhausted(
                "the scenario's steps are spent at %s" % state)
        self.script = [(state, verdict, dict(fields))]
        return super().launch(state_package)


@dataclasses.dataclass
class TraceLine:
    number: int
    from_state: str
    to_state: str
    qualifier: str
    verdict: str
    row: str
    counters_changed: list   # (name, value, ceiling)
    pause: str = None        # the pause's reason, when the run is now paused


# The transition table's destination markers, as the trace qualifies the
# state the machine resolved them to.
QUALIFIER_OF_DESTINATION_MARKER = {
    tables.TO_HOLD_READY_FOR_TEST_SUITE: "hold at ready-for-test-suite",
    tables.TO_BOTH_WORK_STREAMS_RE_ENTER: "both work-streams re-enter",
    tables.TO_RESUME_DESTINATION: "the resume destination",
    tables.TO_RETRY_SAME_STATE: "retry",
    tables.TO_THE_NEXT_ACCEPTANCE_CHECK: "next acceptance-check",
    tables.TO_THE_WRITER_THE_VERDICT_NAMES: "that writer anyway, fresh",
    tables.TO_BOTH_WRITERS_FRESH: "both writers, fresh",
    tables.TO_WHEREVER_THAT_REVIEWING_STATES_ADVANCE_GOES: "as the reviewer's advance",
}


def observe_every_routed_state_exit(machine, trace):
    """Wrap the machine's routing so that every state-exit it routes — a
    reviewing state routes several in one step — leaves one trace line:
    the row from `machine.routed`, the destination from the run, the
    counters by their change across the call."""
    route = machine.route_state_exit

    def route_and_trace(run, state_exit):
        counters_before = run.counters.as_dict()
        advances_before = len(machine.reviewers_advances_applied)
        held_before = len(machine.held_rulings_applied)
        route(run, state_exit)
        row, _, _ = machine.routed[-1]
        qualifiers = []
        if row is None:
            qualifiers.append("machine error")
        elif row.to_state in QUALIFIER_OF_DESTINATION_MARKER:
            qualifiers.append(QUALIFIER_OF_DESTINATION_MARKER[row.to_state])
        for applied, before in ((machine.reviewers_advances_applied, advances_before),
                                (machine.held_rulings_applied, held_before)):
            qualifiers.extend("via row %s" % r.row for r, _ in applied[before:])
        if (run.current_state == tables.INVESTIGATE_WORKFLOW and row is not None
                and run.investigation_opened_by_row not in (None, row.row)):
            qualifiers.append("row %s on entry" % run.investigation_opened_by_row)
        counters_after = run.counters.as_dict()
        changed = [(name, counters_after[name], tables.COUNTER_TABLE_BY_NAME[name].ceiling)
                   for name in tables.COUNTER_NAMES
                   if counters_after[name] != counters_before[name]]
        pause = None
        if run.current_state == tables.INVESTIGATE_WORKFLOW:
            reason = run.machine_error if row is None else run.investigation_opened_by
            pause = "paused state %s, investigation-focus %s: %s" % (
                run.paused_state, run.investigation_focus, reason)
        trace.append(TraceLine(len(trace) + 1, state_exit.state, run.current_state,
                               ", ".join(qualifiers), state_exit.verdict,
                               row.row if row is not None else "—", changed, pause))
        return run.current_state

    machine.route_state_exit = route_and_trace


@dataclasses.dataclass
class ScenarioPlayed:
    scenario: Scenario
    trace: list
    ending: str
    run: object
    never_reached: ScenarioStepNeverReached = None


def play_scenario(scenario, max_steps=200):
    check_steps_against_the_tables(scenario.steps)
    repository = fixture.ThrowawayRepository()
    try:
        machine, run, _, _ = fixture.make_machine([], repository)
        machine.launcher = ScenarioStateExitLauncher(scenario.steps, repository.checkout)
        trace = []
        observe_every_routed_state_exit(machine, trace)
        never_reached = None
        steps = 0
        while run.current_state != tables.ENDED:
            try:
                machine.step(run)
            except machine_module.ScriptedStateExitLauncherExhausted:
                break
            except ScenarioStepNeverReached as error:
                never_reached = error
                break
            steps += 1
            if steps > max_steps:
                raise RuntimeError("the run did not end within %d steps" % max_steps)
        if run.current_state == tables.ENDED:
            ending = "ENDED %s" % run.outcome
            if machine.launcher.steps:
                never_reached = ScenarioStepNeverReached(
                    machine.launcher.steps[0], tables.ENDED,
                    "the run ended %s before it" % run.outcome)
        elif never_reached is not None:
            ending = "STOPPED at %s: line %d names %s, which the run never reaches" % (
                never_reached.standing_at, never_reached.step.line, never_reached.step.state)
        elif run.current_state == tables.INVESTIGATE_WORKFLOW:
            ending = ("STOPPED at investigate-workflow: the scenario's steps are spent; the run "
                      "stands paused, waiting for the user's stop, submit-to-PR-gate or resume")
        else:
            # The state the launcher was asked for: a reviewing state's
            # acceptance-check, which is what the scenario's next step names.
            ending = "STOPPED at %s: the scenario's steps are spent; the run stands there" % (
                machine.launcher.launched[-1]["state"])
        return ScenarioPlayed(scenario, trace, ending, run, never_reached)
    finally:
        repository.remove()


# --- The trace as text ---------------------------------------------------------

def format_trace(played):
    lines = ["scenario: %s" % played.scenario.name]
    transitions = ["%s → %s%s" % (t.from_state, t.to_state, " (%s)" % t.qualifier if t.qualifier else "")
                   for t in played.trace]
    width_step = len("step %d" % max(len(played.trace), 1))
    width_transition = max([len(s) for s in transitions] or [0])
    width_verdict = max([len(t.verdict) for t in played.trace] or [0])
    for t, transition in zip(played.trace, transitions):
        counters = "   ".join("%s %d of %d" % c for c in t.counters_changed)
        line = "%-*s  %-*s  %-*s  row %-3s %s" % (
            width_step, "step %d" % t.number, width_transition, transition,
            width_verdict, t.verdict, t.row, counters)
        lines.append(line.rstrip())
        if t.pause:
            lines.append("PAUSED at investigate-workflow (%s)" % t.pause)
    lines.append(played.ending)
    return "\n".join(lines)


def main(argv):
    if len(argv) != 2:
        sys.stderr.write("usage: %s <scenario.yaml>\n" % pathlib.Path(argv[0]).name)
        return EXIT_MALFORMED_SCENARIO
    path = pathlib.Path(argv[1])
    try:
        scenario = parse_scenario_text(path.read_text())
        played = play_scenario(scenario)
    except OSError as error:
        sys.stderr.write("%s: %s\n" % (path, error))
        return EXIT_MALFORMED_SCENARIO
    except MalformedScenario as error:
        sys.stderr.write("%s: %s\n" % (path, error))
        return EXIT_MALFORMED_SCENARIO
    print(format_trace(played))
    sys.stdout.flush()
    if played.never_reached is not None:
        sys.stderr.write("%s: %s\n" % (path, played.never_reached))
        return EXIT_MALFORMED_SCENARIO
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
