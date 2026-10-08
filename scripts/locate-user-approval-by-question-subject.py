#!/usr/bin/env python3
"""Find where the user answered a question about a subject, by the question's words.

An approval has no file name, and the user's answer is usually just "y", so
this program searches for the words of the question the user answered. It
searches, in parallel:

- the walk-minutes in the log-store on ned-box, which record each question's
  subject beside the answer (over ssh when run on the Mac);
- this machine's agent-session transcripts; on ned-box also the copy of the
  Mac's transcripts in the log-store, and on the Mac also ned-box's
  transcripts, over ssh, which has a time limit where a read through the Mac's
  mount of ned-box's home has none;
- commit messages in this checkout, every ref;
- pull requests on GitHub, with their comments.

For a transcript it prints question-and-answer pairs: the agent's message that
holds the words, then the user's next message. Notifications and other injected
records are left out, by the handoff extractor's rules, but no agent message is:
the user's message answers the last agent message before it, so when that is a
different agent message it is shown too, as what the user replied to, and the
reader judges which question was answered. Several matching agent messages before one user
message make one pair, shown with the last of them. Answered pairs come first,
newest first; a matching message the user never answered is left out unless
--include-unanswered is given, and the report says how many were left out. A word matches
case-insensitively anywhere in a message. By default a message matches when it
holds any of the words; --all-words requires every word in the same message or
line. --since leaves out what is older than a date, read in UTC; a
walk-minutes line is dated by the latest date written in it, and a line with no
date is kept.

Exit codes: 0 every place was searched, whatever was found, including when the
only matches were unanswered questions left out of the report; 1 a place could
not be searched, or was searched only in part; 2 bad invocation.
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
import types
from pathlib import Path

PROGRAM = "locate-user-approval-by-question-subject"
EXTRACTOR_RELATIVE_PATH = Path("scripts") / "handoff-extract-conversation.py"
# Run over ssh from stdin, the program has no file of its own, and the sender
# prepends the extractor's source as EMBEDDED_EXTRACTOR_SOURCE.
RUNNING_FROM_EMBEDDED_SOURCE = "EMBEDDED_EXTRACTOR_SOURCE" in globals()
REPOSITORY_ROOT = (Path.cwd() if RUNNING_FROM_EMBEDDED_SOURCE
                   else Path(__file__).resolve().parents[1])


def _load_extractor():
    name = "handoff_extract_conversation"
    if RUNNING_FROM_EMBEDDED_SOURCE:
        module = types.ModuleType(name)
        sys.modules[name] = module
        exec(compile(globals()["EMBEDDED_EXTRACTOR_SOURCE"], str(EXTRACTOR_RELATIVE_PATH), "exec"),
             module.__dict__)
        return module
    spec = importlib.util.spec_from_file_location(name, REPOSITORY_ROOT / EXTRACTOR_RELATIVE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_extractor = _load_extractor()

NED_BOX_HOSTNAME = "ned-box"
NED_BOX_SSH_TARGET = "nedlern@ned-box"
SSH_OPTIONS = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=10"]
SSH_EXIT_CONNECTION_FAILED = 255
WALK_MINUTES_DIRECTORY = "/home/nedlern/nedschorus-logs/walk"
MAC_TRANSCRIPTS_COPY_ON_NED_BOX = "/home/nedlern/nedschorus-logs/transcripts/mac/projects"
NED_BOX_TRANSCRIPTS_DIRECTORY = "/home/nedlern/.claude/projects"
NED_BOX_UNREACHABLE_REMEDY = (f"make sure ned-box is on and on the LAN, then check that "
                              f"`ssh {NED_BOX_SSH_TARGET} true` succeeds")
GITHUB_REPOSITORY = "nedschorus/nedschorus"
PLAN_ENVIRONMENT_VARIABLE = "LOCATE_USER_APPROVAL_PLAN_JSON"
THIS_MACHINE_TRANSCRIPTS_JSON_FLAG = "--this-machine-transcripts-json"

MAXIMUM_WORDS = 3
SHOWN_PER_SECTION = 20
GITHUB_RESULTS_FETCHED = 50
EXCERPT_CHARACTERS = 300
COMMAND_TIMEOUT_SECONDS = 300
DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")


def production_plan() -> dict:
    """Return the places to search on this machine."""
    on_ned_box = socket.gethostname().split(".")[0] == NED_BOX_HOSTNAME
    transcripts = [str(Path.home() / ".claude" / "projects")]
    if on_ned_box:
        transcripts.append(MAC_TRANSCRIPTS_COPY_ON_NED_BOX)
    else:
        transcripts.append({"directory": NED_BOX_TRANSCRIPTS_DIRECTORY,
                            "ssh_target": NED_BOX_SSH_TARGET,
                            "label": f"ned-box's agent-session transcripts in {NED_BOX_TRANSCRIPTS_DIRECTORY}, "
                                     f"over ssh"})
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

    The handoff extractor's rules leave out injected notices, tool results and
    subagent turns. Every agent message is kept, a short acknowledgement of a
    notification included: a reply is attributed to the message it followed,
    and dropping a message by its length could drop the question answered.
    """
    turns, _ = _extractor.read_dialog_turns(transcript_path, drop_acknowledgements=False)
    return turns


def tail_excerpt(text: str) -> str:
    """Return the end of a message, where an agent's question usually sits."""
    flat = " ".join(text.split())
    return flat if len(flat) <= EXCERPT_CHARACTERS else "…" + flat[-EXCERPT_CHARACTERS:]


def question_answer_pairs(turns, words, all_words: bool):
    """Pair matching agent messages with the user's next message.

    Matching agent messages before one user message make one pair, shown with
    the last of them and a count of the others. When the user's message
    directly followed a different agent message, that message is kept as
    replied_to. Matching messages that no user message follows make one pair
    with no answer.
    """
    pairs = []
    pending = []
    for index, turn in enumerate(turns):
        if turn["voice"] == "assistant":
            if text_matches(turn["text"], words, all_words):
                pending.append(index)
            continue
        if not pending:
            continue
        question_index = pending[-1]
        previous = turns[index - 1]
        replied_to = (tail_excerpt(previous["text"])
                      if previous["voice"] == "assistant" and index - 1 != question_index else None)
        pairs.append({"question": excerpt_around_match(turns[question_index]["text"], words),
                      "earlier_matching": len(pending) - 1,
                      "replied_to": replied_to,
                      "answer": shortened(turn["text"]),
                      "timestamp": turn.get("timestamp", "")})
        pending = []
    if pending:
        last = turns[pending[-1]]
        pairs.append({"question": excerpt_around_match(last["text"], words),
                      "earlier_matching": len(pending) - 1, "replied_to": None,
                      "answer": None, "timestamp": last.get("timestamp", "")})
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


def latest_date_in(text: str):
    dates = DATE_PATTERN.findall(text)
    return max(dates) if dates else None


def grep_unreadable_files(stderr: str):
    """Return what grep's error lines name, one entry per line."""
    return [line.removeprefix("grep: ").strip() for line in stderr.splitlines() if line.strip()]


def in_part_failure(stderr: str) -> str:
    unreadable = grep_unreadable_files(stderr)
    if not unreadable:
        return "searched only in part: grep exited 2 without naming what it could not read"
    return (f"searched only in part: grep could not read {len(unreadable)} file(s): "
            + "; ".join(unreadable[:5]) + (" …" if len(unreadable) > 5 else ""))


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
    if result.returncode not in (0, 1, 2):
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
        # A walk can run over several days, so the file name's date does not date its rulings.
        date = latest_date_in(text)
        if since and date and date < since:
            continue
        sort_date = date or latest_date_in(Path(path).name) or ""
        items.append({"sort_key": sort_date,
                      "line": f"{date or '(no date)'}  {path}:{line_number}: {excerpt_around_match(text, words)}"})
    items.sort(key=lambda item: item["sort_key"], reverse=True)
    place = {"place": label, "items": items}
    if result.returncode == 2:
        place["failure"] = in_part_failure(result.stderr)
    return place


def _shell_quote(text: str) -> str:
    return "'" + text.replace("'", "'\\''") + "'"


def search_transcripts(entry, words, all_words, since, include_unanswered=False):
    """Return a place result for one directory of agent-session transcripts.

    entry is a directory, or a dict with the directory, a label, and, for
    another machine's transcripts, the ssh target to search them through.
    """
    if isinstance(entry, dict):
        directory = entry["directory"]
        label = entry.get("label") or f"agent-session transcripts in {directory}"
        if entry.get("ssh_target"):
            return search_transcripts_over_ssh(entry["ssh_target"], directory, label, words,
                                               all_words, since, include_unanswered)
    else:
        directory, label = entry, f"agent-session transcripts in {entry}"
    if not Path(directory).is_dir():
        return {"place": label, "failure": f"{directory}: the directory does not exist", "items": []}
    grep = ["grep", "-rliF", "--include=*.jsonl", *word_arguments_for_grep(words), directory]
    try:
        result = run_command(grep)
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"place": label, "failure": f"could not run grep: {error}", "items": []}
    if result.returncode not in (0, 1, 2):
        return {"place": label, "failure": f"grep exited {result.returncode}: {last_line(result.stderr)}",
                "items": []}
    paths = [path for path in result.stdout.splitlines() if path]
    if since:
        since_start = start_of_day_in_utc(since).timestamp()
        paths = [path for path in paths if _modified_at_or_after(path, since_start)]
    items, errors = [], []
    hidden_unanswered = 0
    # Worker processes cannot import a program that arrived on stdin.
    pool_class = (concurrent.futures.ThreadPoolExecutor if RUNNING_FROM_EMBEDDED_SOURCE
                  else concurrent.futures.ProcessPoolExecutor)
    with pool_class() as pool:
        for path, pairs, error in pool.map(pairs_in_transcript,
                                           [(path, list(words), all_words) for path in paths]):
            if error:
                errors.append(error)
            for pair in pairs:
                if since and pair["timestamp"] and pair["timestamp"][:10] < since:
                    continue
                if pair["answer"] is None and not include_unanswered:
                    hidden_unanswered += 1 + pair["earlier_matching"]
                    continue
                items.append({"sort_key": (pair["answer"] is not None, pair["timestamp"]),
                              "pair": pair, "path": path})
    items.sort(key=lambda item: item["sort_key"], reverse=True)
    for item in items:
        item["sort_key"] = item["pair"]["timestamp"]
    place = {"place": label, "items": items, "hidden_unanswered": hidden_unanswered}
    problems = []
    if result.returncode == 2:
        problems.append(in_part_failure(result.stderr))
    if errors:
        problems.append(f"{len(errors)} transcript(s) grep listed could not be read, first: {errors[0]}")
    if problems:
        place["failure"] = "; ".join(problems)
    return place


def program_text_for_ssh() -> str:
    """Return this program's source with the extractor's source in front, to run from stdin."""
    extractor_source = (REPOSITORY_ROOT / EXTRACTOR_RELATIVE_PATH).read_text()
    program_source = Path(__file__).read_text()
    return f"EMBEDDED_EXTRACTOR_SOURCE = {extractor_source!r}\n" + program_source


def search_transcripts_over_ssh(ssh_target, directory, label, words, all_words, since,
                                include_unanswered):
    """Run this program's transcript search on the other machine, through ssh."""
    request = json.dumps({"directory": directory, "label": label, "words": list(words),
                          "all_words": all_words, "since": since,
                          "include_unanswered": include_unanswered})
    remote_command = f"python3 - {THIS_MACHINE_TRANSCRIPTS_JSON_FLAG} {_shell_quote(request)}"
    try:
        result = subprocess.run(["ssh", *SSH_OPTIONS, ssh_target, remote_command],
                                input=program_text_for_ssh(), capture_output=True, text=True,
                                timeout=COMMAND_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        return {"place": label, "unreachable": True, "items": [],
                "failure": f"ssh {ssh_target} did not finish within {COMMAND_TIMEOUT_SECONDS} s"}
    except OSError as error:
        return {"place": label, "failure": f"could not run ssh: {error}", "items": []}
    if result.returncode == SSH_EXIT_CONNECTION_FAILED:
        return {"place": label, "unreachable": True, "items": [],
                "failure": f"ssh {ssh_target} failed: {last_line(result.stderr)}"}
    try:
        place = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"place": label, "items": [],
                "failure": f"the search on {ssh_target} exited {result.returncode} without a result: "
                           f"{last_line(result.stderr)}"}
    place["place"] = label
    return place


def start_of_day_in_utc(date_text: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(date_text).replace(tzinfo=datetime.timezone.utc)


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
        command.append(f"--since={since} 00:00:00 +0000")
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
    # One argument per word: gh quotes an argument holding a space, which would make
    # GitHub search for the exact phrase. Words next to each other must all match; OR between them lets any match.
    query_arguments = []
    for index, word in enumerate(words):
        if index and not all_words:
            query_arguments.append("OR")
        query_arguments.append(word)
    command = ["gh", "search", "prs", "--repo", repository, "--limit", str(GITHUB_RESULTS_FETCHED),
               "--json", "title,url,updatedAt"]
    if since:
        command += ["--updated", f">={since}"]
    command += ["--", *query_arguments]
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


def run_searches(plan, words, all_words, since, include_unanswered=False):
    """Run every place's search at once; return the place results in a fixed order."""
    searches = [lambda: search_walk_minutes(plan, words, all_words, since)]
    searches += [(lambda entry=entry: search_transcripts(entry, words, all_words, since,
                                                         include_unanswered))
                 for entry in plan["transcript_directories"]]
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
        lines = [f"  {when}  {item['path']}",
                 f"    Agent: {pair['question']}"]
        if pair.get("earlier_matching"):
            lines.append(f"    ({pair['earlier_matching']} earlier matching agent message(s) "
                         f"before the same user message not shown)")
        if pair.get("replied_to"):
            lines.append(f"    User replied to: {pair['replied_to']}")
        lines.append(f"    User:  {answer}")
        return lines
    return [f"  {item['line']}"]


def render_report(places, words, all_words, since):
    """Return (report text, exit code)."""
    mode = "every word in one message or line" if all_words else "any of the words"
    lines = [f"Searched for {', '.join(repr(word) for word in words)} ({mode})"
             + (f", since {since}" if since else "") + "."]
    total = sum(len(place["items"]) for place in places)
    hidden = sum(place.get("hidden_unanswered", 0) for place in places)
    too_wide = any(len(place["items"]) > SHOWN_PER_SECTION for place in places)
    for place in places:
        if place.get("hidden_unanswered"):
            hidden_line = (f"  {place['hidden_unanswered']} matching agent message(s) that no user message "
                           f"followed are not shown; run again with --include-unanswered to see them.")
        else:
            hidden_line = None
        if not place["items"]:
            if hidden_line:
                lines += ["", f"{place['place']}: no answered question found:", hidden_line]
            continue
        shown = place["items"][:SHOWN_PER_SECTION]
        lines += ["", f"{place['place']}: {len(place['items'])} found, "
                  + ("answered first, newest first" if any("pair" in item for item in place["items"])
                     else "newest first")
                  + (f", showing {SHOWN_PER_SECTION}" if len(place["items"]) > SHOWN_PER_SECTION else "")
                  + ":"]
        for item in shown:
            lines += render_item(item)
        rest = len(place["items"]) - len(shown)
        if rest:
            lines.append(f"  … and {rest} more not shown.")
        if hidden_line:
            lines.append(hidden_line)
    failed = [place for place in places if place.get("failure")]
    searched = [place for place in places if not place.get("failure") or place["items"]]
    lines += ["", "Places searched:"]
    lines += [f"  {place['place']}" + (" (in part)" if place.get("failure") else "") for place in searched]
    if failed:
        lines += ["", "NOT searched, or searched only in part:"]
        lines += [f"  {place['place']}: {place['failure']}" for place in failed]
    if total == 0 and not hidden:
        lines += ["", "Not found in these places."]

    instructions = []
    if total == 0 and hidden:
        instructions += [
            f"No answered question matched, but {hidden} matching agent message(s) that no user "
            "message followed were left out. Run again with --include-unanswered to read them before "
            "you report.",
        ]
    elif total == 0:
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
            "Read each pair: the User line answers the \"User replied to\" line when there is one, "
            "and otherwise the Agent line. Judge from the Agent line whether that was the question "
            "about this subject. Report the answer with its date and transcript, walk-minutes, "
            "commit or pull request.",
        ]
    for place in failed:
        if place.get("unreachable"):
            instructions += [
                f"Tell the user this place on ned-box was not searched: {place['place']}: {place['failure']}.",
                f"Give the user this remedy: {NED_BOX_UNREACHABLE_REMEDY}.",
            ]
        else:
            instructions.append(f"Tell the user this place was not fully searched, and why: "
                                f"{place['place']}: {place['failure']}.")
            if place.get("remedy"):
                instructions.append(f"Give the user this remedy: {place['remedy']}.")
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
    parser.add_argument("words", nargs="*",
                        help=f"one to {MAXIMUM_WORDS} words for the subject of the question, "
                             "such as a program's or file's name")
    parser.add_argument("--all-words", action="store_true",
                        help="require every word in the same message or line")
    parser.add_argument("--since", type=valid_date, metavar="YYYY-MM-DD",
                        help="leave out what is older than this date")
    parser.add_argument("--include-unanswered", action="store_true",
                        help="also list matching agent messages that no user message followed")
    parser.add_argument(THIS_MACHINE_TRANSCRIPTS_JSON_FLAG, metavar="REQUEST_JSON",
                        help="search this machine's transcripts and print the result as JSON: "
                             "what the program runs on the other machine over ssh")
    arguments = parser.parse_args(argv)
    if arguments.this_machine_transcripts_json:
        request = json.loads(arguments.this_machine_transcripts_json)
        place = search_transcripts({"directory": request["directory"], "label": request["label"]},
                                   request["words"], request["all_words"], request["since"],
                                   request["include_unanswered"])
        sys.stdout.write(json.dumps(place))
        return 0
    if not arguments.words:
        parser.error("give one to three words for the subject of the question")
    if len(arguments.words) > MAXIMUM_WORDS:
        parser.error(f"give at most {MAXIMUM_WORDS} words; more words widen the search "
                     "unless --all-words is given")
    words = [word for word in arguments.words if word.strip()]
    if not words:
        parser.error("give at least one word that is not blank")
    places = run_searches(plan_for_this_run(), words, arguments.all_words, arguments.since,
                          arguments.include_unanswered)
    report, exit_code = render_report(places, words, arguments.all_words, arguments.since)
    sys.stdout.write(report)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
