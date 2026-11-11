#!/usr/bin/env python3
"""Change the lines of a proposed-improvements-or-changes-file that the
handler of GHI 1132 may change, and refuse the changes rules 4 and 5 of that
GHI-MD's § The design forbid.

The handler is the forked subagent that settles a file's entries by
docs/agents/queue/proposed-improvements-or-changes-file-reviewer-entries-settling-subagent-instructions.md.
It changes the file only through this program, which
touches nothing but an entry's State line, its Try lines and its
"Second agent:" lines, so an entry's own text is never rewritten.

Subcommands, each on one file:

  show            every entry: its id, its State line, the tries counted
                  since its last user-ruling line, and its last verdict.
  try             adds one "Try <n> — <by>, <time>: <found>" line under each
                  entry named, the same line under each for related entries.
                  Refused for a settled entry, and for an entry that already
                  has MAXIMUM_TRIES tries since its last user-ruling line.
  second-agent-input
                  prints what the handler gives the second agent:
                  SECOND_AGENT_PROMPT, the entry's text without its State,
                  Try and "Second agent:" lines, which carry the handler's
                  conclusion, and the sources the handler names.
  second-agent-verdict
                  adds "Second agent: agrees (or disagrees) that it is not
                  worth doing, <who>, <time>". One verdict per try: refused
                  when no Try line follows the entry's last verdict, so a
                  disagreement spends the try it answers, and asking again
                  takes a new try.
  settle          rewrites the State line as "settled, <how settled> — <by>,
                  <time>: <how>". "not worth doing" is refused unless the
                  entry's last verdict is an agreement and no Try line
                  follows it.
  needs-the-user  rewrites the State line as "needs the user — <by>, <time>:
                  <why>"; `--because three-tries` is refused unless the
                  entry has MAXIMUM_TRIES tries since its last user-ruling
                  line.

Lines are recognised by how they open, as handlers have written them:
"State:", "Try" followed by a space or a colon, "Second agent:", and
"User-ruling" for the line recording the user's decision on the entry, from
which rule 4 counts tries again. An entry runs from its "## E<n>" heading to
the next heading of level one or two. New lines go after the entry's last line that is not blank.

The file is named by its path on this machine, or in the form
nedlern@ned-box:<path> that scripts/ghi-issue-write.py prints for a file in
the log-store; that form is read as a local path on ned-box and refused
elsewhere with the ssh command to run instead.

Does not handle: two handlers changing one file at the same time (GHI 1132's
open question 2): the file is read, changed and replaced whole, so the later
writer's replacement drops the earlier writer's lines. A file beside an
architecture overview is changed in the checkout named, and the handler
commits it.

Failures: a refused change, a missing file or entry, or a file that cannot be
read or written is printed to stderr with what to do, and the program exits 1
without changing the file. Exit 0: done.
"""

import argparse
import datetime
import os
import re
import socket
import sys
import tempfile
from pathlib import Path

SECOND_AGENT_PROMPT = "docs/agents/queue/proposed-improvements-or-changes-file-entry-not-worth-doing-second-agent-prompt.md"
MAXIMUM_TRIES = 3

ENTRY_HEADING_PATTERN = re.compile(r"^## (E\d+)\b")
# Only a heading of level one or two ends an entry: an entry's body may hold a
# hashtag line or a lower heading.
ENTRY_ENDING_HEADING_PATTERN = re.compile(r"^#{1,2} ")
STATE_LINE_OPENING = "State:"
TRY_LINE_PATTERN = re.compile(r"^Try[ :]")
SECOND_AGENT_LINE_OPENING = "Second agent:"
SECOND_AGENT_AGREES_OPENING = "Second agent: agrees"
USER_RULING_LINE_OPENING = "User-ruling"
SETTLED_STATE_OPENING = "State: settled"

LOG_STORE_HOST = "nedlern@ned-box"
LOG_STORE_HOSTNAME = "ned-box"

SETTLED_KINDS = {
    "not-worth-doing": "not worth doing",
    "done": "done",
    "new-ghi": "new GHI filed",
}
NEEDS_THE_USER_REASONS = {
    "cold-read-document": "the change would alter a document the cold-read skill sends to a cold-read-full-run, in a way its step 9 sends to the user",
    "user-ruling-change": "a question whether a user-ruling should change",
    "three-tries": "still open after 3 tries",
}


class Refused(Exception):
    pass


def now() -> str:
    """The time a line carries. A function so a test can fix it."""
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def local_path(named: str) -> Path:
    if named.startswith(LOG_STORE_HOST + ":"):
        if socket.gethostname().split(".")[0] != LOG_STORE_HOSTNAME:
            raise Refused(
                f"{named} is in the log-store on ned-box, and this machine is not ned-box, so nothing was changed.\n"
                "Run the same command on ned-box, from ned-box's clone:\n"
                f"ssh {LOG_STORE_HOST} 'cd ~/Projects/nedschorus && python3 scripts/proposed-improvements-or-changes-file-entry-state-try-and-second-agent-verdict-lines-write.py <the same arguments>'")
        return Path(named[len(LOG_STORE_HOST) + 1:])
    return Path(named)


def entry_spans(lines):
    """{entry id: (index of its heading, index after its last line)}."""
    spans, current, start = {}, None, 0
    for index, line in enumerate(lines):
        if ENTRY_ENDING_HEADING_PATTERN.match(line):
            if current is not None:
                spans[current] = (start, index)
                current = None
            match = ENTRY_HEADING_PATTERN.match(line)
            if match:
                current, start = match.group(1), index
    if current is not None:
        spans[current] = (start, len(lines))
    return spans


def entry_lines(lines, spans, entry):
    if entry not in spans:
        raise Refused(f"The file has no entry {entry}; its entries are: {', '.join(spans) or 'none'}. Nothing was changed.")
    start, end = spans[entry]
    return lines[start:end]


def tries_since_user_ruling(block) -> int:
    count = 0
    for line in block:
        if line.startswith(USER_RULING_LINE_OPENING):
            count = 0
        elif TRY_LINE_PATTERN.match(line):
            count += 1
    return count


def last_index(block, test):
    found = -1
    for index, line in enumerate(block):
        if test(line):
            found = index
    return found


def last_verdict_answers_last_try(block):
    """(the last "Second agent:" line, or None, and whether it follows the last Try line)."""
    verdict = last_index(block, lambda line: line.startswith(SECOND_AGENT_LINE_OPENING))
    attempt = last_index(block, lambda line: bool(TRY_LINE_PATTERN.match(line)))
    if verdict < 0:
        return None, False
    return block[verdict], verdict > attempt


def state_line(block):
    for line in block:
        if line.startswith(STATE_LINE_OPENING):
            return line
    return None


def insertion_index(lines, spans, entry) -> int:
    start, end = spans[entry]
    while end > start + 1 and not lines[end - 1].strip():
        end -= 1
    return end


def replace_state(lines, spans, entry, new_state):
    start, end = spans[entry]
    for index in range(start, end):
        if lines[index].startswith(STATE_LINE_OPENING):
            lines[index] = new_state
            return
    lines.insert(insertion_index(lines, spans, entry), new_state)


def refuse_settled(block, entry):
    state = state_line(block)
    if state is not None and state.startswith(SETTLED_STATE_OPENING):
        raise Refused(f"Entry {entry} is already settled ({state}), so nothing was changed.")


def add_try(lines, entries, by, found):
    spans = entry_spans(lines)
    for entry in entries:
        block = entry_lines(lines, spans, entry)
        refuse_settled(block, entry)
        if tries_since_user_ruling(block) >= MAXIMUM_TRIES:
            raise Refused(
                f"Entry {entry} already has {MAXIMUM_TRIES} tries since the user last decided on it, so no try was recorded under any entry named.\n"
                "Rule 4 of GHI 1132 allows no more; the entry goes to the user:\n"
                f"run this program's needs-the-user subcommand on {entry} with --because three-tries.")
    for entry in sorted(entries, key=lambda name: spans[name][0], reverse=True):
        number = tries_since_user_ruling(entry_lines(lines, spans, entry)) + 1
        lines.insert(insertion_index(lines, spans, entry), f"Try {number} — {by}, {now()}: {found}")
    return lines


def second_agent_input(lines, entry, sources) -> str:
    spans = entry_spans(lines)
    block = entry_lines(lines, spans, entry)
    kept = [line for line in block
            if not line.startswith(STATE_LINE_OPENING)
            and not TRY_LINE_PATTERN.match(line)
            and not line.startswith(SECOND_AGENT_LINE_OPENING)]
    prompt = (Path(__file__).resolve().parent.parent / SECOND_AGENT_PROMPT).read_text(encoding="utf-8")
    listed = "\n".join(f"- {source}" for source in sources)
    return (f"{prompt.rstrip()}\n\n## The entry\n\n" + "\n".join(kept).strip()
            + f"\n\n## The sources the handler cites\n\n{listed}\n")


def add_verdict(lines, entry, agrees, who):
    spans = entry_spans(lines)
    block = entry_lines(lines, spans, entry)
    refuse_settled(block, entry)
    attempt = last_index(block, lambda line: bool(TRY_LINE_PATTERN.match(line)))
    verdict = last_index(block, lambda line: line.startswith(SECOND_AGENT_LINE_OPENING))
    if attempt < 0 or verdict > attempt:
        raise Refused(
            f"Entry {entry} has no Try line after its last verdict, so the verdict was not recorded.\n"
            "Each verdict answers one try: record the try that shows the entry is not worth doing with the try subcommand first,\n"
            "then start a new second agent on it.")
    word = "agrees" if agrees else "disagrees"
    lines.insert(insertion_index(lines, spans, entry),
                 f"Second agent: {word} that it is not worth doing, {who}, {now()}")
    return lines


def settle(lines, entry, kind, by, how):
    spans = entry_spans(lines)
    block = entry_lines(lines, spans, entry)
    refuse_settled(block, entry)
    if kind == "not-worth-doing":
        verdict, answers = last_verdict_answers_last_try(block)
        if verdict is None or not answers or not verdict.startswith(SECOND_AGENT_AGREES_OPENING):
            raise Refused(
                f"Entry {entry} cannot be settled as not worth doing: its last try has no agreement from a second agent, so the entry stays open.\n"
                "Rule 5 of GHI 1132 needs that agreement: start a second agent with the input the second-agent-input subcommand prints, and record its verdict with the second-agent-verdict subcommand.")
    replace_state(lines, spans, entry, f"State: settled, {SETTLED_KINDS[kind]} — {by}, {now()}: {how}")
    return lines


def needs_the_user(lines, entry, because, by, why):
    spans = entry_spans(lines)
    block = entry_lines(lines, spans, entry)
    refuse_settled(block, entry)
    if because == "three-tries" and tries_since_user_ruling(block) < MAXIMUM_TRIES:
        raise Refused(
            f"Entry {entry} has {tries_since_user_ruling(block)} tries since the user last decided on it, fewer than {MAXIMUM_TRIES}, so it was not marked.\n"
            "Try again with the try subcommand, or name the reason rule 7 of GHI 1132 sends it to the user with --because.")
    replace_state(lines, spans, entry, f"State: needs the user — {by}, {now()}: {NEEDS_THE_USER_REASONS[because]}; {why}")
    return lines


def show(lines) -> str:
    spans = entry_spans(lines)
    out = []
    for entry in spans:
        block = entry_lines(lines, spans, entry)
        verdict, answers = last_verdict_answers_last_try(block)
        out.append(f"{entry}: {state_line(block) or 'no State line'}; tries since the user last decided: "
                   f"{tries_since_user_ruling(block)} of {MAXIMUM_TRIES}; last verdict: "
                   f"{(verdict + (' (answers the last try)' if answers else ' (a try came after it)')) if verdict else 'none'}")
    return "\n".join(out) or "The file has no entries."


def write_replacing(path: Path, lines, ending: str):
    descriptor, temporary = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as written:
            written.write("\n".join(lines) + ending)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink()
        raise


def parser():
    top = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = top.add_subparsers(dest="command", required=True)
    command = commands.add_parser("show")
    command.add_argument("file")
    command = commands.add_parser("try")
    command.add_argument("file")
    command.add_argument("entries", nargs="+")
    command.add_argument("--by", required=True)
    command.add_argument("--found", required=True)
    command = commands.add_parser("second-agent-input")
    command.add_argument("file")
    command.add_argument("entry")
    command.add_argument("--source", action="append", required=True)
    command = commands.add_parser("second-agent-verdict")
    command.add_argument("file")
    command.add_argument("entry")
    answer = command.add_mutually_exclusive_group(required=True)
    answer.add_argument("--agrees", action="store_true")
    answer.add_argument("--disagrees", action="store_true")
    command.add_argument("--who", required=True)
    command = commands.add_parser("settle")
    command.add_argument("file")
    command.add_argument("entry")
    command.add_argument("--kind", required=True, choices=sorted(SETTLED_KINDS))
    command.add_argument("--by", required=True)
    command.add_argument("--how", required=True)
    command = commands.add_parser("needs-the-user")
    command.add_argument("file")
    command.add_argument("entry")
    command.add_argument("--because", required=True, choices=sorted(NEEDS_THE_USER_REASONS))
    command.add_argument("--by", required=True)
    command.add_argument("--why", required=True)
    return top


def main(argv=None) -> int:
    arguments = parser().parse_args(argv)
    try:
        path = local_path(arguments.file)
        text = path.read_text(encoding="utf-8")
        ending = "\n" if text.endswith("\n") else ""
        lines = text.splitlines()
        if arguments.command == "show":
            print(show(lines))
            return 0
        if arguments.command == "second-agent-input":
            print(second_agent_input(lines, arguments.entry, arguments.source), end="")
            return 0
        if arguments.command == "try":
            lines = add_try(lines, arguments.entries, arguments.by, arguments.found)
        elif arguments.command == "second-agent-verdict":
            lines = add_verdict(lines, arguments.entry, arguments.agrees, arguments.who)
        elif arguments.command == "settle":
            lines = settle(lines, arguments.entry, arguments.kind, arguments.by, arguments.how)
        else:
            lines = needs_the_user(lines, arguments.entry, arguments.because, arguments.by, arguments.why)
        write_replacing(path, lines, ending)
    except Refused as refusal:
        print(f"REFUSED: {refusal}", file=sys.stderr)
        return 1
    except OSError as failure:
        print(f"FAILED: {arguments.file} could not be read or written, and was left as it was: {failure}\n"
              "If the path is wrong, run again with the path the file is at.", file=sys.stderr)
        return 1
    print(show(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
