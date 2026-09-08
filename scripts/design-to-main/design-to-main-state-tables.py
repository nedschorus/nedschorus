#!/usr/bin/env python3
"""The design-to-main state machine's tables, as data.

Source: docs/design-to-main/design-to-main-state-machine-design.md.
  STATE_TABLE        is section 3.1, one entry per row.
  TRANSITION_TABLE   is section 3.2, one entry per row, numbered in the
                     order the design lists them (row 1 is
                     `initiate-design-to-main / invoked`). Rows the design
                     does not list but section 3.1 implies (the sub-states
                     of a reviewing state "run in order") are numbered
                     after the design's rows and marked source "3.1".
  COUNTER_TABLE      is section 7, one entry per counter.

Nothing here routes. The machine (design-to-main-state-machine.py) reads
these tables; the guards are named here with the design's own words and
evaluated there, so that a row of the design maps to a row of this file.
"""

from dataclasses import dataclass
from typing import Optional, Tuple

# --- The states of section 3.1 -------------------------------------------

INITIATE_DESIGN_TO_MAIN = "initiate-design-to-main"
DESIGN_WRITING = "design-writing"
CONTRACT_REVIEWING = "contract-reviewing"
DESIGN_REVIEWING = "design-reviewing"
CONTRACT_REVISING = "contract-revising"
IMPLEMENTATION_WRITING = "implementation-writing"
IMPLEMENTATION_REVIEWING = "implementation-reviewing"
TEST_DESIGN_WRITING = "test-design-writing"
TEST_DESIGN_REVIEWING = "test-design-reviewing"
TEST_WRITING = "test-writing"
TEST_REVIEWING = "test-reviewing"
TEST_SUITE_EXECUTING = "test-suite-executing"
TEST_SUITE_ARBITRATING = "test-suite-arbitrating"
INVESTIGATE_WORKFLOW = "investigate-workflow"
SUBMIT_TO_PR_GATE = "submit-to-PR-gate"
ENDED = "ended"

# Sub-states (the acceptance-checks of the reviewing states).
CONTRACT_ACCEPTANCE_BY_PROGRAM = "contract-acceptance-by-program"
CONTRACT_ACCEPTANCE_BY_AGENT = "contract-acceptance-by-agent"
CONTRACT_ACCEPTANCE_BY_USER = "contract-acceptance-by-user"
DESIGN_ACCEPTANCE_BY_AGENT = "design-acceptance-by-agent"
DESIGN_ACCEPTANCE_BY_USER = "design-acceptance-by-user"
IMPLEMENTATION_ACCEPTANCE_BY_AGENT = "implementation-acceptance-by-agent"
IMPLEMENTATION_ACCEPTANCE_BY_USER = "implementation-acceptance-by-user"
TEST_DESIGN_ACCEPTANCE_BY_AGENT = "test-design-acceptance-by-agent"
TEST_DESIGN_ACCEPTANCE_BY_USER = "test-design-acceptance-by-user"
TEST_ACCEPTANCE_BY_AGENT = "test-acceptance-by-agent"
TEST_ACCEPTANCE_BY_USER = "test-acceptance-by-user"

# A work-stream's position when its last reviewing state has advanced and
# the other work-stream has not (glossary: ready-for-test-suite).
READY_FOR_TEST_SUITE = "ready-for-test-suite"

IMPLEMENTATION_WORK_STREAM = "implementation-work-stream"
TEST_WORK_STREAM = "test-work-stream"

# The outcomes of `ended` (section 3.4).
OUTCOME_PASSED = "passed"
OUTCOME_STOPPED_BY_USER = "stopped-by-user"
OUTCOME_FAILED = "failed"

# Investigation-focus values (section 6.6).
FOCUS_DESIGN = "design"
FOCUS_CONTRACT = "contract"
FOCUS_TEST_DESIGN = "test-design"
FOCUS_UNKNOWN = "unknown"

# The inputs an input-quick-check-failed may name (section 4).
INPUT_DESIGN = "design"
INPUT_COMPONENT_CONTRACT = "component-contract"
INPUT_TEST_DESIGN = "test-design"

# The classes of a gatekeeper-refusal (section 3.4).
REFUSAL_INFRASTRUCTURE = "infrastructure"
REFUSAL_INTEGRATION = "integration"
REFUSAL_SCOPE = "scope"
REFUSAL_FORM = "form"

# Coverage-types (section 2); the two that are agent-instructions.
COVERAGE_TYPES_THAT_ARE_AGENT_INSTRUCTIONS = ("prompt", "script-and-prompt")

# Verdicts (the exit words of sections 3.1 and 6.1).
V_INVOKED = "invoked"
V_EMITTED = "emitted"
V_ADVANCE = "advance"
V_REJECT_CONTRACT = "reject contract"
V_REJECT_DESIGN = "reject design"
V_REJECT_IMPLEMENTATION = "reject implementation"
V_REJECT_TESTS = "reject tests"
V_REJECT_TEST_DESIGN = "reject test-design"
V_DISCUSS = "discuss"
V_INPUT_QUICK_CHECK_FAILED = "input-quick-check-failed"
V_ESCALATE_TO_USER = "escalate-to-user"
V_PASS = "pass"
V_FAIL = "fail"
V_COULD_NOT_RUN = "could-not-run"
V_FLAKY_TEST = "flaky-test"
V_STOP = "stop"
V_SUBMIT_TO_PR_GATE = "submit-to-PR-gate"
V_RESUME = "resume"
V_ACCEPTED = "accepted"
V_GATE_REJECTION = "gate-rejection"
V_GATEKEEPER_REFUSAL = "gatekeeper-refusal"

# The writer's counter that a `reject <artifact>` or `flaky-test` against a
# counted writer refers to (section 3.2, "any reject whose writer's counter").
WRITER_COUNTER_FOR_VERDICT = {
    V_REJECT_IMPLEMENTATION: "implementation-writes",
    V_REJECT_TESTS: "test-writes",
    V_FLAKY_TEST: "test-writes",
}


@dataclass(frozen=True)
class StateTableRow:
    """One row of section 3.1."""
    name: str
    sub_states: Tuple[str, ...]
    package_beyond_standard: str
    verdicts: Tuple[str, ...]
    # Who does the work (section 1): "conversation", "agent", "program",
    # "machine", "composite", "terminal".
    work: str
    work_stream: Optional[str] = None


STATE_TABLE = (
    StateTableRow(INITIATE_DESIGN_TO_MAIN, (),
                  "the user's invocation of the skill, naming the component",
                  (V_INVOKED,), "conversation"),
    StateTableRow(DESIGN_WRITING, (),
                  "the invocation; on a redesign, the investigation report",
                  (V_EMITTED,), "conversation"),
    StateTableRow(CONTRACT_REVIEWING,
                  (CONTRACT_ACCEPTANCE_BY_PROGRAM, CONTRACT_ACCEPTANCE_BY_AGENT,
                   CONTRACT_ACCEPTANCE_BY_USER),
                  "the previous version and the notes, on a revision",
                  (V_ADVANCE, V_REJECT_CONTRACT, V_DISCUSS), "composite"),
    StateTableRow(DESIGN_REVIEWING,
                  (DESIGN_ACCEPTANCE_BY_AGENT, DESIGN_ACCEPTANCE_BY_USER),
                  "",
                  (V_ADVANCE, V_REJECT_DESIGN, V_REJECT_CONTRACT, V_DISCUSS),
                  "composite"),
    StateTableRow(CONTRACT_REVISING, (),
                  "the notes or the failed-check report, and the version being revised",
                  (V_EMITTED, V_INPUT_QUICK_CHECK_FAILED), "agent"),
    StateTableRow(IMPLEMENTATION_WRITING, (),
                  "on re-entry, the implementation as it stands and the notes; "
                  "when an upstream document changed, its diff",
                  (V_EMITTED, V_INPUT_QUICK_CHECK_FAILED), "agent",
                  IMPLEMENTATION_WORK_STREAM),
    StateTableRow(IMPLEMENTATION_REVIEWING,
                  (IMPLEMENTATION_ACCEPTANCE_BY_AGENT, IMPLEMENTATION_ACCEPTANCE_BY_USER),
                  "the implementation's files; on a second review, the previous reviewer's notes",
                  (V_ADVANCE, V_REJECT_IMPLEMENTATION, V_REJECT_CONTRACT,
                   V_REJECT_DESIGN, V_DISCUSS),
                  "composite", IMPLEMENTATION_WORK_STREAM),
    StateTableRow(TEST_DESIGN_WRITING, (),
                  "on re-entry, the test-design as it stands and the notes; "
                  "when an upstream document changed, its diff",
                  (V_EMITTED, V_INPUT_QUICK_CHECK_FAILED), "agent",
                  TEST_WORK_STREAM),
    StateTableRow(TEST_DESIGN_REVIEWING,
                  (TEST_DESIGN_ACCEPTANCE_BY_AGENT, TEST_DESIGN_ACCEPTANCE_BY_USER),
                  "the test-design",
                  (V_ADVANCE, V_REJECT_TEST_DESIGN, V_REJECT_CONTRACT,
                   V_REJECT_DESIGN, V_DISCUSS),
                  "composite", TEST_WORK_STREAM),
    StateTableRow(TEST_WRITING, (),
                  "the test-design; on re-entry, the tests as they stand and the notes; "
                  "when an upstream document changed, its diff",
                  (V_EMITTED, V_INPUT_QUICK_CHECK_FAILED), "agent",
                  TEST_WORK_STREAM),
    StateTableRow(TEST_REVIEWING,
                  (TEST_ACCEPTANCE_BY_AGENT, TEST_ACCEPTANCE_BY_USER),
                  "the test-design; the tests' files",
                  (V_ADVANCE, V_REJECT_TESTS, V_REJECT_TEST_DESIGN,
                   V_REJECT_CONTRACT, V_REJECT_DESIGN, V_DISCUSS),
                  "composite", TEST_WORK_STREAM),
    StateTableRow(TEST_SUITE_EXECUTING, (),
                  "the implementation; the tests; the test-design",
                  (V_PASS, V_FAIL, V_COULD_NOT_RUN), "machine"),
    StateTableRow(TEST_SUITE_ARBITRATING, (),
                  "the implementation-work-stream's last state-package and files; "
                  "the test-work-stream's; the whole branch",
                  (V_ADVANCE, V_REJECT_IMPLEMENTATION, V_REJECT_TESTS,
                   V_REJECT_CONTRACT, V_FLAKY_TEST, V_ESCALATE_TO_USER),
                  "agent"),
    StateTableRow(INVESTIGATE_WORKFLOW, (),
                  "the whole branch; the notes or state-exit that opened it",
                  (V_STOP, V_SUBMIT_TO_PR_GATE, V_RESUME), "conversation"),
    StateTableRow(SUBMIT_TO_PR_GATE, (),
                  "the accepted implementation and tests",
                  (V_ACCEPTED, V_GATE_REJECTION, V_GATEKEEPER_REFUSAL), "program"),
    StateTableRow(ENDED, (), "", (), "terminal"),
)

STATE_TABLE_BY_NAME = {row.name: row for row in STATE_TABLE}

# Every sub-state, mapped to its composite state.
COMPOSITE_STATE_OF_SUB_STATE = {
    sub_state: row.name for row in STATE_TABLE for sub_state in row.sub_states
}

# The states that also have `escalate-to-user` (section 3.1, the paragraph
# after the table): every reviewing sub-state by agent, and these three.
ACCEPTANCE_CHECKS_BY_AGENT = tuple(
    s for s in COMPOSITE_STATE_OF_SUB_STATE if s.endswith("-acceptance-by-agent"))
STATES_WITH_ESCALATE_TO_USER = (
    CONTRACT_REVISING, TEST_DESIGN_WRITING, TEST_SUITE_ARBITRATING)

WRITING_STATES = (CONTRACT_REVISING, IMPLEMENTATION_WRITING,
                  TEST_DESIGN_WRITING, TEST_WRITING)
COUNTED_WRITING_STATES = {
    IMPLEMENTATION_WRITING: "implementation-writes",
    TEST_WRITING: "test-writes",
}


# --- The counters of section 7 -------------------------------------------

@dataclass(frozen=True)
class CounterCeilingRule:
    """One row of section 7's table.

    `ceiling` is the design's number. `at_ceiling_from_value` is the
    counter value at which section 3.2's guard "the counter at its ceiling"
    holds, taken from the row's own words in the "Ceiling" column: "a third
    entry is refused" and "the third write" put it at the ceiling itself;
    "the second entry is not made" puts it one below (see the build report,
    finding on contract-revisions and test-design-corrections).
    """
    name: str
    increments_when: str
    ceiling: int
    at_ceiling_from_value: int
    at_the_ceiling: str
    per_design_version: bool = True


COUNTER_TABLE = (
    CounterCeilingRule(
        "redesigns",
        "`design-writing` is entered from `investigate-workflow`",
        2, 2, "`ended`, outcome `failed`", per_design_version=False),
    CounterCeilingRule(
        "design-revisions",
        "`design-acceptance-by-agent` rejects the design or the component-contract "
        "before the design's approval",
        2, 2, "the initiator brings the user into the conversation with every set of notes"),
    CounterCeilingRule(
        "implementation-writes",
        "`implementation-writing` emits `emitted` after a `reject implementation` "
        "from review, or as the first write",
        3, 3, "the third write, when it fails review, goes to `test-suite-arbitrating`"),
    CounterCeilingRule(
        "test-writes",
        "`test-writing` emits `emitted` after a `reject tests` from review, "
        "or as the first write",
        3, 3, "the same"),
    CounterCeilingRule(
        "arbitrator-rulings",
        "`test-suite-arbitrating` is entered",
        2, 2, "the third entry opens the investigation with the user"),
    CounterCeilingRule(
        "contract-revisions",
        "`contract-revising` is entered after a rejection or a failed check against "
        "the component-contract, once the design is approved",
        2, 1, "`contract-acceptance-by-user`; the second entry is not made"),
    CounterCeilingRule(
        "test-design-corrections",
        "`test-design-writing` is re-entered after a rejection or a failed check "
        "against the test-design, once the test-design is approved",
        2, 1, "`test-design-acceptance-by-user`; the second entry is not made"),
)

COUNTER_TABLE_BY_NAME = {rule.name: rule for rule in COUNTER_TABLE}
COUNTER_NAMES = tuple(rule.name for rule in COUNTER_TABLE)

# Section 7's counters that are charged when a state is ENTERED, not by a
# row of section 3.2: the rows say "on entry" for these (and, for the
# arbitrator, section 6.5 says every entry).
COUNTER_CHARGED_ON_ENTRY = {
    TEST_SUITE_ARBITRATING: "arbitrator-rulings",
    # redesigns: only when entered from investigate-workflow; the machine
    # checks the previous state.
    DESIGN_WRITING: "redesigns",
}

# The three buckets (section 7, first paragraph): a write that is thrown
# out is counted by why it was thrown out. Keyed by why a writing state was
# re-entered; the value names whose counter that write spends. "the
# writer's counter" is the writing state's own (COUNTED_WRITING_STATES)
# and is charged when the write is emitted; the other two were charged
# already, on the arbitrator's entry or on the document's re-write, so the
# emitted write charges nothing.
BUCKET_FAILED_REVIEW = "failed-review"
BUCKET_ARBITRATOR_RULED = "arbitrator-ruled"
BUCKET_UPSTREAM_DOCUMENT_CHANGED = "upstream-document-changed"

DISCARDED_WRITE_BUCKETS = {
    BUCKET_FAILED_REVIEW: "the writer's counter",
    BUCKET_ARBITRATOR_RULED: "arbitrator-rulings",
    BUCKET_UPSTREAM_DOCUMENT_CHANGED: "that document's counter, and nothing else",
}

# Why a writing state was entered -> the bucket its write is charged to.
ENTRY_REASON_FIRST_WRITE = "first-write"
ENTRY_REASON_REJECT_FROM_REVIEW = "reject-from-review"
ENTRY_REASON_DISCUSS_BY_USER = "discuss-by-user"
ENTRY_REASON_ARBITRATOR_RULING = "arbitrator-ruling"
ENTRY_REASON_CONTRACT_REVISION = "contract-revision"
ENTRY_REASON_TEST_DESIGN_CORRECTION = "test-design-correction"
ENTRY_REASON_REDESIGN = "redesign"
ENTRY_REASON_USER_NAMED_DESTINATION = "user-named-destination"

WRITING_STATE_ENTRY_REASON_TO_BUCKET = {
    ENTRY_REASON_FIRST_WRITE: BUCKET_FAILED_REVIEW,            # "or as the first write"
    ENTRY_REASON_REJECT_FROM_REVIEW: BUCKET_FAILED_REVIEW,
    ENTRY_REASON_DISCUSS_BY_USER: BUCKET_FAILED_REVIEW,        # "counted like any other"
    ENTRY_REASON_ARBITRATOR_RULING: BUCKET_ARBITRATOR_RULED,
    ENTRY_REASON_CONTRACT_REVISION: BUCKET_UPSTREAM_DOCUMENT_CHANGED,
    ENTRY_REASON_TEST_DESIGN_CORRECTION: BUCKET_UPSTREAM_DOCUMENT_CHANGED,
    ENTRY_REASON_REDESIGN: BUCKET_UPSTREAM_DOCUMENT_CHANGED,
    # The user naming a writing state on resume is his own time (a choice
    # of this build; see the report).
    ENTRY_REASON_USER_NAMED_DESTINATION: BUCKET_UPSTREAM_DOCUMENT_CHANGED,
}


# --- The transitions of section 3.2 --------------------------------------

# Destination markers that are not plain state names.
TO_HOLD_READY_FOR_TEST_SUITE = "hold at ready-for-test-suite"
TO_BOTH_WORK_STREAMS_RE_ENTER = "both work-streams re-enter their writing states"
TO_RESUME_DESTINATION = "the resume destination (section 6.6)"
TO_RETRY_SAME_STATE = "the same state (retry)"

# Guard words. Each is a phrase of the design; the machine holds one
# predicate per phrase (GUARD_PREDICATES in design-to-main-state-machine.py).
G_FROM_PROGRAM_CHECK = "from the program check"
G_FIRST_TIME = "first time"
G_SECOND_CONSECUTIVE_TIME = "second consecutive time"
G_DESIGN_NOT_YET_APPROVED = "the design not yet approved"
G_ON_A_CONTRACT_REVISION = "on a contract-revision"
G_FROM_CONTRACT_ACCEPTANCE_BY_AGENT = "from contract-acceptance-by-agent"
G_FROM_CONTRACT_ACCEPTANCE_BY_AGENT_OR_USER = "from contract-acceptance-by-agent or -by-user"
G_FROM_CONTRACT_ACCEPTANCE_BY_USER = "from contract-acceptance-by-user"
G_FROM_DESIGN_ACCEPTANCE_BY_AGENT = "from design-acceptance-by-agent"
G_FROM_DESIGN_ACCEPTANCE_BY_USER = "from design-acceptance-by-user"
G_FROM_IMPLEMENTATION_ACCEPTANCE_BY_USER = "from implementation-acceptance-by-user"
G_FROM_TEST_DESIGN_ACCEPTANCE_BY_AGENT = "from test-design-acceptance-by-agent"
G_FROM_TEST_DESIGN_ACCEPTANCE_BY_USER = "from test-design-acceptance-by-user"
G_FROM_TEST_ACCEPTANCE_BY_USER = "from test-acceptance-by-user"
G_FROM_AN_ACCEPTANCE_CHECK_BY_AGENT = "from a reviewing sub-state by agent"
G_FROM_THE_LAST_ACCEPTANCE_CHECK = "from the last acceptance-check of the reviewing state"
G_FROM_AN_EARLIER_ACCEPTANCE_CHECK = "from an acceptance-check that is not the last"
G_AGAINST_THE_DESIGN = "against the design"
G_AGAINST_THE_COMPONENT_CONTRACT = "against the component-contract"
G_AGAINST_THE_TEST_DESIGN = "against the test-design"
G_TESTS_NOT_YET_BEGUN = "tests not yet begun"
G_TESTS_BEGUN = "tests begun"
G_TEST_WORK_STREAM_READY = "the test-work-stream at ready-for-test-suite"
G_TEST_WORK_STREAM_NOT_READY = "the test-work-stream not yet there"
G_IMPLEMENTATION_WORK_STREAM_READY = "the implementation-work-stream at ready-for-test-suite"
G_IMPLEMENTATION_WORK_STREAM_NOT_READY = "the implementation-work-stream not yet there"
G_COULD_NOT_RUN_FIRST = "the first of consecutive entries"
G_COULD_NOT_RUN_SECOND = "the second consecutive"
G_WRITERS_COUNTER_BELOW_CEILING = "the writer's counter below its ceiling"
G_WRITERS_COUNTER_AT_CEILING = "the writer's counter at its ceiling"
G_FOCUS_NAMED_DESIGN_OR_TEST_DESIGN = "investigation-focus design or test-design as the agent names it"
G_FOCUS_NOT_NAMED = "no investigation-focus named by the agent"
G_RESUME_BELOW_REDESIGNS_CEILING_OR_NOT_TO_DESIGN_WRITING = (
    "the redesigns counter below its ceiling or the destination not design-writing")
G_RESUME_TO_DESIGN_WRITING_AT_REDESIGNS_CEILING = (
    "resume to design-writing, the redesigns counter at its ceiling")
G_REFUSAL_INFRASTRUCTURE = "an infrastructure refusal"
G_FEWER_THAN_FIVE_ATTEMPTS = "fewer than five attempts"
G_FIFTH_INFRASTRUCTURE_ATTEMPT_OR_INTEGRATION_OR_SCOPE_REFUSAL = (
    "an infrastructure refusal, the fifth attempt; or an integration or scope refusal")
G_REFUSAL_FORM = "a form refusal"


def counter_below_ceiling(name):
    return "the %s counter below its ceiling" % name


def counter_at_ceiling(name):
    return "the %s counter at its ceiling" % name


@dataclass(frozen=True)
class TransitionTableRow:
    """One row of section 3.2 (source "3.2") or one the sub-state order of
    section 3.1 implies (source "3.1")."""
    row: str
    from_states: Tuple[str, ...]
    verdicts: Tuple[str, ...]
    guards: Tuple[str, ...]
    to_state: str
    counter: Optional[str] = None
    counter_note: str = ""
    investigation_focus: Optional[str] = None
    outcome: Optional[str] = None
    source: str = "3.2"
    note: str = ""


def _row(row, from_states, verdicts, guards, to_state, counter=None, **kw):
    if isinstance(from_states, str):
        from_states = (from_states,)
    if isinstance(verdicts, str):
        verdicts = (verdicts,)
    return TransitionTableRow(row, tuple(from_states), tuple(verdicts),
                              tuple(guards), to_state, counter, **kw)


TRANSITION_TABLE = (
    _row("1", INITIATE_DESIGN_TO_MAIN, V_INVOKED, (), DESIGN_WRITING,
         note="after the machine has cut the topic branch (section 9)"),
    _row("2", DESIGN_WRITING, V_EMITTED, (), CONTRACT_REVIEWING,
         counter_note="redesigns are counted on entry, not here",
         note="program check only"),
    _row("3", CONTRACT_REVIEWING, V_REJECT_CONTRACT,
         (G_FROM_PROGRAM_CHECK, G_FIRST_TIME), CONTRACT_REVISING,
         counter_note="not counted; a structural failure", note="fresh"),
    _row("4", CONTRACT_REVIEWING, V_REJECT_CONTRACT,
         (G_FROM_PROGRAM_CHECK, G_SECOND_CONSECUTIVE_TIME), INVESTIGATE_WORKFLOW,
         investigation_focus=FOCUS_CONTRACT),
    _row("5", CONTRACT_REVIEWING, V_ADVANCE,
         (G_FROM_PROGRAM_CHECK, G_DESIGN_NOT_YET_APPROVED), DESIGN_REVIEWING),
    _row("6", CONTRACT_REVIEWING, V_ADVANCE,
         (G_FROM_PROGRAM_CHECK, G_ON_A_CONTRACT_REVISION), CONTRACT_ACCEPTANCE_BY_AGENT),
    _row("7", CONTRACT_REVIEWING, V_REJECT_CONTRACT,
         (G_FROM_CONTRACT_ACCEPTANCE_BY_AGENT, counter_below_ceiling("contract-revisions")),
         CONTRACT_REVISING, "contract-revisions"),
    _row("8", CONTRACT_REVIEWING, V_REJECT_CONTRACT,
         (G_FROM_CONTRACT_ACCEPTANCE_BY_AGENT, counter_at_ceiling("contract-revisions")),
         CONTRACT_ACCEPTANCE_BY_USER),
    _row("9", CONTRACT_REVIEWING, V_ADVANCE,
         (G_FROM_CONTRACT_ACCEPTANCE_BY_AGENT_OR_USER, G_ON_A_CONTRACT_REVISION),
         TO_BOTH_WORK_STREAMS_RE_ENTER, note="the revised-contract invalidation rule"),
    _row("10", CONTRACT_REVIEWING, V_DISCUSS, (G_FROM_CONTRACT_ACCEPTANCE_BY_USER,),
         CONTRACT_REVISING, counter_note="the user's own time"),
    _row("11", DESIGN_REVIEWING, V_REJECT_DESIGN,
         (G_FROM_DESIGN_ACCEPTANCE_BY_AGENT, counter_below_ceiling("design-revisions")),
         DESIGN_WRITING, "design-revisions", note="the same initiator; it revises alone"),
    _row("12", DESIGN_REVIEWING, V_REJECT_DESIGN,
         (G_FROM_DESIGN_ACCEPTANCE_BY_AGENT, counter_at_ceiling("design-revisions")),
         DESIGN_WRITING, note="the same initiator brings the user into the conversation"),
    # Row 13 has no ceiling guard in the design; sections 4 and 7 give
    # design-revisions one ceiling for both rejects, so the row is split
    # here the way rows 11 and 12 are (build report, finding on row 13).
    _row("13a", DESIGN_REVIEWING, V_REJECT_CONTRACT,
         (G_FROM_DESIGN_ACCEPTANCE_BY_AGENT, counter_below_ceiling("design-revisions")),
         DESIGN_WRITING, "design-revisions",
         note="the same initiator fixes the component-contract; then the program check"),
    _row("13b", DESIGN_REVIEWING, V_REJECT_CONTRACT,
         (G_FROM_DESIGN_ACCEPTANCE_BY_AGENT, counter_at_ceiling("design-revisions")),
         DESIGN_WRITING, note="split from row 13 by sections 4 and 7"),
    _row("14", DESIGN_REVIEWING, V_DISCUSS, (G_FROM_DESIGN_ACCEPTANCE_BY_USER,),
         DESIGN_WRITING, counter_note="the user's own time"),
    _row("15", DESIGN_REVIEWING, V_ADVANCE, (G_FROM_THE_LAST_ACCEPTANCE_CHECK,),
         IMPLEMENTATION_WRITING,
         note="and, if tests have begun in this design version, test-design-writing"),
    _row("16", CONTRACT_REVISING, V_EMITTED, (), CONTRACT_REVIEWING,
         counter_note="counted on entry"),
    _row("17", CONTRACT_REVISING, V_INPUT_QUICK_CHECK_FAILED, (G_AGAINST_THE_DESIGN,),
         INVESTIGATE_WORKFLOW, investigation_focus=FOCUS_DESIGN),
    _row("18", IMPLEMENTATION_WRITING, V_EMITTED, (), IMPLEMENTATION_REVIEWING,
         "implementation-writes",
         counter_note="charged by the three buckets of section 7: only a first write, "
                      "or one after a reject from review or the user's discuss"),
    _row("19", IMPLEMENTATION_WRITING, V_INPUT_QUICK_CHECK_FAILED,
         (G_AGAINST_THE_COMPONENT_CONTRACT,), CONTRACT_REVISING, "contract-revisions"),
    _row("20", IMPLEMENTATION_WRITING, V_INPUT_QUICK_CHECK_FAILED,
         (G_AGAINST_THE_DESIGN,), INVESTIGATE_WORKFLOW, investigation_focus=FOCUS_DESIGN),
    _row("21", IMPLEMENTATION_REVIEWING, V_ADVANCE,
         (G_FROM_THE_LAST_ACCEPTANCE_CHECK, G_TESTS_NOT_YET_BEGUN), TEST_DESIGN_WRITING),
    _row("22", IMPLEMENTATION_REVIEWING, V_ADVANCE,
         (G_FROM_THE_LAST_ACCEPTANCE_CHECK, G_TESTS_BEGUN, G_TEST_WORK_STREAM_READY),
         TEST_SUITE_EXECUTING),
    _row("23", IMPLEMENTATION_REVIEWING, V_ADVANCE,
         (G_FROM_THE_LAST_ACCEPTANCE_CHECK, G_TESTS_BEGUN, G_TEST_WORK_STREAM_NOT_READY),
         TO_HOLD_READY_FOR_TEST_SUITE),
    _row("24", IMPLEMENTATION_REVIEWING, V_REJECT_IMPLEMENTATION,
         (counter_below_ceiling("implementation-writes"),), IMPLEMENTATION_WRITING),
    _row("25", IMPLEMENTATION_REVIEWING, V_REJECT_IMPLEMENTATION,
         (counter_at_ceiling("implementation-writes"),), TEST_SUITE_ARBITRATING,
         counter_note="arbitrator-rulings, on entry"),
    _row("26", IMPLEMENTATION_REVIEWING, V_REJECT_CONTRACT, (), CONTRACT_REVISING,
         "contract-revisions"),
    _row("27", IMPLEMENTATION_REVIEWING, V_REJECT_DESIGN, (), INVESTIGATE_WORKFLOW,
         investigation_focus=FOCUS_DESIGN),
    _row("28", IMPLEMENTATION_REVIEWING, V_DISCUSS,
         (G_FROM_IMPLEMENTATION_ACCEPTANCE_BY_USER,), IMPLEMENTATION_WRITING,
         counter_note="the user's own time; the write it forces is counted like any other"),
    _row("29", TEST_DESIGN_WRITING, V_EMITTED, (), TEST_DESIGN_REVIEWING),
    _row("30", TEST_DESIGN_WRITING, V_INPUT_QUICK_CHECK_FAILED,
         (G_AGAINST_THE_COMPONENT_CONTRACT,), CONTRACT_REVISING, "contract-revisions"),
    _row("31", TEST_DESIGN_WRITING, V_INPUT_QUICK_CHECK_FAILED,
         (G_AGAINST_THE_DESIGN,), INVESTIGATE_WORKFLOW, investigation_focus=FOCUS_DESIGN),
    _row("32", TEST_DESIGN_REVIEWING, V_REJECT_TEST_DESIGN,
         (G_FROM_TEST_DESIGN_ACCEPTANCE_BY_AGENT,), TEST_DESIGN_WRITING,
         counter_note="a re-write before approval", note="fresh, with the notes"),
    _row("33", TEST_DESIGN_REVIEWING, V_REJECT_CONTRACT, (), CONTRACT_REVISING,
         "contract-revisions"),
    _row("34", TEST_DESIGN_REVIEWING, V_REJECT_DESIGN, (), INVESTIGATE_WORKFLOW,
         investigation_focus=FOCUS_DESIGN),
    _row("35", TEST_DESIGN_REVIEWING, V_DISCUSS, (G_FROM_TEST_DESIGN_ACCEPTANCE_BY_USER,),
         TEST_DESIGN_WRITING),
    _row("36", TEST_DESIGN_REVIEWING, V_ADVANCE, (G_FROM_THE_LAST_ACCEPTANCE_CHECK,),
         TEST_WRITING),
    _row("37", TEST_WRITING, V_EMITTED, (), TEST_REVIEWING, "test-writes",
         counter_note="charged by the three buckets of section 7, as row 18"),
    _row("38", TEST_WRITING, V_INPUT_QUICK_CHECK_FAILED,
         (G_AGAINST_THE_TEST_DESIGN, counter_below_ceiling("test-design-corrections")),
         TEST_DESIGN_WRITING, "test-design-corrections"),
    _row("39", TEST_WRITING, V_INPUT_QUICK_CHECK_FAILED,
         (G_AGAINST_THE_TEST_DESIGN, counter_at_ceiling("test-design-corrections")),
         TEST_DESIGN_ACCEPTANCE_BY_USER),
    _row("40", TEST_WRITING, V_INPUT_QUICK_CHECK_FAILED,
         (G_AGAINST_THE_COMPONENT_CONTRACT,), CONTRACT_REVISING, "contract-revisions"),
    _row("41", TEST_WRITING, V_INPUT_QUICK_CHECK_FAILED,
         (G_AGAINST_THE_DESIGN,), INVESTIGATE_WORKFLOW, investigation_focus=FOCUS_DESIGN),
    _row("42", TEST_REVIEWING, V_ADVANCE,
         (G_FROM_THE_LAST_ACCEPTANCE_CHECK, G_IMPLEMENTATION_WORK_STREAM_READY),
         TEST_SUITE_EXECUTING),
    _row("43", TEST_REVIEWING, V_ADVANCE,
         (G_FROM_THE_LAST_ACCEPTANCE_CHECK, G_IMPLEMENTATION_WORK_STREAM_NOT_READY),
         TO_HOLD_READY_FOR_TEST_SUITE),
    _row("44", TEST_REVIEWING, V_REJECT_TESTS,
         (counter_below_ceiling("test-writes"),), TEST_WRITING),
    _row("45", TEST_REVIEWING, V_REJECT_TESTS,
         (counter_at_ceiling("test-writes"),), TEST_SUITE_ARBITRATING,
         counter_note="arbitrator-rulings, on entry"),
    _row("46", TEST_REVIEWING, V_REJECT_TEST_DESIGN,
         (counter_below_ceiling("test-design-corrections"),), TEST_DESIGN_WRITING,
         "test-design-corrections"),
    _row("47", TEST_REVIEWING, V_REJECT_TEST_DESIGN,
         (counter_at_ceiling("test-design-corrections"),), TEST_DESIGN_ACCEPTANCE_BY_USER),
    _row("48", TEST_REVIEWING, V_REJECT_CONTRACT, (), CONTRACT_REVISING, "contract-revisions"),
    _row("49", TEST_REVIEWING, V_REJECT_DESIGN, (), INVESTIGATE_WORKFLOW,
         investigation_focus=FOCUS_DESIGN),
    _row("50", TEST_REVIEWING, V_DISCUSS, (G_FROM_TEST_ACCEPTANCE_BY_USER,), TEST_WRITING,
         counter_note="the user's own time"),
    _row("51", TEST_SUITE_EXECUTING, V_PASS, (), SUBMIT_TO_PR_GATE),
    _row("52", TEST_SUITE_EXECUTING, V_FAIL, (), TEST_SUITE_ARBITRATING,
         counter_note="the design's column says none; arbitrator-rulings is charged "
                      "on entry (sections 6.5 and 7)"),
    _row("53", TEST_SUITE_EXECUTING, V_COULD_NOT_RUN, (G_COULD_NOT_RUN_FIRST,),
         TO_RETRY_SAME_STATE),
    _row("54", TEST_SUITE_EXECUTING, V_COULD_NOT_RUN, (G_COULD_NOT_RUN_SECOND,),
         TEST_SUITE_ARBITRATING,
         counter_note="as row 52"),
    _row("55", TEST_SUITE_ARBITRATING, V_ADVANCE, (), SUBMIT_TO_PR_GATE,
         note="a rerun passed and the failure was the environment's"),
    _row("56", TEST_SUITE_ARBITRATING, V_REJECT_IMPLEMENTATION,
         (G_WRITERS_COUNTER_BELOW_CEILING,), IMPLEMENTATION_WRITING),
    _row("57", TEST_SUITE_ARBITRATING, (V_REJECT_TESTS, V_FLAKY_TEST),
         (G_WRITERS_COUNTER_BELOW_CEILING,), TEST_WRITING),
    _row("58", TEST_SUITE_ARBITRATING,
         (V_REJECT_IMPLEMENTATION, V_REJECT_TESTS, V_FLAKY_TEST),
         (G_WRITERS_COUNTER_AT_CEILING,), INVESTIGATE_WORKFLOW,
         investigation_focus=FOCUS_UNKNOWN, note="the ruling in the report"),
    _row("59", TEST_SUITE_ARBITRATING, V_REJECT_CONTRACT, (), CONTRACT_REVISING,
         "contract-revisions"),
    _row("60", TEST_SUITE_ARBITRATING, V_ESCALATE_TO_USER, (G_FOCUS_NOT_NAMED,),
         INVESTIGATE_WORKFLOW, investigation_focus=FOCUS_UNKNOWN),
    _row("61",
         (CONTRACT_REVIEWING, DESIGN_REVIEWING, IMPLEMENTATION_REVIEWING,
          TEST_DESIGN_REVIEWING, TEST_REVIEWING,
          CONTRACT_REVISING, TEST_DESIGN_WRITING, TEST_SUITE_ARBITRATING),
         V_ESCALATE_TO_USER,
         (G_FROM_AN_ACCEPTANCE_CHECK_BY_AGENT, G_FOCUS_NAMED_DESIGN_OR_TEST_DESIGN),
         INVESTIGATE_WORKFLOW,
         note="a reviewing sub-state by agent, contract-revising, test-design-writing "
              "or test-suite-arbitrating; investigation-focus as the agent names it"),
    _row("62", INVESTIGATE_WORKFLOW, V_STOP, (), ENDED, outcome=OUTCOME_STOPPED_BY_USER),
    _row("63", INVESTIGATE_WORKFLOW, V_SUBMIT_TO_PR_GATE, (), SUBMIT_TO_PR_GATE,
         note="the user's override; the gate still reviews"),
    _row("64", INVESTIGATE_WORKFLOW, V_RESUME,
         (G_RESUME_BELOW_REDESIGNS_CEILING_OR_NOT_TO_DESIGN_WRITING,),
         TO_RESUME_DESTINATION,
         counter_note="redesigns, if the destination is design-writing; charged on entry"),
    _row("65", INVESTIGATE_WORKFLOW, V_RESUME,
         (G_RESUME_TO_DESIGN_WRITING_AT_REDESIGNS_CEILING,), ENDED,
         outcome=OUTCOME_FAILED,
         note="the user is told in the investigation before it closes"),
    _row("66", SUBMIT_TO_PR_GATE, V_ACCEPTED, (), ENDED, outcome=OUTCOME_PASSED),
    _row("67", SUBMIT_TO_PR_GATE, V_GATE_REJECTION, (), INVESTIGATE_WORKFLOW,
         investigation_focus=FOCUS_UNKNOWN, note="the gate's findings in the report"),
    _row("68", SUBMIT_TO_PR_GATE, V_GATEKEEPER_REFUSAL,
         (G_REFUSAL_INFRASTRUCTURE, G_FEWER_THAN_FIVE_ATTEMPTS), TO_RETRY_SAME_STATE,
         note="backed off"),
    _row("69", SUBMIT_TO_PR_GATE, V_GATEKEEPER_REFUSAL,
         (G_FIFTH_INFRASTRUCTURE_ATTEMPT_OR_INTEGRATION_OR_SCOPE_REFUSAL,),
         INVESTIGATE_WORKFLOW, investigation_focus=FOCUS_UNKNOWN),
    _row("70", SUBMIT_TO_PR_GATE, V_GATEKEEPER_REFUSAL, (G_REFUSAL_FORM,),
         INVESTIGATE_WORKFLOW, investigation_focus=FOCUS_UNKNOWN,
         note="a machine error, the submit state built a bad request"),
    # Section 3.1: a reviewing state's sub-states run in order; `advance`
    # from one that is not the last goes to the next. Section 3.2 has no
    # rows for these; row 6 is the only intra-composite row it lists.
    _row("3.1-a", DESIGN_REVIEWING, V_ADVANCE,
         (G_FROM_DESIGN_ACCEPTANCE_BY_AGENT,), DESIGN_ACCEPTANCE_BY_USER, source="3.1"),
    _row("3.1-b", IMPLEMENTATION_REVIEWING, V_ADVANCE,
         (G_FROM_AN_EARLIER_ACCEPTANCE_CHECK,), IMPLEMENTATION_ACCEPTANCE_BY_USER,
         source="3.1", note="for agent-instructions only"),
    _row("3.1-c", TEST_DESIGN_REVIEWING, V_ADVANCE,
         (G_FROM_TEST_DESIGN_ACCEPTANCE_BY_AGENT,), TEST_DESIGN_ACCEPTANCE_BY_USER,
         source="3.1"),
    _row("3.1-d", TEST_REVIEWING, V_ADVANCE,
         (G_FROM_AN_EARLIER_ACCEPTANCE_CHECK,), TEST_ACCEPTANCE_BY_USER,
         source="3.1", note="for tests that are agent-instructions only"),
)

TRANSITION_TABLE_BY_ROW = {row.row: row for row in TRANSITION_TABLE}

# The design's own row numbers (source 3.2), for the coverage assertion in
# the transitions test: every one must be hit by a legality case.
DESIGN_TRANSITION_ROWS = tuple(row.row for row in TRANSITION_TABLE if row.source == "3.2")


# --- The paths of section 9 ----------------------------------------------

def design_path_while_no_code_exists(component):
    return "docs/designs/queue/%s-design.md" % component


def contract_path_while_no_code_exists(component):
    return "docs/designs/queue/%s-contract.md" % component


RECORD_DIRECTORY_NAME = "design-to-main-record"
RUN_STATE_FILE_NAME = "run-state.json"
USER_RULINGS_FILE_NAME = "user-rulings.md"

# On `resume`, the earliest state downstream of what the user changed
# (section 6.6), in the order the design lists the documents.
RESUME_DESTINATION_BY_EDITED_DOCUMENT = (
    ("design", DESIGN_WRITING),
    ("component-contract", CONTRACT_REVIEWING),
    ("test-design", TEST_DESIGN_REVIEWING),
    ("implementation", IMPLEMENTATION_REVIEWING),
    ("tests", TEST_REVIEWING),
)
