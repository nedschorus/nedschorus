#!/usr/bin/env python3
"""Find where the user answered a question about a subject, by the question's words.

An approval has no file name, and the user's answer is usually just "y", so
this program searches for the words of the question the user answered. It
searches, in parallel:

- the walk-minutes in the log-store on ned-box, which record each question's
  subject beside the answer (over ssh when run on the Mac);
- this machine's agent-session transcripts, and on ned-box also the copy of
  the Mac's transcripts in the log-store;
- commit messages in this checkout, every ref;
- pull requests on GitHub, with their comments.

For a transcript it prints question-and-answer pairs: the agent's message that
holds the words, then the user's next message, newest first. A word matches
case-insensitively anywhere in a message. By default a message matches when it
holds any of the words; --all-words requires every word in the same message or
line. --since leaves out what is older than a date.

Exit codes: 0 every place was searched, whatever was found; 1 a place could
not be searched; 2 bad invocation.
"""

import argparse
import concurrent.futures
import datetime
import importlib.util
import json
import os
import re
import socket
import subprocess
import sys
from pathlib import Path

PROGRAM = "locate-user-approval-by-question-subject"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

_extractor_spec = importlib.util.spec_from_file_location(
    "handoff_extract_conversation",
    REPOSITORY_ROOT / "scripts" / "handoff-extract-conversation.py")
_extractor = importlib.util.module_from_spec(_extractor_spec)
_extractor_spec.loader.exec_module(_extractor)

NED_BOX_HOSTNAME = "ned-box"
NED_BOX_SSH_TARGET = "nedlern@ned-box"
SSH_OPTIONS = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=5"]
SSH_EXIT_CONNECTION_FAILED = 255
WALK_MINUTES_DIRECTORY = "/home/nedlern/nedschorus-logs/walk"
MAC_TRANSCRIPTS_COPY_ON_NED_BOX = "/home/nedlern/nedschorus-logs/transcripts/mac/projects"
GITHUB_REPOSITORY = "nedschorus/nedschorus"
PLAN_ENVIRONMENT_VARIABLE = "LOCATE_USER_APPROVAL_PLAN_JSON"

MAXIMUM_WORDS = 3
SHOWN_PER_SECTION = 20
GITHUB_RESULTS_FETCHED = 50
EXCERPT_CHARACTERS = 300
COMMAND_TIMEOUT_SECONDS = 300
DATE_IN_NAME = re.compile(r"(\d{4}-\d{2}-\d{2})")


def production_plan() -> dict:
    """Return the places to search on this machine."""
    on_ned_box = socket.gethostname().split(".")[0] == NED_BOX_HOSTNAME
    transcripts = [str(Path.home() / ".claude" / "projects")]
    if on_ned_box:
        transcripts.append(MAC_TRANSCRIPTS_COPY_ON_NED_BOX)
    return {
        "walk_minutes": {"directory": WALK_MINUTES_DIRECTORY,
                         "ssh_target": None if on_ned_box else NED_BOX_SSH_TARGET},
        "transcript_directories": transcripts,
        "repository": str(REPOSITORY_ROOT),
        "github_repository": GITHUB_REPOSITORY,
    }


def plan_for_this_run() -> dict:
    override = os.environ.get(PLAN_ENVIRONMENT_VARIABLE)
    return json.loads(override) if override else production_plan()


def text_matches(text: str, words, all_words: bool) -> bool:
    lowered = text.lower()
    hits = [word.lower() in lowered for word in words]
    return all(hits) if all_words else any(hits)


def excerpt_around_match(text: str, words) -> str:
    """Return about EXCERPT_CHARACTERS of text around the first matching word."""
    flat = " ".join(text.split())
    lowered = flat.lower()
    positions = [lowered.find(word.lower()) for word in words]
    positions = [position for position in positions if position >= 0]
    start = max(0, min(positions) - EXCERPT_CHARACTERS // 3) if positions else 0
    piece = flat[start:start + EXCERPT_CHARACTERS]
    prefix = "…" if start > 0 else ""
    suffix = "…" if start + EXCERPT_CHARACTERS < len(flat) else ""
    return prefix + piece + suffix


def shortened(text: str) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= EXCERPT_CHARACTERS else flat[:EXCERPT_CHARACTERS] + "…"


def dialog_with_timestamps(transcript_path: Path):
    """Return the transcript's dialog turns, each with voice, text and timestamp.

    Turns are classified by the handoff extractor's rules, so injected
    notices, tool results and subagent turns are not taken for the user.
    """
    turns = []
    with transcript_path.open("rb") as handle:
        for raw_line in handle:
            if len(raw_line) > _extractor.MAXIMUM_RECORD_BYTES:
                continue
            stripped = raw_line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            turn = _extractor.dialog_turn_from_record(record)
            if turn is None:
                continue
            if turn["voice"] == "user" and turn["text"].startswith(
                    _extractor.INJECTED_TEXT_PREFIXES):
                continue
            turn["timestamp"] = record.get("timestamp") or ""
            turns.append(turn)
    return turns


def question_answer_pairs(turns, words, all_words: bool):
    """Pair each matching agent message with the user's next message.

    When several agent messages before one user message match, the last one is
    kept: it is the one the user answered.
    """
    pairs = []
    pending_question = None
    for turn in turns:
        if turn["voice"] == "assistant":
            if text_matches(turn["text"], words, all_words):
                pending_question = turn
        elif pending_question is not None:
            pairs.append({"question": excerpt_around_match(pending_question["text"], words),
                          "answer": shortened(turn["text"]),
                          "timestamp": turn["timestamp"]})
            pending_question = None
    if pending_question is not None:
        pairs.append({"question": excerpt_around_match(pending_question["text"], words),
                      "answer": None, "timestamp": pending_question["timestamp"]})
    return pairs


def pairs_in_transcript(arguments):
    """Worker: return (path, pairs, error) for one transcript."""
    path, words, all_words = arguments
    try:
        turns = dialog_with_timestamps(Path(path))
    except OSError as error:
        return path, [], f"{path}: {error.strerror or error}"
    return path, question_answer_pairs(turns, words, all_words), None


def run_command(command, timeout=COMMAND_TIMEOUT_SECONDS):
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout)


def last_line(text: str) -> str:
    lines = [line for line in text.strip().splitlines() if line.strip()]
    return lines[-1] if lines else "(no output)"


def word_arguments_for_grep(words):
    arguments = []
    for word in words:
        arguments += ["-e", word]
    return arguments


def date_in_name_or_none(path: str):
    match = DATE_IN_NAME.search(Path(path).name)
    return match.group(1) if match else None


def search_walk_minutes(plan, words, all_words, since):
    """Return a place result for the walk-minutes."""
    place = plan["walk_minutes"]
    directory = place["directory"]
    ssh_target = place.get("ssh_target")
    label = f"walk-minutes in {directory}" + (f" on {ssh_target}" if ssh_target else "")
    grep = ["grep", "-rniF", "--include=*-minutes.md", *word_arguments_for_grep(words), directory]
    if ssh_target:
        command = ["ssh", *SSH_OPTIONS, ssh_target, " ".join(_shell_quote(part) for part in grep)]
    else:
        command = grep
    try:
        result = run_command(command)
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"place": label, "failure": f"could not run grep: {error}", "items": []}
    if ssh_target and result.returncode == SSH_EXIT_CONNECTION_FAILED:
        return {"place": label, "unreachable": True,
                "failure": f"ssh {ssh_target} failed: {last_line(result.stderr)}", "items": []}
    if result.returncode not in (0, 1):
        return {"place": label, "failure": f"grep exited {result.returncode}: {last_line(result.stderr)}",
                "items": []}
    items = []
    for line in result.stdout.splitlines():
        parts = line.split(":", 2)
        if len(parts) < 3:
            continue
        path, line_number, text = parts
        if not text_matches(text, words, all_words):
            continue
        date = date_in_name_or_none(path)
        if since and date and date < since:
            continue
        items.append({"sort_key": date or "", "line": f"{date or '(no date)'}  {path}:{line_number}: {excerpt_around_match(text, words)}"})
    items.sort(key=lambda item: item["sort_key"], reverse=True)
    return {"place": label, "items": items}


def _shell_quote(text: str) -> str:
    return "'" + text.replace("'", "'\\''") + "'"


def search_transcripts(directory, words, all_words, since):
    """Return a place result for one directory of agent-session transcripts."""
    label = f"agent-session transcripts in {directory}"
    if not Path(directory).is_dir():
        return {"place": label, "failure": "the directory does not exist", "items": []}
    grep = ["grep", "-rliF", "--include=*.jsonl", *word_arguments_for_grep(words), directory]
    try:
        result = run_command(grep)
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"place": label, "failure": f"could not run grep: {error}", "items": []}
    # grep exits 2 for an unreadable file even when others matched.
    if result.returncode not in (0, 1, 2) or (result.returncode == 2 and not result.stdout):
        return {"place": label, "failure": f"grep exited {result.returncode}: {last_line(result.stderr)}",
                "items": []}
    paths = [path for path in result.stdout.splitlines() if path]
    if since:
        since_start = datetime.datetime.fromisoformat(since).timestamp()
        paths = [path for path in paths if _modified_at_or_after(path, since_start)]
    items, errors = [], []
    with concurrent.futures.ProcessPoolExecutor() as pool:
        for path, pairs, error in pool.map(pairs_in_transcript,
                                           [(path, list(words), all_words) for path in paths]):
            if error:
                errors.append(error)
            for pair in pairs:
                if since and pair["timestamp"] and pair["timestamp"][:10] < since:
                    continue
                items.append({"sort_key": pair["timestamp"], "pair": pair, "path": path})
    items.sort(key=lambda item: item["sort_key"], reverse=True)
    place = {"place": label, "items": items}
    if errors:
        place["failure"] = f"{len(errors)} transcript(s) could not be read, first: {errors[0]}"
    return place


def _modified_at_or_after(path: str, start: float) -> bool:
    try:
        return os.stat(path).st_mtime >= start
    except OSError:
        return True


def search_commit_messages(plan, words, all_words, since):
    repository = plan["repository"]
    label = f"commit messages in {repository}, every ref"
    command = ["git", "-C", repository, "log", "--all", "-i", "--fixed-strings",
               "--format=%h%x09%cs%x09%s"]
    for word in words:
        command.append(f"--grep={word}")
    if all_words:
        command.append("--all-match")
    if since:
        command.append(f"--since={since}")
    try:
        result = run_command(command)
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"place": label, "failure": f"could not run git log: {error}", "items": []}
    if result.returncode != 0:
        return {"place": label, "failure": f"git log exited {result.returncode}: {last_line(result.stderr)}",
                "items": []}
    items = []
    for line in result.stdout.splitlines():
        parts = line.split("\t", 2)
        if len(parts) == 3:
            items.append({"sort_key": parts[1], "line": f"{parts[1]}  commit {parts[0]}: {parts[2]}"})
    return {"place": label, "items": items}


def search_pull_requests(plan, words, all_words, since):
    repository = plan["github_repository"]
    label = f"pull requests and their comments in {repository} on GitHub"
    query = " ".join(words) if all_words else " OR ".join(words)
    command = ["gh", "search", "prs", "--repo", repository, "--limit", str(GITHUB_RESULTS_FETCHED),
               "--json", "title,url,updatedAt"]
    if since:
        command += ["--updated", f">={since}"]
    command += ["--", query]
    try:
        result = run_command(command)
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"place": label, "failure": f"could not run gh: {error}", "items": []}
    if result.returncode != 0:
        return {"place": label, "failure": f"gh search prs exited {result.returncode}: {last_line(result.stderr)}",
                "items": []}
    try:
        found = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return {"place": label, "failure": "gh search prs printed output that is not JSON", "items": []}
    items = [{"sort_key": entry.get("updatedAt", ""),
              "line": f"{entry.get('updatedAt', '')[:10]}  PR \"{entry.get('title', '')}\" {entry.get('url', '')}"}
             for entry in found]
    items.sort(key=lambda item: item["sort_key"], reverse=True)
    return {"place": label, "items": items}


def run_searches(plan, words, all_words, since):
    """Run every place's search at once; return the place results in a fixed order."""
    searches = [lambda: search_walk_minutes(plan, words, all_words, since)]
    searches += [(lambda directory=directory: search_transcripts(directory, words, all_words, since))
                 for directory in plan["transcript_directories"]]
    searches += [lambda: search_commit_messages(plan, words, all_words, since),
                 lambda: search_pull_requests(plan, words, all_words, since)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(searches)) as pool:
        futures = [pool.submit(search) for search in searches]
        return [future.result() for future in futures]


def render_item(item):
    if "pair" in item:
        pair = item["pair"]
        answer = pair["answer"] if pair["answer"] is not None else "(no user message followed)"
        when = pair["timestamp"][:16].replace("T", " ") + " UTC" if pair["timestamp"] else "(no time)"
        return [f"  {when}  {item['path']}",
                f"    Agent: {pair['question']}",
                f"    User:  {answer}"]
    return [f"  {item['line']}"]


def render_report(places, words, all_words, since):
    """Return (report text, exit code)."""
    mode = "every word in one message or line" if all_words else "any of the words"
    lines = [f"Searched for {', '.join(repr(word) for word in words)} ({mode})"
             + (f", since {since}" if since else "") + "."]
    total = sum(len(place["items"]) for place in places)
    too_wide = any(len(place["items"]) > SHOWN_PER_SECTION for place in places)
    for place in places:
        if not place["items"]:
            continue
        shown = place["items"][:SHOWN_PER_SECTION]
        lines += ["", f"{place['place']}: {len(place['items'])} found, newest first"
                  + (f", showing {SHOWN_PER_SECTION}" if len(place["items"]) > SHOWN_PER_SECTION else "")
                  + ":"]
        for item in shown:
            lines += render_item(item)
        rest = len(place["items"]) - len(shown)
        if rest:
            lines.append(f"  … and {rest} more not shown.")
    failed = [place for place in places if place.get("failure")]
    searched = [place for place in places if not place.get("failure") or place["items"]]
    lines += ["", "Places searched:"]
    lines += [f"  {place['place']}" + (" (in part)" if place.get("failure") else "") for place in searched]
    if failed:
        lines += ["", "NOT searched, or searched only in part:"]
        lines += [f"  {place['place']}: {place['failure']}" for place in failed]
    if total == 0:
        lines += ["", "Not found in these places."]

    instructions = []
    if total == 0:
        instructions += [
            "Nothing matched. Before you report, run this program again with another name for "
            "the subject, or with the name of the program or file the change touched.",
            "If nothing matches then either, report \"not found in\" the places listed above, "
            "never \"no approval\": the question may have used other words.",
        ]
    if too_wide:
        instructions += [
            "Too wide: some places matched more than are shown. Narrow the search with "
            "--all-words, with --since YYYY-MM-DD, or with a more specific word, such as the "
            "name of the program or file the change touched.",
        ]
    if total:
        instructions += [
            "Read each pair: the User line is the answer to the Agent line above it. "
            "Report the answer with its date and transcript, walk-minutes, commit or pull request.",
        ]
    for place in failed:
        if place.get("unreachable"):
            instructions += [
                f"Tell the user the walk-minutes on ned-box were not searched: {place['failure']}.",
                f"Give the user this remedy: make sure ned-box is on and on the LAN, then check "
                f"that `ssh {NED_BOX_SSH_TARGET} true` succeeds.",
            ]
        else:
            instructions.append(f"Tell the user this place was not fully searched, and why: "
                                f"{place['place']}: {place['failure']}.")
    lines += ["", "What to do next:"] + [f"- {instruction}" for instruction in instructions]
    return "\n".join(lines) + "\n", (1 if failed else 0)


def valid_date(text: str) -> str:
    try:
        datetime.date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a date in the form YYYY-MM-DD: {text!r}")
    return text


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog=PROGRAM,
        description="Find where the user answered a question about a subject: walk-minutes, "
                    "agent-session transcripts, commit messages and pull requests, searched in parallel.")
    parser.add_argument("words", nargs="+",
                        help=f"one to {MAXIMUM_WORDS} words for the subject of the question, "
                             "such as a program's or file's name")
    parser.add_argument("--all-words", action="store_true",
                        help="require every word in the same message or line")
    parser.add_argument("--since", type=valid_date, metavar="YYYY-MM-DD",
                        help="leave out what is older than this date")
    arguments = parser.parse_args(argv)
    if len(arguments.words) > MAXIMUM_WORDS:
        parser.error(f"give at most {MAXIMUM_WORDS} words; more words widen the search "
                     "unless --all-words is given")
    words = [word for word in arguments.words if word.strip()]
    if not words:
        parser.error("give at least one word that is not blank")
    places = run_searches(plan_for_this_run(), words, arguments.all_words, arguments.since)
    report, exit_code = render_report(places, words, arguments.all_words, arguments.since)
    sys.stdout.write(report)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
