#!/usr/bin/env python3
"""Run the design-to-main workflow through transition-table nodes and reviewing flows."""

import datetime
import importlib.util
import json
import pathlib
from dataclasses import dataclass
from typing import Optional, Tuple


def _load_sibling_module(file_name, module_name):
    spec = importlib.util.spec_from_file_location(
        module_name, pathlib.Path(__file__).with_name(file_name))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tables = _load_sibling_module("design-to-main-state-tables.py", "design_to_main_state_tables")
run_state_module = _load_sibling_module("design-to-main-run-state.py", "design_to_main_run_state")
git_record_module = _load_sibling_module("design-to-main-git-record.py", "design_to_main_git_record")

RunStateRecord = run_state_module.RunStateRecord
RunCounters = run_state_module.RunCounters
CounterCeilingExceeded = run_state_module.CounterCeilingExceeded
write_counter_charged = run_state_module.write_counter_charged
TopicBranchGitRecord = git_record_module.TopicBranchGitRecord
TopicBranchCutRefused = git_record_module.TopicBranchCutRefused
RefusedBeforeTopicBranchCut = git_record_module.RefusedBeforeTopicBranchCut
compose_state_exit_trailer = git_record_module.compose_state_exit_trailer



@dataclass(frozen=True)
class StateExitRecord:
    """A verdict and its package commit, optional destination, named files, and routing inputs."""
    state: str
    verdict: str
    package_commit: str
    destination: Optional[str] = None
    input_named: Optional[str] = None
    investigation_focus: Optional[str] = None
    coverage_types: Tuple[str, ...] = ()
    refusal_class: Optional[str] = None
    rulings: Tuple[str, ...] = ()
    held_ruling: Optional[str] = None
    # Commit only named files and the run record; unrelated worktree changes do not belong to this state-exit.
    named_files: Tuple[str, ...] = ()
    notes: str = ""

    @property
    def from_state(self):
        """Return the emitting state, or its composite when a sub-state emitted."""
        return tables.COMPOSITE_STATE_OF_SUB_STATE.get(self.state, self.state)


class MalformedStateExitFile(ValueError):
    """An invalid state-exit file, reported with the offending field."""


def state_exit_record_from_json_file(path):
    """Read state-exit.json into a StateExitRecord, validating field names and shapes."""
    path = pathlib.Path(path)
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as error:
        raise MalformedStateExitFile("%s: %s" % (path, error)) from error
    if not isinstance(data, dict):
        raise MalformedStateExitFile("%s: not a JSON object" % path)
    unknown = sorted(set(data) - set(tables.STATE_EXIT_JSON_FIELDS))
    if unknown:
        raise MalformedStateExitFile(
            "%s: fields section 2 does not name: %s" % (path, ", ".join(unknown)))
    missing = [f for f in tables.STATE_EXIT_JSON_FIELDS_REQUIRED if f not in data]
    if missing:
        raise MalformedStateExitFile(
            "%s: required fields missing: %s" % (path, ", ".join(missing)))
    fields = {}
    for json_name, value in data.items():
        record_name = tables.STATE_EXIT_JSON_FIELDS[json_name]
        if json_name == "coverage-type":
            if not isinstance(value, str):
                raise MalformedStateExitFile(
                    "%s: coverage-type is a comma-separated string, not %r" % (path, value))
            value = coverage_types_from_json_field(value)
        elif json_name in ("named-files", "rulings"):
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                raise MalformedStateExitFile(
                    "%s: %s is a list of strings, not %r" % (path, json_name, value))
            value = tuple(value)
        elif not isinstance(value, str):
            raise MalformedStateExitFile(
                "%s: %s is a string, not %r" % (path, json_name, value))
        fields[record_name] = value
    return StateExitRecord(**fields)


def coverage_types_from_json_field(text):
    """Return comma-separated coverage-types as a tuple."""
    return tuple(part.strip() for part in text.split(",") if part.strip())


def coverage_types_as_json_field(coverage_types):
    return ", ".join(coverage_types)


class IllegalStateExit(Exception):
    """A state-exit with no legal transition, routed as a machine error."""


class TransitionTableAmbiguous(Exception):
    """Multiple matching transition rows: a table defect that is never routed."""



@dataclass
class GuardContext:
    run: RunStateRecord
    state_exit: StateExitRecord
    resume_destination: Optional[str] = None


def applicable_acceptance_checks(run, composite_state):
    """Return the applicable acceptance sub-states in execution order."""
    # The contract's user check is entered only on rejection at the revision ceiling, never by advance.
    row = tables.STATE_TABLE_BY_NAME[composite_state]
    if composite_state == tables.CONTRACT_REVIEWING:
        checks = [tables.CONTRACT_ACCEPTANCE_BY_PROGRAM]
        if run.design_approved:
            checks.append(tables.CONTRACT_ACCEPTANCE_BY_AGENT)
        return tuple(checks)
    if composite_state == tables.IMPLEMENTATION_REVIEWING:
        if run.is_agent_instructions(run.implementation_coverage_type):
            return row.sub_states
        return row.sub_states[:1]
    if composite_state == tables.TEST_REVIEWING:
        if run.tests_are_agent_instructions():
            return row.sub_states
        return row.sub_states[:1]
    return row.sub_states


def _from_sub_state(*names):
    return lambda ctx: ctx.state_exit.state in names


def _last_acceptance_check(ctx):
    checks = applicable_acceptance_checks(ctx.run, ctx.state_exit.from_state)
    return bool(checks) and ctx.state_exit.state == checks[-1]


def _earlier_acceptance_check(ctx):
    checks = applicable_acceptance_checks(ctx.run, ctx.state_exit.from_state)
    return ctx.state_exit.state in checks[:-1]


def next_acceptance_check(run, state_exit):
    checks = applicable_acceptance_checks(run, state_exit.from_state)
    return checks[checks.index(state_exit.state) + 1]


def _from_an_acceptance_check_by_agent(ctx):
    state = ctx.state_exit.state
    if state in tables.COMPOSITE_STATE_OF_SUB_STATE:
        return state in tables.ACCEPTANCE_CHECKS_BY_AGENT
    return state in tables.STATES_WITH_ESCALATE_TO_USER


def _writers_counter(ctx):
    return tables.WRITER_COUNTER_FOR_VERDICT[ctx.state_exit.verdict]


def _submit_attempt_number(ctx):
    return ctx.run.submit_retry_count + 1


GUARD_PREDICATES = {
    tables.G_FROM_PROGRAM_CHECK: _from_sub_state(tables.CONTRACT_ACCEPTANCE_BY_PROGRAM),
    tables.G_FIRST_TIME:
        lambda ctx: ctx.run.consecutive_program_check_failure_count == 0,
    tables.G_SECOND_CONSECUTIVE_TIME:
        lambda ctx: ctx.run.consecutive_program_check_failure_count >= 1,
    tables.G_DESIGN_NOT_YET_APPROVED: lambda ctx: not ctx.run.design_approved,
    tables.G_ON_A_CONTRACT_REVISION: lambda ctx: ctx.run.design_approved,
    tables.G_FROM_CONTRACT_ACCEPTANCE_BY_AGENT:
        _from_sub_state(tables.CONTRACT_ACCEPTANCE_BY_AGENT),
    tables.G_FROM_CONTRACT_ACCEPTANCE_BY_AGENT_OR_USER:
        _from_sub_state(tables.CONTRACT_ACCEPTANCE_BY_AGENT, tables.CONTRACT_ACCEPTANCE_BY_USER),
    tables.G_FROM_CONTRACT_ACCEPTANCE_BY_USER:
        _from_sub_state(tables.CONTRACT_ACCEPTANCE_BY_USER),
    tables.G_FROM_DESIGN_ACCEPTANCE_BY_AGENT:
        _from_sub_state(tables.DESIGN_ACCEPTANCE_BY_AGENT),
    tables.G_FROM_DESIGN_ACCEPTANCE_BY_USER:
        _from_sub_state(tables.DESIGN_ACCEPTANCE_BY_USER),
    tables.G_FROM_IMPLEMENTATION_ACCEPTANCE_BY_USER:
        _from_sub_state(tables.IMPLEMENTATION_ACCEPTANCE_BY_USER),
    tables.G_FROM_TEST_DESIGN_ACCEPTANCE_BY_AGENT:
        _from_sub_state(tables.TEST_DESIGN_ACCEPTANCE_BY_AGENT),
    tables.G_FROM_TEST_DESIGN_ACCEPTANCE_BY_USER:
        _from_sub_state(tables.TEST_DESIGN_ACCEPTANCE_BY_USER),
    tables.G_FROM_TEST_ACCEPTANCE_BY_USER:
        _from_sub_state(tables.TEST_ACCEPTANCE_BY_USER),
    tables.G_FROM_AN_ACCEPTANCE_CHECK_BY_AGENT: _from_an_acceptance_check_by_agent,
    tables.G_FROM_THE_LAST_ACCEPTANCE_CHECK: _last_acceptance_check,
    tables.G_FROM_AN_EARLIER_ACCEPTANCE_CHECK: _earlier_acceptance_check,
    tables.G_AGAINST_THE_DESIGN:
        lambda ctx: ctx.state_exit.input_named == tables.INPUT_DESIGN,
    tables.G_AGAINST_THE_DESIGN_CONTRACT:
        lambda ctx: ctx.state_exit.input_named == tables.INPUT_DESIGN_CONTRACT,
    tables.G_AGAINST_THE_TEST_DESIGN:
        lambda ctx: ctx.state_exit.input_named == tables.INPUT_TEST_DESIGN,
    # The shared ceiling row still requires a verdict valid for the emitting writer or reviewer.
    tables.G_A_REJECT_OF_OR_A_FAILED_CHECK_AGAINST_THE_DESIGN_CONTRACT:
        lambda ctx: (
            ctx.state_exit.verdict in tables.STATE_TABLE_BY_NAME[ctx.state_exit.from_state].verdicts
            and (ctx.state_exit.verdict == tables.V_REJECT_CONTRACT
                 or (ctx.state_exit.verdict == tables.V_INPUT_QUICK_CHECK_FAILED
                     and ctx.state_exit.input_named == tables.INPUT_DESIGN_CONTRACT))),
    tables.G_TESTS_NOT_YET_BEGUN: lambda ctx: not ctx.run.tests_begun,
    tables.G_TESTS_BEGUN: lambda ctx: ctx.run.tests_begun,
    tables.G_TEST_WORK_STREAM_READY:
        lambda ctx: ctx.run.work_stream_ready(tables.TEST_WORK_STREAM),
    tables.G_TEST_WORK_STREAM_NOT_READY:
        lambda ctx: not ctx.run.work_stream_ready(tables.TEST_WORK_STREAM),
    tables.G_IMPLEMENTATION_WORK_STREAM_READY:
        lambda ctx: ctx.run.work_stream_ready(tables.IMPLEMENTATION_WORK_STREAM),
    tables.G_IMPLEMENTATION_WORK_STREAM_NOT_READY:
        lambda ctx: not ctx.run.work_stream_ready(tables.IMPLEMENTATION_WORK_STREAM),
    tables.G_COULD_NOT_RUN_FIRST: lambda ctx: ctx.run.consecutive_could_not_run_count == 0,
    tables.G_COULD_NOT_RUN_SECOND: lambda ctx: ctx.run.consecutive_could_not_run_count >= 1,
    # An arbitrator advance stands in for a reviewer; a failed suite or missing entry gives no advance to apply.
    tables.G_ENTERED_FROM_A_REVIEWERS_CEILING:
        lambda ctx: ctx.run.test_suite_arbitrating_entered_from in tables.COMPOSITE_STATE_OF_SUB_STATE,
    tables.G_BEFORE_THE_TEST_DESIGNS_APPROVAL: lambda ctx: not ctx.run.test_design_approved,
    tables.G_AFTER_THE_TEST_DESIGNS_APPROVAL: lambda ctx: ctx.run.test_design_approved,
    tables.G_WRITERS_COUNTER_BELOW_CEILING:
        lambda ctx: ctx.run.counters.below_ceiling(_writers_counter(ctx)),
    tables.G_WRITERS_COUNTER_AT_OR_ABOVE_CEILING:
        lambda ctx: ctx.run.counters.at_ceiling(_writers_counter(ctx)),
    tables.G_FOCUS_NAMED_DESIGN_OR_TEST_DESIGN:
        lambda ctx: ctx.state_exit.investigation_focus in (tables.FOCUS_DESIGN, tables.FOCUS_TEST_DESIGN),
    tables.G_FOCUS_NOT_NAMED:
        lambda ctx: ctx.state_exit.investigation_focus not in (tables.FOCUS_DESIGN, tables.FOCUS_TEST_DESIGN),
    # This guard is evaluated on entry, not on a state-exit.
    tables.G_ENTERED_FOR_THE_THIRD_TIME_IN_THE_DESIGN_VERSION:
        lambda ctx: ctx.run.counters.at_ceiling("arbitrator-rulings"),
    tables.G_RESUME_BELOW_REDESIGNS_CEILING_OR_NOT_TO_DESIGN_WRITING:
        lambda ctx: (ctx.resume_destination != tables.DESIGN_WRITING
                     or ctx.run.counters.below_ceiling("redesigns")),
    tables.G_RESUME_TO_DESIGN_WRITING_AT_REDESIGNS_CEILING:
        lambda ctx: (ctx.resume_destination == tables.DESIGN_WRITING
                     and ctx.run.counters.at_ceiling("redesigns")),
    tables.G_REFUSAL_INFRASTRUCTURE:
        lambda ctx: ctx.state_exit.refusal_class == tables.REFUSAL_INFRASTRUCTURE,
    tables.G_FEWER_THAN_FIVE_ATTEMPTS: lambda ctx: _submit_attempt_number(ctx) < 5,
    tables.G_FIFTH_INFRASTRUCTURE_ATTEMPT_OR_INTEGRATION_OR_SCOPE_REFUSAL:
        lambda ctx: ((ctx.state_exit.refusal_class == tables.REFUSAL_INFRASTRUCTURE
                      and _submit_attempt_number(ctx) >= 5)
                     or ctx.state_exit.refusal_class in (tables.REFUSAL_INTEGRATION,
                                                         tables.REFUSAL_SCOPE)),
    tables.G_REFUSAL_FORM: lambda ctx: ctx.state_exit.refusal_class == tables.REFUSAL_FORM,
}
for _name in tables.COUNTER_NAMES:
    GUARD_PREDICATES[tables.counter_below_ceiling(_name)] = (
        lambda ctx, n=_name: ctx.run.counters.below_ceiling(n))
    GUARD_PREDICATES[tables.counter_at_ceiling(_name)] = (
        lambda ctx, n=_name: ctx.run.counters.at_ceiling(n))
    GUARD_PREDICATES[tables.counter_at_or_above_ceiling(_name)] = (
        lambda ctx, n=_name: ctx.run.counters.at_ceiling(n))


def guards_hold(row, context):
    return all(GUARD_PREDICATES[guard](context) for guard in row.guards)


def refuse_malformed_resume(run, state_exit, resume_destination):
    # Validate before rulings or row lookup so a malformed resume cannot reset counters or alter the pause.
    if state_exit.verdict != tables.V_RESUME:
        return
    from_state = state_exit.from_state
    if (state_exit.held_ruling is not None
            and state_exit.held_ruling not in tables.HELD_RULINGS_A_RESUME_MAY_CARRY):
        raise IllegalStateExit(
            "%r from %s carries %r as its held ruling; a held ruling is one of %s, never "
            "escalate-to-user (section 6.6)" % (
                state_exit.verdict, from_state, state_exit.held_ruling,
                ", ".join(tables.HELD_RULINGS_A_RESUME_MAY_CARRY)))
    if state_exit.destination is not None:
        if (resume_destination not in tables.STATE_TABLE_BY_NAME
                and resume_destination not in tables.COMPOSITE_STATE_OF_SUB_STATE):
            raise IllegalStateExit(
                "%r from %s names %r as its destination, which is no state or sub-state of section 3.1" % (
                    state_exit.verdict, from_state, resume_destination))
        if resume_destination in tables.RESUME_MAY_NOT_NAME:
            raise IllegalStateExit(
                "%r from %s names %r as its destination; a resume may not name %s (section 6.1)" % (
                    state_exit.verdict, from_state, resume_destination,
                    " or ".join(tables.RESUME_MAY_NOT_NAME)))
        if (resume_destination == tables.TEST_SUITE_ARBITRATING
                and run.paused_state != tables.TEST_SUITE_ARBITRATING):
            raise IllegalStateExit(
                "%r from %s names %r as its destination, from an investigation that paused at "
                "%s: the arbitrator rules on the failed suite or the reviewer's ceiling that "
                "entered it before the pause, and there is neither at %s (section 6.5)" % (
                    state_exit.verdict, from_state, resume_destination,
                    run.paused_state, run.paused_state))


def the_one_coverage_type_of_an_implementation(state_exit):
    """Return the implementation's sole coverage-type, raising on multiple values."""
    if len(state_exit.coverage_types) != 1:
        raise IllegalStateExit(
            "%r from %s carries %r as its coverage-type; an implementation has one "
            "(section 2)" % (state_exit.verdict, state_exit.state,
                             coverage_types_as_json_field(state_exit.coverage_types)))
    return state_exit.coverage_types[0]


def refuse_a_write_that_named_no_file(state_exit):
    # An emitted write without an artifact is a machine error, even though other exits may name no files.
    if (state_exit.from_state in tables.WRITING_STATES_INCLUDING_DESIGN_WRITING
            and state_exit.verdict == tables.V_EMITTED
            and not state_exit.named_files):
        raise IllegalStateExit(
            "%r from %s names no files; a write that named no file did not happen "
            "(section 2)" % (state_exit.verdict, state_exit.from_state))


def coverage_types_of_the_test_designs_requirements(test_design_text):
    """Return each requirement's coverage-type in file order."""
    prefix = tables.TEST_DESIGN_COVERAGE_TYPE_LINE_PREFIX
    return tuple(
        line.strip()[len(prefix):].strip()
        for line in test_design_text.splitlines()
        if line.strip().startswith(prefix))


def the_set_of_coverage_types_the_test_design_asks_for(requirement_coverage_types):
    present = {t for t in requirement_coverage_types
               if t != tables.COVERAGE_TYPE_NO_TESTS}
    if not present:
        return (tables.COVERAGE_TYPE_NO_TESTS,)
    return tuple(sorted(present))


def refuse_a_test_write_that_disagrees_with_the_test_design(state_exit, test_design_text):
    # These types decide whether user acceptance is required; trusting an unsupported type could skip that check.
    if test_design_text is None:
        return
    requirements = coverage_types_of_the_test_designs_requirements(test_design_text)
    if not requirements:
        return
    asked_for = the_set_of_coverage_types_the_test_design_asks_for(requirements)
    emitted = tuple(sorted(set(state_exit.coverage_types)))
    if emitted != asked_for:
        raise IllegalStateExit(
            "%r from %s carries %r as its coverage-type; the test-design's requirements "
            "ask for %s (section 6.4)" % (
                state_exit.verdict, state_exit.from_state,
                coverage_types_as_json_field(state_exit.coverage_types),
                coverage_types_as_json_field(asked_for)))


def find_legal_transition_row(run, state_exit, resume_destination=None):
    """Return the matching transition row; raise IllegalStateExit if none matches."""
    context = GuardContext(run, state_exit, resume_destination)
    from_state = state_exit.from_state
    refuse_malformed_resume(run, state_exit, resume_destination)
    refuse_a_write_that_named_no_file(state_exit)
    if (from_state == tables.IMPLEMENTATION_WRITING and state_exit.verdict == tables.V_EMITTED
            and state_exit.coverage_types):
        the_one_coverage_type_of_an_implementation(state_exit)
    matches = [
        row for row in tables.TRANSITION_TABLE
        if from_state in row.from_states
        and state_exit.verdict in row.verdicts
        and guards_hold(row, context)
    ]
    if not matches:
        raise IllegalStateExit(
            "no row of section 3.2 allows %r from %s (emitted by %s)" % (
                state_exit.verdict, from_state, state_exit.state))
    if len(matches) > 1:
        raise TransitionTableAmbiguous(
            "rows %s all match %r from %s" % (
                [r.row for r in matches], state_exit.verdict, from_state))
    row = matches[0]
    # A resume destination is user input to the guard; a stopping row may override it with ended.
    if state_exit.destination is not None and state_exit.verdict != tables.V_RESUME:
        derived = derived_destination(row, context)
        if derived is not None and state_exit.destination != derived:
            raise IllegalStateExit(
                "row %s pairs %r from %s with %s, not %s" % (
                    row.row, state_exit.verdict, from_state, derived,
                    state_exit.destination))
    return row


def derived_destination(row, context):
    """Return the row's fixed destination, or None when the machine must derive it."""
    if row.to_state == tables.TO_RETRY_SAME_STATE:
        return context.state_exit.from_state
    if row.to_state in (tables.TO_HOLD_READY_FOR_TEST_SUITE,
                        tables.TO_BOTH_WORK_STREAMS_RE_ENTER,
                        tables.TO_BOTH_WRITERS_FRESH):
        return None
    if row.to_state == tables.TO_RESUME_DESTINATION:
        return context.resume_destination
    if row.to_state == tables.TO_THE_NEXT_ACCEPTANCE_CHECK:
        return next_acceptance_check(context.run, context.state_exit)
    if row.to_state == tables.TO_THE_WRITER_THE_VERDICT_NAMES:
        return tables.WRITER_STATE_FOR_VERDICT[context.state_exit.verdict]
    if row.to_state == tables.TO_WHEREVER_THAT_REVIEWING_STATES_ADVANCE_GOES:
        advance = the_reviewers_advance_the_arbitrator_stands_in_for(context.run, context.state_exit)
        return derived_destination(find_legal_transition_row(context.run, advance),
                                   GuardContext(context.run, advance))
    return row.to_state


def the_reviewers_advance_the_arbitrator_stands_in_for(run, state_exit):
    """Return the reviewer's advance carrying the arbitrator's package commit."""
    return StateExitRecord(state=run.test_suite_arbitrating_entered_from,
                           verdict=tables.V_ADVANCE,
                           package_commit=state_exit.package_commit)



class ScriptedStateExitLauncherExhausted(RuntimeError):
    """The script ran out; pause the run at its current position."""


class ScriptedStateExitLauncher:
    """Return scripted state-exits in order, using the current package commit unless overridden."""

    def __init__(self, script):
        self.script = list(script)
        self.launched = []
        self.exhausted = False

    def launch(self, state_package):
        self.launched.append(state_package)
        if not self.script:
            self.exhausted = True
            raise ScriptedStateExitLauncherExhausted(
                "the script ran out at %s" % state_package["state"])
        state, verdict, fields = self.script.pop(0)
        if state != state_package["state"]:
            raise AssertionError(
                "the script expected to be launched for %s; the machine launched %s" % (
                    state, state_package["state"]))
        fields = dict(fields)
        package_commit = fields.pop("package_commit", state_package["package-commit"])
        return StateExitRecord(state=state, verdict=verdict,
                               package_commit=package_commit, **fields)



class StateWorkNode:
    """Assemble, launch, and route one state's work, returning the next position."""

    def __init__(self, machine, state):
        self.machine = machine
        self.state = state

    def prep(self, run):
        return self.machine.assemble_state_package(run, self.state)

    def exec(self, state_package):
        return self.machine.launcher.launch(state_package)

    def post(self, run, state_package, state_exit):
        if state_exit.package_commit != state_package["package-commit"]:
            self.machine.discard_stale_state_exit(run, state_package, state_exit)
            return None
        return self.machine.route_state_exit(run, state_exit)

    def run(self, run):
        while True:
            state_package = self.prep(run)
            state_exit = self.exec(state_package)
            next_position = self.post(run, state_package, state_exit)
            if next_position is not None:
                return next_position


class ReviewingStateFlow:
    """Run acceptance-checks until a sub-state exits the composite reviewing state."""

    def __init__(self, machine, composite_state, start_sub_state=None):
        self.machine = machine
        self.composite_state = composite_state
        self.start_sub_state = start_sub_state

    def run(self, run):
        position = self.start_sub_state or applicable_acceptance_checks(run, self.composite_state)[0]
        while tables.COMPOSITE_STATE_OF_SUB_STATE.get(position) == self.composite_state:
            position = StateWorkNode(self.machine, position).run(run)
        return position


class RunEnded(Exception):
    pass


class DesignToMainStateMachineFlow:
    """Route and commit each state-exit of a component's run through completion."""

    def __init__(self, git_record, launcher, today=None):
        self.git_record = git_record
        self.launcher = launcher
        self.today = today or (lambda: datetime.date.today().isoformat())
        self.routed = []
        self.discarded = []
        self.machine_errors = []
        self.held_rulings_applied = []
        self.reviewers_advances_applied = []


    def start(self, component):
        """Start the run after verifying origin/main is available for the topic branch cut."""
        self.git_record.require_topic_branch_start_point()
        return RunStateRecord(component)

    def recover(self):
        """Recover the committed run, preserving investigation edits and discarding other unfinished work."""
        # Read the committed run before discarding: only its branch-cut flag establishes ownership of the checkout.
        text = self.git_record.run_state_text_at_last_commit()
        if text is None:
            raise RefusedBeforeTopicBranchCut(
                "refused to recover: no run-state.json is committed at HEAD (%s on %r), "
                "so there is no state-exit to recover from; the checkout is as it was" % (
                    self.git_record.head_commit(), self.git_record.current_branch()))
        run = RunStateRecord.from_dict(json.loads(text))
        # An ended run has no state to re-run, regardless of its outcome field.
        if run.current_state not in (tables.ENDED, tables.INVESTIGATE_WORKFLOW):
            self.git_record.discard_all_uncommitted_work_for_recovery(run)
        return run


    def node_for(self, position):
        composite = tables.COMPOSITE_STATE_OF_SUB_STATE.get(position)
        if composite is not None:
            return ReviewingStateFlow(self, composite, start_sub_state=position)
        if tables.STATE_TABLE_BY_NAME[position].work == "composite":
            return ReviewingStateFlow(self, position)
        return StateWorkNode(self, position)

    def step(self, run):
        if run.current_state == tables.ENDED:
            raise RunEnded(run.outcome)
        self.node_for(run.current_state).run(run)

    def run_until_ended(self, run, max_steps=200):
        """Return the run's outcome; propagate refusals before the topic branch is cut."""
        steps = 0
        while run.current_state != tables.ENDED:
            self.step(run)
            steps += 1
            if steps > max_steps:
                raise RuntimeError("the run did not end within %d steps" % max_steps)
        return run.outcome


    def assemble_state_package(self, run, state):
        composite = tables.COMPOSITE_STATE_OF_SUB_STATE.get(state, state)
        row = tables.STATE_TABLE_BY_NAME[composite]
        state_package = {
            "state": state,
            "composite-state": composite,
            "component": run.component,
            # Before implementation, the design and contract paths still point to the issue's GHI-MD directory.
            "standard-package": (self.git_record.design_path,
                                 tables.contract_path_beside_design(self.git_record.design_path),
                                 str(self.git_record.user_rulings_path)),
            "beyond-the-standard-package": row.package_beyond_standard,
            "package-commit": self.git_record.head_commit(),
            "design-version": run.design_version,
            "evidence-directory": self.git_record.evidence_directory_for_the_next_instance(state),
        }
        if state == tables.INVESTIGATE_WORKFLOW:
            state_package["investigation-report"] = (
                self.git_record.investigation_report_path_for_the_next_instance())
        elif state == tables.DESIGN_WRITING and run.previous_state == tables.INVESTIGATE_WORKFLOW:
            state_package["investigation-report"] = (
                self.git_record.investigation_report_path_of_the_latest_instance())
        return state_package


    def discard_stale_state_exit(self, run, state_package, state_exit):
        self.discarded.append((state_package, state_exit))

    def route_state_exit(self, run, state_exit):
        """Validate, apply, and commit a state-exit; return the next position."""
        resume_destination = None
        counters_before_rulings = run.counters.as_dict()
        rulings_refused = False
        named_files_not_there = ()
        try:
            # Validate named files before applying any row or ruling: refusal must have no partial effects.
            named_files_not_there = tuple(
                self.git_record.named_files_that_are_not_there(state_exit.named_files))
            if named_files_not_there:
                raise IllegalStateExit(
                    "%r from %s names files that are not there: %s (section 9)" % (
                        state_exit.verdict, state_exit.state, ", ".join(named_files_not_there)))
            # Coverage checks read the worktree, which the transition-table lookup does not have.
            if (state_exit.from_state == tables.TEST_WRITING
                    and state_exit.verdict == tables.V_EMITTED):
                refuse_a_test_write_that_disagrees_with_the_test_design(
                    state_exit, self.git_record.test_design_text())
            if state_exit.verdict == tables.V_RESUME:
                resume_destination = self.resolve_resume_destination(run, state_exit)
            # Apply reset before guards read counter ceilings; defer disk writes until the state-exit is accepted.
            self.apply_rulings_to_the_run(run, state_exit)
            row = find_legal_transition_row(run, state_exit, resume_destination)
            next_position, write_number = self.apply_transition_row(
                run, row, state_exit, resume_destination)
        except (IllegalStateExit, CounterCeilingExceeded) as error:
            if not run.topic_branch_cut:
                # Before this run cuts its topic branch, the checkout belongs to the invoker and must not be discarded or committed.
                raise RefusedBeforeTopicBranchCut(
                    "%r from %s is refused before the topic branch is cut: %s; "
                    "the run does not start and the checkout is as it was" % (
                        state_exit.verdict, state_exit.state, error)) from error
            row = None
            write_number = None
            # Refuse the whole state-exit, including its rulings, so an invalid resume cannot reset counters.
            run.counters = RunCounters(counters_before_rulings)
            rulings_refused = True
            next_position = self.route_machine_error(run, state_exit, error)
        run.previous_state = state_exit.from_state
        # Read edits against the investigation being left before entry can replace its opening commit.
        files_beyond_the_named = self.paths_the_user_changed_in_the_investigation(
            run, state_exit, row)
        # Apply entry rules before commit so persisted run-state describes the state actually entered.
        self.enter(run, next_position)
        if self.investigation_opens_with(run):
            # Store the parent of the opening commit: a commit cannot contain its own SHA.
            run.investigation_opened_at_commit = self.git_record.head_commit()
        commit = self.commit_state_exit(
            run, state_exit, write_number, record_rulings=not rulings_refused,
            files_beyond_the_named=files_beyond_the_named,
            named_files_not_there=named_files_not_there)
        self.routed.append((row, state_exit, commit))
        # Commit named partial work before discarding unclaimed changes.
        # An investigation that stays paused retains the user's worktree edits.
        if not (state_exit.from_state == tables.INVESTIGATE_WORKFLOW
                and run.current_state == tables.INVESTIGATE_WORKFLOW):
            self.git_record.discard_every_change_the_commit_did_not_carry(run)
        return run.current_state

    def mark_investigation_opening(self, run):
        # Mark on opening, not on from-state: a resume can itself open a new investigation.
        run.investigation_opened_at_commit = None

    def investigation_opens_with(self, run):
        """Return whether the current state-exit opened the investigation."""
        return (run.current_state == tables.INVESTIGATE_WORKFLOW
                and run.investigation_opened_at_commit is None)

    def route_machine_error(self, run, state_exit, error):
        """Record an illegal state-exit and open an investigation, preserving an existing pause."""
        self.machine_errors.append((state_exit, error))
        run.machine_error = str(error)
        if state_exit.from_state != tables.INVESTIGATE_WORKFLOW:
            self.mark_investigation_opening(run)
            run.paused_state = state_exit.from_state
            run.investigation_focus = tables.FOCUS_UNKNOWN
            run.investigation_opened_by = "%s from %s: %s" % (
                state_exit.verdict, state_exit.state, error)
            run.investigation_opened_by_row = None
            run.investigation_held_resume_destination = None
        return tables.INVESTIGATE_WORKFLOW

    def apply_rulings_to_the_run(self, run, state_exit):
        for ruling in state_exit.rulings:
            if ruling == "reset":
                run.counters.reset_by_the_user()

    def write_rulings_to_the_record(self, run, state_exit):
        for ruling in state_exit.rulings:
            self.git_record.append_user_ruling(run, ruling, self.today())

    def paths_the_user_changed_in_the_investigation(self, run, state_exit, row):
        """Return user-changed paths for an accepted resume to commit, excluding the record directory."""
        # An accepted resume must commit user edits before another investigation can discard them.
        if (row is None or state_exit.verdict != tables.V_RESUME
                or not run.investigation_opened_at_commit):
            return ()
        return tuple(self.git_record.paths_changed_since(
            self.commit_the_investigation_opened_with(run)))

    def commit_the_investigation_opened_with(self, run):
        """Return the opening commit used as the resume diff baseline."""
        # Opening commits can contain partial work; diffing from their parent would mistake that work for later user edits.
        return self.git_record.first_commit_after(run.investigation_opened_at_commit)

    def commit_state_exit(self, run, state_exit, write_number, record_rulings=True,
                          files_beyond_the_named=(), named_files_not_there=()):
        # Guard before any file write so a refusal leaves no rulings or run-state behind.
        self.git_record.require_topic_branch_cut_for_run(run, "write and commit the state-exit")
        if record_rulings:
            self.write_rulings_to_the_record(run, state_exit)
        run.write_to(self.git_record.absolute(self.git_record.run_state_path))
        trailer = compose_state_exit_trailer(
            state_exit.state, state_exit.verdict, state_exit.package_commit,
            run.counters.as_dict(), write_number)
        subject = "%s: %s %s" % (run.component, state_exit.state, state_exit.verdict)
        # Preserve existing named files in the machine-error commit; missing files remain the reported error.
        named = tuple(f for f in state_exit.named_files if f not in named_files_not_there)
        named += tuple(f for f in files_beyond_the_named if f not in named)
        return self.git_record.commit_state_exit(run, subject, trailer, named)


    def enter(self, run, position):
        """Apply entry counters and rules before the state-exit is committed."""
        if position == tables.DESIGN_WRITING and run.previous_state == tables.INVESTIGATE_WORKFLOW:
            run.counters.increment("redesigns")
            run.start_new_design_version()
        if position == tables.TEST_SUITE_ARBITRATING:
            third_entry = tables.TRANSITION_TABLE_BY_ROW[tables.ROW_THE_ARBITRATORS_THIRD_ENTRY]
            if guards_hold(third_entry, GuardContext(run, None)):
                self.mark_investigation_opening(run)
                run.paused_state = tables.TEST_SUITE_ARBITRATING
                run.investigation_focus = third_entry.investigation_focus
                run.investigation_opened_by = (
                    "the arbitrator's third entry in design version %d (row %s)" % (
                        run.design_version, third_entry.row))
                run.investigation_opened_by_row = third_entry.row
                run.investigation_held_resume_destination = None
                run.previous_state = tables.TEST_SUITE_ARBITRATING
                run.current_state = third_entry.to_state
                return
            run.counters.increment("arbitrator-rulings")
        # A paused reviewing stream must resume at its review, not restart the preceding writing state.
        composite = tables.COMPOSITE_STATE_OF_SUB_STATE.get(position, position)
        work_stream = tables.STATE_TABLE_BY_NAME[composite].work_stream
        if work_stream:
            run.set_work_stream_position(work_stream, composite)
        run.current_state = position


    def enter_writing_state(self, run, state, entry_reason):
        run.writing_state_entry_reason[state] = entry_reason
        work_stream = tables.STATE_TABLE_BY_NAME[state].work_stream
        if work_stream:
            run.set_work_stream_position(work_stream, state)

    def open_investigation(self, run, row, state_exit):
        self.mark_investigation_opening(run)
        run.paused_state = state_exit.from_state
        run.investigation_focus = row.investigation_focus or state_exit.investigation_focus
        run.investigation_opened_by = "%s from %s (row %s)" % (
            state_exit.verdict, state_exit.state, row.row)
        run.investigation_opened_by_row = row.row
        # Hold the redesign destination through investigation so a plain resume does not return to the contract check.
        run.investigation_held_resume_destination = (
            tables.DESIGN_WRITING
            if row.row == tables.ROW_REDESIGN_ORDERED_AT_THE_CONTRACT_CHECK else None)

    def resolve_resume_destination(self, run, state_exit):
        refuse_malformed_resume(run, state_exit, state_exit.destination)
        if state_exit.destination:
            return state_exit.destination
        if (run.investigation_opened_by_row == tables.ROW_THE_ARBITRATORS_THIRD_ENTRY
                and state_exit.held_ruling is not None):
            return tables.TO_APPLY_THE_HELD_RULING
        if run.investigation_held_resume_destination:
            return run.investigation_held_resume_destination
        derived = None
        if run.investigation_opened_at_commit:
            derived = self.git_record.earliest_state_downstream_of_changes(
                self.commit_the_investigation_opened_with(run))
        return derived or run.paused_state

    def apply_the_held_ruling(self, run, state_exit):
        """Route the held arbitrator ruling without re-entering the arbitrator; return the next position."""
        held = StateExitRecord(state=tables.TEST_SUITE_ARBITRATING,
                               verdict=state_exit.held_ruling,
                               package_commit=state_exit.package_commit,
                               input_named=state_exit.input_named,
                               investigation_focus=state_exit.investigation_focus)
        row = find_legal_transition_row(run, held)
        next_position, _ = self.apply_transition_row(run, row, held, None)
        self.held_rulings_applied.append((row, held))
        return next_position

    def apply_the_reviewers_advance(self, run, state_exit):
        """Apply the reviewer's advance, including side effects, and return its destination."""
        advance = the_reviewers_advance_the_arbitrator_stands_in_for(run, state_exit)
        row = find_legal_transition_row(run, advance)
        next_position, _ = self.apply_transition_row(run, row, advance, None)
        self.reviewers_advances_applied.append((row, advance))
        return next_position

    def apply_transition_row(self, run, row, state_exit, resume_destination):
        """Apply row side effects and return (next_position, write_number)."""
        from_state = state_exit.from_state
        verdict = state_exit.verdict
        next_position = row.to_state
        write_number = None

        # The Write trailer follows the charged counter; writes_emitted_per_version also counts forced writes.
        if row.counter in tables.COUNTED_WRITING_STATES.values():
            run.writes_emitted_per_version[from_state] = (
                run.writes_emitted_per_version.get(from_state, 0) + 1)
            entry_reason = run.writing_state_entry_reason.get(
                from_state, tables.ENTRY_REASON_FIRST_WRITE)
            charged = write_counter_charged(from_state, entry_reason)
            if charged:
                write_number = run.counters.increment(
                    charged,
                    forced_by_the_users_discuss=(entry_reason == tables.ENTRY_REASON_DISCUSS_BY_USER))
            else:
                write_number = tables.WRITE_TRAILER_FORCED
        elif row.counter:
            run.counters.increment(row.counter)

        if state_exit.coverage_types:
            if from_state == tables.IMPLEMENTATION_WRITING:
                run.implementation_coverage_type = the_one_coverage_type_of_an_implementation(
                    state_exit)
            elif from_state == tables.TEST_WRITING:
                run.tests_coverage_types = tuple(state_exit.coverage_types)

        if state_exit.state == tables.CONTRACT_ACCEPTANCE_BY_PROGRAM:
            if verdict == tables.V_REJECT_CONTRACT:
                run.consecutive_program_check_failure_count += 1
            else:
                run.consecutive_program_check_failure_count = 0

        if from_state == tables.TEST_SUITE_EXECUTING:
            if row.to_state == tables.TO_RETRY_SAME_STATE:
                run.consecutive_could_not_run_count += 1
            else:
                run.consecutive_could_not_run_count = 0
        if from_state == tables.SUBMIT_TO_PR_GATE:
            if row.to_state == tables.TO_RETRY_SAME_STATE:
                run.submit_retry_count += 1
            else:
                run.submit_retry_count = 0

        # Set the run's branch-cut flag only after cutting succeeds; branch names alone cannot prove run ownership.
        if row.row == tables.ROW_TOPIC_BRANCH_CUT:
            self.git_record.cut_topic_branch()
            run.topic_branch_cut = True

        if row.row == tables.ROW_DESIGN_APPROVED:
            run.design_approved = True
            self.enter_writing_state(run, tables.IMPLEMENTATION_WRITING, self.reason_for_advance(
                run, tables.IMPLEMENTATION_WRITING, tables.ENTRY_REASON_REDESIGN))
        if row.row == tables.ROW_TEST_DESIGN_APPROVED:
            run.test_design_approved = True
            self.enter_writing_state(run, tables.TEST_WRITING, self.reason_for_advance(
                run, tables.TEST_WRITING, self.upstream_reason_for_test_writing(run)))
        if row.row == tables.ROW_TESTS_BEGIN:
            run.tests_begun = True
            run.set_work_stream_position(tables.IMPLEMENTATION_WORK_STREAM, tables.READY_FOR_TEST_SUITE)
            self.enter_writing_state(run, tables.TEST_DESIGN_WRITING, tables.ENTRY_REASON_FIRST_WRITE)
        if row.row == tables.ROW_IMPLEMENTATION_TO_TEST_SUITE:
            run.set_work_stream_position(tables.IMPLEMENTATION_WORK_STREAM, tables.READY_FOR_TEST_SUITE)
        if row.row == tables.ROW_TESTS_TO_TEST_SUITE:
            run.set_work_stream_position(tables.TEST_WORK_STREAM, tables.READY_FOR_TEST_SUITE)
        if row.to_state == tables.TO_HOLD_READY_FOR_TEST_SUITE:
            held = tables.STATE_TABLE_BY_NAME[from_state].work_stream
            other = (tables.TEST_WORK_STREAM if held == tables.IMPLEMENTATION_WORK_STREAM
                     else tables.IMPLEMENTATION_WORK_STREAM)
            run.set_work_stream_position(held, tables.READY_FOR_TEST_SUITE)
            next_position = run.work_stream_position(other)
            if next_position is None:
                raise IllegalStateExit(
                    "%s holds at ready-for-test-suite but the %s has no position" % (held, other))
        if row.to_state == tables.TO_BOTH_WORK_STREAMS_RE_ENTER:
            self.enter_writing_state(run, tables.IMPLEMENTATION_WRITING,
                                     tables.ENTRY_REASON_CONTRACT_REVISION)
            if run.tests_begun:
                self.enter_writing_state(run, tables.TEST_DESIGN_WRITING,
                                         tables.ENTRY_REASON_CONTRACT_REVISION)
            next_position = tables.IMPLEMENTATION_WRITING
        if row.to_state == tables.TO_BOTH_WRITERS_FRESH:
            self.enter_writing_state(run, tables.IMPLEMENTATION_WRITING,
                                     tables.ENTRY_REASON_ARBITRATOR_RULING)
            self.enter_writing_state(run, tables.TEST_WRITING,
                                     tables.ENTRY_REASON_ARBITRATOR_RULING)
            next_position = tables.IMPLEMENTATION_WRITING
        if row.to_state == tables.TO_RETRY_SAME_STATE:
            next_position = from_state
        if row.to_state == tables.TO_THE_NEXT_ACCEPTANCE_CHECK:
            next_position = next_acceptance_check(run, state_exit)
        if row.to_state == tables.TO_THE_WRITER_THE_VERDICT_NAMES:
            next_position = tables.WRITER_STATE_FOR_VERDICT[verdict]
        if row.to_state == tables.TO_WHEREVER_THAT_REVIEWING_STATES_ADVANCE_GOES:
            next_position = self.apply_the_reviewers_advance(run, state_exit)

        if (next_position in (tables.IMPLEMENTATION_WRITING, tables.TEST_WRITING)
                and verdict != tables.V_ADVANCE):
            if verdict == tables.V_DISCUSS:
                reason = tables.ENTRY_REASON_DISCUSS_BY_USER
            elif from_state == tables.TEST_SUITE_ARBITRATING:
                reason = tables.ENTRY_REASON_ARBITRATOR_RULING
            else:
                reason = tables.ENTRY_REASON_REJECT_FROM_REVIEW
            self.enter_writing_state(run, next_position, reason)
        if row.to_state == tables.TEST_DESIGN_WRITING and row.row != tables.ROW_TESTS_BEGIN:
            reason = (tables.ENTRY_REASON_TEST_DESIGN_CORRECTION
                      if row.counter == "test-design-corrections"
                      else tables.ENTRY_REASON_REJECT_FROM_REVIEW)
            self.enter_writing_state(run, tables.TEST_DESIGN_WRITING, reason)
        if row.to_state == tables.INVESTIGATE_WORKFLOW:
            self.open_investigation(run, row, state_exit)
        if row.to_state == tables.ENDED:
            run.outcome = row.outcome
        if row.to_state == tables.TO_RESUME_DESTINATION:
            # Reset before applying a held ruling so every agent gets a fresh per-version budget after user intervention.
            run.counters.zero_the_six_per_version_counters()
            if resume_destination == tables.TO_APPLY_THE_HELD_RULING:
                next_position = self.apply_the_held_ruling(run, state_exit)
            else:
                next_position = resume_destination
                self.position_work_streams_for_resume(run, next_position, state_exit)

        # A resume must retain the arbitrator's original entry cause: its advance still refers to that suite or reviewer.
        if (next_position == tables.TEST_SUITE_ARBITRATING
                and state_exit.verdict != tables.V_RESUME):
            run.test_suite_arbitrating_entered_from = state_exit.state

        return next_position, write_number

    def upstream_reason_for_test_writing(self, run):
        # A test-design rewrite spends that upstream document's budget unless a still earlier document caused it.
        reason = run.writing_state_entry_reason.get(tables.TEST_DESIGN_WRITING)
        if reason in (tables.ENTRY_REASON_CONTRACT_REVISION, tables.ENTRY_REASON_REDESIGN,
                      tables.ENTRY_REASON_USER_NAMED_DESTINATION):
            return reason
        return tables.ENTRY_REASON_TEST_DESIGN_CORRECTION

    def reason_for_advance(self, run, writing_state, reason_if_written_before):
        if run.writes_emitted_per_version.get(writing_state, 0) == 0:
            return tables.ENTRY_REASON_FIRST_WRITE
        return reason_if_written_before

    def position_work_streams_for_resume(self, run, destination, state_exit):
        composite = tables.COMPOSITE_STATE_OF_SUB_STATE.get(destination, destination)
        work_stream = tables.STATE_TABLE_BY_NAME[composite].work_stream
        if work_stream:
            run.set_work_stream_position(work_stream, composite)
        if composite in tables.WRITING_STATES and state_exit.destination:
            run.writing_state_entry_reason[composite] = tables.ENTRY_REASON_USER_NAMED_DESTINATION
