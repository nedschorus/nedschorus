#!/usr/bin/env python3
"""PreToolUse guard on Bash: refuse a hand-typed `gh issue` write that
bypasses the GHI write tool, and say which command to run instead.

WHAT IT REFUSES, all on this project's repository only:
- `gh issue comment` in every form except `--delete-last`, and the
  `--comment`/`-c` flag of `gh issue close` and `gh issue reopen`;
- `gh issue create` and its alias `gh issue new`;
- `gh issue edit` carrying `--body`, `--body-file` or `--attach`, the flags
  that change an issue's body;
- `gh issue edit` carrying `--title`, the flag that changes an issue's title;
- `gh issue delete`.
Everything else passes: `view`, `list`, `status`, `close` and `reopen`
without a comment, and `edit` changing only labels, assignees, milestones,
projects, relationships or type.

THE RULINGS IT CARRIES.
- No comments (user-ruled 2026-09-24, item 4 of the meta-walk
  reboot-test-meta-walk-2026-09-23): "But I don't want comments as agents
  forget to read them. Better to update the ghi-Md". The design's comment
  operation, `docs/issues/46-ghi-info-agent-design.md` § The GHI write path,
  is dropped with it: there is no comment operation and there will be none.
  The same
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
event kind is the interim path" — and the ghi seat's brief, since deleted,
repeated it. Hand-filed and hand-edited issues are the case the design's
§ The GHI write path already names; this hook is the one it specifies.

DECISIONS, and where they depart from the design of record:
- Refuse, not rewrite. The design had this hook rewrite a body-bearing
  create or edit into the tool through `updatedInput`. That predates the
  link-only ruling of 2026-09-15: the tool now takes a GHI-MD path, and a
  `--title`/`--body` pair has no path to rewrite into.
- Hard-block: no override lane. The design ended every refusal with the
  soft-block reconsider line (user-ruled 2026-08-11). Here none of the refused
  forms has a case where the raw command is right after reconsidering: a
  comment's content belongs in the GHI-MD (ruled 2026-09-24), a new issue, a
  new body or a new title goes through the tool, and a delete is always a
  close. The
  reconsider lane that matters, second-guessing a duplicate verdict, lives in
  the tool itself with its own marker `.ghi-issue-write-reconsidered`. This
  hook does not share that marker: the tool treats any marker present as
  consent to skip its duplicate check, so a marker written to pass this hook
  would silently disarm the tool. When the tool cannot do the write, the
  refusal sends the agent to the user.
- Title edits are refused, reversing for titles the design's "Non-body
  edits (labels, title-only, milestones) pass through". The user approved it
  with "Y" on 2026-09-29, item 6 of the walk
  ghi-write-skill-link-only-rewalk-2026-09-28 (minutes:
  nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ghi-write-skill-link-only-rewalk-2026-09-28-minutes.md).
  edit-GHI retitles an issue from its GHI-MD's first heading, so a title
  changed by hand no longer matches the file, and the next edit-GHI run that
  changes that heading sets the title from the file again; merge-lane-2
  raised this in its review of this hook. Refusing `--title` leaves the
  title one source, the GHI-MD's first heading, and the refusal sends the
  agent there. A title edit that also carries a body flag gets the body
  refusal, which tells the agent to run the title edit alone afterwards for
  the title's instructions.
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
import subprocess
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
# The record line names the issue's files on main, looked up with the function
# that builds the issue's body, so this hook and the GHI write tool cannot
# disagree about which files the issue has. {outcome} is what the agent records.
RECORD_LINE_NO_FILE = (
    "This issue has no file on main under docs/issues/<number>-* or a system's "
    "directory: stop and tell the user."
)
RECORD_LINE_ONE_FILE = (
    "Record {outcome} in {path}, then open the edit's pull request with: "
    "python3 scripts/ghi-issue-write.py edit {path}"
)
RECORD_LINE_SEVERAL_FILES = (
    "The issue's files on main are: {paths}. Record {outcome} in the issue's GHI-MD "
    "among them, then open the edit's pull request with: python3 "
    "scripts/ghi-issue-write.py edit <that path>"
)
RECORD_LINE_LOOKUP_FAILED = (
    "Record {outcome} in the issue's GHI-MD, a file named docs/issues/<number>-*.md "
    "or a design in a system's docs/ directory, then open the edit's pull request "
    "with: python3 scripts/ghi-issue-write.py edit <path>"
)
CLOSE_OUTCOME = "the outcome"
REOPEN_OUTCOME = "why the issue is reopening"
COMMENT_OUTCOME = "what the comment would say"
EDIT_BODY_OUTCOME = "the change"
NO_COMMENTS_LINE = (
    "Do not comment on this project's issues: what an issue says lives in its "
    "GHI-MD, and a comment would sit outside it."
)
# Ends the comment, body and title refusals, except where the lookup line only
# says to stop: then there is no pull request to rerun after.
RERUN_LINE = (
    "If you opened that pull request: after it merges, pull main and run the same "
    "python3 scripts/ghi-issue-write.py edit command again; the rerun updates the issue."
)
LABELS_ONLY_LINE = (
    "To change only labels, assignees or the milestone, run gh issue edit without "
    "--title, --body, --body-file and --attach; that needs no file."
)
COMMENT_REFUSAL = NO_COMMENTS_LINE + "\n{record_line}"
CLOSE_WITH_COMMENT_REFUSAL = (
    NO_COMMENTS_LINE + "\n"
    "{record_line}\n"
    "Close the issue after that edit's pull request has merged and its rerun has "
    "finished, without --comment: gh issue close <number> --reason completed, or "
    "--reason \"not planned\", or --duplicate-of <the other issue's number>."
)
CLOSE_WITH_COMMENT_REFUSAL_NO_FILE = NO_COMMENTS_LINE + "\n" + RECORD_LINE_NO_FILE
REOPEN_WITH_COMMENT_REFUSAL = (
    NO_COMMENTS_LINE + "\n"
    "Run gh issue reopen again without --comment.\n"
    "{record_line}"
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
    "Do not set this project's issue bodies with gh issue edit: an issue's body is "
    "the links to its files on main, and scripts/ghi-issue-write.py writes it from "
    "those files.\n"
    + LABELS_ONLY_LINE + "\n"
    "If the command also set the title, run gh issue edit <number> --title alone "
    "afterwards for the title's instructions.\n"
    "{record_line}"
)
# The GHI write tool retitles an issue only when the issue has one file on main
# and the edit changes that file's first heading, so {title_line} stops the
# agent wherever the tool could not retitle.
EDIT_TITLE_REFUSAL = (
    "Do not set this project's issue titles with gh issue edit: "
    "scripts/ghi-issue-write.py sets an issue's title from the first heading of the "
    "issue's GHI-MD, when the issue has one file on main and an edit changes that "
    "heading.\n"
    + LABELS_ONLY_LINE + "\n"
    "{title_line}"
)
TITLE_LINES_ONE_FILE = (
    "If the first heading of {path} already reads the title you want, stop and tell "
    "the user.\n"
    "Otherwise change that heading to the title you want, then open the edit's pull "
    "request with: python3 scripts/ghi-issue-write.py edit {path}"
)
TITLE_LINE_SEVERAL_FILES = (
    "The issue's files on main are: {paths}. scripts/ghi-issue-write.py changes the "
    "title only of an issue with one file, so stop and tell the user."
)
TITLE_LINES_LOOKUP_FAILED = (
    "If the issue has no file or two or more files, counting files named "
    "docs/issues/<number>-*.md and designs in a system's docs/ directory, or the first "
    "heading of the issue's GHI-MD already reads the title you want, stop and tell the "
    "user.\n"
    "Otherwise change the first heading of the issue's GHI-MD to the title you want, "
    "then open the edit's pull request with: python3 scripts/ghi-issue-write.py edit "
    "<path>"
)
DELETE_REFUSAL = (
    "Do not delete this project's issues: a deleted issue cannot be restored.\n"
    "{record_line}\n"
    "Close the issue after that edit's pull request has merged and its rerun has "
    "finished, with the line below that fits.\n"
    "If this issue covers the same work as another issue: gh issue close <number> "
    "--duplicate-of <the other issue's number>\n"
    "If the issue's work is done: gh issue close <number> --reason completed\n"
    "If the issue will not be done, or was filed by mistake and duplicates no other "
    "issue: gh issue close <number> --reason \"not planned\""
)
DELETE_REFUSAL_NO_FILE = (
    "Do not delete this project's issues: a deleted issue cannot be restored.\n"
    "This issue has no file on main under docs/issues/<number>-* or a system's "
    "directory: if the issue was filed by mistake, close it with gh issue close "
    "<number> --reason \"not planned\"; otherwise stop and tell the user."
)

ISSUE_NUMBER_IN_URL_PATTERN = re.compile(r"/issues/(\d+)(?:[/#?]|$)")
# The lookup runs only on a refusal, and a refusal must still arrive if git hangs.
ISSUE_FILE_LOOKUP_TIMEOUT_SECONDS = 10


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


def issue_number_named(positionals):
    """The issue number the command names, from a number or an issue URL, or None."""
    if not positionals:
        return None
    first = positionals[0]
    if first.isdigit():
        return int(first)
    match = ISSUE_NUMBER_IN_URL_PATTERN.search(first)
    return int(match.group(1)) if match else None


def issue_files_on_main(number, working_directory):
    """The issue's files on origin/main, as the GHI write tool lists them, or None
    when they cannot be looked up: no number, no checkout, or a git failure."""
    if number is None or not working_directory:
        return None
    try:
        toplevel = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], cwd=working_directory,
            capture_output=True, text=True, check=False,
            timeout=ISSUE_FILE_LOOKUP_TIMEOUT_SECONDS)
        if toplevel.returncode != 0 or not toplevel.stdout.strip():
            return None
        tool_path = _REPOSITORY_ROOT / "scripts" / "ghi-issue-write.py"
        tool_spec = importlib.util.spec_from_file_location("ghi_issue_write", tool_path)
        tool = importlib.util.module_from_spec(tool_spec)
        tool_spec.loader.exec_module(tool)

        def runner(arguments, cwd=None):
            return tool.run(arguments, timeout=ISSUE_FILE_LOOKUP_TIMEOUT_SECONDS, cwd=cwd)

        return tool.ghi_md_paths_for_issue(number, Path(toplevel.stdout.strip()), runner)
    except Exception:
        return None


def record_line(outcome, files):
    if files is None:
        return RECORD_LINE_LOOKUP_FAILED.format(outcome=outcome)
    if not files:
        return RECORD_LINE_NO_FILE
    if len(files) == 1:
        return RECORD_LINE_ONE_FILE.format(outcome=outcome, path=files[0])
    return RECORD_LINE_SEVERAL_FILES.format(outcome=outcome, paths=", ".join(files))


def title_line(files):
    if files is None:
        return TITLE_LINES_LOOKUP_FAILED
    if not files:
        return RECORD_LINE_NO_FILE
    if len(files) == 1:
        return TITLE_LINES_ONE_FILE.format(path=files[0])
    return TITLE_LINE_SEVERAL_FILES.format(paths=", ".join(files))


def with_rerun_line(text, agent_may_open_pull_request):
    if not agent_may_open_pull_request:
        return text
    return text + "\n" + RERUN_LINE


def comment_refusal(files):
    return with_rerun_line(
        COMMENT_REFUSAL.format(record_line=record_line(COMMENT_OUTCOME, files)),
        files != [])


def edit_body_refusal(files):
    return with_rerun_line(
        EDIT_BODY_REFUSAL.format(record_line=record_line(EDIT_BODY_OUTCOME, files)),
        files != [])


def edit_title_refusal(files):
    return with_rerun_line(
        EDIT_TITLE_REFUSAL.format(title_line=title_line(files)),
        files is None or len(files) == 1)


def refusal_for(subcommand, arguments, repository_from_environment,
                working_directory=None):
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
        return comment_refusal(
            issue_files_on_main(issue_number_named(positionals), working_directory))
    if subcommand in ("close", "reopen"):
        if "--comment" not in flags:
            return None
        files = issue_files_on_main(issue_number_named(positionals), working_directory)
        if subcommand == "close":
            if files == []:
                return CLOSE_WITH_COMMENT_REFUSAL_NO_FILE
            return CLOSE_WITH_COMMENT_REFUSAL.format(
                record_line=record_line(CLOSE_OUTCOME, files))
        return REOPEN_WITH_COMMENT_REFUSAL.format(
            record_line=record_line(REOPEN_OUTCOME, files))
    if subcommand == "create":
        return CREATE_REFUSAL
    if subcommand == "edit":
        if not (EDIT_BODY_FLAGS & set(flags)) and "--title" not in flags:
            return None
        files = issue_files_on_main(issue_number_named(positionals), working_directory)
        if EDIT_BODY_FLAGS & set(flags):
            return edit_body_refusal(files)
        return edit_title_refusal(files)
    if subcommand == "delete":
        files = issue_files_on_main(issue_number_named(positionals), working_directory)
        if files == []:
            return DELETE_REFUSAL_NO_FILE
        return DELETE_REFUSAL.format(record_line=record_line(CLOSE_OUTCOME, files))
    return None


def analyze_command_text(command, working_directory=None):
    """The refusal for the first refused `gh issue` write in the command, or
    None. Heredoc bodies are data and are dropped before reading."""
    shell_view, _heredoc_bodies = split_out_heredocs(command)
    for words in tokenize_simple_commands(shell_view):
        if not words:
            continue
        invocation = find_gh_issue_invocation(words)
        if invocation is None:
            continue
        refusal = refusal_for(*invocation, working_directory=working_directory)
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
    working_directory = payload.get("cwd")
    if not isinstance(working_directory, str):
        working_directory = None
    refusal = analyze_command_text(command, working_directory)
    if refusal:
        deny(refusal)
    return 0


if __name__ == "__main__":
    sys.exit(main())
