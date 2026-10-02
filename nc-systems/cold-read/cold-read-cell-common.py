#!/usr/bin/env python3
"""Shared cold-read-cell execution; launchers supply runtime-specific invocations."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time
import typing

import importlib.util

_record_names_spec = importlib.util.spec_from_file_location(
    "cold_read_record_names",
    pathlib.Path(__file__).with_name("cold-read-record-names.py"))
record_names = importlib.util.module_from_spec(_record_names_spec)
_record_names_spec.loader.exec_module(record_names)

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
PROMPTS_DIR = REPO_ROOT / ".claude" / "skills" / "cold-read" / "prompts"


CELL_CHOICES = ["restate", "defect-hunt", "fast-clarify", "terminology"]
# The judge reads four files per case and needs its own prompt and fixed tier.
TIER_CHOICES = ["deep", "second", "fast"]

# Draft prompts need free labels; labels become report filename tokens.
PROMPT_FILE_CELL_LABEL_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


# EX_USAGE distinguishes launcher refusals from runtime command-line errors (Codex exits 2).
EXIT_BAD_INVOCATION = 64


class CellRefusal(Exception):
    """A refusal carrying its remedy and exit code."""

    def __init__(self, message: str, exit_code: int = EXIT_BAD_INVOCATION):
        super().__init__(message)
        self.exit_code = exit_code


# The keychain remains accessible because masking it logs the agent-binaries out.
CREDENTIAL_DIRECTORIES = (
    pathlib.Path.home() / ".config" / "nedschorus",
    pathlib.Path.home() / ".config" / "gh",
    pathlib.Path.home() / ".ssh",
)
CREDENTIAL_FILE_NAME_PATTERNS = ("*.token", ".env")

# agy reads its login inside its sandbox; Claude and Codex authenticate outside model tools.
REVIEWER_PROGRAM_LOGIN_FILES = {
    "claude": (pathlib.Path.home() / ".claude" / ".credentials.json",),
    "codex": (pathlib.Path.home() / ".codex" / "auth.json",),
    "agy": (pathlib.Path.home() / ".gemini" / "jetski-standalone-oauth-token",
            pathlib.Path.home() / ".gemini" / "oauth_creds.json",
            pathlib.Path.home() / ".gemini" / "antigravity-cli" / "antigravity-oauth-token"),
}


def reviewer_program_login_files(except_program: str = None,
                                 only_present: bool = False) -> list:
    """Return login paths, optionally excluding one program and absent files."""
    # Masking a missing path on Linux can create a mount point on the real disk.
    return [str(path) for program, paths in REVIEWER_PROGRAM_LOGIN_FILES.items()
            if program != except_program
            for path in paths if not only_present or path.is_file()]


def credential_directories_present() -> list:
    return [str(directory) for directory in CREDENTIAL_DIRECTORIES
            if directory.is_dir()]

# Exclude /tmp: disappearing test fixtures can be recreated as sandbox mount points
# or prevent the sandbox from starting.
CREDENTIAL_FILE_SCAN_ROOTS = (pathlib.Path.home(), REPO_ROOT)


def credential_files_found_now() -> list:
    """Return credential-named files outside directories already withheld whole."""
    # find is faster over large homes; unreadable directories are expected, so errors are ignored.
    name_tests = []
    for pattern in CREDENTIAL_FILE_NAME_PATTERNS:
        name_tests += (["-o"] if name_tests else []) + ["-name", pattern]
    roots = []
    for root in CREDENTIAL_FILE_SCAN_ROOTS:
        if root.is_dir() and not any(root == kept or kept in root.parents
                                     for kept in roots):
            roots.append(root)
    completed = subprocess.run(
        ["find", *map(str, roots), "-xdev", "(", *name_tests, ")", "-type", "f"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=False)
    return sorted(
        path for path in set(completed.stdout.splitlines())
        if path and not any(directory == pathlib.Path(path)
                            or directory in pathlib.Path(path).parents
                            for directory in CREDENTIAL_DIRECTORIES))


def codex_credential_denying_permission_profile_arguments(
        profile_name: str, extends: str, platform: str = sys.platform,
        network: bool = False) -> list:
    """Return Codex permission-profile overrides denying credential paths."""
    # JSON string escaping also works for TOML basic strings used as path keys.
    entries = ({":slash_tmp": "read", ":tmpdir": "read"}
               if platform.startswith("linux") and extends == ":workspace" else {})
    denied = credential_directories_present()
    denied += reviewer_program_login_files(only_present=True)
    if platform.startswith("linux"):
        denied += credential_files_found_now()
    else:
        denied += [f"/**/{pattern}" for pattern in CREDENTIAL_FILE_NAME_PATTERNS]
    entries.update((path, "deny") for path in denied)
    table = "{" + ",".join(f"{json.dumps(path)}={json.dumps(access)}"
                           for path, access in entries.items()) + "}"
    arguments = [
        "-c", f'default_permissions="{profile_name}"',
        "-c", f'permissions.{profile_name}.extends="{extends}"',
    ]
    if network:
        arguments += ["-c", f"permissions.{profile_name}.network.enabled=true"]
    return arguments + ["-c", f"permissions.{profile_name}.filesystem={table}"]


class BadInvocationArgumentParser(argparse.ArgumentParser):
    """Use the launcher refusal code to distinguish argparse errors from runtime errors."""

    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(EXIT_BAD_INVOCATION, f"{self.prog}: error: {message}\n")


def build_argument_parser(
    description: str, model_help: str, tier_choices=tuple(TIER_CHOICES),
) -> argparse.ArgumentParser:
    parser = BadInvocationArgumentParser(
        description=description, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    # Validation depends on --prompt-file, which argparse cannot see in choices=.
    parser.add_argument(
        "--cell", required=True,
        help=f"the pass to run, one of {', '.join(CELL_CHOICES)}; with "
             "--prompt-file, any label of lowercase letters and digits joined "
             "by single hyphens, which names the report",
    )
    parser.add_argument("--tier", required=True, choices=list(tier_choices))
    parser.add_argument(
        "--target", required=True,
        help="document path, relative to the repo root or absolute",
    )
    parser.add_argument(
        "--target-origin", metavar="PATH",
        help="the file --target was copied from, when --target is a frozen "
             "copy; the prompt then tells the reviewer to resolve the "
             "document's relative references from this file's directory, "
             "since nothing else was copied beside the target. Relative to "
             "the repo root or absolute; not required to exist, so a retry "
             "still runs after the original moved.",
    )
    parser.add_argument(
        "--report", required=True,
        help="file the reviewer writes its findings to; the caller names it, "
             "and a run that leaves it absent or empty fails",
    )
    parser.add_argument("--model", help=model_help)
    parser.add_argument(
        "--effort", choices=["low", "medium", "high", "xhigh", "max"],
        help="reasoning effort, overriding the tier mapping. Honored exactly, "
             "with no fallback, the way --model is: a caller who names an "
             "effort is answering the question the tier map exists to answer, "
             "and quietly running the mapped level instead would defeat the "
             "request. The fast tier's own launcher "
             "(nc-systems/cold-read/cold-read-agy-cell.py) pins medium; on the Claude and "
             "Codex launchers a low-effort run goes through this flag.",
    )
    parser.add_argument(
        "--prompt-file", metavar="PATH",
        help="read the prompt template from this file instead of the "
             "cell's own, .claude/skills/cold-read/prompts/<cell>.md, "
             "with the same "
             "{TARGET_PATH} and {REPORT_PATH} substitution; relative to the "
             "repository root unless absolute. --cell is still required and "
             "still names the report. This is how a draft prompt is trialled "
             "through the ordinary launcher: on 2026-09-04, 24 trial cells "
             "exited 64 because the only template a cell would read was the "
             "one under prompts/. The stamp records the file's path.",
    )
    return parser


def validate_cell(cell: str, prompt_file_argument) -> None:
    if not prompt_file_argument:
        if cell not in CELL_CHOICES:
            raise CellRefusal(
                f"--cell must be one of {', '.join(CELL_CHOICES)} (got {cell!r}); "
                "a cell name outside that list runs only with --prompt-file, "
                "which names the draft template it reads")
        return
    if not PROMPT_FILE_CELL_LABEL_PATTERN.match(cell):
        raise CellRefusal(
            f"--cell {cell!r} cannot name a report: with --prompt-file the cell "
            "name is a free label that becomes a token of the report's file "
            "name, and must be lowercase letters and digits joined by single "
            "hyphens, like terminology-v9")


def resolve_target(target_argument: str) -> pathlib.Path:
    target = pathlib.Path(target_argument)
    if not target.is_absolute():
        target = REPO_ROOT / target
    if not target.is_file():
        raise CellRefusal(f"target not found: {target}")
    return target


def resolve_report_path(report_argument: str) -> pathlib.Path:
    """Return an absolute report path with any previous report removed."""
    # A stale report would make a run that wrote nothing appear successful.
    report = pathlib.Path(report_argument)
    if not report.is_absolute():
        report = REPO_ROOT / report
    if report.exists() and not report.is_file():
        raise CellRefusal(f"report path is not a file: {report}")
    report.parent.mkdir(parents=True, exist_ok=True)
    report.unlink(missing_ok=True)
    return report


def resolve_prompt_file(prompt_file_argument: str) -> pathlib.Path:
    prompt_file = pathlib.Path(prompt_file_argument)
    if not prompt_file.is_absolute():
        prompt_file = REPO_ROOT / prompt_file
    if not prompt_file.is_file():
        raise CellRefusal(f"prompt file not found: {prompt_file}")
    return prompt_file


def resolve_target_origin(target_origin_argument) -> typing.Optional[pathlib.Path]:
    """Return the absolute reference origin, or None."""
    # The origin only resolves references; moving the original must not prevent a retry.
    if not target_origin_argument:
        return None
    origin = pathlib.Path(target_origin_argument)
    return origin if origin.is_absolute() else REPO_ROOT / origin


def target_origin_paragraph(target: pathlib.Path, target_origin: pathlib.Path) -> str:
    """Return reference-resolution instructions for a frozen target."""
    # Append outside the template so draft prompts also receive the same resolution order.
    return (
        f"\n\n{target} is a frozen copy of {target_origin}. Read the copy for "
        f"the document's text. Resolve each relative path the document "
        f"references from the repository root, {REPO_ROOT}, and when it does "
        f"not exist there, from {target_origin.parent}, the original's "
        f"directory. Never resolve one from the copy's directory.\n"
    )


def compose_prompt(
    cell: str, target: pathlib.Path, report: pathlib.Path, prompt_file=None,
    target_origin=None,
) -> str:
    template_path = (prompt_file if prompt_file is not None
                     else PROMPTS_DIR / f"{cell}.md")
    if not template_path.is_file():
        raise CellRefusal(f"prompt template missing: {template_path}")
    prompt = (
        template_path.read_text(encoding="utf-8")
        .replace("{TARGET_PATH}", str(target))
        .replace("{REPORT_PATH}", str(report))
    )
    if target_origin is not None:
        prompt += target_origin_paragraph(target, target_origin)
    return prompt


class WriteDetectorUnavailable(Exception):
    """The write detector could not check; this is distinct from finding no writes."""


# The grid parses these phrases only after the program prefix, avoiding quoted model text.
# Failure causes explain results; only report presence determines retry decisions.
CAUSE_PHRASE = "cause:"
CAUSE_SEPARATOR = " — "
# Match line starts to avoid quoted document text, allowing the Codex tracing timestamp.
AGENT_BINARY_WIDE_CAUSE_CLASSES = frozenset(
    {"account-limit", "logged-out", "agent-binary-missing"})
USER_CLEARABLE_CAUSE_CLASSES = frozenset(
    {"logged-out", "agent-binary-missing", "account-limit", "model-limit"})
CAUSE_DETAIL_MAX_CHARACTERS = 120
# Drop per-attempt timestamps from details that the grid reports for an entire agent-binary.
DETAIL_IS_REST_OF_LINE = "rest-of-line"
DETAIL_IS_WHOLE_LINE = "whole-line"
LEADING_TRACING_LOGGER_TIMESTAMP = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?\s+")


class RecognisedFailureText(typing.NamedTuple):
    """A runtime failure prefix, cause class, and rule for extracting the detail."""

    cause_class: str
    line_prefix: str
    detail: str


def classify_failed_attempt(
    *, stdout: str, stderr: str, exit_code, recognised_texts, start_error: str = "",
) -> tuple:
    """Return (cause class, detail) for an attempt that produced no report."""
    for line in f"{stdout}\n{stderr}".splitlines():
        stripped = line.strip()
        timestamp = LEADING_TRACING_LOGGER_TIMESTAMP.match(stripped)
        untimestamped = stripped[timestamp.end():] if timestamp else stripped
        for text in recognised_texts or ():
            if untimestamped.startswith(text.line_prefix):
                if text.detail == DETAIL_IS_REST_OF_LINE:
                    detail = untimestamped[len(text.line_prefix):].lstrip(" \t·")
                elif text.detail == DETAIL_IS_WHOLE_LINE:
                    detail = untimestamped
                else:
                    detail = text.detail
                return text.cause_class, detail
    if start_error:
        return "agent-binary-missing", start_error
    if exit_code == 0:
        return "no-report", "no report written"
    last_lines = [line.strip() for line in (stderr if stderr.strip() else stdout).splitlines()
                  if line.strip()]
    detail = last_lines[-1][:CAUSE_DETAIL_MAX_CHARACTERS] if last_lines else "no output"
    return f"exit-{exit_code}", detail


def cause_line(program: str, cause_class: str, detail: str) -> str:
    """Format a failure cause for the cold-read-grid status parser."""
    return f"{program}: {CAUSE_PHRASE} {cause_class}{CAUSE_SEPARATOR}{detail}"


STRAY_WRITE_CHECK_SKIPPED_PHRASE = "stray writes were not checked for this run"
STRAY_WRITE_PHRASE = "files outside its report changed while it ran"
FELL_BACK_PHRASE = "fell back to"


def path_content_fingerprint(path: pathlib.Path) -> str:
    """Return a content fingerprint or a marker for a missing, unreadable, or directory path."""
    # Content comparison ignores writes that restore the original text, unlike mtime comparison.
    if path.is_dir():
        return "directory"
    fingerprint = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1 << 16), b""):
                fingerprint.update(block)
    except FileNotFoundError:
        return "absent"
    except OSError as error:
        return f"unreadable:{type(error).__name__}"
    return fingerprint.hexdigest()


def working_tree_state() -> set:
    """Return changed paths and content fingerprints, including untracked files."""
    # Fingerprints detect edits to already-dirty files; --untracked-files=all exposes files
    # inside already-untracked directories.
    completed = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    if completed.returncode != 0:
        raise WriteDetectorUnavailable(completed.stderr.strip() or "no detail")
    return {
        (name, path_content_fingerprint(REPO_ROOT / name))
        for name in (line[3:] for line in completed.stdout.splitlines())
        if name
    }


def repo_relative_name(path) -> str:
    """Return the repository-relative name, or an empty string for paths outside the repository."""
    if path is None:
        return ""
    try:
        return str(pathlib.Path(path).resolve().relative_to(REPO_ROOT))
    except ValueError:
        return ""


def stray_writes_since(baseline: set, own_report_path=None) -> list[str]:
    """Return paths changed since the baseline, excluding the requested report."""
    changed = {name for name, _fingerprint in working_tree_state() - baseline}
    changed.discard(repo_relative_name(own_report_path))
    return sorted(changed)


# The grid parses this phrase before deleting successful runs' logs.
NEAR_MISS_RECOVERY_PHRASE = "recovered a near-miss report"

# Only launchers that can recognize a complete review in stdout may opt into recovery.
STDOUT_RECOVERY_PHRASE = "recovered the report from the model's chat output"


def recover_report_from_runtime_stdout(
    program: str, report: pathlib.Path, runtime_stdout: str, decide_body,
) -> bool:
    """Write and announce a report recovered from stdout under the launcher's rule."""
    body = decide_body(runtime_stdout or "")
    if not body:
        return False
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(body.strip() + "\n", encoding="utf-8")
    print(
        f"{program}: {STDOUT_RECOVERY_PHRASE} — the model exited 0 without "
        f"writing {report}, and its stdout is a review by this launcher's "
        f"rule; that text is now the report and is stamped like any other.",
        file=sys.stderr,
    )
    return True


def instrument_built_record_directory(directory: pathlib.Path) -> bool:
    """Return whether target/ or reference-check.md marks an instrument-built record directory."""
    return ((directory / record_names.FROZEN_TARGET_DIRECTORY_NAME).is_dir()
            or (directory / "reference-check.md").is_file())


def recover_near_miss_report(
    program: str, report: pathlib.Path, attempt_started_at: float,
) -> bool:
    """Recover one unambiguous misplaced report from this attempt."""
    # Other runs use the same report filename; exclude instrument-built directories.
    # Only this attempt's files qualify, so a failed model cannot be credited to its successor.
    record_dir = report.parent
    records_root = record_dir.parent
    cutoff_text = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(attempt_started_at))
    candidates = []
    for directory, _subdirectories, file_names in os.walk(records_root):
        for file_name in file_names:
            if file_name != report.name:
                continue
            candidate = pathlib.Path(directory) / file_name
            if candidate == report or not candidate.is_file():
                continue
            if instrument_built_record_directory(pathlib.Path(directory)):
                continue
            if candidate.stat().st_mtime < attempt_started_at:
                continue
            if not candidate.read_text(encoding="utf-8").strip():
                continue
            candidates.append(candidate)
    candidates.sort()

    if len(candidates) == 1:
        found = candidates[0]
        # Move rather than copy to avoid leaving two names for one review.
        shutil.move(str(found), str(report))
        print(
            f"{program}: {NEAR_MISS_RECOVERY_PHRASE} — the model wrote "
            f"{found} instead of {report}, elsewhere under {records_root}. "
            f"The file has been moved into place and stamped; the review "
            f"itself is intact.",
            file=sys.stderr,
        )
        return True

    found_text = (
        "nothing" if not candidates
        else "more than one, which is ambiguous and so refused: "
             + ", ".join(str(candidate) for candidate in candidates)
    )
    print(
        f"{program}: no near-miss report to recover — looked for a file named "
        f"{report.name}, modified at or after {cutoff_text}, anywhere under "
        f"{records_root} outside the record directories the instrument built, "
        f"and found {found_text}.",
        file=sys.stderr,
    )
    return False


def verify_report(program: str, report: pathlib.Path) -> None:
    """Reject absent or blank reports and remove blank stubs."""
    # A stub must not be mistaken for a completed review by callers checking only existence.
    if not report.is_file():
        raise CellRefusal(
            f"{program}: the model exited without writing {report}. "
            "A run that produced no report is not a review that found "
            "nothing; treat it as failed and re-run.",
            exit_code=1,
        )
    if not report.read_text(encoding="utf-8").strip():
        report.unlink(missing_ok=True)
        report_name = report.name
        raise CellRefusal(
            f"{program}: the model wrote {report_name} but left it empty. "
            "The empty file has been removed so it cannot read as a clean "
            "review; treat this as failed and re-run.",
            exit_code=1,
        )


TOKENS_USED_PATTERN = re.compile(r"tokens used[:\s]+([\d,]+)", re.IGNORECASE)


def parse_tokens_used(runtime_output: str) -> str:
    """Return the last reported token total, or an empty string if none was reported."""
    # The last count is the total; absence must not be recorded as a zero cost.
    matches = TOKENS_USED_PATTERN.findall(runtime_output or "")
    return matches[-1].replace(",", "") if matches else ""


# A stalled git query must not prevent a finished review from being saved.
CHECKOUT_COMMIT_GIT_TIMEOUT_SECONDS = 10


def checkout_commit_for_provenance_stamp(checkout: pathlib.Path) -> str:
    """Return the checkout commit, with -dirty for tracked changes, or an empty string on failure."""
    # Untracked drafts are routine and do not make the provenance stamp dirty.
    # Do not print failures: the grid parses stderr as cell status.
    def git_output(*arguments):
        """Return git stdout, or None if git cannot answer."""
        try:
            completed = subprocess.run(
                ["git", "-C", str(checkout), *arguments],
                capture_output=True, text=True, check=False,
                timeout=CHECKOUT_COMMIT_GIT_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return completed.stdout if completed.returncode == 0 else None

    commit = (git_output("rev-parse", "--short", "HEAD") or "").strip()
    if not commit:
        return ""
    tracked_changes = git_output("status", "--porcelain", "--untracked-files=no")
    if tracked_changes is None:
        return ""
    return commit + ("-dirty" if tracked_changes.strip() else "")


def stamp_provenance(
    report: pathlib.Path, *, runtime: str, model: str, effort: str,
    cell: str, tier: str, target_argument: str, duration_s: int,
    fallback_from: str = "", checkout: str = "", tokens: str = "",
    prompt_file_argument: str = "",
) -> None:
    """Prepend the report's provenance stamp."""
    # Keep target last: paths with spaces would swallow subsequent whitespace-delimited fields.
    # The checkout is sampled at stamp time and may have changed since the reviewer started.
    fallback_note = f"fallback_from={fallback_from} " if fallback_from else ""
    checkout_note = f"checkout={checkout} " if checkout else ""
    tokens_note = f"tokens={tokens} " if tokens else ""
    prompt_file_note = (
        f"prompt_file={prompt_file_argument} " if prompt_file_argument else "")
    stamp = (
        f"<!-- provenance: runtime={runtime} model={model} {fallback_note}"
        f"effort={effort} cell={cell} tier={tier} duration_s={duration_s} "
        f"{checkout_note}{tokens_note}{prompt_file_note}"
        f"target={target_argument} -->\n\n"
    )
    report.write_text(stamp + report.read_text(encoding="utf-8"), encoding="utf-8")


def run_model_chain(
    *, program: str, runtime: str, chain, effort: str, build_invocation,
    prompt: str, report: pathlib.Path, cell: str, tier: str, target_argument: str,
    baseline, cell_started_at: float, prompt_file_argument: str = "",
    recover_report_from_stdout=None, model_to_effort=None,
    recognised_failure_texts_for_model=None,
) -> int:
    """Try models until one produces a report, then stamp the report."""
    # build_invocation must apply the same per-model effort mapping used by the stamp.
    failed_attempts: list[str] = []
    produced_by = ""
    produced_tokens = ""
    for model in chain:
        # Clear failed attempts' reports so the next model cannot receive credit for their text.
        report.unlink(missing_ok=True)
        # A per-attempt clock prevents recovery from crediting a failed model's stray report to its successor.
        attempt_started_at = time.time()
        command, stdin_text = build_invocation(model, prompt)
        # codex exec reads piped stdin to EOF before starting; input=None would inherit a possibly open pipe.
        stdin_arguments = (
            {"input": stdin_text} if stdin_text is not None
            else {"stdin": subprocess.DEVNULL}
        )
        # Both streams carry failure diagnostics; stderr also carries the runtime's token total.
        try:
            completed = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=REPO_ROOT,
                text=True,
                check=False,
                **stdin_arguments,
            )
        except OSError as error:
            failed_attempts.append(f"{model}({type(error).__name__})")
            print(f"{program}: {model} could not be run: {error}", file=sys.stderr)
            print(cause_line(program, *classify_failed_attempt(
                stdout="", stderr="", exit_code=None, recognised_texts=(),
                start_error=str(error))), file=sys.stderr)
            continue
        recognised_texts = (recognised_failure_texts_for_model(model)
                            if recognised_failure_texts_for_model else ())
        if completed.stderr:
            print(completed.stderr, file=sys.stderr, end="")
        if completed.returncode != 0:
            failed_attempts.append(f"{model}(exit{completed.returncode})")
            if completed.stdout:
                print(completed.stdout, file=sys.stderr)
            print(f"{program}: {model} failed (exit {completed.returncode})", file=sys.stderr)
            print(cause_line(program, *classify_failed_attempt(
                stdout=completed.stdout or "", stderr=completed.stderr or "",
                exit_code=completed.returncode, recognised_texts=recognised_texts)),
                file=sys.stderr)
            continue
        # Recover only after exit 0; a failed model's leftover file is not an accepted review.
        if not report.is_file():
            recover_near_miss_report(program, report, attempt_started_at)
        # Prefer the report file over stdout, including a file recovered from the wrong directory.
        if not report.is_file() and recover_report_from_stdout is not None:
            recover_report_from_runtime_stdout(
                program, report, completed.stdout, recover_report_from_stdout)
        try:
            verify_report(program, report)
        except CellRefusal as refusal:
            # stdout may explain why a successful exit produced no report.
            failed_attempts.append(f"{model}(no-report)")
            if completed.stdout:
                print(completed.stdout, file=sys.stderr)
            print(str(refusal), file=sys.stderr)
            print(cause_line(program, *classify_failed_attempt(
                stdout=completed.stdout or "", stderr=completed.stderr or "",
                exit_code=0, recognised_texts=recognised_texts)), file=sys.stderr)
            continue
        produced_by = model
        # Use only this attempt's stderr: stdout may quote token counts, and earlier attempts cost other models.
        produced_tokens = parse_tokens_used(completed.stderr or "")
        break

    if not produced_by:
        # Remove the final failed attempt's report so readers cannot mistake the orphan for a completed review.
        report.unlink(missing_ok=True)
        print(
            f"{program}: every model for this cell failed — "
            + ", ".join(failed_attempts)
            + ". No report was produced; the cell failed rather than leaving a "
              "stub that would read as a completed review.",
            file=sys.stderr,
        )
        report_stray_writes(program, baseline, report)
        return 1

    if failed_attempts:
        print(
            f"{program}: {FELL_BACK_PHRASE} {produced_by} after "
            + ", ".join(failed_attempts)
            + ". The report's provenance stamp records this.",
            file=sys.stderr,
        )

    stamp_provenance(
        report, runtime=runtime, model=produced_by,
        effort=(model_to_effort or {}).get(produced_by, effort), cell=cell,
        tier=tier, target_argument=target_argument,
        duration_s=int(time.time() - cell_started_at),
        # Use the checkout the reviewer ran in, which may differ from the launcher's working directory.
        checkout=checkout_commit_for_provenance_stamp(REPO_ROOT),
        fallback_from="+".join(failed_attempts),
        tokens=produced_tokens,
        prompt_file_argument=prompt_file_argument,
    )
    report_stray_writes(program, baseline, report)
    print(f"{program}: report written to {report}", file=sys.stderr)
    return 0


def run_cell(
    *, program: str, runtime: str, description: str, model_help: str,
    tier_to_model_chain: dict, tier_to_effort: dict, invocation_builder,
    recover_report_from_stdout=None, recognised_failure_texts_for_model=None,
) -> int:
    # Include failed attempts in the cell's total cost.
    cell_started_at = time.time()
    parser = build_argument_parser(
        description, model_help, tier_choices=tuple(tier_to_model_chain))
    args = parser.parse_args()

    # Snapshot before execution so pre-existing edits are not reported as changes from this run.
    try:
        baseline = working_tree_state()
    except WriteDetectorUnavailable as error:
        baseline = None
        print(f"{program}: could not snapshot the working tree ({error}); "
              "stray writes will not be checked for this run.", file=sys.stderr)

    report = None
    try:
        validate_cell(args.cell, args.prompt_file)
        target = resolve_target(args.target)
        report = resolve_report_path(args.report)
        prompt_file = (
            resolve_prompt_file(args.prompt_file) if args.prompt_file else None)
        prompt = compose_prompt(args.cell, target, report, prompt_file,
                                resolve_target_origin(args.target_origin))
    except CellRefusal as refusal:
        print(f"{program}: {refusal}", file=sys.stderr)
        report_stray_writes(program, baseline, report)
        return refusal.exit_code

    # An explicit model must not silently fall back to a different model.
    chain = (args.model,) if args.model else tier_to_model_chain[args.tier]
    effort = args.effort or tier_to_effort[args.tier]

    return run_model_chain(
        program=program, runtime=runtime, chain=chain, effort=effort,
        build_invocation=invocation_builder(effort), prompt=prompt,
        report=report, cell=args.cell, tier=args.tier,
        target_argument=args.target, baseline=baseline,
        cell_started_at=cell_started_at,
        prompt_file_argument=args.prompt_file or "",
        recover_report_from_stdout=recover_report_from_stdout,
        recognised_failure_texts_for_model=recognised_failure_texts_for_model,
    )


def report_stray_writes(program: str, baseline, own_report_path=None) -> None:
    """Report changes outside the requested report without raising."""
    # Check every runtime and every exit path: a failed reviewer may still have edited the target.
    if baseline is None:
        print(f"{program}: {STRAY_WRITE_CHECK_SKIPPED_PHRASE} — no pre-run "
              "snapshot of the working tree was taken. This is a failure to "
              "look, not a clean result.", file=sys.stderr)
        return
    try:
        stray = stray_writes_since(baseline, own_report_path)
    except WriteDetectorUnavailable as error:
        print(f"{program}: {STRAY_WRITE_CHECK_SKIPPED_PHRASE} — git status "
              f"failed ({error}). This is a failure to look, not a clean "
              "result.", file=sys.stderr)
        return
    if stray:
        # Snapshots detect changed content, not authorship; another worker may have made the edit.
        print(
            f"{program}: {STRAY_WRITE_PHRASE} — {', '.join(stray)}. This cell "
            "cannot tell whether the reviewer wrote them or someone else working "
            "in the checkout did. Inspect before triage and revert only what is "
            "the reviewer's; any report still stands on its own.",
            file=sys.stderr,
        )
