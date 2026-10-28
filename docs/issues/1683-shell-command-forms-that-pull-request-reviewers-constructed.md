---
issue: "[Shell command forms that pull request reviewers constructed and the Bash guards' shared shell reader misreads](https://github.com/nedschorus/nedschorus/issues/1683)"
---

# Shell command forms that pull request reviewers constructed and the Bash guards' shared shell reader misreads

The Bash guards, the PreToolUse hooks in `.claude/settings.json` that check a Bash command before it runs, all read the command through one shared shell reader, `nc-systems/general-tools/shell-command-tree-sitter-bash-reader-common.py`. Reviewers of pull requests that change that reader keep constructing commands it reads differently from bash, such as a force push the force-push guard, `scripts/force-push-with-open-pull-request-guard-hook.py`, lets through. No agent has run any of these commands. This GHI is the one place those constructed forms are collected, so that each does not become its own follow-up pull request.

## How this GHI is used

The user approved this rule on 2026-10-19, answering "A" to item 17 of agent-seat agent-instructions-editor's approval-walk; the approved text had a cold-read-fast-read, whose cold-read-record is the directory `nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/item-17-shell-forms-one-ghi-2026-10-19-4`:

"Today merge-lane-2 sends each such finding to the pull request's author, who opens a follow-up pull request. Instead, merge-lane-2 files one GitHub issue for the shell reader with the ghi-write skill, and from then on adds each such finding to that issue's GHI-MD with the edit-GHI operation, and does not send the finding to the author. A command form moves from that issue to a pull request only when a real command an agent ran, recorded in a transcript, uses that form."

Write only constructed forms here. This repository is public, and recorded commands and transcripts can hold secrets, so no text from a recorded command, a transcript, or the Bash guards' replay corpus (the store of recorded commands that `nc-systems/general-tools/bash-guards-verdict-changes-between-two-git-refs-on-transcript-recorded-commands-check.py` replays through every Bash guard) goes into this file. To show that a recorded command uses a form, cite the transcript's path in the log-store, never its text.

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
| `cat << \<LF>  EOF<LF>x<LF>EOF<LF>git push --force origin b` (the delimiter on an indented continued line) | `cat EOF`; the push is lost | [merge-lane-2's approving review of PR 1574](https://github.com/nedschorus/nedschorus/pull/1574#pullrequestreview-5556505000), the Codex finding |

## Forms that time a guard out

A Bash guard runs under a 30-second timeout, and a guard that times out lets the command run with no report.

| Form | What happens | Found in |
|---|---|---|
| 2,000 repetitions of `zzp <<EOF<LF>x<LF>EOF<LF>zzq a\<LF>b<LF>` (a here-document, then a continued line) | reading takes 44 s on ned-box on 2026-10-19, past the timeout, and reads 5,744 commands where 4,000 are written | [merge-lane-2's approving review of PR 1574](https://github.com/nedschorus/nedschorus/pull/1574#pullrequestreview-5556505000), follow-up 2 |

## Forms whose words differ from bash but whose verdict does not change

In each row, every Bash guard decides as it would on bash's reading, so the right verdict and the guard's verdict agree; only the words the reader passes on differ.

| Form | Reader | bash | Found in |
|---|---|---|---|
| `zzq a\<TAB>2>f` | `zzq` with word `a<TAB>`, the `2` taken as a descriptor | `zzq` with word `a<TAB>2` | [merge-lane-2's review of PR 1530](https://github.com/nedschorus/nedschorus/pull/1530#pullrequestreview-5543478821), follow-up 2 |
| `3<>f git push --force origin b` | the operator `3<` | the operator `<>` on descriptor 3; the guard still denies | [mac-claude's review of PR 1561](https://github.com/nedschorus/nedschorus/pull/1561#pullrequestreview-5553003699), section (e) |
| `\ 0<f zzp a` | a command named `0` | a command named ` 0` (a space, then 0) | [mac-claude's review of PR 1561](https://github.com/nedschorus/nedschorus/pull/1561#pullrequestreview-5553003699), section (e) |
| `0<(true) zzp a` | a command named `0` with word `<(true)` | a command named `0/dev/fd/63` | [mac-claude's review of PR 1561](https://github.com/nedschorus/nedschorus/pull/1561#pullrequestreview-5553003699), section (e) |
| ``zzp `zzq 'a\<LF>b'` `` (a continuation inside single quotes inside backticks) | `zzq` with word `a\<LF>b` | `zzq` with word `ab` | [mac-claude's review of PR 1567](https://github.com/nedschorus/nedschorus/pull/1567#pullrequestreview-5554172978), section (a) |
| `zzs <<EOF<LF>$(zzq 'a\<LF>b')<LF>EOF` (the same inside a here-document body's `$( )`) | `zzq` with word `a\<LF>b` | `zzq` with word `ab` | [mac-claude's review of PR 1567](https://github.com/nedschorus/nedschorus/pull/1567#pullrequestreview-5554172978), section (a) |

## Forms misread at an open pull request's head and read right on main

These forms are misread only by the reader as a pull request that is still open changes it; origin/main at e5485184 reads them as bash reads them. Checked on 2026-10-19 as the first table was, at the head of [PR 1676](https://github.com/nedschorus/nedschorus/pull/1676), commit 5b113a1d. When that pull request merges unchanged, a row moves to the table its effect fits; when it merges with the form read right, or closes, the row is deleted.

| Form | bash | Reader at 5b113a1d | Found in |
|---|---|---|---|
| `cat <\<LF><<EOF<LF>git push --force origin b<LF>EOF` (a continuation splits `<<<`) | joins `<<<EOF`, a here-string, then runs `git push --force origin b` and `EOF` as commands | only `cat`, with a here-document that swallows the push; the force-push guard returns no decision where its right verdict is deny, and main's reader leads it to deny | [mac-claude's inline finding on PR 1676](https://github.com/nedschorus/nedschorus/pull/1676#discussion_r4319808487); the same shape with `tmux kill-server` in place of the push, which the Codex review reports gets past the tmux kill-server guard (not checked here), is the P1 finding of the Codex review of PR 1676, `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers/cx/pr1676-42b411dc/codex-code-review-report.md` |
| `case a in a) :;& esac; echo "$(case b in b) :;& esac)"; echo ';& esac'` | the last `echo` gets the word `;& esac` | the last `echo` gets the word `;; esac`; no Bash guard's verdict changes, since only a quoted argument differs | the P2 finding of the Codex review of PR 1676, `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers/cx/pr1676-42b411dc/codex-code-review-report.md` |

## Forms found and since fixed

These constructed forms, from the reviews of the pull requests linked above and of PRs [1523](https://github.com/nedschorus/nedschorus/pull/1523), [1525](https://github.com/nedschorus/nedschorus/pull/1525), [1530](https://github.com/nedschorus/nedschorus/pull/1530) and [1536](https://github.com/nedschorus/nedschorus/pull/1536), read as bash reads them on origin/main at 21af2b5c, so they are not listed above: escaped blanks next to redirections (`zzp \  >f x`, `zzp a>f \  b`, `zzq \ ;`), escaped tabs (`zzq >f\<TAB>;`, `zzq a\<TAB>;`), `zzq <&- ''\ ;`, `zzq a\<LF>#c`, `zzq a\<LF>2>f`, `git push 2>&- --force origin b`, `env -u 2>&1 0x1</dev/null git push --force origin b`, `env 3>&- 0\<LF></dev/null git push --force origin b`, `zzp ''\  -3>&-`, `env -u \ 0<LF></dev/null git push --force origin b`, `bash 1>&2<LF></dev/null`, `git push -f\<LF>4>/dev/null origin b`, `git push --repo <\<LF>(true) --force origin b`, `0</dev/null git push --force origin b`, a case terminator split by a continuation, a delimiter joined by a continuation inside `$( )`, `: \<<\<LF><'EOF'`, and `case a i\<LF>n`.

## Next action

None until a trigger: merge-lane-2 adds each new constructed form a review finds to the tables above with edit-GHI, and a form goes to a pull request when a recorded command an agent ran uses it, as "How this GHI is used" says. When the agent-seat that builds GHI 1196's shell work replaces or rewrites the reader, it runs every form here against the new reader and removes each row whose form then reads as bash reads it.

## Deferred-decisions

1. Who notices that a recorded command uses a form listed here, and which agent-seat then opens the pull request, is not decided; the approved rule names the trigger, not who watches for it.
2. When the timing row is resolved, since its form is read as bash reads it but too slowly: to be set when the reader is next rewritten.
