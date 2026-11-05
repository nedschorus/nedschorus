#!/usr/bin/env python3
"""Check three candidate lengths of a new name with six fresh readers each, and keep each reader's result.

Usage:
  scripts/new-name-three-lengths-fresh-readers-check.py read --describe SENTENCE
      --full NAME --medium NAME --short NAME [--sent-name NAME]
      [--retry-of RUN_FILE] [--run-file PATH]
  scripts/new-name-three-lengths-fresh-readers-check.py verdicts RUN_FILE
      --verdicts JSON [--choose NAME --reason TEXT]
  scripts/new-name-three-lengths-fresh-readers-check.py per-model-summary

`read` checks that the three candidates differ and get shorter, full to
short, counting words in the last path part without its extension, split at
hyphens, underscores, dots and lower-to-upper case changes, and, given
--sent-name, that the name sent to be checked is one of the three. It then gives each
candidate to six readers at once, eighteen calls in all, each a new process
in its own empty temporary folder, given the name alone: Claude Sonnet 5.5 and
Opus 5.5 (`claude -p`, no tools, no settings, so no CLAUDE.md), Gemini
gemini-3.8-flash-low and gemini-4-argon-medium (through
nc-systems/general-tools/agy-print-prompt-run-in-empty-home-sandbox.py), and
gpt-6.1-terra and gpt-6.1-sol (`codex exec`, read-only, ephemeral). Each
reader answers what the thing does, what else the name could mean, and which
word it was least sure of. A reader that exits nonzero, prints nothing, or
runs past READER_TIMEOUT_SECONDS is recorded as failed; nothing is retried.
`read` writes the run file (default: $TMPDIR/new-name-checks/<run id>.json),
appends one line per reader to the log-store file READER_RESULTS_LOG, prints
each account with its reader id, and prints the `verdicts` command to run.

Judging whether an account matches the sentence is the asking agent's work;
`verdicts` takes the agent's judgement as a JSON object of reader id to
"match" or "miss", one for every reader that answered. A candidate passes when
every reader that answered matched and at most one reader failed. Of the
passing candidates, the shortest wins, unless --choose names another passing
one with --reason. The judgements and the outcome are appended to
READER_RESULTS_LOG. When none passes, a first run says to build three new
candidates once and run `read --retry-of` this run file; a retry that passes
none prints each candidate of both runs with its number of matches, most
first, and says to bring the user the readers' accounts; a retry of a retry
is refused.

`per-model-summary` reads READER_RESULTS_LOG and prints, per model, how often
it answered, matched, was the only miss among a candidate's answering
readers, failed, and its mean seconds, so the readers can be cut back to the
best ones.

The log-store file is appended on ned-box directly, and from any other
machine over `ssh nedlern@ned-box` in batch mode. When the append fails,
`read` and `verdicts` still print their results and write the run file, then
print a line opening FAILED with the error and exit 1, so the gap is seen. The
run file records whether the readers' lines reached the log-store; `verdicts`
appends them with the judgements when they did not, and rerunning `verdicts`
appends the judgements again, so a later summary counts the newest ones.

Exit codes: 0 done; 1 a reader failed so badly that no candidate can pass, or
the log-store append failed, or `verdicts` found no passing candidate; 2 bad
input (candidates not shorter, a missing or extra verdict, --choose not a
passing candidate, a retry of a retry). Model calls cost quota: eighteen per
`read`.
"""

import argparse
import concurrent.futures
import json
import os
import pathlib
import re
import secrets
import shlex
import socket
import subprocess
import sys
import tempfile
import time

PROGRAM = "new-name-three-lengths-fresh-readers-check"
REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
AGY_RUNNER = REPO_ROOT / "nc-systems" / "general-tools" / "agy-print-prompt-run-in-empty-home-sandbox.py"
LOG_STORE_HOSTNAME = "ned-box"
LOG_STORE_SSH_HOST = "nedlern@ned-box"
READER_RESULTS_LOG = "/home/nedlern/nedschorus-logs/name-checks/new-name-fresh-reader-results.jsonl"
READER_TIMEOUT_SECONDS = 300
CANDIDATE_LENGTHS = ("full", "medium", "short")
MAX_FAILED_READERS_FOR_A_PASS = 1
SSH_TIMEOUT_SECONDS = 60
ERROR_LINE_CHARACTERS = 300

# Each reader: (runtime, model, effort).
READERS = (
    ("claude", "claude-sonnet-5-5", "medium"),
    ("claude", "claude-opus-5-5", "medium"),
    ("agy", "gemini-3.8-flash-low", None),
    ("agy", "gemini-4-argon-medium", None),
    ("codex", "gpt-6.1-terra", "medium"),
    ("codex", "gpt-6.1-sol", "medium"),
)

READER_PROMPT = (
    "This name comes from a software project you cannot see. Guess from the name alone: "
    "do not look for files, do not run anything and do not ask a question. "
    "Answer in exactly three lines:\n"
    "DOES: <one sentence: what kind of thing it names, and what it does or holds>\n"
    "COULD ALSO MEAN: <one sentence: another thing the name could reasonably name, or none>\n"
    "LEAST SURE OF: <the one word of the name you were least sure of>\n"
    "Name: {name}"
)


def name_words(name: str) -> list:
    """The words of a name's last path part, without its extension."""
    last = name.rstrip("/").split("/")[-1]
    if "." in last[1:]:
        last = last[:last.rindex(".")] if not last.startswith(".") else last
    last = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", last)
    return [word for word in re.split(r"[-_.\s]+", last) if word]


def candidate_length_problem(candidates: dict):
    """Why the three candidates are not distinct and shorter from full to short, or None."""
    names = [candidates[length] for length in CANDIDATE_LENGTHS]
    if len(set(names)) != 3:
        return "the three candidates must differ"
    counts = [len(name_words(name)) for name in names]
    if not (counts[0] > counts[1] > counts[2] >= 1):
        return ("the candidates must have fewer words from full to short; "
                + ", ".join(f"{length} has {count}" for length, count in zip(CANDIDATE_LENGTHS, counts)))
    return None


def reader_command(runtime: str, model: str, effort, prompt: str, folder: pathlib.Path):
    """(argv, stdin text or None, file the answer is written to or None) for one reader."""
    if runtime == "claude":
        return (["claude", "-p", "--model", model, "--effort", effort, "--tools", "",
                 "--setting-sources", "", "--no-session-persistence", "--output-format", "text"],
                prompt, None)
    if runtime == "agy":
        return [sys.executable, str(AGY_RUNNER), "--model", model, prompt], None, None
    answer_file = folder / "answer.txt"
    return (["codex", "exec", "--ephemeral", "--skip-git-repo-check", "-s", "read-only",
             "-C", str(folder), "-m", model, "-c", f"model_reasoning_effort={effort}",
             "--disable", "memories", "-o", str(answer_file), prompt],
            None, answer_file)


def last_line(text: str) -> str:
    """The last line of a program's output that has text, cut to ERROR_LINE_CHARACTERS."""
    lines = [line for line in text.strip().splitlines() if line.strip()]
    return lines[-1][:ERROR_LINE_CHARACTERS] if lines else ""


def run_ssh(ssh_host: str, remote_command: str, input_text: str = None):
    """(stdout, error text or None) of one batch-mode ssh call; never raises."""
    try:
        completed = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", ssh_host, remote_command],
                                   input=input_text, capture_output=True, text=True, timeout=SSH_TIMEOUT_SECONDS)
    except (OSError, subprocess.TimeoutExpired) as error:
        return None, f"ssh did not run: {error}"
    if completed.returncode:
        return None, f"ssh exit {completed.returncode}: {last_line(completed.stderr)}"
    return completed.stdout, None


def run_reader(runtime: str, model: str, effort, name: str) -> dict:
    """Run one fresh reader on one name; never raises."""
    prompt = READER_PROMPT.format(name=name)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="new-name-reader-") as folder_text:
        folder = pathlib.Path(folder_text)
        argv, stdin_text, answer_file = reader_command(runtime, model, effort, prompt, folder)
        try:
            completed = subprocess.run(
                argv, cwd=folder, input=stdin_text,
                stdin=None if stdin_text is not None else subprocess.DEVNULL,
                capture_output=True, text=True, timeout=READER_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            return {"account": None, "error": f"timed out after {READER_TIMEOUT_SECONDS} s", "seconds": None}
        except OSError as error:
            return {"account": None, "error": f"could not start {argv[0]}: {error}", "seconds": None}
        account = completed.stdout
        if answer_file is not None and answer_file.exists():
            account = answer_file.read_text()
    if completed.returncode:
        return {"account": None, "error": f"exit {completed.returncode}: {last_line(completed.stderr or completed.stdout)}",
                "seconds": None}
    if not account.strip():
        return {"account": None, "error": "printed nothing", "seconds": None}
    return {"account": account.strip(), "error": None, "seconds": round(time.monotonic() - started, 1)}


def run_all_readers(candidates: dict, reader=run_reader) -> list:
    """Every reader on every candidate, at once; reader ids run c1r1 to c3r6."""
    jobs = []
    for candidate_index, length in enumerate(CANDIDATE_LENGTHS, 1):
        for reader_index, (runtime, model, effort) in enumerate(READERS, 1):
            jobs.append((f"c{candidate_index}r{reader_index}", length, candidates[length], runtime, model, effort))
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        futures = [pool.submit(reader, runtime, model, effort, name) for _, _, name, runtime, model, effort in jobs]
        results = [future.result() for future in futures]
    return [{"reader_id": reader_id, "length": length, "name": name, "runtime": runtime, "model": model, **result}
            for (reader_id, length, name, runtime, model, _), result in zip(jobs, results)]


def append_to_log_store(lines: list, log_path: str = None, ssh_host: str = None) -> str:
    """Append JSON lines to the log-store file; return the error text, or None when appended."""
    if log_path is None and ssh_host is None and socket.gethostname().split(".")[0] != LOG_STORE_HOSTNAME:
        ssh_host = LOG_STORE_SSH_HOST
    log_path = log_path or READER_RESULTS_LOG
    text = "".join(json.dumps(line, sort_keys=True) + "\n" for line in lines)
    if ssh_host is None:
        try:
            pathlib.Path(log_path).parent.mkdir(parents=True, exist_ok=True)
            with open(log_path, "a") as log:
                log.write(text)
        except OSError as error:
            return f"could not append to {log_path}: {error}"
        return None
    remote = f"mkdir -p {shlex.quote(str(pathlib.PurePosixPath(log_path).parent))} && cat >> {shlex.quote(log_path)}"
    _, error = run_ssh(ssh_host, remote, text)
    return f"could not append to {ssh_host}:{log_path}: {error}" if error else None


def default_run_file(run_id: str) -> pathlib.Path:
    return pathlib.Path(os.environ.get("TMPDIR", tempfile.gettempdir())) / "new-name-checks" / f"{run_id}.json"


def command_read(arguments, reader=run_reader, log_path=None, ssh_host=None) -> int:
    candidates = {"full": arguments.full, "medium": arguments.medium, "short": arguments.short}
    problem = candidate_length_problem(candidates)
    if not problem and arguments.sent_name and arguments.sent_name not in candidates.values():
        problem = (f"the sent name {arguments.sent_name} is not one of the three candidates; it has "
                   f"{len(name_words(arguments.sent_name))} words, so put it at the length that count fits")
    if problem:
        print(f"{PROGRAM}: REFUSED: {problem}. Nothing was run, so no model call was spent.\n"
              "Build three candidates that differ, each with fewer words than the one before, "
              "and run `read` again with them.", file=sys.stderr)
        return 2
    retry_number = 0
    if arguments.retry_of:
        earlier = json.loads(pathlib.Path(arguments.retry_of).read_text())
        if earlier.get("retry_number", 0) >= 1:
            print(f"{PROGRAM}: REFUSED: {arguments.retry_of} is already a retry; the check builds new "
                  "candidates once. Bring the user the readers' accounts of both runs.", file=sys.stderr)
            return 2
        retry_number = 1
    run_id = time.strftime("%Y-%m-%dT%H%M%SZ", time.gmtime()) + "-" + secrets.token_hex(3)
    results = run_all_readers(candidates, reader)
    run = {"run_id": run_id, "describe": arguments.describe, "candidates": candidates,
           "retry_of": arguments.retry_of, "retry_number": retry_number, "readers": results}
    run_file = pathlib.Path(arguments.run_file) if arguments.run_file else default_run_file(run_id)
    run_file.parent.mkdir(parents=True, exist_ok=True)
    for length in CANDIDATE_LENGTHS:
        print(f"== {length}: {candidates[length]}")
        for result in (r for r in results if r["length"] == length):
            if result["error"]:
                print(f"[{result['reader_id']}] {result['model']}: FAILED: {result['error']}")
            else:
                print(f"[{result['reader_id']}] {result['model']} ({result['seconds']} s):\n{result['account']}")
    error = append_to_log_store(reader_log_lines(run), log_path, ssh_host)
    run["readers_logged"] = error is None
    run_file.write_text(json.dumps(run, indent=2))
    answered = [r["reader_id"] for r in results if not r["error"]]
    print(f"\nRun file: {run_file}")
    print("Judge each account against the sentence: it matches when it names the same kind of thing "
          "and the same job; vague where the sentence is specific is a miss. Then run:")
    print(f"python3 {pathlib.Path(__file__).relative_to(REPO_ROOT)} verdicts {run_file} --verdicts '"
          + json.dumps({reader_id: "match|miss" for reader_id in answered}) + "'")
    if error:
        print(f"FAILED: the readers' results were not added to the log-store: {error}. "
              f"They are kept in {run_file}, and the `verdicts` command above adds them to the log-store "
              "with your judgements, so run it as usual.")
        return 1
    return 0


def matches_per_candidate(runs: list) -> list:
    """(name, matches, readers that answered) for every candidate of the runs, most matches first, then shortest."""
    rows = []
    for run in runs:
        verdicts = run.get("verdicts", {})
        for length in CANDIDATE_LENGTHS:
            answered = [r for r in run["readers"] if r["length"] == length and not r["error"]]
            rows.append((run["candidates"][length],
                         sum(verdicts.get(r["reader_id"]) == "match" for r in answered), len(answered)))
    return sorted(rows, key=lambda row: (-row[1], len(name_words(row[0]))))


def reader_log_lines(run: dict) -> list:
    return [{"kind": "reader", "run_id": run["run_id"], "describe": run["describe"], **result}
            for result in run["readers"]]


def outcome(run: dict, verdicts: dict) -> dict:
    """Which candidates pass, given a match or miss for every reader that answered."""
    passing = []
    for length in CANDIDATE_LENGTHS:
        readers = [r for r in run["readers"] if r["length"] == length]
        failed = [r for r in readers if r["error"]]
        answered = [r for r in readers if not r["error"]]
        if len(failed) <= MAX_FAILED_READERS_FOR_A_PASS and all(verdicts[r["reader_id"]] == "match" for r in answered):
            passing.append(length)
    return {"passing": passing}


def command_verdicts(arguments, log_path=None, ssh_host=None) -> int:
    run_file = pathlib.Path(arguments.run_file)
    run = json.loads(run_file.read_text())
    verdicts = json.loads(arguments.verdicts)
    answered = {r["reader_id"] for r in run["readers"] if not r["error"]}
    missing = sorted(answered - set(verdicts))
    extra = sorted(set(verdicts) - answered)
    bad = sorted(k for k, v in verdicts.items() if v not in ("match", "miss"))
    if missing or extra or bad:
        print(f"{PROGRAM}: REFUSED: give \"match\" or \"miss\" for each reader that answered, and no other; "
              f"missing {missing}, not answering readers {extra}, neither match nor miss {bad}.", file=sys.stderr)
        return 2
    result = outcome(run, verdicts)
    passing = result["passing"]
    chosen = None
    if passing:
        shortest = passing[-1]
        if arguments.choose:
            by_name = {run["candidates"][length]: length for length in passing}
            if arguments.choose not in by_name or not arguments.reason:
                print(f"{PROGRAM}: REFUSED: --choose must name a passing candidate, with --reason; "
                      f"passing: {[run['candidates'][length] for length in passing]}.", file=sys.stderr)
                return 2
            chosen = by_name[arguments.choose]
        else:
            chosen = shortest
    lines = [{"kind": "verdict", "run_id": run["run_id"], "reader_id": r["reader_id"], "model": r["model"],
              "length": r["length"], "verdict": verdicts.get(r["reader_id"], "failed"),
              "only_miss": verdicts.get(r["reader_id"]) == "miss" and all(
                  verdicts.get(o["reader_id"]) == "match" for o in run["readers"]
                  if o["length"] == r["length"] and o is not r and not o["error"])}
             for r in run["readers"]]
    lines.append({"kind": "outcome", "run_id": run["run_id"], "describe": run["describe"],
                  "candidates": run["candidates"], "passing": passing, "chosen": chosen,
                  "choose_reason": arguments.reason if arguments.choose else None,
                  "retry_number": run.get("retry_number", 0)})
    run["verdicts"] = verdicts
    run["outcome"] = lines[-1]
    if not run.get("readers_logged", True):
        lines = reader_log_lines(run) + lines
    error = append_to_log_store(lines, log_path, ssh_host)
    run["readers_logged"] = run.get("readers_logged", True) or error is None
    run_file.write_text(json.dumps(run, indent=2))
    if chosen:
        print(f"Chosen: {run['candidates'][chosen]} ({chosen}). Passing: "
              + ", ".join(f"{run['candidates'][length]} ({length})" for length in passing))
    elif run.get("retry_number", 0) == 0:
        print("No candidate passed. Build three new candidates once, from the misses, and run "
              f"`read ... --retry-of {run_file}`.")
    else:
        print("No candidate passed on the retry either. Matches per candidate, most first:")
        for name, count, total in matches_per_candidate([run, json.loads(pathlib.Path(run["retry_of"]).read_text())]):
            print(f"  {count} of {total}: {name}")
        print(f"Report the first, with what its readers got wrong, and bring the user the readers' accounts in "
              f"{run_file} and {run.get('retry_of')}.")
    if error:
        print(f"FAILED: the judgements were not added to the log-store: {error}. The outcome above stands. "
              "Run this same command again once ned-box answers; until then the per-model data lacks this run.")
        return 1
    return 0 if chosen else 1


def read_log_lines(log_path=None, ssh_host=None) -> list:
    if log_path is None and ssh_host is None and socket.gethostname().split(".")[0] != LOG_STORE_HOSTNAME:
        ssh_host = LOG_STORE_SSH_HOST
    log_path = log_path or READER_RESULTS_LOG
    if ssh_host is None:
        text = pathlib.Path(log_path).read_text() if pathlib.Path(log_path).exists() else ""
    else:
        text, error = run_ssh(ssh_host, f"cat {shlex.quote(log_path)} 2>/dev/null || true")
        if error:
            raise OSError(error)
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def per_model_summary(lines: list) -> dict:
    """Per model: answered, matched, only misses, failed, mean seconds; latest verdict per run and reader."""
    verdicts = {}
    for line in lines:
        if line["kind"] == "verdict":
            verdicts[(line["run_id"], line["reader_id"])] = line
    summary = {}
    for line in lines:
        if line["kind"] != "reader":
            continue
        row = summary.setdefault(line["model"], {"answered": 0, "matched": 0, "only_miss": 0, "failed": 0, "seconds": []})
        if line["error"]:
            row["failed"] += 1
            continue
        row["answered"] += 1
        row["seconds"].append(line["seconds"])
        verdict = verdicts.get((line["run_id"], line["reader_id"]))
        if verdict and verdict["verdict"] == "match":
            row["matched"] += 1
        if verdict and verdict["only_miss"]:
            row["only_miss"] += 1
    for row in summary.values():
        seconds = row.pop("seconds")
        row["mean_seconds"] = round(sum(seconds) / len(seconds), 1) if seconds else None
    return summary


def command_per_model_summary(arguments, log_path=None, ssh_host=None) -> int:
    try:
        lines = read_log_lines(log_path, ssh_host)
    except OSError as error:
        print(f"FAILED: could not read {log_path or READER_RESULTS_LOG}: {error}. "
              "Run this command again once ned-box answers.")
        return 1
    print("model\tanswered\tmatched\tonly miss\tfailed\tmean s")
    for model, row in sorted(per_model_summary(lines).items()):
        print(f"{model}\t{row['answered']}\t{row['matched']}\t{row['only_miss']}\t{row['failed']}\t{row['mean_seconds']}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog=PROGRAM, description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    read = sub.add_parser("read")
    read.add_argument("--describe", required=True)
    for length in CANDIDATE_LENGTHS:
        read.add_argument(f"--{length}", required=True)
    read.add_argument("--sent-name")
    read.add_argument("--retry-of")
    read.add_argument("--run-file")
    verdict = sub.add_parser("verdicts")
    verdict.add_argument("run_file")
    verdict.add_argument("--verdicts", required=True)
    verdict.add_argument("--choose")
    verdict.add_argument("--reason")
    sub.add_parser("per-model-summary")
    arguments = parser.parse_args(argv)
    if arguments.command == "read":
        return command_read(arguments)
    if arguments.command == "verdicts":
        return command_verdicts(arguments)
    return command_per_model_summary(arguments)


if __name__ == "__main__":
    sys.exit(main())
