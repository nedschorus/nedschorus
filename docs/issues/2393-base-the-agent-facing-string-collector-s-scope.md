---
issue: "[Base the agent-facing string collector's scope rules on Python's symtable module instead of hand-written rules](https://github.com/nedschorus/nedschorus/issues/2393)"
---

# Base the agent-facing string collector's scope rules on Python's symtable module instead of hand-written rules

Filed by cold-read-improvement on 2026-11-02, as the follow-up that the `#root_cause_not_fixed` line of [PR 2346](https://github.com/nedschorus/nedschorus/pull/2346) names. Line numbers are on that pull request's head, `5f5f26cd1`.

## What is wrong

`nc-systems/general-tools/python-source-agent-facing-string-collector-common.py` lists the strings a Python file hands an agent; `scripts/pull-request-review-plan.py` uses that list to decide which strings merge-lane-2 fast-reads in a pull request. To follow a local name to the strings bound to it, the collector must know which names a function, lambda, class body or comprehension binds, and which outer binding a name refers to. It works this out with its own rules, chiefly `scope_assigned_names` (`:537-558`), `nodes_in_own_scope` (`:581`) and `definition_time_expressions` (`:515`). Each binding form those rules do not model is a miss of its own, and reviews keep finding new ones: Codex found seven forms after [PR 2280](https://github.com/nedschorus/nedschorus/pull/2280) and two after [PR 2318](https://github.com/nedschorus/nedschorus/pull/2318), and PR 2346 added the forms it could. The standard library's `symtable` module reports, for every scope, which names are local, global, nonlocal, free or parameters, as the compiler itself decides; rules built on it would not miss a binding form.

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

merge-lane-2 graded items 2 to 4 as hypothetical, since no file in the repository uses those forms; they show the pattern this GHI removes. The Codex report is `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers/cx/pr2346-09e5d982/codex-code-review-report.md`.

## What to do

Rewrite the collector's scope handling, in the walk that follows local names and in helper discovery (`calls_and_parameters_they_see`, `helper_printers_in_tree`) alike, so that which names each scope binds, and which scope a name refers to, come from `symtable.symtable(source, path, "exec")`; keep the collector's rules for which strings are messages as they are. `symtable` gives no `ast` node for a scope, and comprehensions, lambdas and PEP 695 type-parameter lists get child scopes of their own, often several on one line, so how each `symtable` scope is matched to its `ast` node is the first thing the design settles. Source that `ast.parse` rejects is rejected by `symtable` too, and the collector keeps returning no entries for it. Two choices also need a decision in the design, and the module docstring is updated to state what was decided:

- The class-body simplification the module docstring states: a name a class body binds hides the enclosing function's local everywhere in the class body, lambdas included, though Python's own scoping would let a lambda see the function's local. With `symtable` the collector could follow Python exactly; keeping the simplification would mean keeping one hand-written rule on top of `symtable`, since `symtable` follows Python. Which to do is part of this work.
- Whether the collector still reads only the function that holds the form, as the docstring's "Where a followed name may be bound" says, or also follows a name to module level, which `symtable` makes easy.

Turn the four misses above into test cases in `nc-systems/general-tools/tests/python-source-agent-facing-string-collector-common-test.py`, each failing before the rewrite, and keep every existing case passing or change it with the reason in the commit message. Then compare the collector's entries over every non-test Python file at main against the rewrite, as PR 2346's description did by hand, and explain each gained or lost entry in the pull request; write the comparison as a script that takes two commits and prints the gained and lost entries, so the next change to the collector can rerun it.

## Related

GHI [Replace the hand-written parsers in the project's hooks and scripts with real parsers](https://github.com/nedschorus/nedschorus/issues/1196) is the general effort this belongs to; its work so far moved shell-command parsing onto tree-sitter-bash. This GHI covers the Python collector's scope rules only.
