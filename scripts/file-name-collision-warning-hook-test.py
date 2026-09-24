#!/usr/bin/env python3
"""Tests for file-name-collision-warning-hook.py.

Run: python3 scripts/file-name-collision-warning-hook-test.py
Prints one line per case and exits non-zero if any case fails.

Most cases run the hook as a program against a throwaway repository under a
temporary directory. The timeout cases also import it as a module, because
what arguments it hands subprocess.run, and what it does when a call times
out, cannot be seen from outside the process.

The last case is different in kind: it asserts the property on THIS
repository -- that no two tracked files share a name -- and is the half of
the ruling a hook cannot cover, because a file created by git mv, by a shell
copy, or by a program that writes its own files never passes through the
Edit or Write tools. It runs over a planted collision in a throwaway
repository first, for the reason below.

THE FIRST CASE IS THE POSITIVE ONE, deliberately. A check that has never
been shown able to say "something here" is worth nothing when it says
"nothing here"; that failure has been found repeatedly across this fleet, so
the instrument proves it can warn before any case asserts silence.
"""

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path, PurePath

SCRIPT_PATH = Path(__file__).with_name("file-name-collision-warning-hook.py")
REPOSITORY_ROOT = Path(__file__).resolve().parent.parent

# The hook as a module as well as a program: the timeout cases below ask what
# arguments it hands subprocess.run and what it does when a call times out,
# neither of which is visible from outside the process.
HOOK_MODULE_SPEC = importlib.util.spec_from_file_location(
    "file_name_collision_warning_hook", SCRIPT_PATH)
HOOK_MODULE = importlib.util.module_from_spec(HOOK_MODULE_SPEC)
HOOK_MODULE_SPEC.loader.exec_module(HOOK_MODULE)

# Named here rather than read from the hook: a test that asks the code under
# test which names are exempt cannot notice the set changing.
EXEMPT_FILE_NAMES_IN_TEST = {"skill.md", "readme.md", ".gitkeep"}

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def git(arguments, cwd: Path):
    return subprocess.run(["git", *arguments], cwd=str(cwd),
                          capture_output=True, text=True, check=False)


def commit_file(repository: Path, name: str, content: str = "x\n"):
    (repository / name).parent.mkdir(parents=True, exist_ok=True)
    (repository / name).write_text(content, encoding="utf-8")
    git(["add", "--", name], repository)
    git(["commit", "-q", "-m", f"add {name}"], repository)


def write_file(repository: Path, name: str, content: str = "new\n") -> Path:
    """A file on disk that git does not know about: what an agent's Write
    leaves behind before anyone commits."""
    target = repository / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def hook_payload(cwd, file_path, tool_name="Write") -> dict:
    """The shape a PostToolUse hook is handed: the session's own cwd, the
    tool's name, and tool_input.file_path -- absolute for both Edit and
    Write."""
    return {
        "session_id": "file-name-collision-warning-test-session",
        "transcript_path": "/dev/null",
        "cwd": str(cwd),
        "hook_event_name": "PostToolUse",
        "tool_name": tool_name,
        "tool_input": {"file_path": str(file_path)},
        "tool_response": {"filePath": str(file_path), "success": True},
    }


def run_hook(payload):
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run([sys.executable, str(SCRIPT_PATH)], input=text,
                          capture_output=True, text=True, check=False,
                          env=dict(os.environ))


def agent_text(result) -> str:
    """What the AGENT was told. Plain stdout on a PostToolUse hook reaches
    the debug log and nobody else; only hookSpecificOutput.additionalContext
    arrives."""
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError:
        return ""
    if not isinstance(parsed, dict):
        return ""
    return parsed.get("hookSpecificOutput", {}).get("additionalContext", "")


def silent(result) -> bool:
    return result.returncode == 0 and result.stdout.strip() == ""


with tempfile.TemporaryDirectory() as temporary_directory:
    tmp = Path(temporary_directory).resolve()
    repository = tmp / "checkout"
    repository.mkdir()
    git(["init", "-q", "-b", "main"], repository)
    git(["config", "user.email", "test@example.invalid"], repository)
    git(["config", "user.name", "file-name-collision test"], repository)

    commit_file(repository, "scripts/cold-read-grid.py")
    commit_file(repository, "scripts/only-one-of-these.py")
    # Hard-linked under a case variant below, and nothing else.
    commit_file(repository, "docs/hard-linked-notes.md")
    # A tracked name carrying uppercase, which the repository really has --
    # AGENTS.md, CLAUDE.md, engineering-code-review-SKILL.md. Without one,
    # only the fold on the written side is ever exercised.
    commit_file(repository, "docs/Design-To-Main-Notes.md")
    commit_file(repository, ".claude/skills/walk-me-through/SKILL.md")
    commit_file(repository, "docs/README.md")
    commit_file(repository, "nc-queue/.gitkeep")
    commit_file(repository, ".gitignore", "docs/walk/\ncold-read-records/\n")

    # --- the instrument can say "something here" ------------------------
    colliding = write_file(repository, "nc-systems/cold-read/cold-read-grid.py")
    warned = run_hook(hook_payload(repository, colliding))
    warning = agent_text(warned)
    check("a new file whose name is already a tracked file's warns",
          warning != "", f"stdout was {warned.stdout!r}")
    check("the warning names BOTH paths, so no search is needed",
          "nc-systems/cold-read/cold-read-grid.py" in warning
          and "scripts/cold-read-grid.py" in warning, warning)
    check("the warning arrives on additionalContext under PostToolUse",
          (json.loads(warned.stdout or "{}").get("hookSpecificOutput", {})
           .get("hookEventName")) == "PostToolUse", warned.stdout)
    check("the hook exits 0 even when it warns (a warning never fails a turn)",
          warned.returncode == 0, str(warned.returncode))

    # --- the two instructions, each with its condition -------------------
    # The wording the user approved on 2026-09-22 has a break at each
    # instruction boundary, and CLAUDE.md asks for one instruction to a line
    # in text an agent reads at the moment it acts. Until 2026-09-23 the
    # three arrived as one physical line, which substring assertions could
    # not see, so the count is pinned here and the lines are read by index.
    warning_lines = warning.split("\n")
    check("the warning arrives as three lines, one instruction to a line",
          len(warning_lines) == 3, repr(warning))
    padded_warning_lines = warning_lines + ["", "", ""]
    check("line 1 is the fact, and it names both paths",
          padded_warning_lines[0].startswith("file-name-collision-warning: "
                                             "you wrote"),
          repr(padded_warning_lines[0]))
    check("line 2 tells a mover to delete the old path, naming it",
          padded_warning_lines[1] == "If you are moving the file, delete "
          "scripts/cold-read-grid.py in this change.",
          repr(padded_warning_lines[1]))
    check("line 3 points at CLAUDE.md's naming rule instead of restating it",
          padded_warning_lines[2].startswith(
              "If both files are meant to exist, rename the one you just "
              "wrote by CLAUDE.md's naming rule")
          and "3 or 4 parts" not in warning and "three or four" not in warning,
          repr(padded_warning_lines[2]))

    # --- silence, each for its own reason --------------------------------
    fresh = write_file(repository, "scripts/nothing-shares-this-name.py")
    check("a name that matches no tracked file is silent",
          silent(run_hook(hook_payload(repository, fresh))))

    existing = repository / "scripts" / "only-one-of-these.py"
    check("editing the only file with that name is silent",
          silent(run_hook(hook_payload(repository, existing, "Edit"))))

    for exempt in ("nc-systems/handoff/SKILL.md", "scripts/README.md",
                   "docs/.gitkeep"):
        written = write_file(repository, exempt)
        check(f"the exempt name {Path(exempt).name} is silent",
              silent(run_hook(hook_payload(repository, written))))

    ignored = write_file(repository,
                         "docs/walk/cold-read-grid.py")
    check("a write inside a gitignored directory is silent",
          silent(run_hook(hook_payload(repository, ignored))))

    outside = tmp / "scratchpad" / "cold-read-grid.py"
    outside.parent.mkdir(parents=True, exist_ok=True)
    outside.write_text("scratch\n", encoding="utf-8")
    check("a write outside the checkout is silent",
          silent(run_hook(hook_payload(repository, outside))))

    not_a_repository = tmp / "loose"
    not_a_repository.mkdir()
    loose_file = not_a_repository / "cold-read-grid.py"
    loose_file.write_text("loose\n", encoding="utf-8")
    check("a session seated outside any checkout is silent",
          silent(run_hook(hook_payload(not_a_repository, loose_file))))

    # --- letter case: two files, or one file spelled two ways ------------
    # The positive pair comes first: both sides of the comparison are folded,
    # so each side gets a case whose tracked fixture carries the uppercase.
    # Then the distinction that is not about case at all -- whether there are
    # two files -- which the filesystem answers and the platform does not.
    cased = write_file(repository, "nc-systems/Cold-Read-Grid.PY")
    check("a written name differing only in letter case warns",
          agent_text(run_hook(hook_payload(repository, cased))) != "",
          "the fold on the WRITTEN side did not fire")

    lowercased = write_file(repository, "nc-systems/design-to-main-notes.md")
    check("a TRACKED name differing only in letter case warns",
          agent_text(run_hook(hook_payload(repository, lowercased))) != "",
          "the fold on the TRACKED side did not fire")

    # One file named twice, not two files. On a filesystem that folds case
    # -- the Mac's does, ned-box's does not -- this write lands on the
    # tracked file, so the directory still holds one entry and there is no
    # collision. Which branch runs is read off the disk, not off the
    # platform and not off the hook's own answer.
    variant = repository / "scripts" / "Only-One-Of-These.py"
    variant.write_text("case variant\n", encoding="utf-8")
    entries_after_the_variant_write = set(os.listdir(repository / "scripts"))
    variant_result = run_hook(hook_payload(repository, variant))
    if "Only-One-Of-These.py" in entries_after_the_variant_write:
        check("a case variant is a second file where case is kept, and warns",
              agent_text(variant_result) != "",
              f"two entries on disk, hook said {variant_result.stdout!r}")
    else:
        check("a case variant is the same file where case is folded, "
              "and is silent",
              silent(variant_result),
              f"one entry on disk, hook said {variant_result.stdout!r}")

    # The same question with the answer fixed to ONE file on every machine.
    # The case above takes its folded branch only on a filesystem that folds
    # case, so on ned-box, where every full sweep runs, nothing reached
    # is_the_same_file_on_this_filesystem(): with its samefile() call replaced
    # by `return False` this suite still passed there (mac-claude's inline
    # finding on PR nedschorus#641, review 5294748911, 2026-09-23). A hard
    # link is one file under two spellings, which is what samefile() sees
    # where case is folded. Where case IS folded, the link is refused because
    # the variant spelling already names the tracked file -- one file under
    # two spellings before any link is made -- so both machines end with the
    # fixture this case needs.
    linked_tracked = repository / "docs" / "hard-linked-notes.md"
    linked_variant = repository / "docs" / "Hard-Linked-Notes.md"
    try:
        os.link(linked_tracked, linked_variant)
        link_detail = "hard link made"
    except FileExistsError:
        link_detail = "the variant spelling already named the tracked file"
    except OSError as link_refused:
        link_detail = f"os.link failed: {link_refused!r}"
    try:
        one_file_two_spellings = linked_variant.samefile(linked_tracked)
    except OSError as stat_refused:
        one_file_two_spellings = False
        link_detail += f"; samefile failed: {stat_refused!r}"
    check("the hard-link fixture is one file under two spellings",
          one_file_two_spellings, link_detail)
    linked_result = run_hook(hook_payload(repository, linked_variant))
    check("one file under two spellings is silent on every filesystem "
          "(hard link)",
          silent(linked_result),
          f"{link_detail}; hook said {linked_result.stdout!r}")

    # --- a slow git may not cost the turn ---------------------------------
    # The hook runs at every Edit and every Write, so each git call is
    # bounded. The recorder runs the hook in process and delegates to the
    # real subprocess.run, so it sees every git call the file makes --
    # including one a later change adds.
    recorded_git_calls = []
    real_subprocess_run = subprocess.run

    def recording_subprocess_run(*arguments, **keywords):
        if arguments and arguments[0] and arguments[0][0] == "git":
            recorded_git_calls.append(keywords)
        return real_subprocess_run(*arguments, **keywords)

    original_stdin = sys.stdin
    recorded_stdout = io.StringIO()
    HOOK_MODULE.subprocess.run = recording_subprocess_run
    try:
        sys.stdin = io.StringIO(
            json.dumps(hook_payload(repository, colliding)))
        with redirect_stdout(recorded_stdout):
            in_process_exit_code = HOOK_MODULE.main()
    finally:
        HOOK_MODULE.subprocess.run = real_subprocess_run
        sys.stdin = original_stdin

    # THE POSITIVE HALF: the recorder saw the git calls. Without it the next
    # case would pass over an empty list, which is the very defect the last
    # case in this file was fixed for.
    check("the recorder sees the hook's git calls (rev-parse, check-ignore, "
          "ls-files)",
          len(recorded_git_calls) == 3, f"{len(recorded_git_calls)} recorded")
    check("the hook run in process still warns and still exits 0",
          "file-name-collision-warning" in recorded_stdout.getvalue()
          and in_process_exit_code == 0,
          repr(recorded_stdout.getvalue()))
    check("every git call the hook makes carries a positive timeout",
          bool(recorded_git_calls) and all(
              isinstance(call.get("timeout"), (int, float))
              and not isinstance(call.get("timeout"), bool)
              and call["timeout"] > 0 for call in recorded_git_calls),
          repr([call.get("timeout") for call in recorded_git_calls]))

    # A timeout raises subprocess.TimeoutExpired, which is a SubprocessError
    # and NOT an OSError, so passing timeout= without naming it in the except
    # clauses would turn a slow git into a traceback.
    answered_listing = HOOK_MODULE.git_output(["ls-files", "-z"], repository)
    check("git_output returns git's answer when git answers",
          answered_listing is not None
          and "scripts/cold-read-grid.py" in answered_listing,
          repr(answered_listing))
    check("is_ignored answers True for a path .gitignore covers",
          HOOK_MODULE.is_ignored(PurePath("docs/walk/cold-read-grid.py"),
                                 repository))

    def timing_out_subprocess_run(*arguments, **keywords):
        raise subprocess.TimeoutExpired(cmd=["git"], timeout=1)

    def answer_or_the_escape(call):
        """What the call returned, or the exception it let past. A timeout
        that escapes is this suite's finding to report, not its own crash."""
        try:
            return call()
        except subprocess.TimeoutExpired:
            return "subprocess.TimeoutExpired escaped the hook"

    HOOK_MODULE.subprocess.run = timing_out_subprocess_run
    try:
        timed_out_listing = answer_or_the_escape(
            lambda: HOOK_MODULE.git_output(["ls-files", "-z"], repository))
        timed_out_ignore = answer_or_the_escape(
            lambda: HOOK_MODULE.is_ignored(
                PurePath("docs/walk/cold-read-grid.py"), repository))
    finally:
        HOOK_MODULE.subprocess.run = real_subprocess_run
    check("a git call that times out is git failing, not git saying nothing",
          timed_out_listing is None, repr(timed_out_listing))
    check("a check-ignore that times out is caught, not raised at the agent",
          timed_out_ignore is False, repr(timed_out_ignore))

    # --- malformed payloads cost nothing and say nothing ------------------
    check("a payload that is not JSON exits 0 and prints nothing",
          silent(run_hook("not json at all")))
    no_tool_input = hook_payload(repository, colliding)
    del no_tool_input["tool_input"]
    check("a payload with no tool_input exits 0 and prints nothing",
          silent(run_hook(no_tool_input)))
    no_cwd = hook_payload(repository, colliding)
    del no_cwd["cwd"]
    check("a payload with no cwd exits 0 and prints nothing",
          silent(run_hook(no_cwd)))
    empty_path = hook_payload(repository, colliding)
    empty_path["tool_input"] = {"file_path": ""}
    check("a payload with an empty file_path exits 0 and prints nothing",
          silent(run_hook(empty_path)))

# --- the half a hook cannot cover: this repository, as it stands ---------
# THE POSITIVE CASE COMES FIRST here too, and until 2026-09-23 it did not
# exist: git ls-files was run with its return code unread, so a repository
# that could not be listed produced no names, no collisions, and a PASS over
# zero files. A failure to look and a look that found nothing read the same.
# tracked_name_collisions() now raises on both, and a planted collision in a
# throwaway repository is what shows it can still say "something here".
def tracked_name_collisions(repository_root: Path):
    """(every tracked name, the names belonging to more than one file).

    Raises when git does not answer and when it lists nothing: the hook
    draws that same line in git_output(), where None is "git failed" and
    never "git found nothing", and this case is worth nothing without it.
    """
    listed = subprocess.run(["git", "ls-files", "-z"],
                            cwd=str(repository_root), capture_output=True,
                            text=True, check=False)
    if listed.returncode != 0:
        raise RuntimeError(
            f"git ls-files exited {listed.returncode} in {repository_root}: "
            f"{listed.stderr.strip()}")
    names = {}
    for tracked in listed.stdout.split("\0"):
        if tracked:
            names.setdefault(Path(tracked).name.lower(), []).append(tracked)
    if not names:
        raise RuntimeError(
            f"git ls-files listed no tracked file in {repository_root}")
    return names, {name: paths for name, paths in names.items()
                   if len(paths) > 1 and name not in EXEMPT_FILE_NAMES_IN_TEST}


with tempfile.TemporaryDirectory() as planted_temporary_directory:
    planted = Path(planted_temporary_directory).resolve() / "checkout"
    planted.mkdir()
    git(["init", "-q", "-b", "main"], planted)
    git(["config", "user.email", "test@example.invalid"], planted)
    git(["config", "user.name", "file-name-collision test"], planted)
    commit_file(planted, "scripts/named-twice-on-purpose.py")
    commit_file(planted, "nc-systems/named-twice-on-purpose.py")
    commit_file(planted, "docs/README.md")
    commit_file(planted, "nc-queue/README.md")
    planted_failure = ""
    planted_names, planted_collisions = {}, {}
    try:
        planted_names, planted_collisions = tracked_name_collisions(planted)
    except RuntimeError as unanswered:
        planted_failure = str(unanswered)
    check("the repository-wide check reports a planted collision",
          sorted(planted_collisions) == ["named-twice-on-purpose.py"]
          and sorted(planted_collisions["named-twice-on-purpose.py"]) == [
              "nc-systems/named-twice-on-purpose.py",
              "scripts/named-twice-on-purpose.py"],
          planted_failure or repr(planted_collisions))
    check("the repository-wide check lets the exempt names repeat",
          "readme.md" in planted_names
          and "readme.md" not in planted_collisions,
          planted_failure or repr(sorted(planted_names)))

    unlistable = Path(planted_temporary_directory).resolve() / "not-a-checkout"
    unlistable.mkdir()
    try:
        tracked_name_collisions(unlistable)
    except RuntimeError as unanswered:
        check("a repository git cannot list is a failure, not a clean result",
              "git ls-files exited" in str(unanswered), str(unanswered))
    else:
        check("a repository git cannot list is a failure, not a clean result",
              False, "tracked_name_collisions returned instead of raising")

try:
    tracked_names, collisions = tracked_name_collisions(REPOSITORY_ROOT)
except RuntimeError as unanswered:
    check("no two tracked files in this repository share a name", False,
          str(unanswered))
else:
    check("no two tracked files in this repository share a name",
          not collisions,
          f"over {len(tracked_names)} names: " + "; ".join(
              f"{name}: {', '.join(paths)}"
              for name, paths in sorted(collisions.items())))

print()
if failures:
    print(f"{len(failures)} case(s) failed")
    sys.exit(1)
print("all cases passed")
