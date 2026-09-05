<!-- provenance: runtime=codex model=gpt-5.6-terra effort=low cell=fast-clarify tier=floor duration_s=40 tokens=27450 target=docs/walk/claude-code-release-changes-affecting-the-fleet-2026-08-31-item2-rewrite.md -->

# 1. What it says

## Item 2 of 11: Why the Mac stopped updating, and what to do about it

Claude Code on the Mac was installed by Homebrew at version 2.1.241 on 24 August, but each seat launch subsequently ran `claude update`, which found an update, instructed the user to use Homebrew, and nevertheless returned success. Because the launcher warns only on failure, it silently continued launching seats on the stale version; manually running Homebrew’s upgrade command updated the Mac to 2.1.252. Claude’s updater intentionally does not replace a Homebrew installation, whereas the Ubuntu box uses Claude’s own installation and updates correctly; the durable choices are to replace the Mac’s Homebrew installation with Claude’s own installation or modify the Mac launcher to upgrade through Homebrew, with the former recommended for a common installation method and unchanged launcher.

# 2. Where you stumbled

1. [question] “this Mac” — Which specific Mac is the document referring to?

2. [question] “The launcher” — What launcher is meant, and where is its implementation or configuration?

3. [question] “the box” — Which Ubuntu host is “the box”?

4. [question] “Every seat launch” — What is a seat launch, and which component invokes the update command during one?

5. [question] “On 24 August” — Which year is meant?

6. [question] “Remove Homebrew’s copy from the Mac and install Claude’s own” — Which supported installation procedure and resulting executable location are intended?

# 3. What it does not cover

1. [no-rule] “Two ways to fix it for good:” — What should the owner do if the Mac has both a Homebrew installation and a Claude-installer installation, so both stated approaches appear applicable?

2. [no-rule] “teach the launcher to run `brew upgrade claude-code@latest` on this Mac” — What should the launcher do when that Homebrew upgrade fails, requires user action, or reports success without installing a newer version?

3. [no-rule] “Remove Homebrew’s copy from the Mac and install Claude’s own” — How is the owner to determine that the Homebrew copy has been removed and the replacement is the copy launched by every seat?

4. [no-rule] “The launcher then works unchanged on both machines.” — What condition determines that this change is complete, rather than merely installed?
