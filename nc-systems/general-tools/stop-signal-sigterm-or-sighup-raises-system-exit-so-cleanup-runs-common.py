"""Turn SIGTERM and SIGHUP into SystemExit while a `with` block runs, so the block's finally clauses run.

A Bash tool timeout or TaskStop stops a program with SIGTERM, and a closing terminal sends SIGHUP; by
default either ends the process at once, so a finally that removes a temporary directory or a git
worktree never runs. Inside stop_signals_raise_system_exit_so_cleanup_runs(), either signal raises
SystemExit(128 + the signal number), the code a shell gives a process the signal killed; the context
manager puts the previous handlers back when the block ends.

What it does not handle: SIGKILL, which no handler can catch; a block run outside the main thread,
where signal.signal raises ValueError; and children of the program, which get the signal only when it is
sent to their process group. A second signal during cleanup raises again, interrupting that cleanup.

Unlike the Bash guards replay's stop_deferred(), the SystemExit is not deferred around subprocess calls:
the replay polls Popen.wait() in a loop and so meets the gap in Popen._wait() where a raise leaves the
wait lock held, while a caller blocked once in subprocess.run() almost never does. If the raise does hit
that gap, the program hangs in subprocess.run() until it is killed, and its cleanup does not run.
"""

import contextlib
import signal

STOP_SIGNALS = (signal.SIGTERM, signal.SIGHUP)


def raise_system_exit_for_stop_signal(signal_number, _frame):
    raise SystemExit(128 + signal_number)


@contextlib.contextmanager
def stop_signals_raise_system_exit_so_cleanup_runs():
    previous_handlers = {number: signal.signal(number, raise_system_exit_for_stop_signal)
                         for number in STOP_SIGNALS}
    try:
        yield
    finally:
        for number, handler in previous_handlers.items():
            signal.signal(number, handler)
