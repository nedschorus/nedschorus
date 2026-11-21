#!/usr/bin/env python3
"""Find, in an agent's text, a claim about the current state of something
outside the text that may have changed since the agent last looked: that an
agent-seat or agent-session is offline, that `claude` is logged out or logged
in to some account, that a machine or share is down, unreachable or not
mounted, that a job or service has stopped or is not running, or that work is
still waiting or on hold for something.

Two programs share this list, so a phrase added here reaches both:
scripts/agent-reply-possibly-stale-system-status-claim-recheck-reminder-hook.py, a Stop hook that reads
the agent's last reply, and the approval-walk-waiting-item-cold-read-fast-read
step of
nn-systems/skills/walk-me-through/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py,
which reads an approval-walk item before it is shown. Load it by file path.

The list is narrow on purpose: a false match costs the agent's attention, so
precision matters more than recall. Each pattern was chosen from the wording of
claims the user corrected; what agents say while they work, such as "the tests
are still running" or "I wrote the report to X", matches none. A claim about a
pull request, a GHI or an account's name, and a claim that something IS
running, are left out, because their wording is shared by too much ordinary
progress talk.

Text an agent quotes rather than asserts is skipped, as
scripts/absence-claim-locator-reminder-hook.py's strip_noise() skips it: code,
block quotes and double-quoted text. A match in a sentence that is conditional
before the match, as in "if ned-box is down", or that waits on the reader, as
in "still waiting for your answer", is not a claim. The module, and the modules it loads, use the
standard library alone, so a Stop hook that loads it starts fast.
"""
import importlib.util
import re
from pathlib import Path

_absence_claim_hook_specification = importlib.util.spec_from_file_location(
    "absence_claim_locator_reminder_hook",
    Path(__file__).resolve().parents[2] / "scripts" / "absence-claim-locator-reminder-hook.py")
_absence_claim_hook = importlib.util.module_from_spec(_absence_claim_hook_specification)
_absence_claim_hook_specification.loader.exec_module(_absence_claim_hook)

# Keyed by what each pattern finds; a key is what a program prints beside the matched phrase.
SYSTEM_STATUS_CLAIM_PATTERNS = {
    "offline": r"(?<![\w-])offline(?![\w-])|\bnot\s+(?:yet\s+)?(?:back\s+)?online\b",
    # "once it's back online" and "when it comes back up" say it is offline now, whatever the conditional.
    "back online": r"\b(?:comes?|came|is|are|'s|'re|gets?)\s+back\s+online\b|\b(?:is|are|'s|'re)\s+back\s+up\b",
    "logged out": r"\b(?:logged|signed)[ -]out\b|\bnot\s+logged\s+in\b",
    "logged in to an account": r"\b(?:logged|signed)\s+(?:back\s+)?in\s+(?:again\s+)?(?:to|as|with|on)\s+(?:[\w@.+-]+\s+){0,3}accounts?\b",
    # "down to 3" and "write down" are not a machine down: an auxiliary or "still" comes first, and no "to" after.
    "down": r"\b(?:is|are|was|were|went|goes|still|'s|'re)\s+(?:still\s+|now\s+|currently\s+)?down\b(?!\s*(?:to|from|by|for|in|the|a|an)\b|-)",
    # "can't reach" is left out: agents use it for what a program or a machine can reach at all, not for a fault now.
    "unreachable": r"\bunreachable\b|\bnot\s+reachable\b|\b(?:could\s+not|couldn't)\s+reach\b|\b(?:cannot|can't|could\s+not|couldn't)\s+be\s+reached\b|\bnot\s+mounted\b|\b(?:won't|will\s+not|does\s+not|doesn't)\s+mount\b",
    "not running": r"\b(?:is\s+not|isn't|are\s+not|aren't|was\s+not|wasn't|were\s+not|weren't|no\s+longer)\s+(?:currently\s+|still\s+)?running\b(?!\s+(?:the|a|an|any|its|their|this|that|these|those)\b)",
    "none running": r"\b(?:no|none\s+of\s+(?:its|the|their|his|our|my))\s+(?:[\w-]+\s+){0,3}(?:sessions?|agent-sessions?|agent-seats?|seats?|agents?|process(?:es)?|jobs?|workers?)\s+(?:is|are)\s+(?:live|running|alive|up|online)\b",
    "stopped": r"\bstopped\s+(?:updating|running|working|responding)\b|\b(?:jobs?|services?|timers?|daemons?|crontab|cron|agent-seats?|agent-sessions?)\s+(?:[\w-]+\s+){0,4}(?:is|are|was|were|has|have)\s+(?:been\s+)?(?:all\s+)?(?:gone|stopped|dead|disabled)\b",
    "still broken": r"\bstill\s+broken\b",
    "still waiting": r"\bstill\s+(?:waiting|waits|held|blocked|pending|on\s+hold)\b|\bon\s+hold\b|\bheld\s+until\b",
}
COMPILED_SYSTEM_STATUS_CLAIM_PATTERNS = {name: re.compile(pattern, re.I)
                                         for name, pattern in SYSTEM_STATUS_CLAIM_PATTERNS.items()}
# Patterns that state the current state even inside a conditional: "once it comes back online" says it is offline.
PATTERNS_CLAIMING_UNDER_A_CONDITIONAL = ("back online",)
CONDITIONAL_BEFORE_MATCH = re.compile(
    r"\b(?:if|unless|when|whenever|while|would|should|could|might|may|once|until|whether|in\s+case|suppose|assume)\b", re.I)
# The reader is what is waited for: an open approval-walk says so in every message, and the user knows it.
WAITS_ON_THE_READER = re.compile(r"^\s*(?:on|for|until)\s+(?:you\b|you've\b|your\b|the\s+user(?:'s)?\b|his\b|him\b|he\b)", re.I)
# Work said to wait, as in "tasks #743 and #748 are still waiting on cold-read-research": an approval-walk, a subagent
# or a pull request said to wait is progress the agent follows itself, and matches too often to be worth a reminder.
WAITING_WORK = re.compile(r"\b(?:tasks?|work|messages?|promise)\b", re.I)
# "the worktrees of any agent-seat whose handoff-supervisor is not running" names a kind, not a status.
KIND_NAMED_BY_WHOSE = re.compile(r"\bwhose\b[^,;:.]{0,60}$", re.I)
SENTENCE = re.compile(r".+?(?:[.!?](?=\s|$)|$)")


def possibly_stale_system_status_claim_phrases_find(text):
    """Return a list of (pattern name, matched phrase), one per claim in text about the current status of a system, in text order."""
    found = []
    for unit in re.finditer(r"[^\n]+", _absence_claim_hook.strip_noise(text)):
        for sentence_match in SENTENCE.finditer(unit.group()):
            sentence = sentence_match.group()
            for name, pattern in COMPILED_SYSTEM_STATUS_CLAIM_PATTERNS.items():
                for match in pattern.finditer(sentence):
                    before, after = sentence[:match.start()], sentence[match.end():]
                    if name not in PATTERNS_CLAIMING_UNDER_A_CONDITIONAL and CONDITIONAL_BEFORE_MATCH.search(before):
                        continue
                    if KIND_NAMED_BY_WHOSE.search(before):
                        continue
                    if name == "still waiting" and (WAITS_ON_THE_READER.match(after) or not WAITING_WORK.search(before)):
                        continue
                    found.append((match.start() + sentence_match.start() + unit.start(), name, match.group()))
    return [(name, phrase) for _, name, phrase in sorted(found)]
