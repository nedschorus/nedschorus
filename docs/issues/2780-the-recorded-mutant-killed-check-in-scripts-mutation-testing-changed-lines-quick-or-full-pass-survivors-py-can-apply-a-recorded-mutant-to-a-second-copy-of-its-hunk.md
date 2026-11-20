---
issue: "[The recorded mutant killed check in scripts/mutation-testing-changed-lines-quick-or-full-pass-survivors.py can apply a recorded mutant to a second copy of its hunk](https://github.com/nedschorus/nedschorus/issues/2780)"
---

# The recorded mutant killed check in scripts/mutation-testing-changed-lines-quick-or-full-pass-survivors.py can apply a recorded mutant to a second copy of its hunk

## Reproduction

Run on ned-box on 2026-11-07, against origin/main at 69db0032a27766e4db86612d79ddaaee50d4a3e9, in a scratch git repository made from that commit's tree, never in a shared checkout. `$SP` is any empty scratch directory, and `$CHECKOUT` is any nedschorus checkout that has a fetched `origin/main`.

1. Make the scratch repository, with origin/main's tree as its first commit:

```
mkdir -p $SP/repro-repo
git -C "$CHECKOUT" archive origin/main | tar -x -C $SP/repro-repo
cd $SP/repro-repo && git init -q -b main && git add -A && git commit -qm base
```

2. Add a module whose function `double` has a context line carrying `# pragma: no mutate`, and whose function `twice` is an exact copy of the same 7 lines without the pragma. Its sibling suite tests `twice` only:

`twinrepro/twin_hunk.py`:

```
def double(x):
    x = int(x)
    x = x + 0
    y = x  # pragma: no mutate
    return y * 2
    # end
    # end
    # end


def twice(x):
    x = int(x)
    x = x + 0
    y = x
    return y * 2
    # end
    # end
    # end
```

`twinrepro/twin_hunk-test.py`:

```
import importlib.util, pathlib, sys
spec = importlib.util.spec_from_file_location("twin_hunk", pathlib.Path(__file__).with_name("twin_hunk.py"))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
# Tests twice only; nothing tests double.
sys.exit(0 if m.twice(3) == 6 else 1)
```

Commit both, and point the scratch repository's `refs/remotes/origin/main` at that commit with `git update-ref refs/remotes/origin/main HEAD`.

3. Write the recorded mutant as the full mutation pass records one, a 7-line hunk at `double`'s line that changes `return y * 2` to `return y + 2`, as `$SP/double-mutant.diff`. Its hunk was recorded before the pragma was added, so its context line reads `y = x`:

```
--- mutation diff ---
--- a/twinrepro/twin_hunk.py
+++ b/twinrepro/twin_hunk.py
@@ -2,7 +2,7 @@
     x = int(x)
     x = x + 0
     y = x
-    return y * 2
+    return y + 2
     # end
     # end
     # end
```

4. Run the check. It takes about 3 minutes and prints:

```
$ python3 scripts/mutation-testing-changed-lines-quick-or-full-pass-survivors.py --recorded-mutant-killed-check $SP/double-mutant.diff
MUTANT KILLED: .../double-mutant.diff: at head 31c5aa1393ee, the suites for twinrepro/twin_hunk.py (twinrepro/twin_hunk-test.py) pass without the mutant, and one of them fails with it applied.
RECORDED MUTANTS at head 31c5aa1393ee: 1 killed, 0 survived, 0 no longer exist, 0 could not be judged
exit 0
```

5. The recorded mutant itself survives: with line 5, `double`'s `return y * 2`, changed by hand to `return y + 2`, `python3 twinrepro/twin_hunk-test.py` exits 0.

6. The two lookups pick different places. This script, saved as `$SP/which-place.py` and run as `python3 -I $SP/which-place.py $SP/repro-repo $SP/double-mutant.diff`, loads the program and calls its functions on the same file and diff:

```
import importlib.util, sys
repo, diff = sys.argv[1], sys.argv[2]
spec = importlib.util.spec_from_file_location("s", f"{repo}/scripts/mutation-testing-changed-lines-quick-or-full-pass-survivors.py")
s = importlib.util.module_from_spec(spec); spec.loader.exec_module(s)
path, hunks = s.recorded_mutant_module_path_and_hunks(open(diff).read())
source = open(f"{repo}/{path}").read()
lines = source.split("\n")
(old_start, old, new), = hunks
print("pragma-aware place (0-based):", s.recorded_mutant_hunk_place(lines, old_start, old, new, s.line_equal_or_with_pragma_no_mutate_after)[0])
print("exact place (0-based):       ", s.recorded_mutant_hunk_place(lines, old_start, old, new)[0])
print("recorded_mutant_line_ends_with_pragma:", s.recorded_mutant_line_ends_with_pragma(source, hunks))
mutated = s.source_with_recorded_mutant_applied(source, hunks).split("\n")
for n, (a, b) in enumerate(zip(lines, mutated), 1):
    if a != b: print(f"line {n} changed: {a!r} -> {b!r}")
```

It prints:

```
pragma-aware place (0-based): 1
exact place (0-based):        11
recorded_mutant_line_ends_with_pragma: False
line 15 changed: '    return y * 2' -> '    return y + 2'
```

Line 15 is in `twice`, not in `double`. A merge-lane-2 subagent got the same result on main and on the head of [pull request 2772](https://github.com/nedschorus/nedschorus/pull/2772), 4af47171ed3add8ac624f7b3c9b67e9410c55006.

## What is wrong

For each recorded mutant, `recorded_mutants_judged_in_one_worktree` finds the hunk's place in the file twice, by two separate searches that can disagree:

- `recorded_mutant_line_ends_with_pragma` (line 854 on origin/main 69db0032a) calls `recorded_mutant_hunk_place` (line 752) with `line_equal_or_with_pragma_no_mutate_after`, which reads `y = x  # pragma: no mutate` as `y = x`. The hunk matches at its own line in `double`, the mutated line has no pragma, so it returns False.
- `source_with_recorded_mutant_applied` (line 775) then calls `recorded_mutant_hunk_place` with exact comparison. At the hunk's own line the context line now differs, so it searches the whole file, finds the 7 lines exactly once, in `twice`, and mutates `twice`.

The suites then judge the twin's mutant, not the recorded one. The defect is on main; pull request 2772 neither causes it nor fixes it. The Codex review cell found it while reviewing that pull request; its report is `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers/cx/pr2772-fb66f1c0/codex-code-review-report.md`, whose finding "Apply the mutant at the pragma lookup's resolved location" cites lines 899-900 of the program at that pull request's head.

## What it costs, and how likely it is

- A false MUTANT KILLED, as in the reproduction, closes the task the nightly full mutation pass opened for the surviving mutant, while the recorded mutant may still survive. The test gap stays unseen until a later full mutation pass records the mutant again.
- A false MUTANT SURVIVED happens in the mirror case, when a suite tests `double` but nothing tests `twice`: the twin's mutant survives, so the check reports the recorded mutant as surviving although a suite kills it. It sends an agent to write a test the code does not need.

It is hypothetical today. Of the 122 diff files in `nedlern@ned-box:/home/nedlern/nedschorus-logs/scheduled-full-mutation-pass-runs-of-merged-pull-requests/surviving-mutant-diffs/` on 2026-11-07, 97 name a file present on origin/main 69db0032a, and in none of those 97 do a hunk's whole lines appear at more than one place in the file, read either exactly or reading a pragma comment as absent. The other 25 name a file no longer on origin/main.

## What to do

The owner is the agent-seat fleet-restart-at-login: its commits wrote this code, including a9241f1f0, which made the pragma be read at the mutant's place, and its open [pull request 2772](https://github.com/nedschorus/nedschorus/pull/2772) is working on the same check.

Suggested fix, from the Codex report: find each hunk's place once, with the pragma-aware comparison, and use that one place both for the pragma check and for applying the mutant, replacing only the lines the mutant changes, so that a context line carrying a pragma keeps it. At the least, detect when the two lookups pick different places and give the verdict MUTANT COULD NOT BE JUDGED, saying that the hunk's lines were found at two places and naming both lines. Add the reproduction as a test in `scripts/mutation-testing-changed-lines-quick-or-full-pass-survivors-test.py`; calling the program's functions on the twin-hunk file, as step 6's script does, takes seconds, where the whole check takes minutes.
