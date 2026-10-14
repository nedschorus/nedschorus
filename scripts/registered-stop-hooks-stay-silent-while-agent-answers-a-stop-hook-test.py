#!/usr/bin/env python3
"""Fail when a Stop or SubagentStop hook registered in .claude/settings.json
does not obey, before anything else, the shared rule that Stop hooks stay
silent while the agent answers a Stop hook.

The rule and its reason are in
nc-systems/general-tools/claude-code-stop-hooks-stay-silent-while-agent-answers-a-stop-hook-rule-common.py:
a Stop hook says nothing at a Stop that ends the agent's answer to a Stop
hook's output, or the agent keeps answering hooks instead of stopping.

Each registered Stop or SubagentStop hook is checked two ways:
  - its source calls stop_hook_stays_silent_while_agent_answers_a_stop_hook;
  - run with stop_hook_active true, from an empty directory and with HOME set
    to an empty directory, it exits 0, prints nothing on stdout or stderr, and
    writes nothing under HOME, which catches a hook that cannot load the rule's module.
That run has nothing for most hooks to speak about, so it cannot show that
the rule's check comes before the hook's work; each hook's own test does that, with
a case where the hook would speak but for stop_hook_active.
A hook whose source lacks the call is not run, because a hook that skips the
rule's check may act on the checkout it is started in.
"""
import ast
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parent.parent
SETTINGS = REPOSITORY / ".claude" / "settings.json"
RULE_MODULE = ("nc-systems/general-tools/"
                "claude-code-stop-hooks-stay-silent-while-agent-answers-a-stop-hook-rule-common.py")
RULE_FUNCTION = "stop_hook_stays_silent_while_agent_answers_a_stop_hook"
STOP_EVENTS = ("Stop", "SubagentStop")
HOOK_RUN_TIMEOUT_SECONDS = 60

MISSING_CALL_MESSAGE = (
    "{hook} is registered as a {event} hook and does not call {function}.\n"
    "Why: when any Stop hook speaks, the agent must answer it, and every Stop hook runs "
    "again at the end of that answer. A hook that speaks then keeps the agent answering "
    "hooks instead of stopping. The rule and its reasons are in {module}.\n"
    "Fix: in {hook}, load {module} by file path, as scripts/checkout-freshness-catch-up.py "
    "does, and make this the hook's first act on its payload, before it reads files, writes "
    "state or prints:\n"
    "    if stop_hooks_stay_silent_rule.{function}(payload):\n"
    "        exit 0, printing nothing")
SPOKE_MESSAGE = (
    "{hook}, run as a {event} hook with stop_hook_active true, {what}.\n"
    "Why: stop_hook_active true means this Stop ends the agent's answer to a Stop hook; "
    "a hook that acts or speaks here keeps the agent answering hooks instead of stopping. "
    "The rule and its reasons are in {module}.\n"
    "Fix: in {hook}, move the call of {function} to the hook's first act on its payload, "
    "and when it returns True exit 0 without printing or writing anything. If the hook "
    "failed to load {module}, check the path it loads it from.")

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def registered_stop_hooks(settings):
    """[(event, hook path relative to the repository)] for every Stop and SubagentStop hook."""
    hooks = []
    for event in STOP_EVENTS:
        for matcher in settings.get("hooks", {}).get(event, []):
            for hook in matcher.get("hooks", []):
                for word in hook.get("command", "").split():
                    word = word.replace('"$CLAUDE_PROJECT_DIR"/', "").replace(
                        "$CLAUDE_PROJECT_DIR/", "").strip("\"'")
                    if word.endswith(".py") and (event, word) not in hooks:
                        hooks.append((event, word))
    return hooks


def source_calls_rule_function(source):
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            called = node.func
            name = (called.attr if isinstance(called, ast.Attribute)
                    else called.id if isinstance(called, ast.Name) else None)
            if name == RULE_FUNCTION:
                return True
    return False


def run_hook_while_agent_answers(hook_path, event):
    """(exit code, stdout, stderr, files written under HOME) for one run."""
    with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as cwd:
        payload = {"hook_event_name": event, "stop_hook_active": True,
                   "session_id": "stop-hooks-stay-silent-while-agent-answers-a-stop-hook-test", "cwd": cwd,
                   "transcript_path": str(Path(cwd) / "no-transcript.jsonl"),
                   "agent_transcript_path": str(Path(cwd) / "no-transcript.jsonl"),
                   "last_assistant_message": "The file is missing."}
        environment = dict(os.environ, HOME=home, CLAUDE_PROJECT_DIR=str(REPOSITORY))
        completed = subprocess.run(
            [sys.executable, str(REPOSITORY / hook_path)], input=json.dumps(payload),
            capture_output=True, text=True, cwd=cwd, env=environment,
            timeout=HOOK_RUN_TIMEOUT_SECONDS)
        written = [str(path.relative_to(home)) for path in Path(home).rglob("*")]
        return completed.returncode, completed.stdout, completed.stderr, written


def main():
    rule_module_source = (REPOSITORY / RULE_MODULE).read_text(encoding="utf-8")
    check("the rule module defines the rule function",
          f"def {RULE_FUNCTION}(" in rule_module_source,
          f"{RULE_MODULE} no longer defines {RULE_FUNCTION}")

    check("the source check finds no call in a hook without one",
          not source_calls_rule_function("import json\nprint(json.dumps({'decision': 'block'}))\n"))
    check("the source check finds a call through the loaded module",
          source_calls_rule_function(f"if stop_hooks_stay_silent_rule.{RULE_FUNCTION}(payload):\n    pass\n"))

    hooks = registered_stop_hooks(json.loads(SETTINGS.read_text(encoding="utf-8")))
    check("settings.json registers at least one Stop hook", bool(hooks),
          f"{SETTINGS} registers no Stop or SubagentStop hook this test can read")
    for event, hook_path in hooks:
        source = (REPOSITORY / hook_path).read_text(encoding="utf-8")
        calls = source_calls_rule_function(source)
        check(f"{event} {hook_path} calls the rule function", calls,
              MISSING_CALL_MESSAGE.format(hook=hook_path, event=event, function=RULE_FUNCTION,
                                          module=RULE_MODULE))
        if not calls:
            continue
        returncode, stdout, stderr, written = run_hook_while_agent_answers(hook_path, event)
        problems = []
        if returncode != 0:
            problems.append(f"exited {returncode}")
        if stdout.strip():
            problems.append(f"printed on stdout: {stdout.strip()[:200]}")
        if stderr.strip():
            problems.append(f"printed on stderr: {stderr.strip()[:200]}")
        if written:
            problems.append(f"wrote under HOME: {', '.join(written[:5])}")
        check(f"{event} {hook_path} stays silent while the agent answers a Stop hook",
              not problems,
              SPOKE_MESSAGE.format(hook=hook_path, event=event, what="; ".join(problems),
                                   function=RULE_FUNCTION, module=RULE_MODULE))

    total = len(failures)
    print(f"\n{'FAILED' if total else 'PASSED'}: {total} failure(s)")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
