#!/usr/bin/env python3
"""The design-to-main state machine's core (section 1 of the design: the
program that runs the workflow, holding no judgement).

Shape, borrowed from PocketFlow's node and flow pages without the
dependency (section 11): a state is a node with prep (assemble the
state-package), exec (launch the work) and post (route on the action word
the work returned); a reviewing state is a flow that acts as a node,
running its sub-states in order; the machine is the flow that runs the
run. PocketFlow wires successors with `node - "action" >> node`; here the
wiring is the transition table of section 3.2, read as data from
design-to-main-state-tables.py, so a row of the design is a row of the code.

This slice launches no agent and pushes nothing: the launcher is a stub
that returns scripted state-exits (ScriptedStateExitLauncher), and the
git record commits on the topic branch of whatever repository it is given.

Run the tests: scripts/design-to-main/tests/*-test.py, each directly.
"""

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
CounterCeilingExceeded = run_state_module.CounterCeilingExceeded
write_counter_charged = run_state_module.write_counter_charged
TopicBranchGitRecord = git_record_module.TopicBranchGitRecord
TopicBranchCutRefused = git_record_module.TopicBranchCutRefused
RefusedBeforeTopicBranchCut = git_record_module.RefusedBeforeTopicBranchCut
compose_state_exit_trailer = git_record_module.compose_state_exit_trailer


# --- The state-exit (section 2) --------------------------------------------

@dataclass(frozen=True)
class StateExitRecord:
    """What a state's work emits and the machine routes on: a verdict, a
    destination, and the commit of the state-package it was built from.

    `state` is the state or sub-state that emitted it. `destination` is
    optional here: the machine derives the destination from the row and,
    when the work names one, checks that it is the row's (see the build
    report on rows whose destination depends on the machine's own state).
    The other fields carry what a guard of section 3.2 reads off the
    state-exit: the input an input-quick-check-failed names, the
    investigation-focus an escalate-to-user names, the coverage-type an
    emitted write carries, the class of a gatekeeper-refusal, and any user
    rulings given in a dialog (`reset` among them).
    """
    state: str
    verdict: str
    package_commit: str
    destination: Optional[str] = None
    input_named: Optional[str] = None
    investigation_focus: Optional[str] = None
    coverage_type: Optional[str] = None
    refusal_class: Optional[str] = None
    rulings: Tuple[str, ...] = ()
    notes: str = ""

    @property
    def from_state(self):
        """The state of section 3.1 this state-exit leaves: the composite
        state when a sub-state emitted it."""
        return tables.COMPOSITE_STATE_OF_SUB_STATE.get(self.state, self.state)


class IllegalStateExit(Exception):
    """No row of section 3.2 allows this state-exit from this state: a
    machine error (section 3.2), routed to investigate-workflow."""


class TransitionTableAmbiguous(Exception):
    """More than one row matched: a defect in the table, never routed."""


# --- The legal-transition check (section 3.2) --------------------------------

@dataclass
class GuardContext:
    run: RunStateRecord
    state_exit: StateExitRecord
    resume_destination: Optional[str] = None


def applicable_acceptance_checks(run, composite_state):
    """The sub-states a reviewing state runs, in order, for this run
    (section 3.1): the user's check of an implementation or of tests only
    when they are agent-instructions; the contract's agent check only on a
    contract-revision, and its user check only at the ceiling."""
    row = tables.STATE_TABLE_BY_NAME[composite_state]
    if composite_state == tables.CONTRACT_REVIEWING:
        checks = [tables.CONTRACT_ACCEPTANCE_BY_PROGRAM]
        if run.design_approved:
            checks.append(tables.CONTRACT_ACCEPTANCE_BY_AGENT)
            if run.counters.at_ceiling("contract-revisions"):
                checks.append(tables.CONTRACT_ACCEPTANCE_BY_USER)
        return tuple(checks)
    if composite_state == tables.IMPLEMENTATION_REVIEWING:
        if run.is_agent_instructions(run.implementation_coverage_type):
            return row.sub_states
        return row.sub_states[:1]
    if composite_state == tables.TEST_REVIEWING:
        if run.is_agent_instructions(run.tests_coverage_type):
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
        lambda ctx: ctx.run.consecutive_contract_program_check_failures == 0,
    tables.G_SECOND_CONSECUTIVE_TIME:
        lambda ctx: ctx.run.consecutive_contract_program_check_failures >= 1,
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
    tables.G_AGAINST_THE_COMPONENT_CONTRACT:
        lambda ctx: ctx.state_exit.input_named == tables.INPUT_COMPONENT_CONTRACT,
    tables.G_AGAINST_THE_TEST_DESIGN:
        lambda ctx: ctx.state_exit.input_named == tables.INPUT_TEST_DESIGN,
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
    tables.G_WRITERS_COUNTER_BELOW_CEILING:
        lambda ctx: ctx.run.counters.below_ceiling(_writers_counter(ctx)),
    tables.G_WRITERS_COUNTER_AT_CEILING:
        lambda ctx: ctx.run.counters.at_ceiling(_writers_counter(ctx)),
    tables.G_FOCUS_NAMED_DESIGN_OR_TEST_DESIGN:
        lambda ctx: ctx.state_exit.investigation_focus in (tables.FOCUS_DESIGN, tables.FOCUS_TEST_DESIGN),
    tables.G_FOCUS_NOT_NAMED:
        lambda ctx: ctx.state_exit.investigation_focus not in (tables.FOCUS_DESIGN, tables.FOCUS_TEST_DESIGN),
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


def guards_hold(row, context):
    return all(GUARD_PREDICATES[guard](context) for guard in row.guards)


def find_legal_transition_row(run, state_exit, resume_destination=None):
    """Given a state and a state-exit, the row of section 3.2 that allows
    it; IllegalStateExit when none does."""
    context = GuardContext(run, state_exit, resume_destination)
    from_state = state_exit.from_state
    # On `resume` a destination the user typed in the dialog is checked
    # before any row is looked up (a derived one always comes from the
    # tables): one that names no state or sub-state is a machine error
    # like any other illegal state-exit (section 3.2, "any other
    # state-exit"). Row 70's guard holds for any string that is not
    # design-writing, and a row applied to a name the tables do not know
    # would escape the machine as a KeyError instead of being routed to
    # investigate-workflow.
    if (state_exit.verdict == tables.V_RESUME
            and state_exit.destination is not None
            and resume_destination not in tables.STATE_TABLE_BY_NAME
            and resume_destination not in tables.COMPOSITE_STATE_OF_SUB_STATE):
        raise IllegalStateExit(
            "%r from %s names %r as its destination, which is no state or sub-state of section 3.1" % (
                state_exit.verdict, from_state, resume_destination))
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
    # On `resume` the destination is the user's input to the guard, not a
    # claim about the row: row 71 overrides it with `ended`.
    if state_exit.destination is not None and state_exit.verdict != tables.V_RESUME:
        derived = derived_destination(row, context)
        if derived is not None and state_exit.destination != derived:
            raise IllegalStateExit(
                "row %s pairs %r from %s with %s, not %s" % (
                    row.row, state_exit.verdict, from_state, derived,
                    state_exit.destination))
    return row


def derived_destination(row, context):
    """The destination a row names, or None where the row's destination is
    the machine's to work out (a hold, a resume, both work-streams)."""
    if row.to_state == tables.TO_RETRY_SAME_STATE:
        return context.state_exit.from_state
    if row.to_state in (tables.TO_HOLD_READY_FOR_TEST_SUITE,
                        tables.TO_BOTH_WORK_STREAMS_RE_ENTER):
        return None
    if row.to_state == tables.TO_RESUME_DESTINATION:
        return context.resume_destination
    return row.to_state


# --- The launcher stub -------------------------------------------------------

class ScriptedStateExitLauncherExhausted(RuntimeError):
    """The script ran out: the run pauses where it is."""


class ScriptedStateExitLauncher:
    """Stands in for launching an agent or running a script: returns the
    next scripted state-exit for the state it is asked to launch.

    `script` is a list of (state-or-sub-state, verdict, fields) tuples,
    consumed in order; `fields` are StateExitRecord's optional fields.
    A scripted `package_commit` overrides the state-package's, to feign a
    stale state-exit; otherwise the state-exit carries the commit the
    state-package was built from.
    """

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


# --- Nodes and flows ---------------------------------------------------------

class StateWorkNode:
    """One state's (or sub-state's) work: prep assembles the state-package,
    exec launches it, post routes on the verdict it came back with. `run`
    returns the next position of the run."""

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
            return None  # the state is re-run
        return self.machine.route_state_exit(run, state_exit)

    def run(self, run):
        while True:
            state_package = self.prep(run)
            state_exit = self.exec(state_package)
            next_position = self.post(run, state_package, state_exit)
            if next_position is not None:
                return next_position


class ReviewingStateFlow:
    """A reviewing state is composite (section 3.1): a flow of its
    acceptance-checks, run in order, that acts as a node. It ends with the
    state-exit of the sub-state that ended it — the first whose row leaves
    the composite."""

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
    """The flow that runs one component's run, from initiate-design-to-main
    to ended, routing every state-exit through the transition table and
    committing each to the topic branch."""

    def __init__(self, git_record, launcher, today=None):
        self.git_record = git_record
        self.launcher = launcher
        self.today = today or (lambda: datetime.date.today().isoformat())
        self.routed = []            # (row, state_exit, commit) in order
        self.discarded = []         # stale state-exits
        self.machine_errors = []

    # -- starting and recovering ---------------------------------------------

    def start(self, component):
        return RunStateRecord(component)

    def recover(self):
        """Section 9, recovery: re-run the state from the last commit's
        run-state.json; uncommitted files are the dead process's, discarded.
        The run is read from the last commit BEFORE the discard, so that the
        discard is guarded by the run's own `topic-branch-cut`: a run that
        died before row 1's cut, or an invocation with no run committed at
        HEAD at all, has no commit to recover from and the checkout is the
        invoker's — refused (RefusedBeforeTopicBranchCut), nothing
        discarded."""
        text = self.git_record.run_state_text_at_last_commit()
        if text is None:
            raise RefusedBeforeTopicBranchCut(
                "refused to recover: no run-state.json is committed at HEAD (%s on %r), "
                "so there is no state-exit to recover from; the checkout is as it was" % (
                    self.git_record.head_commit(), self.git_record.current_branch()))
        run = RunStateRecord.from_dict(json.loads(text))
        # A run at `ended` has no state to re-run, so there is nothing of a
        # dead process's to discard: what is in the checkout is the
        # invoker's, kept. What recover() should return or refuse on a
        # finished run is the user's to rule.
        if run.outcome is None:
            self.git_record.discard_all_uncommitted_work_for_recovery(run)
        return run

    # -- the flow ---------------------------------------------------------------

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
        """Run to `ended` and return the outcome. Two refusals leave here
        uncaught, both from before row 1 has cut the topic branch (section
        6.6): TopicBranchCutRefused when row 1's cut is refused, and
        RefusedBeforeTopicBranchCut when initiate-design-to-main emits
        anything but `invoked`. Either way the refusal is the report to
        the invoking conversation, and the run does not start — nothing
        written, nothing committed, the checkout as it was, whatever
        branch it stood on."""
        steps = 0
        while run.current_state != tables.ENDED:
            self.step(run)
            steps += 1
            if steps > max_steps:
                raise RuntimeError("the run did not end within %d steps" % max_steps)
        return run.outcome

    # -- the state-package (section 2) ---------------------------------------

    def assemble_state_package(self, run, state):
        composite = tables.COMPOSITE_STATE_OF_SUB_STATE.get(state, state)
        row = tables.STATE_TABLE_BY_NAME[composite]
        return {
            "state": state,
            "composite-state": composite,
            "component": run.component,
            "standard-package": ("the design", "the component-contract",
                                 str(self.git_record.user_rulings_path)),
            "beyond-the-standard-package": row.package_beyond_standard,
            "package-commit": self.git_record.head_commit(),
            "design-version": run.design_version,
        }

    # -- routing -----------------------------------------------------------------

    def discard_stale_state_exit(self, run, state_package, state_exit):
        self.discarded.append((state_package, state_exit))

    def route_state_exit(self, run, state_exit):
        """Check the state-exit against section 3.2, apply the row, commit
        (section 9), and return the next position."""
        resume_destination = None
        if state_exit.verdict == tables.V_RESUME:
            resume_destination = self.resolve_resume_destination(run, state_exit)
        # A `reset` ruling takes effect on the counters before the row is
        # looked up (row 71 guards on the redesigns ceiling); the rulings
        # themselves are written to the branch with the commit, below,
        # after the guard — nothing is on disk if this state-exit is refused.
        self.apply_rulings_to_the_run(run, state_exit)
        try:
            row = find_legal_transition_row(run, state_exit, resume_destination)
            next_position, write_number = self.apply_transition_row(
                run, row, state_exit, resume_destination)
        except (IllegalStateExit, CounterCeilingExceeded) as error:
            if not run.topic_branch_cut:
                # Before row 1 has cut the topic branch a machine error
                # cannot open an investigation: the discard and the commit
                # that open one would run against the invoking
                # conversation's checkout — on `main`, or on the topic
                # branch a finished run for this component left it on,
                # which is why the run's own flag decides and not the
                # branch name. Refused here, before the run's state is
                # touched, so that the run is still at
                # initiate-design-to-main and nothing is on disk; the
                # record's own guard (require_topic_branch_cut_for_run)
                # is the backstop behind this for any path that skips it.
                raise RefusedBeforeTopicBranchCut(
                    "%r from %s is refused before the topic branch is cut: %s; "
                    "the run does not start and the checkout is as it was" % (
                        state_exit.verdict, state_exit.state, error)) from error
            row = None
            write_number = None
            next_position = self.route_machine_error(run, state_exit, error)
        run.previous_state = state_exit.from_state
        # Entry-charged counters and entry rules apply before the commit, so
        # that run-state.json on the branch is the state the run is in.
        self.enter(run, next_position)
        if self.investigation_opens_with(run, state_exit):
            # Section 6.6: the investigation pauses the run — the agent
            # that was working is ended and its uncommitted work discarded,
            # its state re-run on resume. Discarded here, before the
            # opening state-exit is committed, so that the opening commit
            # carries the state-exit and the record (run-state.json, a
            # ruling appended, a reviewer's notes) and nothing the paused
            # agent half-wrote; that is what makes the resume diff the
            # user's edits and only those.
            self.git_record.discard_uncommitted_work_outside_the_record(run)
            # The commit the resume diff runs against (section 6.6): the
            # branch head now, the PARENT of the opening commit, not the
            # opening commit itself. The parent, because the value must be
            # in run-state.json inside the opening commit for the branch
            # to carry it through the pause (a successor recovering from
            # investigate-workflow reads it there), and a commit's own SHA
            # cannot be written into a file it contains. The diff is the
            # same against either: after the discard, the opening commit
            # touches only the record directory, which the diff ignores.
            run.investigation_opened_at_commit = self.git_record.head_commit()
        commit = self.commit_state_exit(run, state_exit, write_number)
        self.routed.append((row, state_exit, commit))
        return run.current_state

    def investigation_opens_with(self, run, state_exit):
        """Whether this state-exit is the one that opens an investigation:
        the run is now paused in investigate-workflow and the state-exit
        came from somewhere else. A state-exit from investigate-workflow
        itself that leaves the run there (a stray verdict, below) does
        not open a new investigation over the one in progress."""
        return (run.current_state == tables.INVESTIGATE_WORKFLOW
                and state_exit.from_state != tables.INVESTIGATE_WORKFLOW)

    def route_machine_error(self, run, state_exit, error):
        """Section 3.2: any other state-exit is a machine error; the run
        pauses in investigate-workflow, investigation-focus unknown, the
        illegal state-exit in the arbitrator's report.

        Emitted from investigate-workflow itself — a verdict other than
        stop, submit-to-PR-gate or resume — the machine error is recorded
        and committed like any other, but the run stays paused where it
        was: the paused state, the focus and the opening commit are the
        investigation's, not overwritten with investigate-workflow and
        unknown, which would send every plain resume back into the
        investigation and lose the user's edits before the stray exit."""
        self.machine_errors.append((state_exit, error))
        run.machine_error = str(error)
        if state_exit.from_state != tables.INVESTIGATE_WORKFLOW:
            run.paused_state = state_exit.from_state
            run.investigation_focus = tables.FOCUS_UNKNOWN
            run.investigation_opened_by = "%s from %s: %s" % (
                state_exit.verdict, state_exit.state, error)
        return tables.INVESTIGATE_WORKFLOW

    def apply_rulings_to_the_run(self, run, state_exit):
        """What a ruling does to the run in memory: `reset` zeroes the
        counters (section 7). The rulings reach the branch's user-rulings
        file with the state-exit's commit (write_rulings_to_the_record)."""
        for ruling in state_exit.rulings:
            if ruling == "reset":
                run.counters.reset_by_the_user()

    def write_rulings_to_the_record(self, run, state_exit):
        for ruling in state_exit.rulings:
            self.git_record.append_user_ruling(run, ruling, self.today())

    def commit_state_exit(self, run, state_exit, write_number):
        # Guarded before anything is written — the rulings, then
        # run-state.json — not only at the record's commit, so a refusal
        # leaves no file behind.
        self.git_record.require_topic_branch_cut_for_run(run, "write and commit the state-exit")
        self.write_rulings_to_the_record(run, state_exit)
        run.write_to(self.git_record.absolute(self.git_record.run_state_path))
        trailer = compose_state_exit_trailer(
            state_exit.state, state_exit.verdict, state_exit.package_commit,
            run.counters.as_dict(), write_number)
        subject = "%s: %s %s" % (run.component, state_exit.state, state_exit.verdict)
        return self.git_record.commit_state_exit(run, subject, trailer)

    # -- entering a state -------------------------------------------------------

    def enter(self, run, position):
        """Section 7's entry-charged counters and section 3.2's entry rules,
        applied when the run moves to `position`, before the state-exit
        that moves it is committed. A sub-state position charges nothing."""
        if position == tables.DESIGN_WRITING and run.previous_state == tables.INVESTIGATE_WORKFLOW:
            # A redesign: counted on entry; resets the version.
            run.counters.increment("redesigns")
            run.start_new_design_version()
        if position == tables.TEST_SUITE_ARBITRATING:
            if run.counters.at_ceiling("arbitrator-rulings"):
                # The arbitrator's third entry opens the investigation
                # (sections 6.5, 7); its ruling rides in the report.
                run.paused_state = tables.TEST_SUITE_ARBITRATING
                run.investigation_focus = tables.FOCUS_UNKNOWN
                run.investigation_opened_by = "the arbitrator's third entry in design version %d" % run.design_version
                run.previous_state = tables.TEST_SUITE_ARBITRATING
                run.current_state = tables.INVESTIGATE_WORKFLOW
                return
            run.counters.increment("arbitrator-rulings")
        # A work-stream's position is the state it is in, reviewing states
        # included: the hold rows (23, 43) send the run to the other
        # work-stream's position, and a stream paused in a reviewing state
        # resumes there, not at the writing state before it.
        composite = tables.COMPOSITE_STATE_OF_SUB_STATE.get(position, position)
        work_stream = tables.STATE_TABLE_BY_NAME[composite].work_stream
        if work_stream:
            run.set_work_stream_position(work_stream, composite)
        run.current_state = position

    # -- applying a row -----------------------------------------------------------

    def enter_writing_state(self, run, state, entry_reason):
        run.writing_state_entry_reason[state] = entry_reason
        work_stream = tables.STATE_TABLE_BY_NAME[state].work_stream
        if work_stream:
            run.set_work_stream_position(work_stream, state)

    def open_investigation(self, run, row, state_exit):
        run.paused_state = state_exit.from_state
        run.investigation_focus = row.investigation_focus or state_exit.investigation_focus
        run.investigation_opened_by = "%s from %s (row %s)" % (
            state_exit.verdict, state_exit.state, row.row)

    def resolve_resume_destination(self, run, state_exit):
        """Section 6.6: the destination the user names; else the earliest
        state downstream of what the diff shows changed; else the state
        that was paused."""
        if state_exit.destination:
            return state_exit.destination
        derived = None
        if run.investigation_opened_at_commit:
            derived = self.git_record.earliest_state_downstream_of_changes(
                run.investigation_opened_at_commit)
        return derived or run.paused_state

    def apply_transition_row(self, run, row, state_exit, resume_destination):
        """Side effects of a row: counters, flags, positions; returns the
        next position and the write number for the trailer."""
        from_state = state_exit.from_state
        verdict = state_exit.verdict
        next_position = row.to_state
        write_number = None

        # The row's counter (section 7: only an emitted state-exit charges
        # a write counter, and by the three buckets).
        if row.counter in tables.COUNTED_WRITING_STATES.values():
            run.writes_emitted_per_version[from_state] = (
                run.writes_emitted_per_version.get(from_state, 0) + 1)
            write_number = run.writes_emitted_per_version[from_state]
            charged = write_counter_charged(
                from_state, run.writing_state_entry_reason.get(
                    from_state, tables.ENTRY_REASON_FIRST_WRITE))
            if charged:
                run.counters.increment(charged)
        elif row.counter:
            run.counters.increment(row.counter)

        if state_exit.coverage_type:
            if from_state == tables.IMPLEMENTATION_WRITING:
                run.implementation_coverage_type = state_exit.coverage_type
            elif from_state == tables.TEST_WRITING:
                run.tests_coverage_type = state_exit.coverage_type

        # The contract's program check: consecutive failures.
        if state_exit.state == tables.CONTRACT_ACCEPTANCE_BY_PROGRAM:
            if verdict == tables.V_REJECT_CONTRACT:
                run.consecutive_contract_program_check_failures += 1
            else:
                run.consecutive_contract_program_check_failures = 0

        # The suite's consecutive could-not-run count and the submit retries.
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

        # Row 1: the machine cuts the topic branch before design-writing.
        # A refusal (TopicBranchCutRefused) leaves the machine here, before
        # anything is entered or committed, and leaves the run's flag
        # unset: a state-exit committed now would land on whatever branch
        # the checkout stands on. The flag, set only once the cut has
        # succeeded, is what the record's guard reads before every discard
        # and commit; it goes to the branch in run-state.json with row 1's
        # own commit, so a successor recovering the run reads it there.
        if row.row == tables.ROW_TOPIC_BRANCH_CUT:
            self.git_record.cut_topic_branch(self.topic_branch_start_point)
            run.topic_branch_cut = True

        # Approvals and the work-streams.
        if row.row == tables.ROW_DESIGN_APPROVED:
            run.design_approved = True
            self.enter_writing_state(run, tables.IMPLEMENTATION_WRITING, self.reason_for_advance(
                run, tables.IMPLEMENTATION_WRITING, tables.ENTRY_REASON_REDESIGN))
            if run.tests_begun:
                self.enter_writing_state(run, tables.TEST_DESIGN_WRITING,
                                         tables.ENTRY_REASON_REDESIGN)
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
        if row.to_state == tables.TO_RETRY_SAME_STATE:
            next_position = from_state

        # Re-entering a writing state by a reject, a discuss or the
        # arbitrator's ruling: why, for the three buckets. (Rows 18 and 39,
        # the advances from upstream, set their reason above.)
        if (row.to_state in (tables.IMPLEMENTATION_WRITING, tables.TEST_WRITING)
                and verdict != tables.V_ADVANCE):
            if verdict == tables.V_DISCUSS:
                reason = tables.ENTRY_REASON_DISCUSS_BY_USER
            elif from_state == tables.TEST_SUITE_ARBITRATING:
                reason = tables.ENTRY_REASON_ARBITRATOR_RULING
            else:
                reason = tables.ENTRY_REASON_REJECT_FROM_REVIEW
            self.enter_writing_state(run, row.to_state, reason)
        if row.to_state == tables.TEST_DESIGN_WRITING and row.row != tables.ROW_TESTS_BEGIN:
            reason = (tables.ENTRY_REASON_TEST_DESIGN_CORRECTION
                      if row.counter == "test-design-corrections"
                      else tables.ENTRY_REASON_REJECT_FROM_REVIEW)
            self.enter_writing_state(run, tables.TEST_DESIGN_WRITING, reason)
        # Investigations and endings.
        if row.to_state == tables.INVESTIGATE_WORKFLOW:
            self.open_investigation(run, row, state_exit)
        if row.to_state == tables.ENDED:
            run.outcome = row.outcome
        if row.to_state == tables.TO_RESUME_DESTINATION:
            next_position = resume_destination
            self.position_work_streams_for_resume(run, next_position, state_exit)

        return next_position, write_number

    def upstream_reason_for_test_writing(self, run):
        """Tests re-entered after the test-design was re-written: the
        test-design changed, whatever sent its writer back, so the write is
        bounded by that document's counter (section 7) unless a document
        further upstream was the cause."""
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

    topic_branch_start_point = "origin/main"
