#!/usr/bin/env python3
"""Tests for the force-push guard (force-push-with-open-pull-request-guard-hook.py).

No case runs a real `git push`, a real `gh` or a real network call: every
decision drives the guard in-process with a stubbed runner that answers for
both probes. The guard exists because a force push is irreversible, so its
test must not be able to perform one.

Two fixtures carry the incident this guard was built from (2026-09-17): the
approved head of the pull request "Fast read: say when the cold-read-full-run
is still required" was rebased and force-pushed, spending a reviewer's round.

Cases named D1..D5 are the defects the fleet seat named in review of the plan,
before a line was written. Each is the failure it predicted:
  D1  the destination side of a colon refspec is the branch, not the source
  D2  a bare push from a worktree must resolve that worktree's branch
  D3  an unreachable or slow `gh` allows and says so — it never blocks
  D4  the refusal names the pull request by title and url, never by number
  D5  the ruling "stop rather than reverse" is the refusal's second line

Run: python3 scripts/force-push-with-open-pull-request-guard-hook-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import contextlib
import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

HOOK_SCRIPT = Path(__file__).with_name(
    "force-push-with-open-pull-request-guard-hook.py")

_spec = importlib.util.spec_from_file_location("force_push_guard", HOOK_SCRIPT)
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)

FAST_READ_PULL_REQUEST = {
    "title": "Fast read: say when the cold-read-full-run is still required",
    "url": "https://github.com/nedschorus/nedschorus/pull/466",
}
SESSION_WORKTREE = "/a/session/worktree"

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


class ProbeRunner:
    """Stands in for subprocess.run inside both of the guard's probes,
    dispatching on the program so one runner serves each case.

    `branch` is what `git rev-parse --abbrev-ref HEAD` answers; `open_pull_requests`
    maps a branch name to the pull request `gh pr list --head <branch>` finds,
    so a case can register a pull request for one branch and prove the guard
    asked about that one and not another."""

    def __init__(self, branch="a-local-topic-branch", open_pull_requests=None,
                 gh_returncode=0, gh_stderr="", gh_stdout=None, gh_raises=None,
                 git_returncode=0, git_raises=None):
        self.branch = branch
        self.open_pull_requests = open_pull_requests or {}
        self.gh_returncode = gh_returncode
        self.gh_stderr = gh_stderr
        self.gh_stdout = gh_stdout
        self.gh_raises = gh_raises
        self.git_returncode = git_returncode
        self.git_raises = git_raises
        self.calls = []
        self.call_kwargs = []

    def __call__(self, argv, **kwargs):
        self.calls.append(argv)
        self.call_kwargs.append(kwargs)
        if argv[0] == "git":
            if self.git_raises:
                raise self.git_raises
            return subprocess.CompletedProcess(
                argv, self.git_returncode, self.branch + "\n", "")
        if argv[0] == "gh":
            if self.gh_raises:
                raise self.gh_raises
            if self.gh_stdout is not None:
                stdout = self.gh_stdout
            else:
                asked_about = argv[argv.index("--head") + 1]
                found = self.open_pull_requests.get(asked_about)
                stdout = json.dumps([found] if found else [])
            return subprocess.CompletedProcess(
                argv, self.gh_returncode, stdout, self.gh_stderr)
        raise AssertionError(f"the guard ran an unexpected program: {argv}")

    def branches_asked_about(self):
        return [argv[argv.index("--head") + 1]
                for argv in self.calls if argv[0] == "gh"]

    def probe_directories(self):
        return [kwargs.get("cwd") for kwargs in self.call_kwargs]


class SteppingClock:
    """A monotonic clock the test moves by hand. Frozen unless a case steps it,
    so no case depends on how fast the machine running it is."""

    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class SlowProbeRunner(ProbeRunner):
    """A ProbeRunner whose every probe costs `seconds_per_probe` of the shared
    clock, standing in for a GitHub that answers, but slowly."""

    def __init__(self, clock, seconds_per_probe, **kwargs):
        super().__init__(**kwargs)
        self.clock = clock
        self.seconds_per_probe = seconds_per_probe

    def __call__(self, argv, **kwargs):
        self.clock.now += self.seconds_per_probe
        return super().__call__(argv, **kwargs)


def decide(command, runner=None, cwd=SESSION_WORKTREE, clock=None):
    """Return (decision, reason) for one Bash command."""
    runner = runner or ProbeRunner()
    guard_run = guard.GuardRun(runner, clock or SteppingClock())
    return guard.analyze_command_text(command, cwd, guard_run)


def run_main(payload, runner=None):
    """Drive main() as the harness does, returning (exit_code, parsed_stdout)."""
    runner = runner or ProbeRunner()
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        code = guard.main(stdin=io.StringIO(json.dumps(payload)), runner=runner,
                          clock=SteppingClock())
    text = stdout.getvalue().strip()
    return code, (json.loads(text) if text else None)


# ---------------------------------------------------------------------------
# The shared shell reader is really imported, and really splits invocations
# from prose. A signature change in the keystroke guard fails HERE rather than
# failing open in front of a live push.
# ---------------------------------------------------------------------------

check("the shared tokenizer is imported from the keystroke guard",
      callable(guard.tokenize_simple_commands) and callable(guard.split_out_heredocs)
      and callable(guard.is_program))
check("the shared tokenizer keeps quoted prose as one data word",
      guard.tokenize_simple_commands('git commit -m "git push --force"')
      == [["git", "commit", "-m", "git push --force"]],
      repr(guard.tokenize_simple_commands('git commit -m "git push --force"')))

# ---------------------------------------------------------------------------
# The core decision: a force push at a branch with an open pull request.
# ---------------------------------------------------------------------------

runner = ProbeRunner(open_pull_requests={"the-pr-branch": FAST_READ_PULL_REQUEST})
decision, reason = decide("git push --force origin the-pr-branch", runner)
check("a force push at an open pull request's head is denied",
      decision == "deny", f"{decision}: {reason}")
check("D4 the refusal names the pull request by title",
      reason and FAST_READ_PULL_REQUEST["title"] in reason, reason)
check("D4 the refusal names the pull request by url",
      reason and FAST_READ_PULL_REQUEST["url"] in reason, reason)
check("D4 the refusal never cites the pull request by bare number",
      reason and "#466" not in reason, reason)
lines = (reason or "").splitlines()
check("D5 'stop rather than reverse' is the refusal's SECOND line",
      len(lines) > 1
      and lines[1].startswith(
          "If you are force-pushing to restore what an earlier force push replaced")
      and "stop" in lines[1] and "message merge-lane" in lines[1]
      and "ListAgents" in lines[1],
      lines[1] if len(lines) > 1 else reason)
check("the refusal teaches the remedy: a new commit on top, pushed without --force",
      reason and "new commit on top" in reason and "without --force" in reason,
      reason)
check("the refusal names the escape hatch",
      reason and guard.ESCAPE_HATCH_ASSIGNMENT in reason, reason)
# The incident's own shape: the agent had ALREADY rebased locally, so a plain
# push is rejected as non-fast-forward. The refusal must say how to get back
# to the pushed head, with the real branch name so the commands paste.
check("the refusal tells an agent that already rewrote locally how to recover",
      reason and "git branch the-pr-branch-rewritten" in reason
      and "git switch -C the-pr-branch origin/the-pr-branch" in reason, reason)
check("the recovery never discards uncommitted work (no reset --hard)",
      reason and "reset --hard" not in reason, reason)

# User-ruled 2026-09-18: agents need clear, direct, specific instructions.
# Nothing an agent reads carries a date, a citation or a ruling's name; those
# belong in the module docstring, where maintainers read them.
for label, text in [
    ("the refusal", reason),
    ("the unresolvable refusal", decide("cd $WORKTREE && git push --force")[1]),
    ("the unchecked note", decide(
        "git push --force origin the-pr-branch",
        ProbeRunner(gh_raises=subprocess.TimeoutExpired("gh", 10)))[1]),
]:
    asides = [marker for marker in ("2026", "CLAUDE.md", "ruling", "ruled", "(merge-lane")
              if marker in (text or "")]
    check(f"{label} carries no dates, citations or rulings", not asides,
          f"{asides}: {text}")

runner = ProbeRunner(open_pull_requests={})
decision, reason = decide("git push --force origin a-branch-with-no-pull-request", runner)
check("a force push at a branch with no open pull request is allowed",
      decision is None, f"{decision}: {reason}")

# ---------------------------------------------------------------------------
# D1: the DESTINATION side of a colon refspec is the branch under review.
# `git push --force origin my-local-name:the-pr-branch` rewrites the-pr-branch;
# asking about my-local-name would find nothing and allow the very push the
# guard exists to stop.
# ---------------------------------------------------------------------------

runner = ProbeRunner(open_pull_requests={"the-pr-branch": FAST_READ_PULL_REQUEST})
decision, reason = decide(
    "git push --force origin my-local-name:the-pr-branch", runner)
check("D1 a colon refspec is judged by its destination, not its source",
      decision == "deny", f"{decision}: {reason}")
check("D1 the guard asked gh about the destination branch only",
      runner.branches_asked_about() == ["the-pr-branch"],
      str(runner.branches_asked_about()))

runner = ProbeRunner(open_pull_requests={"my-local-name": FAST_READ_PULL_REQUEST})
decision, _ = decide("git push --force origin my-local-name:a-fresh-branch", runner)
check("D1 a pull request on the SOURCE name does not block the push",
      decision is None, str(decision))

runner = ProbeRunner(open_pull_requests={"the-pr-branch": FAST_READ_PULL_REQUEST})
decision, _ = decide(
    "git push --force origin HEAD:refs/heads/the-pr-branch", runner)
check("a refs/heads/ destination is stripped to the branch name",
      decision == "deny", str(decision))

# ---------------------------------------------------------------------------
# D2: a bare push resolves the branch from the checkout the command runs in.
# The incident's shape is a push from a worktree, so the hook's own directory
# is not a safe stand-in.
# ---------------------------------------------------------------------------

runner = ProbeRunner(branch="the-pr-branch",
                     open_pull_requests={"the-pr-branch": FAST_READ_PULL_REQUEST})
decision, _ = decide("git push --force", runner)
check("D2 a bare force push resolves the current branch and is denied",
      decision == "deny", str(decision))
check("D2 the current branch came from the session's own cwd",
      ["git", "-C", SESSION_WORKTREE, "rev-parse", "--abbrev-ref", "HEAD"]
      in runner.calls, str(runner.calls))

runner = ProbeRunner(branch="the-pr-branch",
                     open_pull_requests={"the-pr-branch": FAST_READ_PULL_REQUEST})
decision, _ = decide("git -C /elsewhere/wt-fast-read push --force origin", runner)
check("D2 `git -C` moves the checkout the branch is resolved from",
      decision == "deny", str(decision))
check("D2 the probe ran in the -C directory",
      ["git", "-C", "/elsewhere/wt-fast-read", "rev-parse", "--abbrev-ref", "HEAD"]
      in runner.calls, str(runner.calls))

runner = ProbeRunner(branch="the-pr-branch",
                     open_pull_requests={"the-pr-branch": FAST_READ_PULL_REQUEST})
decision, _ = decide("cd /elsewhere/wt-fast-read && git push --force", runner)
check("D2 a literal `cd` earlier in the chain moves the checkout",
      decision == "deny", str(decision))
check("D2 gh ran in the cd'd directory, so it infers the right repository",
      "/elsewhere/wt-fast-read" in runner.probe_directories(),
      str(runner.probe_directories()))

runner = ProbeRunner()
decision, reason = decide("cd $WORKTREE && git push --force", runner)
check("D2 an unexpanded directory is refused as unresolvable",
      decision == "deny", f"{decision}: {reason}")
check("D2 that refusal asks for the path written out and probes nothing",
      reason and "written out" in reason and "$WORKTREE" in reason
      and "<checkout path>" in reason and not runner.calls, reason)
check("D2 the unresolvable refusal names the escape hatch",
      reason and guard.ESCAPE_HATCH_ASSIGNMENT in reason, reason)

runner = ProbeRunner(branch="the-pr-branch",
                     open_pull_requests={"the-pr-branch": FAST_READ_PULL_REQUEST})
decision, _ = decide("git push --force origin HEAD", runner)
check("an explicit HEAD refspec resolves to the current branch",
      decision == "deny", str(decision))

# ---------------------------------------------------------------------------
# D3: `gh` unreachable, unauthenticated, slow or unparseable — allow, and say
# what went unchecked. A guard that blocks when GitHub is down stops ordinary
# work for nothing.
# ---------------------------------------------------------------------------

for label, runner in [
    ("a timeout", ProbeRunner(gh_raises=subprocess.TimeoutExpired("gh", 10))),
    ("gh missing", ProbeRunner(gh_raises=FileNotFoundError("gh"))),
    ("gh failing", ProbeRunner(gh_returncode=1, gh_stderr="gh: not authenticated")),
    ("unparseable output", ProbeRunner(gh_stdout="not json at all")),
]:
    decision, reason = decide("git push --force origin the-pr-branch", runner)
    check(f"D3 {label} allows the push rather than blocking it",
          decision == "unchecked", f"{decision}: {reason}")
    check(f"D3 {label} says what went unchecked and names the branch",
          reason and reason.startswith("Not checked:")
          and "the-pr-branch" in reason, reason)

decision, reason = decide(
    "git push --force origin the-pr-branch",
    ProbeRunner(gh_returncode=1, gh_stderr="gh: not authenticated"))
check("D3 the unchecked note carries gh's own first line of complaint",
      reason and "not authenticated" in reason, reason)

runner = ProbeRunner(gh_raises=subprocess.TimeoutExpired("gh", 10))
decision, reason = decide("git push --force origin the-pr-branch", runner)
check("D3 the unchecked note tells the agent how to confirm by hand",
      reason and "gh pr list --state open --head the-pr-branch" in reason, reason)
check("D3 the note's fallback works when gh itself cannot run",
      reason and "or fails, message merge-lane" in reason
      and "ListAgents" in reason, reason)
# Asking gh again helps after a timeout or an unreadable answer, and fails
# the same way after gh could not run or failed outright — so only the first
# two tell the agent to run it.
for label, runner, retry in [
    ("a timeout", ProbeRunner(gh_raises=subprocess.TimeoutExpired("gh", 10)), True),
    ("unparseable output", ProbeRunner(gh_stdout="not json at all"), True),
    ("gh missing", ProbeRunner(gh_raises=FileNotFoundError("gh")), False),
    ("gh not logged in", ProbeRunner(gh_returncode=1, gh_stderr="gh auth login"), False),
]:
    _, note = decide("git push --force origin the-pr-branch", runner)
    if retry:
        check(f"D3 after {label}, the note asks the agent to run gh again",
              note and "Run: gh pr list" in note, note)
    else:
        check(f"D3 after {label}, the note never asks for the gh that just failed",
              note and "gh pr list" not in note
              and "so it can check for an open pull request" in note, note)

check("D3 the note says what an empty answer means",
      reason and "If it lists nothing, no pull request was affected." in reason,
      reason)

check("D3 one probe cannot spend the whole shared budget",
      guard.GH_TIMEOUT_SECONDS < guard.PROBE_BUDGET_SECONDS
      and guard.GIT_TIMEOUT_SECONDS < guard.PROBE_BUDGET_SECONDS)

# The shared budget. A hook that overruns its registered timeout fails open
# SILENTLY; a guard that stops probing in time can still say what went
# unchecked. Three branches, no pull requests, and a GitHub that takes 15
# seconds an answer: the first probe gets the full per-probe cap, the second
# only what is left of the budget, and the third is never started.
clock = SteppingClock()
runner = SlowProbeRunner(clock, 15.0, open_pull_requests={})
decision, reason = decide(
    "git push --force origin branch-one branch-two branch-three",
    runner, clock=clock)
check("budget: exhaustion is reported as unchecked, never as a refusal",
      decision == "unchecked", f"{decision}: {reason}")
check("budget: the note says the limit ran out, and before which branch",
      reason and "limit ran out" in reason and "branch-three" in reason,
      reason)
check("budget: no probe is started once the budget is spent",
      runner.branches_asked_about() == ["branch-one", "branch-two"],
      str(runner.branches_asked_about()))
timeouts = [kwargs["timeout"] for kwargs in runner.call_kwargs]
check("budget: the first probe gets its own cap, the next only what is left",
      timeouts == [guard.GH_TIMEOUT_SECONDS, guard.PROBE_BUDGET_SECONDS - 15.0],
      str(timeouts))

clock = SteppingClock()
runner = SlowProbeRunner(clock, 15.0, open_pull_requests={
    "branch-two": FAST_READ_PULL_REQUEST})
decision, _ = decide("git push --force origin branch-one branch-two",
                     runner, clock=clock)
check("budget: a pull request found inside the budget is still refused",
      decision == "deny", str(decision))

# The budget is measured from the guard's own start, and shared across every
# push in the command: a slow answer for the first push leaves the second one
# unable to resolve its branch, and that is reported, not refused.
clock = SteppingClock()
runner = SlowProbeRunner(clock, guard.PROBE_BUDGET_SECONDS + 5.0,
                         open_pull_requests={})
decision, reason = decide(
    "git push --force origin a-fresh-branch && git push --force",
    runner, clock=clock)
check("budget: a budget spent by an earlier push reports the later branch",
      decision == "unchecked" and "the current branch" in (reason or ""),
      f"{decision}: {reason}")
check("budget: and the later push's branch probe was never started",
      not any(argv[0] == "git" for argv in runner.calls), str(runner.calls))
runner = ProbeRunner(open_pull_requests={})
decide("git push --force origin a-branch", runner)
check("D3 every probe passes an explicit timeout",
      all("timeout" in kwargs for kwargs in runner.call_kwargs),
      str(runner.call_kwargs))

runner = ProbeRunner(git_raises=subprocess.TimeoutExpired("git", 5))
decision, reason = decide("git push --force", runner)
check("D3 an unanswerable `git rev-parse` allows and says so",
      decision == "unchecked", f"{decision}: {reason}")

runner = ProbeRunner(git_raises=subprocess.TimeoutExpired("git", 5))
decision, reason = decide("git push --force", runner)
check("an unresolved current branch gets a gh command that runs as written",
      reason and 'gh pr list --state open --head "$(git branch --show-current)"'
      in reason and "whether the current branch has" in reason, reason)

# git's default push.default=simple refuses a push that needs a current
# branch when HEAD is detached, so the guard stays out of the way: no
# refusal, and no note carrying a `gh` command that could not work.
for command in ["git push --force", "git push --force origin HEAD"]:
    runner = ProbeRunner(branch="HEAD")
    decision, reason = decide(command, runner)
    check(f"a detached HEAD is left to git, silently: {command}",
          decision is None and reason is None, f"{decision}: {reason}")
    check(f"and gh is never asked: {command}",
          not runner.branches_asked_about(), str(runner.calls))

# ---------------------------------------------------------------------------
# Which forms force. Missing one of these is a silent hole; treating a
# non-forcing push as forced is a false refusal an agent has to argue with.
# ---------------------------------------------------------------------------

FORCING = [
    "git push --force origin the-pr-branch",
    "git push -f origin the-pr-branch",
    "git push -fu origin the-pr-branch",
    "git push -uf origin the-pr-branch",
    "git push --force-with-lease origin the-pr-branch",
    "git push --force-with-lease=the-pr-branch:abc1234 origin the-pr-branch",
    "git push origin +the-pr-branch",
    "git push --repo somewhere --force origin the-pr-branch",
    "git push -o ci.skip --force origin the-pr-branch",
    "git push --force -- origin the-pr-branch",
]
for command in FORCING:
    runner = ProbeRunner(open_pull_requests={"the-pr-branch": FAST_READ_PULL_REQUEST})
    decision, reason = decide(command, runner)
    check(f"forces: {command}", decision == "deny", f"{decision}: {reason}")

NOT_FORCING = [
    "git push origin the-pr-branch",
    "git push -u origin the-pr-branch",
    "git push --set-upstream origin the-pr-branch",
    "git push --force-if-includes origin the-pr-branch",
    "git push -o force origin the-pr-branch",
    "git push -of origin the-pr-branch",
    "git push --push-option --force origin the-pr-branch",
    "git push --delete origin the-pr-branch",
    "git push --force --delete origin the-pr-branch",
    "git push -d origin the-pr-branch",
    "git push --force origin :the-pr-branch",
    "git push --force origin refs/tags/v1.0",
    "git fetch --force origin the-pr-branch",
    "git pull --force",
]
for command in NOT_FORCING:
    runner = ProbeRunner(open_pull_requests={"the-pr-branch": FAST_READ_PULL_REQUEST})
    decision, reason = decide(command, runner)
    check(f"does not force: {command}", decision is None, f"{decision}: {reason}")
    check(f"and probes nothing: {command}", not runner.calls, str(runner.calls))

# ---------------------------------------------------------------------------
# Prose is data. The guard's own commit message and pull request body say
# `git push --force`; the keystroke guard blocked its own commit message once,
# which is why these cases exist at all.
# ---------------------------------------------------------------------------

PROSE = [
    'git commit -m "deny a git push --force at an open pull request"',
    'grep -rn "git push --force" scripts/',
    'echo "the remedy is not git push --force origin the-pr-branch"',
    'gh pr create --title "Guard git push --force" --body "denies -f"',
]
for command in PROSE:
    runner = ProbeRunner(open_pull_requests={"the-pr-branch": FAST_READ_PULL_REQUEST})
    decision, reason = decide(command, runner)
    check(f"prose is data: {command[:52]}", decision is None, f"{decision}: {reason}")

runner = ProbeRunner(open_pull_requests={"the-pr-branch": FAST_READ_PULL_REQUEST})
heredoc_command = (
    "gh pr create --body-file - <<'EOF'\n"
    "This guard denies `git push --force origin the-pr-branch`.\n"
    "EOF\n"
)
decision, reason = decide(heredoc_command, runner)
check("a heredoc body naming the command is data, not an invocation",
      decision is None, f"{decision}: {reason}")

# ---------------------------------------------------------------------------
# The escape hatch: the one sanctioned rewrite, and the one form of it.
# ---------------------------------------------------------------------------

runner = ProbeRunner(open_pull_requests={"the-pr-branch": FAST_READ_PULL_REQUEST})
decision, reason = decide(
    f"{guard.ESCAPE_HATCH_ASSIGNMENT} git push --force origin the-pr-branch",
    runner)
check("the escape hatch allows the sanctioned rewrite",
      decision is None, f"{decision}: {reason}")
check("the escape hatch skips the probes entirely",
      not runner.calls, str(runner.calls))

runner = ProbeRunner(open_pull_requests={"the-pr-branch": FAST_READ_PULL_REQUEST})
decision, _ = decide(
    f'echo "{guard.ESCAPE_HATCH_ASSIGNMENT}" && git push --force origin the-pr-branch',
    runner)
check("the escape hatch inside a quoted string is data and does not authorize",
      decision == "deny", str(decision))

refusal = decide("git push --force origin the-pr-branch", ProbeRunner(
    open_pull_requests={"the-pr-branch": FAST_READ_PULL_REQUEST}))[1]
check("the refusal says the escape hatch goes directly on the git push",
      refusal and "directly in front of the git push command" in refusal, refusal)

# The prefix sanctions only the command it sits on. An agent that puts it on
# the `cd` of `cd $WORKTREE && git push --force` has not sanctioned the push.
runner = ProbeRunner()
decision, _ = decide(
    f"{guard.ESCAPE_HATCH_ASSIGNMENT} cd $WORKTREE && git push --force", runner)
check("the escape hatch on a preceding cd does not sanction the push after it",
      decision == "deny", str(decision))

runner = ProbeRunner(branch="the-pr-branch",
                     open_pull_requests={"the-pr-branch": FAST_READ_PULL_REQUEST})
decide("SOME_SETTING=1 cd /elsewhere/wt-fast-read && git push --force", runner)
check("a cd carrying an environment assignment still moves the checkout",
      ["git", "-C", "/elsewhere/wt-fast-read", "rev-parse", "--abbrev-ref", "HEAD"]
      in runner.calls, str(runner.calls))

runner = ProbeRunner(open_pull_requests={"the-pr-branch": FAST_READ_PULL_REQUEST})
decision, _ = decide(
    f"{guard.ESCAPE_HATCH_VARIABLE}=0 git push --force origin the-pr-branch", runner)
check("only the documented =1 form authorizes a rewrite",
      decision == "deny", str(decision))

# ---------------------------------------------------------------------------
# Several pushes, several branches, and one question per branch.
# ---------------------------------------------------------------------------

runner = ProbeRunner(open_pull_requests={"the-pr-branch": FAST_READ_PULL_REQUEST})
decision, _ = decide(
    "git push --force origin a-fresh-branch the-pr-branch", runner)
check("a force push naming several refspecs is judged on each",
      decision == "deny", str(decision))

runner = ProbeRunner(open_pull_requests={"the-pr-branch": FAST_READ_PULL_REQUEST})
decide("git push --force origin the-pr-branch the-pr-branch", runner)
check("the same branch is asked about once",
      runner.branches_asked_about() == ["the-pr-branch"],
      str(runner.branches_asked_about()))

runner = ProbeRunner(open_pull_requests={"the-pr-branch": FAST_READ_PULL_REQUEST})
decision, _ = decide(
    "git push origin a-fresh-branch && git push --force origin the-pr-branch",
    runner)
check("a force push later in a chain is still found",
      decision == "deny", str(decision))

# ---------------------------------------------------------------------------
# The harness contract: what main() writes, and what it ignores.
# ---------------------------------------------------------------------------

code, output = run_main(
    {"tool_name": "Bash", "cwd": SESSION_WORKTREE,
     "tool_input": {"command": "git push --force origin the-pr-branch"}},
    ProbeRunner(open_pull_requests={"the-pr-branch": FAST_READ_PULL_REQUEST}))
check("a denial exits 0 and speaks through the hook's JSON", code == 0, str(code))
check("the denial is a PreToolUse deny decision",
      output and output["hookSpecificOutput"]["permissionDecision"] == "deny",
      str(output))
check("the deny reason carries the pull request's title",
      output and FAST_READ_PULL_REQUEST["title"]
      in output["hookSpecificOutput"]["permissionDecisionReason"], str(output))

code, output = run_main(
    {"tool_name": "Bash", "cwd": SESSION_WORKTREE,
     "tool_input": {"command": "git push --force origin the-pr-branch"}},
    ProbeRunner(gh_raises=subprocess.TimeoutExpired("gh", 10)))
check("an unchecked push exits 0", code == 0, str(code))
check("an unchecked push NEVER emits an allow decision, which would bypass "
      "the user's own permission rules",
      output is None or "permissionDecision" not in output["hookSpecificOutput"],
      str(output))
check("an unchecked push reaches the agent through additionalContext",
      output and output["hookSpecificOutput"]["additionalContext"].startswith(
          "Not checked:"),
      str(output))

for payload in [
    {"tool_name": "Edit", "tool_input": {"file_path": "/x"}},
    {"tool_name": "Bash", "tool_input": {}},
    {"tool_name": "Bash", "tool_input": {"command": ""}},
]:
    code, output = run_main(payload)
    check(f"passes through untouched: {json.dumps(payload)[:56]}",
          code == 0 and output is None, f"{code} {output}")

stdout = io.StringIO()
with contextlib.redirect_stdout(stdout):
    code = guard.main(stdin=io.StringIO("not json"), runner=ProbeRunner(),
                      clock=SteppingClock())
check("an unreadable payload exits 0 and says nothing",
      code == 0 and not stdout.getvalue().strip(), f"{code} {stdout.getvalue()}")

result = subprocess.run(
    [sys.executable, str(HOOK_SCRIPT)],
    input=json.dumps({"tool_name": "Bash", "cwd": SESSION_WORKTREE,
                      "tool_input": {"command": "echo hello"}}),
    capture_output=True, text=True, check=False)
check("run end-to-end as the harness runs it, an ordinary command passes",
      result.returncode == 0 and not result.stdout.strip(),
      f"{result.returncode} {result.stdout} {result.stderr}")

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
