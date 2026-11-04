#!/usr/bin/env python3
"""Test advisor settings and repository headless Claude command builders.

Run with python3; prints PASS/FAIL lines and exits nonzero on failure.
"""

import ast
import copy
import importlib.util
import json
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
MODULE_FILE = "claude-headless-run-settings-with-advisor-turned-off-common.py"
PROGRAMS = [
    "nc-systems/cold-read/cold-read-claude-cell.py",
    "nc-systems/skills/walk-me-through/walk-me-through-agent-question-to-user-outside-approval-walk-items-refusal-stop-hook.py",
    "scripts/ghi-guide-agent-ask.py",
    "scripts/merge-lane-pull-request-claude-reviewer-headless-run-and-review-post.py",
    "scripts/sanity-check-adversarial-prompts.py",
    "nc-systems/handoff/uncommitted-work-snapshot-hook-real-claude-session-weekly-owner-check.py",
]
failures = 0


def check(name, condition, detail=None):
    global failures
    if condition:
        print(f"PASS  {name}")
    else:
        failures += 1
        print(f"FAIL  {name}: {detail!r}")


def load(relative):
    path = REPOSITORY_ROOT / relative
    name = path.stem.replace("-", "_")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


settings = load("nc-systems/general-tools/" + MODULE_FILE)
build = settings.claude_headless_run_settings_json_with_advisor_turned_off
check("default settings contain only the disabled advisor", json.loads(build()) == {"advisorModel": ""})
own = {"advisorModel": "fable", "disableAllHooks": True, "permissions": {"deny": ["Read(secret)"]}}
before = copy.deepcopy(own)
result = build(own)
check("settings are JSON text", isinstance(result, str))
check("own settings survive and advisor override wins", json.loads(result) == {**own, "advisorModel": ""})
check("own settings are not mutated", own == before)

git_environment = load("nc-systems/general-tools/git-redirecting-environment-variables-removal-common.py")
tracked = subprocess.run(["git", "ls-files", "-z"], cwd=REPOSITORY_ROOT,
                         check=True, capture_output=True, text=True,
                         env=git_environment.environment_without_git_redirecting_variables()).stdout.split("\0")
programs = {relative: (REPOSITORY_ROOT / relative).read_text() for relative in tracked
            if relative.endswith(".py") and not relative.endswith("-test.py")
            and "tests" not in Path(relative).parts and Path(relative).name != MODULE_FILE}
# A program may take its settings from another program that loads the module, as overview-write
# takes cold-read-claude-cell.py's SETTINGS.
loaders = {Path(relative).name for relative, source in programs.items() if MODULE_FILE in source}
found = set()
for relative, source in programs.items():
    for node in ast.walk(ast.parse(source, filename=relative)):
        if not isinstance(node, (ast.List, ast.Tuple)) or len(node.elts) < 2:
            continue
        first, second = node.elts[:2]
        claude = ((isinstance(first, ast.Constant) and first.value == "claude")
                  or (isinstance(first, ast.Name) and "claude" in first.id))
        if not (claude and isinstance(second, ast.Constant) and second.value in ("-p", "--print")):
            continue
        found.add(relative)
        detail = ("build that command's --settings with "
                  "claude_headless_run_settings_json_with_advisor_turned_off from " + MODULE_FILE)
        check(f"{relative}:{node.lineno} uses shared advisor settings",
              any(isinstance(element, ast.Constant) and element.value == "--settings"
                  for element in node.elts)
              and any(name in source for name in loaders | {MODULE_FILE}), detail)
check("scan finds all six required programs", set(PROGRAMS) <= found, sorted(found))


def argv_settings(name, argv, expected=None, settings_file=False):
    check(name + " has exactly one --settings", argv.count("--settings") == 1, argv)
    if argv.count("--settings") != 1:
        return
    value = argv[argv.index("--settings") + 1]
    parsed = json.loads(Path(value).read_text() if settings_file else value)
    check(name + " disables advisor", parsed.get("advisorModel") == "", parsed)
    if expected:
        check(name + " preserves own settings", expected(parsed), parsed)


cold, refusal, guide, reviewer, sanity, weekly = map(load, PROGRAMS)
argv, prompt = cold.invocation_builder("low")("some-model", "prompt")
own_hooks = lambda value: value.get("disableAllHooks") is True
cold_settings = lambda value: own_hooks(value) and bool(value.get("permissions", {}).get("deny"))
argv_settings("cold-read", argv, cold_settings)
argv = shlex.split(reviewer.resume_command("a-session-id"))
argv_settings("reviewer resume", argv)
check("reviewer resume keeps session id", argv[argv.index("--resume") + 1] == "a-session-id", argv)

captured = []


def fake_run(argv, *args, **kwargs):
    captured.append(list(argv))
    return subprocess.CompletedProcess(argv, 1, "", "")


class FakeProcess:
    pid = 123
    returncode = 0

    def __init__(self, argv, *args, **kwargs):
        captured.append(list(argv))

    def communicate(self, *args, **kwargs):
        return "", ""

    def wait(self, *args, **kwargs):
        return 0


saved_popen, saved_killpg = reviewer.subprocess.Popen, reviewer.os.killpg
try:
    reviewer.subprocess.Popen = FakeProcess
    reviewer.os.killpg = lambda *args: None
    reviewer.run_reviewer("{}", "prompt", REPOSITORY_ROOT, {}, 1)
finally:
    reviewer.subprocess.Popen, reviewer.os.killpg = saved_popen, saved_killpg
argv_settings("reviewer launch", captured.pop())

saved_run = refusal.subprocess.run
try:
    refusal.subprocess.run = fake_run
    refusal.model_judgement(["question"], ["question"], 1, "1", "item")
    argv_settings("refusal hook", captured.pop(), own_hooks)
    for session_id in (None, "a-session-id"):
        guide.run_claude("prompt", session_id, REPOSITORY_ROOT, 1)
        argv = captured.pop()
        argv_settings(f"guide {session_id}", argv)
        check(f"guide {session_id} keeps user settings source",
              argv[argv.index("--setting-sources") + 1] == "user", argv)
        if session_id:
            check("guide resume keeps session id", argv[argv.index("--resume") + 1] == session_id, argv)
finally:
    refusal.subprocess.run = saved_run

saved_launch = sanity.run_agent_binary_unless_run_stopped
try:
    def fake_review(argv, *args, **kwargs):
        captured.append(list(argv))
        return subprocess.CompletedProcess(argv, 0, "a review\n", "")
    sanity.run_agent_binary_unless_run_stopped = fake_review
    sanity.run_claude("prompt")
finally:
    sanity.run_agent_binary_unless_run_stopped = saved_launch
argv = captured.pop()
argv_settings("sanity review", argv)
check("sanity keeps user settings source", argv[argv.index("--setting-sources") + 1] == "user", argv)

overview = load("nc-systems/skills/overview-write/overview-write-architecture-overview-claim-check-by-fresh-agent.py")
saved_run = overview.subprocess.run
try:
    overview.subprocess.run = fake_review
    overview.run_fresh_agent(REPOSITORY_ROOT, "prompt")
finally:
    overview.subprocess.run = saved_run
argv_settings("overview fresh agent", captured.pop(), cold_settings)

with tempfile.TemporaryDirectory() as directory:
    clone = Path("/some/clone")
    settings_path = Path(directory) / "settings.json"
    settings_path.write_text(weekly.hook_settings_json(clone))
    parsed = json.loads(settings_path.read_text())
    check("weekly settings keep PostToolUse hook",
          bool(parsed.get("hooks", {}).get("PostToolUse")), parsed)
    saved_popen = weekly.subprocess.Popen
    try:
        weekly.subprocess.Popen = FakeProcess
        weekly.start_claude("claude", clone, settings_path)
    finally:
        weekly.subprocess.Popen = saved_popen
    argv = captured.pop()
    argv_settings("weekly launch", argv, settings_file=True)
    check("weekly launch uses settings file", argv[argv.index("--settings") + 1] == str(settings_path), argv)

print(f"{failures} case(s) failed" if failures else "all cases passed")
sys.exit(bool(failures))
