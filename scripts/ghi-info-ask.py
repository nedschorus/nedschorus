#!/usr/bin/env python3
"""Ask ghi-info, the project's knowledge agent over its GitHub-issue corpus
(nedschorus#46, design doc docs/issues/46-ghi-info-agent-design.md § The
ask path). Run by any agent — and by the ghi-write skill's step 1 — before
filing or editing an issue, to learn what already covers the ground.

Usage:
  ghi-info-ask.py "<question>" [--include-closed]

Prints the reading list ghi-info returns (or its escalate:/out-of-scope
reply, passed through verbatim) to stdout and exits 0. On any failure —
gh unreachable, the box unreachable, ghi-info's own run erroring or timing
out — prints one line to stderr and exits 1. A failed ask never blocks a
write (design's own words): the caller's job is to fall down the ghi-write
skill's fallback ladder, not to treat exit 1 as fatal.

Seat and machine: ghi-info lives ONLY on the Ubuntu box, at
$NEDSCHORUS_AGENTS_ROOT/ghi-info (default ~/agents/ghi-info) — its mirror,
session id, and reincarnation counters all live in that one checkout, per the
design's "wrapper state ... lives there." This script is the SAME file on
both machines (it is checked into the repo, so every checkout — Mac or box
— carries an identical copy): on the Mac it notices no seat directory
locally and re-execs itself over `ssh ned`, one hop, so every step below
(refresh, session state, the claude call, the post-check) runs box-side
where the mirror and state actually live. On the box, inside a bootstrapped
seat, it just runs.

Where the box's seat is, is resolved BY THE BOX — its own shell applies the
same ${NEDSCHORUS_AGENTS_ROOT:-~/agents} rule launch-claude-ubuntu
documents. This script never sends a path of its own: the first live run
failed exactly there, having spliced in the Mac's expanded
/Users/el/agents/ghi-info, which of course does not exist on the box.

There is no wrapper-side auto-bootstrap: if the seat does not exist on the
box, the run says so and names the path it looked in, rather than trying to
create a knowledge agent's home out of thin air. A caller that gets that
error is not stuck — the ghi-write skill's fallback ladder covers a failed
ask by design.

Session lifecycle (design § The ghi-info session): no process outlives one
ask. Every call is a fresh `claude -p`, resumed by the session id under
`ghi_info_session_id` in `.ghi-info-state.json` in the seat directory,
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
from it. ghi-info's answers cite the pair documents under docs/issues/ and
the wiki pages, and it reads those from this disk — a stale checkout is
stale answers about the very designs the issues point at, and superseded
skills to answer under. The freshness hook's merge used to keep the
checkout current; that merge is gone, so the refresh belongs to the caller
that knows an ask is about to happen. It never fails an ask: any refusal —
a dirty tree, a commit of ghi-info's own, an unreachable origin — is one
stderr line and the ask proceeds against what is on disk.

Concurrency: the state file is flock'd. An ask that cannot get the lock
(another ask is mid-flight) does not wait and does not touch the stored
session — it cold-starts a throwaway session of its own and never writes
its outcome back to the state file (design: "nothing waits, nothing shares
a transcript").

Two guards against a reply that is not the answer (measured 2026-09-17).
This script returns the run's LAST message, and on that day ghi-info answered
the question at 20:16:59Z and then answered the checkout-freshness Stop hook
13 seconds later; the caller got "No action needed on my part ..." with exit
0, so its fallback ladder never fired. So the run no longer loads this
project's settings (--setting-sources user, the flag PR #417 gave the
cold-read cells for the same leak), and a reply that names no issue and is
neither out-of-scope nor escalate: fails the ask instead of being passed
back.

Post-check (design step 4): every pointer ghi-info returns is checked
against the just-refreshed mirror by this script, never taken on the
agent's word. A closed pointer that the caller did not ask for via
--include-closed is treated as drift — stale context — and triggers exactly
one recheck turn, the corrected reply becoming the final answer. This
script does not itself rewrite ghi-info's truthful-tag wording; the
cold-start prompt already instructs ghi-info to tag closed pointers itself,
and the post-check's job is deciding WHETHER a recheck is owed, not
re-authoring the reply.
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

_watcher_spec = importlib.util.spec_from_file_location(
    "watch_agent_dialogs", SCRIPT_DIRECTORY / "watch-agent-dialogs.py")
watcher = importlib.util.module_from_spec(_watcher_spec)
_watcher_spec.loader.exec_module(watcher)

_threshold_hook_spec = importlib.util.spec_from_file_location(
    "handoff_context_threshold_hook", SCRIPT_DIRECTORY / "handoff-context-threshold-hook.py")
threshold_hook = importlib.util.module_from_spec(_threshold_hook_spec)
_threshold_hook_spec.loader.exec_module(threshold_hook)

AGENT_BOX = os.environ.get("NEDSCHORUS_AGENT_BOX", "ned")
DEFAULT_AGENTS_ROOT = Path(os.environ.get("NEDSCHORUS_AGENTS_ROOT", "~/agents")).expanduser()
DEFAULT_SEAT_DIR = DEFAULT_AGENTS_ROOT / "ghi-info"
DEFAULT_REPO = "nedschorus/nedschorus"
STATE_FILE_NAME = ".ghi-info-state.json"
LOCK_FILE_NAME = ".ghi-info-state.lock"

# Model: named constant + env override, per issue #46's own framing —
# "settled empirically." Starting pick for this build, not a measured
# choice among fable/opus/sonnet.
GHI_INFO_MODEL = os.environ.get("GHI_INFO_MODEL", "claude-sonnet-5")
# "One overall timeout (inside the hook budget)" (design § The ask path) —
# ONE deadline for the whole ask, not one per claude call. An ask can spend
# up to three turns (a cold start's two, plus a drift recheck), and giving
# each the full allowance made a nominal five-minute ask a possible
# fifteen-minute one — the opposite of what "inside the hook budget" is for
# (PR #143 review, Codex P2). Each turn is handed only what is left.
# NM's three-watchdog machinery is deliberately not carried over (design:
# "version 1 here starts with one timeout").
ASK_TIMEOUT_SECONDS = int(os.environ.get("GHI_INFO_ASK_TIMEOUT_SECONDS", "300"))

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
# misattribution, not a wrong answer: the Mac reports "the box was silent"
# instead of the box's real refresh error, and both land the caller on the
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

POINTER_PATTERN = re.compile(r"#(\d+)")

COLD_START_PROMPT_TEMPLATE = """You are ghi-info: this project's knowledge agent over its GitHub-issue corpus. Other agents send you one request at a time; you answer it from the corpus you hold in context and stop. You are the judgment layer — every mechanical fact (fetching, counting, verifying) is script work done for you before a request reaches you.

You run inside a checkout of the project repository; your knowledge is the local mirror in it at {mirror_path}, regenerated by script and refreshed before every request:

- issues-open.md — every open issue in full: number, title, labels, updated time, body, comments. Read this file whole now, before anything else.
- issues-closed.md — one line per closed issue. Do not load it whole; grep it only when a request asks about closed history.

GitHub is the source of truth; the mirror is your working copy of it. Answer from the mirror only — never fetch issue state from GitHub (no gh queries, no API, no web). The facts a request states are already established by script; your job is only the judgment.

Requests arrive in four forms:

1. **You are asked for a reading list**: what should an agent read before it files or edits an issue on some topic. Reply with a bare list — "read #13, #24, #31" — plus, only when needed, note lines in plain sentences. Closed issues belong in a reply only when the request says closed history is wanted; tag each truthfully: "#31 (closed 2026-08-08)".
2. **You are shown a draft issue** — title and body — and asked whether the corpus already covers it. When the draft is an edit of an existing issue, the request names that issue: leave it out of the comparison. Reply with exactly one line, nothing else: `verdict: too-similar #n` (an existing issue already covers this ground; #n is that issue), or `verdict: related #n,#m` (no collision, but the author should know these), or `verdict: unrelated`. In these shapes #n,#m stands for one or more issue numbers. A reply in any other shape is thrown away.
3. **You are told a fact that corrects your last reply** — an issue you cited has closed — and asked to redo that one judgment. The fact is already established by script from the refreshed mirror: do not question or verify it; re-read the named entry in issues-closed.md, including any Superseded-by: link, and reply with a corrected reading list.
4. **You are asked to repair a link** — a cross-reference the maintenance sweep found broken. The request states the defect; repair exactly that link and nothing else. Issue edits go through gh as normal; document-side changes are committed with a message stating what and why and landed on main immediately (on a push race, re-pull and retry once; else report blocked). Reply done: <the repair>, done: no change needed — <why>, or blocked: <what stopped you>.

Boundaries:

- Asked a question about anything beyond the issue corpus — the wiki, the code, anything else — reply exactly: out-of-scope.
- Whether an old ruling still binds is never yours to judge. Reply: escalate: <one sentence naming the ruling and the doubt>.
- These boundary replies apply to questions. A draft-body request always gets a verdict line — conflict with a ruled issue is exactly what too-similar covers. A question beyond the corpus gets out-of-scope even when it touches a ruling."""


def compose_resume_ask_prompt(question: str, include_closed: bool, changed_numbers,
                              is_resume: bool) -> str:
    """§ Prompts: Resume ask prompt. The changed-entries preamble appears only
    on a resumed session whose refresh actually changed entries; the
    asker's question rides through unrewritten."""
    parts = []
    if is_resume and changed_numbers:
        named = ", ".join(f"#{n}" for n in changed_numbers)
        parts.append(
            f"Since your last request, these mirror entries changed: {named}. "
            "Re-read them in the mirror before answering — an entry may have "
            "moved to issues-closed.md."
        )
    parts.append(f"You are asked for a reading list. {question}")
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


def is_passthrough_reply(text: str) -> bool:
    """escalate:/out-of-scope replies are not reading lists (design step 4);
    the post-check does not apply to them, and neither does drift recheck."""
    stripped = text.strip().lower()
    return stripped.startswith("escalate:") or stripped == "out-of-scope"


def reply_answers_the_question(text: str) -> bool:
    """Whether a reply is an answer at all, rather than something else the
    session said.

    A reading list names issues, and the two passthrough replies are fixed
    strings; anything with neither is not an answer this caller can use. The
    case that earned this check (2026-09-17): the run's last message was
    "No action needed on my part -- this session hasn't touched any scripts
    or tests", a reply to a Stop hook, and the ask returned it with exit 0,
    so the caller's fallback ladder never fired.

    A true answer that names no issue -- "nothing covers this" in those words
    -- is refused by this check too, and that costs one trip down the
    fallback ladder, which never blocks a write. Silently passing a
    non-answer costs a write made against no knowledge at all.
    """
    return bool(POINTER_PATTERN.search(text)) or is_passthrough_reply(text)


def find_unexpected_closed_pointers(reply_text: str, cache: dict, include_closed: bool):
    """Every #n pointer in the reply, checked against the mirror cache.

    --include-closed makes every closed pointer expected by definition (the
    caller asked for closed history); otherwise any closed pointer means
    ghi-info's context predates the issue's close — drift, not a fact it
    established. Returns [(number, closed_date), ...].
    """
    if include_closed:
        return []
    flagged = []
    for match in POINTER_PATTERN.finditer(reply_text):
        number = match.group(1)
        issue = cache.get("issues", {}).get(number)
        if issue and issue.get("state") == "CLOSED":
            closed_at = issue.get("closedAt") or ""
            flagged.append((number, closed_at[:10] if closed_at else "?"))
    # Stable order, no duplicate numbers.
    seen = set()
    unique = []
    for number, date in flagged:
        if number not in seen:
            seen.add(number)
            unique.append((number, date))
    return unique


# The key under which `.ghi-info-state.json` holds the id of the ghi-info
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
GHI_INFO_SESSION_ID_STATE_KEY = "ghi_info_session_id"
# Read-only, for state files written before the rename. load_state migrates it
# in, every write after that uses the new key alone, so a state file converts on
# the first read this program gives it. Removable once no seat carries a
# `.ghi-info-state.json` older than 2026-09-22.
LEGACY_SESSION_ID_STATE_KEY = "session_id"


def default_state() -> dict:
    return {GHI_INFO_SESSION_ID_STATE_KEY: None, "closes_since_birth": 0, "recent_matches": []}


def load_state(state_path: Path) -> dict:
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default_state()
    merged = default_state()
    merged.update({key: state[key] for key in merged if key in state})
    if (merged[GHI_INFO_SESSION_ID_STATE_KEY] is None
            and state.get(LEGACY_SESSION_ID_STATE_KEY) is not None):
        merged[GHI_INFO_SESSION_ID_STATE_KEY] = state[LEGACY_SESSION_ID_STATE_KEY]
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
    project_directory = watcher.project_directory_for_seat(seat_dir, projects_root)
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
    size = transcript_size_bytes(seat_dir, state.get(GHI_INFO_SESSION_ID_STATE_KEY), projects_root)
    if size is not None and size >= TRANSCRIPT_SIZE_THRESHOLD_BYTES:
        return True, f"transcript {size} bytes (threshold {TRANSCRIPT_SIZE_THRESHOLD_BYTES})"
    transcript_path = transcript_path_for(seat_dir, state.get(GHI_INFO_SESSION_ID_STATE_KEY), projects_root)
    used = (threshold_hook.context_used_percentage_from_transcript(str(transcript_path))
            if transcript_path is not None else None)
    if used is not None and used >= CONTEXT_USED_PERCENTAGE_THRESHOLD:
        return True, (f"context {used:.0f}% used "
                      f"(threshold {CONTEXT_USED_PERCENTAGE_THRESHOLD:g}%)")
    return False, None


def run_claude(prompt: str, resume_session_id, seat_dir: Path, timeout_seconds: int):
    """One `claude -p` turn. Returns (result_dict, error). No terminal exists
    to approve tool use here (same reasoning as nedsmessenger's adapter,
    the named precedent) — bypassPermissions is the only workable mode for
    an unattended agent."""
    # --setting-sources user keeps THIS PROJECT'S hooks out of the run
    # (measured 2026-09-17). ghi-info answered a reading-list question
    # correctly at 20:16:59Z and then, 13 seconds later, answered the
    # checkout-freshness Stop hook's "Rerun the test suites for what you
    # touched"; this script returns the run's last message, so the caller got
    # the housekeeping reply and the reading list was thrown away, with exit
    # 0. A cold-read cell had the same leak, and PR #417 gave it the same
    # flag. The seat's own settings.json is project settings, so nothing here
    # needs it: permissions come from bypassPermissions above.
    command = ["claude", "-p", prompt, "--output-format", "json",
              "--setting-sources", "user",
              "--permission-mode", "bypassPermissions", "--model", GHI_INFO_MODEL]
    if resume_session_id:
        command += ["--resume", resume_session_id]
    # Without this the handoff hook tells the session to hand off at its
    # threshold, and the handoff notice comes back as the answer (2026-09-16).
    # This script reincarnates the session itself: should_recycle.
    environment = {**os.environ,
                   threshold_hook.REINCARNATION_OWNED_BY_CALLER_VARIABLE: "scripts/ghi-info-ask.py"}
    try:
        completed = subprocess.run(command, cwd=str(seat_dir), capture_output=True,
                                   text=True, timeout=timeout_seconds, check=False,
                                   env=environment)
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
       projects_root: Path = None):
    """The whole ask path (design § The ask path, steps 1-5). Returns
    (answer_text, error) — exactly one is not None."""
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
        return run_claude(prompt, resume_session_id, seat_dir, remaining)

    try:
        return _locked_ask(question, include_closed, seat_dir, repo,
                           projects_root, state_path, lock_path, turn)
    except SeatDirectoryUnusable as error:
        return None, str(error)


def _locked_ask(question, include_closed, seat_dir, repo, projects_root,
                state_path, lock_path, turn):
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
                                    mirror_dir, turn)
        finally:
            if throwaway_mirror is not None:
                shutil.rmtree(throwaway_mirror, ignore_errors=True)


def fast_forward_seat_checkout(seat_dir: Path) -> str:
    """Bring the ghi-info checkout level with origin/main before it is read.

    Returns one line for stderr, or "" when there is nothing to say.

    WHY THE ASK DOES THIS. ghi-info answers questions about issues, and the
    substance of most issues lives in THIS repository — the pair documents
    under docs/issues/ and the wiki pages — which it reads from this checkout.
    A stale checkout means stale answers about the very designs the issues
    point at, and it means ghi-info runs under superseded skills and a
    superseded copy of this script. Until 2026-09-15 the freshness hook's
    merge was the only thing keeping it current; that merge is gone
    (nedschorus#324 — it kept landing on heads frozen under review), so the
    refresh moves to the one caller that KNOWS an ask is about to happen,
    rather than a turn-end hook that had to guess. User-ruled 2026-09-15;
    the remaining half of nedschorus#334.

    NOT checkout-freshness-catch-up.py's fast_forward_reference_checkout.
    That one requires the checkout to be parked on main and treats any other
    branch as a blocker — which is exactly the guarantee a REFERENCE copy
    needs, and this checkout sits on its own `ghi-info` branch. Loosening it
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
        return f"ghi-info-ask: {seat_dir} is not a git checkout; leaving it as it stands"

    status = git(["status", "--porcelain"], timeout=30)
    if status.returncode != 0:
        # An unreadable tree reads as unsafe, never as clean — the same
        # silent-safety rule the freshness hook applies to the same question.
        return "ghi-info-ask: could not read the seat checkout's status; not refreshing it"
    tracked_changes = [line for line in status.stdout.splitlines()
                       if not line.startswith("??")]
    if tracked_changes:
        # ghi-info commits its own document-side link repairs and lands them
        # on main; work in progress here is real work, not debris.
        return (f"ghi-info-ask: the seat checkout has {len(tracked_changes)} uncommitted "
                f"tracked change(s); not refreshing it")

    fetched = git(["fetch", "--quiet", "origin"], timeout=60)
    if fetched.returncode != 0:
        return (f"ghi-info-ask: could not fetch origin in the seat checkout "
                f"({fetched.stderr.strip() or 'no detail'}); answering from what is on disk")

    behind = git(["rev-list", "--count", "HEAD..origin/main"], timeout=30)
    try:
        count = int(behind.stdout.strip())
    except ValueError:
        return "ghi-info-ask: could not count the seat checkout's drift from origin/main"
    if count == 0:
        return ""

    merged = git(["merge", "--ff-only", "origin/main"], timeout=120)
    if merged.returncode != 0:
        return (f"ghi-info-ask: the seat checkout is {count} behind origin/main and would "
                f"not fast-forward ({merged.stderr.strip() or 'no detail'}); answering from "
                f"what is on disk")
    return f"ghi-info-ask: refreshed the seat checkout {count} commit(s) to origin/main"


def _ask_within_lock(question, include_closed, seat_dir, repo, projects_root,
                     state, state_path, locked, mirror_dir, turn):
    """The ask itself, with the lock decision and the mirror already settled.

    Split out so the throwaway mirror's cleanup is one `finally` around the
    whole body rather than a branch on every early return.
    """

    # The checkout itself comes first, before anything reads from it: the
    # documents the issues point at, the skills ghi-info runs under, and this
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
    has_session = locked and state.get(GHI_INFO_SESSION_ID_STATE_KEY)
    changed = []
    recycle, recycle_reason = False, None

    if has_session:
        delta_result, error = mirror_refresh.refresh(mirror_dir, repo, full=False)
        if delta_result is None:
            return None, f"mirror refresh failed: {error}"
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
            print(f"ghi-info-ask: reincarnating the session — {recycle_reason}",
                  file=sys.stderr)
        full_result, error = mirror_refresh.refresh(mirror_dir, repo, full=True)
        if full_result is None:
            return None, f"mirror refresh (full, for cold-start) failed: {error}"
        cache = mirror_refresh.read_cache(mirror_dir / mirror_refresh.CACHE_FILE_NAME)
        # The slot names the mirror DIRECTORY, not one of its files: the
        # design's sentence is followed by a bullet list of BOTH files, so
        # filling it with issues-open.md left issues-closed.md with no
        # stated location (PR #143 review, P3).
        cold_start_text = COLD_START_PROMPT_TEMPLATE.format(
            mirror_path=full_result["mirror_dir"])
        cold_reply, error = turn(cold_start_text, None)
        if cold_reply is None:
            return None, f"ghi-info cold-start failed: {error}"
        session_id = cold_reply["session_id"]
        resume_prompt = compose_resume_ask_prompt(question, include_closed, [], False)
    else:
        session_id = state[GHI_INFO_SESSION_ID_STATE_KEY]
        resume_prompt = compose_resume_ask_prompt(question, include_closed, changed, True)

    answer_reply, error = turn(resume_prompt, session_id)
    if answer_reply is None:
        return None, f"ghi-info ask failed: {error}"
    session_id = answer_reply.get("session_id", session_id)
    reply_text = (answer_reply.get("result") or "").strip()

    # Step 4: post-check.
    stale = False
    if not is_passthrough_reply(reply_text):
        unexpected = find_unexpected_closed_pointers(reply_text, cache, include_closed)
        if unexpected:
            stale = True
            drift_reply, error = turn(compose_drift_notice(unexpected), session_id)
            if drift_reply is not None:
                session_id = drift_reply.get("session_id", session_id)
                reply_text = (drift_reply.get("result") or "").strip()
            # A failed recheck falls back to the original reply rather
            # than failing the whole ask — the pointer may simply carry
            # a now-stale tag, which is better than no answer at all.

    if locked:
        if cold_starting:
            state = default_state()
        state[GHI_INFO_SESSION_ID_STATE_KEY] = session_id
        recent = state.get("recent_matches", [])
        recent.append(stale)
        state["recent_matches"] = recent[-STALE_MATCH_WINDOW:]
        save_state(state_path, state)

    if not reply_answers_the_question(reply_text):
        return None, ("ghi-info's reply names no issue and is not an "
                      "out-of-scope or escalate: reply, so it is not an "
                      f"answer to this question: {reply_text[:200]!r}")

    return reply_text, None


def build_remote_command(question: str, include_closed: bool, repo: str) -> str:
    """The command the box runs, as one string: ssh hands it to the box's
    login shell, which parses it exactly once — no second parse layer here
    (unlike the launchers, which also cross tmux's pane-command parse), so
    shlex.quote is the whole escaping story for operator values.

    The seat path is resolved BOX-side, by the box's own shell, using the
    same ${NEDSCHORUS_AGENTS_ROOT:-~/agents} rule launch-claude-ubuntu
    documents. Splicing this machine's expanded path in instead was the
    first live run's failure: the Mac sent `cd /Users/el/agents/ghi-info`,
    which of course does not exist on the box.

    Two further properties this shape buys:
      - `--seat-dir "$PWD"` after a successful cd means the box-side run
        takes the local branch unconditionally. Without it, a box whose
        seat directory is missing would ssh to itself — an infinite
        delegation loop rather than an error.
      - a failed cd keeps the shell's OWN diagnostic (which names the real
        cause — missing, not a directory, unreadable) and adds the remedy
        beside it. Suppressing the shell's line would make a permissions
        failure read as "no seat", pointing the operator at the wrong fix.
    """
    invocation = "python3 scripts/ghi-info-ask.py " + shlex.quote(question)
    if include_closed:
        invocation += " --include-closed"
    invocation += " --repo " + shlex.quote(repo)
    invocation += ' --seat-dir "$PWD"'
    return "\n".join([
        'seat="${NEDSCHORUS_AGENTS_ROOT:-$HOME/agents}/ghi-info"',
        'cd "$seat" || {',
        '  echo "ghi-info-ask: could not enter the ghi-info seat at $seat on this box'
        ' — bootstrap it (a checkout of this repository at that path), then retry" >&2',
        '  exit 1',
        '}',
        invocation,
    ])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Ask ghi-info a reading-list question.",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__,
    )
    parser.add_argument("question", help="the reading-list question, relayed verbatim")
    parser.add_argument("--include-closed", action="store_true",
                        help="closed history is wanted (precedent, absence claims)")
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--seat-dir", default=None,
                        help="run locally against this seat directory, skipping the "
                             "SSH-to-box decision entirely (testing; an operator running "
                             "box-side with a non-default path)")
    arguments = parser.parse_args(argv)

    if arguments.seat_dir is not None:
        seat_dir = Path(arguments.seat_dir).expanduser()
    else:
        seat_dir = DEFAULT_SEAT_DIR
        if not seat_dir.is_dir():
            remote_command = build_remote_command(arguments.question,
                                                  arguments.include_closed,
                                                  arguments.repo)
            try:
                completed = subprocess.run(
                    ["ssh", AGENT_BOX, remote_command], capture_output=True, text=True,
                    timeout=SSH_TIMEOUT_SECONDS, check=False,
                )
            except subprocess.TimeoutExpired:
                print(f"ghi-info-ask: the box was silent for {SSH_TIMEOUT_SECONDS}s "
                      "and was killed", file=sys.stderr)
                return 1
            except OSError as error:
                print(f"ghi-info-ask: could not reach the box: {error}", file=sys.stderr)
                return 1
            sys.stdout.write(completed.stdout)
            sys.stderr.write(completed.stderr)
            return completed.returncode

    if not seat_dir.is_dir():
        print(f"ghi-info-ask: no seat at {seat_dir} — bootstrap it first "
              f"(a checkout of this repository at that path on {AGENT_BOX}), then retry",
              file=sys.stderr)
        return 1

    answer, error = ask(arguments.question, arguments.include_closed, seat_dir,
                        arguments.repo)
    if answer is None:
        print(f"ghi-info-ask: {error}", file=sys.stderr)
        return 1
    print(answer)
    return 0


if __name__ == "__main__":
    sys.exit(main())
