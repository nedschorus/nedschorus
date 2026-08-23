# nedschorus — Codex agents: read CLAUDE.md

Read [CLAUDE.md](CLAUDE.md) at this repository's root and follow it — it is the single home for this project's rules. Any reference to Claude there typically also applies to Codex, unless it names a Claude-specific function that Codex has no equivalent for.

Mechanics, for maintainers: the Codex runtime — the GitHub review bot and `codex exec` review (pinned invocation: `scripts/code-review-codex-cell.py`) — injects this file by its documented mechanism; Claude Code reads CLAUDE.md directly and never reads this file (verified 2026-08-20, tools-disallowed probe). This file was a duplicate rules home until 2026-08-22, when the user ruled it a pointer; the rules live only in CLAUDE.md now, so nothing here needs syncing when they change.
