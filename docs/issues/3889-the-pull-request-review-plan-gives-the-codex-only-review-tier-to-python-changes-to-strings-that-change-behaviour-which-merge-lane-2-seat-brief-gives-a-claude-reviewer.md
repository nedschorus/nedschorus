---
issue: "[The pull request review plan gives the Codex-only review tier to Python changes to strings that change behaviour, which merge-lane-2's seat-brief gives a Claude reviewer](https://github.com/nedschorus/nedschorus/issues/3889)"
---

# The pull request review plan gives the Codex-only review tier to Python changes to strings that change behaviour, which merge-lane-2's seat-brief gives a Claude reviewer

Filed by merge-lane-2 on ned-box on 2026-11-18. The reproduction comes first; the contradiction and the next action follow it.

## Reproduction

The program is `scripts/pull-request-review-plan.py` as it is on main at `d81207545`. The test script loads the program's function `classify_changed_file_into_class_tier_and_reason` and runs it on three throwaway git repositories, each holding one file, `guard_example.py`, committed once before and once after one change:

1. A list element of a command list changes from `"push"` to `"push --force"`: `REFUSED_GIT_SUBCOMMANDS = ["push", "reset"]` becomes `REFUSED_GIT_SUBCOMMANDS = ["push --force", "reset"]`, beside a function `refused(c)` that returns `c in REFUSED_GIT_SUBCOMMANDS`. This changes which commands the function refuses.
2. A regular expression is widened: `PATTERN = re.compile(r"^git push\b")` becomes `PATTERN = re.compile(r"^git (push|reset)\b")`.
3. A control case: a number constant changes, `LIMIT = 1` becomes `LIMIT = 2`.

The command, run on ned-box, where `<dir>` is `/home/nedlern/.cache/claude-code-tmp/claude-1000/-home-nedlern-agents-merge-lane-2/2739e5ae-39cf-4328-9704-7a7cb333dde6/scratchpad/verify` (a session scratch directory, which a cleanup may remove, so the script is copied in full below):

    cd <dir> && python3 -I tier_classifier_string_constant_test.py <dir>/repos

The script, `tier_classifier_string_constant_test.py`, which takes the directory to make the throwaway repositories in as its one argument:

    import importlib.util, subprocess, tempfile, pathlib, sys
    spec = importlib.util.spec_from_file_location("plan", "/home/nedlern/agents/merge-lane-2/scripts/pull-request-review-plan.py")
    plan = importlib.util.module_from_spec(spec); spec.loader.exec_module(plan)
    cases = {
     "list element 'push' -> 'push --force'": ('REFUSED_GIT_SUBCOMMANDS = ["push", "reset"]\n\ndef refused(c):\n    return c in REFUSED_GIT_SUBCOMMANDS\n',
                                             'REFUSED_GIT_SUBCOMMANDS = ["push --force", "reset"]\n\ndef refused(c):\n    return c in REFUSED_GIT_SUBCOMMANDS\n'),
     "regex constant widened": ('import re\nPATTERN = re.compile(r"^git push\\b")\n', 'import re\nPATTERN = re.compile(r"^git (push|reset)\\b")\n'),
     "control: number constant 1 -> 2": ('LIMIT = 1\n', 'LIMIT = 2\n'),
    }
    for name,(old,new) in cases.items():
        d = pathlib.Path(tempfile.mkdtemp(dir=sys.argv[1]))
        g = lambda *a: subprocess.run(["git","-C",str(d),"-c","user.name=t","-c","user.email=t@t",*a],check=True,capture_output=True,text=True).stdout.strip()
        g("init","-q"); f=d/"guard_example.py"
        f.write_text(old); g("add","."); g("commit","-qm","old"); o=g("rev-parse","HEAD")
        f.write_text(new); g("commit","-qam","new"); n=g("rev-parse","HEAD")
        print(name, "->", plan.classify_changed_file_into_class_tier_and_reason(d, o, n, "guard_example.py", "M", set()))

Its output, exit status 0:

    list element 'push' -> 'push --force' -> ('code', 'codex-review-and-head-tests-tier', 'guard_example.py changes only docstrings, comments and string constants')
    regex constant widened -> ('code', 'codex-review-and-head-tests-tier', 'guard_example.py changes only docstrings, comments and string constants')
    control: number constant 1 -> 2 -> ('code', 'claude-and-codex-review-and-head-tests-tier', 'guard_example.py changes its syntax tree beyond docstrings, comments and string constants')

Both string changes change what the code does, yet they get `codex-review-and-head-tests-tier`, which has no Claude reviewer; the number change gets `claude-and-codex-review-and-head-tests-tier`.

## Why it happens

The program's docstring states the rule it follows, Rule 1: "Python changes limited to docstrings, comments and string constants get codex-review-and-head-tests-tier." The code carries the rule out in the class `SyntaxTreeWithoutDocstringsOrStringValues`, whose method `visit_Constant` sets every string constant to `""` before the old and new syntax trees are compared, so any change to any string, printed or not, compares equal. The rule and the code came in together, in PR [pull-request-review-plan: compute a pull request's review tier, fix-round delta and brief facts](https://github.com/nedschorus/nedschorus/pull/943), commit `121248c25`.

## The contradiction

merge-lane-2's seat-brief, `nedlern@ned-box:/home/nedlern/agents/merge-lane-2/CLAUDE.local.md` (machine-local, not in the repository), gives the Codex-only tier to "Tests only, or only printed text, comments and docstrings, or only shell commands and code blocks in Markdown", and gives "Every other code change" one fresh Claude reviewer as well. A string that is not printed text, such as an element of a command list or a regular expression, is "every other code change" under the seat-brief but gets the Codex-only tier under the program.

The program still sends every change to a registered hook, to `.claude/guard-hooks/` and to `.claude/settings.json` to `claude-and-codex-review-and-head-tests-tier` whatever it changes. A module that a hook only imports, and every other program, is not covered by that exception, so a change to a string that steers its behaviour reaches main without a Claude reviewer.

## What to do next

Which rule is intended, the program's Rule 1 or the seat-brief's "printed text", is a design question for the program's owner, merge-lane-2, and the user; this issue does not choose a fix. The next action is for merge-lane-2 to put the choice to the user. Three ways out are open, and none is chosen here. First, the program changes so that only a docstring, a comment or a string that is printed text counts as allowed at the lower tier, with a test built from the reproduction's first two cases; the program already finds printed strings for another purpose, with `tool_message_to_agent_string_nodes_in_source`, which it loads from `nc-systems/general-tools/`, and that finder could decide which strings `visit_Constant` blanks. Second, the seat-brief changes to say "string constants", as the program does. Third, the seat-brief's tier bullets stop restating the rule and say only that the tier is the one the program prints, so the rule is kept in one place.
