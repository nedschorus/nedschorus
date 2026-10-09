#!/usr/bin/env python3
"""Tests for bare-number-citation-in-markdown-and-agent-reply-warning-hook.py.

Run: python3 scripts/bare-number-citation-in-markdown-and-agent-reply-warning-hook-test.py
Prints one line per case and exits non-zero if any case fails.

The scanner's cases call bare_references_in() directly. The hook's cases run
the hook as Claude Code does, as a subprocess reading a payload on stdin: the
PostToolUse cases against a throwaway repository under a temporary directory,
the Stop cases against transcripts written there.

Every git call, the hook's included, runs with the variables that redirect
git (GIT_DIR and its kin) removed, so a GIT_DIR inherited from the caller
cannot point these writes at another repository.
"""

import atexit
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().with_name(
        "git-redirecting-environment-removal-test-fixture.py"))
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

HOOK_PATH = Path(__file__).resolve().with_name("bare-number-citation-in-markdown-and-agent-reply-warning-hook.py")

# An attended session, as an agent-seat's own is; the headless cases override it.
HOOK_ENVIRONMENT = {name: value for name, value in os.environ.items()
                    if name != "NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER"}
HOOK_ENVIRONMENT["CLAUDE_CODE_SESSION_ATTENDED"] = "1"

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


specification = importlib.util.spec_from_file_location("bare_number_citation_in_markdown_and_agent_reply_warning_hook", HOOK_PATH)
hook = importlib.util.module_from_spec(specification)
specification.loader.exec_module(hook)


def found(text):
    return [reference.reference for reference in hook.bare_references_in(text)]


# ---------------------------------------------------------------------------
# The scanner, called directly.
# ---------------------------------------------------------------------------

for text, expected in (
        ("Merged in PR 931 today.", "PR 931"),
        ("Merged in PR #931 today.", "PR #931"),
        ("Merged in PR#931 today.", "PR#931"),
        ("see pr 931", "pr 931"),
        ("PRs 931 and 932 merged.", "PRs 931"),
        ("the pull request 931 merged", "pull request 931"),
        ("the pull requests #931 merged", "pull requests #931"),
        ("Issue 46 holds it.", "Issue 46"),
        ("issues #46 hold it.", "issues #46"),
        ("see GHI 1058", "GHI 1058"),
        ("see ghi #1058", "ghi #1058"),
        ("task 170 is open", "task 170"),
        ("Tasks #170 are open", "Tasks #170"),
        ("evidence on #37.", "#37"),
        ("(#12345)", "#12345")):
    check(f"a bare reference is found: {text}", found(text) == [expected], found(text))

check("an ID-type word with # is one hit, not also a hit for the # alone",
      found("PR #426 and #427") == ["PR #426", "#427"], found("PR #426 and #427"))

for text in ("item 3 of 10", "it took 42 seconds", "the 1058 count",
             "&#123; is an entity", "page#12 is a fragment", "#1 is one digit",
             "#123456 is six digits", "## 3 is a heading", "#12abc is no number",
             "issue1058 is one word", "a reissue 3 is not an issue",
             "the task's 3 parts"):
    check(f"no bare reference is found: {text}", found(text) == [], found(text))

check("text in a fenced code block is skipped",
      found("Before.\n```\nPR 931\n#37\n```\nAfter.") == [],
      found("Before.\n```\nPR 931\n#37\n```\nAfter."))
check("text in a tilde fence is skipped",
      found("~~~sh\ngh pr view 931\n~~~\n") == [], found("~~~sh\ngh pr view 931\n~~~\n"))
check("a fence opened on a list item's marker line is skipped, and prose after it is read",
      found("- ```\n  PR 1\n  ```\n\nPR 2 merged.") == ["PR 2"],
      found("- ```\n  PR 1\n  ```\n\nPR 2 merged."))
check("text in an inline code span is skipped",
      found("run `gh pr view 931` and `#37`") == [], found("run `gh pr view 931` and `#37`"))
check("text in a double-backtick code span is skipped",
      found("run ``PR 931`` now") == [], found("run ``PR 931`` now"))
link = "PR [PR 931: the fix](https://github.com/nedschorus/nedschorus/pull/931#issue-12)"
check("a Markdown link's text and target are both skipped", found(link) == [], found(link))
nested = "GHI [Fix [the] issue 7](https://example.com/issues/7) closed"
check("a link whose text holds brackets is skipped whole", found(nested) == [], found(nested))
check("a bare URL is skipped",
      found("see https://example.com/page/#12 and <https://x.org/#34>") == [],
      found("see https://example.com/page/#12 and <https://x.org/#34>"))
for line in ("supports-issues: 1058, 1036", "issue-marker: #1058",
             "  supports-issues: #12"):
    check(f"a line a program reads is skipped: {line}", found(line) == [], found(line))
check("a line merely mentioning supports-issues later is still read",
      found("We set supports-issues: on PR 12.") == ["PR 12"],
      found("We set supports-issues: on PR 12."))
check("a hit outside a link on the same line as a link is found",
      found("[x](https://y.z/pull/1) and PR 2") == ["PR 2"],
      found("[x](https://y.z/pull/1) and PR 2"))

lined = hook.bare_references_in("one\nPR 5 here\nthree\n#77 there")
check("hits carry their line numbers",
      [(reference.line_number, reference.reference) for reference in lined]
      == [(2, "PR 5"), (4, "#77")], [(r.line_number, r.reference) for r in lined])
check("line numbers to report filter the hits",
      [r.reference for r in hook.bare_references_in("PR 1\nPR 2", {2})] == ["PR 2"])
excerpt = hook.bare_references_in("x" * 100 + " PR 9 " + "y" * 100)[0].excerpt
check("a long line's excerpt is bounded and marked as cut",
      excerpt.startswith("...") and excerpt.endswith("...") and "PR 9" in excerpt
      and len(excerpt) < 100, excerpt)

note = hook.note_text(hook.LAST_MESSAGE_OPENING_LINES,
                      hook.bare_references_in(" ".join(f"PR {n}" for n in range(1, 14))))
check("the note lists at most ten hits and counts the rest",
      note.count('" in "') == 10 and "3 more not listed" in note, note)
check("the note says how to cite instead",
      "ID-type and its name" in note and "PR [title](url), not a bare number" in note, note)


# ---------------------------------------------------------------------------
# The hook, run as a subprocess.
# ---------------------------------------------------------------------------

def run_hook(payload, environment=None):
    stdin = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run([sys.executable, str(HOOK_PATH)], input=stdin,
                          capture_output=True, text=True, timeout=60,
                          env=environment or HOOK_ENVIRONMENT)


def context_of(result):
    if not result.stdout.strip():
        return None
    output = json.loads(result.stdout)
    return output["hookSpecificOutput"]


SCRATCH = Path(tempfile.mkdtemp(prefix="bare-number-citation-in-markdown-and-agent-reply-warning-hook-test-"))
atexit.register(shutil.rmtree, str(SCRATCH), True)
REPOSITORY = SCRATCH / "repository"
REPOSITORY.mkdir()


def git(*arguments):
    return subprocess.run(["git", *arguments], cwd=str(REPOSITORY), capture_output=True,
                          text=True, check=True)


git("init", "-q")
git("config", "user.email", "test@example.com")
git("config", "user.name", "test")
toplevel = git("rev-parse", "--show-toplevel").stdout.strip()
if Path(toplevel).resolve() != REPOSITORY.resolve():
    print(f"FAIL  the scratch repository is a repository at its own path: {toplevel}")
    sys.exit(1)
(REPOSITORY / ".gitignore").write_text("ignored/\n", encoding="utf-8")
(REPOSITORY / "docs").mkdir()
(REPOSITORY / "docs" / "old.md").write_text("Old text cites PR 100.\n", encoding="utf-8")
git("add", "-A")
git("commit", "-q", "-m", "fixture")


def tool_payload(tool_name, file_path, **tool_input):
    return {"hook_event_name": "PostToolUse", "tool_name": tool_name, "cwd": str(REPOSITORY),
            "tool_input": {"file_path": str(file_path), **tool_input}}


result = run_hook(tool_payload("Write", REPOSITORY / "docs" / "new.md",
                               content="Title\n\nMerged in PR 931.\n"))
context = context_of(result)
check("Write of a new Markdown file with a bare reference gets a PostToolUse note",
      result.returncode == 0 and context is not None
      and context["hookEventName"] == "PostToolUse"
      and 'docs/new.md:3: "PR 931"' in context["additionalContext"], result.stdout)

result = run_hook(tool_payload("Write", REPOSITORY / "docs" / "old.md",
                               content="Old text cites PR 100.\nNew text cites #200.\n"))
context = context_of(result)
check("Write reports only lines HEAD does not hold",
      context is not None and '"#200"' in context["additionalContext"]
      and "PR 100" not in context["additionalContext"], result.stdout)

result = run_hook(tool_payload("Write", REPOSITORY / "docs" / "old.md",
                               content="Old text cites PR 100.\nA plain line.\n"))
check("Write whose only hit is on a committed line is silent",
      result.returncode == 0 and result.stdout == "", result.stdout)

result = run_hook(tool_payload("Edit", REPOSITORY / "docs" / "old.md",
                               old_string="Old", new_string="See issue #46 for it."))
context = context_of(result)
check("Edit with a bare reference in new_string gets a note with an excerpt",
      context is not None and '"issue #46" in "See issue #46 for it."'
      in context["additionalContext"], result.stdout)

result = run_hook(tool_payload("Edit", REPOSITORY / "docs" / "old.md", old_string="Old",
                               new_string="See [issue 46](https://x.y/issues/46)."))
check("Edit with no bare reference is silent",
      result.returncode == 0 and result.stdout == "", result.stdout)

result = run_hook(tool_payload("Write", REPOSITORY / "notes.txt", content="PR 931\n"))
check("a file that is not Markdown is not scanned", result.stdout == "", result.stdout)

(REPOSITORY / "ignored").mkdir()
result = run_hook(tool_payload("Write", REPOSITORY / "ignored" / "x.md", content="PR 931\n"))
check("a Markdown file git ignores is not scanned", result.stdout == "", result.stdout)

result = run_hook(tool_payload("Write", SCRATCH / "outside.md", content="PR 931\n"))
check("a Markdown file outside the session's checkout is not scanned",
      result.stdout == "", result.stdout)

result = run_hook(tool_payload("Read", REPOSITORY / "docs" / "old.md"))
check("a tool other than Edit or Write is ignored", result.stdout == "", result.stdout)


# --- Stop -------------------------------------------------------------------

def transcript(*records):
    path = SCRATCH / f"transcript-{len(list(SCRATCH.glob('transcript-*')))}.jsonl"
    with open(path, "w", encoding="utf-8") as handle:
        for record in records:
            handle.write((record if isinstance(record, str) else json.dumps(record)) + "\n")
    return path


def user(text):
    return {"type": "user", "message": {"role": "user", "content": text}}


def assistant(message_id, *blocks):
    return {"type": "assistant", "message": {"id": message_id, "role": "assistant",
                                             "content": list(blocks)}}


def text_block(text):
    return {"type": "text", "text": text}


def stop_payload(path, **extra):
    return {"hook_event_name": "Stop", "transcript_path": str(path),
            "session_id": "s", "stop_hook_active": False, **extra}


path = transcript(user("status?"),
                  assistant("m1", text_block("Working.")),
                  assistant("m2", {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}}),
                  "not json at all",
                  assistant("m3", text_block("Done: PR 931 merged, `PR 5` is code.")))
result = run_hook(stop_payload(path))
context = context_of(result)
check("Stop: a bare reference in the last message gets a Stop note",
      result.returncode == 0 and context is not None and context["hookEventName"] == "Stop"
      and '"PR 931"' in context["additionalContext"]
      and "cites 1 pull request(s)" in context["additionalContext"], result.stdout)

path = transcript(user("first"), assistant("m1", text_block("See PR 12.")),
                  user("second"), assistant("m2", text_block("All clear.")))
result = run_hook(stop_payload(path))
check("Stop: a bare reference only in an earlier turn is silent",
      result.returncode == 0 and result.stdout == "", result.stdout)

path = transcript(user("go"), assistant("m1", text_block("See GHI 7.")),
                  assistant("m2", text_block("Finished, no numbers.")))
result = run_hook(stop_payload(path))
check("Stop: only the last message with text is scanned",
      result.stdout == "", result.stdout)

path = transcript(user("go"), assistant("m1", text_block("See PR 12.")))
result = run_hook(stop_payload(path, stop_hook_active=True))
check("Stop: silent when stop_hook_active is set", result.stdout == "", result.stdout)

headless = dict(HOOK_ENVIRONMENT, CLAUDE_CODE_SESSION_ATTENDED="0")
result = run_hook(stop_payload(path), headless)
check("Stop: silent in a headless claude -p child", result.stdout == "", result.stdout)
owned = dict(HOOK_ENVIRONMENT, NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER="1")
result = run_hook(stop_payload(path), owned)
check("Stop: silent when a caller owns the session", result.stdout == "", result.stdout)

result = run_hook(stop_payload(SCRATCH / "no-such-transcript.jsonl"))
check("Stop: a missing transcript fails open, silent, exit 0",
      result.returncode == 0 and result.stdout == "" and result.stderr == "",
      (result.returncode, result.stdout, result.stderr))


# --- Fail open on bad input ---------------------------------------------------

for name, stdin in (("not JSON", "{oops"), ("a JSON list", "[1, 2]"), ("empty stdin", ""),
                    ("an unknown event", json.dumps({"hook_event_name": "Other"})),
                    ("tool_input not an object",
                     json.dumps({"hook_event_name": "PostToolUse", "tool_name": "Write",
                                 "tool_input": "x", "cwd": str(REPOSITORY)})),
                    ("no cwd", json.dumps({"hook_event_name": "PostToolUse",
                                           "tool_name": "Write",
                                           "tool_input": {"file_path": "a.md",
                                                          "content": "PR 1"}})),
                    ("a transcript_path that is not a string",
                     json.dumps({"hook_event_name": "Stop", "transcript_path": 5}))):
    result = run_hook(stdin)
    check(f"bad input fails open, silent, exit 0: {name}",
          result.returncode == 0 and result.stdout == "" and result.stderr == "",
          (result.returncode, result.stdout, result.stderr))

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
