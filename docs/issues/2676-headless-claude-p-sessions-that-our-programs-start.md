---
issue: "[Headless claude -p sessions that our programs start load the user's claude.ai connectors, Gmail, Google Drive and Google Calendar among them, and most run in bypassPermissions mode](https://github.com/nedschorus/nedschorus/issues/2676)"
---

# Headless claude -p sessions that our programs start load the user's claude.ai connectors, Gmail, Google Drive and Google Calendar among them, and most run in bypassPermissions mode

## Reproduction

On ned-box, Claude Code 2.1.318, 2026-11-05. Each run started from an empty directory as `claude -p --model haiku --max-turns 1 --input-format stream-json --output-format stream-json --verbose <the flags below>`, with the prompt "Reply with the word ok and use no tools." sent on stdin 20 seconds after start. Only the `system`/`init` event was read: its `permissionMode`, and the `mcp__` names in its `tools` list. Each row passes the flags that decide the permission mode, the settings and the tools; flags that do not, such as `--json-schema`, `--system-prompt` and `--model`, were left out or replaced by `--model haiku`.

| flags, copied from | permissionMode | tools | `mcp__` tools |
|---|---|---|---|
| `--allowedTools Read,Grep,Glob,Write,WebFetch --disallowedTools Bash,Monitor --settings '{"disableAllHooks":true}'` (the cold-read Claude cell) | bypassPermissions | 104 | 72 |
| `--setting-sources user --permission-mode bypassPermissions` (ghi-guide-agent-ask) | bypassPermissions | 104 | 72 |
| `--permission-mode dontAsk --allowedTools Read Grep Glob Bash WebFetch WebSearch` (the merge-lane Claude reviewer) | dontAsk | 106 | 72 |
| `--tools "" --settings '{"disableAllHooks":true}' --no-session-persistence` (the walk-me-through Stop hook) | bypassPermissions | 72 | 72 |
| the reviewer's flags plus `--strict-mcp-config` | dontAsk | 31 | 0 |
| `--tools "" --strict-mcp-config` | bypassPermissions | 0 | 0 |

Every run with `mcp__` tools listed `mcp__claude_ai_Gmail__send_message`, `mcp__claude_ai_Google_Drive__share_file`, `mcp__claude_ai_Google_Drive__trash_file` and `mcp__claude_ai_Google_Calendar__delete_event`, from the five claude.ai connectors (Claude Docs, Strava, Google Drive, Gmail, Google Calendar), all `connected`. `bypassPermissions` comes from `permissions.defaultMode` in `~/.claude/settings.json` on ned-box; `--settings` and `--setting-sources user` both keep the user's settings, so neither removes that mode. `--strict-mcp-config`, given without `--mcp-config`, removed every MCP server. The Mac was not tested (unverified there); several of these programs run on it too.

The 20-second wait matters. With the prompt sent at once, the init event shows the five claude.ai servers as `pending` and lists no `mcp__` tools, which looks safe but is not: the servers connect a few seconds later, while the session runs. A check of this defect has to wait for the servers, or read `mcp_servers` in the init event, which lists them in either case.

The reviewer of [pull request 2594](https://github.com/nedschorus/nedschorus/pull/2594) first found the same thing with `--json-schema <schema> --tools ""`.

## Why it matters

A headless session with these tools can send mail from the user's account, share or trash his Drive files and delete his calendar events, which cannot be undone. In `bypassPermissions` mode nothing asks before such a call, so the only thing that stops one is the model choosing not to make it. The sessions read text we do not control, such as pull request diffs, documents under review and web pages, so a prompt injection in that text could make the call. `--tools`, `--allowedTools` and `--disallowedTools` name built-in tools and do not keep MCP tools out; under `dontAsk`, a tool outside `--allowedTools` should be denied, but that was not tested here (unverified).

## Affected programs, on main at 17d6e4839

| program | permission mode the session runs in | MCP flags |
|---|---|---|
| `nc-systems/cold-read/cold-read-claude-cell.py`, `invocation_builder` (line 93); also run, as a subprocess or by import, by `nc-systems/cold-read/cold-read-grid.py`, `nc-systems/cold-read/cold-read-restater-judge-cell.py` and `scripts/tool-message-to-agent-ask-two-fresh-agents-next-step-and-check-named-script-flags.py` | user default, bypassPermissions | none |
| `scripts/sanity-check-adversarial-prompts.py`, `run_claude` (line 623), `--setting-sources user` | user default, bypassPermissions | none |
| `scripts/ghi-guide-agent-ask.py`, `run_claude` (line 566) | `--permission-mode bypassPermissions` | none |
| `scripts/merge-lane-pull-request-claude-reviewer-headless-run-and-review-post.py`, `run_reviewer` (line 218), and the `claude -p --resume` command it prints for an agent to run by hand (line 264) | `--permission-mode dontAsk` | none |
| `nc-systems/skills/walk-me-through/walk-me-through-agent-question-to-user-outside-approval-walk-items-refusal-stop-hook.py`, `model_judgement` (line 531), a Stop hook in `.claude/settings.json` that starts `claude -p` to judge question-like text in an agent message | user default, bypassPermissions | none |
| `nc-systems/skills/overview-write/overview-write-architecture-overview-claim-check-by-fresh-agent.py`, `run_fresh_agent` (line 447) | user default, bypassPermissions | none |
| `nc-systems/handoff/uncommitted-work-snapshot-hook-scheduled-check-that-real-claude-session-is-recorded-as-owner.py`, `start_claude` (line 152) | user default, bypassPermissions | none |

Search: `git grep -n -E '"claude", "-p"|claude_program, "-p"|--output-format' origin/main`, excluding tests; no program on main passes `--strict-mcp-config` or `--mcp-config` (`git grep -- "--strict-mcp-config\|--mcp-config" origin/main -- "*.py"` finds none outside tests). The shared launcher that the design in [GHI 2266](https://github.com/nedschorus/nedschorus/issues/2266) plans, a `run_claude` in a file `scripts/guide-agent-ask-scripts-common.py` not yet built, would have the same gap as that design is drafted, and [GHI 41](https://github.com/nedschorus/nedschorus/issues/41), one CLI for every headless agent run, is where a single fix could live.

## What to do

1. Add `--strict-mcp-config` to every launch in the table above, the printed resume command included. None of these programs uses an MCP tool. This flag is the fix that was shown to work; step 2 narrows what is left.
2. Pass an explicit `--permission-mode` to each, so the user's `defaultMode` does not decide it: `dontAsk` with the tools the program needs in `--allowedTools`, which is the default choice, or `bypassPermissions` only where a program fails under `dontAsk` because a tool call it needs is refused, with that reason in a comment.
3. Add one repository-wide test that finds every `claude -p` launch in tracked code other than tests, as the search above does, and fails on any launch without `--strict-mcp-config` and an explicit `--permission-mode`, and on any `bypassPermissions` outside an allow-list kept in the test. A launch added later is then caught without anyone remembering.
4. Make GHI 2266's shared launcher do the same before it lands; the test in step 3 fails on it until it does.
