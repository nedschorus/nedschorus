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

    def reset_for_new_design_version(self):
        """A redesign resets the version (section 3.2): every per-design-
        version counter starts from zero; the redesigns counter does not."""
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
    position, or ready-for-test-suite; the counters; tests-begun; whether
    the design and the test-design are approved; the consecutive
    could-not-run and submit-retry counts; the outcome once ended.

    Fields beyond section 9's list are named in the build report: the
    current state, the consecutive program-check failures, each writing
    state's entry reason (for the three buckets), the writes emitted per
    version (the `Write:` number), the coverage-types, and what an
    investigation needs to resume. One more, `topic-branch-cut`: whether
    row 1 has cut the run's topic branch (section 6.6). Until it has, the
    machine owns nothing in the checkout and refuses every discard and
    commit; the git record's guard reads this flag off the run, not the
    name of the branch the checkout stands on, because a finished run
    leaves the checkout on its topic branch and the name cannot tell a
    fresh invocation from that. Persisted here so that a successor
    process recovering a run reads it from the branch.
    """

    FIELDS = (
        "component", "current-state", "design-version", "outcome",
        "topic-branch-cut",
        "counters", "tests-begun", "design-approved", "test-design-approved",
        "implementation-work-stream-position", "test-work-stream-position",
        "consecutive-could-not-run-count", "submit-retry-count",
        "consecutive-contract-program-check-failures",
        "implementation-coverage-type", "tests-coverage-type",
        "writing-state-entry-reason", "writes-emitted-per-version",
        "paused-state", "investigation-focus", "investigation-opened-at-commit",
        "investigation-opened-by", "machine-error",
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
        self.consecutive_contract_program_check_failures = 0
        self.implementation_coverage_type = None
        self.tests_coverage_type = None
        self.writing_state_entry_reason = {}
        self.writes_emitted_per_version = {}
        self.paused_state = None
        self.investigation_focus = None
        self.investigation_opened_at_commit = None
        self.investigation_opened_by = None
        self.machine_error = None

    # -- section 3.2, "A redesign resets the version" --------------------

    def start_new_design_version(self):
        self.design_version += 1
        self.counters.reset_for_new_design_version()
        self.tests_begun = False
        self.implementation_work_stream_position = None
        self.test_work_stream_position = None
        self.design_approved = False
        self.test_design_approved = False
        self.writes_emitted_per_version = {}
        self.writing_state_entry_reason = {}
        self.consecutive_contract_program_check_failures = 0

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
            "consecutive-contract-program-check-failures":
                self.consecutive_contract_program_check_failures,
            "implementation-coverage-type": self.implementation_coverage_type,
            "tests-coverage-type": self.tests_coverage_type,
            "writing-state-entry-reason": dict(self.writing_state_entry_reason),
            "writes-emitted-per-version": dict(self.writes_emitted_per_version),
            "paused-state": self.paused_state,
            "investigation-focus": self.investigation_focus,
            "investigation-opened-at-commit": self.investigation_opened_at_commit,
            "investigation-opened-by": self.investigation_opened_by,
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
        run.consecutive_contract_program_check_failures = data[
            "consecutive-contract-program-check-failures"]
        run.implementation_coverage_type = data.get("implementation-coverage-type")
        run.tests_coverage_type = data.get("tests-coverage-type")
        run.writing_state_entry_reason = dict(data.get("writing-state-entry-reason", {}))
        run.writes_emitted_per_version = dict(data.get("writes-emitted-per-version", {}))
        run.paused_state = data.get("paused-state")
        run.investigation_focus = data.get("investigation-focus")
        run.investigation_opened_at_commit = data.get("investigation-opened-at-commit")
        run.investigation_opened_by = data.get("investigation-opened-by")
        run.machine_error = data.get("machine-error")
        return run

    def write_to(self, path):
        path = pathlib.Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.as_dict(), indent=2, sort_keys=True) + "\n")

    @classmethod
    def read_from(cls, path):
        return cls.from_dict(json.loads(pathlib.Path(path).read_text()))
