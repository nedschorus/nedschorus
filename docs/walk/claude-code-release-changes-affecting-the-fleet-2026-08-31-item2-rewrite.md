## Item 2 of 11: Why the Mac stopped updating, and what to do about it

Here is what actually happened on this Mac.

On 24 August, Claude Code version 2.1.241 was installed here using Homebrew —
the package manager you use for other software on this machine.

Every seat launch since then has run the command `claude update`. That command
looked for a newer version, found one, and then stopped. It printed "Claude is
managed by Homebrew" and said to run `brew upgrade` instead. Then it reported
success.

The launcher prints a warning only when that command reports failure. It saw
success, so it printed nothing and started the seat on 2.1.241. Fifteen seats
launched that way today alone.

Half an hour ago we ran `brew upgrade claude-code@latest` by hand. It took
seconds. The Mac now runs 2.1.252.

The cause: a Mac can hold Claude Code in two different ways. Homebrew can
install it, or Claude's own installer can. `claude update` only replaces copies
that Claude's own installer put there. It refuses to overwrite Homebrew's copy
deliberately — two programs writing the same file would leave Homebrew's records
wrong, and the two would fight at every later upgrade.

The Ubuntu box holds Claude's own install, so `claude update` works there. Only
the Mac is mismatched.

Two ways to fix it for good:

- Remove Homebrew's copy from the Mac and install Claude's own, matching the
  box. The launcher then works unchanged on both machines.
- Keep Homebrew's copy, and teach the launcher to run
  `brew upgrade claude-code@latest` on this Mac.

My recommendation: the first. One install method on both machines, and no new
logic in the launcher.
