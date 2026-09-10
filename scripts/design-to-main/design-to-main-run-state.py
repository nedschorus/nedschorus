#!/usr/bin/env python3
"""The run-state of one design-to-main run: the counters of section 7 and
the file of section 9, `run-state.json`.

Loaded by design-to-main-state-machine.py through importlib (this file's
name has hyphens, as scripts/ names its files). It reads the tables from
design-to-main-state-tables.py and holds no routing.
"""

import importlib.util
import json
import pathlib

_tables_spec = importlib.util.spec_from_file_location(
    "design_to_main_state_tables",
    pathlib.Path(__file__).with_name("design-to-main-state-tables.py"))
tables = importlib.util.module_from_spec(_tables_spec)
_tables_spec.loader.exec_module(tables)


class CounterCeilingExceeded(Exception):
    """An increment would take a counter past its ceiling. The design never
    routes such an increment; reaching here is a machine error."""


class RunCounters:
    """The seven counters of section 7, with their ceilings."""

    def __init__(self, values=None):
        self.values = {name: 0 for name in tables.COUNTER_NAMES}
        if values:
            for name, value in values.items():
                if name not in self.values:
                    raise KeyError("no counter named %r in section 7" % name)
                self.values[name] = int(value)

    def value(self, name):
        return self.values[name]

    def rule(self, name):
        return tables.COUNTER_TABLE_BY_NAME[name]

    def at_ceiling(self, name):
        """Section 3.2's guard "the <name> counter at its ceiling"."""
        return self.values[name] >= self.rule(name).at_ceiling_from_value

    def below_ceiling(self, name):
        return not self.at_ceiling(name)

    def increment(self, name):
        rule = self.rule(name)
        if self.values[name] + 1 > rule.ceiling:
            raise CounterCeilingExceeded(
                "%s is %d; its ceiling is %d (%s)" % (
                    name, self.values[name], rule.ceiling, rule.at_the_ceiling))
        self.values[name] += 1
        return self.values[name]

    def zero_the_six_per_version_counters(self):
        """The six per-version counters start from zero; the redesigns
        counter does not. A redesign does this (section 3.2, "A redesign
        resets the version"), and so does every resume from an
        investigation (section 7, row 71; user-ruled 2026-09-09, the
        eighth walk: "if I intervene all the agents get their chance
        again")."""
        for rule in tables.COUNTER_TABLE:
            if rule.per_design_version:
                self.values[rule.name] = 0

    def reset_by_the_user(self):
        """The user's `reset` (section 7): zeroes every counter, the
        redesigns counter included."""
        for name in self.values:
            self.values[name] = 0

    def as_dict(self):
        return dict(self.values)


def write_counter_charged(writing_state, entry_reason):
    """The three buckets of section 7, applied to an emitted write.

    Returns the counter an `emitted` from `writing_state` spends, or None
    when the write it replaces was thrown out for a reason another counter
    already paid for (the arbitrator's entry, or the re-write of the
    upstream document that changed).
    """
    writers_counter = tables.COUNTED_WRITING_STATES.get(writing_state)
    if writers_counter is None:
        return None
    bucket = tables.WRITING_STATE_ENTRY_REASON_TO_BUCKET[entry_reason]
    if bucket == tables.BUCKET_FAILED_REVIEW:
        return writers_counter
    return None


class RunStateRecord:
    """`run-state.json` (section 9): the design version; each work-stream's
    position, or ready-for-test-suite; the counters of section 7;
    tests-begun; whether the design and the test-design are approved; the
    consecutive could-not-run, program-check-failure and submit-retry
    counts; why each state was entered (the writing states' entry reasons,
    for the three buckets; what entered test-suite-arbitrating, for rows
    58 and 59); each artifact's coverage-type; the paused
    state and the commit at which an investigation opened; whether row 1
    has cut the topic branch; the outcome once ended.

    Fields beyond that list: the current and previous state; the writes
    emitted per version (for the first-write rule); the investigation's
    focus, what opened it and by which row, the destination it holds for
    its resume; and the last machine error. `topic-branch-cut` is the
    flag the git record's guard reads off the run before every discard
    and commit (section 6.6) — not the name of the branch the checkout
    stands on, because a finished run leaves the checkout on its topic
    branch and the name cannot tell a fresh invocation from that.
    Persisted so that a successor process recovering a run reads it from
    the branch.
    """

    FIELDS = (
        "component", "current-state", "design-version", "outcome",
        "topic-branch-cut",
        "counters", "tests-begun", "design-approved", "test-design-approved",
        "implementation-work-stream-position", "test-work-stream-position",
        "consecutive-could-not-run-count", "submit-retry-count",
        "consecutive-program-check-failure-count",
        "implementation-coverage-type", "tests-coverage-type",
        "writing-state-entry-reason", "writes-emitted-per-version",
        "test-suite-arbitrating-entered-from",
        "paused-state", "investigation-focus", "investigation-opened-at-commit",
        "investigation-opened-by", "investigation-opened-by-row",
        "investigation-held-resume-destination", "machine-error",
        "previous-state",
    )

    def __init__(self, component):
        self.component = component
        self.current_state = tables.INITIATE_DESIGN_TO_MAIN
        self.previous_state = None
        self.design_version = 1
        self.outcome = None
        self.topic_branch_cut = False
        self.counters = RunCounters()
        self.tests_begun = False
        self.design_approved = False
        self.test_design_approved = False
        self.implementation_work_stream_position = None
        self.test_work_stream_position = None
        self.consecutive_could_not_run_count = 0
        self.submit_retry_count = 0
        self.consecutive_program_check_failure_count = 0
        self.implementation_coverage_type = None
        self.tests_coverage_type = None
        self.writing_state_entry_reason = {}
        self.writes_emitted_per_version = {}
        # Why test-suite-arbitrating was entered, as the state or sub-state
        # whose state-exit entered it: test-suite-executing on a failed
        # suite or a could-not-run, a reviewing sub-state on a reviewer's
        # reject at the writer's ceiling. Rows 58 and 59 route the
        # arbitrator's `advance` on it (section 6.5).
        self.test_suite_arbitrating_entered_from = None
        self.paused_state = None
        self.investigation_focus = None
        self.investigation_opened_at_commit = None
        self.investigation_opened_by = None
        # The row of section 3.2 that opened the investigation, or None for
        # a machine error; row 64 (the arbitrator's third entry) is the one
        # a resume must not return to (section 6.6).
        self.investigation_opened_by_row = None
        # The destination the investigation's opening held for its resume
        # (row 11: design-writing), applied when the user names none.
        self.investigation_held_resume_destination = None
        self.machine_error = None

    # -- section 3.2, "A redesign resets the version" --------------------

    def start_new_design_version(self):
        self.design_version += 1
        self.counters.zero_the_six_per_version_counters()
        self.tests_begun = False
        self.implementation_work_stream_position = None
        self.test_work_stream_position = None
        self.design_approved = False
        self.test_design_approved = False
        self.writes_emitted_per_version = {}
        self.writing_state_entry_reason = {}
        self.test_suite_arbitrating_entered_from = None
        self.consecutive_program_check_failure_count = 0

    # -- work-streams ------------------------------------------------------

    def work_stream_position(self, work_stream):
        if work_stream == tables.IMPLEMENTATION_WORK_STREAM:
            return self.implementation_work_stream_position
        if work_stream == tables.TEST_WORK_STREAM:
            return self.test_work_stream_position
        raise KeyError(work_stream)

    def set_work_stream_position(self, work_stream, position):
        if work_stream == tables.IMPLEMENTATION_WORK_STREAM:
            self.implementation_work_stream_position = position
        elif work_stream == tables.TEST_WORK_STREAM:
            self.test_work_stream_position = position
        else:
            raise KeyError(work_stream)

    def work_stream_ready(self, work_stream):
        return self.work_stream_position(work_stream) == tables.READY_FOR_TEST_SUITE

    def is_agent_instructions(self, coverage_type):
        return coverage_type in tables.COVERAGE_TYPES_THAT_ARE_AGENT_INSTRUCTIONS

    # -- the file -----------------------------------------------------------

    def as_dict(self):
        return {
            "component": self.component,
            "current-state": self.current_state,
            "previous-state": self.previous_state,
            "design-version": self.design_version,
            "outcome": self.outcome,
            "topic-branch-cut": self.topic_branch_cut,
            "counters": self.counters.as_dict(),
            "tests-begun": self.tests_begun,
            "design-approved": self.design_approved,
            "test-design-approved": self.test_design_approved,
            "implementation-work-stream-position": self.implementation_work_stream_position,
            "test-work-stream-position": self.test_work_stream_position,
            "consecutive-could-not-run-count": self.consecutive_could_not_run_count,
            "submit-retry-count": self.submit_retry_count,
            "consecutive-program-check-failure-count":
                self.consecutive_program_check_failure_count,
            "implementation-coverage-type": self.implementation_coverage_type,
            "tests-coverage-type": self.tests_coverage_type,
            "writing-state-entry-reason": dict(self.writing_state_entry_reason),
            "writes-emitted-per-version": dict(self.writes_emitted_per_version),
            "test-suite-arbitrating-entered-from": self.test_suite_arbitrating_entered_from,
            "paused-state": self.paused_state,
            "investigation-focus": self.investigation_focus,
            "investigation-opened-at-commit": self.investigation_opened_at_commit,
            "investigation-opened-by": self.investigation_opened_by,
            "investigation-opened-by-row": self.investigation_opened_by_row,
            "investigation-held-resume-destination": self.investigation_held_resume_destination,
            "machine-error": self.machine_error,
        }

    @classmethod
    def from_dict(cls, data):
        run = cls(data["component"])
        run.current_state = data["current-state"]
        run.previous_state = data.get("previous-state")
        run.design_version = data["design-version"]
        run.outcome = data.get("outcome")
        # Absent means not cut: a file without the flag recovers into a
        # run the record refuses to discard for or commit, never one it
        # takes as cut.
        run.topic_branch_cut = bool(data.get("topic-branch-cut", False))
        run.counters = RunCounters(data["counters"])
        run.tests_begun = data["tests-begun"]
        run.design_approved = data["design-approved"]
        run.test_design_approved = data["test-design-approved"]
        run.implementation_work_stream_position = data["implementation-work-stream-position"]
        run.test_work_stream_position = data["test-work-stream-position"]
        run.consecutive_could_not_run_count = data["consecutive-could-not-run-count"]
        run.submit_retry_count = data["submit-retry-count"]
        run.consecutive_program_check_failure_count = data[
            "consecutive-program-check-failure-count"]
        run.implementation_coverage_type = data.get("implementation-coverage-type")
        run.tests_coverage_type = data.get("tests-coverage-type")
        run.writing_state_entry_reason = dict(data.get("writing-state-entry-reason", {}))
        run.writes_emitted_per_version = dict(data.get("writes-emitted-per-version", {}))
        run.test_suite_arbitrating_entered_from = data.get("test-suite-arbitrating-entered-from")
        run.paused_state = data.get("paused-state")
        run.investigation_focus = data.get("investigation-focus")
        run.investigation_opened_at_commit = data.get("investigation-opened-at-commit")
        run.investigation_opened_by = data.get("investigation-opened-by")
        run.investigation_opened_by_row = data.get("investigation-opened-by-row")
        run.investigation_held_resume_destination = data.get(
            "investigation-held-resume-destination")
        run.machine_error = data.get("machine-error")
        return run

    def write_to(self, path):
        path = pathlib.Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.as_dict(), indent=2, sort_keys=True) + "\n")

    @classmethod
    def read_from(cls, path):
        return cls.from_dict(json.loads(pathlib.Path(path).read_text()))
