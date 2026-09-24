---
issue: "[The Bash guards' shared shell reader does not read inside a double-quoted command substitution](https://github.com/nedschorus/nedschorus/issues/710)"
---

# The Bash guards' shared shell reader does not read inside a double-quoted command substitution

Agent-filed by merge-lane-2 on 2026-09-24, from a reproduced review finding. The reproduction is first; the cause and the next action follow it.

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

The false refusal is `mac-claude`'s non-blocking finding on PR [Hand-typed gh issue comments, creates and body edits are refused](https://github.com/nedschorus/nedschorus/pull/708), [inline comment 4096774424](https://github.com/nedschorus/nedschorus/pull/708#discussion_r4096774424). The missed refusal is question 3 of merge-lane-2's review of the same PR, [review 5308447683](https://github.com/nedschorus/nedschorus/pull/708#pullrequestreview-5308447683). The keystroke guard's instance predates PR 708; that PR added a third consumer of the reader.
