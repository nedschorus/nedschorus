---
issue: "[The Bash guards' shared shell reader does not read inside a double-quoted command substitution](https://github.com/nedschorus/nedschorus/issues/710)"
---

# The Bash guards' shared shell reader does not read inside a double-quoted command substitution

Agent-filed by merge-lane-2 on 2026-09-24, from a reproduced review finding. Its outcome is first; the reproduction, the cause and the next action follow it.

## Outcome

PR [The Bash guards' shell reader reads a command substitution inside double quotes as commands](https://github.com/nedschorus/nedschorus/pull/886) builds the next action below. It merged on 2026-10-02 as `36c270f1`, after four review rounds. The shared reader in `scripts/synthetic-keystroke-guard-hook.py` now reads a `$( … )` inside double quotes as commands, and reads the `$( … )` substitutions in a heredoc's body, which bash also runs. All three guards that use the reader take the change, and so does the leading-dash guard, `scripts/search-file-argument-read-as-option-guard-hook.py`, which main gained while the pull request was in review; its test, `scripts/search-file-argument-read-as-option-guard-hook-test.py`, gained cases for the change.

As the next action asks, both reproductions are test cases in each guard's own test, written with that guard's own command: `.claude/hooks/ghi-issue-write-redirect-test.py`, `scripts/synthetic-keystroke-guard-hook-test.py` and `scripts/force-push-with-open-pull-request-guard-hook-test.py`.

The pull request also refuses some commands that main let through, in each of which bash runs a guarded command. The user ruled on 2026-10-02 that those refusals stay. His "Y for both" covers a `$'…\'…'` string before a guarded command, and a guarded command in a substitution inside a heredoc's body. His "Y" covers three more found in round 3: a partly quoted or backslashed heredoc delimiter followed by a guarded command; a `"$( … )"` whose heredoc body holds a `"`, followed by a guarded command; and a backticked guarded command after a `$'…\'…'` string. In the same review, he adopted a stopping rule for reviews of the guards' reader: a finding blocks a merge only when replaying the real commands agents typed changes a guard's verdict, or when evidence shows agents commonly type the form; a form found only by construction or by a random generator is a non-blocking note. Replayed at the merged head, 103,032 real (command, working directory) pairs from both machines changed no verdict.

Left as notes, not built: at about 500 nested unquoted heredocs inside body substitutions, the guards raise RecursionError and let the command through (in `scripts/synthetic-keystroke-guard-hook.py`, the reader's limit on nesting depth, `MAX_SUBSTITUTION_NESTING`, is not checked on the heredoc path). It is a constructed form, so under the stopping rule it does not block; the seat fleet-restart-at-login holds it as a follow-up.

## Reproduction

On main at `2e294ed9`, feed each command below to a guard as a PreToolUse payload: `{"tool_name": "Bash", "tool_input": {"command": <command>}, "cwd": "."}` on the guard's stdin. Run it from a checkout's root, with `CLAUDE_PROJECT_DIR=.`.

**A false refusal.** This legitimate commit, in Claude Code's default heredoc form, is denied by `.claude/hooks/ghi-issue-write-redirect.py` with "Do not comment on this project's issues.":

    git commit -m "$(cat <<'EOF'
    Drop the interim path

    The skill said: "plain `gh issue comment` is the interim path." Gone now.
    EOF
    )"

`scripts/synthetic-keystroke-guard-hook.py` does the same to a message of the same shape, with "Blocked: tmux target '$SEAT' contains an unexpanded variable":

    git commit -m "$(cat <<'EOF'
    Document the rule

    The brief says: "never `tmux send-keys -t $SEAT Enter` into a seat." Stated now.
    EOF
    )"

The same two messages without the pair of `"` around the backticked command are allowed by both guards.

**A missed refusal.** In `.claude/hooks/ghi-issue-write-redirect.py`, the wrapped form passes and the bare form is refused:

| command | result |
|---|---|
| `URL="$(gh issue create -t A -b B)"` | allowed |
| `URL=$(gh issue create -t A -b B)` | denied |
| `echo "$(gh issue comment 46 -b x)"` | allowed |
| `echo $(gh issue comment 46 -b x)` | denied |

All eight results were reproduced by merge-lane-2 on 2026-09-24.

## Why it happens

Three guards share one reader, `split_out_heredocs` and `tokenize_simple_commands` in `scripts/synthetic-keystroke-guard-hook.py`:
- `scripts/synthetic-keystroke-guard-hook.py` itself;
- `scripts/force-push-with-open-pull-request-guard-hook.py`;
- `.claude/hooks/ghi-issue-write-redirect.py`, since PR [Hand-typed gh issue comments, creates and body edits are refused](https://github.com/nedschorus/nedschorus/pull/708).

The reader treats everything inside `"..."` as one quoted data word, including a `$(...)` command substitution, whose contents the shell runs as commands. Two consequences follow:
1. A command inside `"$(...)"` is never read as a command, so the guards miss it: the missed refusal above.
2. A heredoc opened inside `"$(...)"` is never split out. Its `<<` sits inside what the reader takes for a string, so the heredoc body stays in the text the tokenizer reads. The tokenizer then ends the outer `"` at the first `"` in the message. Any backtick that follows falls outside every quote, and the command inside it comes out as a simple command of its own: the false refusal above.

## What it costs

- **A false refusal** blocks a legitimate `git commit` or `gh pr create`. The refusal text names an unrelated rule, and nothing in it says the match was inside the agent's own message. The agent recovers by passing the message from a file, `git commit -F <file>`. How often: none of the 8 commit messages on main and none of the 5 pull-request bodies that mention a `gh issue` write verb would have been refused, measured by the reviewer on 2026-09-24. The likeliest trigger is a follow-up to the /ghi-write skill whose messages quote the skill's old interim-path sentence.
- **A missed refusal** lets a write through exactly as it went before the guard existed. No agent is known to have wrapped a guarded command this way. Capturing a created issue's URL with `URL="$(gh issue create ...)"` is an ordinary shell habit, though.

The force-push guard was not probed for either symptom here. It reads the same words, so it inherits the same reading.

## Next action

In `tokenize_simple_commands` and `split_out_heredocs`, treat a `$(` inside double quotes as opening a nested command list, read it as commands, and resume the double-quoted string at its matching `)`. Add both reproductions above as cases in each guard's test: `scripts/synthetic-keystroke-guard-hook-test.py`, `.claude/hooks/ghi-issue-write-redirect-test.py`, and `scripts/force-push-with-open-pull-request-guard-hook-test.py`.

## Where it came from

The false refusal is `mac-claude`'s non-blocking finding on PR [Hand-typed gh issue comments, creates and body edits are refused](https://github.com/nedschorus/nedschorus/pull/708), [inline comment 4096774424](https://github.com/nedschorus/nedschorus/pull/708#discussion_r4096774424). The missed refusal is question 3 of merge-lane-2's review of the same PR, [review 5308447683](https://github.com/nedschorus/nedschorus/pull/708#pullrequestreview-5308447683). The keystroke guard's instance predates PR [Hand-typed gh issue comments, creates and body edits are refused](https://github.com/nedschorus/nedschorus/pull/708); that pull request added a third consumer of the reader.
