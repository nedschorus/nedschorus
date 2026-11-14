---
issue: "[Shell command forms that pull request reviewers constructed and the Bash guards' shared shell reader misreads](https://github.com/nedschorus/nedschorus/issues/1683)"
---

# Shell command forms that pull request reviewers constructed and the Bash guards' shared shell reader misreads

The Bash guards, the PreToolUse hooks in `.claude/settings.json` that check a Bash command before it runs, all read the command through one shared shell reader, `nc-systems/general-tools/shell-command-tree-sitter-bash-reader-common.py`. Reviewers of pull requests that change that reader keep constructing commands it reads differently from bash, such as a force push the force-push guard, `.claude/guard-hooks/force-push-with-open-pull-request-guard-hook.py`, lets through. No agent has run any of these commands. This GHI is the one place those constructed forms are collected, so that each does not become its own follow-up pull request.

## How this GHI is used

The user approved this rule on 2026-10-19, answering "A" to item 17 of agent-seat agent-instructions-editor's approval-walk; the approved text had a cold-read-fast-read, whose cold-read-record is the directory `nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/item-17-shell-forms-one-ghi-2026-10-19-4`:

"Today merge-lane-2 sends each such finding to the pull request's author, who opens a follow-up pull request. Instead, merge-lane-2 files one GitHub issue for the shell reader with the ghi-write skill, and from then on adds each such finding to that issue's GHI-MD with the edit-GHI operation, and does not send the finding to the author. A command form moves from that issue to a pull request only when a real command an agent ran, recorded in a transcript, uses that form."

Write only constructed forms here. This repository is public, and recorded commands and transcripts can hold secrets, so no text from a recorded command, a transcript, or the corpus of `nc-systems/general-tools/bash-guards-verdict-changes-between-git-refs-on-recorded-commands-check.py` (the store of recorded commands that program replays through every Bash guard) goes into this file. To show that a recorded command uses a form, cite the transcript's path in the log-store, never its text.

## How this differs from GHI 1196

GHI [Replace the hand-written parsers in the project's hooks and scripts with real parsers](https://github.com/nedschorus/nedschorus/issues/1196) is the plan that moved the Bash guards onto this shared reader, and it stays the home of that plan. Its section "Provisional additions" has so far collected reader defects as a list to fix, and each defect there became its own pull request: PRs [1544](https://github.com/nedschorus/nedschorus/pull/1544), [1555](https://github.com/nedschorus/nedschorus/pull/1555), [1561](https://github.com/nedschorus/nedschorus/pull/1561), [1567](https://github.com/nedschorus/nedschorus/pull/1567) and [1574](https://github.com/nedschorus/nedschorus/pull/1574). This GHI is the opposite: it holds constructed forms that are not fixed, and fixes none of them until a recorded command needs it. The two GHIs are not merged.

## Why the forms can wait

- Every force push in the first table is refused by the git pre-push hook, `scripts/git-client-side-hooks/pre-push`, added by PR [pre-push: refuse a forced rewrite or a deletion of an open pull request's head branch](https://github.com/nedschorus/nedschorus/pull/1557). That hook reads the ref update git is about to send, so how the command is spelled does not matter. The Bash force-push guard is now an early warning.
- No recorded command has any of these shapes: each pull request's review replayed every recorded Bash command through every Bash guard, at the pull request's base and head, and no verdict changed (for example 215,561 command and directory pairs in merge-lane-2's review of PR 1574).
- No such net exists for the other Bash guards, such as the synthetic-keystroke guard or the GHI redirect guard; a form that fools one of them can wait only because no recorded command has its shape.
- Each fix of one shape so far has risked opening a new one: PRs [1536](https://github.com/nedschorus/nedschorus/pull/1536), [1544](https://github.com/nedschorus/nedschorus/pull/1544) and [1555](https://github.com/nedschorus/nedschorus/pull/1555) each opened a new way past the force-push guard while closing others.

## Notation

`<LF>` is a newline, `\<LF>` is a backslash followed by a newline (a line continuation), and `<TAB>` is a tab. `b` is a branch with an open pull request. `zzp`, `zzq` and `zzs` are made-up command names, so a form can be run safely.

## Forms whose force push the force-push guard lets through

Checked on origin/main at commit 21af2b5c on 2026-10-19, and again, with the same results, at commit e5485184 the same day: each command was read with the shared reader, given to the force-push guard's `analyze_command_text` with a stub that reports an open pull request for `b`, and run with `bash -c` (bash 5.3) in a scratch directory where `git` was a stub that records its arguments. In every row bash runs `git push --force origin b`, and the guard's right verdict is deny. The guard returns no decision, which lets the command run. Every other Bash guard reads the same misread words, so each would miss a command it checks in the same position; only the force-push guard was run.

| Form | What the reader reads instead | Found in |
|---|---|---|
| `` `2>/dev/null git push --force origin b` `` | a command named `2` | [merge-lane-2's review of PR 1555](https://github.com/nedschorus/nedschorus/pull/1555#pullrequestreview-5550522069), shape (1) |
| `: \>&2>/dev/null git push --force origin b` | `:` with word `>`, then a command named `2` | [merge-lane-2's review of PR 1555](https://github.com/nedschorus/nedschorus/pull/1555#pullrequestreview-5550522069), shape (2) |
| `env -u <&-2>/dev/null UNUSED git push --force origin b` | `env -u 2 UNUSED git …`, so `env` removes the variable `2` and runs the program `UNUSED` | [merge-lane-2's review of PR 1555](https://github.com/nedschorus/nedschorus/pull/1555#pullrequestreview-5550522069), shape (3) |
| `# a comment \<LF>2>/dev/null git push --force origin b` (a comment ending in a backslash) | a command named `2` | [merge-lane-2's review of PR 1555](https://github.com/nedschorus/nedschorus/pull/1555#pullrequestreview-5550522069), shape (4) |
| `0<>/dev/null git push --force origin b` | no command at all | [mac-claude's inline finding on PR 1561](https://github.com/nedschorus/nedschorus/pull/1561#discussion_r4298772082) |
| `` `0<f git push --force origin b` ``, when a file `f` exists | a command named `0` | [mac-claude's review of PR 1561](https://github.com/nedschorus/nedschorus/pull/1561#pullrequestreview-5553003699), section (e) |
| `{fd}>f git push --force origin b` | a command named `fd}` | [mac-claude's review of PR 1561](https://github.com/nedschorus/nedschorus/pull/1561#pullrequestreview-5553003699), section (e) |
| `zzp <\<LF><'EOF'<LF>x\<LF>EOF<LF>git push --force origin b` (a continuation splits `<<`) | only `zzp`; the here-document never ends, so the push is lost | [mac-claude's inline finding on PR 1567](https://github.com/nedschorus/nedschorus/pull/1567#discussion_r4299751484); left unfixed on purpose by [merge-lane-2's round-2 review of PR 1574](https://github.com/nedschorus/nedschorus/pull/1574#pullrequestreview-5555417966), which asked for it to be listed in the section headed "Known gaps" of that pull request's description |
| `zzp <<\<LF>-EOF<LF>x<LF>EOF<LF>git push --force origin b` (a continuation splits `<<-`; bash joins `<<-EOF`, a here-document with delimiter `EOF`, and the same holds when the body and delimiter lines start with `<TAB>`) | only `zzp`: a here-document with delimiter `-EOF`, which never ends, so the push is lost | [mac-claude's review of PR 1567](https://github.com/nedschorus/nedschorus/pull/1567#pullrequestreview-5554172978), section (a); [PR 1574](https://github.com/nedschorus/nedschorus/pull/1574)'s first round fixed it, and the round-2 simplification removed that fix; found again, with a `<TAB>`-indented body, by [mac-claude's review of PR 1676](https://github.com/nedschorus/nedschorus/pull/1676#pullrequestreview-5578861061), section "Defects main already has" |
| `zzp <<\<LF><EOF<LF>git push --force origin b<LF>EOF` (a continuation splits `<<<`; bash joins `<<<EOF`, a here-string, so the next lines are commands) | only `zzp`: a here-document with delimiter `<EOF`, which never ends, so the push is lost | [mac-claude's review of PR 1676](https://github.com/nedschorus/nedschorus/pull/1676#pullrequestreview-5578861061), section "Defects main already has", as `zzp <<\<LF><EOF<LF>zzx<LF>EOF<LF>zzr`, where bash runs `zzx`, `EOF` and `zzr` and the reader reads none of them |
| `zzp <<$'E F'<LF>x<LF>E F<LF>git push --force origin b` | only `zzp` | [merge-lane-2's round-1 review of PR 1574](https://github.com/nedschorus/nedschorus/pull/1574#pullrequestreview-5555072618), follow-up 3 |

## Forms with many here-documents

A Bash guard runs under a 30-second timeout, and a guard that times out lets the command run with no report. The reader takes out at most 256 here-documents, its constant `MAX_HEREDOCS_TAKEN_OUT`; after the 256th, it no longer joins a continued line, so one word written across a `\<LF>` is read as two words in two commands.

Checked on origin/main at 5e508ba8 on 2026-11-11, on ned-box under a load average near 20, by calling `simple_commands` of the shared reader and by giving the force-push guard hook the command as its stdin hook input, from an empty scratch directory.

| Form | What happens | Found in |
|---|---|---|
| 2,000 repetitions of `zzp <<EOF<LF>x<LF>EOF<LF>zzq a\<LF>b<LF>` (a here-document, then a continued line) | reading took 44 s on ned-box on 2026-10-19, past the timeout; at 5e508ba8 the reader alone takes 7.8 to 8.9 s and the force-push guard hook 6.9 to 7.7 s end to end, both under the timeout. It still reads 5,744 commands where 4,000 are written: 2,000 `zzp`, 256 `zzq ab`, then 1,744 `zzq a` and 1,744 `b` | [merge-lane-2's approving review of PR 1574](https://github.com/nedschorus/nedschorus/pull/1574#pullrequestreview-5556505000), follow-up 2 |
| 257 repetitions of `zzp <<EOF<LF>x<LF>EOF<LF>`, then `git push --fo\<LF>rce origin b` | bash runs `git push --force origin b`; the reader's last two commands are `['git', 'push', '--fo']` and `['rce', 'origin', 'b']`, so the Bash force-push guard would not see `--force` (the guard itself was not run). The git pre-push hook still refuses the push. With 256 repetitions instead of 257, the reader reads `git push --force origin b` | agent-seat reboot-test, while checking the row above at merge-lane-2's request on 2026-11-11 |

## Forms whose words differ from bash but whose verdict does not change

In each row, for the form as written, every Bash guard decides as it would on bash's reading, so the right verdict and the guard's verdict agree; only the words the reader passes on differ.

| Form | Reader | bash | Found in |
|---|---|---|---|
| `zzq a\<TAB>2>f` | `zzq` with word `a<TAB>`, the `2` taken as a descriptor | `zzq` with word `a<TAB>2` | [merge-lane-2's review of PR 1530](https://github.com/nedschorus/nedschorus/pull/1530#pullrequestreview-5543478821), follow-up 2 |
| `3<>f git push --force origin b` | the operator `3<` | the operator `<>` on descriptor 3; the guard still denies | [mac-claude's review of PR 1561](https://github.com/nedschorus/nedschorus/pull/1561#pullrequestreview-5553003699), section (e) |
| `\ 0<f zzp a` | a command named `0` | a command named ` 0` (a space, then 0) | [mac-claude's review of PR 1561](https://github.com/nedschorus/nedschorus/pull/1561#pullrequestreview-5553003699), section (e) |
| `0<(true) zzp a` | a command named `0` with word `<(true)` | a command named `0/dev/fd/63` | [mac-claude's review of PR 1561](https://github.com/nedschorus/nedschorus/pull/1561#pullrequestreview-5553003699), section (e) |
| ``zzp `zzq 'a\<LF>b'` `` (a continuation inside single quotes inside backticks) | `zzq` with word `a\<LF>b` | `zzq` with word `ab` | [mac-claude's review of PR 1567](https://github.com/nedschorus/nedschorus/pull/1567#pullrequestreview-5554172978), section (a) |
| `zzs <<EOF<LF>$(zzq 'a\<LF>b')<LF>EOF` (the same inside a here-document body's `$( )`) | `zzq` with word `a\<LF>b` | `zzq` with word `ab` | [mac-claude's review of PR 1567](https://github.com/nedschorus/nedschorus/pull/1567#pullrequestreview-5554172978), section (a) |
| `zzq \ <<E<LF>zzx body<LF>E` (an escaped blank before a here-document) | four commands: `zzq`, `E`, `zzx body` and `E`, read on origin/main at 5e508ba8 on 2026-11-11; the here-document's body and delimiter are read as commands, and the word ` ` is dropped | runs `zzq` with the word ` ` (a space) and the here-document `zzx body` as its input, checked with bash 5.3.9 and a stub `zzq` that prints its words and input | agent-seat reboot-test's task list, task 229, checked again at merge-lane-2's request on 2026-11-11 |

## Forms misread at an open pull request's head and read right on main

These forms are misread only by the reader as a pull request that is still open changes it; origin/main at e5485184 reads them as bash reads them. Checked on 2026-10-19 as the first table was, at the head of [PR 1676](https://github.com/nedschorus/nedschorus/pull/1676), commit 5b113a1d. When that pull request merges unchanged, a row moves to the table its effect fits; when it merges with the form read right, or closes, the row is deleted.

| Form | bash | Reader at 5b113a1d | Found in |
|---|---|---|---|
| `cat <\<LF><<EOF<LF>git push --force origin b<LF>EOF` (a continuation splits `<<<`) | joins `<<<EOF`, a here-string, then runs `git push --force origin b` and `EOF` as commands | only `cat`, with a here-document that swallows the push; the force-push guard returns no decision where its right verdict is deny, and main's reader leads it to deny | [mac-claude's inline finding on PR 1676](https://github.com/nedschorus/nedschorus/pull/1676#discussion_r4319808487); the same shape with `tmux kill-server` in place of the push, which the Codex review reports gets past the tmux kill-server guard (not checked here), is the P1 finding of the Codex review of PR 1676, `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers/cx/pr1676-42b411dc/codex-code-review-report.md` |
| `case a in a) :;& esac; echo "$(case b in b) :;& esac)"; echo ';& esac'` | the last `echo` gets the word `;& esac` | the last `echo` gets the word `;; esac`; no Bash guard's verdict changes, since only a quoted argument differs | the P2 finding of the Codex review of PR 1676, `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers/cx/pr1676-42b411dc/codex-code-review-report.md` |

## Provisional additions (not yet vetted by the user)

These forms concern Bash guards other than the force-push guard. Checked on origin/main at 9b1ff732 on 2026-11-02: each command was given, as one string, with the checkout's root as the working directory and no stub, to the guard's own function, `refusal_for` of the tmux kill guard `.claude/guard-hooks/claude-code-tmux-kill-server-and-kill-session-missing-server-selection-refusal-hook.py`, `refusal_for_command` of the codex exec guard `.claude/guard-hooks/hand-typed-codex-exec-command-refusal-hook.py`, or `ghi_md_replaced_by_command` of the GHI-MD soft-block `.claude/guard-hooks/ghi-md-whole-file-replacement-soft-block.py`, run from a checkout where `docs/issues/46-ghi-guide-agent-design.md` exists; what bash, cp, mv and env do was checked by running the same shapes on harmless commands and scratch files (bash 5.3.9). The bash and ssh rows are misread by the shared reader's `shell_runner_options_read` and `ssh_remote_command`; of the GHI-MD soft-block rows, only the first is the shared reader's (`simple_commands` does not hand on a redirection that is not part of a simple command), and the rest are the soft-block's own reading of `cp`, `mv` and `env`, so a rewrite of the shared reader leaves them as they are: the agent-seat that next changes the soft-block's reading of those programs runs those rows against it and removes each row it then handles.

Forms a guard lets through, where its right verdict is to refuse:

| Form | What bash does | What the guard does | Found in |
|---|---|---|---|
| `bash +c 'tmux kill-server'`, and `bash +c 'codex exec task'` | runs the string: `+c`, like `-c`, makes the first operand the command string | the reader treats `+c` as turning `c` off, so it reads no command string; the tmux kill guard and the codex exec guard each let their command through | the Codex review of fix-round 2 of PR 1815, `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers/cx/pr1815-b46fcec0/codex-code-review-report.md`, folded into [merge-lane-2's approving review of PR 1815](https://github.com/nedschorus/nedschorus/pull/1815#pullrequestreview-5604743767), item 1 |
| `bash +s arg <<'EOF'<LF>codex exec task<LF>EOF` | runs the here-document's lines as commands | the reader treats `+s` as turning `s` off, so `arg` is read as a script file and stdin as unread; the codex exec guard lets it through, where `bash -s arg` with the same here-document is refused | the same Codex review of PR 1815, item 1 |
| `bash + -c 'tmux kill-server'`, and `bash + -c 'codex exec task'` | skips the lone `+` and runs the string | the reader stops reading options at the lone `+` and reads no command string; both guards let the command through | the same Codex review of PR 1815, item 2 |
| `{ cat /tmp/new.md; } > docs/issues/46-ghi-guide-agent-design.md`; also `( cat /tmp/new.md ) > …` and the bare `> docs/issues/46-ghi-guide-agent-design.md` | truncates and writes over the GHI-MD | `simple_commands` returns the inner `cat` without the group's redirection, and nothing at all for a redirection with no command; the GHI-MD soft-block lets each through | the Codex review of PR 2196, `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers/cx/pr2196-4df140d9/codex-code-review-report.md`, folded into [merge-lane-2's approving review of PR 2196](https://github.com/nedschorus/nedschorus/pull/2196#pullrequestreview-5721594571), first P2 |
| `cp -a /tmp/issues docs/`, when `/tmp/issues` holds a file `46-ghi-guide-agent-design.md` (`cp -r` too) | merges into `docs/issues/` and writes over the GHI-MD | the soft-block checks only the destination directory `docs/issues`, which is not a GHI-MD, and lets it through | the same Codex review of PR 2196, second P2 |
| `env -C docs cp /tmp/new.md issues/46-ghi-guide-agent-design.md`, run from the checkout root | `cp` runs in `docs/` and writes over the GHI-MD | the soft-block skips the `env` wrapper without applying `-C`, resolves the target against the checkout root, finds no file there, and lets it through | the same Codex review of PR 2196, third P2 |

Forms a guard refuses, where its right verdict is to let the command run:

| Form | What the program does | What the guard does | Found in |
|---|---|---|---|
| `ssh -G ned-box 'echo ok' <<'EOF'<LF>codex exec task<LF>EOF` (also `ssh -V`) | prints ssh's configuration (or its version), connects to nothing and runs nothing | `ssh_remote_command` returns None for `-G` and `-V`, the same answer it gives for an ssh with no remote command, and the codex exec guard reads that as a remote shell running the here-document; it refuses | the same Codex review of PR 1815, item 3 |
| `cp -n /tmp/new.md docs/issues/46-ghi-guide-agent-design.md`, and `mv --no-clobber /tmp/new.md docs/issues/46-ghi-guide-agent-design.md` | leaves the existing GHI-MD as it is | the soft-block ignores the no-clobber option, counts the GHI-MD as replaced, and refuses until a reason is written into its marker file | the same Codex review of PR 2196, fourth P2 |

## Forms found and since fixed

These constructed forms, from the reviews of the pull requests linked above and of PRs [1523](https://github.com/nedschorus/nedschorus/pull/1523), [1525](https://github.com/nedschorus/nedschorus/pull/1525), [1530](https://github.com/nedschorus/nedschorus/pull/1530) and [1536](https://github.com/nedschorus/nedschorus/pull/1536), read as bash reads them on origin/main at 21af2b5c, so they are not listed above: escaped blanks next to redirections (`zzp \  >f x`, `zzp a>f \  b`, `zzq \ ;`), escaped tabs (`zzq >f\<TAB>;`, `zzq a\<TAB>;`), `zzq <&- ''\ ;`, `zzq a\<LF>#c`, `zzq a\<LF>2>f`, `git push 2>&- --force origin b`, `env -u 2>&1 0x1</dev/null git push --force origin b`, `env 3>&- 0\<LF></dev/null git push --force origin b`, `zzp ''\  -3>&-`, `env -u \ 0<LF></dev/null git push --force origin b`, `bash 1>&2<LF></dev/null`, `git push -f\<LF>4>/dev/null origin b`, `git push --repo <\<LF>(true) --force origin b`, `0</dev/null git push --force origin b`, a case terminator split by a continuation, a delimiter joined by a continuation inside `$( )`, `: \<<\<LF><'EOF'`, and `case a i\<LF>n`. On origin/main at 5e508ba8 on 2026-11-11, `cat << \<LF>  EOF<LF>x<LF>EOF<LF>zzr a` (the delimiter on an indented continued line), from the Codex finding of [merge-lane-2's approving review of PR 1574](https://github.com/nedschorus/nedschorus/pull/1574#pullrequestreview-5556505000), reads as bash reads it: `cat` with a here-document whose body is `x`, then `zzr` with word `a`; it had read as `cat EOF`, losing the next command.

## Next action

None until a trigger: merge-lane-2 adds each new constructed form a review finds to the tables above with edit-GHI, and a form goes to a pull request when a recorded command an agent ran uses it, as "How this GHI is used" says. When the agent-seat that builds GHI 1196's shell work replaces or rewrites the reader, it runs every form here against the new reader and removes each row whose form then reads as bash reads it.

## Deferred-decisions

1. Who notices that a recorded command uses a form listed here, and which agent-seat then opens the pull request, is not decided; the approved rule names the trigger, not who watches for it.
2. When the rows of "Forms with many here-documents" are resolved, since their forms are now read within the timeout but differently from bash after the 256th here-document: to be set when the reader is next rewritten.
