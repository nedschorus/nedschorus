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
session id, and recycle counters all live in that one checkout, per the
design's "wrapper state ... lives there." This script is the SAME file on
both machines (it is checked into the repo, so every checkout — Mac or box
— carries an identical copy): on the Mac it notices the seat directory does
not exist locally and re-execs itself over `ssh ned` inside that directory
on the box, one hop, so every step below (refresh, session state, the
claude call, the post-check) runs box-side where the mirror and state
actually live. On the box itself, inside a bootstrapped seat, it just runs.
There is no wrapper-side auto-bootstrap: if the seat directory does not
exist yet on the box, this script says so and names the setup command
rather than trying to create a knowledge agent's home out of thin air.

Session lifecycle (design § The ghi-info session): no process outlives one
ask. Every call is a fresh `claude -p`, resumed by session id read from
`.ghi-info-state.json` in the seat directory, cold-started when no session
is stored or a recycle trigger fires (closes-since-birth, the stale-match
rate, or transcript size — the named constants below). Recycling means: one
FULL mirror rebuild (not the routine per-ask delta), then the cold-start
prompt as its own turn, then the actual question as a second turn on that
same fresh session — both prompts are verbatim from the design's § Prompts,
never composed here.

Concurrency: the state file is flock'd. An ask that cannot get the lock
(another ask is mid-flight) does not wait and does not touch the stored
session — it cold-starts a throwaway session of its own and never writes
its outcome back to the state file (design: "nothing waits, nothing shares
a transcript").

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
import subprocess
import sys
from datetime import datetime, timezone
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
# applied per claude call, not once across a cold-start's two turns plus a
# possible drift recheck; NM's three-watchdog machinery is deliberately not
# carried over (design: "version 1 here starts with one timeout").
ASK_TIMEOUT_SECONDS = int(os.environ.get("GHI_INFO_ASK_TIMEOUT_SECONDS", "300"))
# SSH delegation's own timeout must cover the worst case run box-side: a
# cold start (two claude calls) plus one drift recheck (a third).
SSH_TIMEOUT_SECONDS = ASK_TIMEOUT_SECONDS * 3 + 30

# Recycle-trigger constants (design § Verify at build's Constants list).
CLOSES_SINCE_BIRTH_THRESHOLD = 20
STALE_MATCH_WINDOW = 10
STALE_MATCH_THRESHOLD = 2
# The design points at "NM's working values" for this one; grepped
# nedsmessenger/adapter/adapter.py 2026-08-23 and it carries no
# transcript-size constant to inherit — only timeouts. Starting value only,
# tuned in live use per the design's own Constants clause.
TRANSCRIPT_SIZE_THRESHOLD_BYTES = 5_000_000

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


def default_state() -> dict:
    return {"session_id": None, "closes_since_birth": 0, "recent_matches": []}


def load_state(state_path: Path) -> dict:
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default_state()
    merged = default_state()
    merged.update({key: state[key] for key in merged if key in state})
    return merged


def save_state(state_path: Path, state: dict) -> None:
    temp_path = state_path.with_name(state_path.name + ".tmp")
    temp_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(state_path)


@contextlib.contextmanager
def state_lock(lock_path: Path):
    """Yields True if the exclusive lock was acquired, False if contended.

    A contended lock means another ask is mid-flight (design § The ask
    path, step 2): this ask must not wait and must not touch the shared
    session or state file — it proceeds read-only against a throwaway.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(lock_path, "a+")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield True
        except OSError:
            yield False
    finally:
        handle.close()


def transcript_size_bytes(seat_dir: Path, session_id: str, projects_root: Path):
    if not session_id:
        return None
    project_directory = watcher.project_directory_for_seat(seat_dir, projects_root)
    transcript_path = project_directory / f"{session_id}.jsonl"
    try:
        return transcript_path.stat().st_size
    except OSError:
        return None


def should_recycle(state: dict, seat_dir: Path, projects_root: Path):
    """(bool, reason) — the three numeric recycle triggers. Whether there is
    a session AT ALL is the caller's separate, prior check."""
    closes = state.get("closes_since_birth", 0)
    if closes >= CLOSES_SINCE_BIRTH_THRESHOLD:
        return True, f"{closes} closes since birth (threshold {CLOSES_SINCE_BIRTH_THRESHOLD})"
    recent = state.get("recent_matches", [])[-STALE_MATCH_WINDOW:]
    stale_count = sum(1 for is_stale in recent if is_stale)
    if stale_count >= STALE_MATCH_THRESHOLD:
        return True, (f"{stale_count} stale matches in the last {len(recent)} "
                      f"answers (threshold {STALE_MATCH_THRESHOLD})")
    size = transcript_size_bytes(seat_dir, state.get("session_id"), projects_root)
    if size is not None and size >= TRANSCRIPT_SIZE_THRESHOLD_BYTES:
        return True, f"transcript {size} bytes (threshold {TRANSCRIPT_SIZE_THRESHOLD_BYTES})"
    return False, None


def run_claude(prompt: str, resume_session_id, seat_dir: Path, timeout_seconds: int):
    """One `claude -p` turn. Returns (result_dict, error). No terminal exists
    to approve tool use here (same reasoning as nedsmessenger's adapter,
    the named precedent) — bypassPermissions is the only workable mode for
    an unattended agent."""
    command = ["claude", "-p", prompt, "--output-format", "json",
              "--permission-mode", "bypassPermissions", "--model", GHI_INFO_MODEL]
    if resume_session_id:
        command += ["--resume", resume_session_id]
    try:
        completed = subprocess.run(command, cwd=str(seat_dir), capture_output=True,
                                   text=True, timeout=timeout_seconds, check=False)
    except subprocess.TimeoutExpired:
        return None, f"claude was silent for {timeout_seconds}s and was killed"
    except OSError as error:
        return None, f"could not run claude: {error}"
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "no output").strip()[:500]
        return None, f"claude exited {completed.returncode}: {detail}"
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return None, f"claude produced no parseable result: {completed.stdout[:500]!r}"
    if result.get("is_error"):
        return None, f"claude reported an error: {str(result.get('result'))[:500]}"
    return result, None


def ask(question: str, include_closed: bool, seat_dir: Path, repo: str,
       timeout_seconds: int = ASK_TIMEOUT_SECONDS,
       projects_root: Path = None):
    """The whole ask path (design § The ask path, steps 1-5). Returns
    (answer_text, error) — exactly one is not None."""
    if projects_root is None:
        projects_root = Path.home() / ".claude" / "projects"
    mirror_dir = seat_dir / mirror_refresh.DEFAULT_MIRROR_DIR
    state_path = seat_dir / STATE_FILE_NAME
    lock_path = seat_dir / LOCK_FILE_NAME

    with state_lock(lock_path) as locked:
        state = load_state(state_path) if locked else default_state()

        # Step 1: the routine delta refresh, always.
        delta_result, error = mirror_refresh.refresh(mirror_dir, repo, full=False)
        if delta_result is None:
            return None, f"mirror refresh failed: {error}"
        changed = delta_result["changed"]
        cache = mirror_refresh.read_cache(mirror_dir / mirror_refresh.CACHE_FILE_NAME)
        if locked:
            new_closures = sum(
                1 for number in changed
                if cache.get("issues", {}).get(str(number), {}).get("state") == "CLOSED"
            )
            state["closes_since_birth"] = state.get("closes_since_birth", 0) + new_closures

        # Step 2: resume, or cold-start.
        has_session = locked and state.get("session_id")
        recycle, recycle_reason = (
            should_recycle(state, seat_dir, projects_root) if has_session else (False, None)
        )
        cold_starting = not has_session or recycle

        if cold_starting:
            full_result, error = mirror_refresh.refresh(mirror_dir, repo, full=True)
            if full_result is None:
                return None, f"mirror refresh (full, for cold-start) failed: {error}"
            cache = mirror_refresh.read_cache(mirror_dir / mirror_refresh.CACHE_FILE_NAME)
            cold_start_text = COLD_START_PROMPT_TEMPLATE.format(
                mirror_path=full_result["open_path"])
            cold_reply, error = run_claude(cold_start_text, None, seat_dir, timeout_seconds)
            if cold_reply is None:
                return None, f"ghi-info cold-start failed: {error}"
            session_id = cold_reply["session_id"]
            resume_prompt = compose_resume_ask_prompt(question, include_closed, [], False)
        else:
            session_id = state["session_id"]
            resume_prompt = compose_resume_ask_prompt(question, include_closed, changed, True)

        answer_reply, error = run_claude(resume_prompt, session_id, seat_dir, timeout_seconds)
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
                drift_reply, error = run_claude(compose_drift_notice(unexpected),
                                                session_id, seat_dir, timeout_seconds)
                if drift_reply is not None:
                    session_id = drift_reply.get("session_id", session_id)
                    reply_text = (drift_reply.get("result") or "").strip()
                # A failed recheck falls back to the original reply rather
                # than failing the whole ask — the pointer may simply carry
                # a now-stale tag, which is better than no answer at all.

        if locked:
            if cold_starting:
                state = default_state()
            state["session_id"] = session_id
            recent = state.get("recent_matches", [])
            recent.append(stale)
            state["recent_matches"] = recent[-STALE_MATCH_WINDOW:]
            save_state(state_path, state)

        return reply_text, None


def build_remote_command(seat_dir_remote: str, question: str, include_closed: bool) -> str:
    """One string, sent as ssh's single trailing argument so the box's login
    shell parses it exactly once — no second parse layer here (unlike the
    launchers, which also cross tmux's pane-command parse)."""
    ask_invocation = "python3 scripts/ghi-info-ask.py " + shlex.quote(question)
    if include_closed:
        ask_invocation += " --include-closed"
    return f"cd {shlex.quote(seat_dir_remote)} && {ask_invocation}"


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
            remote_command = build_remote_command(str(seat_dir), arguments.question,
                                                  arguments.include_closed)
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
