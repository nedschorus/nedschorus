# How a program reports success, failure and findings with its exit code

Every script, hook and test suite in this project ends with an exit code, and other programs, shells, CI steps and agents act on that code before they read any output. A code that means one thing in one program and the opposite in another makes a caller stop on success or carry on after a failure. This page sets what each code means, so a caller can act on the code alone and read the output for the details.

## The rule

A program does its work and prints whatever it finds or reports; its exit code answers one yes-or-no question about that invocation, stated in one line of its `--help` and of its first docstring line. A program with several modes, such as a `--check` mode beside its normal work, states one question for each mode:

- **0**: yes.
- **1**: no. The output says what was found or what was not done.
- **2**: the program could not answer, for example because it was called the wrong way, a file was missing, ned-box could not be reached, or the program crashed. The output says why and what to do.

So "could not answer" always has its own code, 2, and never shares one with an answer, and exit 1 from any program means the same thing: the answer is no. Unix standardizes only 0 for success and nonzero for failure, and many Unix programs exit with codes above 2, such as `timeout` with 124 and `ssh` with 255; this page adopts for every program the convention of `grep`, `diff` and `cmp`: `grep` exits 0 if a line is selected, 1 if no lines were selected, and 2 if an error occurred, and `diff` and `cmp` exit 0 if their inputs are the same, 1 if different, and 2 if trouble. Each question is phrased so that yes is the outcome a caller can go ahead on. The sections below give the question for each kind of program.

A program that crashes could not answer, but a Python program that stops on an exception nothing caught exits 1, which a caller would read as "no": a crashed conflict check as "conflict found", a crashed search as "not found". So every program catches what it did not expect at its top level, prints the cause, and exits 2. A Claude Code hook's top level exits 1 instead, the code the Hooks section below gives for a Claude Code hook that breaks, with the one exception that section gives.

When one invocation answers its question and also does other work, such as a search that also copies what it found, the question decides between 0 and 1, and any part of the invocation that could not be done makes it 2, whatever the answer was, because 1 already means "no" to the question. Such a program follows the section for its question, not the section A program that does work. `grep` does the same unless given `-q`: it exits 2 when an error occurred, even when it selected lines elsewhere.

## A program that checks something

A check asks "is everything right?": a linter, a conflict check, a citation check, a test suite, and a `--check` mode of any program. A program that decides whether something may go ahead is a check too: the main-gatekeeper, deciding whether a change may go to main, asks "may this go ahead?", and exits 1 when it refuses. A check follows the convention of `diff`, `shellcheck` and `git diff --exit-code`:

- **0**: it checked everything it was asked to, and found nothing wrong.
- **1**: it checked everything it was asked to, and found something; the findings are in its output.
- **2**: it could not check everything it was asked to. A check that could not read one file, or could not reach one machine, exits 2 even when it found something elsewhere, because a caller that reads 0 or 1 takes the check as complete. It still prints what it found, and says what it could not check.

A test file, a file whose name ends in `-test.py`, is a check like any other: it exits 0 when every test case passes, 1 when a test case fails, and 2 when it could not run. A file Python cannot start, such as one with a syntax error, exits 1 before any of the file's code runs, so the file's own top level never gets the chance to exit 2. So every test file prints a verdict line, as the section What every program prints with its code says, and `scripts/run-all-test-suites.py`, which runs the test files, reads an exit 1 with no verdict line as could not run, 2. Today the runner reads every nonzero code as a failure; reading the verdict line is work still to be done.

A test file's verdict line is one exact hashtag line per outcome, as canary tests do with `#canary_pass` and `#canary_fail`. The exact form of each line is set by the wiki page on how a test reports its result, which the agent-seat MD-skills is writing.

## A program that searches or answers a question

A search asks "is it there?", and a query asks "is it so?": a file locator, a backup search, a transcript search, a mode that asks whether a supervisor is running. It follows the convention of `grep` and `test`:

- **0**: it searched everywhere it was asked to, and the answer is yes: found, running, attached.
- **1**: it searched everywhere it was asked to, and the answer is no: not found, not running.
- **2**: it could not search everywhere it was asked to, or could not tell. A search that found a copy but could not search one backup exits 2, and prints the copy it found.

The `--help` line reads, for example: "Exits 0 if the path is found, 1 if it is found nowhere, 2 if a place could not be searched."

A search prints what it found on stdout, as `grep` does, so a search that finds nothing prints nothing there, apart from its verdict line when its `--help` says it prints one. It then prints one line on stderr saying where it looked, which a person or an agent sees but a caller saving the results does not, such as "find-deleted-path-across-backups: searched git and 4 Time Machine backups; the path is in none of them."

## A program that does work

A program that does work, such as copying, building, installing, cleaning up, filing a GHI, asking an agent, or printing a report or a status, asks "did all the work get done?":

- **0**: yes, it did all the work it was asked to do. A status report exits 0 when it read the status, whatever the status is. When the work is asking an agent, any reply the agent gives counts as work done, a refusal included; the kind of reply goes in the verdict line, for the caller to read.
- **1**: no, not all of the work got done: a step failed, only part of the work was done, or the program refused on purpose, such as a request to cancel a change that has already reached main. The output says what was done, what was not, and why.
- **2**: it could not answer the question: it was called the wrong way, it crashed, or it could not tell whether the work got done.

Exit 1 for work that did not all get done keeps the rule above: 1 when the program can answer its question and the answer is no, 2 when it cannot answer. A cleanup that could not delete one worktree, or could not list the worktrees, can answer "not all done": it exits 1, and does not report success. A caller of a program that does work treats any nonzero code as a failure.

## Hooks

A hook follows the exit codes its host defines, not the three above:

- **A Claude Code hook** exits 0 to let the act go ahead, with any reminder in its output, and refuses the act on purpose either by exiting 2 or by a decision in its JSON output at exit 0, such as `"permissionDecision": "deny"`, as the Claude Code hooks reference (https://code.claude.com/docs/en/hooks) defines. What exit 2 does differs by hook event; the hooks reference's table "Exit code 2 behavior per event" gives each. When the hook itself breaks, for example because a command it runs fails, it exits 1 and prints what broke on its error output: on most events Claude Code then lets the act go ahead and shows the user a hook error notice with the first line of that output, so the break is seen and work is not stopped. When the agent's next act depends on the check having run, as with a guard that could not check a command, the hook instead exits 0 and tells the agent in `additionalContext`. A hook never turns its own failure into a silent 0.
- **A git hook** exits 0 to let the push or commit go ahead and 1 to refuse it; git refuses on any nonzero code. Each check the hook runs is a check as this page defines one, exiting 0, 1 or 2. The hook refuses on a check's 1. On a check's 2 it lets the push go ahead and prints that the check could not run and why, so that one broken check does not stop every agent-seat's pushes.

### What a Claude Code hook prints on each stream

Claude Code reads a Claude Code hook's output, and reads each stream in its own way at each exit code, as the hooks reference says:

- At exit 0, Claude Code reads stdout as JSON output when stdout holds one JSON object and nothing else. The object's `additionalContext` reaches the agent, and its `systemMessage` reaches the user. Plain text on stdout reaches the agent only on a few events, such as `UserPromptSubmit` and `SessionStart`. "Claude never sees stderr from a hook that exits 0."
- At exit 2, Claude Code stops the act on the events that can block it, and takes stderr as the reason. Who sees the reason differs by event: the agent on `PreToolUse`, for example, but only the user on `UserPromptSubmit`; the table "Exit code 2 behavior per event" gives each.
- At any other code, the user sees a hook error notice that carries the first line of stderr, and the hooks reference gives the agent no way to see any of it. Valid JSON output on stdout at such a code makes Claude Code ignore the code and act on the JSON alone.

So a Claude Code hook writes each stream for the reader Claude Code gives that stream:

- To tell the agent something, the hook puts it in `additionalContext` in its JSON output, and exits 0.
- To refuse the act, the hook exits 2, with the reason on stderr, or exits 0 with the decision and its reason in its JSON output.
- When the hook breaks, it catches the error, prints the whole cause as the first line of stderr, not a multi-line traceback, prints nothing on stdout, and exits 1. Only the first line reaches the user, and JSON on stdout would make Claude Code ignore the exit code. The one exception is a break that the agent's next act depends on, such as a guard that could not check a command: there the hook exits 0 and tells the agent in `additionalContext`, as the Claude Code hook bullet above says.
- The hook never writes to stderr when it exits 0, because the agent never sees stderr then, and the user sees it only in Claude Code's debug log.

These rules are exceptions to the rest of this page. Exit 2 from a Claude Code hook means "refuse", not "could not answer" as in the section The rule, and a hook that could not answer, because it broke, exits 1, which from any other program means "no". The rules also differ from "What every program prints with its code": a hook prints no verdict line; its refusal reason goes on stderr or in its JSON output, never on stdout as plain text with the rest of an answer; a warning it has for the agent goes in `additionalContext`, and one for the user in `systemMessage`, never on stderr as other programs' warnings and progress do; and the cause of a break goes on stderr as for any program, but whole on its first line, which only the user sees.

## What every program prints with its code

- The output and the exit code always agree: a program never prints that the answer is yes and exits 1, or prints an error and exits 0.
- A caller that needs more than the code, such as which conflict or which kind of reply, reads a fixed verdict line in the output, such as `VERDICT: CONFLICT`. The verdict line adds detail; it never contradicts the code.
- A program whose `--help` says it prints a verdict line, and every test file, prints that line on stdout, as the last line, whether the exit code is 0, 1 or 2; under `--json`, inside the JSON. This page does not yet set how the verdict goes inside the JSON, only that it goes there.
- The verdict line, on stdout, names the outcome; the cause goes on stderr.
- A program that crashes before it prints its verdict line still prints one: its top-level catch prints a verdict line saying it could not answer, then exits 2.
- A program whose `--help` says it prints a verdict line, and every test file, also prints its findings on stdout, because findings are part of the answer, and that includes what the program found when it exits 1. The program prints the cause of a failure, and what to do about it, on stderr.
- A caller of a program whose `--help` says it prints a verdict line decides what to do from the exit code and stdout alone. The caller may show the program's stderr to a person, but never searches stderr to decide what to do. `scripts/merge-gate.sh` shows the case this rule prevents: the script prints its pass line on stdout, at line 390, but `GATE REFUSED` on stderr, at line 133, so its caller, `scripts/merge-lane-pull-request-merge-through-merge-gate-with-stacked-pull-request-retarget.py`, merges the two streams at line 106 and searches them at line 108 for the words `mergeStateStatus is UNKNOWN` to decide whether to run `merge-gate.sh` again.
- A program prints its progress, its warnings and its error messages on stderr, each starting with the program's name, and its answer on stdout, with its verdict line if it prints one, so that stdout holds only the answer. Progress is the running commentary a long program prints so a person can see the program has not stopped, such as "running suite 12 of 40".
- A program that offers `-q`, quiet, or `-v`, verbose, changes with them only what it prints on stderr, never what it prints on stdout, and `-q` never hides an error.
- A program that prints colour colours only text going to a terminal, and never when the `NO_COLOR` environment variable is set, because a colour code in a file or a pipe is a few characters of garbage in the middle of the text.
- A program asked for help with `--help` or `-h` prints the help on stdout and exits 0, because the help is the answer that was asked for. A program called the wrong way, such as with a missing argument, prints the error and its short usage line on stderr and exits 2, because it could not answer. `scripts/merge-gate.sh` does both: for `--help`, lines 142 to 150 print its help on stdout and exit 0, and at line 152 it prints on stderr that it takes exactly three arguments, and exits 2.
- A program that offers machine-readable output, such as JSON, prints that output on stdout, and only when asked, for example with `--json`, so a person running the program still reads plain sentences. Under `--json`, any verdict goes inside the JSON.
- Under `--json`, a program that exits 1 or 2 still prints its JSON on stdout, with the verdict inside; the cause still goes on stderr.
- A program that exits 1 or 2 prints why, and what to do, as the page [How to write an agent-facing-message](nedschorus-how-to-write-an-agent-facing-message-such-as-a-hook-refusal-or-script-error.md) says.
- No program uses a code above 2, unless its host requires one. A program that runs another program on another machine, such as over ssh, passes that program's code through unchanged; ssh's own 255, for a connection that failed, is above 2, so callers read it as 2. More outcomes than these go in the verdict line, because a caller checking for nonzero cannot tell 3 from 1.

## A caller

- A shell line, a CI step or a program that runs a check or a search decides on the code, 0, 1 or 2, and treats any code above 2, such as one a shell gives for a killed program, as 2. It never treats "nonzero" as one outcome when the program can exit 1 with an answer.
- A caller that runs a program and continues anyway, such as with `|| true`, says in its own output that it continued after a failure.
- A function called from other code reports a failure by raising an error, not by returning a code; only a program's top level turns that error into an exit code.

## Designs not yet built

A design or a GHI-MD that specifies a program's exit codes follows this page. A design written before this page that specifies other codes is changed to match before its program is built.
