#!/usr/bin/env python3
"""Two copies of resupervise-seat-test.py running at once give each other's verdicts no say.

Two copies once shared fixed tmux session names on shared servers: the second
copy's session creation failed, the case printed SKIP, its checks never ran,
and the copy still printed "all cases passed". These cases run real copies of
that suite side by side, held together by its overlap barrier at the moment
both hold their tmux sessions, and compare each copy's case results with a
solo run: the same PASS names, no FAIL, no SKIP.

Run: python3 scripts/resupervise-seat-test-two-copies-at-once-test.py
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SUITE = Path(__file__).with_name("resupervise-seat-test.py")
GIT_REDIRECTING_VARIABLES = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
                             "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR")
BARRIER_POINTS = ("default-server-session-held", "per-seat-server-session-held")
COPY_TIMEOUT_SECONDS = 300
COLLECTOR_STAND_IN_DEADLINE_SECONDS = 10
# More than any pipe buffer, so a copy writing it to an unread pipe would block.
COLLECTOR_STAND_IN_OUTPUT_BYTES = 1024 * 1024

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def copy_environment(**extra):
    environment = {k: v for k, v in os.environ.items() if k not in GIT_REDIRECTING_VARIABLES}
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment.update(extra)
    return environment


class Copy:
    """A started process, the file its output goes to, and the temp directory it was given."""

    def __init__(self, process, output_path, temp_directory):
        self.process = process
        self.output_path = output_path
        self.temp_directory = temp_directory


def start_command(command, scratch, label, **extra):
    """Start a command whose output goes to its own file, so no copy can block on an unread pipe.

    Its TMPDIR is its own directory under the scratch, so whatever the copy leaves
    behind when it dies stays where the parent can remove it.
    """
    temp_directory = scratch / f"{label}-tmp"
    temp_directory.mkdir()
    output_path = scratch / f"{label}.out"
    with open(output_path, "w", encoding="utf-8") as output_file:
        process = subprocess.Popen(command, env=copy_environment(TMPDIR=str(temp_directory), **extra),
                                   stdout=output_file, stderr=subprocess.STDOUT)
    return Copy(process, output_path, temp_directory)


def start_copy(scratch, label, **extra):
    return start_command([sys.executable, "-B", str(SUITE)], scratch, label, **extra)


def finish(copy, timeout=COPY_TIMEOUT_SECONDS):
    try:
        copy.process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        copy.process.kill()
        copy.process.wait()
        raise
    return copy.process.returncode, copy.output_path.read_text(encoding="utf-8", errors="replace")


def finish_all(copies, timeout=COPY_TIMEOUT_SECONDS):
    """Wait for every copy; each writes to its own file, so the order of waiting cannot stall one."""
    return [finish(copy, timeout) for copy in copies]


def leftover_workspaces(copy):
    return sorted(str(path) for path in copy.temp_directory.glob("resupervise-seat-test-*"))


def case_results(returncode, output):
    """The case identities a run printed, by verdict, plus its exit status and namespace."""
    results = {"exit": returncode, "PASS": set(), "FAIL": set(), "SKIP": set(), "namespace": None}
    for line in output.splitlines():
        verdict = line[:4]
        if verdict in ("PASS", "FAIL", "SKIP") and line[4:6] == "  ":
            results[verdict].add(line[6:].split(":", 1)[0] if verdict != "PASS" else line[6:])
        elif line.startswith("tmux namespace for this run: "):
            results["namespace"] = line.split(": ", 1)[1].strip()
    return results


def differences_from_solo(solo, copy):
    """Every way a copy's results differ from the solo run; empty when they match."""
    differences = []
    if copy["exit"] != solo["exit"]:
        differences.append(f"exit {copy['exit']}, solo exit {solo['exit']}")
    missing = solo["PASS"] - copy["PASS"]
    extra = copy["PASS"] - solo["PASS"]
    if missing:
        differences.append(f"{len(missing)} PASS case(s) the solo run had are missing: {sorted(missing)}")
    if extra:
        differences.append(f"{len(extra)} PASS case(s) the solo run did not have: {sorted(extra)}")
    for verdict in ("FAIL", "SKIP"):
        if copy[verdict] != solo[verdict]:
            differences.append(f"{verdict} cases {sorted(copy[verdict])}, solo {sorted(solo[verdict])}")
    return differences


def remove_leftover_namespace(namespace):
    """Kill the servers a copy that died at the barrier left in its own namespace, and remove it."""
    if not namespace:
        return
    socket_directory = Path(namespace) / f"tmux-{os.getuid()}"
    if socket_directory.is_dir():
        for socket in socket_directory.iterdir():
            subprocess.run(["tmux", "-S", str(socket), "kill-server"], capture_output=True, check=False)
    shutil.rmtree(namespace, ignore_errors=True)


def run_comparison_control_case(solo_output):
    """The comparison itself catches a copy that skipped, so a bypassed check cannot read as a match."""
    end_to_end_passes = {"PASS  the proceed path runs the launcher",
                         "PASS  the proceed path clears the stale tmux session",
                         "PASS  the record survives the exec into the launcher"}
    skipped = [line for line in solo_output.splitlines() if line not in end_to_end_passes] + [
        "SKIP  end-to-end: could not create a tmux session (duplicate session: resupervise-seat-test-seat)"]
    solo = case_results(0, solo_output)
    check("control: the solo run holds the three end-to-end checks the control removes",
          end_to_end_passes <= set(solo_output.splitlines()), "a check was renamed; update the control")
    differences = differences_from_solo(solo, case_results(0, "\n".join(skipped)))
    check("control: a copy that skipped its tmux checks but exited 0 is reported as different",
          any("missing" in d for d in differences) and any(d.startswith("SKIP") for d in differences),
          f"differences found: {differences}")
    check("control: a solo run compared with itself shows no difference",
          differences_from_solo(solo, solo) == [], str(differences_from_solo(solo, solo)))


def run_two_copies_case(solo, scratch, barrier_directory):
    """Two copies hold their default-server and per-seat sessions at the same moment; each matches solo."""
    environment = {"RESUPERVISE_SEAT_TEST_OVERLAP_BARRIER_DIRECTORY": str(barrier_directory),
                   "RESUPERVISE_SEAT_TEST_OVERLAP_PEER_COUNT": "2"}
    first = start_copy(scratch, "two-copies-first", **environment)
    second = start_copy(scratch, "two-copies-second", **environment)
    results = [case_results(*outcome) for outcome in finish_all([first, second])]
    for point in BARRIER_POINTS:
        arrivals = list(barrier_directory.glob(f"{point}-arrived-*"))
        releases = list(barrier_directory.glob(f"{point}-released-*"))
        check(f"both copies reached the barrier where they hold their sessions: {point}",
              len(arrivals) == 2 and len(releases) == 2,
              f"{len(arrivals)} arrival(s), {len(releases)} release(s)")
        # Neither copy may leave before both arrive, or the copies never held their sessions together.
        if arrivals and releases:
            last_arrival = max(path.stat().st_mtime_ns for path in arrivals)
            first_release = min(path.stat().st_mtime_ns for path in releases)
            check(f"both copies held their sessions at the same moment: {point}",
                  first_release >= last_arrival,
                  f"a copy left {last_arrival - first_release} ns before the other arrived")
    for label, copy in zip(("first", "second"), results):
        differences = differences_from_solo(solo, copy)
        check(f"the {label} of two overlapping copies has the solo run's cases and verdict",
              differences == [], "; ".join(differences))
    check("the two overlapping copies used different tmux namespaces",
          results[0]["namespace"] and results[1]["namespace"]
          and results[0]["namespace"] != results[1]["namespace"],
          f"{results[0]['namespace']} and {results[1]['namespace']}")
    leftovers = [copy["namespace"] for copy in results if copy["namespace"] and Path(copy["namespace"]).exists()]
    check("each copy removed its own tmux namespace when it finished", not leftovers, f"left: {leftovers}")
    workspaces = leftover_workspaces(first) + leftover_workspaces(second)
    check("each copy removed its own workspace when it finished", not workspaces, f"left: {workspaces}")


def run_copy_killed_at_barrier_case(solo, scratch, barrier_directory):
    """A copy that dies while holding its per-seat server session takes nothing from the other copy.

    It dies at the last barrier so the surviving copy never waits for a peer that is gone.
    """
    environment = {"RESUPERVISE_SEAT_TEST_OVERLAP_BARRIER_DIRECTORY": str(barrier_directory),
                   "RESUPERVISE_SEAT_TEST_OVERLAP_PEER_COUNT": "2"}
    dying = start_copy(scratch, "copy-killed-dying", **environment,
                       RESUPERVISE_SEAT_TEST_OVERLAP_EXIT_AT_BARRIER=BARRIER_POINTS[-1])
    surviving = start_copy(scratch, "copy-killed-surviving", **environment)
    (dying_exit, dying_output), surviving_outcome = finish_all([dying, surviving])
    surviving_results = case_results(*surviving_outcome)
    dying_results = case_results(dying_exit, dying_output)
    remove_leftover_namespace(dying_results["namespace"])
    abandoned = leftover_workspaces(dying)
    check("the dying copy's abandoned workspace is in its own temp directory, where it can be removed",
          len(abandoned) == 1, f"found: {abandoned}")
    # The dying copy exits without running its own cleanup, so its workspace is removed here.
    shutil.rmtree(dying.temp_directory, ignore_errors=True)
    check("the copy told to die at the barrier did die there", dying_exit == 9, f"exit {dying_exit}")
    workspaces = leftover_workspaces(surviving) + (
        [str(dying.temp_directory)] if dying.temp_directory.exists() else [])
    check("no workspace of either copy is left after a copy died at the barrier",
          not workspaces, f"left: {workspaces}")
    differences = differences_from_solo(solo, surviving_results)
    check("the surviving copy still has the solo run's cases and verdict",
          differences == [], "; ".join(differences))


def run_collector_does_not_stall_case(scratch):
    """A copy that writes much before the barrier cannot stall the copy waiting for it.

    The first stand-in waits for a marker the second creates only after writing
    more than a pipe buffer holds. Collected from pipes, one after the other,
    the second blocks on its full pipe and the first times out.
    """
    marker = scratch / "collector-stand-in-marker"
    waiter = (f"import os, sys, time\n"
              f"deadline = time.monotonic() + {COLLECTOR_STAND_IN_DEADLINE_SECONDS}\n"
              f"while not os.path.exists({str(marker)!r}):\n"
              f"    if time.monotonic() > deadline:\n"
              f"        print('the marker never appeared'); sys.exit(1)\n"
              f"    time.sleep(0.05)\n"
              f"print('waiter saw the marker')\n")
    writer = (f"import sys\n"
              f"sys.stdout.write('x' * {COLLECTOR_STAND_IN_OUTPUT_BYTES}); sys.stdout.flush()\n"
              f"open({str(marker)!r}, 'w').close()\n")
    waiting = start_command([sys.executable, "-c", waiter], scratch, "collector-waiter")
    writing = start_command([sys.executable, "-c", writer], scratch, "collector-writer")
    try:
        outcomes = finish_all([waiting, writing], timeout=2 * COLLECTOR_STAND_IN_DEADLINE_SECONDS)
    except subprocess.TimeoutExpired as stalled:
        for copy in (waiting, writing):
            if copy.process.poll() is None:
                copy.process.kill()
                copy.process.wait()
        check("a copy writing more than a pipe buffer before the barrier does not stall the other",
              False, f"collection timed out: {stalled}")
        return
    check("a copy writing more than a pipe buffer before the barrier does not stall the other",
          outcomes[0][0] == 0 and "waiter saw the marker" in outcomes[0][1],
          f"waiter exit {outcomes[0][0]}: {outcomes[0][1][-200:]}")
    check("a copy's full output reaches its file",
          outcomes[1][0] == 0 and len(outcomes[1][1]) == COLLECTOR_STAND_IN_OUTPUT_BYTES,
          f"writer exit {outcomes[1][0]}, {len(outcomes[1][1])} bytes")


def run_creation_failure_case(scratch):
    """With tmux installed but unable to make a session, the suite fails; it does not skip to green."""
    real_tmux = shutil.which("tmux")
    fake_bin = scratch / "fake-tmux-bin"
    fake_bin.mkdir()
    fake_tmux = fake_bin / "tmux"
    fake_tmux.write_text(
        "#!/bin/sh\n"
        'for argument in "$@"; do\n'
        '  if [ "$argument" = new-session ]; then echo "forced creation failure" >&2; exit 1; fi\n'
        "done\n"
        f'exec "{real_tmux}" "$@"\n', encoding="utf-8")
    fake_tmux.chmod(0o755)
    returncode, output = finish(start_copy(scratch, "creation-failure",
                                           PATH=f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}"))
    results = case_results(returncode, output)
    check("a forced tmux creation failure makes the suite exit nonzero", returncode != 0,
          f"exit {returncode}")
    check("both tmux cases report the creation failure as FAIL",
          {"end-to-end", "per-seat end-to-end"} <= results["FAIL"], f"FAIL cases {sorted(results['FAIL'])}")
    check("no tmux case is skipped when tmux is installed", not results["SKIP"],
          f"SKIP cases {sorted(results['SKIP'])}")


def main() -> int:
    if shutil.which("tmux") is None:
        print("SKIP  two copies at once: tmux is not installed, so the suite has no tmux cases to collide")
        return 0
    with tempfile.TemporaryDirectory(prefix="resupervise-two-copies-") as scratch_name:
        scratch = Path(scratch_name)
        solo_exit, solo_output = finish(start_copy(scratch, "solo"))
        solo = case_results(solo_exit, solo_output)
        check("the solo run passes with no FAIL and no SKIP",
              solo_exit == 0 and not solo["FAIL"] and not solo["SKIP"] and solo["PASS"],
              solo_output[-2000:])
        if failures:
            print(f"\n{len(failures)} case(s) failed: {', '.join(failures)}")
            return 1
        run_comparison_control_case(solo_output)
        run_collector_does_not_stall_case(scratch)
        first_barriers = scratch / "barriers-two-copies"
        first_barriers.mkdir()
        run_two_copies_case(solo, scratch, first_barriers)
        second_barriers = scratch / "barriers-copy-killed"
        second_barriers.mkdir()
        run_copy_killed_at_barrier_case(solo, scratch, second_barriers)
        run_creation_failure_case(scratch)

    print()
    if failures:
        print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
        return 1
    print("all cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
