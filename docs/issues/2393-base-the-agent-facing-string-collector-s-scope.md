---
issue: "[Fix the agent-facing string collector's scope rules for global declarations, comprehension targets and type parameters](https://github.com/nedschorus/nedschorus/issues/2393)"
---

# Fix the agent-facing string collector's scope rules for global declarations, comprehension targets and type parameters

Filed by cold-read-improvement on 2026-11-02, as the follow-up that the `#root_cause_not_fixed` line of [PR 2346](https://github.com/nedschorus/nedschorus/pull/2346) names. Line numbers are on that pull request's head, `5f5f26cd1`.

## What is wrong

`nc-systems/general-tools/python-source-agent-facing-string-collector-common.py` lists the strings a Python file hands an agent; `scripts/pull-request-review-plan.py` uses that list to decide which strings merge-lane-2 fast-reads in a pull request. To follow a local name to the strings bound to it, the collector must know which names a function, lambda, class body or comprehension binds, and which outer binding a name refers to. It works this out with its own rules, chiefly `scope_assigned_names` (`:537-558`), `nodes_in_own_scope` (`:581`) and `definition_time_expressions` (`:515`). Each binding form those rules do not model is a miss of its own, and reviews keep finding new ones: Codex found seven forms after [PR 2280](https://github.com/nedschorus/nedschorus/pull/2280) and two after [PR 2318](https://github.com/nedschorus/nedschorus/pull/2318), and PR 2346 added the forms it could.

## Misses still at PR 2346's head

1. **`global` in a nested function.** No branch of `scope_assigned_names` handles `ast.Global`. Reproduced at `5f5f26cd1` by loading the collector and calling `agent_facing_string_nodes_in_source` on this source:

   ```
   text = 1
   def emit(text):
       def inner():
           global text
           print(text)
       inner()
   emit("global hidden")
   ```

   It returns `{'line': 7, 'label': 'emit()', 'text': 'global hidden', ...}`, but `inner` prints the module-level `text`, not `emit`'s parameter, so `"global hidden"` never reaches a printed line. From merge-lane-2's review comment on PR 2346 at the collector's line 537.
2. **A comprehension's target does not hide a name while the collector follows a helper's calls** (`:548-549`, and `calls_and_parameters_they_see` at `:219-241`): for a helper `emit(text)` whose nested `inner()` holds `[print(text) for text in ["actual"]]`, the call `emit("never shown")` lists `"never shown"`, though the comprehension prints its own `text`. `calls_and_parameters_they_see` walks comprehension bodies without hiding their targets. Codex review cell on PR 2346.
3. **A name read inside a comprehension's target counts as bound** (`:493`): a target can be a subscript, as in `print([text for messages[text] in items])`, where `text` is read, not bound; with a local `text = "shown"`, the collector loses `"shown"`. Codex review cell on PR 2346.
4. **A type parameter's own name does not hide an outer name in its bound and default** (`:519-525`): with an enclosing local `text = "unused"` and `class C[text: print(text)]: pass`, the bound's `text` is the type parameter, but the collector reads the bound in the enclosing scope and lists `"unused"`. Codex review cell on PR 2346.

merge-lane-2 graded items 2 to 4 as hypothetical, since no file in the repository uses those forms. The Codex report is `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers/cx/pr2346-09e5d982/codex-code-review-report.md`.

## What is decided

The user approved with "A", on 2026-11-02, item 8.1 of cold-read-improvement's approval-walk cold-read-improvement-handoff-intake-decisions-2026-10-31 (walk-document `nedlern@ned-box:/home/nedlern/agents/cold-read-improvement/docs/walk/cold-read-improvement-handoff-intake-decisions-2026-10-31.md`, "Item 8.1 of 16"), whose recommendation was: "approve the four direct fixes, and rewrite the issue to drop the rebuild."

- The four misses are fixed in the collector's existing rules, each with a test that fails without its fix.
- The rebuild this GHI first planned is dropped: taking each scope's bindings from the standard library's `symtable.symtable(source, path, "exec")` instead of from the collector's own rules.

Why the rebuild was dropped, from checks on Python 3.14.4 on ned-box:

- **symtable gives list, set and dict comprehensions no scope of their own.** Since Python 3.12 these comprehensions are inlined into the enclosing function (PEP 709), and symtable reports their targets as the function's own locals. For `def f(items): a = [t for t in items]; d = [w for messages[w] in items]`, symtable lists `t`, `w` and even the read `messages` among `f`'s names; only a generator expression keeps a scope of its own. So symtable cannot say that the `text` in `[print(text) for text in ...]` is the comprehension's, which is misses 2 and 3; comprehensions are where most of the collector's misses were.
- **symtable's answers differ between Python versions.** Comprehension inlining arrived in 3.12, and 3.14 adds annotation scopes. The edit hook that uses the collector, `nc-systems/general-tools/python-edit-changed-agent-facing-message-check-reminder-hook.py`, runs on both the Mac and ned-box, whose Python versions can differ, so rules built on symtable could collect different strings on each machine.
- **symtable gives no link from a scope to its `ast` node.** Matching its scopes to the code by kind, name and line would be a new hand-written layer.

A rebuild of the collector's scope rules, as one model of how Python scopes names rather than one rule per binding form, becomes worth doing when either of these holds:

- misses keep turning up in forms that real files in the repository use, not only in forms that reviewers construct, so that fixing them one rule at a time costs more than the rebuild;
- both machines run one fixed Python version, and a scope tracker that models comprehensions as that version runs them is available, so that the rebuild can take its answers from that tracker.

Until then, a new miss is fixed in the rule that missed it, with a test that fails without the fix.

## Outcome

[PR 2426](https://github.com/nedschorus/nedschorus/pull/2426), merged on 2026-11-02, fixed the four misses in the collector, without symtable:

1. A nested function's `global text` hides the helper's parameter `text`: `scope_assigned_names` adds the names a scope declares global.
2. A comprehension's target hides the enclosing name in the comprehension's later parts, both in helper discovery (`calls_and_parameters_they_see`) and where the collector visits printed forms (the new `visit_comprehension_parts`), but not in its first iterable, which Python evaluates in the enclosing scope. Both go through the new `comprehension_parts_with_names_they_hide`.
3. A name read inside a target, as `text` in `for messages[text] in items`, is no longer taken as bound: `comprehension_target_names` keeps only the names the target stores to.
4. A type parameter's name hides the outer name in its own bound and default, and in a generic definition's annotations, bases and keywords (PEP 695): the new `type_parameter_scope_expressions` splits these out of `definition_time_expressions`.

The module docstring's "Where a followed name may be bound" states all four. PR 2426 added seven cases to `nc-systems/general-tools/tests/python-source-agent-facing-string-collector-common-test.py`: six fail on the collector before the fix, and the seventh, a parameter printed in a comprehension's first iterable, checks that the fix does not hide too much. Over the 370 Python files at main, test files skipped, the collector's entries were the same before and after the fix.

## Next action

Once the pull request that lands this GHI-MD edit has merged and `python3 scripts/ghi-issue-write.py edit` has been rerun on it, close the issue with `gh issue close 2393 --repo nedschorus/nedschorus --reason completed`.

## Related

GHI [Replace the hand-written parsers in the project's hooks and scripts with real parsers](https://github.com/nedschorus/nedschorus/issues/1196) is the general effort this belongs to; its work so far moved shell-command parsing onto tree-sitter-bash. This GHI covers the Python collector's scope rules only.
