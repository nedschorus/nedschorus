#!/usr/bin/env python3
"""Rewrite one git checkout's tracked files from the nedschorus and nc- names to the nedsnodes and nn- names, one stage at a time, and report every old name left.

Usage:
  scripts/project-rename-repository-contents-rewrite-hack.py --checkout DIR --stage 1|2|3
  scripts/project-rename-repository-contents-rewrite-hack.py --checkout DIR --residue-report

Each stage makes the change of one pull request of the project rename:
  1. the GitHub repository's owner and name: `nedschorus/nedschorus` becomes `nedsnodes/nedsnodes` in every file but Markdown, and the owner and name constants of the bare-number citation hook. It leaves the value of an `OLD_REPOSITORY` constant alone, through which code that reads GitHub links keeps accepting the old name.
  2. the machine paths, env vars, task-list names, job labels and unit names the move program, scripts/project-rename-machine-state-move-hack.py, moves: the reference-checkout and worktrees directory under Projects, the log-store, ~/.config/nedschorus, Claude Code project keys, `NEDSCHORUS_*` names, `nedschorus-<seat>-tasks`, `com.nedschorus.*` labels, ~/.local/state/nedschorus, ~/.local/share/nedschorus and each ~/.cache/nedschorus-* directory, the `nc-shared-database-service.service` unit, whose file it also renames, and the test suites' slice `nc\x2dtest\x2dsuites.slice`. It leaves the value of an `TASK_LIST_ID_PREFIX_BEFORE_PROJECT_RENAME` constant alone, through which code that reads task-list IDs keeps accepting the old prefix.
  3. the directories nc-systems, nc-queue and docs/nedschorus-wiki, the files whose names start `nc-shared-database` or `nedschorus-`, and in contents every citation of those paths, every wiki page name, and the nc- system names in code, alone or inside a longer identifier (`nc-shared-database`, `nc_shared_database`, `NC_SHARED_DATABASE`, `NcSharedDatabase`, `nc_systems`, `NC_SYSTEMS`). A kept file moves with its directory but keeps its name and content. For each Bash guard it moves, it adds the guard's former path to the map of former paths in the Bash-guard verdict check, so that check still reads a base ref's hook as the same guard.
A stage changes only the names its rules match, so it can be run alone on any checkout, including one that does not hold this program, and a second invocation changes nothing. Run the stages in order 1, 2, 3 on a branch that should carry all three.

--residue-report lists every match of an old name left in the checkout's tracked files and paths, each with the allowlist reason that covers it, counted by reason, and prints each match no reason covers. In a GHI-MD, a `nedschorus-` name counts as kept only when no file in the checkout has its new name, so a citation stage 3 missed is reported.

WHAT IT DOES NOT DO OR HANDLE. It changes only files git tracks; it does not commit. It leaves alone a path as it was at a past commit: a commit-pinned link (`blob/<commit>/<path>`), a `<commit>:<path>`, a line marked `# in git history only`, and a line that assigns a name ending `_BEFORE_PROJECT_RENAME`. It leaves alone the files the KEPT_PATHS list names: this program and its test, the move program and its test, which hold the old names on purpose, captured GitHub responses, recorded fixtures and transcripts, and archived queue records. It does not rewrite prose: glossary terms that start nc-, such as nc-head-commit, the words NedsChorus and NC, Markdown links to github.com/nedschorus/nedschorus, which GitHub redirects, and `nedschorus#<number>` citations wait for a later pull request, and the residue report names each. It keeps names of machine state that no step of the move program renames: /etc/sudoers.d/nedschorus-* and the `user.email` `unconfigured-agent@nedschorus.invalid` that each checkout's git config pins. The residue report finds an old name only in the spellings its OLD_NAME pattern lists. A file that is not UTF-8 is skipped and named.

HARM IT CAN CAUSE. It rewrites tracked files in place; `git checkout -- .` and `git clean` on the moved paths undo an invocation whose changes were not committed. A path as it was at a past commit in a form it does not recognise, such as a path in prose with no commit beside it, is rewritten to a path that commit never had. A rule that matches too much corrupts the names it touches, which the tests guard against for `sync-`, `async-`, `func-` and `SYNC_`.

HOW IT CAN FAIL. Stage 3 refuses to move a path whose new name is already tracked with other content, names each such path, moves the rest, and exits 1; when the new path holds the same content, it removes the old path with `git rm` instead of moving it, and adds the new path to git when git does not track it. A `git` command that fails prints its error and exits 1, with the changes made so far left in the working tree. --residue-report exits 1 when a match has no allowlist reason, and 0 otherwise.
"""

import argparse
import fnmatch
import re
import subprocess
import sys
from pathlib import Path

PROGRAM = "project-rename-repository-contents-rewrite-hack"
EXIT_OK = 0
EXIT_FAILED = 1

# No word character before an old name: `sync-` and `func-` end in `nc-`, and `SYNC_` ends in `NC_`. An escape
# such as \n or \t in a string literal ends in a letter, so a name may follow one.
B = r"(?:(?<![A-Za-z0-9_])|(?<=\\[ntr0]))"
# Nor a hyphen, where the name must not be the tail of a longer kebab name.
BH = r"(?:(?<![A-Za-z0-9_-])|(?<=\\[ntr0]))"
END = r"(?![A-Za-z0-9_])"
ENDH = r"(?![A-Za-z0-9_-])"

KEPT_PATHS = {
    "scripts/project-rename-repository-contents-rewrite-hack.py": "this program: holds the old names on purpose",
    "scripts/project-rename-repository-contents-rewrite-hack-test.py": "this program's test: holds the old names on purpose",
    "scripts/project-rename-machine-state-move-hack.py": "the move program: holds the old names on purpose",
    "scripts/project-rename-machine-state-move-hack-test.py": "the move program's test: holds the old names on purpose",
    "scripts/merge-gate-test-captured-github-responses/*": "captured GitHub responses, which tests name by literal file name",
    "*-fixtures/*": "recorded fixtures",
    "*.jsonl": "recorded transcripts and streams",
    "nc-queue/archived/*": "archived queue records",
    "nn-queue/archived/*": "archived queue records",
    "cold-read-reviewer-test-cases/*": "frozen documents the cold-read reviewer tests read",
}


def kept_reason(path):
    for pattern, reason in KEPT_PATHS.items():
        if fnmatch.fnmatchcase(path, pattern):
            return reason
    return None


def is_markdown(path):
    return path.endswith(".md")


class Rule:
    def __init__(self, pattern, replacement, markdown=True):
        self.pattern = re.compile(pattern)
        self.replacement = replacement
        self.markdown = markdown

    def applies_to(self, path):
        return self.markdown or not is_markdown(path)



# Code that reads GitHub links keeps accepting the old repository name, which GitHub redirects and old text holds,
# through a constant of this name; stage 1 leaves its value alone, so a rerun keeps the old name there.
OLD_REPOSITORY_CONSTANT = r'(?<!OLD_REPOSITORY = ")(?<!OLD_REPOSITORY=)'
# Code that reads task-list IDs keeps accepting the old prefix, which the task lists on disk keep, through a constant
# of this name; stage 2 leaves its value alone.
TASK_LIST_ID_PREFIX_BEFORE_PROJECT_RENAME_CONSTANT = r'(?<!TASK_LIST_ID_PREFIX_BEFORE_PROJECT_RENAME = ")'

STAGE_RULES = {
    1: [
        Rule(OLD_REPOSITORY_CONSTANT + B + r"nedschorus/nedschorus" + ENDH, "nedsnodes/nedsnodes", markdown=False),
        Rule(r"(?<= -R)nedschorus/nedschorus" + ENDH, "nedsnodes/nedsnodes", markdown=False),
        # The bare-number citation hook names the owner and the repository in two constants.
        Rule(r'(?<=GITHUB_REPOSITORY_OWNER = ")nedschorus(?=")', "nedsnodes", markdown=False),
        Rule(r'(?<=GITHUB_REPOSITORY_NAME = ")nedschorus(?=")', "nedsnodes", markdown=False),
    ],
    2: [
        Rule(r"(?<=Projects/)nedschorus(?=-worktrees" + ENDH + "|" + ENDH + ")", "nedsnodes"),
        Rule(r'(?<="Projects" / ")nedschorus(?=")', "nedsnodes"),
        Rule(r"(?<=Projects-)nedschorus" + END, "nedsnodes"),
        Rule(BH + r"nedschorus-logs", "nedsnodes-logs"),
        Rule(r"(?<=\.config/)nedschorus" + ENDH, "nedsnodes"),
        Rule(r'(?<="\.config" / ")nedschorus(?=")', "nedsnodes"),
        # The state directories and caches the move program's step 6a renames.
        Rule(r"(?<=\.local/state/)nedschorus" + ENDH, "nedsnodes"),
        Rule(r"(?<=\.local/share/)nedschorus" + ENDH, "nedsnodes"),
        Rule(r'(?<="state" / ")nedschorus(?=")|(?<="share" / ")nedschorus(?=")', "nedsnodes"),
        Rule(r'(?<=\.cache/)nedschorus-|(?<="\.cache" / ")nedschorus-', "nedsnodes-"),
        Rule(r"(?:(?<![A-Za-z0-9])|(?<=\\[ntr0]))NEDSCHORUS_", "NEDSNODES_"),
        Rule(B + r"com\.nedschorus\.", "com.nedsnodes."),
        Rule(BH + r"nedschorus(?=-(?:<[^>\n]*>|\{[^}\n]*\}|[^\s\"'/`<{])*-tasks" + ENDH + ")", "nedsnodes"),
        Rule(r"""(?<=["'])""" + TASK_LIST_ID_PREFIX_BEFORE_PROJECT_RENAME_CONSTANT + r"""nedschorus-(?=["'])""", "nedsnodes-"),
        Rule(BH + r"nc-shared-database-service(?=\.service\b)", "nn-shared-database-service"),
        Rule(r"(?<=systemctl --user status )nc-shared-database-service" + ENDH, "nn-shared-database-service"),
        # The test suites' systemd slice, made at run time and written with systemd's escape for a hyphen.
        Rule(r"(?<![A-Za-z0-9_])nc(?=\\x2dtest\\x2dsuites\.slice)", "nn"),
    ],
    3: [
        Rule(BH + r"nc-systems" + ENDH, "nn-systems"),
        Rule(BH + r"nc-queue" + ENDH, "nn-queue"),
        Rule(BH + r"nedschorus-wiki" + ENDH, "nedsnodes-wiki"),
        Rule(r'(?<=\("docs", ")nedschorus-wiki(?=")', "nedsnodes-wiki"),
        # A page under the wiki directory, real or made up by a test, such as nedschorus-widget-architecture-overview.md.
        Rule(r'(?<=-wiki/)nedschorus-|(?<=-wiki/queue/)nedschorus-|(?<=-wiki" / ")nedschorus-', "nedsnodes-"),
        # A page name pattern, such as `nedschorus-<subject>.md`; nedschorus-<seat>-tasks belongs to stage 2.
        Rule(BH + r"nedschorus-(?=<[^>\n]*>(?!-tasks))", "nedsnodes-"),
        # A system's overview page by name alone, real or made up by a test, such as nedschorus-aardvark-architecture-overview.md.
        Rule(BH + r"nedschorus-(?=[a-z0-9]+(?:-[a-z0-9]+)*-architecture-overview)", "nedsnodes-"),
        # A wiki page name built from a template, such as f"nedschorus-{system}-architecture-overview.md";
        # the task-list template nedschorus-{seat}-tasks belongs to stage 2.
        Rule(BH + r"nedschorus-(?=\{[^}]*\}-(?!tasks" + ENDH + "))", "nedsnodes-"),
        # Its file, backups and token files too, which the move program's step 6a renames on disk.
        Rule(BH + r"nc-shared-database", "nn-shared-database"),
        Rule(B + r"nc_shared_database", "nn_shared_database"),
        Rule(B + r"NC_SHARED_DATABASE", "NN_SHARED_DATABASE"),
        Rule(r"(?<![A-Za-z0-9_])NcSharedDatabase", "NnSharedDatabase"),
        Rule(B + r"nc_systems" + END, "nn_systems"),
        Rule(B + r"NC_SYSTEMS", "NN_SYSTEMS"),
        # The same names inside a longer identifier, such as NED_BOX_NC_SHARED_DATABASE_BACKUP_DIRECTORY.
        Rule(r"(?<=_)nc_shared_database", "nn_shared_database"),
        Rule(r"(?<=_)NC_SHARED_DATABASE", "NN_SHARED_DATABASE"),
        Rule(r"(?<=_)nc_systems" + END, "nn_systems"),
    ],
}


def stage_3_path(path):
    """The path stage 3 moves a tracked file to, or the path itself. A kept file moves with its directory but keeps
    its own name."""
    kept = kept_reason(path) is not None
    parts = path.split("/")
    if parts[0] == "nc-systems":
        parts[0] = "nn-systems"
    elif parts[0] == "nc-queue":
        parts[0] = "nn-queue"
    elif parts[:2] == ["docs", "nedschorus-wiki"]:
        parts[1] = "nedsnodes-wiki"
    renamed = []
    for index, part in enumerate(parts):
        if kept and index == len(parts) - 1:
            pass
        elif part.startswith("nc-shared-database"):
            part = "nn-" + part[len("nc-"):]
        elif part.startswith("nedschorus-"):
            part = "nedsnodes-" + part[len("nedschorus-"):]
        renamed.append(part)
    return "/".join(renamed)


def stage_2_path(path):
    name = path.rsplit("/", 1)[-1]
    if name == "nc-shared-database-service.service":
        return path[: -len(name)] + "nn-shared-database-service.service"
    return path


STAGE_PATH_MOVES = {1: lambda path: path, 2: stage_2_path, 3: stage_3_path}


def stage_3_page_name_rules(paths):
    """A rule that renames a citation by name alone, such as `nedschorus-glossary.md`, of a `nedschorus-` file
    stage 3 renames, and a name that is the start of such files' names, such as `nedschorus-handoff-architecture`."""
    stems = set()
    for path in paths:
        name = path.rsplit("/", 1)[-1]
        if name.startswith("nedschorus-") and stage_3_path(path) != path:
            stems.add(name.split(".", 1)[0])
        elif name.startswith("nedsnodes-") and kept_reason(path) is None:
            # A file an earlier run of this stage renamed, which a rerun must still find citations of.
            stems.add("nedschorus-" + name.split(".", 1)[0][len("nedsnodes-"):])

    def renamed(match):
        token = match.group(0)
        if any(stem.startswith(token) for stem in stems):
            return "nedsnodes-" + token[len("nedschorus-"):]
        return token

    return [Rule(BH + r"nedschorus-[a-z0-9]+(?:-[a-z0-9]+)*-?" + ENDH, renamed)] if stems else []


def git(checkout, *arguments):
    result = subprocess.run(["git", "-C", str(checkout), *arguments], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"{PROGRAM}: FAILED: git {' '.join(arguments)} exited {result.returncode}: {result.stderr.strip()}\n"
              f"Fix the cause, then run this program again: it changes only what is still old.", file=sys.stderr)
        sys.exit(EXIT_FAILED)
    return result.stdout


def tracked_paths(checkout):
    return [path for path in git(checkout, "ls-files", "-z").split("\0") if path]


def read_text(file):
    data = file.read_bytes()
    if b"\0" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


# A path as it was at a past commit, which no rule rewrites: a commit-pinned link such as
# github.com/<owner>/<repo>/blob/<commit>/<path>, a `<commit>:<path>` argument, and a line that names a former path
# and is marked so, or assigns the names a reader keeps from before the rename.
PINNED_TO_A_COMMIT = re.compile(r"(?:blob|tree|raw|blame)/[0-9a-f]{7,40}/[^\s)\]>`'\"]*"
                                r"|(?<![A-Za-z0-9_/.:-])(?=[0-9]*[a-f])(?=[a-f]*[0-9])[0-9a-f]{7,40}:[^\s)\]>`'\"]+")
HISTORY_ONLY_MARK = "# in git history only"
NAMES_BEFORE_PROJECT_RENAME_ASSIGNMENT = re.compile(r"_BEFORE_PROJECT_RENAME = ")


def rewritten(text, rules):
    lines = []
    for line in text.splitlines(keepends=True):
        if HISTORY_ONLY_MARK in line or NAMES_BEFORE_PROJECT_RENAME_ASSIGNMENT.search(line):
            lines.append(line)
            continue
        pieces = []
        start = 0
        for pinned in PINNED_TO_A_COMMIT.finditer(line):
            pieces.append(rewritten_piece(line[start:pinned.start()], rules))
            pieces.append(pinned.group(0))
            start = pinned.end()
        pieces.append(rewritten_piece(line[start:], rules))
        lines.append("".join(pieces))
    return "".join(lines)


def rewritten_piece(piece, rules):
    for rule in rules:
        piece = rule.pattern.sub(rule.replacement, piece)
    return piece


def rewrite_contents(checkout, paths, rules):
    changed = 0
    skipped = []
    for path in paths:
        if kept_reason(path) is not None:
            continue
        file = checkout / path
        if file.is_symlink() or not file.is_file():
            continue
        applicable = [rule for rule in rules if rule.applies_to(path)]
        if not applicable:
            continue
        text = read_text(file)
        if text is None:
            skipped.append(path)
            continue
        new_text = rewritten(text, applicable)
        if new_text != text:
            # write_bytes keeps the file's mode, so an executable stays executable.
            file.write_bytes(new_text.encode("utf-8"))
            changed += 1
    for path in skipped:
        print(f"{PROGRAM}: skipped {path}: not UTF-8 text")
    return changed


def move_paths(checkout, paths, move):
    tracked = set(paths)
    moved = 0
    refused = []
    for path in paths:
        target = move(path)
        if target == path:
            continue
        if target in tracked or (checkout / target).exists():
            if (checkout / target).is_file() and (checkout / target).read_bytes() == (checkout / path).read_bytes():
                # -f: the content rewrite has just left the old path modified and unstaged, which a plain rm refuses.
                git(checkout, "rm", "-q", "-f", "--", path)
                if target not in tracked:
                    git(checkout, "add", "--", target)
                    tracked.add(target)
                moved += 1
            else:
                refused.append((path, target))
            continue
        (checkout / target).parent.mkdir(parents=True, exist_ok=True)
        git(checkout, "mv", "--", path, target)
        tracked.add(target)
        moved += 1
    return moved, refused


BASH_GUARD_CHECK = "bash-guards-verdict-changes-between-git-refs-on-recorded-commands-check.py"


def stage_3_path_before(path):
    """The path a stage-3 path had before stage 3 moved it, or the path itself."""
    parts = path.split("/")
    if parts[0] == "nn-systems":
        parts[0] = "nc-systems"
    elif parts[0] == "nn-queue":
        parts[0] = "nc-queue"
    elif parts[:2] == ["docs", "nedsnodes-wiki"]:
        parts[1] = "nedschorus-wiki"
    parts = ["nc-" + part[len("nn-"):] if part.startswith("nn-shared-database") else
             "nedschorus-" + part[len("nedsnodes-"):] if part.startswith("nedsnodes-") else part for part in parts]
    return "/".join(parts)


def add_former_paths_of_moved_bash_guards(checkout, paths):
    """Give each Bash guard stage 3 moved a line in the Bash-guard check's map of former paths, so the check reads a
    base ref's hook at the former path as the same guard."""
    check = next((path for path in paths if path.rsplit("/", 1)[-1] == BASH_GUARD_CHECK), None)
    if check is None:
        return
    file = checkout / check
    text = file.read_text(encoding="utf-8")
    guards = re.search(r"^GUARDS = \{\n(.*?)^\}", text, re.MULTILINE | re.DOTALL)
    former_paths = re.search(r"^BASH_GUARD_CURRENT_PATHS_BY_FORMER_PATH = \{\n", text, re.MULTILINE)
    if guards is None or former_paths is None:
        return
    added = ""
    for guard in re.findall(r'^    "([^"]+)":', guards.group(1), re.MULTILINE):
        former = stage_3_path_before(guard)
        if former != guard and f'"{former}":' not in text:
            added += f'    "{former}":  {HISTORY_ONLY_MARK}\n        "{guard}",\n'
    if added:
        file.write_text(text[:former_paths.end()] + added + text[former_paths.end():], encoding="utf-8")


def run_stage(checkout, stage):
    paths = tracked_paths(checkout)
    rules = list(STAGE_RULES[stage])
    if stage == 3:
        rules = stage_3_page_name_rules(paths) + rules
    changed = rewrite_contents(checkout, paths, rules)
    moved, refused = move_paths(checkout, tracked_paths(checkout), STAGE_PATH_MOVES[stage])
    if stage == 3:
        add_former_paths_of_moved_bash_guards(checkout, tracked_paths(checkout))
    print(f"{PROGRAM}: stage {stage}: rewrote {changed} files, moved {moved} paths")
    if refused:
        print(f"{PROGRAM}: REFUSED to move {len(refused)} paths, because the new path already holds other content:")
        for path, target in refused:
            print(f"  {path} -> {target}")
        print("Compare each pair, keep the content the branch needs at the new path, delete the old path with "
              "`git rm`, then run this stage again.")
        return EXIT_FAILED
    return EXIT_OK


OLD_NAME = re.compile(r"(?i:nedschorus)|" + B + r"(?:nc[-_]|NC_|Nc(?=[A-Z]))|" + B + r"NC" + END
                      + r"|(?<=_)(?:nc_|NC_)|(?<=[A-Za-z0-9]-)nc-|(?<=[a-z])Nc(?=[A-Z])|nc\\x2d")

GLOSSARY_TERM_STEMS = (r"head[-_]commits?|test[-_]suites?|test[-_]sandbox(?:es)?|architecture[-_]overviews?|"
                       r"topic[-_]branch(?:es)?|mutation[-_]testing|critical[-_]code|checkin[-_]quality[-_]gate|"
                       r"python[-_]toolchain|system(?!s)|tests?|candidate|prune[-_]test")

# (path glob, pattern, reason): the pattern is searched in one line of a file whose path matches the glob,
# and every span it matches is covered by the reason.
ALLOWLIST = [
    ("*", r"(?i:nedschorus)#\d+", "a `nedschorus#<number>` citation, prose for the later pull request"),
    ("*", r'(?i:nedschorus)#(?:\\d|\(|")', "code that recognises `nedschorus#<number>` citations, which old text holds"),
    ("*.md", r"(?i:nedschorus)(?![-/_a-z0-9]|\.[a-z])", "the project's name in Markdown prose, for the later pull request"),
    ("*", r"NedsChorus|Nedschorus", "the project's name in prose, for the later pull request"),
    ("*", B + r"NC" + END, "the abbreviation NC in prose, for the later pull request"),
    ("*", r"(?<![A-Za-z0-9])(?i:nc[-_]?(?:" + GLOSSARY_TERM_STEMS + r"))[A-Za-z0-9_-]*",
     "an nc- glossary term, or a name made from one, renamed with its glossary entry in the prose pull request"),
    ("*", B + r"[A-Za-z0-9_-]*nc-test-suite[A-Za-z0-9_-]*",
     "a file or name made from the nc-test-suite glossary term, renamed with the term in the prose pull request"),
    ("*.md", r"(?:https?://)?(?:github\.com/)?(?i:nedschorus)/nedschorus\b[^\s)\]>`]*",
     "a Markdown link or command naming the old repository, which GitHub redirects; prose for the later pull request"),
    ("*", r"(?:NedSchorus|Nedschorus)/(?:NedSchorus|nedschorus)", "test data spelling the owner in another case"),
    ("*", r"nedschorus-nedschorus-\d+-[a-z-]+(?:\.json)?", "the name of a captured GitHub response file"),
    ("*", r"nedschorus\.invalid",
     "the git user.email each checkout's config pins, and test identities; no step of the move program changes the config"),
    ("*", r"nedschorus-git-gatekeeper-github-token", "a keychain item on the Mac, which no step of the move program renames"),
    ("*", r"(?:(?<=in )|(?<=for ))nedschorus\b|(?<=org )`nedschorus`", "the project's name in prose, for the later pull request"),
    ("*", r"(?i:nedschorus)/(?:ghi-api-probes|side-work|topic-)", "another repository or a branch of the old owner, in prose or test data"),
    ("*", r"from (?i:nedschorus)/", "a merge commit subject in test data"),
    ("*", r"sudoers\.d/nedschorus-[a-z-]+|# nedschorus:", "an installed sudoers file no step of the move program renames"),
    ("*", r"nc-systems-[a-z0-9-]+-tool-message-to-agent-[0-9-]+|[0-9-]+-nedschorus-[a-z0-9-]+",
     "the name of a file already in the log-store"),
    ("*", r"(?i:nedschorus)[-_](?:gatekeeper|emergency-stop-hook-notes|pull-request-head-test-run|run-all-test-suites-test|"
          r"backup-readonly-mount|found-copies|install-test|"
          r"canary|shell-command-text|"
          r"install[-_]test|main-gatekeeper|scheduled-full-test-run-of-main)[A-Za-z0-9_.-]*|/private/repos/nedschorus\b",
     "a run-time scratch name or test data name, renamed in the prose pull request"),
    ("*.md", r"`nc-`|`nedschorus-`|nedschorus-agent-seat|short for NedsChorus",
     "the naming page's prose on the nc- and nedschorus- prefixes, for the later pull request"),
    ("*", r"nedschorus-ai-native-software-development\.md", "a citation of a file that is not in the repository"),
    ("*", r'(?:(?<=OLD_REPOSITORY = ")|(?<=OLD_REPOSITORY=))nedschorus/nedschorus',
     "the old repository name, which code reading GitHub links still accepts, since GitHub redirects it and old text holds it"),
    ("*", r'(?<=TASK_LIST_ID_PREFIX_BEFORE_PROJECT_RENAME = ")nedschorus-',
     "the old task-list ID prefix, which code reading task-list IDs still accepts, since the task lists on disk keep it"),
    ("scripts/ghi-issue-write-test.py", r'github\.com/nedschorus/"|^\s*"nedschorus/issues/',
     "test data: a GHI-MD link in the old shape, split across two string literals"),
    ("*", r'(?i:nedschorus)(?= (?:seat|agents|PR|\d))|outside nedschorus|"nedschorus"(?=[,}\n)\] ]|$)|(?<=a )nedschorus(?= )'
          r"|nedschorus's|in_nedschorus|nedschorus \"$",
     "the project's name in prose or test data, for the later pull request"),
    ("*", r"projects-nedschorus-", "test data name, renamed in the prose pull request"),
    ("docs/issues/*", r"(?i:nedschorus)\.com\b", "the project's old domain, in prose for the later pull request"),
    ("docs/issues/*", r"(?<![A-Za-z0-9_-])[a-z0-9]+(?:-[a-z0-9]+)*-nedschorus-[a-z0-9.-]*",
     "a file name with nedschorus- inside it, not at its start: an outside file or a log-store record"),
    ("docs/issues/*", r"nedschorus-\[", "a regular expression for the old page-name prefix, in a command a GHI-MD records as run"),
    ("*", PINNED_TO_A_COMMIT.pattern, "a path as it was at a past commit, which stage 3 leaves alone"),
    ("*", r"^.*" + re.escape(HISTORY_ONLY_MARK) + r".*$|^.*_BEFORE_PROJECT_RENAME = .*$",
     "a former path marked `# in git history only`, or the names a reader keeps from before the rename"),
    ("docs/issues/*", r"^docs/issues/\S+\.md$",
     "a GHI-MD's own file name, which its GitHub issue's body links, so it keeps its name"),
    ("*", r"(?i:nedschorus)(?= (?:checkout|project|repository)\b)|(?<=in a )nedschorus\b|\bthe nedschorus\b",
     "the project's name in prose, for the later pull request"),
]


# A GHI-MD names files by name alone; such a name keeps its old spelling only when no file in the checkout has the
# renamed name, as for a retired file, a page a GHI-MD proposes, a log-store record or a machine path.
NAME_OF_NO_RENAMED_FILE_REASON = ("a `nedschorus-` name of no file in the checkout under its new name: a retired, "
                                  "proposed or outside file, a log-store record or a machine path")
NEDSCHORUS_NAME = re.compile(BH + r"nedschorus-[a-z0-9]+(?:-[a-z0-9]+)*-?" + ENDH)


def names_of_no_renamed_file(line, renamed_stems):
    for found in NEDSCHORUS_NAME.finditer(line):
        new_name = "nedsnodes-" + found.group(0)[len("nedschorus-"):]
        if not any(stem.startswith(new_name) for stem in renamed_stems):
            yield found.start(), found.end(), NAME_OF_NO_RENAMED_FILE_REASON


def residue(checkout):
    allowlist = [(glob, re.compile(pattern), reason) for glob, pattern, reason in ALLOWLIST]
    counts = {}
    uncovered = []
    paths = tracked_paths(checkout)
    renamed_stems = {path.rsplit("/", 1)[-1].split(".", 1)[0] for path in paths
                     if path.rsplit("/", 1)[-1].startswith("nedsnodes-")}
    for path in paths:
        reason = kept_reason(path)
        file = checkout / path
        text = read_text(file) if file.is_file() and not file.is_symlink() else None
        lines = [("<path>", path)] + ([] if text is None else list(enumerate(text.splitlines(), 1)))
        for number, line in lines:
            matches = list(OLD_NAME.finditer(line))
            if not matches:
                continue
            if reason is not None:
                counts[reason] = counts.get(reason, 0) + len(matches)
                continue
            covered_spans = []
            for glob, pattern, entry_reason in allowlist:
                if fnmatch.fnmatchcase(path, glob):
                    for found in pattern.finditer(line):
                        covered_spans.append((found.start(), found.end(), entry_reason))
            if fnmatch.fnmatchcase(path, "docs/issues/*"):
                covered_spans.extend(names_of_no_renamed_file(line, renamed_stems))
            for match in matches:
                entry = next((r for start, end, r in covered_spans if start <= match.start() < end), None)
                if entry is None:
                    uncovered.append(f"{path}:{number}: {line.strip()[:200]}")
                else:
                    counts[entry] = counts.get(entry, 0) + 1
    total = sum(counts.values())
    print(f"{PROGRAM}: residue: {total} old-name matches covered by the allowlist, {len(uncovered)} not covered")
    for entry, count in sorted(counts.items(), key=lambda item: -item[1]):
        print(f"  {count:6d}  {entry}")
    if uncovered:
        print("Matches no allowlist reason covers; rename each in its stage's rules, or add a reason:")
        for line in uncovered:
            print(f"  {line}")
        return EXIT_FAILED
    return EXIT_OK


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--checkout", required=True, type=Path)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--stage", type=int, choices=sorted(STAGE_RULES))
    action.add_argument("--residue-report", action="store_true")
    arguments = parser.parse_args(argv)
    checkout = arguments.checkout.resolve()
    if arguments.residue_report:
        return residue(checkout)
    return run_stage(checkout, arguments.stage)


if __name__ == "__main__":
    sys.exit(main())
