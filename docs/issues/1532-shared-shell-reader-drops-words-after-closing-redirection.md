---
issue: "[Shared shell reader drops words after closing redirection; force-push guard misses --force](https://github.com/nedschorus/nedschorus/issues/1532)"
---

# Shared shell reader drops words after closing redirection; force-push guard misses --force

## Reproduction

On main at 986387b3, on ned-box, run in a scratch checkout:

```
python3 - <<'EOF'
import importlib.util, sys
sys.path.insert(0, 'nc-systems/general-tools')
spec = importlib.util.spec_from_file_location('r', 'nc-systems/general-tools/shell-command-tree-sitter-bash-reader-common.py')
r = importlib.util.module_from_spec(spec); spec.loader.exec_module(r)
for c in ['git push --force origin main', 'git push >&- --force origin main', 'git push 2>&- --force origin main']:
    print(repr(c), [list(x) for x in r.simple_commands(c)])
EOF
```

It prints:

```
'git push --force origin main' [['git', 'push', '--force', 'origin', 'main']]
'git push >&- --force origin main' [['git', 'push']]
'git push 2>&- --force origin main' [['git', 'push'], ['origin', 'main']]
```

Bash itself passes `push --force origin main` to git for all three: `bash -c 'set -- push 2>&- --force origin main; echo "$@"'` prints `push --force origin main`.

The force-push guard, `scripts/force-push-with-open-pull-request-guard-hook.py`, run on a PreToolUse Bash input for a branch with an open pull request (the branch `shell-reader-escaped-blank-gap-knows-where-previous-word-ends` of [PR 1530: Shell reader: escaped blanks that touch a word's end stay in that word, as bash reads them](https://github.com/nedschorus/nedschorus/pull/1530), while it was open), denies `git push --force origin <branch>`, but exits 0 with no output, which allows the command, for `git push >&- --force origin <branch>` and `git push 2>&- --force origin <branch>`.

## Why it matters

The force-push guard exists so that a frozen-head, the pushed head commit of a pull request under review, is never rewritten. With a closing redirection (`>&-`, `2>&-` or `<&-`) anywhere before `--force`, an agent's force push to a branch with an open pull request goes through, and the reviewed head commit is lost from the branch. Every other guard that calls `simple_commands` in `nc-systems/general-tools/shell-command-tree-sitter-bash-reader-common.py` reads the same truncated words.

The cause, as the reproduction shows: tree-sitter-bash parses a closing operator ending in `&-` as a redirection that takes a destination. For `>&-`, every following word becomes that destination. For `2>&-`, only the next word does, and the parser then inserts a missing `;`, so `origin main` becomes a separate command. Either way, the words never reach the command's arguments.

Found by mac-claude's review 5543474061 of that pull request (https://github.com/nedschorus/nedschorus/pull/1530#pullrequestreview-5543474061). The same review showed that the pull request had made the misread reach one more case (`zzq <&- ''\ ;` loses its one-space argument). merge-lane-2 reproduced the guard bypass with the commands above.

## Outcome

Fixed by [PR 1536: Shell reader: words after a closing redirection are arguments, so the force-push guard sees --force](https://github.com/nedschorus/nedschorus/pull/1536), merged into main on 2026-10-16 at 08:09:30Z as merge commit 37b47858. When a redirection operator ends in `&-`, the shared shell reader now keeps every word after it as an argument of the same command. The force-push guard refuses `git push <operator> --force origin <branch>` for each of six spellings (`>&-`, `2>&-`, `<&-` and `3>&-` before `--force`, and `2>&-` before `-f` and before `--force-with-lease`) for a branch with an open pull request; each guard-level test fails on the base and passes with the fix. The pull request's reviewer replayed 210,029 recorded Bash commands through every guard at the base and at the fix, and every guard gave the same answer for every command.

The fix leaves two rarer ways past the force-push guard, which main already had in other spellings and which no recorded command uses: a descriptor written in hex before the closing operator, such as `0x1>&-`, and a backslash-newline just before a `<` redirection. reboot-test is closing both, with the other follow-ups to PR 1536, on branch `shell-reader-next-redirection-descriptor-is-decimal-digits-only`.
