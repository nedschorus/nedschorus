#!/usr/bin/env python3
"""State, transition, and counter tables for the design-to-main machine."""

from dataclasses import dataclass
from typing import Optional, Tuple


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

# One work-stream can be ready while the other is still under review.
READY_FOR_TEST_SUITE = "ready-for-test-suite"

IMPLEMENTATION_WORK_STREAM = "implementation-work-stream"
TEST_WORK_STREAM = "test-work-stream"

OUTCOME_PASSED = "passed"
OUTCOME_STOPPED_BY_USER = "stopped-by-user"
OUTCOME_FAILED = "failed"

FOCUS_DESIGN = "design"
FOCUS_CONTRACT = "contract"
FOCUS_TEST_DESIGN = "test-design"
FOCUS_UNKNOWN = "unknown"

INPUT_DESIGN = "design"
INPUT_DESIGN_CONTRACT = "design-contract"
INPUT_TEST_DESIGN = "test-design"

REFUSAL_INFRASTRUCTURE = "infrastructure"
REFUSAL_INTEGRATION = "integration"
REFUSAL_SCOPE = "scope"
REFUSAL_FORM = "form"

COVERAGE_TYPES_THAT_ARE_AGENT_INSTRUCTIONS = ("prompt", "script-and-prompt")
# no-tests runs nothing and counts as neither pass nor fail; emit it alone when the coverage set is empty.
COVERAGE_TYPE_NO_TESTS = "no-tests"
# Only coverage-type lines are machine-readable; the rest of the test-design syntax belongs to its author.
TEST_DESIGN_COVERAGE_TYPE_LINE_PREFIX = "coverage-type:"

V_INVOKED = "invoked"
V_EMITTED = "emitted"
V_ADVANCE = "advance"
V_REJECT_CONTRACT = "reject contract"
V_REJECT_DESIGN = "reject design"
V_REJECT_IMPLEMENTATION = "reject implementation"
V_REJECT_TESTS = "reject tests"
V_REJECT_TEST_DESIGN = "reject test-design"
# Rejecting both sibling artifacts re-enters both writers.
V_REJECT_IMPLEMENTATION_AND_TESTS = "reject implementation and tests"
V_DISCUSS = "discuss"
V_REDESIGN_ORDERED_BY_USER_AFTER_CONTRACT_FAILED_TWICE = (
    "redesign-ordered-by-user-after-contract-failed-twice")  # only at contract-acceptance-by-user
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

# The one user-ruling the machine acts on; every other user-ruling is only appended to the user-rulings file.
RULING_ZERO_ALL_RUN_COUNTERS_INCLUDING_REDESIGNS = "zero-all-run-counters-including-redesigns"

WRITER_COUNTER_FOR_VERDICT = {
    V_REJECT_IMPLEMENTATION: "implementation-writes",
    V_REJECT_TESTS: "test-writes",
    V_FLAKY_TEST: "test-writes",
}
WRITER_STATE_FOR_VERDICT = {
    V_REJECT_IMPLEMENTATION: IMPLEMENTATION_WRITING,
    V_REJECT_TESTS: TEST_WRITING,
    V_FLAKY_TEST: TEST_WRITING,
}


@dataclass(frozen=True)
class StateTableRow:
    """A state and the role that performs its work."""
    name: str
    sub_states: Tuple[str, ...]
    package_beyond_standard: str
    verdicts: Tuple[str, ...]
    work: str
    work_stream: Optional[str] = None


STATE_TABLE = (
    StateTableRow(INITIATE_DESIGN_TO_MAIN, (),
                  "the user's invocation of the skill, naming the component and the design's GHI-MD",
                  (V_INVOKED,), "conversation"),
    StateTableRow(DESIGN_WRITING, (),
                  "the invocation; on a redesign, the investigation report",
                  (V_EMITTED,), "conversation"),
    StateTableRow(CONTRACT_REVIEWING,
                  (CONTRACT_ACCEPTANCE_BY_PROGRAM, CONTRACT_ACCEPTANCE_BY_AGENT,
                   CONTRACT_ACCEPTANCE_BY_USER),
                  "the previous version and the notes, on a revision",
                  (V_ADVANCE, V_REJECT_CONTRACT, V_DISCUSS,
                   V_REDESIGN_ORDERED_BY_USER_AFTER_CONTRACT_FAILED_TWICE), "composite"),
    StateTableRow(DESIGN_REVIEWING,
                  (DESIGN_ACCEPTANCE_BY_AGENT, DESIGN_ACCEPTANCE_BY_USER),
                  "on a second review, the previous reviewer's notes and the writer's notes",
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
                  "the implementation's files; on a second review, the previous reviewer's notes and the writer's notes",
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
                  "the test-design; on a second review, the previous reviewer's notes and the writer's notes",
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
                  "the test-design; the tests' files; on a second review, the previous reviewer's notes and the writer's notes",
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
                   V_REJECT_IMPLEMENTATION_AND_TESTS,
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

COMPOSITE_STATE_OF_SUB_STATE = {
    sub_state: row.name for row in STATE_TABLE for sub_state in row.sub_states
}

ACCEPTANCE_CHECKS_BY_AGENT = tuple(
    s for s in COMPOSITE_STATE_OF_SUB_STATE if s.endswith("-acceptance-by-agent"))
STATES_WITH_ESCALATE_TO_USER = (
    CONTRACT_REVISING, TEST_DESIGN_WRITING, TEST_SUITE_ARBITRATING)

WRITING_STATES = (CONTRACT_REVISING, IMPLEMENTATION_WRITING,
                  TEST_DESIGN_WRITING, TEST_WRITING)
# Design-writing emits artifacts but does not use the four writing states' counter buckets.
WRITING_STATES_INCLUDING_DESIGN_WRITING = (DESIGN_WRITING,) + WRITING_STATES
COUNTED_WRITING_STATES = {
    IMPLEMENTATION_WRITING: "implementation-writes",
    TEST_WRITING: "test-writes",
}



@dataclass(frozen=True)
class CounterCeilingRule:
    """A counter ceiling and the value at which the ceiling guard applies."""
    # Revision counters stop one below the stated ceiling: the original and one revision exhaust the allowance.
    name: str
    increments_when: str
    ceiling: int
    at_ceiling_from_value: int
    at_the_ceiling: str
    per_design_version: bool = True
    # User discussion can force counted writes past the ceiling; only the two write counters allow this.
    may_be_taken_past_its_ceiling_by_the_users_discuss: bool = False


COUNTER_TABLE = (
    CounterCeilingRule(
        "redesigns",
        "`design-writing` is entered from `investigate-workflow`",
        2, 2, "`ended`, outcome `failed`", per_design_version=False),
    CounterCeilingRule(
        "design-revisions",
        "`design-acceptance-by-agent` rejects the design or the design-contract "
        "before the design's approval",
        2, 2, "the initiator brings the user into the conversation with every set of notes"),
    CounterCeilingRule(
        "implementation-writes",
        "`implementation-writing` emits `emitted` after a `reject implementation` "
        "from review, or as the first write",
        3, 3, "the third write, when it fails review, goes to `test-suite-arbitrating`; "
              "a write the user's discuss forces may take it past three, and "
              "\"at its ceiling\" reads at or above",
        may_be_taken_past_its_ceiling_by_the_users_discuss=True),
    CounterCeilingRule(
        "test-writes",
        "`test-writing` emits `emitted` after a `reject tests` from review, "
        "or as the first write",
        3, 3, "the same; at or above, as above",
        may_be_taken_past_its_ceiling_by_the_users_discuss=True),
    CounterCeilingRule(
        "arbitrator-rulings",
        "`test-suite-arbitrating` is entered",
        2, 2, "the third entry opens the investigation with the user, launching no "
              "arbitrator here; the investigation's arbitrator rules, and its ruling rides "
              "in the report and on its resume. A write the arbitrator orders is bounded by "
              "this counter, not the writer's, whose counter stops deciding once the "
              "arbitrator is in and is not reset"),
    CounterCeilingRule(
        "contract-revisions",
        "`contract-revising` is entered after a rejection or a failed check against "
        "the design-contract, once the design is approved",
        2, 1, "`contract-acceptance-by-user`: one revision; the user is called after "
              "the original and one contract-revision have both failed review, and no "
              "second is written"),
    CounterCeilingRule(
        "test-design-corrections",
        "`test-design-writing` is re-entered after a rejection or a failed check "
        "against the test-design, once the test-design is approved",
        2, 1, "`test-design-acceptance-by-user`: one correction; the user is called after "
              "the approved test-design and one correction have both failed, and no "
              "second is written"),
)

COUNTER_TABLE_BY_NAME = {rule.name: rule for rule in COUNTER_TABLE}
COUNTER_NAMES = tuple(rule.name for rule in COUNTER_TABLE)

COUNTER_CHARGED_ON_ENTRY = {
    TEST_SUITE_ARBITRATING: "arbitrator-rulings",
    # Count redesigns only when entered from investigate-workflow.
    DESIGN_WRITING: "redesigns",
}

# Charge emitted writes by re-entry reason; arbitrator and document-rewrite buckets were already charged upstream.
BUCKET_FAILED_REVIEW = "failed-review"
BUCKET_ARBITRATOR_RULED = "arbitrator-ruled"
BUCKET_UPSTREAM_DOCUMENT_CHANGED = "upstream-document-changed"

DISCARDED_WRITE_BUCKETS = {
    BUCKET_FAILED_REVIEW: "the writer's counter",
    BUCKET_ARBITRATOR_RULED: "arbitrator-rulings",
    BUCKET_UPSTREAM_DOCUMENT_CHANGED: "that document's counter, and nothing else",
}

ENTRY_REASON_FIRST_WRITE = "first-write"
ENTRY_REASON_REJECT_FROM_REVIEW = "reject-from-review"
ENTRY_REASON_DISCUSS_BY_USER = "discuss-by-user"
ENTRY_REASON_ARBITRATOR_RULING = "arbitrator-ruling"
ENTRY_REASON_CONTRACT_REVISION = "contract-revision"
ENTRY_REASON_TEST_DESIGN_CORRECTION = "test-design-correction"
ENTRY_REASON_DESIGN_CHANGED_UPSTREAM = "design-changed-upstream"
ENTRY_REASON_USER_NAMED_DESTINATION = "user-named-destination"

WRITING_STATE_ENTRY_REASON_TO_BUCKET = {
    ENTRY_REASON_FIRST_WRITE: BUCKET_FAILED_REVIEW,
    ENTRY_REASON_REJECT_FROM_REVIEW: BUCKET_FAILED_REVIEW,
    ENTRY_REASON_DISCUSS_BY_USER: BUCKET_FAILED_REVIEW,
    ENTRY_REASON_ARBITRATOR_RULING: BUCKET_ARBITRATOR_RULED,
    ENTRY_REASON_CONTRACT_REVISION: BUCKET_UPSTREAM_DOCUMENT_CHANGED,
    ENTRY_REASON_TEST_DESIGN_CORRECTION: BUCKET_UPSTREAM_DOCUMENT_CHANGED,
    ENTRY_REASON_DESIGN_CHANGED_UPSTREAM: BUCKET_UPSTREAM_DOCUMENT_CHANGED,
    # A writing state selected by the user on resume is uncounted.
    ENTRY_REASON_USER_NAMED_DESTINATION: BUCKET_UPSTREAM_DOCUMENT_CHANGED,
}



TO_HOLD_READY_FOR_TEST_SUITE = "hold at ready-for-test-suite"
TO_BOTH_WORK_STREAMS_RE_ENTER = "both work-streams re-enter their writing states"
TO_RESUME_DESTINATION = "the resume destination (section 6.6)"
# A resume without a destination applies the held ruling without re-entering the arbitrator.
TO_APPLY_THE_HELD_RULING = "the ruling the arbitrator held in its report (section 6.6)"
RESUME_MAY_NOT_NAME = (ENDED, INITIATE_DESIGN_TO_MAIN)
# A held ruling cannot escalate: the arbitrator is already consulting the user.
HELD_RULINGS_A_RESUME_MAY_CARRY = (
    V_REJECT_IMPLEMENTATION, V_REJECT_TESTS, V_REJECT_IMPLEMENTATION_AND_TESTS,
    V_FLAKY_TEST, V_REJECT_CONTRACT, V_ADVANCE)
TO_RETRY_SAME_STATE = "the same state (retry)"
TO_THE_NEXT_ACCEPTANCE_CHECK = "the state's next acceptance-check, in the order section 3.1 lists"
TO_THE_WRITER_THE_VERDICT_NAMES = "that writer anyway, fresh"
TO_BOTH_WRITERS_FRESH = "both writers, fresh"
# An arbitrator advance overturns the rejecting reviewer and follows that reviewer's advance route.
TO_WHEREVER_THAT_REVIEWING_STATES_ADVANCE_GOES = (
    "wherever that reviewing state's own advance goes")

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
G_AGAINST_THE_DESIGN_CONTRACT = "against the design-contract"
G_AGAINST_THE_TEST_DESIGN = "against the test-design"
G_A_REJECT_OF_OR_A_FAILED_CHECK_AGAINST_THE_DESIGN_CONTRACT = (
    "a reject of, or a failed check against, the design-contract")
G_TESTS_NOT_YET_BEGUN = "tests not yet begun"
G_TESTS_BEGUN = "tests begun"
G_TEST_WORK_STREAM_READY = "the test-work-stream at ready-for-test-suite"
G_TEST_WORK_STREAM_NOT_READY = "the test-work-stream not yet there"
G_IMPLEMENTATION_WORK_STREAM_READY = "the implementation-work-stream at ready-for-test-suite"
G_IMPLEMENTATION_WORK_STREAM_NOT_READY = "the implementation-work-stream not yet there"
G_COULD_NOT_RUN_FIRST = "the first of consecutive entries"
G_COULD_NOT_RUN_SECOND = "the second consecutive"
# An advance is valid only after a reviewer ceiling, never after a failed or unrun suite.
G_ENTERED_FROM_A_REVIEWERS_CEILING = "entered from a reviewer's ceiling"
# Test-design rejection is uncounted before approval and a test-design-correction afterward.
G_BEFORE_THE_TEST_DESIGNS_APPROVAL = "before the test-design's approval"
G_AFTER_THE_TEST_DESIGNS_APPROVAL = "after the test-design's approval"
G_WRITERS_COUNTER_BELOW_CEILING = "the writer's counter below its ceiling"
G_WRITERS_COUNTER_AT_OR_ABOVE_CEILING = "the writer's counter at or above its ceiling"
# The reject route reads only the writer's counter; arbitrator entries are bounded separately.
G_FOCUS_NAMED_DESIGN_OR_TEST_DESIGN = "investigation-focus design or test-design as the agent names it"
G_FOCUS_NOT_NAMED = "no investigation-focus named by the agent"
G_ENTERED_FOR_THE_THIRD_TIME_IN_THE_DESIGN_VERSION = (
    "entered for the third time in the design version")
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


def counter_at_or_above_ceiling(name):
    # The design uses a separate name for write ceilings because a user discussion can force writes past them.
    return "the %s counter at or above its ceiling" % name


# Diagram views retain the design's display order.
DIAGRAM_VIEW_MAIN_PATH = "main-path"
DIAGRAM_VIEW_REWORK_AND_ARBITRATION = "rework-and-arbitration"
DIAGRAM_VIEW_INVESTIGATION = "investigation"
DIAGRAM_VIEW_INSIDE_THE_REVIEWING_STATES = "inside-the-reviewing-states"
# Retry loops, user discussion returns, and arbitrator advances are omitted from the diagrams.
DIAGRAM_VIEW_NOT_DRAWN = "not-drawn"
DIAGRAM_VIEWS_DRAWN = (
    DIAGRAM_VIEW_MAIN_PATH, DIAGRAM_VIEW_REWORK_AND_ARBITRATION,
    DIAGRAM_VIEW_INVESTIGATION, DIAGRAM_VIEW_INSIDE_THE_REVIEWING_STATES)


@dataclass(frozen=True)
class TransitionTableRow:
    """A transition with its guard, destination, counter effect, and diagram view."""
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
    view: Optional[str] = None


def _row(row, from_states, verdicts, guards, to_state, counter=None, **kw):
    if isinstance(from_states, str):
        from_states = (from_states,)
    if isinstance(verdicts, str):
        verdicts = (verdicts,)
    return TransitionTableRow(row, tuple(from_states), tuple(verdicts),
                              tuple(guards), to_state, counter, **kw)


TRANSITION_TABLE = (
    _row("1", INITIATE_DESIGN_TO_MAIN, V_INVOKED, (), DESIGN_WRITING,
         note="after the machine has cut the topic branch (section 9)",
         view=DIAGRAM_VIEW_MAIN_PATH),
    _row("2", DESIGN_WRITING, V_EMITTED, (), CONTRACT_REVIEWING,
         counter_note="redesigns are counted on entry, not here",
         note="program check only",
         view=DIAGRAM_VIEW_MAIN_PATH),
    _row("3", CONTRACT_REVIEWING, V_REJECT_CONTRACT,
         (G_FROM_PROGRAM_CHECK, G_FIRST_TIME), CONTRACT_REVISING,
         counter_note="not counted; a structural failure",
         view=DIAGRAM_VIEW_REWORK_AND_ARBITRATION),
    _row("4", CONTRACT_REVIEWING, V_REJECT_CONTRACT,
         (G_FROM_PROGRAM_CHECK, G_SECOND_CONSECUTIVE_TIME), INVESTIGATE_WORKFLOW,
         investigation_focus=FOCUS_CONTRACT,
         view=DIAGRAM_VIEW_INVESTIGATION),
    _row("5", CONTRACT_REVIEWING, V_ADVANCE,
         (G_FROM_PROGRAM_CHECK, G_DESIGN_NOT_YET_APPROVED), DESIGN_REVIEWING,
         view=DIAGRAM_VIEW_MAIN_PATH),
    _row("6", CONTRACT_REVIEWING, V_ADVANCE,
         (G_FROM_PROGRAM_CHECK, G_ON_A_CONTRACT_REVISION), CONTRACT_ACCEPTANCE_BY_AGENT,
         view=DIAGRAM_VIEW_INSIDE_THE_REVIEWING_STATES),
    _row("7", CONTRACT_REVIEWING, V_REJECT_CONTRACT,
         (G_FROM_CONTRACT_ACCEPTANCE_BY_AGENT, counter_below_ceiling("contract-revisions")),
         CONTRACT_REVISING, "contract-revisions",
         view=DIAGRAM_VIEW_REWORK_AND_ARBITRATION),
    _row("8", CONTRACT_REVIEWING, V_REJECT_CONTRACT,
         (G_FROM_CONTRACT_ACCEPTANCE_BY_AGENT, counter_at_ceiling("contract-revisions")),
         CONTRACT_ACCEPTANCE_BY_USER,
         view=DIAGRAM_VIEW_INSIDE_THE_REVIEWING_STATES),
    _row("9", CONTRACT_REVIEWING, V_ADVANCE,
         (G_FROM_CONTRACT_ACCEPTANCE_BY_AGENT_OR_USER, G_ON_A_CONTRACT_REVISION),
         TO_BOTH_WORK_STREAMS_RE_ENTER, note="the revised-contract invalidation rule",
         view=DIAGRAM_VIEW_REWORK_AND_ARBITRATION),
    _row("10", CONTRACT_REVIEWING, V_DISCUSS, (G_FROM_CONTRACT_ACCEPTANCE_BY_USER,),
         CONTRACT_REVISING, counter_note="the user's own time",
         view=DIAGRAM_VIEW_NOT_DRAWN),
    _row("11", CONTRACT_REVIEWING, V_REDESIGN_ORDERED_BY_USER_AFTER_CONTRACT_FAILED_TWICE,
         (G_FROM_CONTRACT_ACCEPTANCE_BY_USER,),
         INVESTIGATE_WORKFLOW, investigation_focus=FOCUS_CONTRACT,
         counter_note="redesigns, on entry to design-writing",
         note="then design-writing as a redesign: the investigation holds design-writing "
              "as its resume destination (section 6.6), the redesigns ceiling deciding at "
              "the resume (rows 72, 73)",
         view=DIAGRAM_VIEW_INVESTIGATION),
    _row("12", DESIGN_REVIEWING, V_REJECT_DESIGN,
         (G_FROM_DESIGN_ACCEPTANCE_BY_AGENT, counter_below_ceiling("design-revisions")),
         DESIGN_WRITING, "design-revisions", note="the same initiator; it revises alone",
         view=DIAGRAM_VIEW_REWORK_AND_ARBITRATION),
    _row("13", DESIGN_REVIEWING, V_REJECT_DESIGN,
         (G_FROM_DESIGN_ACCEPTANCE_BY_AGENT, counter_at_ceiling("design-revisions")),
         DESIGN_WRITING, note="the same initiator brings the user into the conversation",
         view=DIAGRAM_VIEW_REWORK_AND_ARBITRATION),
    _row("14", DESIGN_REVIEWING, V_REJECT_CONTRACT,
         (G_FROM_DESIGN_ACCEPTANCE_BY_AGENT, counter_below_ceiling("design-revisions")),
         DESIGN_WRITING, "design-revisions",
         note="the same initiator fixes the design-contract; then the program check",
         view=DIAGRAM_VIEW_REWORK_AND_ARBITRATION),
    _row("15", DESIGN_REVIEWING, V_REJECT_CONTRACT,
         (G_FROM_DESIGN_ACCEPTANCE_BY_AGENT, counter_at_ceiling("design-revisions")),
         DESIGN_WRITING, note="the same initiator brings the user into the conversation",
         view=DIAGRAM_VIEW_REWORK_AND_ARBITRATION),
    # Contract-reviewing has separate routes: only rejection at the revision ceiling reaches the user check.
    _row("16", (DESIGN_REVIEWING, IMPLEMENTATION_REVIEWING,
                TEST_DESIGN_REVIEWING, TEST_REVIEWING),
         V_ADVANCE, (G_FROM_AN_EARLIER_ACCEPTANCE_CHECK,), TO_THE_NEXT_ACCEPTANCE_CHECK,
         note="any reviewing state whose next check the design lists nowhere else; "
              "the user's check of an implementation or of tests exists only for "
              "agent-instructions (section 3.1)",
         view=DIAGRAM_VIEW_INSIDE_THE_REVIEWING_STATES),
    _row("17", DESIGN_REVIEWING, V_DISCUSS, (G_FROM_DESIGN_ACCEPTANCE_BY_USER,),
         DESIGN_WRITING, counter_note="the user's own time",
         view=DIAGRAM_VIEW_NOT_DRAWN),
    _row("18", DESIGN_REVIEWING, V_ADVANCE, (G_FROM_THE_LAST_ACCEPTANCE_CHECK,),
         IMPLEMENTATION_WRITING,
         view=DIAGRAM_VIEW_MAIN_PATH),
    _row("19", CONTRACT_REVISING, V_EMITTED, (), CONTRACT_REVIEWING,
         counter_note="counted on entry",
         view=DIAGRAM_VIEW_REWORK_AND_ARBITRATION),
    _row("20", CONTRACT_REVISING, V_INPUT_QUICK_CHECK_FAILED, (G_AGAINST_THE_DESIGN,),
         INVESTIGATE_WORKFLOW, investigation_focus=FOCUS_DESIGN,
         view=DIAGRAM_VIEW_INVESTIGATION),
    _row("21", IMPLEMENTATION_WRITING, V_EMITTED, (), IMPLEMENTATION_REVIEWING,
         "implementation-writes",
         counter_note="only when the state was entered by a reject implementation from "
                      "review, by the user's discuss, or as the first write; a write "
                      "forced by an upstream change or ordered by the arbitrator charges "
                      "nothing here (section 7, the three buckets)",
         view=DIAGRAM_VIEW_MAIN_PATH),
    _row("22", IMPLEMENTATION_WRITING, V_INPUT_QUICK_CHECK_FAILED,
         (G_AGAINST_THE_DESIGN_CONTRACT, counter_below_ceiling("contract-revisions")),
         CONTRACT_REVISING, "contract-revisions",
         view=DIAGRAM_VIEW_REWORK_AND_ARBITRATION),
    _row("23", IMPLEMENTATION_WRITING, V_INPUT_QUICK_CHECK_FAILED,
         (G_AGAINST_THE_DESIGN,), INVESTIGATE_WORKFLOW, investigation_focus=FOCUS_DESIGN,
         view=DIAGRAM_VIEW_INVESTIGATION),
    _row("24", IMPLEMENTATION_REVIEWING, V_ADVANCE,
         (G_FROM_THE_LAST_ACCEPTANCE_CHECK, G_TESTS_NOT_YET_BEGUN), TEST_DESIGN_WRITING,
         view=DIAGRAM_VIEW_MAIN_PATH),
    _row("25", IMPLEMENTATION_REVIEWING, V_ADVANCE,
         (G_FROM_THE_LAST_ACCEPTANCE_CHECK, G_TESTS_BEGUN, G_TEST_WORK_STREAM_READY),
         TEST_SUITE_EXECUTING,
         view=DIAGRAM_VIEW_REWORK_AND_ARBITRATION),
    _row("26", IMPLEMENTATION_REVIEWING, V_ADVANCE,
         (G_FROM_THE_LAST_ACCEPTANCE_CHECK, G_TESTS_BEGUN, G_TEST_WORK_STREAM_NOT_READY),
         TO_HOLD_READY_FOR_TEST_SUITE,
         view=DIAGRAM_VIEW_REWORK_AND_ARBITRATION),
    _row("27", IMPLEMENTATION_REVIEWING, V_REJECT_IMPLEMENTATION,
         (counter_below_ceiling("implementation-writes"),), IMPLEMENTATION_WRITING,
         view=DIAGRAM_VIEW_REWORK_AND_ARBITRATION),
    _row("28", IMPLEMENTATION_REVIEWING, V_REJECT_IMPLEMENTATION,
         (counter_at_or_above_ceiling("implementation-writes"),), TEST_SUITE_ARBITRATING,
         counter_note="arbitrator-rulings, on entry",
         view=DIAGRAM_VIEW_REWORK_AND_ARBITRATION),
    _row("29", IMPLEMENTATION_REVIEWING, V_REJECT_CONTRACT, (counter_below_ceiling("contract-revisions"),),
         CONTRACT_REVISING, "contract-revisions",
         view=DIAGRAM_VIEW_REWORK_AND_ARBITRATION),
    _row("30", IMPLEMENTATION_REVIEWING, V_REJECT_DESIGN, (), INVESTIGATE_WORKFLOW,
         investigation_focus=FOCUS_DESIGN,
         view=DIAGRAM_VIEW_INVESTIGATION),
    _row("31", IMPLEMENTATION_REVIEWING, V_DISCUSS,
         (G_FROM_IMPLEMENTATION_ACCEPTANCE_BY_USER,), IMPLEMENTATION_WRITING,
         counter_note="the user's own time; the write it forces is counted like any other, "
                      "and may take the counter past its ceiling (section 6.6)",
         view=DIAGRAM_VIEW_NOT_DRAWN),
    _row("32", TEST_DESIGN_WRITING, V_EMITTED, (), TEST_DESIGN_REVIEWING,
         view=DIAGRAM_VIEW_MAIN_PATH),
    _row("33", TEST_DESIGN_WRITING, V_INPUT_QUICK_CHECK_FAILED,
         (G_AGAINST_THE_DESIGN_CONTRACT, counter_below_ceiling("contract-revisions")),
         CONTRACT_REVISING, "contract-revisions",
         view=DIAGRAM_VIEW_REWORK_AND_ARBITRATION),
    _row("34", TEST_DESIGN_WRITING, V_INPUT_QUICK_CHECK_FAILED,
         (G_AGAINST_THE_DESIGN,), INVESTIGATE_WORKFLOW, investigation_focus=FOCUS_DESIGN,
         view=DIAGRAM_VIEW_INVESTIGATION),
    _row("35", TEST_DESIGN_REVIEWING, V_REJECT_TEST_DESIGN,
         (G_FROM_TEST_DESIGN_ACCEPTANCE_BY_AGENT, G_BEFORE_THE_TEST_DESIGNS_APPROVAL),
         TEST_DESIGN_WRITING,
         counter_note="a re-write before approval", note="with the notes",
         view=DIAGRAM_VIEW_REWORK_AND_ARBITRATION),
    _row("36", TEST_DESIGN_REVIEWING, V_REJECT_TEST_DESIGN,
         (G_FROM_TEST_DESIGN_ACCEPTANCE_BY_AGENT, G_AFTER_THE_TEST_DESIGNS_APPROVAL,
          counter_below_ceiling("test-design-corrections")),
         TEST_DESIGN_WRITING, "test-design-corrections",
         counter_note="section 7; user-ruled 2026-09-14, the tenth walk, item 7",
         note="with the notes",
         view=DIAGRAM_VIEW_REWORK_AND_ARBITRATION),
    _row("37", TEST_DESIGN_REVIEWING, V_REJECT_TEST_DESIGN,
         (G_FROM_TEST_DESIGN_ACCEPTANCE_BY_AGENT, G_AFTER_THE_TEST_DESIGNS_APPROVAL,
          counter_at_ceiling("test-design-corrections")),
         TEST_DESIGN_ACCEPTANCE_BY_USER,
         view=DIAGRAM_VIEW_INSIDE_THE_REVIEWING_STATES),
    _row("38", TEST_DESIGN_REVIEWING, V_REJECT_CONTRACT, (counter_below_ceiling("contract-revisions"),),
         CONTRACT_REVISING, "contract-revisions",
         view=DIAGRAM_VIEW_REWORK_AND_ARBITRATION),
    _row("39", TEST_DESIGN_REVIEWING, V_REJECT_DESIGN, (), INVESTIGATE_WORKFLOW,
         investigation_focus=FOCUS_DESIGN,
         view=DIAGRAM_VIEW_INVESTIGATION),
    _row("40", TEST_DESIGN_REVIEWING, V_DISCUSS, (G_FROM_TEST_DESIGN_ACCEPTANCE_BY_USER,),
         TEST_DESIGN_WRITING,
         view=DIAGRAM_VIEW_NOT_DRAWN),
    _row("41", TEST_DESIGN_REVIEWING, V_ADVANCE, (G_FROM_THE_LAST_ACCEPTANCE_CHECK,),
         TEST_WRITING,
         view=DIAGRAM_VIEW_MAIN_PATH),
    _row("42", TEST_WRITING, V_EMITTED, (), TEST_REVIEWING, "test-writes",
         counter_note="on the same rule as row 21",
         view=DIAGRAM_VIEW_MAIN_PATH),
    _row("43", TEST_WRITING, V_INPUT_QUICK_CHECK_FAILED,
         (G_AGAINST_THE_TEST_DESIGN, counter_below_ceiling("test-design-corrections")),
         TEST_DESIGN_WRITING, "test-design-corrections",
         view=DIAGRAM_VIEW_REWORK_AND_ARBITRATION),
    _row("44", TEST_WRITING, V_INPUT_QUICK_CHECK_FAILED,
         (G_AGAINST_THE_TEST_DESIGN, counter_at_ceiling("test-design-corrections")),
         TEST_DESIGN_ACCEPTANCE_BY_USER,
         view=DIAGRAM_VIEW_INSIDE_THE_REVIEWING_STATES),
    _row("45", TEST_WRITING, V_INPUT_QUICK_CHECK_FAILED,
         (G_AGAINST_THE_DESIGN_CONTRACT, counter_below_ceiling("contract-revisions")),
         CONTRACT_REVISING, "contract-revisions",
         view=DIAGRAM_VIEW_REWORK_AND_ARBITRATION),
    _row("46", TEST_WRITING, V_INPUT_QUICK_CHECK_FAILED,
         (G_AGAINST_THE_DESIGN,), INVESTIGATE_WORKFLOW, investigation_focus=FOCUS_DESIGN,
         view=DIAGRAM_VIEW_INVESTIGATION),
    _row("47", TEST_REVIEWING, V_ADVANCE,
         (G_FROM_THE_LAST_ACCEPTANCE_CHECK, G_IMPLEMENTATION_WORK_STREAM_READY),
         TEST_SUITE_EXECUTING,
         view=DIAGRAM_VIEW_MAIN_PATH),
    _row("48", TEST_REVIEWING, V_ADVANCE,
         (G_FROM_THE_LAST_ACCEPTANCE_CHECK, G_IMPLEMENTATION_WORK_STREAM_NOT_READY),
         TO_HOLD_READY_FOR_TEST_SUITE,
         view=DIAGRAM_VIEW_REWORK_AND_ARBITRATION),
    _row("49", TEST_REVIEWING, V_REJECT_TESTS,
         (counter_below_ceiling("test-writes"),), TEST_WRITING,
         view=DIAGRAM_VIEW_REWORK_AND_ARBITRATION),
    _row("50", TEST_REVIEWING, V_REJECT_TESTS,
         (counter_at_or_above_ceiling("test-writes"),), TEST_SUITE_ARBITRATING,
         counter_note="arbitrator-rulings, on entry",
         view=DIAGRAM_VIEW_REWORK_AND_ARBITRATION),
    _row("51", TEST_REVIEWING, V_REJECT_TEST_DESIGN,
         (counter_below_ceiling("test-design-corrections"),), TEST_DESIGN_WRITING,
         "test-design-corrections",
         view=DIAGRAM_VIEW_REWORK_AND_ARBITRATION),
    _row("52", TEST_REVIEWING, V_REJECT_TEST_DESIGN,
         (counter_at_ceiling("test-design-corrections"),), TEST_DESIGN_ACCEPTANCE_BY_USER,
         view=DIAGRAM_VIEW_INSIDE_THE_REVIEWING_STATES),
    _row("53", TEST_REVIEWING, V_REJECT_CONTRACT, (counter_below_ceiling("contract-revisions"),),
         CONTRACT_REVISING, "contract-revisions",
         view=DIAGRAM_VIEW_REWORK_AND_ARBITRATION),
    _row("54", TEST_REVIEWING, V_REJECT_DESIGN, (), INVESTIGATE_WORKFLOW,
         investigation_focus=FOCUS_DESIGN,
         view=DIAGRAM_VIEW_INVESTIGATION),
    _row("55", TEST_REVIEWING, V_DISCUSS, (G_FROM_TEST_ACCEPTANCE_BY_USER,), TEST_WRITING,
         counter_note="the user's own time",
         view=DIAGRAM_VIEW_NOT_DRAWN),
    _row("56", TEST_SUITE_EXECUTING, V_PASS, (), SUBMIT_TO_PR_GATE,
         view=DIAGRAM_VIEW_MAIN_PATH),
    _row("57", TEST_SUITE_EXECUTING, V_FAIL, (), TEST_SUITE_ARBITRATING,
         counter_note="arbitrator-rulings, charged on entry to test-suite-arbitrating "
                      "(sections 6.5 and 7; COUNTER_CHARGED_ON_ENTRY)",
         view=DIAGRAM_VIEW_REWORK_AND_ARBITRATION),
    _row("58", TEST_SUITE_EXECUTING, V_COULD_NOT_RUN, (G_COULD_NOT_RUN_FIRST,),
         TO_RETRY_SAME_STATE,
         view=DIAGRAM_VIEW_NOT_DRAWN),
    _row("59", TEST_SUITE_EXECUTING, V_COULD_NOT_RUN, (G_COULD_NOT_RUN_SECOND,),
         TEST_SUITE_ARBITRATING,
         counter_note="as row 57",
         view=DIAGRAM_VIEW_REWORK_AND_ARBITRATION),
    _row("60", TEST_SUITE_ARBITRATING, V_ADVANCE,
         (G_ENTERED_FROM_A_REVIEWERS_CEILING,), TO_WHEREVER_THAT_REVIEWING_STATES_ADVANCE_GOES,
         note="the reviewer was wrong (section 6.5): the artifact continues as if the "
              "reviewer had advanced it",
         view=DIAGRAM_VIEW_NOT_DRAWN),
    _row("61", TEST_SUITE_ARBITRATING, V_REJECT_IMPLEMENTATION,
         (G_WRITERS_COUNTER_BELOW_CEILING,), IMPLEMENTATION_WRITING,
         counter_note="arbitrator-rulings, charged on entry to test-suite-arbitrating, "
                      "as every row of this state; the write it orders is the "
                      "arbitrator's bucket",
         view=DIAGRAM_VIEW_REWORK_AND_ARBITRATION),
    _row("62", TEST_SUITE_ARBITRATING, (V_REJECT_TESTS, V_FLAKY_TEST),
         (G_WRITERS_COUNTER_BELOW_CEILING,), TEST_WRITING,
         counter_note="as row 61",
         view=DIAGRAM_VIEW_REWORK_AND_ARBITRATION),
    _row("63", TEST_SUITE_ARBITRATING, (V_REJECT_IMPLEMENTATION, V_REJECT_TESTS, V_FLAKY_TEST),
         (G_WRITERS_COUNTER_AT_OR_ABOVE_CEILING,),
         TO_THE_WRITER_THE_VERDICT_NAMES,
         counter_note="the writer's counter stops deciding and is not reset; the write "
                      "is bounded by arbitrator-rulings, and past that by the user's "
                      "resume (section 7)",
         view=DIAGRAM_VIEW_REWORK_AND_ARBITRATION),
    _row("64", TEST_SUITE_ARBITRATING, V_REJECT_IMPLEMENTATION_AND_TESTS,
         (),
         TO_BOTH_WRITERS_FRESH,
         counter_note="each write bounded as row 63",
         note="both artifacts contradicting the design-contract; the "
              "implementation-work-stream runs first (section 3.1)",
         view=DIAGRAM_VIEW_REWORK_AND_ARBITRATION),
    # Apply this ceiling on entry, before launching the arbitrator; no verdict is required.
    _row("65", TEST_SUITE_ARBITRATING, (),
         (G_ENTERED_FOR_THE_THIRD_TIME_IN_THE_DESIGN_VERSION,), INVESTIGATE_WORKFLOW,
         investigation_focus=FOCUS_UNKNOWN,
         note="no arbitrator launched here; the investigation's arbitrator rules, and "
              "the ruling it would have made rides in its report and on its resume "
              "state-exit as held-ruling (section 6.6); applied on entry (sections 6.5, 7)",
         view=DIAGRAM_VIEW_INVESTIGATION),
    _row("66", TEST_SUITE_ARBITRATING, V_REJECT_CONTRACT, (counter_below_ceiling("contract-revisions"),),
         CONTRACT_REVISING, "contract-revisions",
         view=DIAGRAM_VIEW_REWORK_AND_ARBITRATION),
    _row("67",
         (IMPLEMENTATION_WRITING, IMPLEMENTATION_REVIEWING, TEST_DESIGN_WRITING,
          TEST_DESIGN_REVIEWING, TEST_WRITING, TEST_REVIEWING, TEST_SUITE_ARBITRATING),
         (V_REJECT_CONTRACT, V_INPUT_QUICK_CHECK_FAILED),
         (G_A_REJECT_OF_OR_A_FAILED_CHECK_AGAINST_THE_DESIGN_CONTRACT,
          counter_at_ceiling("contract-revisions")),
         CONTRACT_ACCEPTANCE_BY_USER,
         note="any state above (sections 5.3, 6.6); contract-reviewing's own is row 8, "
              "and design-reviewing's rejects of the contract are rows 14 and 15",
         view=DIAGRAM_VIEW_INSIDE_THE_REVIEWING_STATES),
    _row("68", TEST_SUITE_ARBITRATING, V_ESCALATE_TO_USER, (G_FOCUS_NOT_NAMED,),
         INVESTIGATE_WORKFLOW, investigation_focus=FOCUS_UNKNOWN,
         view=DIAGRAM_VIEW_INVESTIGATION),
    _row("69",
         (CONTRACT_REVIEWING, DESIGN_REVIEWING, IMPLEMENTATION_REVIEWING,
          TEST_DESIGN_REVIEWING, TEST_REVIEWING,
          CONTRACT_REVISING, TEST_DESIGN_WRITING, TEST_SUITE_ARBITRATING),
         V_ESCALATE_TO_USER,
         (G_FROM_AN_ACCEPTANCE_CHECK_BY_AGENT, G_FOCUS_NAMED_DESIGN_OR_TEST_DESIGN),
         INVESTIGATE_WORKFLOW,
         note="a reviewing sub-state by agent, contract-revising, test-design-writing "
              "or test-suite-arbitrating; investigation-focus as the agent names it",
         view=DIAGRAM_VIEW_INVESTIGATION),
    _row("70", INVESTIGATE_WORKFLOW, V_STOP, (), ENDED, outcome=OUTCOME_STOPPED_BY_USER,
         view=DIAGRAM_VIEW_INVESTIGATION),
    _row("71", INVESTIGATE_WORKFLOW, V_SUBMIT_TO_PR_GATE, (), SUBMIT_TO_PR_GATE,
         note="the user's override; the gate still reviews",
         view=DIAGRAM_VIEW_INVESTIGATION),
    _row("72", INVESTIGATE_WORKFLOW, V_RESUME,
         (G_RESUME_BELOW_REDESIGNS_CEILING_OR_NOT_TO_DESIGN_WRITING,),
         TO_RESUME_DESTINATION,
         counter_note="redesigns, if the destination is design-writing; charged on entry. "
                      "The six per-version counters start from zero on every resume (section 7)",
         view=DIAGRAM_VIEW_INVESTIGATION),
    _row("73", INVESTIGATE_WORKFLOW, V_RESUME,
         (G_RESUME_TO_DESIGN_WRITING_AT_REDESIGNS_CEILING,), ENDED,
         outcome=OUTCOME_FAILED,
         note="the user is told in the investigation before it closes",
         view=DIAGRAM_VIEW_INVESTIGATION),
    _row("74", SUBMIT_TO_PR_GATE, V_ACCEPTED, (), ENDED, outcome=OUTCOME_PASSED,
         view=DIAGRAM_VIEW_MAIN_PATH),
    _row("75", SUBMIT_TO_PR_GATE, V_GATE_REJECTION, (), INVESTIGATE_WORKFLOW,
         investigation_focus=FOCUS_UNKNOWN, note="the gate's findings in the report",
         view=DIAGRAM_VIEW_INVESTIGATION),
    _row("76", SUBMIT_TO_PR_GATE, V_GATEKEEPER_REFUSAL,
         (G_REFUSAL_INFRASTRUCTURE, G_FEWER_THAN_FIVE_ATTEMPTS), TO_RETRY_SAME_STATE,
         note="backed off",
         view=DIAGRAM_VIEW_NOT_DRAWN),
    _row("77", SUBMIT_TO_PR_GATE, V_GATEKEEPER_REFUSAL,
         (G_FIFTH_INFRASTRUCTURE_ATTEMPT_OR_INTEGRATION_OR_SCOPE_REFUSAL,),
         INVESTIGATE_WORKFLOW, investigation_focus=FOCUS_UNKNOWN,
         view=DIAGRAM_VIEW_INVESTIGATION),
    _row("78", SUBMIT_TO_PR_GATE, V_GATEKEEPER_REFUSAL, (G_REFUSAL_FORM,),
         INVESTIGATE_WORKFLOW, investigation_focus=FOCUS_UNKNOWN,
         note="a machine error, the submit state built a bad request",
         view=DIAGRAM_VIEW_INVESTIGATION),
)

TRANSITION_TABLE_BY_ROW = {row.row: row for row in TRANSITION_TABLE}

# Name rows used by the machine so design renumbering cannot silently redirect special handling.
ROW_TOPIC_BRANCH_CUT = "1"
ROW_DESIGN_APPROVED = "18"
ROW_TESTS_BEGIN = "24"
ROW_IMPLEMENTATION_TO_TEST_SUITE = "25"
ROW_TEST_DESIGN_APPROVED = "41"
ROW_TESTS_TO_TEST_SUITE = "47"
ROW_THE_ARBITRATORS_THIRD_ENTRY = "65"
ROW_REDESIGN_ORDERED_AT_THE_CONTRACT_CHECK = "11"
for _row_number in (ROW_TOPIC_BRANCH_CUT, ROW_DESIGN_APPROVED, ROW_TESTS_BEGIN,
                    ROW_IMPLEMENTATION_TO_TEST_SUITE, ROW_TEST_DESIGN_APPROVED,
                    ROW_TESTS_TO_TEST_SUITE, ROW_THE_ARBITRATORS_THIRD_ENTRY,
                    ROW_REDESIGN_ORDERED_AT_THE_CONTRACT_CHECK):
    assert _row_number in TRANSITION_TABLE_BY_ROW, _row_number

DESIGN_TRANSITION_ROWS = tuple(row.row for row in TRANSITION_TABLE if row.source == "3.2")



# Before code exists, refine the design in its issue document with the contract beside it; move both when code starts.

def contract_path_beside_design(design_path):
    """Return the contract path beside the design before the component has code."""
    stem = design_path[:-len(".md")] if design_path.endswith(".md") else design_path
    if stem.endswith("-design"):
        stem = stem[:-len("-design")]
    return stem + "-contract.md"


RECORD_DIRECTORY_NAME = "design-to-main-record"
# Forced writes do not spend the writer's counter.
WRITE_TRAILER_FORCED = "forced"
RUN_STATE_FILE_NAME = "run-state.json"
USER_RULINGS_FILE_NAME = "user-rulings.md"
# Evidence instance numbers start at one and span the run.
EVIDENCE_DIRECTORY_NAME = "evidence"
NOTES_FILE_NAME = "notes.md"
STATE_EXIT_FILE_NAME = "state-exit.json"
# Report numbers use the investigation instance count.
INVESTIGATION_REPORTS_DIRECTORY_NAME = "reports"
INVESTIGATION_REPORT_FILE_NAME_FORMAT = "investigation-%d.md"

STATE_EXIT_JSON_FIELDS = {
    "state": "state",
    "verdict": "verdict",
    "package-commit": "package_commit",
    "destination": "destination",
    "input-named": "input_named",
    "investigation-focus": "investigation_focus",
    "coverage-type": "coverage_types",       # comma-separated coverage types
    "refusal-class": "refusal_class",
    "held-ruling": "held_ruling",
    "named-files": "named_files",
    "rulings": "rulings",                    # the user's words verbatim
}
# named-files must be present even when empty; omission makes the state-exit malformed.
STATE_EXIT_JSON_FIELDS_REQUIRED = ("state", "verdict", "package-commit", "named-files")

RESUME_DESTINATION_BY_EDITED_DOCUMENT = (
    ("design", DESIGN_WRITING),
    ("design-contract", CONTRACT_REVIEWING),
    ("test-design", TEST_DESIGN_REVIEWING),
    ("implementation", IMPLEMENTATION_REVIEWING),
    ("tests", TEST_REVIEWING),
)
