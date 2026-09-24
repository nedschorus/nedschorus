#!/usr/bin/env python3
"""PreToolUse guard on Bash: refuse a hand-typed `gh issue` write that
bypasses the GHI write tool, and say which command to run instead.

WHAT IT REFUSES, all on this project's repository only:
- `gh issue comment` in every form except `--delete-last`, and the
  `--comment`/`-c` flag of `gh issue close` and `gh issue reopen`;
- `gh issue create` and its alias `gh issue new`;
- `gh issue edit` carrying `--body`, `--body-file` or `--attach`, the flags
  that change an issue's body;
- `gh issue delete`.
Everything else passes: `view`, `list`, `status`, `close` and `reopen`
without a comment, and `edit` changing only labels, assignees, milestones,
projects, relationships, type or title.

THE RULINGS IT CARRIES.
- No comments (user-ruled 2026-09-24, item 4 of the meta-walk
  reboot-test-meta-walk-2026-09-23): "But I don't want comments as agents
  forget to read them. Better to update the ghi-Md". The design's comment
  verb, `docs/issues/46-ghi-info-agent-design.md` § The GHI write path, is
  dropped with it: there is no comment verb and there will be none. The same
  walk approved this hook with "Y" to: refuse a hand-typed `gh issue
  comment`, `gh issue create` or `gh issue edit` and say what to do instead.
- A GHI's body is the links to its GHI-MD and nothing else (user-ruled
  2026-09-15). A hand-set body or a hand-filed issue breaks that, and only
  `scripts/ghi-issue-write.py` builds it, so create and body edits go there.
- Issues are never deleted; the record is append-forward (the design,
  § The GHI write path, "Delete is denied — close instead").

THE BEHAVIOUR IT DEFENDS AGAINST, named per CLAUDE.md's reviewer rule: agents
posting issue comments by hand. The /ghi-write skill tells them to do exactly
that today — "until #46 builds the tool, plain `gh issue comment` naming the
event kind is the interim path" — and `docs/agents/ghi-instructions.md`
repeats it. Hand-filed and hand-edited issues are the case the design's
§ The GHI write path already names; this hook is the one it specifies.

DECISIONS, and where they depart from the design of record:
- Refuse, not rewrite. The design had this hook rewrite a body-bearing
  create or edit into the tool through `updatedInput`. That predates the
  link-only ruling of 2026-09-15: the tool now takes a GHI-MD path, and a
  `--title`/`--body` pair has no path to rewrite into.
- Hard-block: no override lane. The design ended every refusal with the
  soft-block reconsider line (user-ruled 2026-08-11). Here none of the refused
  forms has a case where the raw command is right after reconsidering: a
  comment's content belongs in the GHI-MD (ruled 2026-09-24), a new issue or a
  new body goes through the tool, and a delete is always a close. The
  reconsider lane that matters, second-guessing a duplicate verdict, lives in
  the tool itself with its own marker `.ghi-issue-write-reconsidered`. This
  hook does not share that marker: the tool treats any marker present as
  consent to skip its duplicate check, so a marker written to pass this hook
  would silently disarm the tool. When the tool cannot do the write, the
  refusal sends the agent to the user.
- Title-only edits pass, as the design's "Non-body edits (labels,
  title-only, milestones) pass through" says. The tool retitles an issue when
  its GHI-MD's heading changes; a hand retitle is the design's accepted
  residual. Flagged in the pull request for the user to reverse.
- `gh issue comment --delete-last` passes: it removes a comment, which is
  the direction the ruling wants, and refusing it defends against nothing.
- Another repository passes. `-R`/`--repo`, `GH_REPO=` in front of the
  command, or an issue URL naming another repository send the write
  elsewhere, and the ruling is about this project's issues. An agent may
  report a defect upstream.
- The repository flag is read wherever gh accepts it: between `gh` and
  `issue`, between `issue` and the subcommand, and after the subcommand, in
  every spelling gh takes (`-R X`, `-RX`, `-R=X`, `--repo X`, `--repo=X`;
  each checked against gh 2.101.0 on 2026-09-24). When the flag is given
  more than once, gh uses the last one, and so does this guard. Reading it
  only after the subcommand let `gh -R nedschorus/nedschorus issue create`
  and `gh issue -R nedschorus/nedschorus comment` through while naming this
  repository, and agents do write `gh --repo X issue ...`. Found in the
  review of PR "Hand-typed gh issue comments, creates and body edits are
  refused" (https://github.com/nedschorus/nedschorus/pull/708), where Codex
  also raised it.
- `gh api` writes to issue endpoints are out of scope: the design's accepted
  residual (user-ruled 2026-08-07, reaffirmed 2026-08-09), "the enumeration
  holes stay open — `gh api`, MCP tools, creative quoting — under the
  cooperative posture".

WHAT IT CANNOT SEE, so nobody mistakes a choice for an oversight:
- The GHI write tool's own `gh` calls are subprocesses, below the Bash tool,
  so this hook never sees them; running the tool is `python3
  scripts/ghi-issue-write.py ...`, whose program is python3.
- ghi-info's headless sessions run with `--setting-sources user`
  (`scripts/ghi-info-ask.py`), so this project's hooks do not load there, and
  its link-repair edits are untouched.
- A `gh` behind `ssh`, `sh -c`, `eval`, `timeout`, `command`, or in a heredoc
  body is not recognised; `env` in front is. The same limits as the
  force-push guard, whose reading this shares.
- A gh alias the user defined is not expanded.

The tokenizer, the heredoc split and `is_program` are imported from
scripts/synthetic-keystroke-guard-hook.py, the project's shared shell reader,
as the force-push guard does: one reader, reviewed once.
"""

import importlib.util
import json
import re
import sys
from pathlib import Path

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_shell_reader_path = _REPOSITORY_ROOT / "scripts" / "synthetic-keystroke-guard-hook.py"
_shell_reader_spec = importlib.util.spec_from_file_location(
    "synthetic_keystroke_guard_hook", _shell_reader_path)
shell_reader = importlib.util.module_from_spec(_shell_reader_spec)
_shell_reader_spec.loader.exec_module(shell_reader)

split_out_heredocs = shell_reader.split_out_heredocs
tokenize_simple_commands = shell_reader.tokenize_simple_commands
is_program = shell_reader.is_program

PROJECT_REPOSITORY = "nedschorus/nedschorus"

ENVIRONMENT_ASSIGNMENT_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
ENV_COMMAND_VALUE_OPTIONS = {"-u", "--unset"}
ISSUE_URL_PATTERN = re.compile(
    r"^(?:https?://)?(?:www\.)?github\.com/([^/]+/[^/#?]+)/issues/", re.IGNORECASE)

# Each subcommand's flags that take a value, long form, with the short form
# mapped to it. A value is data: `--title "-b fix"` must not read as `-b`.
# Read from `gh issue <subcommand> --help`, gh 2.101.0, 2026-09-24.
SHORT_TO_LONG = {
    "-b": "--body", "-F": "--body-file", "-t": "--title", "-m": "--milestone",
    "-c": "--comment", "-r": "--reason", "-R": "--repo", "-a": "--assignee",
    "-l": "--label", "-p": "--project", "-T": "--template", "-e": "--editor",
    "-w": "--web",
}
VALUE_FLAGS = {
    "edit": {"--add-assignee", "--add-blocked-by", "--add-blocking",
             "--add-label", "--add-project", "--add-sub-issue", "--attach",
             "--body", "--body-file", "--milestone", "--parent",
             "--remove-assignee", "--remove-blocked-by", "--remove-blocking",
             "--remove-label", "--remove-project", "--remove-sub-issue",
             "--title", "--type", "--repo"},
    "close": {"--comment", "--duplicate-of", "--reason", "--repo"},
    "reopen": {"--comment", "--repo"},
    "comment": {"--attach", "--body", "--body-file", "--repo"},
    "create": {"--assignee", "--attach", "--blocked-by", "--blocking",
               "--body", "--body-file", "--label", "--milestone", "--parent",
               "--project", "--recover", "--template", "--title", "--type",
               "--repo"},
    "delete": {"--repo"},
}
SUBCOMMAND_ALIASES = {"new": "create"}
EDIT_BODY_FLAGS = {"--body", "--body-file", "--attach"}

# What an agent reads. Each line is one instruction and the condition it
# applies under; the rulings and reasons live in this docstring (user-ruled
# 2026-09-18, CLAUDE.md).
COMMENT_REFUSAL = (
    "Do not comment on this project's issues.\n"
    "Put the content in the issue's GHI-MD, docs/issues/<number>-*.md, then "
    "land it with: python3 scripts/ghi-issue-write.py edit <path>\n"
    "If the issue has no GHI-MD, stop and tell the user."
)
STATE_CHANGE_COMMENT_REFUSAL = (
    "Run gh issue {subcommand} again without --comment.\n"
    "Record the reason in the issue's GHI-MD, docs/issues/<number>-*.md, "
    "with: python3 scripts/ghi-issue-write.py edit <path>\n"
    "If the issue has no GHI-MD, stop and tell the user."
)
CREATE_REFUSAL = (
    "Do not file this project's issues with gh issue create.\n"
    "Write the issue as a GHI-MD, a markdown file whose first heading is the "
    "issue's title, then file it with: python3 scripts/ghi-issue-write.py "
    "create <path>\n"
    "If scripts/ghi-issue-write.py refuses, follow its message; if it cannot "
    "run, stop and tell the user."
)
EDIT_BODY_REFUSAL = (
    "Do not set this project's issue bodies with gh issue edit.\n"
    "Edit the issue's GHI-MD, docs/issues/<number>-*.md, then land it with: "
    "python3 scripts/ghi-issue-write.py edit <path>\n"
    "To change only labels, assignees or the milestone, run gh issue edit "
    "without --body, --body-file and --attach.\n"
    "If the issue has no GHI-MD, stop and tell the user."
)
DELETE_REFUSAL = (
    "Do not delete this project's issues.\n"
    "Close the issue instead: gh issue close <number> --reason completed, or "
    "--reason \"not planned\"."
)


def normalized_repository(value):
    """OWNER/REPO in lower case, from `[HOST/]OWNER/REPO` or an issue URL."""
    match = ISSUE_URL_PATTERN.match(value)
    if match:
        return match.group(1).lower()
    parts = [part for part in value.strip().rstrip("/").split("/") if part]
    if len(parts) >= 2:
        return "/".join(parts[-2:]).lower()
    return value.strip().lower()


def find_gh_issue_invocation(words):
    """Given one simple command's words, return (subcommand, arguments,
    repository_from_environment) for an invoked `gh issue <subcommand>`, or
    None. Quoted prose naming it arrives as one data word and never matches.
    Leading assignments and an `env` in front are read through, and a
    repository flag before the subcommand is carried into the arguments."""
    index = 0
    repository_from_environment = None
    while index < len(words) and ENVIRONMENT_ASSIGNMENT_PATTERN.match(words[index]):
        if words[index].startswith("GH_REPO="):
            repository_from_environment = words[index][len("GH_REPO="):]
        index += 1
    if index < len(words) and is_program(words[index], "env"):
        index += 1
        while index < len(words):
            word = words[index]
            if ENVIRONMENT_ASSIGNMENT_PATTERN.match(word):
                if word.startswith("GH_REPO="):
                    repository_from_environment = word[len("GH_REPO="):]
                index += 1
                continue
            if word in ENV_COMMAND_VALUE_OPTIONS:
                index += 2
                continue
            if word.startswith("-"):
                index += 1
                continue
            break
    if index >= len(words) or not is_program(words[index], "gh"):
        return None
    repository_flag_values = []
    index = skip_repository_flags(words, index + 1, repository_flag_values)
    if index >= len(words) or words[index] != "issue":
        return None
    index = skip_repository_flags(words, index + 1, repository_flag_values)
    if index >= len(words):
        return None
    subcommand = SUBCOMMAND_ALIASES.get(words[index], words[index])
    arguments = ([f"--repo={value}" for value in repository_flag_values]
                 + words[index + 1:])
    return subcommand, arguments, repository_from_environment


def skip_repository_flags(words, index, repository_flag_values):
    """Step past gh's -R/--repo flags starting at words[index], in every
    spelling gh accepts, appending each value to repository_flag_values.
    Return the index of the first word that is not one."""
    while index < len(words):
        word = words[index]
        if word in ("-R", "--repo"):
            if index + 1 >= len(words):
                return len(words)
            repository_flag_values.append(words[index + 1])
            index += 2
        elif word.startswith("--repo="):
            repository_flag_values.append(word[len("--repo="):])
            index += 1
        elif word.startswith("-R") and len(word) > 2:
            value = word[3:] if word[2] == "=" else word[2:]
            repository_flag_values.append(value)
            index += 1
        else:
            return index
    return index


def parse_arguments(subcommand, arguments):
    """Return (flags, positionals): flags maps each long flag present to the
    list of its values (True for a flag without one). Short forms, `=` forms
    and a short flag's attached value (`-bText`) are read as gh reads them."""
    value_flags = VALUE_FLAGS.get(subcommand, set())
    flags = {}
    positionals = []
    index = 0
    while index < len(arguments):
        word = arguments[index]
        index += 1
        if word == "--":
            positionals.extend(arguments[index:])
            break
        if word.startswith("--"):
            name, has_value, value = word.partition("=")
            if has_value:
                flags.setdefault(name, []).append(value)
            elif name in value_flags:
                value = arguments[index] if index < len(arguments) else ""
                index += 1
                flags.setdefault(name, []).append(value)
            else:
                flags[name] = True
            continue
        if word.startswith("-") and len(word) > 1:
            short = word[:2]
            name = SHORT_TO_LONG.get(short, short)
            if name in value_flags:
                if len(word) > 2:
                    # `-R=X` means X, as gh's flag parser reads it.
                    value = word[3:] if word[2] == "=" else word[2:]
                else:
                    value = arguments[index] if index < len(arguments) else ""
                    index += 1
                flags.setdefault(name, []).append(value)
            else:
                flags[name] = True
            continue
        positionals.append(word)
    return flags, positionals


def names_another_repository(flags, positionals, repository_from_environment):
    """True when the write is aimed at a repository other than this project's."""
    named = []
    repository_values = flags.get("--repo")
    if isinstance(repository_values, list):
        # gh uses the last repository flag given, wherever it sits.
        named.append(repository_values[-1])
    elif repository_from_environment is not None:
        named.append(repository_from_environment)
    named.extend(word for word in positionals if ISSUE_URL_PATTERN.match(word))
    return any(normalized_repository(value) != PROJECT_REPOSITORY
               for value in named if value)


def refusal_for(subcommand, arguments, repository_from_environment):
    """The refusal text for one `gh issue` invocation, or None to let it run."""
    if subcommand not in VALUE_FLAGS:
        return None
    flags, positionals = parse_arguments(subcommand, arguments)
    if names_another_repository(flags, positionals, repository_from_environment):
        return None
    if subcommand == "comment":
        writes = ("--body" in flags or "--body-file" in flags
                  or "--edit-last" in flags or "--attach" in flags)
        if "--delete-last" in flags and not writes:
            return None
        return COMMENT_REFUSAL
    if subcommand in ("close", "reopen"):
        if "--comment" in flags:
            return STATE_CHANGE_COMMENT_REFUSAL.format(subcommand=subcommand)
        return None
    if subcommand == "create":
        return CREATE_REFUSAL
    if subcommand == "edit":
        if EDIT_BODY_FLAGS & set(flags):
            return EDIT_BODY_REFUSAL
        return None
    if subcommand == "delete":
        return DELETE_REFUSAL
    return None


def analyze_command_text(command):
    """The refusal for the first refused `gh issue` write in the command, or
    None. Heredoc bodies are data and are dropped before reading."""
    shell_view, _heredoc_bodies = split_out_heredocs(command)
    for words in tokenize_simple_commands(shell_view):
        if not words:
            continue
        invocation = find_gh_issue_invocation(words)
        if invocation is None:
            continue
        refusal = refusal_for(*invocation)
        if refusal:
            return refusal
    return None


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))


def main(stdin=sys.stdin):
    try:
        payload = json.load(stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    if not command:
        return 0
    refusal = analyze_command_text(command)
    if refusal:
        deny(refusal)
    return 0


if __name__ == "__main__":
    sys.exit(main())
