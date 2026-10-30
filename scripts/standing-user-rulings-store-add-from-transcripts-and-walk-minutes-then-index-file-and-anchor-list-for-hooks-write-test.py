#!/usr/bin/env python3
"""Tests for standing-user-rulings-store-add-from-transcripts-and-walk-minutes-then-index-file-and-anchor-list-for-hooks-write.py.

Run: python3 scripts/standing-user-rulings-store-add-from-transcripts-and-walk-minutes-then-index-file-and-anchor-list-for-hooks-write-test.py
Prints one line per case and exits non-zero if any case fails.

Every case builds its own log-store, agents directory and git repository in a temporary directory;
no real transcript, walk-minutes or store is read or written.
"""

import datetime
import fcntl
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from zoneinfo import ZoneInfo

PROGRAM = Path(__file__).with_name(
    "standing-user-rulings-store-add-from-transcripts-and-walk-minutes-then-index-file-and-anchor-list-for-hooks-write.py")
WALK_CHECK_PROGRAM = (Path(__file__).resolve().parents[1] / "nc-systems" / "skills" / "walk-me-through"
                      / "walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


load("git_redirecting_environment_removal_test_fixture", Path(__file__).resolve().with_name(
    "git-redirecting-environment-removal-test-fixture.py")).remove_git_redirecting_environment_variables_from_this_process()
# A flag the program refuses: were importing it to run main(), it would exit here instead of reading the real log-store.
argv, sys.argv = sys.argv, [str(PROGRAM), "--importing-the-program-must-not-run-it"]
try:
    program = load("standing_user_rulings_index_program", PROGRAM)
except SystemExit:
    print("FAIL  importing the program does not run it")
    sys.exit(1)
finally:
    sys.argv = argv
failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


SEAT_DIRECTORY = "/home/nedlern/agents/alpha-seat"
REPOSITORY_FILES = ("CLAUDE.md", "scripts/tool-one.py", "nc-systems/cold-read/cold-read-fast-read.py",
                    "nc-systems/handoff/handoff-supervisor.py", ".claude/skills/find-info/SKILL.md",
                    "docs/issues/2118-ruling-agent-keeps-user-rulings.md", "SKILL.md", "CLAUDE")


def human(text, stamp, cwd=SEAT_DIRECTORY, **fields):
    record = {"type": "user", "message": {"role": "user", "content": text}, "origin": {"kind": "human"},
              "entrypoint": "cli", "timestamp": stamp, "cwd": cwd, "sessionId": "session-one"}
    record.update(fields)
    return record


def peer(text, stamp):
    return {"type": "user", "message": {"role": "user", "content": text}, "origin": {"kind": "peer"},
            "isMeta": True, "timestamp": stamp, "cwd": SEAT_DIRECTORY}


def queued(text, stamp):
    return {"type": "attachment", "timestamp": stamp, "cwd": SEAT_DIRECTORY, "attachment": {
        "type": "queued_command", "prompt": text, "origin": {"kind": "human"}}}


def agent(text, stamp="2026-10-20T00:00:00Z"):
    return {"type": "assistant", "timestamp": stamp, "cwd": SEAT_DIRECTORY,
            "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}


def lines_of(records):
    return "".join(json.dumps(record) + "\n" for record in records)


class Case:
    def __init__(self, directory):
        self.top = Path(directory)
        self.log_store = self.top / "log-store"
        self.mirror = self.log_store / "agent-session-files-by-machine"
        self.agents = self.top / "agents"
        self.checkout = self.top / "checkout"
        (self.agents / "alpha-seat" / "docs" / "walk").mkdir(parents=True)
        (self.agents / "merge-lane-2").mkdir(parents=True)
        self.make_repository()

    def make_repository(self):
        for name in REPOSITORY_FILES:
            path = self.checkout / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("x\n")
        git = ["git", "-C", str(self.checkout), "-c", "user.name=t", "-c", "user.email=t@t"]
        subprocess.run(git[:3] + ["init", "-q"], check=True)
        subprocess.run(git + ["add", "-A"], check=True)
        subprocess.run(git + ["commit", "-q", "-m", "files"], check=True)
        subprocess.run(git + ["update-ref", "refs/remotes/origin/main", "HEAD"], check=True)

    def transcript(self, machine, records, name="session-one.jsonl", key="-home-nedlern-agents-alpha-seat",
                   append=False):
        tree = self.mirror / ("recovered/from-time-machine" if machine == "recovered" else f"{machine}/projects")
        path = tree / key / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a" if append else "w") as handle:
            handle.write(records if isinstance(records, str) else lines_of(records))
        return path

    def minutes(self, name, lines, shipped=False):
        directory = (self.log_store / "walk") if shipped else (self.agents / "alpha-seat" / "docs" / "walk")
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / name
        path.write_text("".join(line + "\n" for line in lines))
        return path

    def run(self, *extra):
        return subprocess.run([sys.executable, str(PROGRAM), "--log-store", str(self.log_store),
                               "--agents-directory", str(self.agents), "--repository-checkout", str(self.checkout),
                               *extra], capture_output=True, text=True, timeout=120)

    @property
    def store_directory(self):
        return self.log_store / "user-rulings"

    def query(self, sql, parameters=()):
        connection = sqlite3.connect(str(self.store_directory / program.STORE_FILE_NAME))
        try:
            return connection.execute(sql, parameters).fetchall()
        finally:
            connection.close()

    def entries(self):
        return self.query("SELECT kind, text, said_at_utc, source_path, source_line, agent_message_answered "
                          "FROM entries ORDER BY entry_id")

    def tags(self, text):
        return {row[0] for row in self.query(
            "SELECT tag FROM entry_tags JOIN entries USING (entry_id) WHERE text = ?", (text,))}

    def index(self):
        lines = (self.store_directory / program.INDEX_FILE_NAME).read_text().splitlines()
        return json.loads(lines[0]), [json.loads(line) for line in lines[1:]]

    def anchors(self):
        return (self.store_directory / program.ANCHOR_LIST_FILE_NAME).read_text().splitlines()


def described(result):
    return f"exit {result.returncode}; stdout {result.stdout!r}; stderr {result.stderr!r}"


ANSWERED = ("Item 3 asks about GHI 2118 and PR 2120, my task #127 and merge-lane-2's task #12; "
            "the change edits /Users/el/agents/alpha-seat/.claude/worktrees/w/nc-systems/cold-read/cold-read-fast-read.py "
            "and scripts/tool-one.py. Approve?")

# His words, a peer's message, a queued message, a claude -p prompt and a handoff opener.
with tempfile.TemporaryDirectory() as directory:
    case = Case(directory)
    path = case.transcript("ned-box", [
        human("start on the store", "2026-10-20T01:00:00Z"),
        agent(ANSWERED),
        human("A, approve; also look at /home/nedlern/agents/alpha-seat/CLAUDE.md and .claude/skills/find-info/SKILL.md",
              "2026-10-20T01:05:00Z"),
        peer("Another Claude session sent a message: about GHI 9", "2026-10-20T01:06:00Z"),
        queued("and the hook too", "2026-10-20T01:07:00Z"),
        human("Review this file for a range of defects.", "2026-10-20T01:08:00Z", entrypoint="sdk-cli"),
        human("Read /h/a-dialog-0002.md — the dialog from the session you are continuing", "2026-10-20T01:09:00Z"),
    ])
    result = case.run()
    entries = case.entries()
    check("a first run exits 0 and adds his typed and queued messages only",
          result.returncode == 0 and [entry[1] for entry in entries] == [
              "start on the store",
              "A, approve; also look at /home/nedlern/agents/alpha-seat/CLAUDE.md and .claude/skills/find-info/SKILL.md",
              "and the hook too"], described(result) + f" {entries}")
    check("each entry keeps its UTC time, its transcript line and the agent message he answered",
          entries[1][2:] == ("2026-10-20T01:05:00Z", str(path), 3, ANSWERED) and entries[0][5] is None
          and entries[2][5] is None, entries)
    check("the summary line counts what was added and what the index file holds",
          "added 3 user-words and 0 walk-minutes-user-ruling entries" in result.stdout
          and "holds 3 standing entries" in result.stdout, result.stdout)
    check("each entry keeps its agent-session's id",
          case.query("SELECT DISTINCT session_id FROM entries") == [("session-one",)],
          case.query("SELECT DISTINCT session_id FROM entries"))
    check("the store records its schema version",
          case.query("PRAGMA user_version") == [(1,)], case.query("PRAGMA user_version"))
    approve = entries[1][1]
    check("GHIs, pull requests, tasks and systems in the agent message, and files in his words, become tags; "
          "a path's shorter trailing parts, such as SKILL.md, do not",
          case.tags(approve) == {"GHI 2118", "PR 2120", "task alpha-seat 127", "task merge-lane-2 12",
                                 "nc-systems/cold-read/", "CLAUDE.md", ".claude/skills/find-info/SKILL.md",
                                 "nc-systems/skills/"}, case.tags(approve))
    check("a file named only in the agent message is not a tag",
          "scripts/tool-one.py" not in case.tags(approve)
          and "nc-systems/cold-read/cold-read-fast-read.py" not in case.tags(approve), case.tags(approve))
    header, index = case.index()
    check("the index file starts with its build time and lists standing entries newest first",
          header["standing_entry_count"] == 3 and "index_built_at_utc" in header
          and [entry["said_at_utc"] for entry in index] == ["2026-10-20T01:07:00Z", "2026-10-20T01:05:00Z",
                                                            "2026-10-20T01:00:00Z"], (header, index))
    check("a text of fewer than 30 words is in the index file whole",
          [entry["text"] for entry in index][2] == "start on the store", index)
    check("an index line carries its id, link, tags and anchors",
          index[1]["link"] == f"nedlern@ned-box:{path} line 3" and index[1]["id"].startswith("entry-")
          and "/docs/issues/2118-ruling-agent-keeps-user-rulings.md" in index[1]["anchors"], index[1])
    check("the anchor list holds tagged files, system directories and GHI-MD paths, each with a leading slash",
          case.anchors() == ["/.claude/skills/find-info/SKILL.md", "/CLAUDE.md",
                             "/docs/issues/2118-ruling-agent-keeps-user-rulings.md", "/nc-systems/cold-read/",
                             "/nc-systems/skills/"], case.anchors())
    rerun = case.run()
    check("a rerun with nothing new adds nothing",
          rerun.returncode == 0 and len(case.entries()) == 3
          and "added 0 user-words and 0 walk-minutes-user-ruling entries" in rerun.stdout, described(rerun))
    check("the pair table is there, empty, and its first state is unreviewed",
          case.query("SELECT count(*) FROM entry_pairs") == [(0,)]
          and "DEFAULT 'unreviewed'" in case.query("SELECT sql FROM sqlite_master WHERE name = 'entry_pairs'")[0][0],
          case.query("SELECT sql FROM sqlite_master WHERE name = 'entry_pairs'"))
    check("the store is full-text searchable over his words and the agent message",
          case.query("SELECT rowid FROM entries_full_text WHERE entries_full_text MATCH 'merge'") == [(2,)],
          case.query("SELECT rowid FROM entries_full_text WHERE entries_full_text MATCH 'merge'"))

# A transcript that grows, with a last line still being written.
with tempfile.TemporaryDirectory() as directory:
    case = Case(directory)
    path = case.transcript("mac", [human("one", "2026-10-21T00:00:00Z"), agent("About GHI 46?")])
    whole_line = json.dumps(human("two", "2026-10-21T00:05:00Z"))
    case.transcript("mac", "not json\n" + whole_line[:20], append=True)
    first = case.run()
    check("a last line without its newline is not read yet",
          first.returncode == 0 and [entry[1] for entry in case.entries()] == ["one"], described(first))
    case.transcript("mac", whole_line[20:] + "\n" + json.dumps(human("three", "2026-10-21T00:06:00Z")) + "\n",
                    append=True)
    second = case.run()
    entries = case.entries()
    check("the next run reads on from where the last stopped, counting every line, malformed ones included",
          second.returncode == 0 and [(entry[1], entry[4]) for entry in entries] == [("one", 1), ("two", 4),
                                                                                       ("three", 5)],
          described(second) + f" {entries}")
    check("the agent message he answered carries over between runs",
          entries[1][5] == "About GHI 46?" and case.tags("two") == {"GHI 46"}, (entries, case.tags("two")))

# The same message in the Mac's mirror and the recovered copy; a file rewritten shorter.
with tempfile.TemporaryDirectory() as directory:
    case = Case(directory)
    records = [human("same words", "2026-08-01T00:00:00Z"), agent("ok"), human("later", "2026-08-01T00:02:00Z")]
    mac = case.transcript("mac", records)
    case.transcript("recovered", [agent("an older copy starts earlier")] + records[:1])
    result = case.run()
    entries = case.entries()
    check("a message in the mirror and in the recovered copy is stored once, linked to the mirror",
          result.returncode == 0 and [(entry[1], entry[3]) for entry in entries] == [
              ("same words", str(mac)), ("later", str(mac))], described(result) + f" {entries}")
    case.transcript("mac", records[:1])
    again = case.run()
    check("a file rewritten shorter is read again from its start without adding twice",
          again.returncode == 0 and len(case.entries()) == 2
          and case.query("SELECT size_read FROM source_files_read WHERE path = ?", (str(mac),))
          == [(mac.stat().st_size,)], described(again))

# Several agent turns before he answers, a long agent message, a JSON line that is not a record, a bare file name.
with tempfile.TemporaryDirectory() as directory:
    case = Case(directory)
    long_message = "x" * 9000 + " ends with GHI 46"
    path = case.transcript("ned-box", [
        agent("First part names PR 7."), agent("Second part."), human("noted", "2026-10-24T00:00:00Z"),
        agent(long_message), human("ok", "2026-10-24T00:01:00Z"),
    ])
    case.transcript("ned-box", "[1, 2]\nnot json\n" + lines_of([
        human("see CLAUDE.md", "2026-10-24T00:02:00Z"),
        human("see scripts/tool-one.py", "2026-10-24T00:03:00Z"),
        agent("This touches nc-systems/handoff/ and nc-systems/new-system/plan.md."),
        human("no time", ""),
    ]), append=True)
    result = case.run()
    entries = {entry[1]: entry for entry in case.entries()}
    check("the agent message he answered joins every agent turn since his previous message",
          entries["noted"][5] == "First part names PR 7.\n\nSecond part." and case.tags("noted") == {"PR 7"},
          (entries.get("noted"), case.tags("noted")))
    check("a long agent message keeps its last 8,000 characters",
          entries["ok"][5] == long_message[-8000:] and len(entries["ok"][5]) == 8000
          and case.tags("ok") == {"GHI 46"}, len(entries["ok"][5] or ""))
    check("a JSON line that is not a record is skipped, and the lines after it are read",
          result.returncode == 0 and entries["see CLAUDE.md"][4] == 8, described(result) + f" {entries}")
    check("a file outside nc-systems/ and .claude/skills/ is a tag with no system",
          case.tags("see scripts/tool-one.py") == {"scripts/tool-one.py"}, case.tags("see scripts/tool-one.py"))
    check("a system directory named by a path that is no file on origin/main is still a system tag",
          case.tags("no time") == {"nc-systems/handoff/", "nc-systems/new-system/"}, case.tags("no time"))
    check("a message with no timestamp is stored once, and again not on a rerun",
          "no time" in entries and case.run().returncode == 0
          and [entry[1] for entry in case.entries()].count("no time") == 1, entries.get("no time"))
    check("a top-level repository file named alone, without a path, is a tag",
          case.tags("see CLAUDE.md") == {"CLAUDE.md"}, case.tags("see CLAUDE.md"))

# A transcript is read on from its stored position, not from its start.
with tempfile.TemporaryDirectory() as directory:
    case = Case(directory)
    path = case.transcript("mac", [human("AAAA", "2026-10-25T00:00:00Z")])
    case.run()
    path.write_text(path.read_text().replace("AAAA", "BBBB") + lines_of([human("next", "2026-10-25T00:01:00Z")]))
    result = case.run()
    check("a grown transcript is read from where the last run stopped, so earlier lines are not read again",
          result.returncode == 0 and [entry[1] for entry in case.entries()] == ["AAAA", "next"],
          described(result) + f" {case.entries()}")

# A session outside nedschorus is stored with no tags.
with tempfile.TemporaryDirectory() as directory:
    case = Case(directory)
    case.transcript("recovered", [agent("GHI 30 is open."),
                                  human("fix GHI 30 in scripts/tool-one.py", "2026-07-01T00:00:00Z",
                                        cwd="/Users/el/Projects/nedlern")], key="-Users-el-Projects-nedlern")
    result = case.run()
    check("a message from an agent-session outside nedschorus is stored but not tagged",
          result.returncode == 0 and len(case.entries()) == 1 and case.tags("fix GHI 30 in scripts/tool-one.py") == set(),
          described(result) + f" {case.tags('fix GHI 30 in scripts/tool-one.py')}")

# Walk-minutes: the check program's answer line, a deferred line, a dated citation, a shipped copy.
walk_check = load("walk_me_through_check", WALK_CHECK_PROGRAM)
answer_line = walk_check.CHECK_MINUTES.format(item="item 6.2 of 8", answered="approved", hashtag="",
                                              date_and_time="2026-10-29 07:24")
obvious_line = walk_check.CHECK_MINUTES.format(item="item 2 of 8", answered="approved",
                                               hashtag=walk_check.OBVIOUS_HASHTAG, date_and_time="2026-01-15 23:30")
deferred_line = walk_check.CHECK_DEFERRED_MINUTES.format(item="item 6 of 8", date_and_time="2026-10-28 18:04")
cited_line = 'Item 5.2 (GHI 2118, scripts/tool-one.py): "y" (user-ruled 2026-10-16). Approved as shown.'
timed_line = "Item 17.2, A, approved (user-ruled 2026-10-29T00:16:22Z)."
with tempfile.TemporaryDirectory() as directory:
    case = Case(directory)
    live = case.minutes("alpha-seat-open-decisions-2026-10-28-minutes.md",
                        ["# Minutes", answer_line, deferred_line, cited_line, timed_line, obvious_line])
    case.minutes("alpha-seat-open-decisions-2026-10-28-minutes.md", [answer_line, cited_line], shipped=True)
    case.minutes("other-walk-minutes.md", [cited_line + " Shipped elsewhere."], shipped=True)
    (case.log_store / "walk" / "superseded").mkdir()
    (case.log_store / "walk" / "superseded" / "old-minutes.md").write_text(timed_line + " superseded\n")
    result = case.run()
    entries = case.query("SELECT text, said_at_utc, source_path, source_line, agent_seat FROM entries "
                         "WHERE kind = 'walk-minutes-user-ruling' ORDER BY entry_id")
    pacific = datetime.datetime(2026, 10, 29, 7, 24, tzinfo=ZoneInfo("America/Los_Angeles"))
    check("walk-me-through's answer line is a user-ruling, its local time stored as UTC",
          result.returncode == 0 and entries[0][:4] == (answer_line, pacific.astimezone(datetime.timezone.utc)
                                                        .strftime("%Y-%m-%dT%H:%MZ"), str(live), 2)
          and entries[0][1] == "2026-10-29T14:24Z", described(result) + f" {entries}")
    check("a winter answer line is converted at the winter offset, and its hashtag is read",
          ("2026-01-16T07:30Z") in [entry[1] for entry in entries if entry[0] == obvious_line], entries)
    check("a deferred answer line decides nothing and is not stored",
          deferred_line not in [entry[0] for entry in entries], entries)
    check("a user-ruled citation keeps its date, or its UTC time, as written",
          [(entry[0], entry[1]) for entry in entries if entry[0] in (cited_line, timed_line)]
          == [(cited_line, "2026-10-16"), (timed_line, "2026-10-29T00:16:22Z")], entries)
    check("a live walk-minutes file and its shipped copy store each line once; superseded copies are not read",
          sorted(entry[0] for entry in entries) == sorted([answer_line, cited_line, timed_line, obvious_line,
                                                           cited_line + " Shipped elsewhere."]), entries)
    check("a walk-minutes entry is tagged from its line and links to its walk-minutes line",
          case.tags(cited_line) == {"GHI 2118", "scripts/tool-one.py"} and entries[0][4] == "alpha-seat", (case.tags(cited_line), entries))
    with open(live, "a") as handle:
        handle.write("New line (user-ruled 2026-10-30).\n")
    rerun = case.run()
    check("a changed walk-minutes file adds only its new user-ruling lines",
          rerun.returncode == 0 and "added 0 user-words and 1 walk-minutes-user-ruling entries" in rerun.stdout,
          described(rerun))

# A transcript replaced by another file at its path is read from its start.
# The stored inode is set above, then below, the new file's, whichever order the file system gave them.
for stored_inode_above in (True, False):
    with tempfile.TemporaryDirectory() as directory:
        case = Case(directory)
        path = case.transcript("mac", [human("CCCC", "2026-10-25T00:00:00Z")])
        case.run()
        replacement = path.with_name("replacement.tmp")
        replacement.write_text(lines_of([human("DDDD", "2026-10-25T00:00:00Z"),
                                         human("more", "2026-10-25T00:01:00Z")]))
        os.replace(replacement, path)
        connection = sqlite3.connect(str(case.store_directory / program.STORE_FILE_NAME))
        with connection:
            connection.execute("UPDATE source_files_read SET inode = ?",
                               (path.stat().st_ino + 2 ** 40 if stored_inode_above else 0,))
        connection.close()
        result = case.run()
        check(f"a transcript replaced by another file is read from its start (stored inode "
              f"{'above' if stored_inode_above else 'below'} the new file's)",
              result.returncode == 0 and [entry[1] for entry in case.entries()] == ["CCCC", "DDDD", "more"],
              described(result) + f" {case.entries()}")

# A walk-minutes file rewritten shorter is read again.
with tempfile.TemporaryDirectory() as directory:
    case = Case(directory)
    minutes = case.minutes("alpha-seat-walk-2026-10-28-minutes.md",
                           ["# Minutes", "padding line " * 20, "First (user-ruled 2026-10-16)."])
    case.run()
    case.minutes("alpha-seat-walk-2026-10-28-minutes.md", ["Second (user-ruled 2026-10-17)."])
    result = case.run()
    check("a walk-minutes file rewritten shorter is read again",
          "added 0 user-words and 1 walk-minutes-user-ruling entries" in result.stdout, described(result))

# Another run holds the lock.
with tempfile.TemporaryDirectory() as directory:
    case = Case(directory)
    case.transcript("ned-box", [human("words", "2026-10-22T00:00:00Z")])
    case.store_directory.mkdir(parents=True)
    with open(case.store_directory / program.LOCK_FILE_NAME, "w") as holder:
        fcntl.flock(holder, fcntl.LOCK_EX)
        held = case.run()
    check("a run while another holds the lock exits 3 and adds nothing",
          held.returncode == 3 and "No action is needed:" in held.stdout
          and not (case.store_directory / program.STORE_FILE_NAME).exists(), described(held))

# A transcript that cannot be read.
with tempfile.TemporaryDirectory() as directory:
    case = Case(directory)
    blocked = case.transcript("mac", [human("unreadable", "2026-10-22T00:00:00Z")], name="blocked.jsonl")
    case.transcript("ned-box", [human("readable", "2026-10-22T00:01:00Z")])
    blocked.chmod(0)
    result = case.run()
    blocked.chmod(0o644)
    check("a transcript that cannot be read is reported FAILED, exit 1, and the others are still added",
          result.returncode == 1 and f"FAILED: transcript {blocked}:" in result.stderr
          and "read again from where it stopped at the next run" in result.stderr
          and "send prime-intellect" in result.stderr
          and [entry[1] for entry in case.entries()] == ["readable"]
          and f"transcript {blocked}" in case.query("SELECT failures FROM index_program_runs")[0][0],
          described(result))
    later = case.run()
    check("the next run reads the transcript that failed",
          later.returncode == 0 and [entry[1] for entry in case.entries()] == ["readable", "unreadable"],
          described(later))

# A walk-minutes file that cannot be read; a log-store with nothing in it yet.
with tempfile.TemporaryDirectory() as directory:
    case = Case(directory)
    blocked = case.minutes("alpha-seat-blocked-2026-10-28-minutes.md", ["Blocked (user-ruled 2026-10-16)."])
    case.minutes("alpha-seat-open-2026-10-28-minutes.md", ["Open (user-ruled 2026-10-17)."])
    blocked.chmod(0)
    result = case.run()
    blocked.chmod(0o644)
    check("a walk-minutes file that cannot be read is reported FAILED, exit 1, and the others are still added",
          result.returncode == 1 and f"FAILED: walk-minutes {blocked}:" in result.stderr
          and [entry[1] for entry in case.entries()] == ["Open (user-ruled 2026-10-17)."], described(result))
with tempfile.TemporaryDirectory() as directory:
    case = Case(directory)
    result = case.run()
    check("a first run on a log-store that does not exist yet makes the store's directory and an empty index",
          result.returncode == 0 and not (case.log_store / "agent-session-files-by-machine").exists()
          and case.index()[0]["standing_entry_count"] == 0 and case.anchors() == [], described(result))

# A failure part way through a transcript leaves neither its entries nor its progress behind.
with tempfile.TemporaryDirectory() as directory:
    case = Case(directory)
    path = case.transcript("ned-box", [human("first", "2026-10-22T00:00:00Z"), human("second", "2026-10-22T00:01:00Z")])
    case.store_directory.mkdir(parents=True)
    connection = program.open_store(case.store_directory / program.STORE_FILE_NAME)
    repository = program.Repository(case.checkout)
    real_add_entry, calls = program.add_entry, []

    def add_entry_failing_at_second(connection_, entry, tags_by_source):
        calls.append(entry["text"])
        if entry["text"] == "second":
            raise sqlite3.OperationalError("disk I/O error")
        return real_add_entry(connection_, entry, tags_by_source)

    program.add_entry = add_entry_failing_at_second
    try:
        with connection:
            program.read_transcript(connection, "ned-box", path, repository, set())
        raised = False
    except sqlite3.OperationalError:
        raised = True
    finally:
        program.add_entry = real_add_entry
    check("a failure part way through a transcript rolls back its entries and its progress",
          raised and calls == ["first", "second"]
          and connection.execute("SELECT count(*) FROM entries").fetchone() == (0,)
          and connection.execute("SELECT count(*) FROM source_files_read").fetchone() == (0,), calls)
    connection.close()

# The index file cannot be written.
with tempfile.TemporaryDirectory() as directory:
    case = Case(directory)
    case.transcript("ned-box", [human("kept", "2026-10-22T00:00:00Z")])
    (case.store_directory / (program.INDEX_FILE_NAME + ".partial")).mkdir(parents=True)
    result = case.run()
    check("an index file that cannot be written is reported FAILED, exit 1, and the store keeps the entries",
          result.returncode == 1 and "FAILED: the index file or the anchor list:" in result.stderr
          and f"`python3 {PROGRAM.resolve()}` once more" in result.stderr and "not written" in result.stdout
          and [entry[1] for entry in case.entries()] == ["kept"]
          and not (case.store_directory / program.INDEX_FILE_NAME).exists(), described(result))

# origin/main cannot be read.
with tempfile.TemporaryDirectory() as directory:
    case = Case(directory)
    case.transcript("ned-box", [human("words", "2026-10-22T00:00:00Z")])
    subprocess.run(["git", "-C", str(case.checkout), "update-ref", "-d", "refs/remotes/origin/main"], check=True)
    result = case.run()
    check("a checkout whose origin/main cannot be read stops the run, exit 2, before anything is added",
          result.returncode == 2 and "FAILED: this run: git ls-tree of origin/main" in result.stderr
          and f"git -C {case.checkout} fetch origin main" in result.stderr
          and "--repository-checkout" in result.stderr
          and not (case.store_directory / program.STORE_FILE_NAME).exists(), described(result))

# The store cannot be opened, or is newer than the program.
with tempfile.TemporaryDirectory() as directory:
    case = Case(directory)
    case.store_directory.mkdir(parents=True)
    (case.store_directory / program.STORE_FILE_NAME).write_text("this is not a database, but text long enough " * 40)
    result = case.run()
    check("a store that cannot be opened stops the run, exit 2, and says not to replace it",
          result.returncode == 2 and "cannot be opened" in result.stderr
          and "do not delete, move or replace the store" in result.stderr, described(result))
with tempfile.TemporaryDirectory() as directory:
    case = Case(directory)
    case.store_directory.mkdir(parents=True)
    newer = sqlite3.connect(str(case.store_directory / program.STORE_FILE_NAME))
    newer.execute(f"PRAGMA user_version={program.SCHEMA_VERSION + 1}")
    newer.close()
    result = case.run()
    check("a store with a newer schema stops the run, exit 2",
          result.returncode == 2 and "run your checkout's copy of this program again" in result.stderr,
          described(result))
with tempfile.TemporaryDirectory() as directory:
    case = Case(directory)
    case.log_store.mkdir()
    (case.log_store / "user-rulings").write_text("a file where the store's directory should be\n")
    result = case.run()
    check("a store directory that cannot be made stops the run, exit 2",
          result.returncode == 2 and "FAILED: the store directory" in result.stderr, described(result))

# The index file cuts long texts, and leaves out entries that are no longer standing.
with tempfile.TemporaryDirectory() as directory:
    case = Case(directory)
    long_text = " ".join(f"w{number}" for number in range(40))
    case.transcript("ned-box", [human(long_text, "2026-10-23T00:00:00Z"), agent("GHI 2118?"),
                                human("superseded words", "2026-10-23T00:01:00Z")])
    case.run()
    connection = sqlite3.connect(str(case.store_directory / program.STORE_FILE_NAME))
    with connection:
        connection.execute("UPDATE entries SET state = 'superseded' WHERE text = 'superseded words'")
    connection.close()
    case.run()
    header, index = case.index()
    check("an index line holds the first 30 words of a long text, and superseded entries are left out",
          header["standing_entry_count"] == 1 and index[0]["text"] == " ".join(long_text.split()[:30]) + " …"
          and case.anchors() == []
          and "w29 …" in (case.store_directory / program.INDEX_FILE_NAME).read_text(encoding="utf-8"),
          (header, index, case.anchors()))

# A transcript and a walk-minutes file unchanged since the last run are not opened.
with tempfile.TemporaryDirectory() as directory:
    case = Case(directory)
    transcript = case.transcript("ned-box", [human("unchanged", "2026-10-26T00:00:00Z")])
    minutes = case.minutes("alpha-seat-unchanged-2026-10-26-minutes.md", ["Kept (user-ruled 2026-10-26)."])
    empty = case.minutes("alpha-seat-empty-2026-10-26-minutes.md", [])
    first = case.run()
    transcript.chmod(0)
    minutes.chmod(0)
    try:
        again = case.run()
    finally:
        transcript.chmod(0o644)
        minutes.chmod(0o644)
    check("a transcript and a walk-minutes file whose size and mtime are unchanged are not opened",
          first.returncode == 0 and again.returncode == 0 and "FAILED" not in again.stderr, described(again))
    check("an empty walk-minutes file is recorded as read, with no lines",
          case.query("SELECT size_read, lines_read FROM source_files_read WHERE path = ?", (str(empty),)) == [(0, 0)],
          case.query("SELECT path, size_read, lines_read FROM source_files_read"))

# A transcript rewritten in place at the same size is read on from its stored position.
with tempfile.TemporaryDirectory() as directory:
    case = Case(directory)
    path = case.transcript("mac", [human("EEEE", "2026-10-26T00:00:00Z")])
    case.run()
    path.write_text(path.read_text().replace("EEEE", "FFFF"))
    os.utime(path, ns=(path.stat().st_atime_ns, path.stat().st_mtime_ns + 10 ** 9))
    result = case.run()
    check("a transcript of the same size but a new mtime is read on from where the last run stopped",
          result.returncode == 0 and [entry[1] for entry in case.entries()] == ["EEEE"],
          described(result) + f" {case.entries()}")

# A text of exactly 30 words.
with tempfile.TemporaryDirectory() as directory:
    case = Case(directory)
    thirty = " ".join(f"v{number}" for number in range(30))
    case.transcript("ned-box", [human(thirty, "2026-10-26T00:00:00Z")])
    case.run()
    check("a text of exactly 30 words is in the index file whole, without the mark of a cut",
          case.index()[1][0]["text"] == thirty, case.index())

print(f"{'FAILED' if failures else 'all cases passed'}: {len(failures)} failure(s)")
sys.exit(1 if failures else 0)
