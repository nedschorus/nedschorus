#!/usr/bin/env python3
"""Compute the merge seat's review tier and facts for a pull request's brief.

Rule 1: tiers follow content. Tests, fenced Markdown code, and Python changes
limited to docstrings, comments and string constants get seat-and-codex.
Python behaviour changes and other code get full-reviewer. Prose gets
seat-alone. Settings, Bash guards and registered hooks always get a full
reviewer; all of .claude/hooks/ does too, including test files there.

Rule 2: a fix round reviews only its new commits, unless the delta contains
a merge, the branch history was rewritten, or the delta changes behaviour
in a program the earlier round's check exercised. That last condition is
approximated by a non-test, non-Markdown delta file getting full-reviewer:
the review history does not record exactly which checks were exercised.
Rounds count distinct reviewed heads other than the current head, so a
review already posted on the current head does not start another round.
When a delta holds a merge, or follows rewritten history, its files are
restricted to the pull request's own files on either head; main's unrelated
files should not decide the delta tier. All applicable reasons remain listed.

Rule 3: list changed agent-facing strings, with their context and old text.
Tests are excluded: a test's copy of an expected message is not handed to
an agent. F-string placeholders survive in the listing.

Merged pull requests use the merge commit's first parent as the diff base:
the current base branch already contains the head and would hide the change.
No rename detection is used: moving a program changes behaviour for callers,
so a rename is a deletion and an addition. Markdown prose anywhere is
seat-alone because prose outside code is outside the review scope.

Reads the pull request, reviews, inline comments and live base tip through
four read-only gh calls, and commits, refs and diffs from the local repository.
Never fetches, pushes or writes refs. git merge-tree --write-tree may write
tree objects. Writes no file except the optional --brief-skeleton, opened
exclusively because a rerun must not erase the seat's hand-written checks.
Exit 0: success. Exit 1: refusal, including malformed arguments or unavailable
inputs. Exit 2: program defect, with exception and traceback on stderr.

Usage:
  scripts/pull-request-review-plan.py --pull-request N [--repository DIR]
      [--github-repository OWNER/NAME] [--json] [--brief-skeleton PATH]
"""

import argparse
import ast
import difflib
import json
import os
import re
import shlex
import subprocess
import sys
import traceback
from pathlib import Path
from urllib.parse import quote

REVIEW_TIER_ORDER = {"seat-alone": 0, "seat-and-codex": 1, "full-reviewer": 2}
GITHUB_PULL_REQUEST_FIELDS = "number,title,url,state,author,headRefOid,baseRefName,mergeCommit"
GIT_FULL_HASH_PATTERN = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
DIFF_HUNK_HEADER_PATTERN = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", re.MULTILINE)
REGISTERED_HOOK_PATH_PATTERN = re.compile(r'\$CLAUDE_PROJECT_DIR"?/([^"\s]+)')
AGENT_STRING_NAME_SUFFIXES = ("_ADVICE", "_MESSAGE", "_TEMPLATE", "_LINE", "_LINES", "_REFUSAL")
PROSE_DIRECTORY_CODE_EXTENSIONS = {".py", ".sh", ".json", ".yaml", ".yml", ".toml", ".js"}
GIT_REDIRECTING_ENVIRONMENT_VARIABLES = (
    "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR",
)


class ReviewPlanRefusal(Exception):
    """An unavailable input or invalid request prevents a review plan."""


class RefusingArgumentParser(argparse.ArgumentParser):
    """Reserve exit 2 for program defects rather than malformed arguments."""

    def error(self, message):
        raise ReviewPlanRefusal(
            f"the command line is malformed, so no plan was computed: {message}.\n"
            "To correct the command line: read --help, then run this again with valid arguments.")


def first_output_line(text):
    return next(iter(text.splitlines()), "no diagnostic was given")


def run_git_in_repository(repository, *arguments):
    # -C must select the stated repository even in a seat with ambient GIT_DIR.
    environment = dict(os.environ)
    for variable in GIT_REDIRECTING_ENVIRONMENT_VARIABLES:
        environment.pop(variable, None)
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        return subprocess.run(["git", "-C", str(repository), *arguments],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", env=environment, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as failure:
        raise ReviewPlanRefusal(
            f"git could not read the repository, so no plan was computed: {failure}.\n"
            "If git is unavailable or timed out: fix the cause, then run this again.") from failure


def required_git_output(repository, *arguments):
    result = run_git_in_repository(repository, *arguments)
    if result.returncode:
        raise ReviewPlanRefusal(
            f"`{shlex.join(['git', '-C', str(repository), *arguments])}` failed, "
            f"so no plan was computed: {first_output_line(result.stderr)}.\n"
            "If git says it cannot find a revision: run "
            f"`{shlex.join(['git', '-C', str(repository), 'fetch', 'origin'])}`, then run this again.\n"
            "Otherwise: tell the user what git said.")
    return result.stdout.strip()


def commit_is_in_repository(repository, revision):
    return run_git_in_repository(repository, "cat-file", "-e", f"{revision}^{{commit}}").returncode == 0


def commit_is_ancestor_of(repository, earlier, later):
    result = run_git_in_repository(repository, "merge-base", "--is-ancestor", earlier, later)
    if result.returncode not in (0, 1):
        raise ReviewPlanRefusal(
            f"git could not compare commit ancestry, so no plan was computed: "
            f"{first_output_line(result.stderr)}.\n"
            "If git says it cannot find a revision: run "
            f"`{shlex.join(['git', '-C', str(repository), 'fetch', 'origin'])}`, then run this again.\n"
            "Otherwise: tell the user what git said.")
    return result.returncode == 0


def read_revision_blob_or_none(repository, revision, path):
    result = run_git_in_repository(repository, "show", f"{revision}:{path}")
    return result.stdout if result.returncode == 0 else None


def read_github_json_or_refuse(arguments, expected_shape):
    command = ["gh", *arguments]
    instructions = (
        "If gh says the pull request was not found: check the number and --github-repository.\n"
        "If gh says it is not logged in or its token was rejected: tell the user what gh said; "
        "this program needs gh to read the pull request.\n"
        "Otherwise: run this again once the cause is fixed.")
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=60)
    except (OSError, subprocess.TimeoutExpired) as failure:
        raise ReviewPlanRefusal(f"`{shlex.join(command)}` could not run, so no plan "
                                f"was computed: {failure}.\n{instructions}") from failure
    if result.returncode:
        raise ReviewPlanRefusal(f"`{shlex.join(command)}` failed with exit {result.returncode}: "
                                f"{first_output_line(result.stderr)}.\n{instructions}")
    try:
        payload = json.loads(result.stdout)
        if not expected_shape(payload):
            raise ValueError("the JSON does not have the expected fields and types")
        return payload
    except (ValueError, TypeError, KeyError) as failure:
        raise ReviewPlanRefusal(
            f"`{shlex.join(command)}` returned unexpected JSON, so no plan was computed: {failure}.\n"
            "To proceed: tell the user which gh call returned unexpected JSON and what was wrong with it; "
            "no plan can be computed without it.") from failure


def is_nonempty_string(value):
    return isinstance(value, str) and bool(value)


def is_full_commit_hash(value):
    return isinstance(value, str) and GIT_FULL_HASH_PATTERN.fullmatch(value) is not None


def github_pull_request_has_expected_shape(payload):
    return (isinstance(payload, dict) and type(payload.get("number")) is int
            and payload["number"] > 0 and isinstance(payload.get("title"), str)
            and is_nonempty_string(payload.get("url"))
            and payload.get("state") in ("OPEN", "CLOSED", "MERGED")
            and isinstance(payload.get("author"), dict)
            and is_nonempty_string(payload["author"].get("login"))
            and is_full_commit_hash(payload.get("headRefOid"))
            and is_nonempty_string(payload.get("baseRefName"))
            and "mergeCommit" in payload
            and (payload["mergeCommit"] is None
                 or (isinstance(payload["mergeCommit"], dict)
                     and is_full_commit_hash(payload["mergeCommit"].get("oid")))))


def github_review_has_expected_shape(review):
    return (isinstance(review, dict) and type(review.get("id")) is int
            and is_nonempty_string(review.get("node_id"))
            and isinstance(review.get("user"), dict)
            and is_nonempty_string(review["user"].get("login"))
            and is_nonempty_string(review.get("state"))
            and (review["state"] == "PENDING"
                 or (is_full_commit_hash(review.get("commit_id"))
                     and is_nonempty_string(review.get("submitted_at")))))


def github_comment_has_expected_shape(comment):
    return (isinstance(comment, dict) and "pull_request_review_id" in comment
            and (comment["pull_request_review_id"] is None
                 or type(comment["pull_request_review_id"]) is int))


def github_pages_have_expected_shape(payload, item_validator):
    return (isinstance(payload, list)
            and all(isinstance(page, list) and all(item_validator(item) for item in page)
                    for page in payload))


def github_branch_has_expected_shape(payload):
    return (isinstance(payload, dict) and isinstance(payload.get("commit"), dict)
            and is_full_commit_hash(payload["commit"].get("sha")))


def parse_diff_hunk_line_ranges(diff_text):
    """Each tuple is (old start, old count, new start, new count)."""
    return [tuple(int(value) if value is not None else 1 for value in match.groups())
            for match in DIFF_HUNK_HEADER_PATTERN.finditer(diff_text)]


def line_span_intersects_hunk_side(start, end, hunk_start, hunk_count):
    return hunk_count > 0 and start < hunk_start + hunk_count and end >= hunk_start


def fenced_code_block_line_numbers_in_markdown(source):
    inside_lines = set()
    fence_character = None
    fence_length = 0
    for line_number, line in enumerate((source or "").splitlines(), 1):
        if fence_character is None:
            opener = re.match(r"(`{3,}|~{3,})", line.lstrip())
            if opener:
                fence_character = opener[0][0]
                fence_length = len(opener[0])
                inside_lines.add(line_number)
        else:
            inside_lines.add(line_number)
            stripped = line.strip()
            if len(stripped) >= fence_length and set(stripped) == {fence_character}:
                fence_character = None
    return inside_lines


class SyntaxTreeWithoutDocstringsOrStringValues(ast.NodeTransformer):
    """Preserve code structure while ignoring the text allowed at a lower tier."""

    def visit(self, node):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if (node.body and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)):
                node.body = node.body[1:]
        return super().visit(node)

    def visit_Constant(self, node):
        if isinstance(node.value, str):
            node.value = ""
        return node


def normalized_syntax_tree_dump_without_strings(source):
    return ast.dump(SyntaxTreeWithoutDocstringsOrStringValues().visit(ast.parse(source)))


def path_is_test_file(path):
    return path.endswith("-test.py") or "tests" in path.split("/")[:-1]


def registered_hook_paths_at_revision(repository, revision):
    source = read_revision_blob_or_none(repository, revision, ".claude/settings.json")
    try:
        settings = json.loads(source) if source is not None else {}
    except ValueError:
        return set()
    if not isinstance(settings, dict) or not isinstance(settings.get("hooks", {}), dict):
        return set()
    registered_paths = set()
    for event_entries in settings.get("hooks", {}).values():
        if not isinstance(event_entries, list):
            continue
        for event_entry in event_entries:
            hook_entries = event_entry.get("hooks", []) if isinstance(event_entry, dict) else []
            if not isinstance(hook_entries, list):
                continue
            for hook_entry in hook_entries:
                command = hook_entry.get("command") if isinstance(hook_entry, dict) else None
                if isinstance(command, str):
                    registered_paths.update(REGISTERED_HOOK_PATH_PATTERN.findall(command))
    return registered_paths


def hook_path_rule_reason(path, registered_paths):
    if path.startswith(".claude/hooks/"):
        return f"{path} is under .claude/hooks/; every file there always gets a full reviewer"
    if path.startswith("scripts/") and path.count("/") == 1 and path.endswith("guard-hook.py"):
        return f"{path} is a Bash guard; a change to it always gets a full reviewer"
    if path in registered_paths:
        return f"{path} is registered as a hook in .claude/settings.json; a change to it always gets a full reviewer"
    return None


def classify_changed_file_into_class_tier_and_reason(repository, old_revision, new_revision,
                                                      path, status, registered_paths):
    if path == ".claude/settings.json":
        return ("settings", "full-reviewer", ".claude/settings.json registers the hooks; a change to it always gets a full reviewer")
    hook_reason = hook_path_rule_reason(path, registered_paths)
    if hook_reason:
        return "hook", "full-reviewer", hook_reason
    if path_is_test_file(path):
        return "test", "seat-and-codex", f"{path} is a test file"
    if path.endswith(".md"):
        old_lines = fenced_code_block_line_numbers_in_markdown(read_revision_blob_or_none(repository, old_revision, path))
        new_lines = fenced_code_block_line_numbers_in_markdown(read_revision_blob_or_none(repository, new_revision, path))
        diff_text = required_git_output(repository, "diff", "-U0", "--no-ext-diff", "--no-textconv",
                                        "--no-color", old_revision, new_revision, "--", path)
        changes_code = any(
            any(start <= line < start + count for line in inside)
            for old_start, old_count, new_start, new_count in parse_diff_hunk_line_ranges(diff_text)
            for start, count, inside in ((old_start, old_count, old_lines), (new_start, new_count, new_lines)))
        if changes_code:
            return "code", "seat-and-codex", f"{path} changes lines inside fenced code blocks"
        return "prose", "seat-alone", f"{path} changes only prose outside fenced code blocks"
    if (path.startswith(("docs/", "nc-queue/"))
            and Path(path).suffix not in PROSE_DIRECTORY_CODE_EXTENSIONS):
        return "prose", "seat-alone", f"{path} is prose under docs/ or nc-queue/"
    if path.endswith(".py"):
        if status == "A":
            return "code", "full-reviewer", f"{path} is a new program"
        if status == "D":
            return "code", "full-reviewer", f"{path} is deleted"
        syntax_dumps = []
        for side, revision in (("old side", old_revision), ("new side", new_revision)):
            source = read_revision_blob_or_none(repository, revision, path)
            try:
                if source is None:
                    raise SyntaxError("no source blob")
                syntax_dumps.append(normalized_syntax_tree_dump_without_strings(source))
            except (SyntaxError, ValueError):
                return "code", "full-reviewer", f"{path} does not parse at {side}"
        if syntax_dumps[0] == syntax_dumps[1]:
            return "code", "seat-and-codex", f"{path} changes only docstrings, comments and string constants"
        return "code", "full-reviewer", f"{path} changes its syntax tree beyond docstrings, comments and string constants"
    return "code", "full-reviewer", f"{path} is not Python or Markdown, so no check shows its change leaves behaviour alone"


def changed_files_with_classes_and_tiers(repository, old_revision, new_revision,
                                        hook_registration_old_revision=None):
    # Keep NUL separators: paths can contain spaces, tabs and newlines.
    output = run_git_in_repository(repository, "diff", "--no-renames", "--name-status", "-z", old_revision, new_revision)
    if output.returncode:
        raise ReviewPlanRefusal(
            f"git could not read changed files, so no plan was computed: {first_output_line(output.stderr)}.\n"
            "Once both revisions can be read: run this again.")
    fields = output.stdout.split("\0")
    if fields[-1] == "":
        fields.pop()
    if len(fields) % 2:
        raise ValueError("git's NUL-separated name-status output has an incomplete entry")
    # Include hooks present when the branch was cut, as well as registrations
    # added on main or the branch since then.
    registered_paths = (registered_hook_paths_at_revision(repository, old_revision)
                        | registered_hook_paths_at_revision(repository, new_revision))
    if hook_registration_old_revision is not None:
        registered_paths |= registered_hook_paths_at_revision(repository, hook_registration_old_revision)
    changed_files = []
    for status, path in zip(fields[::2], fields[1::2]):
        file_class, tier, reason = classify_changed_file_into_class_tier_and_reason(
            repository, old_revision, new_revision, path, status, registered_paths)
        changed_files.append({"path": path, "status": status, "class": file_class,
                              "tier": tier, "reason": reason})
    return sorted(changed_files, key=lambda entry: entry["path"])


def review_tier_and_deciding_reason(changed_files):
    if not changed_files:
        return "seat-alone", "the pull request changes no file"
    deciding_file = min(changed_files, key=lambda entry: (
        -REVIEW_TIER_ORDER[entry["tier"]], entry["class"] not in ("hook", "settings"),
        path_is_test_file(entry["path"]), entry["path"]))
    return deciding_file["tier"], deciding_file["reason"]


def string_nodes_without_f_string_parts(expression):
    if isinstance(expression, ast.JoinedStr):
        yield expression
    elif isinstance(expression, ast.Constant) and isinstance(expression.value, str):
        yield expression
    else:
        for child in ast.iter_child_nodes(expression):
            yield from string_nodes_without_f_string_parts(child)


class AgentFacingStringNodeCollector(ast.NodeVisitor):
    """Record string spans and their call, assignment or exception context."""

    def __init__(self):
        self.enclosing_names = []
        self.string_entries = []
        self.seen_node_contexts = set()

    def collect_expression_strings(self, expression, label):
        if expression is None:
            return
        if self.enclosing_names:
            label += f" in {'.'.join(self.enclosing_names)}()"
        for node in string_nodes_without_f_string_parts(expression):
            identity = (id(node), label)
            if identity in self.seen_node_contexts:
                continue
            self.seen_node_contexts.add(identity)
            self.string_entries.append({"line": node.lineno, "end_line": node.end_lineno,
                                        "label": label, "text": ast.unparse(node) if isinstance(node, ast.JoinedStr) else node.value})

    def visit_enclosing_definition(self, node):
        self.enclosing_names.append(node.name)
        self.generic_visit(node)
        self.enclosing_names.pop()

    visit_FunctionDef = visit_enclosing_definition
    visit_AsyncFunctionDef = visit_enclosing_definition
    visit_ClassDef = visit_enclosing_definition

    def visit_Call(self, node):
        call_name = ast.unparse(node.func)
        if call_name in ("print", "sys.stderr.write", "sys.stdout.write"):
            for argument in [*node.args, *(keyword.value for keyword in node.keywords)]:
                self.collect_expression_strings(argument, call_name)
        self.generic_visit(node)

    def visit_Raise(self, node):
        self.collect_expression_strings(node.exc, "raise")
        self.generic_visit(node)

    def visit_assignment_value(self, node):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name) and target.id.endswith(AGENT_STRING_NAME_SUFFIXES):
                self.collect_expression_strings(node.value, f"{target.id} =")
        self.generic_visit(node)

    visit_Assign = visit_assignment_value
    visit_AnnAssign = visit_assignment_value
    visit_AugAssign = visit_assignment_value


def agent_facing_string_nodes_in_source(source):
    if source is None:
        return []
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return []
    collector = AgentFacingStringNodeCollector()
    if ("__doc__" in source and tree.body and isinstance(tree.body[0], ast.Expr)
            and isinstance(tree.body[0].value, ast.Constant)
            and isinstance(tree.body[0].value.value, str)):
        collector.collect_expression_strings(tree.body[0].value, "module docstring (printed by --help)")
    collector.visit(tree)
    return sorted(collector.string_entries, key=lambda entry: (entry["line"], entry["label"]))


def changed_agent_facing_text_entries(repository, old_revision, new_revision, changed_files):
    entries = []
    for changed_file in changed_files:
        path = changed_file["path"]
        if (not path.endswith(".py") or path_is_test_file(path)
                or not path.startswith(("scripts/", ".claude/hooks/", "nc-systems/"))
                or changed_file["status"] == "D"):
            continue
        new_nodes = agent_facing_string_nodes_in_source(read_revision_blob_or_none(repository, new_revision, path))
        if changed_file["status"] == "A":
            entries.extend({"path": path, "line": node["line"], "label": node["label"],
                            "old_text": None, "new_text": node["text"]} for node in new_nodes)
            continue
        old_nodes = agent_facing_string_nodes_in_source(read_revision_blob_or_none(repository, old_revision, path))
        diff_text = required_git_output(repository, "diff", "-U0", "--no-ext-diff", "--no-textconv", "--no-color",
                                        old_revision, new_revision, "--", path)
        listed_new_nodes = set()
        used_old_nodes = set()
        for old_start, old_count, new_start, new_count in parse_diff_hunk_line_ranges(diff_text):
            old_candidates = [(index, node) for index, node in enumerate(old_nodes)
                              if line_span_intersects_hunk_side(node["line"], node["end_line"], old_start, old_count)]
            for new_index, new_node in enumerate(new_nodes):
                if new_index in listed_new_nodes or not line_span_intersects_hunk_side(
                        new_node["line"], new_node["end_line"], new_start, new_count):
                    continue
                if any(node["text"] == new_node["text"] for _, node in old_candidates):
                    continue
                old_match = next(((index, node) for index, node in old_candidates
                                  if index not in used_old_nodes and node["label"] == new_node["label"]
                                  and node["text"] != new_node["text"]), None)
                if old_match:
                    used_old_nodes.add(old_match[0])
                listed_new_nodes.add(new_index)
                entries.append({"path": path, "line": new_node["line"], "label": new_node["label"],
                                "old_text": old_match[1]["text"] if old_match else None, "new_text": new_node["text"]})
    return sorted(entries, key=lambda entry: (entry["path"], entry["line"], entry["label"]))


def suites_split_from_a_program_test_at_revision(repository, revision, sibling_test_path, program_stem):
    """The files at revision in sibling_test_path's directory named
    <program_stem>-<anything>-test.py, sibling_test_path among them when it
    exists: a program whose suite is split by topic keeps the program's name
    in front of each part's."""
    directory = os.path.dirname(sibling_test_path)
    listed = required_git_output(repository, "ls-tree", "-z", "--name-only", revision, "--",
                                 directory + "/" if directory else ".")
    return {path for path in listed.split("\0")
            if os.path.basename(path).startswith(program_stem + "-") and path.endswith("-test.py")}


def test_files_to_run_for_changed_files(repository, head, changed_files):
    candidate_paths = set()
    for changed_file in changed_files:
        path = Path(changed_file["path"])
        if path.name.endswith("-test.py"):
            candidate_paths.add(path.as_posix())
        elif path.suffix == ".py" and not path_is_test_file(path.as_posix()):
            test_name = path.stem + "-test.py"
            for candidate in (path.parent / test_name, path.parent / "tests" / test_name,
                              path.parent / ".." / "tests" / test_name):
                # posix normpath collapses '..' before asking git for a blob.
                normalized = os.path.normpath(candidate.as_posix())
                if not normalized.startswith("../"):
                    candidate_paths.add(normalized)
                    candidate_paths.update(suites_split_from_a_program_test_at_revision(
                        repository, head, normalized, path.stem))
    return sorted(path for path in candidate_paths
                  if run_git_in_repository(repository, "cat-file", "-e", f"{head}:{path}").returncode == 0)


def posting_rule_and_reason_for_author(author):
    if author == "mac-claude":
        return ("the reviewer posts a COMMENT whose first line is APPROVE or REQUEST_CHANGES",
                "reviewers post as mac-claude, and GitHub refuses an approving review from a pull request's author")
    if author == "ned-review-merge":
        return ("mac-claude posts a normal review, and its approval is the one the merge needs",
                "ned-review-merge, the seat's account, cannot approve a pull request it opened")
    return "a normal review", None


def merged_tree_against_origin_main(repository, head):
    result = run_git_in_repository(repository, "merge-tree", "--write-tree", "--name-only", "--no-messages", "origin/main", head)
    if result.returncode in (0, 1):
        lines = result.stdout.splitlines()
        if not lines or not is_full_commit_hash(lines[0]):
            raise ValueError("git merge-tree did not return a tree hash")
        return {"tree": lines[0], "conflicting_paths": [line for line in lines[1:] if line] if result.returncode == 1 else [], "error": None}
    return {"tree": None, "conflicting_paths": [], "error": first_output_line(result.stderr)}


def compute_pull_request_review_plan(arguments):
    repository = arguments.repository.resolve()
    fetch_command = shlex.join(["git", "-C", str(repository), "fetch", "origin"])
    if run_git_in_repository(repository, "rev-parse", "--git-dir").returncode:
        raise ReviewPlanRefusal(f"{repository} is not inside a git repository, so no plan can be read from it.\n"
                                "To select a repository: pass its directory with --repository, then run this again.")
    github_repository = arguments.github_repository
    number = arguments.pull_request
    api_prefix = f"repos/{github_repository}"
    pull_request = read_github_json_or_refuse(
        ["pr", "view", str(number), "--repo", github_repository, "--json", GITHUB_PULL_REQUEST_FIELDS],
        lambda payload: github_pull_request_has_expected_shape(payload) and payload["number"] == number)
    review_pages = read_github_json_or_refuse(
        ["api", "--paginate", "--slurp", f"{api_prefix}/pulls/{number}/reviews"],
        lambda payload: github_pages_have_expected_shape(payload, github_review_has_expected_shape))
    comment_pages = read_github_json_or_refuse(
        ["api", "--paginate", "--slurp", f"{api_prefix}/pulls/{number}/comments"],
        lambda payload: github_pages_have_expected_shape(payload, github_comment_has_expected_shape))
    base_branch = pull_request["baseRefName"]
    live_branch = read_github_json_or_refuse(
        ["api", f"{api_prefix}/branches/{quote(base_branch, safe='')}"], github_branch_has_expected_shape)
    head = pull_request["headRefOid"]
    if not commit_is_in_repository(repository, head):
        head_fetch = shlex.join(["git", "-C", str(repository), "fetch", "origin", f"pull/{number}/head"])
        raise ReviewPlanRefusal(f"the head of pull request {number}, {head}, is not in the repository at {repository}, "
                                f"so no plan can be read from it.\nTo make it available: run `{head_fetch}`, then run this again.")
    for branch in dict.fromkeys((base_branch, "main")):
        if not commit_is_in_repository(repository, f"refs/remotes/origin/{branch}"):
            raise ReviewPlanRefusal(f"origin/{branch} is missing from the repository at {repository}, so no plan can be computed.\n"
                                    f"To make the base available: run `{fetch_command}`, then run this again.")
    diff_base = required_git_output(repository, "rev-parse", f"refs/remotes/origin/{base_branch}")
    diff_base_reason = f"the local base branch origin/{base_branch}, because the pull request is not merged"
    if pull_request["state"] == "MERGED" and pull_request["mergeCommit"] is not None:
        merge_commit = pull_request["mergeCommit"]["oid"]
        if not commit_is_in_repository(repository, merge_commit):
            raise ReviewPlanRefusal(f"merge commit {merge_commit} is not in the repository at {repository}, so the merged pull request's diff cannot be read.\n"
                                    f"To make the merge available: run `{fetch_command}`, then run this again.")
        diff_base = required_git_output(repository, "rev-parse", f"{merge_commit}^1")
        diff_base_reason = f"the first parent of merge commit {merge_commit}, because the pull request is merged"
    merge_base = required_git_output(repository, "merge-base", diff_base, head)
    origin_main = required_git_output(repository, "rev-parse", "refs/remotes/origin/main")
    live_base = live_branch["commit"]["sha"]
    warning = None
    if (not commit_is_in_repository(repository, live_base)
            or not commit_is_ancestor_of(repository, live_base, f"origin/{base_branch}")):
        warning = f"local origin/{base_branch} is behind GitHub's; run `{fetch_command}` and run this again"
    changed_files = changed_files_with_classes_and_tiers(
        repository, merge_base, head, hook_registration_old_revision=diff_base)
    tier, tier_reason = review_tier_and_deciding_reason(changed_files)
    posted_reviews = [review for page in review_pages for review in page if review["state"] != "PENDING"]
    inline_counts = {}
    for page in comment_pages:
        for comment in page:
            review_id = comment["pull_request_review_id"]
            inline_counts[review_id] = inline_counts.get(review_id, 0) + 1
    earlier_reviews = [review for review in posted_reviews if review["commit_id"] != head]
    earlier_heads = {review["commit_id"] for review in earlier_reviews}
    earlier = max(earlier_reviews, key=lambda review: (review["submitted_at"], review["id"]))["commit_id"] if earlier_reviews else None
    posting_rule, posting_reason = posting_rule_and_reason_for_author(pull_request["author"]["login"])
    plan = {
        "pull_request": number, "title": pull_request["title"], "url": pull_request["url"], "state": pull_request["state"],
        "head": head, "base_branch": base_branch, "diff_base": diff_base, "diff_base_reason": diff_base_reason,
        "merge_base": merge_base, "origin_main": origin_main, "base_branch_behind_github_warning": warning,
        "merged_tree": merged_tree_against_origin_main(repository, head), "author": pull_request["author"]["login"],
        "posting_rule": posting_rule, "posting_rule_reason": posting_reason, "tier": tier, "tier_decided_by": tier_reason,
        "round": len(earlier_heads) + 1, "fix_round": bool(earlier_heads), "earlier_reviewed_head": earlier,
        "delta_range": f"{earlier}..{head}" if earlier else None, "delta_tier": None, "delta_tier_decided_by": None,
        "delta_files_restricted_to_pull_request_files": False, "delta_only_review_applies": None,
        "delta_only_review_reasons": [], "reviews": [
            {"id": review["id"], "node_id": review["node_id"], "author": review["user"]["login"], "state": review["state"],
             "head": review["commit_id"], "head_relation": "current head" if review["commit_id"] == head else "earlier head",
             "inline_comments": inline_counts.get(review["id"], 0)} for review in posted_reviews],
        "changed_files": changed_files, "delta_files": [],
        "test_files_to_run": test_files_to_run_for_changed_files(repository, head, changed_files),
        "agent_facing_text_whole_pull_request": changed_agent_facing_text_entries(repository, merge_base, head, changed_files),
        "agent_facing_text_delta": [],
    }
    if earlier:
        plan["delta_only_review_applies"] = False
        if not commit_is_in_repository(repository, earlier):
            plan["delta_only_review_reasons"] = [f"the earlier reviewed head {earlier} is not in this repository: the branch was force-pushed, or it was not fetched"]
        else:
            merge_commits = required_git_output(repository, "rev-list", "--merges", "--first-parent", f"{earlier}..{head}").splitlines()
            rewritten = not commit_is_ancestor_of(repository, earlier, head)
            delta_files = changed_files_with_classes_and_tiers(
                repository, earlier, head, hook_registration_old_revision=diff_base)
            if merge_commits or rewritten:
                earlier_merge_base = required_git_output(repository, "merge-base", diff_base, earlier)
                earlier_files = changed_files_with_classes_and_tiers(repository, earlier_merge_base, earlier)
                own_paths = {entry["path"] for entry in changed_files + earlier_files}
                delta_files = [entry for entry in delta_files if entry["path"] in own_paths]
                plan["delta_files_restricted_to_pull_request_files"] = True
            plan["delta_files"] = delta_files
            plan["agent_facing_text_delta"] = changed_agent_facing_text_entries(repository, earlier, head, delta_files)
            plan["delta_tier"], plan["delta_tier_decided_by"] = review_tier_and_deciding_reason(delta_files)
            reasons = plan["delta_only_review_reasons"]
            if merge_commits:
                reasons.append("the delta holds merge commit(s): " + ", ".join(commit[:12] for commit in merge_commits))
            if rewritten:
                reasons.append("the branch's history was rewritten")
            changed_programs = [entry["path"] for entry in delta_files
                                if not path_is_test_file(entry["path"]) and not entry["path"].endswith(".md")
                                and entry["tier"] == "full-reviewer"]
            if changed_programs:
                reasons.append("the delta changes behaviour in a program the earlier round's check exercised: " + ", ".join(changed_programs))
            plan["delta_only_review_applies"] = not reasons
    return plan


def merged_tree_summary(merged_tree):
    if merged_tree["error"]:
        return "could not be computed: " + merged_tree["error"]
    if merged_tree["conflicting_paths"]:
        return "conflict with origin/main in: " + ", ".join(merged_tree["conflicting_paths"])
    return merged_tree["tree"]


def review_summary_line(review):
    return (f"{review['id']} {review['author']} {review['state']} on {review['head'][:12]} "
            f"({review['head_relation']}), {review['inline_comments']} inline comments; node id {review['node_id']}")


def plan_fact_lines(plan):
    lines = [f"head: {plan['head']}", f"base branch: {plan['base_branch']}",
             f"diff base: {plan['diff_base']} ({plan['diff_base_reason']})", f"merge base: {plan['merge_base']}",
             f"origin/main: {plan['origin_main']}" + (f"; WARNING: {plan['base_branch_behind_github_warning']}" if plan['base_branch_behind_github_warning'] else ""),
             f"merged tree: {merged_tree_summary(plan['merged_tree'])}", f"author: {plan['author']}",
             f"posting rule: {plan['posting_rule']}" + (f" ({plan['posting_rule_reason']})" if plan['posting_rule_reason'] else ""),
             f"tier: {plan['tier']}", f"  decided by: {plan['tier_decided_by']}",
             f"round: {plan['round']}" + (" (a fix round)" if plan['fix_round'] else "")]
    if plan["fix_round"]:
        lines.extend([f"  earlier reviewed head: {plan['earlier_reviewed_head']}", f"  delta range: {plan['delta_range']}"
                      + (" (files restricted to the pull request's own files)" if plan['delta_files_restricted_to_pull_request_files'] else ""),
                      f"  delta tier: {plan['delta_tier'] or 'not available'}"])
        if plan["delta_tier_decided_by"]:
            lines.append(f"    decided by: {plan['delta_tier_decided_by']}")
        if plan["delta_only_review_applies"]:
            lines.append(f"  delta-only review: applies: review only {plan['delta_range']}")
        else:
            lines.append("  delta-only review: does not apply:")
            lines.extend(f"    - {reason}" for reason in plan["delta_only_review_reasons"])
    return lines


def changed_lines_for_agent_text_entry(entry):
    if entry["old_text"] is None or entry["new_text"] is None:
        return None
    old_lines = entry["old_text"].splitlines()
    new_lines = entry["new_text"].splitlines()
    if max(len(old_lines), len(new_lines)) <= 8:
        return None
    return list(difflib.unified_diff(old_lines, new_lines, lineterm="", n=2))[2:]


def render_text_agent_entries(entries):
    lines = []
    for entry in entries:
        lines.append(f"  {entry['path']}:{entry['line']} {entry['label']}")
        changed_lines = changed_lines_for_agent_text_entry(entry)
        if changed_lines is not None:
            lines.append("    changed lines:")
            lines.extend("      " + line for line in changed_lines)
            continue
        for field, label in (("old_text", "old"), ("new_text", "new")):
            text_lines = (entry[field] if entry[field] is not None else "none").split("\n")
            lines.append(f"    {label}: {text_lines[0]}")
            lines.extend("         " + line for line in text_lines[1:])
    return lines or ["  none"]


def render_pull_request_review_plan_text(plan):
    lines = [f"pull request {plan['pull_request']}: {plan['title']} ({plan['state']})", f"url: {plan['url']}", *plan_fact_lines(plan), "reviews:"]
    lines.extend(["  " + review_summary_line(review) for review in plan["reviews"]] or ["  none"])
    for heading, files in [("changed files", plan["changed_files"])] + ([("delta files", plan["delta_files"])] if plan["fix_round"] else []):
        lines.append(heading + ":")
        lines.extend([f"  {entry['class']:<8} {entry['tier']:<15} {entry['path']} ({entry['status']}): {entry['reason']}" for entry in files] or ["  none"])
    lines.append("test files to run:")
    lines.extend(["  " + path for path in plan["test_files_to_run"]] or ["  none"])
    lines.append(f"agent-facing text, whole pull request ({plan['merge_base'][:12]}..{plan['head'][:12]}):")
    lines.extend(render_text_agent_entries(plan["agent_facing_text_whole_pull_request"]))
    if plan["fix_round"]:
        lines.append(f"agent-facing text, this round's delta ({plan['earlier_reviewed_head'][:12]}..{plan['head'][:12]}):")
        lines.extend(render_text_agent_entries(plan["agent_facing_text_delta"]))
    return "\n".join(lines) + "\n"


def markdown_fenced_text_lines(text, info_string=""):
    text = "none" if text is None else text
    longest_backtick_run = max((len(match[0]) for match in re.finditer(r"`+", text)), default=0)
    fence = "`" * max(3, longest_backtick_run + 1)
    return [fence + info_string, text, fence]


def render_pull_request_brief_skeleton(plan):
    lines = [f"## Pull request {plan['pull_request']}: {plan['title']}", "", plan["url"], ""]
    lines.extend("- " + line.strip().removeprefix("- ") for line in plan_fact_lines(plan))
    lines.extend(["", "### Reviews", ""])
    lines.extend(["- " + review_summary_line(review) for review in plan["reviews"]] or ["none"])
    for heading, entries in [("Changed files", plan["changed_files"])] + ([("Delta files", plan["delta_files"])] if plan["fix_round"] else []):
        lines.extend(["", "### " + heading, ""])
        lines.extend([f"- {entry['path']} ({entry['status']}): {entry['class']}, {entry['tier']}; {entry['reason']}" for entry in entries] or ["none"])
    lines.extend(["", "### Test files to run", ""])
    lines.extend(["- " + path for path in plan["test_files_to_run"]] or ["none"])
    lines.extend(["", "### Agent-facing text", ""])
    groups = [("Whole pull request", plan["merge_base"], plan["agent_facing_text_whole_pull_request"])]
    if plan["fix_round"]:
        groups.append(("This round's delta", plan["earlier_reviewed_head"], plan["agent_facing_text_delta"]))
    for heading, old_revision, entries in groups:
        lines.extend([f"#### {heading} ({old_revision[:12]}..{plan['head'][:12]})", ""])
        if not entries:
            lines.extend(["none", ""])
        for entry in entries:
            lines.extend([f"{entry['path']}:{entry['line']} {entry['label']}", ""])
            changed_lines = changed_lines_for_agent_text_entry(entry)
            if changed_lines is not None:
                lines.extend(["changed lines:", *markdown_fenced_text_lines("\n".join(changed_lines), "diff"), ""])
            else:
                lines.extend(["Old:", *markdown_fenced_text_lines(entry["old_text"]), "", "New:",
                              *markdown_fenced_text_lines(entry["new_text"]), ""])
    return "\n".join(lines + ["### What to check", "", ""])


def write_brief_skeleton_exclusively(path, text):
    try:
        with open(path, "x", encoding="utf-8") as handle:
            handle.write(text)
    except FileExistsError as failure:
        raise ReviewPlanRefusal(f"the brief skeleton at {path} already exists, so writing it was stopped to preserve the seat's checks.\n"
                                "To write another skeleton: choose a new --brief-skeleton path.") from failure
    except OSError as failure:
        raise ReviewPlanRefusal(f"the brief skeleton at {path} could not be written: {failure.strerror}.\n"
                                "If the directory is missing or unwritable: choose an existing writable directory, then run this again.") from failure


def build_review_plan_argument_parser():
    parser = RefusingArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pull-request", type=int, required=True, metavar="N")
    parser.add_argument("--repository", type=Path, default=Path.cwd(), metavar="DIR")
    parser.add_argument("--github-repository", default="nedschorus/nedschorus", metavar="OWNER/NAME")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--brief-skeleton", type=Path, metavar="PATH")
    return parser


def main(argv=None):
    try:
        arguments = build_review_plan_argument_parser().parse_args(argv)
        if arguments.pull_request <= 0:
            raise ReviewPlanRefusal(f"--pull-request is not positive ({arguments.pull_request}), so no plan was computed.\n"
                                    "To select a pull request: use a positive integer, then run this again.")
        if re.fullmatch(r"[^/\s]+/[^/\s]+", arguments.github_repository) is None:
            raise ReviewPlanRefusal("--github-repository is not OWNER/NAME, so no plan was computed.\n"
                                    "To select a GitHub repository: pass OWNER/NAME, then run this again.")
        if arguments.brief_skeleton is not None:
            if os.path.lexists(arguments.brief_skeleton):
                raise ReviewPlanRefusal(f"the brief skeleton at {arguments.brief_skeleton} already exists, so writing it was stopped to preserve the seat's checks.\n"
                                        "To write another skeleton: choose a new --brief-skeleton path.")
            if not arguments.brief_skeleton.parent.is_dir():
                raise ReviewPlanRefusal(f"the directory for brief skeleton {arguments.brief_skeleton} does not exist, so no skeleton was written.\n"
                                        "To write a skeleton: choose an existing directory, then run this again.")
        plan = compute_pull_request_review_plan(arguments)
        if arguments.brief_skeleton is not None:
            write_brief_skeleton_exclusively(arguments.brief_skeleton, render_pull_request_brief_skeleton(plan))
        sys.stdout.write(json.dumps(plan, indent=2) + "\n" if arguments.json else render_pull_request_review_plan_text(plan))
        return 0
    except ReviewPlanRefusal as refusal:
        print(f"pull-request-review-plan: {refusal}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as defect:
        print(f"pull-request-review-plan: program defect: {type(defect).__name__}: {defect}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(2)
