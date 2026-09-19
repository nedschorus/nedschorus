#!/usr/bin/env python3
"""The design-to-main state machine's tables, as data.

Source: docs/design-to-main/design-to-main-state-machine-design.md.
  STATE_TABLE        is section 3.1, one entry per row.
  TRANSITION_TABLE   is section 3.2, one entry per row, numbered in the
                     order the design lists them (row 1 is
                     `initiate-design-to-main / invoked`, row 78 the last
                     gatekeeper-refusal). Every row has source "3.2".
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
# The fourth value, a test-design's only (section 2): a test-requirement
# marked `no-tests` runs nothing and counts as neither pass nor fail
# (section 6.4). A `test-writing` `emitted` carries it alone when the set
# is empty, never beside a type that is present (user-ruled 2026-09-14,
# the tenth walk, item 6).
COVERAGE_TYPE_NO_TESTS = "no-tests"
# Section 6.4: each test-requirement carries its coverage-type on a line
# of its own, which is what the machine reads for the check of the test
# writer's set against the test-design (user-ruled 2026-09-11, the ninth
# walk, item 7). The rest of the test-design's syntax is step 1's
# (section 11), so this prefix is all the machine reads of the file.
TEST_DESIGN_COVERAGE_TYPE_LINE_PREFIX = "coverage-type:"

# Verdicts (the exit words of sections 3.1 and 6.1).
V_INVOKED = "invoked"
V_EMITTED = "emitted"
V_ADVANCE = "advance"
V_REJECT_CONTRACT = "reject contract"
V_REJECT_DESIGN = "reject design"
V_REJECT_IMPLEMENTATION = "reject implementation"
V_REJECT_TESTS = "reject tests"
V_REJECT_TEST_DESIGN = "reject test-design"
# The arbitrator's one ruling against both sibling artifacts (sections 3.1
# and 6.1: "one or both of the implementation and the tests"; "both are
# named and both are re-entered"). The design fixes no spelling for the
# word; this one is reported with the slice.
V_REJECT_IMPLEMENTATION_AND_TESTS = "reject implementation and tests"
V_DISCUSS = "discuss"
V_REDESIGN = "redesign"          # the user's, at contract-acceptance-by-user only
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
# counted writer refers to (section 3.2, rows 61 to 63, "whose writer's
# counter"), and the writer the verdict sends the run to.
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
                  "the user's invocation of the skill, naming the component and the design's GHI-MD",
                  (V_INVOKED,), "conversation"),
    StateTableRow(DESIGN_WRITING, (),
                  "the invocation; on a redesign, the investigation report",
                  (V_EMITTED,), "conversation"),
    StateTableRow(CONTRACT_REVIEWING,
                  (CONTRACT_ACCEPTANCE_BY_PROGRAM, CONTRACT_ACCEPTANCE_BY_AGENT,
                   CONTRACT_ACCEPTANCE_BY_USER),
                  "the previous version and the notes, on a revision",
                  (V_ADVANCE, V_REJECT_CONTRACT, V_DISCUSS, V_REDESIGN), "composite"),
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
# Section 4's writing states, design-writing among them: the initiator
# writes the design and the component-contract as the others write theirs.
# WRITING_STATES above is the four whose entry reason the counters' buckets
# read (section 7), which design-writing has no part in; this is the set
# section 2 means by "a writing state's `emitted`", whose empty
# `named-files` is a machine error (user-ruled 2026-09-14, the tenth walk,
# item 3).
WRITING_STATES_INCLUDING_DESIGN_WRITING = (DESIGN_WRITING,) + WRITING_STATES
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
    "one revision: the user is called after the original and one
    contract-revision have both failed review, and no second is written"
    (and the same for test-design-corrections) puts it one below
    (user-ruled 2026-09-08, the seventh walk, item 2).
    """
    name: str
    increments_when: str
    ceiling: int
    at_ceiling_from_value: int
    at_the_ceiling: str
    per_design_version: bool = True
    # Section 7 after the eighth walk (item 6, user-ruled 2026-09-09): a
    # write the user's discuss forces is counted like any other and may
    # take the two write counters past their ceiling, which the ceiling
    # guards then read as "at or above". No other counter goes past.
    may_be_taken_past_its_ceiling_by_the_users_discuss: bool = False


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
        "the component-contract, once the design is approved",
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
    # The user naming a writing state on resume is his own time: uncounted
    # (user-ruled 2026-09-08, the seventh walk, item 8, kept as built).
    ENTRY_REASON_USER_NAMED_DESTINATION: BUCKET_UPSTREAM_DOCUMENT_CHANGED,
}


# --- The transitions of section 3.2 --------------------------------------

# Destination markers that are not plain state names.
TO_HOLD_READY_FOR_TEST_SUITE = "hold at ready-for-test-suite"
TO_BOTH_WORK_STREAMS_RE_ENTER = "both work-streams re-enter their writing states"
TO_RESUME_DESTINATION = "the resume destination (section 6.6)"
# A resume destination that is not a state: from the investigation the
# arbitrator's third entry opened (row 65), a resume that names no
# destination applies the ruling the arbitrator held in its report,
# routed through test-suite-arbitrating's rows without entering it.
TO_APPLY_THE_HELD_RULING = "the ruling the arbitrator held in its report (section 6.6)"
# The two names of section 3.1 a resume may not name (section 6.1).
RESUME_MAY_NOT_NAME = (ENDED, INITIATE_DESIGN_TO_MAIN)
# The rulings a resume from that investigation may carry as `held-ruling`
# (section 6.6): the arbitrator's six, never escalate-to-user, since the
# arbitrator is already talking to the user (user-ruled 2026-09-09, the
# eighth walk, item 5).
HELD_RULINGS_A_RESUME_MAY_CARRY = (
    V_REJECT_IMPLEMENTATION, V_REJECT_TESTS, V_REJECT_IMPLEMENTATION_AND_TESTS,
    V_FLAKY_TEST, V_REJECT_CONTRACT, V_ADVANCE)
TO_RETRY_SAME_STATE = "the same state (retry)"
TO_THE_NEXT_ACCEPTANCE_CHECK = "the state's next acceptance-check, in the order section 3.1 lists"
TO_THE_WRITER_THE_VERDICT_NAMES = "that writer anyway, fresh"
TO_BOTH_WRITERS_FRESH = "both writers, fresh"
# Row 60: the arbitrator, entered from a reviewer's ceiling, advances —
# the reviewer was wrong (section 6.5), and the artifact continues as if
# that reviewer had advanced it: the machine routes an `advance` from the
# sub-state whose reject entered test-suite-arbitrating, by that reviewing
# state's own rows.
TO_WHEREVER_THAT_REVIEWING_STATES_ADVANCE_GOES = (
    "wherever that reviewing state's own advance goes")

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
G_A_REJECT_OF_OR_A_FAILED_CHECK_AGAINST_THE_COMPONENT_CONTRACT = (
    "a reject of, or a failed check against, the component-contract")
G_TESTS_NOT_YET_BEGUN = "tests not yet begun"
G_TESTS_BEGUN = "tests begun"
G_TEST_WORK_STREAM_READY = "the test-work-stream at ready-for-test-suite"
G_TEST_WORK_STREAM_NOT_READY = "the test-work-stream not yet there"
G_IMPLEMENTATION_WORK_STREAM_READY = "the implementation-work-stream at ready-for-test-suite"
G_IMPLEMENTATION_WORK_STREAM_NOT_READY = "the implementation-work-stream not yet there"
G_COULD_NOT_RUN_FIRST = "the first of consecutive entries"
G_COULD_NOT_RUN_SECOND = "the second consecutive"
# Row 60 reads why test-suite-arbitrating was entered — the state or
# sub-state whose state-exit entered it, recorded in the run-state
# (section 9, "why each state was entered"). Entered on a failed suite or
# a could-not-run, the arbitrator's advance has no row: a suite that
# failed is never advanced because a run of it passed (section 6.5;
# user-ruled 2026-09-14, the tenth walk, item 16).
G_ENTERED_FROM_A_REVIEWERS_CEILING = "entered from a reviewer's ceiling"
# Rows 35 to 37 (user-ruled 2026-09-14, the tenth walk, item 7): the
# test-design reviewer's reject is uncounted before the test-design's
# approval and a test-design-correction after it (section 7).
G_BEFORE_THE_TEST_DESIGNS_APPROVAL = "before the test-design's approval"
G_AFTER_THE_TEST_DESIGNS_APPROVAL = "after the test-design's approval"
G_WRITERS_COUNTER_BELOW_CEILING = "the writer's counter below its ceiling"
G_WRITERS_COUNTER_AT_OR_ABOVE_CEILING = "the writer's counter at or above its ceiling"
# Row 63 reads the writer's counter and nothing else: arbitrator-rulings is
# charged on entry and bounds the arbitrator's entries (row 65 opens the
# investigation on the third), and past the ceilings every further cycle
# is gated by the user's resume (section 7; user-ruled 2026-09-09, the
# eighth walk, item 5).
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
    """The write counters' ceiling guard (section 3.2, rows 28 and 50; the
    eighth walk, item 6): the same predicate as counter_at_ceiling — the
    machine reads every ceiling as ">=" — under the design's words for
    the two counters a discuss may take past their ceiling."""
    return "the %s counter at or above its ceiling" % name


# The views of section 3.3 a row is drawn in (user-ruled 2026-09-16, the
# walk design-tables-checker-findings-from-pr-409, item 4), in the order
# section 3.3 shows them; design-to-main-state-diagram-generator.py draws
# each view from the rows that name it.
# The edges a run takes when every state advances, invocation to ended.
DIAGRAM_VIEW_MAIN_PATH = "main-path"
# Each writer and its reviewer's rejections, the ceilings to the arbitrator, its rulings, and the return to the suite.
DIAGRAM_VIEW_REWORK_AND_ARBITRATION = "rework-and-arbitration"
# Every way into investigate-workflow and every way out of it.
DIAGRAM_VIEW_INVESTIGATION = "investigation"
# The acceptance-checks of each reviewing state, and every edge that ends at one.
DIAGRAM_VIEW_INSIDE_THE_REVIEWING_STATES = "inside-the-reviewing-states"
# A row section 3.3 does not draw: a retry loop, the user's discuss return, row 60.
DIAGRAM_VIEW_NOT_DRAWN = "not-drawn"
DIAGRAM_VIEWS_DRAWN = (
    DIAGRAM_VIEW_MAIN_PATH, DIAGRAM_VIEW_REWORK_AND_ARBITRATION,
    DIAGRAM_VIEW_INVESTIGATION, DIAGRAM_VIEW_INSIDE_THE_REVIEWING_STATES)


@dataclass(frozen=True)
class TransitionTableRow:
    """One row of section 3.2."""
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
    # Section 3.3's view that draws the row: one of DIAGRAM_VIEWS_DRAWN, or DIAGRAM_VIEW_NOT_DRAWN.
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
    _row("11", CONTRACT_REVIEWING, V_REDESIGN, (G_FROM_CONTRACT_ACCEPTANCE_BY_USER,),
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
         note="the same initiator fixes the component-contract; then the program check",
         view=DIAGRAM_VIEW_REWORK_AND_ARBITRATION),
    _row("15", DESIGN_REVIEWING, V_REJECT_CONTRACT,
         (G_FROM_DESIGN_ACCEPTANCE_BY_AGENT, counter_at_ceiling("design-revisions")),
         DESIGN_WRITING, note="the same initiator brings the user into the conversation",
         view=DIAGRAM_VIEW_REWORK_AND_ARBITRATION),
    # Row 16 says "any reviewing state". contract-reviewing is left out
    # because its checks are the design's own rows: the program check's
    # advance is row 5 or 6, and the agent check's advance on a revision
    # is row 9 whatever the revisions counter reads — the user's check is
    # reached only by a reject (rows 8 and 67), never by an advance
    # (section 6.6: the ceiling guarantees a FAILED revision reaches him).
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
         (G_AGAINST_THE_COMPONENT_CONTRACT, counter_below_ceiling("contract-revisions")),
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
         (G_AGAINST_THE_COMPONENT_CONTRACT, counter_below_ceiling("contract-revisions")),
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
         (G_AGAINST_THE_COMPONENT_CONTRACT, counter_below_ceiling("contract-revisions")),
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
         note="both artifacts contradicting the component-contract; the "
              "implementation-work-stream runs first (section 3.1)",
         view=DIAGRAM_VIEW_REWORK_AND_ARBITRATION),
    # Row 65 has no verdict: it is applied when test-suite-arbitrating is
    # ENTERED with arbitrator-rulings at its ceiling (the machine's enter()),
    # before any arbitrator is launched there. Its guard is the entry check.
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
         (G_A_REJECT_OF_OR_A_FAILED_CHECK_AGAINST_THE_COMPONENT_CONTRACT,
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

# The rows the machine applies by number, beyond the row's own destination
# and counter: named here so that the machine never carries a bare number
# that the design's next renumbering would silently mis-aim.
ROW_TOPIC_BRANCH_CUT = "1"                        # row 1 cuts the topic branch first
ROW_DESIGN_APPROVED = "18"                        # sets design-approved; enters implementation-writing
ROW_TESTS_BEGIN = "24"                            # sets tests-begun; enters test-design-writing
ROW_IMPLEMENTATION_TO_TEST_SUITE = "25"           # the implementation-work-stream is ready
ROW_TEST_DESIGN_APPROVED = "41"                   # sets test-design-approved; enters test-writing
ROW_TESTS_TO_TEST_SUITE = "47"                    # the test-work-stream is ready
ROW_THE_ARBITRATORS_THIRD_ENTRY = "65"            # applied on entry, no verdict
ROW_REDESIGN_ORDERED_AT_THE_CONTRACT_CHECK = "11"  # the investigation holds design-writing
for _row_number in (ROW_TOPIC_BRANCH_CUT, ROW_DESIGN_APPROVED, ROW_TESTS_BEGIN,
                    ROW_IMPLEMENTATION_TO_TEST_SUITE, ROW_TEST_DESIGN_APPROVED,
                    ROW_TESTS_TO_TEST_SUITE, ROW_THE_ARBITRATORS_THIRD_ENTRY,
                    ROW_REDESIGN_ORDERED_AT_THE_CONTRACT_CHECK):
    assert _row_number in TRANSITION_TABLE_BY_ROW, _row_number

# The design's own row numbers (source 3.2), for the coverage assertion in
# the transitions test: every one must be hit by a legality case.
DESIGN_TRANSITION_ROWS = tuple(row.row for row in TRANSITION_TABLE if row.source == "3.2")


# --- The paths of section 9 ----------------------------------------------

# Before code exists, the design is its issue's GHI-MD, refined in place, and
# the component-contract sits beside it (user-ruled 2026-09-18); the
# invocation names the GHI-MD. When code starts both move into the
# component's directory as <component>-design.md and <component>-contract.md.

def contract_path_beside_design(design_path):
    """The component-contract's path while no code exists: beside the design,
    named like it, with `-design.md` (or plain `.md`) replaced by
    `-contract.md`."""
    stem = design_path[:-len(".md")] if design_path.endswith(".md") else design_path
    if stem.endswith("-design"):
        stem = stem[:-len("-design")]
    return stem + "-contract.md"


RECORD_DIRECTORY_NAME = "design-to-main-record"
# The `Write:` trailer of a write the writer's counter does not count — one
# forced by an upstream change or ordered by the arbitrator (section 9).
WRITE_TRAILER_FORCED = "forced"
RUN_STATE_FILE_NAME = "run-state.json"
USER_RULINGS_FILE_NAME = "user-rulings.md"
# `<record>/evidence/<state or sub-state>-<n>/`, for the nth instance of
# that state or sub-state counted from 1 (`implementation-writing-1` is
# the first), holding the instance's notes and its state-exit (section 9;
# user-ruled 2026-09-08, the eighth walk, item 3).
EVIDENCE_DIRECTORY_NAME = "evidence"
NOTES_FILE_NAME = "notes.md"
STATE_EXIT_FILE_NAME = "state-exit.json"
# `<record>/reports/investigation-<n>.md`, each investigation report, `<n>`
# the count of the investigate-workflow instance that wrote it, counted as
# the evidence directory counts (section 9; user-ruled 2026-09-14, the
# tenth walk, item 17).
INVESTIGATION_REPORTS_DIRECTORY_NAME = "reports"
INVESTIGATION_REPORT_FILE_NAME_FORMAT = "investigation-%d.md"

# The fields of state-exit.json (section 2), spelled with hyphens, mapped
# to StateExitRecord's fields (design-to-main-state-machine.py). The
# reader is state_exit_record_from_json_file there.
STATE_EXIT_JSON_FIELDS = {
    "state": "state",
    "verdict": "verdict",
    "package-commit": "package_commit",
    "destination": "destination",
    "input-named": "input_named",
    "investigation-focus": "investigation_focus",
    "coverage-type": "coverage_types",       # a comma-separated string: every type in the set
    "refusal-class": "refusal_class",
    "held-ruling": "held_ruling",
    "named-files": "named_files",            # a list, always written (section 2)
    "rulings": "rulings",                    # a list, the user's words verbatim
}
# `named-files` is always written, an empty list when the agent produced
# no artifact, so an absent field is a malformed state-exit (section 2;
# user-ruled 2026-09-14, the tenth walk, item 3).
STATE_EXIT_JSON_FIELDS_REQUIRED = ("state", "verdict", "package-commit", "named-files")

# On `resume`, the earliest state downstream of what the user changed
# (section 6.6), in the order the design lists the documents.
RESUME_DESTINATION_BY_EDITED_DOCUMENT = (
    ("design", DESIGN_WRITING),
    ("component-contract", CONTRACT_REVIEWING),
    ("test-design", TEST_DESIGN_REVIEWING),
    ("implementation", IMPLEMENTATION_REVIEWING),
    ("tests", TEST_REVIEWING),
)
