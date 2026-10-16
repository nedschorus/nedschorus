#!/usr/bin/env python3
"""Fail when a Stop or SubagentStop hook registered in .claude/settings.json
does not obey, before anything else, the shared rule that Stop hooks stay
silent while the agent answers a Stop hook.

The rule and its reason are in
nc-systems/general-tools/claude-code-stop-hooks-stay-silent-while-agent-answers-a-stop-hook-rule-common.py:
a Stop hook says nothing at a Stop that ends the agent's answer to a Stop
hook's output, or the agent keeps answering hooks instead of stopping.

Each registered Stop or SubagentStop hook is checked two ways:
  - its source calls stop_hook_stays_silent_while_agent_answers_a_stop_hook, or
    stop_hook_output_may_be_printed_while_agent_answers_a_stop_hook for a hook
    under the rule's one exemption, a notice for the user;
  - run with stop_hook_active true, from an empty directory and with HOME set
    to an empty directory, it exits 0, prints nothing on stderr and nothing on
    stdout but a notice-only output, and writes nothing under HOME, which
    catches a hook that cannot load the rule's module.
That run has nothing for most hooks to speak about, so it cannot show that
the rule's check comes before the hook's work; each hook's own test does that, with
a case where the hook would speak but for stop_hook_active.
A registered Stop or SubagentStop command that names no Python file fails,
because this test cannot read it.
A hook whose source lacks the call is not run, because a hook that skips the
rule's check may act on the checkout it is started in.
"""
import ast
import importlib.util
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
EXEMPTION_FUNCTION = "stop_hook_output_may_be_printed_while_agent_answers_a_stop_hook"
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
UNCHECKABLE_MESSAGE = (
    "{event} hook command {command!r} in .claude/settings.json names no Python file, so "
    "this test cannot check that the hook obeys the rule in {module}.\n"
    "Why: every Stop hook must stay silent while the agent answers a Stop hook, or the "
    "agent keeps answering hooks instead of stopping; a hook this test cannot read could "
    "break that rule unseen.\n"
    "Fix: write the hook in Python and have it call {function} first, as the other Stop "
    "hooks do.\n"
    "If the hook must be another kind of program, teach this test to check that kind.")
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
    """([(event, hook path relative to the repository)], [(event, command)]) for every
    Stop and SubagentStop hook: the Python hooks this test checks, and the commands
    that name no Python file, which it cannot check."""
    hooks, unchecked = [], []
    for event in STOP_EVENTS:
        for matcher in settings.get("hooks", {}).get(event, []):
            for hook in matcher.get("hooks", []):
                command = hook.get("command", "")
                paths = []
                for word in command.split():
                    word = word.replace('"$CLAUDE_PROJECT_DIR"/', "").replace(
                        "$CLAUDE_PROJECT_DIR/", "").strip("\"'")
                    if word.endswith(".py"):
                        paths.append(word)
                if not paths:
                    unchecked.append((event, command))
                for path in paths:
                    if (event, path) not in hooks:
                        hooks.append((event, path))
    return hooks, unchecked


def source_calls_rule_function(source):
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            called = node.func
            name = (called.attr if isinstance(called, ast.Attribute)
                    else called.id if isinstance(called, ast.Name) else None)
            if name in (RULE_FUNCTION, EXEMPTION_FUNCTION):
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


def load_rule_module():
    spec = importlib.util.spec_from_file_location("stop_hooks_stay_silent_rule", REPOSITORY / RULE_MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rule_module = load_rule_module()


def check_exemption():
    notice = json.dumps({"systemMessage": "Item 3 of 9: the point"})
    answering = {"stop_hook_active": True}
    not_answering = {"stop_hook_active": False}
    check("a systemMessage-only output is a notice", rule_module.stop_hook_output_only_shows_the_user_a_notice(notice))
    for name, output in [
            ("a block", json.dumps({"decision": "block", "reason": "fix it"})),
            ("a notice beside a block", json.dumps({"systemMessage": "x", "decision": "block", "reason": "y"})),
            ("additionalContext", json.dumps({"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": "x"}})),
            ("an empty systemMessage", json.dumps({"systemMessage": "  "})),
            ("a systemMessage that is not text", json.dumps({"systemMessage": 3})),
            ("text that is not JSON", "Item 3 of 9"),
            ("a JSON list", json.dumps(["systemMessage"]))]:
        check(f"{name} is not a notice", not rule_module.stop_hook_output_only_shows_the_user_a_notice(output))
    check("a notice may be printed while the agent answers a Stop hook",
          rule_module.stop_hook_output_may_be_printed_while_agent_answers_a_stop_hook(answering, notice))
    block_output = json.dumps({"decision": "block", "reason": "fix it"})
    check("a block may not be printed while the agent answers a Stop hook",
          not rule_module.stop_hook_output_may_be_printed_while_agent_answers_a_stop_hook(answering, block_output))
    check("a block may be printed when the agent is not answering a Stop hook",
          rule_module.stop_hook_output_may_be_printed_while_agent_answers_a_stop_hook(not_answering, block_output))
    check("no output is never printed",
          not rule_module.stop_hook_output_may_be_printed_while_agent_answers_a_stop_hook(not_answering, None))


def main():
    rule_module_source = (REPOSITORY / RULE_MODULE).read_text(encoding="utf-8")
    check("the rule module defines the rule function",
          f"def {RULE_FUNCTION}(" in rule_module_source,
          f"{RULE_MODULE} no longer defines {RULE_FUNCTION}")
    check_exemption()
    check("the source check finds a call of the exemption function",
          source_calls_rule_function(f"if not rule.{EXEMPTION_FUNCTION}(payload, output):\n    pass\n"))

    check("the source check finds no call in a hook without one",
          not source_calls_rule_function("import json\nprint(json.dumps({'decision': 'block'}))\n"))
    check("the source check finds a call through the loaded module",
          source_calls_rule_function(f"if stop_hooks_stay_silent_rule.{RULE_FUNCTION}(payload):\n    pass\n"))

    sample_hooks, sample_unchecked = registered_stop_hooks({"hooks": {"Stop": [{"hooks": [
        {"type": "command", "command": 'python3 "$CLAUDE_PROJECT_DIR"/scripts/a-hook.py'},
        {"type": "command", "command": "bash scripts/a-hook.sh"}]}]}})
    check("the settings reader returns a Python hook to check and a hook it cannot check",
          sample_hooks == [("Stop", "scripts/a-hook.py")]
          and sample_unchecked == [("Stop", "bash scripts/a-hook.sh")],
          (sample_hooks, sample_unchecked))

    hooks, unchecked = registered_stop_hooks(json.loads(SETTINGS.read_text(encoding="utf-8")))
    for event, command in unchecked:
        check(f"{event} hook {command!r} can be checked", False,
              UNCHECKABLE_MESSAGE.format(event=event, command=command, module=RULE_MODULE,
                                         function=RULE_FUNCTION))
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
        if stdout.strip() and not rule_module.stop_hook_output_only_shows_the_user_a_notice(stdout):
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
