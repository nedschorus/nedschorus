# Part four: the messages of the test suites that enforce a repository-wide rule

This document is part four of GHI [Every refusal and warning a program hands an agent says why and what to do instead](https://github.com/nedschorus/nedschorus/issues/956). The GHI's GHI-MD, `docs/issues/956-every-refusal-and-warning-a-program-hands-an.md`, is part one, and its section "Later parts" lists the parts after it. Part two, `docs/issues/956-part-two-the-git-hooks-messages.md`, covered the git hooks. This part covers the failure messages of ten test suites that check a rule about the whole repository rather than one program's behavior. It shows each message that leaves the agent a question open, as the agent sees the message, and proposes the exact words to replace it, with the code changes the new words need. None of the proposed wording is built. The next action is a cold-read-full-run of this document, then one approval-walk with the user, then one pull request, cut from main, that builds what the user approves, with its test cases.

## What a reader needs first

**Which suites.** A test suite here is a file named `*-test.py` that `scripts/run-all-test-suites.py` runs. Most suites test one program. The ten in this part instead check a rule that holds across files: that no two tracked files share a name, that a list in one file matches the definitions in another, that a design document and the code agree. They are:

- `scripts/file-name-collision-warning-hook-test.py`
- `scripts/system-glossaries-listed-on-the-project-glossary-test.py`
- `scripts/pr-reviewer-instructions-copies-test.py`
- `scripts/supervisor-file-names-defined-once-test.py`
- `scripts/walk-file-endings-match-the-skill-test.py`
- `scripts/nedschorus-glossary-alphabetical-order-test.py`
- `nc-systems/cold-read/tests/cold-read-record-names-test.py`
- `scripts/design-to-main/tests/design-to-main-design-names-exist-in-state-tables-test.py`
- `scripts/design-to-main/tests/design-to-main-design-rows-pair-with-state-tables-test.py`
- `scripts/force-push-with-open-pull-request-guard-hook-test.py`, for its two cases that read `.claude/settings.json`

**Who reads the failure.** An agent runs the suites its change can affect before pushing, as CLAUDE.md says: "Before pushing, run only the test suites your change can affect: `python3 scripts/run-all-test-suites.py --only-suites-whose-recorded-inputs-changed-since origin/main`." merge-lane-2 runs the same selection on the pull request's head commit merged onto main. Either way, the reader of a failure is usually an agent whose change broke a rule written in a file the agent never opened, such as a skill, a design or `.claude/settings.json`. The failure is the agent's only account of that rule. So a complete failure message says which rule broke, where the rule is written, what the agent's change did to break it, and how to fix it. When the fix belongs in a file the agent may not change on its own, it says so.

**How a failure is printed.** Eight of the ten suites print one line per case through a `check()` function: `PASS  <case name>` or `FAIL  <case name>: <detail>`. The detail is the message. The two design-to-main suites use Python's `unittest`, where a failed assertion prints the assertion's message, or, when the assertion has none, only the values compared, such as `AssertionError: ['row 24: from-states …'] != []`.

**Files an agent may not change alone.** The instruction-file guard, `.claude/hooks/instruction-file-guard.py`, refuses an edit to any file under `.claude/` until the user's approval is quoted into its marker. Two of the files that write the rules below are such files: `.claude/skills/walk-me-through/SKILL.md` and `.claude/settings.json`. A message whose fix is there says to ask the user.

**The four questions.** As in parts one and two, a message is complete when the message says:

1. What was refused or found, naming the file or the command.
2. Why: the rule being enforced, or what goes wrong if the agent goes ahead.
3. What to do instead, as an instruction.
4. Under which condition each instruction applies, when the message gives more than one.

**Where the list comes from.** Part one's audit put these four questions to 139 messages printed by this repository's programs; its report is `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/MD-skills/refusal-and-warning-message-audit-2026-10-01.md`. It read 38 messages from these ten suites at commit cfd6516f and found 20 with a gap. Every message below was read again from main at the commit [Merge pull request #1075 from nedschorus/ghi-956-edit-ghipairef15a4328a1316b6](https://github.com/nedschorus/nedschorus/commit/c16466b6), and the line numbers are main's at that commit. The rereading confirmed the audit's 20 and found one more, message 17. Message 1's two forms are one message, as the audit counted them, and message 16's three assertions are three.

## What every failure should tell the agent

Each proposed text keeps the suite's own first sentence, which says what was found, and adds lines after it:

- one sentence naming the rule and the file that writes it, when the first sentence does not;
- one line per fix, each opening with the condition it applies under, such as "If your change renamed one of those programs";
- for a fix in a file under `.claude/`, a line saying to ask the user to approve that change;
- for a failure the agent's change did not cause, a line saying to tell the user, because the fix belongs to whoever made the change.

A failure an agent did not cause is common for these suites: a rule can break on main when two pull requests that each pass merge together. The agent can tell by checking whether its change touches the files the message names, with `git diff --name-status origin/main...HEAD`.

## The messages, one at a time

### 1. Two tracked files share a name

**When an agent sees this.** An agent adds `scripts/stale-branch-report.py` while `nc-systems/handoff/stale-branch-report.py` already exists, and runs the suites.

**What the agent is told today** (`scripts/file-name-collision-warning-hook-test.py:480`; when git cannot list the files, the same case prints git's error instead, at `:477`):

```
FAIL  no two tracked files in this repository share a name: over 446 names: stale-branch-report.py: nc-systems/handoff/stale-branch-report.py, scripts/stale-branch-report.py
```

```
FAIL  no two tracked files in this repository share a name: git ls-files exited 128 in /Users/el/agents/wt-x: fatal: not a git repository
```

**What the agent cannot tell from the text.** Why two files may not share a name, what to do, and what to do when the agent's change added neither file. The second form does not say that nothing was checked.

**Proposed text** (`{listing}` is today's detail):

```
FAIL  no two tracked files in this repository share a name: {listing}
A basename, other than SKILL.md, README.md and .gitkeep, belongs to one tracked file, so a file can be cited by its basename.
If your change added or renamed one of those files, rename it by CLAUDE.md's naming rule and update what points at it.
If your change added none of those files, tell the user which files collide.
```

```
FAIL  no two tracked files in this repository share a name: git ls-files exited {status} in {checkout}: {error}
The suite could not list this checkout's tracked files, so it checked nothing.
Fix what git reports, then run this suite again.
```

### 2. The project glossary's listing paragraph is missing

**When an agent sees this.** An agent rewords the paragraph of `docs/nedschorus-wiki/nedschorus-glossary.md` that lists the system glossaries, and the sentence "A new system glossary is listed here when it is created" is gone.

**What the agent is told today** (`scripts/system-glossaries-listed-on-the-project-glossary-test.py:168`):

```
FAIL  the project glossary's paragraph listing the system glossaries is located: the paragraph could not be located: no paragraph of docs/nedschorus-wiki/nedschorus-glossary.md carries "A new system glossary is listed here when it is created" — put that wording back in the paragraph above the entries, or set SYSTEM_GLOSSARY_PARAGRAPH_ANCHOR in scripts/system-glossaries-listed-on-the-project-glossary-test.py to wording that paragraph carries
```

**What the agent cannot tell from the text.** Which of the two fixes applies when.

**Proposed text** (`{page}`, `{anchor}` and `{suite}` as today):

```
FAIL  the project glossary's paragraph listing the system glossaries is located: no paragraph of {page} carries "{anchor}", the wording this suite finds the paragraph by.
If your change reworded that sentence by mistake, put the wording back.
If the new wording is meant to stay, set SYSTEM_GLOSSARY_PARAGRAPH_ANCHOR in {suite} to wording only that paragraph carries.
```

### 3. The listing paragraph's wording appears twice

**When an agent sees this.** An agent copies the listing paragraph's sentence into a glossary entry.

**What the agent is told today** (`scripts/system-glossaries-listed-on-the-project-glossary-test.py:175`):

```
FAIL  the project glossary's paragraph listing the system glossaries is located: the paragraph could not be located: 2 paragraphs of docs/nedschorus-wiki/nedschorus-glossary.md carry "A new system glossary is listed here when it is created" — leave that wording in the one paragraph above the entries, or set SYSTEM_GLOSSARY_PARAGRAPH_ANCHOR in scripts/system-glossaries-listed-on-the-project-glossary-test.py to wording only that paragraph carries
```

**What the agent cannot tell from the text.** Which fix applies when.

**Proposed text:**

```
FAIL  the project glossary's paragraph listing the system glossaries is located: {count} paragraphs of {page} carry "{anchor}", the wording this suite finds the paragraph by, so it cannot tell which one lists the system glossaries.
If your change copied that wording into another paragraph, reword the copy.
If both paragraphs are meant to keep it, set SYSTEM_GLOSSARY_PARAGRAPH_ANCHOR in {suite} to wording only the listing paragraph carries.
```

### 4. The project glossary names a glossary git does not track

**When an agent sees this.** An agent renames `nc-systems/handoff/handoff-glossary.md`, and the project glossary still names the old path.

**What the agent is told today** (`scripts/system-glossaries-listed-on-the-project-glossary-test.py:280`):

```
FAIL  every glossary path the project glossary names is one git tracks: named but not tracked: ['nc-systems/handoff/handoff-glossary.md'] — correct each in docs/nedschorus-wiki/nedschorus-glossary.md to a path git tracks, or commit the file it names
```

**What the agent cannot tell from the text.** Which fix applies when, and what to do for a glossary that was deleted.

**Proposed text** (`{absent}` and `{page}` as today):

```
FAIL  every glossary path the project glossary names is one git tracks: named but not tracked: {absent}
If your change renamed one of those glossaries, correct its path in {page}.
If your change deleted one, remove it from {page}.
If one is new and not yet committed, commit it.
```

### 5. A program this suite watches has moved out of its sight

**When an agent sees this.** An agent moves `scripts/recover-crashed-seats.py` to `nc-systems/handoff/tools/recover-crashed-seats.py`.

**What the agent is told today** (`scripts/supervisor-file-names-defined-once-test.py:702`):

```
FAIL  every program that needs these names is among the scripts read: ['recover-crashed-seats.py'] not found under scripts/ or nc-systems/*/ -- a program this suite exists to watch has moved somewhere it does not read, and the cases below now pass on it by finding nothing
```

**What the agent cannot tell from the text.** What to do. A deleted program is treated the same as a moved one.

**Proposed text** (`{programs}` as today; `{suite}` is the suite's path):

```
FAIL  every program that needs these names is among the scripts read: {programs} not found under scripts/ or nc-systems/*/, the directories this suite reads, so the cases below cannot see them.
If your change moved one of those programs to another directory, add that directory to production_scripts() in {suite}.
If your change renamed one, rename it in PROGRAMS_THAT_NEED_THESE_FILE_NAMES in {suite}.
If your change deleted one, remove it from PROGRAMS_THAT_NEED_THESE_FILE_NAMES in {suite}.
```

### 6. A suffix constant is defined outside the supervisor

**When an agent sees this.** An agent defines `HANDOFF_FILE_SUFFIX = "-handoff.md"` in `scripts/recover-crashed-seats.py` instead of importing it.

**What the agent is told today** (`scripts/supervisor-file-names-defined-once-test.py:786`):

```
FAIL  the suffix constants are defined in one script: defined in ['handoff-supervisor.py', 'recover-crashed-seats.py'], expected only handoff-supervisor.py
```

**What the agent cannot tell from the text.** Why one script, and what to do.

**Proposed text** (`{defining}` and `{supervisor}` as today):

```
FAIL  the suffix constants are defined in one script: defined in {defining}, expected only {supervisor}, so that renaming one of these file names is one edit.
If a script other than {supervisor} defines one, delete that definition and use the constant from {supervisor}.
If {supervisor} no longer defines them, put the definitions back in {supervisor}.
```

### 7. The walk skill no longer names its files' endings

**When an agent sees this.** An agent edits `.claude/skills/walk-me-through/SKILL.md` and writes the files' names as `docs/walk/NAME-draft.md` instead of `docs/walk/<name>-draft.md`.

**What the agent is told today** (`scripts/walk-file-endings-match-the-skill-test.py:64`):

```
FAIL  the skill names the walk files' endings: found only [''] in SKILL.md; the pattern this test reads is <name>-<role>.md
```

**What the agent cannot tell from the text.** Why the skill must name the endings, and what to do.

**Proposed text** (`{suffixes}` as today):

```
FAIL  the skill names the walk files' endings: found only {suffixes} in .claude/skills/walk-me-through/SKILL.md, which decides the endings of an approval-walk's files; this suite finds them written as <name>-<role>.md and needs at least four.
If your change rewrote those names in the skill, write them in the <name>-<role>.md form again; the skill is under .claude/, so ask the user to approve that change.
```

### 8. The cold read builds a walk file ending the skill does not name

**When an agent sees this.** An agent changes `WALK_SUGGESTIONS_SUFFIX` in `nc-systems/cold-read/cold-read-fast-read.py` to `-review.md`.

**What the agent is told today** (`scripts/walk-file-endings-match-the-skill-test.py:72`):

```
FAIL  cold-read-fast-read.py WALK_SUGGESTIONS_SUFFIX is an ending the skill names: builds '-review.md', which SKILL.md does not name; the skill decides the endings, so change the skill first or follow it
```

**What the agent cannot tell from the text.** When to change the skill and when to follow it, and that changing the skill needs the user.

**Proposed text** (`{constant}` and `{ending}` as today):

```
FAIL  cold-read-fast-read.py {constant} is an ending the skill names: builds {ending}, which .claude/skills/walk-me-through/SKILL.md does not name; the skill decides the endings of an approval-walk's files.
If your change set {constant} in nc-systems/cold-read/cold-read-fast-read.py, set it to an ending the skill names.
If the skill should name the new ending, ask the user to approve that change to the skill, which is under .claude/.
```

### 9. The walk shipper ships an ending the skill does not name

**When an agent sees this.** An agent adds a role `-notes` to `WALK_FILE_ROLES` in `scripts/walk-files-ship.py`.

**What the agent is told today** (`scripts/walk-file-endings-match-the-skill-test.py:80`):

```
FAIL  every walk-files-ship.py role suffix is one the skill names: ships ['-notes'], which SKILL.md does not name
```

**What the agent cannot tell from the text.** Why it matters, and what to do.

**Proposed text** (`{unnamed}` as today):

```
FAIL  every walk-files-ship.py role suffix is one the skill names: ships {unnamed}, which .claude/skills/walk-me-through/SKILL.md does not name; the skill decides the endings of an approval-walk's files.
If your change added or renamed a role in WALK_FILE_ROLES in scripts/walk-files-ship.py, use an ending the skill names.
If the skill should name the new ending, ask the user to approve that change to the skill, which is under .claude/.
```

### 10. The cold read and the shipper disagree on the suggestions file

**When an agent sees this.** The fast read writes `-suggestions.md`, and an agent renames the shipper's suggestions role to `-suggestion`.

**What the agent is told today** (`scripts/walk-file-endings-match-the-skill-test.py:86`):

```
FAIL  the fast read's suggestions ending is the shipper's suggestions role: the fast read writes '-suggestions.md' but the shipper's roles are ['-draft', '-suggestion', '', '-minutes', '-dispositions']
```

**What the agent cannot tell from the text.** What goes wrong, and what to do.

**Proposed text** (`{written}` and `{roles}` as today):

```
FAIL  the fast read's suggestions ending is the shipper's suggestions role: the fast read writes {written} but the shipper's roles are {roles}, so a walk draft's suggestions file would not be shipped to the log-store.
Make WALK_SUGGESTIONS_SUFFIX in nc-systems/cold-read/cold-read-fast-read.py and the suggestions role in WALK_FILE_ROLES in scripts/walk-files-ship.py the same ending, the one .claude/skills/walk-me-through/SKILL.md names.
```

### 11. The cold read's shared module lacks a name it owns

**When an agent sees this.** An agent renames `fresh_record_directory` in `nc-systems/cold-read/cold-read-record-names.py` to `new_record_directory`.

**What the agent is told today** (`nc-systems/cold-read/tests/cold-read-record-names-test.py:387`):

```
FAIL  the shared module defines every name it owns: cold-read-record-names.py is missing ['fresh_record_directory']
```

**What the agent cannot tell from the text.** Why the module must define the name, and what to do.

**Proposed text** (`{module}` and `{missing}` as today; `{suite}` is the suite's path):

```
FAIL  the shared module defines every name it owns: {module} is missing {missing}, names the suite's OWNED_NAMES says only {module} defines; with a name missing, the check that no cold-read program keeps its own copy finds nothing for it.
If your change renamed one of those names in {module}, rename it in OWNED_NAMES in {suite} too.
If your change deleted one and no program uses it, remove it from OWNED_NAMES in {suite}.
If a program still uses it, put its definition back in {module}.
```

### 12. The cold read's shared module looks runnable

**When an agent sees this.** An agent adds an `if __name__ == "__main__":` block to `nc-systems/cold-read/cold-read-record-names.py` to try a function by hand.

**What the agent is told today** (`nc-systems/cold-read/tests/cold-read-record-names-test.py:407`):

```
FAIL  the shared module has no command-line entry point: cold-read-record-names.py looks runnable; it is imported by five programs and should do nothing on its own
```

**What the agent cannot tell from the text.** What to do. "five programs" is a count that goes stale.

**Proposed text** (`{module}` as today):

```
FAIL  the shared module has no command-line entry point: {module} contains "__main__"; the cold-read programs import it, so it must do nothing on its own.
Remove its if __name__ == "__main__": block, and put any command-line program in a file of its own.
```

### 13. The design names something the code does not define

**When an agent sees this.** An agent renames the state `test-design-writing` to `test-design-drafting` in `scripts/design-to-main/design-to-main-state-tables.py`, and the design still names the old one.

**What the agent is told today** (`scripts/design-to-main/tests/design-to-main-design-names-exist-in-state-tables-test.py:213`):

```
AssertionError: Items in the first set but not the second:
'test-design-writing' : backticked in the design, defined by no code and on no list
```

**What the agent cannot tell from the text.** Which design, what to do, and what to do when the agent cannot tell whether the design or the code is right.

**Proposed message** (`{design}` is `docs/design-to-main/design-to-main-state-machine-design.md`):

```
backticked in {design}, defined by no code and on no list of this suite.
If the design misspells a name the code defines, correct the design.
If your change renamed or removed the name in scripts/design-to-main/, change the design to match.
If the word is not a name of the state machine, add it with its reason to BACKTICKED_TOKENS_THAT_ARE_NOT_MACHINE_NAMES in this suite.
If you cannot tell whether the design or the code is right, add the name to KNOWN_MISMATCHES_AWAITING_A_RULING in this suite and tell the user which name.
```

### 14. A name listed as defined elsewhere is no longer there

**When an agent sees this.** An agent removes a string from a module that `MACHINE_NAMES_DEFINED_OUTSIDE_THE_STATE_TABLES_MODULE` says defines it.

**What the agent is told today** (`scripts/design-to-main/tests/design-to-main-design-names-exist-in-state-tables-test.py:230`; the assertion has no message):

```
AssertionError: False is not true
```

**What the agent cannot tell from the text.** Anything: which name, which file, why, or what to do.

**Proposed message** (`{name}` and `{file_name}` from the subtest):

```
{name} is listed in MACHINE_NAMES_DEFINED_OUTSIDE_THE_STATE_TABLES_MODULE as a string in scripts/design-to-main/{file_name}, and that file no longer has it.
If your change renamed it in {file_name}, give the entry the new name.
If the design no longer names it, remove the entry.
```

### 15. A listed exception is now a name the state tables define

**When an agent sees this.** An agent adds a state to the state tables module whose name is already on one of this suite's exception lists.

**What the agent is told today** (`scripts/design-to-main/tests/design-to-main-design-names-exist-in-state-tables-test.py:234` and `:235`; the assertions have no message):

```
AssertionError: Items in the first set but not the second:
'reviewing'
```

**What the agent cannot tell from the text.** Which list, why it matters, and what to do.

**Proposed messages**, for `:234` and `:235`:

```
on BACKTICKED_TOKENS_THAT_ARE_NOT_MACHINE_NAMES in this suite, and now a name the state tables module defines; a name of the state machine must be checked, not exempted.
Remove each from BACKTICKED_TOKENS_THAT_ARE_NOT_MACHINE_NAMES.
```

```
on MACHINE_NAMES_DEFINED_OUTSIDE_THE_STATE_TABLES_MODULE in this suite, and now a name the state tables module defines.
Remove each from MACHINE_NAMES_DEFINED_OUTSIDE_THE_STATE_TABLES_MODULE.
```

### 16. The design's tables and the code's tables disagree

**When an agent sees this.** An agent changes row 24's to-state in `TRANSITION_TABLE` in `scripts/design-to-main/design-to-main-state-tables.py`, and section 3.2 of the design still shows the old one.

**What the agent is told today** (`scripts/design-to-main/tests/design-to-main-design-rows-pair-with-state-tables-test.py:340`, `:344` and `:349`; the assertions have no message):

```
AssertionError: Lists differ: ["row 24: to-state 'test-design-writing', the To cell's first state 'implementation-writing'"] != []
```

**What the agent cannot tell from the text.** That the two copies are kept in step by hand, which copy is the source for what, and what to do.

**Proposed messages.** For `:340`, section 3.2 against `TRANSITION_TABLE`:

```
section 3.2 of {design} and TRANSITION_TABLE in scripts/design-to-main/design-to-main-state-tables.py disagree on the rows listed above. Both copies are edited by hand; section 3.2 is the source for what a transition is, and the code for what it does.
If your change edited one copy, make the same change in the other.
If your change edited neither, tell the user which rows disagree.
```

For `:344`, section 3.1 against `STATE_TABLE`, and `:349`, section 3.1's package column against `STATE_TABLE`'s `package_beyond_standard`, the same three lines with "section 3.1" and `STATE_TABLE` in place of "section 3.2" and `TRANSITION_TABLE`, and "on the states listed above" in place of "on the rows listed above".

### 17. A phrase the row matcher reads is gone from the design

**When an agent sees this.** An agent rewords section 3.2's From cells, and the phrase "any reviewing state but" no longer appears in any of them.

**What the agent is told today** (`scripts/design-to-main/tests/design-to-main-design-rows-pair-with-state-tables-test.py:361`, `:363` and `:365`; the message is the phrase alone). The audit did not list this message.

```
AssertionError: False is not true : any reviewing state but
```

**What the agent cannot tell from the text.** That the suite reads this phrase to understand the cells, why its absence matters, and what to do.

**Proposed message** (`{phrase}` is the phrase; `{cell}` is From, Trigger or To):

```
the suite reads the phrase "{phrase}" in section 3.2's {cell} cells, and no row of {design} uses it now, so the code that reads it can no longer be tested.
If your change reworded those cells, put the phrase back, or change the phrase constant in this suite to the new wording and rerun it.
```

### 18. The force-push guard is not registered once

**When an agent sees this.** An agent edits `.claude/settings.json` and drops, or duplicates, the entry that runs `scripts/force-push-with-open-pull-request-guard-hook.py`.

**What the agent is told today** (`scripts/force-push-with-open-pull-request-guard-hook-test.py:857`):

```
FAIL  the guard is wired exactly once as a PreToolUse Bash hook: []
```

**What the agent cannot tell from the text.** Where the guard is registered, why once, and what to do.

**Proposed text** (`{entries}` as today):

```
FAIL  the guard is wired exactly once as a PreToolUse Bash hook: found {entries}; .claude/settings.json must register scripts/force-push-with-open-pull-request-guard-hook.py once, as a PreToolUse hook on Bash, or the guard does not run, or runs twice.
If your change removed or duplicated that entry, restore exactly one; .claude/settings.json is under .claude/, so ask the user to approve that change.
```

### 19. The force-push guard's timeout is not above its budget

**When an agent sees this.** An agent raises `PROBE_BUDGET_SECONDS` in `scripts/force-push-with-open-pull-request-guard-hook.py` from 20 to 40, above the 30 seconds `.claude/settings.json` gives the hook.

**What the agent is told today** (`scripts/force-push-with-open-pull-request-guard-hook-test.py:860`):

```
FAIL  the registered timeout exceeds the guard's probe budget: timeout 30 vs budget 40.0
```

**What the agent cannot tell from the text.** Why the timeout must exceed the budget, and what to do.

**Proposed text** (`{timeout}` and `{budget}` as today):

```
FAIL  the registered timeout exceeds the guard's probe budget: timeout {timeout} vs budget {budget}; a hook that runs past its timeout lets the command through without a word, so the timeout .claude/settings.json registers must be above the guard's PROBE_BUDGET_SECONDS.
If your change raised PROBE_BUDGET_SECONDS in scripts/force-push-with-open-pull-request-guard-hook.py, lower it below the timeout, or ask the user to approve a higher timeout in .claude/settings.json, which is under .claude/.
```

## Messages left as they are

The audit found the other 18 messages of these suites complete, and the rereading agrees:

- `scripts/system-glossaries-listed-on-the-project-glossary-test.py`: git could not list the glossaries (`:154`), the checkout holds no project glossary (`:252`), no system glossary is tracked (`:262`), nothing was checked (`:270`), and a system glossary is not listed (`:275`).
- `scripts/pr-reviewer-instructions-copies-test.py`: the two copies of the review-scope rule differ (`:169`), and CLAUDE.md does not name the file and the suite (`:174`).
- `scripts/supervisor-file-names-defined-once-test.py`: the suffix constants are missing from the supervisor (`:233`), a script composes a file name itself (`:708`), a composing helper is missing (`:717`), and the names the suite hunts are a stale copy (`:750`).
- `scripts/nedschorus-glossary-alphabetical-order-test.py`: the glossary is out of order (`:136`), with its two fixture checks.
- `nc-systems/cold-read/tests/cold-read-record-names-test.py`: a cold-read program keeps its own copy of a name (`:369`), and a program binds a name without loading the module (`:401`).
- `scripts/design-to-main/tests/design-to-main-design-names-exist-in-state-tables-test.py`: a known mismatch is no longer one (`:217`), and a known mismatch is now a string in a module (`:222`).

## Code the new texts need

- Each `check()` detail and each assertion message above changes as shown. The nine `unittest` assertions that have no message today, at `scripts/design-to-main/tests/design-to-main-design-names-exist-in-state-tables-test.py:230`, `:234` and `:235`, and `scripts/design-to-main/tests/design-to-main-design-rows-pair-with-state-tables-test.py:340`, `:344` and `:349`, gain one. The phrase assertions at `:361`, `:363` and `:365` gain the message of message 17 in place of the bare phrase.
- Message 16 lists the disagreeing rows above its lines: the assertion's own comparison prints them, so the message only adds the lines after them.
- Message 1's second form needs the case at `scripts/file-name-collision-warning-hook-test.py:477` to append its two lines to git's error.

## Tests

Each suite tests its own rule against the repository, so a failure message prints only when the rule breaks. Several suites already build broken fixtures to show a case can fail: `scripts/system-glossaries-listed-on-the-project-glossary-test.py`, `scripts/supervisor-file-names-defined-once-test.py`, `scripts/file-name-collision-warning-hook-test.py` and the two design-to-main suites. The pull request adds, in each suite, a fixture case per changed message that breaks the rule, captures the message, and checks that its lines are the approved lines. For the suites with no fixtures today, `scripts/walk-file-endings-match-the-skill-test.py`, `nc-systems/cold-read/tests/cold-read-record-names-test.py` and the force-push suite's two wiring cases, the message text moves into a function the case and its new fixture both call.
