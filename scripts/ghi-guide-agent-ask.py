#!/usr/bin/env python3
"""Ask ghi-guide-agent, the project's knowledge agent over its GitHub-issue corpus
(nedschorus#46, design doc docs/issues/46-ghi-guide-agent-design.md § The
ask path). Run by any agent — and by the ghi-write skill's step 1 — before
filing or editing an issue, to learn what already covers the ground.

Usage:
  ghi-guide-agent-ask.py "<question>" [--include-closed]
  ghi-guide-agent-ask.py --question-file <path> [--include-closed]
  ... [--print-answer-json] [--request-form draft-verdict]

ghi-guide-agent's answer is a JSON object that `claude -p --json-schema`
constrains to ghi_guide_agent_answer_json_schema_build_for_kinds; its `kind` says
which reply it is, and --request-form says which kinds it may be
(GHI_GUIDE_AGENT_ANSWER_KINDS_EACH_REQUEST_FORM_ALLOWS). By default this program prints what ghi_guide_agent_answer_render_as_caller_stdout_stderr_and_exit_code makes of
it, with the exit codes below. With --print-answer-json it prints the object
itself on stdout instead, whatever the exit code, for a program such as
scripts/ghi-issue-write.py that reads its fields; a failed ask prints nothing
on stdout.

Exit codes:
  0  the reading list ghi-guide-agent returns, printed to stdout; without
     --include-closed, OPEN_ISSUES_ONLY_INCLUDE_CLOSED_HINT_MESSAGE follows on
     stderr, so the caller learns the flag when the answer omits closed issues
  1  a failed ask — gh unreachable, the box unreachable, ghi-guide-agent's own run
     erroring or timing out, or its answer not usable. Stderr carries one
     line, or, for an unusable answer, GHI_GUIDE_AGENT_ANSWER_NOT_USABLE_MESSAGE_TEMPLATE's
     two lines, the second saying what to do. A failed ask never blocks a
     write (design's own words): the caller's job is to fall down the
     ghi-write skill's fallback ladder, not to treat exit 1 as fatal.
  2  ghi-guide-agent answered with kind `not-about-issues`: the question was not
     about issues. NOT_ABOUT_ISSUES_MESSAGE on stderr, nothing on stdout.
  3  ghi-guide-agent answered with kind `ask-user-about-ruling`: it found a ruling
     of the user's it may not judge. RULING_QUESTION_MESSAGE, carrying its
     sentence, on stderr, nothing on stdout.

Why 2 and 3 are not passed through (user-ruled 2026-09-29, walk
SKILL-ghi-write-2026-09-29-4, item 1 revised, "y"). Until then the two
replies went to stdout verbatim with exit 0, as if they were answers. The
user, reading the /ghi-write sentences proposed to explain them: "Not great.
Out-of-scope is not helpful response. I think better wording would be "Not a
query re GHIs") It should respond with a error like - "GHI-info reports
which issues relate to a querry" or something like tha. Also escalate or
whatever the other response is makes no sense either." And, on a first
wording of the ruling message: "this doesn't make sense - that a newer one
may override". The two messages are the approved text, word for word, and
replace the /ghi-write sentences that would have explained the bare replies.
Exit codes of their own, rather than 1, because 1 sends a caller down the
fallback ladder, which is wrong for both: one wants the question reworded,
the other wants the user.

A draft that conflicts with a ruling the user made gets the ruling question,
not a verdict. too-similar is a soft block an agent may pass on its own
judgment, and a ruling is the user's to settle; the GHI write tool writes the
issue and records the question in a proposed-improvements-or-changes-file
in the log-store on ned-box. Every ruling question carries the number of the issue
holding the ruling, its `ruling_issue`, so that record can cite the ruling. The prompt reaches ghi-guide-agent at a cold start, so a session started
earlier keeps its old prompt until it is next reincarnated.

Seat and machine: ghi-guide-agent lives ONLY on the Ubuntu box, at ~/agents/ghi-guide-agent
there — its mirror, session id, and reincarnation counters all live in that
one checkout, per the design's "wrapper state ... lives there." This script is the SAME file on
both machines (it is checked into the repo, so every checkout — Mac or box
— carries an identical copy). It tells which machine it is on by the
hostname, never by whether the seat directory exists: on any machine whose
hostname is not NED_BOX_HOSTNAME it re-execs itself over `ssh ned` (the
Mac's ssh alias for the box), one hop, so every step below (refresh, session
state, the claude call, the post-check) runs box-side where the mirror and
state actually live. On the box it runs locally, and a missing seat
directory there is a failed ask that names the directory and how to create
it, not a hop to a host the box cannot resolve.

Where the box's seat is, is resolved BY THE BOX — its own shell expands
$HOME/agents/ghi-guide-agent, the fixed box root launch-claude-ubuntu seats every
box seat under (it reads no agents-root variable, user-ruled 2026-09-22 in
merge-lane-2's walk). This script never sends a path of its own: the first
live run failed exactly there, having spliced in the Mac's expanded
/Users/el/agents/ghi-guide-agent, which of course does not exist on the box.

There is no wrapper-side auto-bootstrap: if the seat does not exist on the
box, the run says so and names the path it looked in, rather than trying to
create a knowledge agent's home out of thin air. A caller that gets that
error is not stuck — the ghi-write skill's fallback ladder covers a failed
ask by design.

Session lifecycle (design § The ghi-guide-agent session): no process outlives one
ask. Every call is a fresh `claude -p`, resumed by the session id under
`ghi_guide_agent_session_id` in `.ghi-guide-agent-state.json` in the seat directory,
cold-started when no session is stored or a reincarnation trigger fires (closes-since-birth, the stale-match
rate, transcript size, or the share of context in use — the named constants
below). Reincarnating is this script's job alone: the project's handoff hook
stays silent in the sessions it runs (run_claude). Reincarnation means: one
FULL mirror rebuild (not the routine per-ask delta), then the cold-start
prompt as its own turn, then the actual question as a second turn on that
same fresh session — both prompts are verbatim from the design's § Prompts,
never composed here.

Checkout freshness (user-ruled 2026-09-15, nedschorus#324/#334): the lock
holder fast-forwards the seat CHECKOUT to origin/main before anything reads
from it. ghi-guide-agent's answers cite the pair documents under docs/issues/ and
the wiki pages, and it reads those from this disk — a stale checkout is
stale answers about the very designs the issues point at, and superseded
skills to answer under. The freshness hook's merge used to keep the
checkout current; that merge is gone, so the refresh belongs to the caller
that knows an ask is about to happen. It never fails an ask: any refusal —
a dirty tree, a local commit not on origin/main, an unreachable origin — is one
stderr line and the ask proceeds against what is on disk.

Concurrency: the state file is flock'd. An ask that cannot get the lock
(another ask is mid-flight) does not wait and does not touch the stored
session — it cold-starts a throwaway session of its own and never writes
its outcome back to the state file (design: "nothing waits, nothing shares
a transcript").

The answer is read from the result's `structured_output`, never from its
text, so a reply the session gave after its answer, such as one to a Stop
hook, cannot stand in for it. `claude -p` exits 0 with `"is_error": false`
even when the model never satisfied the schema, leaving `structured_output`
null; that, and an object that lacks a field its kind needs, fail the ask
(ghi_guide_agent_answer_extract_and_schema_check_from_claude_result).

Post-check (design step 4): every issue number in the answer is checked
against the just-refreshed mirror by this script, never taken on the
agent's word. A closed issue that the caller did not ask for via
--include-closed is treated as drift — stale context — and triggers exactly
one recheck turn, the corrected answer becoming the final answer. The
"(closed <date>)" tag on a closed issue in the printed reading list comes
from the mirror too.
"""

import argparse
import contextlib
import fcntl
import importlib.util
import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPT_DIRECTORY = Path(__file__).resolve().parent

_mirror_spec = importlib.util.spec_from_file_location(
    "ghi_mirror_refresh", SCRIPT_DIRECTORY / "ghi-mirror-refresh.py")
mirror_refresh = importlib.util.module_from_spec(_mirror_spec)
_mirror_spec.loader.exec_module(mirror_refresh)

_claude_code_session_transcript_lookup_and_text_search_common_spec = importlib.util.spec_from_file_location(
    "claude_code_session_transcript_lookup_and_text_search_common",
    SCRIPT_DIRECTORY / "claude-code-session-transcript-lookup-and-text-search-common.py")
claude_code_session_transcript_lookup_and_text_search_common = importlib.util.module_from_spec(_claude_code_session_transcript_lookup_and_text_search_common_spec)
_claude_code_session_transcript_lookup_and_text_search_common_spec.loader.exec_module(claude_code_session_transcript_lookup_and_text_search_common)

_threshold_hook_spec = importlib.util.spec_from_file_location(
    "handoff_context_threshold_hook", SCRIPT_DIRECTORY / "handoff-context-threshold-hook.py")
threshold_hook = importlib.util.module_from_spec(_threshold_hook_spec)
_threshold_hook_spec.loader.exec_module(threshold_hook)

_git_output_spec = importlib.util.spec_from_file_location(
    "git_machine_readable_output_runner_and_parser_common",
    SCRIPT_DIRECTORY.parent / "nc-systems" / "general-tools"
    / "git-machine-readable-output-runner-and-parser-common.py")
git_output = importlib.util.module_from_spec(_git_output_spec)
_git_output_spec.loader.exec_module(git_output)

_command_line_prefix_spec = importlib.util.spec_from_file_location(
    "claude_code_headless_run_command_line_prefix_with_no_connectors_and_explicit_permission_mode_common",
    SCRIPT_DIRECTORY.parent / "nc-systems" / "general-tools"
    / "claude-code-headless-run-command-line-prefix-with-no-connectors-and-explicit-permission-mode-common.py")
command_line_prefix = importlib.util.module_from_spec(_command_line_prefix_spec)
_command_line_prefix_spec.loader.exec_module(command_line_prefix)

AGENT_BOX = os.environ.get("NEDSCHORUS_AGENT_BOX", "ned")
# AGENT_BOX is the Mac's ssh alias for the box, which the box itself cannot resolve.
NED_BOX_HOSTNAME = "ned-box"
DEFAULT_AGENTS_ROOT = Path(os.environ.get("NEDSCHORUS_AGENTS_ROOT", "~/agents")).expanduser()
DEFAULT_SEAT_DIR = DEFAULT_AGENTS_ROOT / "ghi-guide-agent"
DEFAULT_REPO = "nedschorus/nedschorus"
STATE_FILE_NAME = ".ghi-guide-agent-state.json"
LOCK_FILE_NAME = ".ghi-guide-agent-state.lock"

# Model: named constant + env override, per issue #46's own framing —
# "settled empirically." Starting pick for this build, not a measured
# choice among fable/opus/sonnet.
GHI_GUIDE_AGENT_MODEL = os.environ.get("GHI_GUIDE_AGENT_MODEL", "claude-sonnet-5")
# ghi-guide-agent only reads: the mirror, the files open issues link to, and the log-store.
GHI_GUIDE_AGENT_ALLOWED_TOOLS = "Read,Grep,Glob"
# "One overall timeout (inside the hook budget)" (design § The ask path) —
# ONE deadline for the whole ask, not one per claude call. An ask can spend
# up to three turns (a cold start's two, plus a drift recheck), and giving
# each the full allowance made a nominal five-minute ask a possible
# fifteen-minute one — the opposite of what "inside the hook budget" is for
# (PR #143 review, Codex P2). Each turn is handed only what is left.
# NM's three-watchdog machinery is deliberately not carried over (design:
# "version 1 here starts with one timeout").
ASK_TIMEOUT_SECONDS = int(os.environ.get("GHI_GUIDE_AGENT_ASK_TIMEOUT_SECONDS", "300"))

# A claude that cannot authenticate says so in its JSON result's `result` field
# ("Failed to authenticate: OAuth session expired and could not be refreshed",
# seen box-side 2026-09-11 after the login there lapsed). Nothing in this script
# can repair that: the remedy is an interactive login on the box, so the message
# names it rather than leaving the caller to fall down the fallback ladder blind.
LOGGED_OUT_PATTERN = re.compile(r"authenticat|oauth", re.IGNORECASE)
LOGGED_OUT_REMEDY = (f" — the claude on {AGENT_BOX} is logged out; run `claude auth login` "
                     f"there (from the Mac: `ssh -t {AGENT_BOX} claude auth login`), then retry")
# The box gets the ask's own budget plus room for the ssh round trip and a
# routine refresh. This does NOT guarantee the Mac outlasts every box-side
# run: the ask's deadline bounds only the claude turns, while the mirror
# refresh is bounded separately by ghi-mirror-refresh's own constants
# (MAX_PAGES x the per-call gh timeout), which can exceed this slack when
# GitHub stalls (PR #143 review, P3). The cost of that case is
# misattribution, not a wrong answer: the Mac reports that the ssh call did
# not finish instead of the box's real refresh error, and both land the caller on the
# ghi-write skill's fallback ladder.
SSH_TIMEOUT_SECONDS = ASK_TIMEOUT_SECONDS + 120

# Reincarnation-trigger constants (design § Verify at build's Constants list).
CLOSES_SINCE_BIRTH_THRESHOLD = 20
STALE_MATCH_WINDOW = 10
STALE_MATCH_THRESHOLD = 2
# The design points at "NM's working values" for this one; grepped
# nedsmessenger/adapter/adapter.py 2026-08-23 and it carries no
# transcript-size constant to inherit — only timeouts. Starting value only,
# tuned in live use per the design's own Constants clause.
TRANSCRIPT_SIZE_THRESHOLD_BYTES = 5_000_000
# The share of the model's context window in use, read by the handoff hook's
# own reader. On 2026-09-16 the session stood at 52% with a 3.7 MB transcript,
# under the size trigger, and the handoff hook fired mid-answer instead. That
# hook is silent in these sessions now, so this is what bounds them. Below the
# hook's 50 because it is checked before an ask and the ask then adds to it,
# and the design's reincarnation errs eager.
CONTEXT_USED_PERCENTAGE_THRESHOLD = 40.0

GHI_GUIDE_AGENT_ANSWER_KIND_READING_LIST = "reading-list"
GHI_GUIDE_AGENT_ANSWER_KIND_VERDICT = "verdict"
GHI_GUIDE_AGENT_ANSWER_KIND_REPAIR = "repair"
GHI_GUIDE_AGENT_ANSWER_KIND_NOT_ABOUT_ISSUES = "not-about-issues"
GHI_GUIDE_AGENT_ANSWER_KIND_ASK_USER_ABOUT_RULING = "ask-user-about-ruling"
VERDICTS = ("too-similar", "related", "unrelated")
REPAIR_OUTCOMES = ("done", "no-change", "blocked")

GHI_GUIDE_AGENT_ANSWER_JSON_SCHEMA_PROPERTIES = {
    "kind": {
        "enum": [GHI_GUIDE_AGENT_ANSWER_KIND_READING_LIST, GHI_GUIDE_AGENT_ANSWER_KIND_VERDICT, GHI_GUIDE_AGENT_ANSWER_KIND_REPAIR,
                 GHI_GUIDE_AGENT_ANSWER_KIND_NOT_ABOUT_ISSUES, GHI_GUIDE_AGENT_ANSWER_KIND_ASK_USER_ABOUT_RULING],
        "description": ("Which reply this is: reading-list for request forms 1 and 3, "
                        "verdict for form 2, repair for form 4, and not-about-issues or "
                        "ask-user-about-ruling for the Boundaries.")},
    "issues": {
        "type": "array", "items": {"type": "integer"},
        "description": ("For reading-list and verdict: the issue numbers, without #, "
                        "in the order you would have the asker read them.")},
    "notes": {
        "type": "array", "items": {"type": "string"},
        "description": "For reading-list: note lines in plain sentences, only when needed."},
    "verdict": {
        "enum": list(VERDICTS),
        "description": "For verdict: too-similar, related or unrelated."},
    "outcome": {
        "enum": list(REPAIR_OUTCOMES),
        "description": "For repair: done, no-change or blocked."},
    "sentence": {
        "type": "string",
        "description": ("For repair: the repair, why no change was needed, or what "
                        "stopped you. For ask-user-about-ruling: one sentence naming "
                        "the ruling and the doubt.")},
    "ruling_issue": {
        "type": "integer",
        "description": ("For ask-user-about-ruling: the number of the issue that "
                        "holds the ruling.")},
}
# The fields each kind must fill beyond `kind`.
GHI_GUIDE_AGENT_ANSWER_FIELDS_EACH_KIND_NEEDS = {
    GHI_GUIDE_AGENT_ANSWER_KIND_READING_LIST: ("issues",),
    GHI_GUIDE_AGENT_ANSWER_KIND_VERDICT: ("verdict", "issues"),
    GHI_GUIDE_AGENT_ANSWER_KIND_REPAIR: ("outcome", "sentence"),
    GHI_GUIDE_AGENT_ANSWER_KIND_NOT_ABOUT_ISSUES: (),
    GHI_GUIDE_AGENT_ANSWER_KIND_ASK_USER_ABOUT_RULING: ("ruling_issue", "sentence"),
}
# The fields a kind may leave out.
GHI_GUIDE_AGENT_ANSWER_OPTIONAL_FIELDS_EACH_KIND_MAY_GIVE = {
    GHI_GUIDE_AGENT_ANSWER_KIND_READING_LIST: ("notes",),
}
# The answer kinds each --request-form allows. No program sends form 4, a link
# repair, so no request form allows `repair`.
GHI_GUIDE_AGENT_REQUEST_FORM_READING_LIST = "reading-list"
GHI_GUIDE_AGENT_REQUEST_FORM_DRAFT_VERDICT = "draft-verdict"
GHI_GUIDE_AGENT_ANSWER_KINDS_EACH_REQUEST_FORM_ALLOWS = {
    GHI_GUIDE_AGENT_REQUEST_FORM_READING_LIST: (
        GHI_GUIDE_AGENT_ANSWER_KIND_READING_LIST, GHI_GUIDE_AGENT_ANSWER_KIND_NOT_ABOUT_ISSUES,
        GHI_GUIDE_AGENT_ANSWER_KIND_ASK_USER_ABOUT_RULING),
    # scripts/ghi-issue-write.py's adjudication, whose question is always a
    # draft GHI-MD and so is always about issues.
    GHI_GUIDE_AGENT_REQUEST_FORM_DRAFT_VERDICT: (
        GHI_GUIDE_AGENT_ANSWER_KIND_VERDICT, GHI_GUIDE_AGENT_ANSWER_KIND_ASK_USER_ABOUT_RULING),
}


def ghi_guide_agent_answer_json_schema_build_for_kinds(kinds) -> dict:
    """The schema `claude -p --json-schema` holds an answer to: one of
    `kinds`, only the fields those kinds use, and each kind's needed fields
    required when `kind` names it.

    The API refuses oneOf, anyOf and allOf at a schema's top level (Claude
    Code 2.1.323) and accepts if/then/else there, so each kind's needed
    fields are one link of an if/then/else chain."""
    used = {"kind"}
    for kind in kinds:
        used.update(GHI_GUIDE_AGENT_ANSWER_FIELDS_EACH_KIND_NEEDS[kind])
        used.update(GHI_GUIDE_AGENT_ANSWER_OPTIONAL_FIELDS_EACH_KIND_MAY_GIVE.get(kind, ()))
    properties = {field: dict(value) for field, value
                  in GHI_GUIDE_AGENT_ANSWER_JSON_SCHEMA_PROPERTIES.items() if field in used}
    properties["kind"]["enum"] = list(kinds)
    schema = {"type": "object", "additionalProperties": False,
              "required": ["kind"], "properties": properties}
    chain = None
    for kind in reversed(kinds):
        needed = GHI_GUIDE_AGENT_ANSWER_FIELDS_EACH_KIND_NEEDS[kind]
        if not needed:
            continue
        link = {"if": {"properties": {"kind": {"const": kind}}},
                "then": {"required": list(needed)}}
        if chain is not None:
            link["else"] = chain
        chain = link
    if chain is not None:
        schema.update(chain)
    return schema

COLD_START_PROMPT_TEMPLATE = """You are ghi-guide-agent: this project's knowledge agent over its GitHub-issue corpus. Other agents send you one request at a time; you answer it from the corpus you hold in context and stop. You are the judgment layer — every mechanical fact (fetching, counting, verifying) is script work done for you before a request reaches you.

You run inside a checkout of the project repository; your knowledge is the local mirror in it at {mirror_path}, regenerated by script and refreshed before every request:

- issues-open.md — every open issue in full: number, title, labels, updated time, body, comments. Read this file whole now, before anything else.
- issues-closed.md — one line per closed issue. Do not load it whole; grep it only when a request asks about closed history.

GitHub is the source of truth; the mirror is your working copy of it. Answer from the mirror only: never read issue state from GitHub (no gh queries, no API, no web). The one time you run gh is to make the issue edit a link repair (form 4) needs; take the issue's current text from the mirror. The facts a request states are already established by script; your job is only the judgment.

Your answer to every request is a JSON object whose `kind` says which reply it is; each form below and each boundary says which kind and fields to give.

Requests arrive in four forms:

1. **You are asked for a reading list**: what should an agent read before it files or edits an issue on some topic. Answer with kind `reading-list`: the issue numbers in `issues`, plus, only when needed, note lines in plain sentences in `notes`. Closed issues belong in a reply only when the request says closed history is wanted.
2. **You are shown a draft issue** — title and body — and asked whether the corpus already covers it. When the draft is an edit of an existing issue, the request names that issue: leave it out of the comparison. Answer with kind `verdict`: `too-similar` with the issue that already covers this ground in `issues`, `related` with the issues the author should know in `issues` (no collision), or `unrelated` with `issues` empty. When the draft conflicts with a ruling the user made, answer instead with the ruling question under Boundaries.
3. **You are told a fact that corrects your last reply** — an issue you cited has closed — and asked to redo that one judgment. The fact is already established by script from the refreshed mirror: do not question or verify it; re-read the named entry in issues-closed.md, including any Superseded-by: link, and answer with a corrected reading list.
4. **You are asked to repair a link** — a cross-reference the maintenance sweep found broken. The request states the defect; repair exactly that link and nothing else. Issue edits go through gh as normal; document-side changes are landed through `scripts/ghi-issue-write.py`, whose pull request merge-lane-2 reviews and merges; never push to main yourself. Answer with kind `repair`: `outcome` done and the repair in `sentence`, no-change and why no change was needed in `sentence`, or blocked and what stopped you in `sentence`.

Boundaries:

- Asked a question about anything beyond the issue corpus — the wiki, the code, anything else — answer with kind `not-about-issues`.
- Whether an old ruling still binds is never yours to judge. Answer with kind `ask-user-about-ruling`: the issue that holds the ruling in `ruling_issue`, and one sentence naming the ruling and the doubt in `sentence`.
- A draft-body request gets a verdict, except that a draft that conflicts with a ruling the user made gets the ruling question: whether the ruling still binds, or still binds this draft, is the user's to settle. A question beyond the corpus gets not-about-issues even when it touches a ruling."""


ASK_PROMPT_ISSUES_WHOSE_DESIGN_A_PLAN_SHOULD_REUSE_REQUEST_SENTENCE = (
    "If the question describes a plan, also name any issue whose design built "
    "something the plan should reuse instead of building its own.")


def compose_resume_ask_prompt(question: str, include_closed: bool, changed_numbers,
                              is_resume: bool) -> str:
    """§ Prompts: Resume ask prompt. The changed-entries preamble appears only
    on a resumed session whose refresh actually changed entries; the
    asker's question rides through unrewritten, and ASK_PROMPT_ISSUES_WHOSE_DESIGN_A_PLAN_SHOULD_REUSE_REQUEST_SENTENCE
    follows it in every ask."""
    parts = []
    if is_resume and changed_numbers:
        named = ", ".join(f"#{n}" for n in changed_numbers)
        parts.append(
            f"Since your last request, these mirror entries changed: {named}. "
            "Re-read them in the mirror before answering — an entry may have "
            "moved to issues-closed.md."
        )
    parts.append(f"You are asked for a reading list. {question}")
    parts.append(ASK_PROMPT_ISSUES_WHOSE_DESIGN_A_PLAN_SHOULD_REUSE_REQUEST_SENTENCE)
    if include_closed:
        parts.append(
            "Closed history is wanted for this request: grep issues-closed.md "
            "as well; closed pointers are expected, each tagged with its close date."
        )
    return "\n\n".join(parts)


def compose_drift_notice(unexpected_closed) -> str:
    """§ Prompts: Drift notice. One line per flagged pointer; "one recheck
    per ask" means one turn total, not one turn per flagged pointer."""
    lines = []
    for number, closed_date in unexpected_closed:
        lines.append(
            f"#{number} closed on {closed_date} — the mirror is current; "
            "re-read its entry in issues-closed.md, including any "
            "Superseded-by: link, and give a corrected reading list."
        )
    return "\n".join(lines)


# What main() hands the caller in place of the two boundary answers, and the
# exit code each carries. The text is the user's approved wording (module docstring,
# "Why 2 and 3 are not passed through"); change it only by his walk.
# `<your subject>` and `<terms>` are placeholders the caller fills in.
EXIT_NOT_ABOUT_ISSUES = 2
EXIT_RULING_QUESTION = 3
NOT_ABOUT_ISSUES_MESSAGE = (
    "Not a question about GitHub issues: ghi-guide-agent reports which issues relate to a subject.\n"
    'Ask again as: scripts/ghi-guide-agent-ask.py "Which issues cover <your subject>?"\n'
    "If that is refused too, search yourself: gh issue list --repo nedschorus/nedschorus "
    '--state all --search "<terms>"')
RULING_QUESTION_MESSAGE_TEMPLATE = (
    "ghi-guide-agent found a ruling of the user's that it cannot tell still applies: {sentence}\n"
    "If you are filing or editing a GHI, go on with scripts/ghi-issue-write.py as planned: it records this question in the log-store on ned-box and tells you to dispatch a subagent to settle it.\n"
    "If you are not filing or editing a GHI, ask the user whether that ruling still applies, and put the question on your task list.")
# What follows the sentence: the number of the issue holding the ruling.
RULING_QUESTION_RULING_GHI_NUMBER_SUFFIX_TEMPLATE = " (held in GHI {number})"
# Printed on stderr after an answer asked without --include-closed. stderr,
# because stdout is the answer that callers such as ghi-issue-write.py parse.
# It names neither the question nor a --question-file path: an ask from off
# the box runs box-side with --question-file /dev/stdin, and that run's stderr
# reaches the caller unchanged, so any command it spelled out would not be
# the caller's.
OPEN_ISSUES_ONLY_INCLUDE_CLOSED_HINT_MESSAGE = (
    "ghi-guide-agent-ask: this answer covers open issues only.\n"
    "To search closed issues as well, such as for precedent or before saying no issue "
    "covers a subject, rerun the same command with --include-closed added.")
# The failure when ghi-guide-agent answered but the answer cannot be used.
# scripts/ghi-issue-write.py finds the line by this opening, which it copies.
GHI_GUIDE_AGENT_ANSWER_NOT_USABLE_MESSAGE_OPENING = "ghi-guide-agent's answer is not usable:"
GHI_GUIDE_AGENT_ANSWER_NOT_USABLE_MESSAGE_TEMPLATE = (
    GHI_GUIDE_AGENT_ANSWER_NOT_USABLE_MESSAGE_OPENING + " {problem}\n"
    "If you are filing or editing a GHI, go on down the ask's fallback ladder in "
    ".claude/skills/ghi-write/SKILL.md; for any other ask, go on without "
    "ghi-guide-agent's answer.")


def ghi_guide_agent_answer_extract_and_schema_check_from_claude_result(result: dict, kinds):
    """(answer, None) when the result's `structured_output` is an answer
    of one of `kinds` that this program can use, else (None, a sentence
    saying what came back).

    `claude -p --json-schema` exits 0 with `"is_error": false` and a null
    `structured_output` when the model never satisfied the schema, so the
    object is checked here, field by field, rather than trusted."""
    answer = result.get("structured_output")
    if not isinstance(answer, dict):
        return None, ("claude returned no JSON answer (structured_output is "
                      f"{json.dumps(answer)}); its text reply began: "
                      f"{str(result.get('result') or '')[:200]!r}")
    shown = json.dumps(answer)[:300]
    properties = ghi_guide_agent_answer_json_schema_build_for_kinds(kinds)["properties"]
    kind = answer.get("kind")
    if not isinstance(kind, str) or kind not in kinds:
        return None, f"the answer's kind {kind!r} is none the schema allows: {shown}"
    unknown = sorted(set(answer) - set(properties))
    if unknown:
        return None, f"the answer has fields the schema does not: {', '.join(unknown)}: {shown}"
    missing = [field for field in GHI_GUIDE_AGENT_ANSWER_FIELDS_EACH_KIND_NEEDS[kind] if field not in answer]
    if missing:
        return None, f"the {kind} answer lacks its {', '.join(missing)} field: {shown}"
    for field, value in answer.items():
        allowed = properties[field].get("enum")
        if allowed is not None:
            if value not in allowed:
                return None, f"the answer's {field} {value!r} is none the schema allows: {shown}"
        elif properties[field].get("type") == "array":
            item_type = int if properties[field]["items"]["type"] == "integer" else str
            if not (isinstance(value, list)
                    and all(isinstance(item, item_type) and not isinstance(item, bool)
                            for item in value)):
                return None, f"the answer's {field} is not a list of {properties[field]['items']['type']}s: {shown}"
        else:
            field_type = int if properties[field]["type"] == "integer" else str
            if not isinstance(value, field_type) or isinstance(value, bool):
                return None, f"the answer's {field} is not of the schema's type {properties[field]['type']}: {shown}"
    if kind == GHI_GUIDE_AGENT_ANSWER_KIND_READING_LIST and not answer["issues"] and not answer.get("notes"):
        return None, f"the reading-list answer names no issue and gives no note: {shown}"
    return answer, None


def answer_issue_numbers(answer: dict):
    """The issue numbers the post-check verifies against the mirror: a
    reading list's and a verdict's. A ruling question's issue holds a ruling
    the user made, so it is the user's to judge, closed or not."""
    if answer["kind"] in (GHI_GUIDE_AGENT_ANSWER_KIND_READING_LIST, GHI_GUIDE_AGENT_ANSWER_KIND_VERDICT):
        return answer["issues"]
    return []


def ghi_guide_agent_answer_render_as_caller_stdout_stderr_and_exit_code(answer: dict, closed_on: dict):
    """(stdout text, stderr text, exit code) that main() prints for a checked
    answer when --print-answer-json is not given. `closed_on` maps the
    number of each closed issue in the answer to its close date, which tags
    that issue in a reading list."""
    kind = answer["kind"]
    if kind == GHI_GUIDE_AGENT_ANSWER_KIND_NOT_ABOUT_ISSUES:
        return "", NOT_ABOUT_ISSUES_MESSAGE, EXIT_NOT_ABOUT_ISSUES
    if kind == GHI_GUIDE_AGENT_ANSWER_KIND_ASK_USER_ABOUT_RULING:
        sentence = (answer["sentence"].strip()
                    + RULING_QUESTION_RULING_GHI_NUMBER_SUFFIX_TEMPLATE.format(
                        number=answer["ruling_issue"]))
        return ("", RULING_QUESTION_MESSAGE_TEMPLATE.format(sentence=sentence),
                EXIT_RULING_QUESTION)
    if kind == GHI_GUIDE_AGENT_ANSWER_KIND_READING_LIST:
        lines = []
        if answer["issues"]:
            lines.append("read " + ", ".join(
                f"#{number}" + (f" (closed {closed_on[number]})" if number in closed_on else "")
                for number in answer["issues"]))
        lines += [note.strip() for note in answer.get("notes", []) if note.strip()]
        return "\n".join(lines), "", 0
    numbers = ",".join(f"#{number}" for number in answer["issues"])
    return f"verdict: {answer['verdict']}" + (f" {numbers}" if numbers else ""), "", 0


def closed_issue_dates(numbers, cache: dict) -> dict:
    """{number: close date} for each of `numbers` that the mirror cache
    holds as closed; "?" when the cache has no close time."""
    dates = {}
    for number in numbers:
        issue = cache.get("issues", {}).get(str(number))
        if issue and issue.get("state") == "CLOSED":
            closed_at = issue.get("closedAt") or ""
            dates[number] = closed_at[:10] if closed_at else "?"
    return dates


def find_unexpected_closed_pointers(numbers, cache: dict, include_closed: bool):
    """Each of the answer's issue numbers that the mirror holds as closed.

    --include-closed makes every closed issue expected by definition (the
    caller asked for closed history); otherwise any closed issue means
    ghi-guide-agent's context predates the issue's close — drift, not a fact it
    established. Returns [(number, closed_date), ...] in the answer's order,
    each number once.
    """
    if include_closed:
        return []
    return list(closed_issue_dates(numbers, cache).items())


# The key under which `.ghi-guide-agent-state.json` holds the id of the ghi-guide-agent
# session this program cold-started and resumes. A bare `session_id` does not
# say whose session: this program runs inside a calling agent's session, and
# launches another, so a reader of the state file had two candidates and no way
# to choose. Renamed on the user's ruling at item 5 of walk
# md-skills-seat-questions-and-concerns-2026-09-21, which followed the same
# rename in the handoff-supervisor (PR "The supervisor's state names the session
# it launched, not \"the session\"").
#
# NOT the same key as the one `claude -p` returns in its JSON: that one is the
# agent-binary's own output contract, read as `reply["session_id"]` below, and
# renaming it here would break the read.
GHI_GUIDE_AGENT_SESSION_ID_STATE_KEY = "ghi_guide_agent_session_id"
# Read-only, for state files written before the rename. load_state migrates it
# in, every write after that uses the new key alone, so a state file converts on
# the first read this program gives it. Removable once no seat carries a
# `.ghi-guide-agent-state.json` older than 2026-09-22.
LEGACY_SESSION_ID_STATE_KEY = "session_id"


def default_state() -> dict:
    return {GHI_GUIDE_AGENT_SESSION_ID_STATE_KEY: None, "closes_since_birth": 0, "recent_matches": []}


def load_state(state_path: Path) -> dict:
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default_state()
    merged = default_state()
    merged.update({key: state[key] for key in merged if key in state})
    if (merged[GHI_GUIDE_AGENT_SESSION_ID_STATE_KEY] is None
            and state.get(LEGACY_SESSION_ID_STATE_KEY) is not None):
        merged[GHI_GUIDE_AGENT_SESSION_ID_STATE_KEY] = state[LEGACY_SESSION_ID_STATE_KEY]
    return merged


def save_state(state_path: Path, state: dict) -> None:
    temp_path = state_path.with_name(state_path.name + ".tmp")
    temp_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(state_path)


class SeatDirectoryUnusable(Exception):
    """The seat directory cannot be locked or written — raised so the ask
    path reports it as one line rather than a traceback."""


@contextlib.contextmanager
def state_lock(lock_path: Path):
    """Yields True if the exclusive lock was acquired, False if contended.

    A contended lock means another ask is mid-flight (design § The ask
    path, step 2): this ask must not wait and must not touch the shared
    session or state file — it proceeds read-only against a throwaway.
    """
    # An unusable seat directory must reach the caller as this module's
    # documented one-line failure, not a traceback (PR #143 review question).
    # The open and the mkdir are the two calls that touch the filesystem
    # before any work starts, so they are where that promise is kept.
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(lock_path, "a+")
    except OSError as error:
        raise SeatDirectoryUnusable(
            f"the seat directory at {lock_path.parent} is not usable: {error}") from error
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield True
        except OSError:
            yield False
    finally:
        handle.close()


def transcript_path_for(seat_dir: Path, session_id: str, projects_root: Path):
    if not session_id:
        return None
    project_directory = claude_code_session_transcript_lookup_and_text_search_common.project_directory_for_seat(seat_dir, projects_root)
    return project_directory / f"{session_id}.jsonl"


def transcript_size_bytes(seat_dir: Path, session_id: str, projects_root: Path):
    transcript_path = transcript_path_for(seat_dir, session_id, projects_root)
    if transcript_path is None:
        return None
    try:
        return transcript_path.stat().st_size
    except OSError:
        return None


def should_recycle(state: dict, seat_dir: Path, projects_root: Path):
    """(bool, reason) — the four numeric reincarnation triggers. Whether there is
    a session AT ALL is the caller's separate, prior check."""
    closes = state.get("closes_since_birth", 0)
    if closes >= CLOSES_SINCE_BIRTH_THRESHOLD:
        return True, f"{closes} closes since birth (threshold {CLOSES_SINCE_BIRTH_THRESHOLD})"
    recent = state.get("recent_matches", [])[-STALE_MATCH_WINDOW:]
    stale_count = sum(1 for is_stale in recent if is_stale)
    if stale_count >= STALE_MATCH_THRESHOLD:
        return True, (f"{stale_count} stale matches in the last {len(recent)} "
                      f"answers (threshold {STALE_MATCH_THRESHOLD})")
    size = transcript_size_bytes(seat_dir, state.get(GHI_GUIDE_AGENT_SESSION_ID_STATE_KEY), projects_root)
    if size is not None and size >= TRANSCRIPT_SIZE_THRESHOLD_BYTES:
        return True, f"transcript {size} bytes (threshold {TRANSCRIPT_SIZE_THRESHOLD_BYTES})"
    transcript_path = transcript_path_for(seat_dir, state.get(GHI_GUIDE_AGENT_SESSION_ID_STATE_KEY), projects_root)
    used = (threshold_hook.context_used_percentage_from_transcript(str(transcript_path))
            if transcript_path is not None else None)
    if used is not None and used >= CONTEXT_USED_PERCENTAGE_THRESHOLD:
        return True, (f"context {used:.0f}% used "
                      f"(threshold {CONTEXT_USED_PERCENTAGE_THRESHOLD:g}%)")
    return False, None


def run_claude(prompt: str, resume_session_id, seat_dir: Path, timeout_seconds: int,
               json_schema: dict):
    """One `claude -p` turn. Returns (result_dict, error). No terminal exists
    to approve tool use here, so the run is in dontAsk mode: ghi-guide-agent
    reads and searches the mirror, its agent-home and the log-store, and any
    other tool call is refused rather than waiting for an answer."""
    # --setting-sources user keeps THIS PROJECT'S hooks out of the run
    # (measured 2026-09-17). ghi-guide-agent answered a reading-list question
    # correctly at 20:16:59Z and then, 13 seconds later, answered the
    # checkout-freshness Stop hook's "Rerun the test suites for what you
    # touched"; this script returns the run's last message, so the caller got
    # the housekeeping reply and the reading list was thrown away, with exit
    # 0. A cold-read cell had the same leak, and PR #417 gave it the same
    # flag. The seat's own settings.json is project settings, so nothing here
    # needs it: permissions come from GHI_GUIDE_AGENT_ALLOWED_TOOLS.
    # The prompt goes on stdin: one argument may not exceed 128 KiB on
    # Linux, and a draft GHI-MD with its diff can be larger. It must not
    # follow --allowedTools either, which takes any number of values and
    # would read the prompt as one more tool name.
    command = [*command_line_prefix.claude_code_headless_run_command_line_prefix_build("dontAsk"),
               "--output-format", "json", "--setting-sources", "user",
               "--json-schema", json.dumps(json_schema),
               "--allowedTools", GHI_GUIDE_AGENT_ALLOWED_TOOLS, "--model", GHI_GUIDE_AGENT_MODEL]
    if resume_session_id:
        command += ["--resume", resume_session_id]
    # Without this the handoff hook tells the session to hand off at its
    # threshold, and the handoff notice comes back as the answer (2026-09-16).
    # This script reincarnates the session itself: should_recycle.
    environment = {**os.environ,
                   threshold_hook.REINCARNATION_OWNED_BY_CALLER_VARIABLE: "scripts/ghi-guide-agent-ask.py"}
    try:
        completed = subprocess.run(command, cwd=str(seat_dir), capture_output=True,
                                   text=True, timeout=timeout_seconds, check=False,
                                   env=environment, input=prompt)
    except subprocess.TimeoutExpired:
        return None, f"claude was silent for {timeout_seconds}s and was killed"
    except OSError as error:
        return None, f"could not run claude: {error}"
    # Parse stdout BEFORE branching on the exit code: a failing claude exits 1
    # and still writes a complete JSON result, with the diagnosis in `result`
    # (2026-09-11: the box's expired login). Reporting the raw blob cut at 500
    # characters showed usage counters and hid the cause, which sits ~1100
    # bytes in.
    result = None
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        result = parsed
    if completed.returncode != 0 or (result is not None and result.get("is_error")):
        if result is not None and result.get("result") is not None:
            detail = str(result.get("result")).strip()[:500]
            message = (f"claude exited {completed.returncode}: {detail}"
                       if completed.returncode != 0
                       else f"claude reported an error: {detail}")
        else:
            detail = (completed.stderr or completed.stdout or "no output").strip()[:500]
            message = f"claude exited {completed.returncode}: {detail}"
        if LOGGED_OUT_PATTERN.search(detail):
            message += LOGGED_OUT_REMEDY
        return None, message
    if result is None:
        return None, f"claude produced no parseable result: {completed.stdout[:500]!r}"
    return result, None


def ask(question: str, include_closed: bool, seat_dir: Path, repo: str,
       timeout_seconds: int = ASK_TIMEOUT_SECONDS,
       projects_root: Path = None,
       request_form: str = GHI_GUIDE_AGENT_REQUEST_FORM_READING_LIST):
    """The whole ask path (design § The ask path, steps 1-5). Returns
    (answer, closed_on, error): the checked answer object, of a kind
    `request_form` allows, and closed_issue_dates of its issue numbers, or
    (None, None, error)."""
    kinds = GHI_GUIDE_AGENT_ANSWER_KINDS_EACH_REQUEST_FORM_ALLOWS[request_form]
    # Every turn of the ask, the cold start and the drift recheck included,
    # gets the same schema.
    json_schema = ghi_guide_agent_answer_json_schema_build_for_kinds(kinds)
    if projects_root is None:
        projects_root = Path.home() / ".claude" / "projects"
    state_path = seat_dir / STATE_FILE_NAME
    lock_path = seat_dir / LOCK_FILE_NAME

    # One deadline for the whole ask, however many turns it takes.
    deadline = time.monotonic() + timeout_seconds

    def turn(prompt, resume_session_id):
        """A claude turn that can only spend what the ask has left."""
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None, (f"the ask's {timeout_seconds}s budget was already spent "
                          "before this turn could start")
        return run_claude(prompt, resume_session_id, seat_dir, remaining, json_schema)

    try:
        return _locked_ask(question, include_closed, seat_dir, repo,
                           projects_root, state_path, lock_path, turn, kinds)
    except SeatDirectoryUnusable as error:
        return None, None, str(error)


def _locked_ask(question, include_closed, seat_dir, repo, projects_root,
                state_path, lock_path, turn, kinds):
    """Holds the lock, settles which mirror this run publishes into, and
    cleans up a throwaway one on every exit path."""
    with state_lock(lock_path) as locked:
        state = load_state(state_path) if locked else default_state()

        # The shared mirror has exactly one writer: the lock holder. A
        # contended ask publishes into a private directory it deletes on the
        # way out, so the two runs' renames can never interleave and leave a
        # reader looking at a new open file beside an old closed one, or roll
        # the cache cutoff backward (PR #143 review, Codex P2). This costs
        # nothing extra: a contended ask cold-starts, so it was fetching the
        # whole corpus either way. It is also what the design already asks
        # for in spirit — "nothing waits, nothing shares a transcript" — with
        # the mirror counted among the things not shared.
        throwaway_mirror = None
        if locked:
            mirror_dir = seat_dir / mirror_refresh.DEFAULT_MIRROR_DIR
        else:
            seat_dir.mkdir(parents=True, exist_ok=True)
            throwaway_mirror = Path(tempfile.mkdtemp(
                prefix=".ghi-mirror-throwaway-", dir=seat_dir))
            mirror_dir = throwaway_mirror

        try:
            return _ask_within_lock(question, include_closed, seat_dir, repo,
                                    projects_root, state, state_path, locked,
                                    mirror_dir, turn, kinds)
        finally:
            if throwaway_mirror is not None:
                shutil.rmtree(throwaway_mirror, ignore_errors=True)


def fast_forward_seat_checkout(seat_dir: Path) -> str:
    """Bring the ghi-guide-agent checkout level with origin/main before it is read.

    Returns one line for stderr, or "" when there is nothing to say.

    WHY THE ASK DOES THIS. ghi-guide-agent answers questions about issues, and the
    substance of most issues lives in THIS repository — the pair documents
    under docs/issues/ and the wiki pages — which it reads from this checkout.
    A stale checkout means stale answers about the very designs the issues
    point at, and it means ghi-guide-agent runs under superseded skills and a
    superseded copy of this script. Until 2026-09-15 the freshness hook's
    merge was the only thing keeping it current; that merge is gone
    (nedschorus#324 — it kept landing on heads frozen under review), so the
    refresh moves to the one caller that KNOWS an ask is about to happen,
    rather than a turn-end hook that had to guess. User-ruled 2026-09-15;
    the remaining half of nedschorus#334.

    NOT checkout-freshness-catch-up.py's fast_forward_reference_checkout.
    That one requires the checkout to be parked on main and treats any other
    branch as a blocker — which is exactly the guarantee a REFERENCE copy
    needs, and this checkout sits on its own `ghi-guide-agent` branch. Loosening it
    for this caller would weaken it for the reference copy, so this is a
    second, narrower function rather than a shared one.

    FRESHNESS MUST NEVER FAIL AN ASK. Every failure path here returns a line
    and lets the ask proceed against whatever is on disk. A slightly stale
    reading list beats no reading list — and a caller cannot tell an ask that
    failed here from one where the box was down, so failing would send it
    down the ghi-write fallback ladder for a reason that does not warrant it.
    """

    def git(arguments, timeout=60):
        # LC_ALL=C for the same reason the freshness hook forces it: this
        # reads git's refusal prose into an operator-facing line.
        try:
            return subprocess.run(["git", *arguments], cwd=str(seat_dir),
                                  capture_output=True, text=True, check=False,
                                  timeout=timeout, env={**os.environ, "LC_ALL": "C"})
        except (OSError, subprocess.SubprocessError) as error:
            return subprocess.CompletedProcess(
                arguments, 1, "", f"{type(error).__name__}: {error}")

    inside = git(["rev-parse", "--is-inside-work-tree"], timeout=15)
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        return f"ghi-guide-agent-ask: {seat_dir} is not a git checkout; leaving it as it stands"

    status = git(["status", "--porcelain", "-z"], timeout=30)
    if status.returncode != 0:
        # An unreadable tree reads as unsafe, never as clean — the same
        # silent-safety rule the freshness hook applies to the same question.
        return "ghi-guide-agent-ask: could not read the seat checkout's status; not refreshing it"
    tracked_changes = [entry for entry in git_output.status_entries(status.stdout)
                       if entry.code != "??"]
    if tracked_changes:
        # ghi-guide-agent's document-side link repairs go through ghi-issue-write.py's
        # pull requests, so uncommitted tracked changes here are real work, not debris.
        return (f"ghi-guide-agent-ask: the seat checkout has {len(tracked_changes)} uncommitted "
                f"tracked change(s); not refreshing it")

    fetched = git(["fetch", "--quiet", "origin"], timeout=60)
    if fetched.returncode != 0:
        return (f"ghi-guide-agent-ask: could not fetch origin in the seat checkout "
                f"({fetched.stderr.strip() or 'no detail'}); answering from what is on disk")

    behind = git(["rev-list", "--count", "HEAD..origin/main"], timeout=30)
    try:
        count = int(behind.stdout.strip())
    except ValueError:
        return "ghi-guide-agent-ask: could not count the seat checkout's drift from origin/main"
    if count == 0:
        return ""

    merged = git(["merge", "--ff-only", "--no-overwrite-ignore", "origin/main"], timeout=120)  # pragma: no mutate, a limit a second longer or shorter on a fast-forward changes nothing a test can see without a git merge that runs for two minutes
    if merged.returncode != 0:
        return (f"ghi-guide-agent-ask: the seat checkout is {count} behind origin/main and would "
                f"not fast-forward ({merged.stderr.strip() or 'no detail'}); answering from "
                f"what is on disk")
    return f"ghi-guide-agent-ask: refreshed the seat checkout {count} commit(s) to origin/main"


def _ask_within_lock(question, include_closed, seat_dir, repo, projects_root,
                     state, state_path, locked, mirror_dir, turn, kinds):
    """The ask itself, with the lock decision and the mirror already settled.

    Split out so the throwaway mirror's cleanup is one `finally` around the
    whole body rather than a branch on every early return.
    """

    # The checkout itself comes first, before anything reads from it: the
    # documents the issues point at, the skills ghi-guide-agent runs under, and this
    # script's own siblings all come off this disk.
    #
    # Only under the lock. A contended run holds no lock and publishes into a
    # throwaway mirror precisely so it cannot disturb the holder; swapping the
    # checkout's files beneath the holder's running claude would undo that.
    if locked:
        refresh_line = fast_forward_seat_checkout(seat_dir)
        if refresh_line:
            print(refresh_line, file=sys.stderr)

    # Steps 1-2 interleave, because which refresh is owed depends on
    # whether this ask resumes or cold-starts, and the reincarnation decision
    # in turn depends on what the delta saw close.
    #
    # With no session to resume (first ever ask, or a contended lock),
    # the answer is known before any fetch: a cold start needs the whole
    # corpus rebuilt anyway, so go straight to the full refresh. Running
    # the routine delta first would fetch the entire corpus TWICE on
    # every first run — the delta has no cutoff to search from without a
    # cache, so it is itself a full fetch.
    has_session = locked and state.get(GHI_GUIDE_AGENT_SESSION_ID_STATE_KEY)
    changed = []
    recycle, recycle_reason = False, None

    if has_session:
        delta_result, error = mirror_refresh.refresh(mirror_dir, repo, full=False)
        if delta_result is None:
            return None, None, f"mirror refresh failed: {error}"
        changed = delta_result["changed"]
        cache = mirror_refresh.read_cache(mirror_dir / mirror_refresh.CACHE_FILE_NAME)
        # Counts a changed issue that is currently closed. An already-
        # closed issue touched again (a late comment) counts once more,
        # which only makes reincarnation more eager — the direction the
        # design asks for ("Reincarnation errs eager").
        new_closures = sum(
            1 for number in changed
            if cache.get("issues", {}).get(str(number), {}).get("state") == "CLOSED"
        )
        state["closes_since_birth"] = state.get("closes_since_birth", 0) + new_closures
        recycle, recycle_reason = should_recycle(state, seat_dir, projects_root)

    cold_starting = not has_session or recycle

    if cold_starting:
        if recycle_reason:
            # A reincarnation silently replacing the session would leave the
            # next investigator no way to tell a fresh answer from a
            # resumed one; the trigger that fired is the useful part.
            print(f"ghi-guide-agent-ask: reincarnating the session — {recycle_reason}",
                  file=sys.stderr)
        full_result, error = mirror_refresh.refresh(mirror_dir, repo, full=True)
        if full_result is None:
            return None, None, f"mirror refresh (full, for cold-start) failed: {error}"
        cache = mirror_refresh.read_cache(mirror_dir / mirror_refresh.CACHE_FILE_NAME)
        # The slot names the mirror DIRECTORY, not one of its files: the
        # design's sentence is followed by a bullet list of BOTH files, so
        # filling it with issues-open.md left issues-closed.md with no
        # stated location (PR #143 review, P3).
        cold_start_text = COLD_START_PROMPT_TEMPLATE.format(
            mirror_path=full_result["mirror_dir"])
        # The cold-start turn asks nothing, so its structured_output is not read.
        cold_reply, error = turn(cold_start_text, None)
        if cold_reply is None:
            return None, None, f"ghi-guide-agent cold-start failed: {error}"
        session_id = cold_reply["session_id"]
        resume_prompt = compose_resume_ask_prompt(question, include_closed, [], False)
    else:
        session_id = state[GHI_GUIDE_AGENT_SESSION_ID_STATE_KEY]
        resume_prompt = compose_resume_ask_prompt(question, include_closed, changed, True)

    answer_reply, error = turn(resume_prompt, session_id)
    if answer_reply is None:
        return None, None, f"ghi-guide-agent ask failed: {error}"
    session_id = answer_reply.get("session_id", session_id)
    answer, problem = ghi_guide_agent_answer_extract_and_schema_check_from_claude_result(answer_reply, kinds)

    # Step 4: post-check.
    stale = False
    if answer is not None:
        unexpected = find_unexpected_closed_pointers(
            answer_issue_numbers(answer), cache, include_closed)
        if unexpected:
            stale = True
            drift_reply, error = turn(compose_drift_notice(unexpected), session_id)
            if drift_reply is not None:
                session_id = drift_reply.get("session_id", session_id)
                corrected, _ = ghi_guide_agent_answer_extract_and_schema_check_from_claude_result(drift_reply, kinds)
                if corrected is not None:
                    answer = corrected
            # A failed recheck keeps the first answer rather than failing
            # the whole ask: a closed issue in a reading list is tagged as
            # closed, which is better than no answer at all.

    if locked:
        if cold_starting:
            state = default_state()
        state[GHI_GUIDE_AGENT_SESSION_ID_STATE_KEY] = session_id
        recent = state.get("recent_matches", [])
        recent.append(stale)
        state["recent_matches"] = recent[-STALE_MATCH_WINDOW:]
        save_state(state_path, state)

    if answer is None:
        return None, None, GHI_GUIDE_AGENT_ANSWER_NOT_USABLE_MESSAGE_TEMPLATE.format(problem=problem)
    return answer, closed_issue_dates(answer_issue_numbers(answer), cache), None


def build_remote_command(question: str, include_closed: bool, repo: str,
                         question_on_stdin: bool = False,
                         print_answer_json: bool = False,
                         request_form: str = GHI_GUIDE_AGENT_REQUEST_FORM_READING_LIST) -> str:
    """The command the box runs, as one string: ssh hands it to the box's
    login shell, which parses it exactly once — no second parse layer here
    (unlike the launchers, which also cross tmux's pane-command parse), so
    shlex.quote is the whole escaping story for operator values.

    The seat path is resolved BOX-side, by the box's own shell, as
    $HOME/agents/ghi-guide-agent: the fixed box root launch-claude-ubuntu seats
    every box seat under, reading no agents-root variable (user-ruled
    2026-09-22, merge-lane-2's walk). A variable read here would steer an
    interactive box shell and not this ssh one, which sources no ~/.bashrc. Splicing this machine's expanded path in instead was the
    first live run's failure: the Mac sent `cd /Users/el/agents/ghi-guide-agent`,
    which of course does not exist on the box.

    Two further properties this shape buys:
      - `--seat-dir "$PWD"` after a successful cd means the box-side run
        runs in the directory the shell entered, which is the seat by
        construction, whatever DEFAULT_SEAT_DIR resolves to there.
      - a failed cd keeps the shell's OWN diagnostic (which names the real
        cause — missing, not a directory, unreadable) and adds the remedy
        beside it. Suppressing the shell's line would make a permissions
        failure read as "no seat", pointing the operator at the wrong fix.
    """
    # With `question_on_stdin` the caller hands ssh the question as stdin,
    # since one argument may not exceed 128 KiB on Linux.
    invocation = "python3 scripts/ghi-guide-agent-ask.py " + (
        "--question-file /dev/stdin" if question_on_stdin
        else shlex.quote(question))
    if include_closed:
        invocation += " --include-closed"
    if print_answer_json:
        invocation += " --print-answer-json"
    if request_form != GHI_GUIDE_AGENT_REQUEST_FORM_READING_LIST:
        invocation += " --request-form " + shlex.quote(request_form)
    invocation += " --repo " + shlex.quote(repo)
    invocation += ' --seat-dir "$PWD"'
    return "\n".join([
        'seat="$HOME/agents/ghi-guide-agent"',
        'cd "$seat" || {',
        '  echo "ghi-guide-agent-ask: could not enter the ghi-guide-agent seat at $seat on this box'
        ' — bootstrap it (a checkout of this repository at that path), then retry" >&2',
        '  exit 1',
        '}',
        invocation,
    ])


def running_on_ned_box() -> bool:
    return socket.gethostname().split(".")[0] == NED_BOX_HOSTNAME


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Ask ghi-guide-agent a reading-list question.",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__,
    )
    parser.add_argument("question", nargs="?",
                        help="the reading-list question, relayed verbatim")
    parser.add_argument("--question-file", default=None,
                        help="read the question from this file instead; for a "
                             "question too long to pass as one argument")
    parser.add_argument("--include-closed", action="store_true",
                        help="closed history is wanted (precedent, absence claims)")
    parser.add_argument("--print-answer-json", action="store_true",
                        help="print ghi-guide-agent's answer as one JSON object on stdout, "
                             "whatever the exit code, instead of the text printed by default")
    parser.add_argument("--request-form", choices=list(GHI_GUIDE_AGENT_ANSWER_KINDS_EACH_REQUEST_FORM_ALLOWS),
                        default=GHI_GUIDE_AGENT_REQUEST_FORM_READING_LIST,
                        help="reading-list (default): the answer is a reading list; draft-verdict: "
                             "the question holds a draft GHI-MD, and the answer is a "
                             "verdict or a ruling question")
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--seat-dir", default=None,
                        help="run locally against this seat directory, skipping the "
                             "SSH-to-box decision entirely (testing; an operator running "
                             "box-side with a non-default path)")
    arguments = parser.parse_args(argv)
    if (arguments.question is None) == (arguments.question_file is None):
        parser.error("give the question, or --question-file, but not both")
    question = arguments.question
    if arguments.question_file is not None:
        try:
            question = Path(arguments.question_file).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            print(f"ghi-guide-agent-ask: could not read the question file: {error}",
                  file=sys.stderr)
            return 1

    if arguments.seat_dir is not None:
        seat_dir = Path(arguments.seat_dir).expanduser()
    else:
        seat_dir = DEFAULT_SEAT_DIR
        if not running_on_ned_box():
            question_on_stdin = arguments.question_file is not None
            remote_command = build_remote_command(question,
                                                  arguments.include_closed,
                                                  arguments.repo,
                                                  question_on_stdin,
                                                  arguments.print_answer_json,
                                                  arguments.request_form)
            try:
                completed = subprocess.run(
                    ["ssh", AGENT_BOX, remote_command], capture_output=True, text=True,
                    timeout=SSH_TIMEOUT_SECONDS, check=False,
                    input=question if question_on_stdin else None,
                )
            except subprocess.TimeoutExpired:
                print(f"ghi-guide-agent-ask: the ssh call to {AGENT_BOX} did not finish "
                      f"within {SSH_TIMEOUT_SECONDS}s, so this script stopped it; "
                      f"that alone does not show {AGENT_BOX} is down.", file=sys.stderr)
                return 1
            except OSError as error:
                print(f"ghi-guide-agent-ask: could not start ssh to {AGENT_BOX}: {error}",
                      file=sys.stderr)
                return 1
            sys.stdout.write(completed.stdout)
            sys.stderr.write(completed.stderr)
            return completed.returncode

    if not seat_dir.is_dir():
        # One line, because scripts/ghi-issue-write.py reports only the last stderr line.
        print(f"ghi-guide-agent-ask: the ask failed: ghi-guide-agent's agent-home "
              f"{seat_dir} does not exist on {NED_BOX_HOSTNAME}, and the ask runs inside it. "
              f"Create it, from either machine, with `ssh nedlern@{NED_BOX_HOSTNAME} "
              f"'git -C ~/Projects/nedschorus worktree add --detach {seat_dir} origin/main && "
              f"touch \"$(git -C {seat_dir} rev-parse --absolute-git-dir)/agent-home-marker\"'`, "
              f"which makes it an agent-home resting at origin/main; then run the command that "
              f"printed this message again, unchanged, once. If the agent-home cannot be "
              f"created, or the second ask fails too: when you are filing or editing a GHI, "
              f"go on down the ask's fallback ladder in .claude/skills/ghi-write/SKILL.md; "
              f"for any other ask, go on without ghi-guide-agent's answer, and tell the user that "
              f"ghi-guide-agent cannot answer until its agent-home exists on ned-box.",
              file=sys.stderr)
        return 1

    answer, closed_on, error = ask(question, arguments.include_closed, seat_dir,
                                   arguments.repo, request_form=arguments.request_form)
    if answer is None:
        print(f"ghi-guide-agent-ask: {error}", file=sys.stderr)
        return 1
    stdout_text, stderr_text, exit_code = ghi_guide_agent_answer_render_as_caller_stdout_stderr_and_exit_code(
        answer, closed_on)
    if arguments.print_answer_json:
        print(json.dumps(answer))
    elif stdout_text:
        print(stdout_text)
    if stderr_text:
        print(stderr_text, file=sys.stderr)
    if exit_code == 0 and not arguments.include_closed:
        print(OPEN_ISSUES_ONLY_INCLUDE_CLOSED_HINT_MESSAGE, file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
