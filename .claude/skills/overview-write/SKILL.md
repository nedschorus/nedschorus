---
name: overview-write
description: Use when you write, refresh or fix an nc-architecture-overview, the page docs/nedschorus-wiki/nedschorus-<system>-architecture-overview.md of a system under nc-systems/, and when scripts/pull-request-review-plan.py refuses a pull request because an overview has no claim-check report showing every claim supported. Points to the page that says how an overview is written, and runs the program that checks its claims against the code.
---

# overview-write

An nc-architecture-overview tells an agent who must change a system how the system is built. Its usual defect is a confident statement about the code that is wrong, which a cold read cannot see, so a program checks every assertion against the code before the overview merges. The page `docs/nedschorus-wiki/nedschorus-how-to-write-an-architecture-overview.md`, called the how-to page here, holds the rules; this skill runs its check.

1. Write or refresh the overview as the how-to page says, ending it with the `**Checked against:**` line that names the commit whose code you describe: a commit of main, or, in a pull request that also changes the code the overview describes, a commit of that pull request that holds the code and is earlier in its history than the overview edit. Give it the cold read the how-to page's section "Checking an overview" names: a cold-read-full-run for a new overview, a cold-read-fast-read for a refresh. Commit it on your topic branch.

2. On ned-box, in the checkout of your topic branch, run `python3 nc-systems/skills/overview-write/overview-write-architecture-overview-claim-check-by-fresh-agent.py --overview <overview path>`. From the Mac, run it through `ssh nedlern@ned-box`, in a checkout there that holds your branch. It checks the overview as your branch's newest commit holds it, adding `--revision <commit>` to check another commit's: first `scripts/md-drift-lint.py`, then one fresh-agent, which takes several minutes. It prints its result and the path of its report in the log-store.

3. Do what the program's last line says.

4. When you believe a verdict is wrong, write a file outside the checkout that quotes each disputed assertion and gives your answer with the quoted line it rests on, and run step 2 again with `--writer-answers <that file>`. When an assertion is still disputed after two rounds, bring it to the user with the reports, as the how-to page says, and do not push until he rules.

5. `scripts/pull-request-review-plan.py` refuses a pull request that adds or changes an overview until the newest report on the overview's exact text shows every assertion supported. A report stays valid while that text is unchanged, through a rebase included; any change to the text needs step 2 again.
