#!/usr/bin/env python3
"""Fail when a registered hook's message for a rule does not start with a rule ID,
or when two hooks share one rule ID.

Each message a hook in .claude/settings.json prints for a rule, a refusal, a
warning or a reminder, starts with `[rule <id>]`, as
nc-systems/general-tools/claude-code-registered-hook-rule-id-pattern-hook-files-list-and-source-scan-common.py says, so
the weekly count of each ID in the transcripts can name the rules that never
fire.

The suite loads each registered hook, as
scripts/registered-hook-messages-carry-no-citations-test.py does, and reads
every module-level constant named in capitals whose name ends in one of the
tool-message-to-agent collector's suffixes, such as _MESSAGE, _REASON or
_LINES. Each such constant either starts with a rule ID, its first item for a
tuple or list, or is listed in CONSTANTS_THAT_OPEN_NO_RULE_MESSAGE with the
reason it opens none: it is a later part of a message, it says the hook failed
or could not check, or it is no message for a rule at all. A message built
inline, outside such a constant, is not read; the citations suite fails a
registered hook that declares no message constant.

An ID belongs to one hook file: the suite fails an ID written in two registered
hooks, an ID that opens no message constant of its hook, and a `[rule` that is
not a well-formed ID. Within one hook file, an ID that opens more than one
message constant must be listed in MESSAGE_VARIANTS_OF_ONE_RULE with exactly
the constants it opens, so that giving a second rule's message an existing ID
fails here until an author lists it as a variant and a reviewer sees that.
"""
import importlib.util
import re
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parent.parent
SETTINGS = REPOSITORY / ".claude" / "settings.json"


def load_by_path(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


rule_ids = load_by_path("claude_code_registered_hook_rule_id_pattern_hook_files_list_and_source_scan_common",
                        REPOSITORY / "nc-systems" / "general-tools" / "claude-code-registered-hook-rule-id-pattern-hook-files-list-and-source-scan-common.py")
collector = load_by_path(
    "python_source_tool_message_to_agent_string_collector_common",
    REPOSITORY / "nc-systems" / "general-tools" / "python-source-tool-message-to-agent-string-collector-common.py")

LATER_PART = "a later part of a message, after the opening that carries its rule's ID"
HOOK_FAILED = "says the hook failed or could not check, and lets the act through"
NOT_A_RULE = "no message for a rule: text the hook hands on as data"
COMMAND_MODE = "printed when an agent runs the file as a command, not when it runs as a hook"

# (hook path, constant name): why the constant opens no message for a rule.
CONSTANTS_THAT_OPEN_NO_RULE_MESSAGE = {
    # fork A
    (".claude/guard-hooks/claude-code-tmux-kill-server-and-kill-session-missing-server-selection-refusal-hook.py", "PARSER_UNAVAILABLE_NEXT_STEP_LINES"): HOOK_FAILED,
    (".claude/guard-hooks/force-push-with-open-pull-request-guard-hook.py", "PARSER_UNAVAILABLE_NEXT_STEP_LINES"): HOOK_FAILED,
    (".claude/guard-hooks/force-push-with-open-pull-request-guard-hook.py", "UNCHECKED_NOTE_FIRST_LINE"): HOOK_FAILED,
    (".claude/guard-hooks/force-push-with-open-pull-request-guard-hook.py", "UNCHECKED_NOTE_NO_RETRY_TEMPLATE"): HOOK_FAILED,
    (".claude/guard-hooks/force-push-with-open-pull-request-guard-hook.py", "UNCHECKED_NOTE_RETRY_TEMPLATE"): HOOK_FAILED,
    (".claude/guard-hooks/ghi-issue-write-hand-typed-gh-command-refusal.py", "CLOSE_LINES"): LATER_PART,
    (".claude/guard-hooks/ghi-issue-write-hand-typed-gh-command-refusal.py", "LABELS_ONLY_LINE"): LATER_PART,
    (".claude/guard-hooks/ghi-issue-write-hand-typed-gh-command-refusal.py", "PARSER_UNAVAILABLE_NEXT_STEP_LINES"): HOOK_FAILED,
    (".claude/guard-hooks/ghi-issue-write-hand-typed-gh-command-refusal.py", "RERUN_LINE"): LATER_PART,
    (".claude/guard-hooks/ghi-md-whole-file-replacement-soft-block.py", "PARSER_UNAVAILABLE_NEXT_STEP_LINES"): HOOK_FAILED,
    (".claude/guard-hooks/git-worktree-remove-cold-read-record-and-sanity-check-record-ship-to-log-store-first-guard-hook.py", "GIT_WORKTREE_REMOVE_NOT_THE_WHOLE_SHELL_COMMAND_REFUSAL_REASON"): LATER_PART,
    (".claude/guard-hooks/git-worktree-remove-cold-read-record-and-sanity-check-record-ship-to-log-store-first-guard-hook.py", "GIT_WORKTREE_REMOVE_PATH_WRITTEN_OUT_RUN_AGAIN_INSTRUCTION_TEMPLATE"): LATER_PART,
    (".claude/guard-hooks/git-worktree-remove-cold-read-record-and-sanity-check-record-ship-to-log-store-first-guard-hook.py", "PARSER_UNAVAILABLE_NEXT_STEP_LINES"): HOOK_FAILED,
    (".claude/guard-hooks/git-worktree-remove-cold-read-record-and-sanity-check-record-ship-to-log-store-first-guard-hook.py", "PATH_NAMES_NO_WORKTREE_REASON_TEMPLATE"): LATER_PART,
    (".claude/guard-hooks/git-worktree-remove-cold-read-record-and-sanity-check-record-ship-to-log-store-first-guard-hook.py", "PATH_NAMES_NO_WORKTREE_RUN_AGAIN_INSTRUCTION_TEMPLATE"): LATER_PART,
    (".claude/guard-hooks/git-worktree-remove-cold-read-record-and-sanity-check-record-ship-to-log-store-first-guard-hook.py", "RECORDS_NOT_READ_NOTICE"): HOOK_FAILED,
    (".claude/guard-hooks/git-worktree-remove-cold-read-record-and-sanity-check-record-ship-to-log-store-first-guard-hook.py", "RECORD_BEING_WRITTEN_LINE_TEMPLATE"): LATER_PART,
    (".claude/guard-hooks/git-worktree-remove-cold-read-record-and-sanity-check-record-ship-to-log-store-first-guard-hook.py", "RECORD_CHECK_FAILED_LINE_TEMPLATE"): LATER_PART,
    (".claude/guard-hooks/git-worktree-remove-cold-read-record-and-sanity-check-record-ship-to-log-store-first-guard-hook.py", "REMOVAL_NOT_DEFERRED_ENDING_TEMPLATE"): LATER_PART,
    (".claude/guard-hooks/git-worktree-remove-cold-read-record-and-sanity-check-record-ship-to-log-store-first-guard-hook.py", "REMOVAL_NOT_DEFERRED_FAILURE_TEMPLATE"): LATER_PART,
    (".claude/guard-hooks/git-worktree-remove-cold-read-record-and-sanity-check-record-ship-to-log-store-first-guard-hook.py", "SHIPMENT_FAILED_UNRESOLVED_INSTRUCTION_TEMPLATE"): LATER_PART,
    (".claude/guard-hooks/git-worktree-remove-cold-read-record-and-sanity-check-record-ship-to-log-store-first-guard-hook.py", "SHIPMENT_FAILED_UNRESOLVED_SCOPE_TEMPLATE"): LATER_PART,
    (".claude/guard-hooks/git-worktree-remove-cold-read-record-and-sanity-check-record-ship-to-log-store-first-guard-hook.py", "SHIPPER_PRINTED_NOTHING_LINE_TEMPLATE"): LATER_PART,
    (".claude/guard-hooks/git-worktree-remove-cold-read-record-and-sanity-check-record-ship-to-log-store-first-guard-hook.py", "SHIPPING_BUDGET_SPENT_LINE_TEMPLATE"): LATER_PART,
    (".claude/guard-hooks/git-worktree-remove-cold-read-record-and-sanity-check-record-ship-to-log-store-first-guard-hook.py", "SHIP_RECORDS_YOURSELF_NEXT_STEP_LINES"): HOOK_FAILED,
    (".claude/guard-hooks/git-worktree-remove-cold-read-record-and-sanity-check-record-ship-to-log-store-first-guard-hook.py", "UNSHIPPED_RECORD_LINE_TEMPLATE"): LATER_PART,
    (".claude/guard-hooks/git-worktree-remove-cold-read-record-and-sanity-check-record-ship-to-log-store-first-guard-hook.py", "WORKTREE_LISTING_FAILED_NOTICE"): HOOK_FAILED,
    (".claude/guard-hooks/guarded-file-unapproved-change-afterward-backup-and-ask-hook.py", "ASK_INSTRUCTIONS"): LATER_PART,
    (".claude/guard-hooks/hand-typed-codex-exec-command-refusal-hook.py", "PARSER_UNAVAILABLE_NEXT_STEP_LINES"): HOOK_FAILED,
    (".claude/guard-hooks/hand-typed-codex-exec-command-refusal-hook.py", "USAGE_LINE"): LATER_PART,
    (".claude/guard-hooks/handoff-deferral-cold-read-full-run-launch-refusal-hook.py", "PARSER_UNAVAILABLE_NEXT_STEP_TEMPLATE"): HOOK_FAILED,
    (".claude/guard-hooks/instruction-file-guard.py", "OBVIOUS_FIX_MARKER_LINES"): LATER_PART,
    (".claude/guard-hooks/instruction-file-guard.py", "PRE_APPROVED_CHANGE_MARKER_FIRST_LINE"): LATER_PART,
    (".claude/guard-hooks/instruction-file-guard.py", "PRE_APPROVED_CHANGE_MARKER_SECOND_LINE"): LATER_PART,
    (".claude/guard-hooks/instruction-file-guard.py", "ROUTE_AROUND_LINES"): LATER_PART,
    (".claude/guard-hooks/pkill-killall-and-process-name-pattern-kill-refusal-hook.py", "PARSER_UNAVAILABLE_NEXT_STEP_LINES"): HOOK_FAILED,
    (".claude/guard-hooks/search-file-argument-read-as-option-guard-hook.py", "PARSER_UNAVAILABLE_NEXT_STEP_LINES"): HOOK_FAILED,
    (".claude/guard-hooks/session-location-write-guard.py", "COULD_NOT_CHECK_MESSAGE"): HOOK_FAILED,
    (".claude/guard-hooks/synthetic-keystroke-guard-hook.py", "PARSER_UNAVAILABLE_NEXT_STEP_LINES"): HOOK_FAILED,
    (".claude/guard-hooks/synthetic-keystroke-guard-hook.py", "SHOW_THE_USER_ELSEWHERE_LINE"): LATER_PART,
    (".claude/guard-hooks/synthetic-keystroke-guard-hook.py", "SHOW_THE_USER_ON_MAC_LINE"): LATER_PART,
    ("nc-systems/general-tools/agent-seat-worktree-create-with-owner-file-claude-code-worktree-create-hook.py", "FAILED_MESSAGE_TEMPLATE"): HOOK_FAILED,
    ("nc-systems/general-tools/checkout-freshness-changed-skill-invoke-again-refusal-stop-hook.py", "FROM_NOW_ON_LINE"): LATER_PART,
    ("nc-systems/general-tools/checkout-freshness-changed-skill-invoke-again-refusal-stop-hook.py", "REFUSAL_INSTRUCTIONS_TEMPLATE"): LATER_PART,
    ("nc-systems/general-tools/checkout-freshness-changed-skill-invoke-again-refusal-stop-hook.py", "REFUSAL_REASON_TEMPLATE"): LATER_PART,
    ("nc-systems/general-tools/claude-code-bash-git-push-of-markdown-change-citation-checks-reminder-hook.py", "FAILURE_LINE_TEMPLATE"): HOOK_FAILED,
    ("nc-systems/general-tools/claude-code-bash-git-push-of-markdown-change-citation-checks-reminder-hook.py", "NOT_CHECKED_OUT_LINE_TEMPLATE"): LATER_PART,
    ("nc-systems/general-tools/pull-request-follow-up-request-from-merge-lane-2-message-save-and-forked-subagent-brief-hand-over-user-prompt-submit-hook.py", "NOT_SAVED_LINES"): HOOK_FAILED,
    ("nc-systems/general-tools/python-edit-changed-tool-message-to-agent-strings-check-reminder-hook.py", "FAST_READ_FILES_NOT_WRITTEN_TEMPLATE"): LATER_PART,
    ("nc-systems/general-tools/python-edit-changed-tool-message-to-agent-strings-check-reminder-hook.py", "FAST_READ_MESSAGE_TEMPLATE"): LATER_PART,
    ("nc-systems/general-tools/python-edit-changed-tool-message-to-agent-strings-check-reminder-hook.py", "FILE_DID_NOT_PARSE_MESSAGE_TEMPLATE"): HOOK_FAILED,
    ("nc-systems/general-tools/python-edit-changed-tool-message-to-agent-strings-check-reminder-hook.py", "LISTING_LINE_TEMPLATE"): LATER_PART,
    ("nc-systems/general-tools/python-edit-changed-tool-message-to-agent-strings-check-reminder-hook.py", "MORE_NOT_LISTED_LINE_TEMPLATE"): LATER_PART,
    ("nc-systems/general-tools/python-edit-changed-tool-message-to-agent-strings-check-reminder-hook.py", "NOT_INSPECTED_MESSAGE_TEMPLATE"): HOOK_FAILED,
    ("nc-systems/skills/emergency-stop/emergency-stop-file-shown-and-push-and-merge-refusal-hook.py", "UNREADABLE_LINE"): LATER_PART,
    ("nc-systems/skills/emergency-stop/emergency-stop-file-shown-and-push-and-merge-refusal-hook.py", "UNREAD_COMMAND_LINE"): LATER_PART,
    ("nc-systems/skills/walk-me-through/walk-me-through-agent-question-to-user-outside-approval-walk-items-refusal-stop-hook.py", "DECIDED_BY_MODEL_NOTICE"): LATER_PART,
    ("nc-systems/skills/walk-me-through/walk-me-through-agent-question-to-user-outside-approval-walk-items-refusal-stop-hook.py", "MODEL_CHECK_FAILED_NOTICE"): LATER_PART,
    ("nc-systems/skills/walk-me-through/walk-me-through-agent-question-to-user-outside-approval-walk-items-refusal-stop-hook.py", "MODEL_PROMPT_TEMPLATE"): NOT_A_RULE,
    ("nc-systems/skills/walk-me-through/walk-me-through-agent-question-to-user-outside-approval-walk-items-refusal-stop-hook.py", "NOT_LOGGED_NOTICE"): LATER_PART,
    ("nc-systems/skills/walk-me-through/walk-me-through-agent-question-to-user-outside-approval-walk-items-refusal-stop-hook.py", "NO_PAGE_TEMPLATE"): LATER_PART,
    ("nc-systems/skills/walk-me-through/walk-me-through-agent-question-to-user-outside-approval-walk-items-refusal-stop-hook.py", "NO_WALK_REFUSAL_INSTRUCTIONS"): LATER_PART,
    ("nc-systems/skills/walk-me-through/walk-me-through-agent-question-to-user-outside-approval-walk-items-refusal-stop-hook.py", "REFUSAL_INSTRUCTIONS"): LATER_PART,
    ("nc-systems/skills/walk-me-through/walk-me-through-agent-reply-to-user-not-ending-with-waiting-item-closing-line-refusal-stop-hook.py", "NO_DECISION_INSTRUCTIONS"): LATER_PART,
    ("nc-systems/skills/walk-me-through/walk-me-through-agent-reply-to-user-not-ending-with-waiting-item-closing-line-refusal-stop-hook.py", "OLD_MARKER_INSTRUCTIONS"): LATER_PART,
    ("nc-systems/skills/walk-me-through/walk-me-through-agent-reply-to-user-not-ending-with-waiting-item-closing-line-refusal-stop-hook.py", "REPLY_LACKS_CLOSING_LINE_INSTRUCTIONS"): LATER_PART,
    ("nc-systems/skills/walk-me-through/walk-me-through-agent-reply-to-user-not-ending-with-waiting-item-closing-line-refusal-stop-hook.py", "UNPUBLISHED_INSTRUCTIONS"): LATER_PART,
    ("nc-systems/skills/walk-me-through/walk-me-through-agent-reply-to-user-not-ending-with-waiting-item-closing-line-refusal-stop-hook.py", "UNUSABLE_INSTRUCTIONS"): LATER_PART,
    ("nc-systems/skills/walk-me-through/walk-me-through-pending-user-alerts-claim-and-insert-as-approval-walk-items-user-prompt-submit-hook.py", "ALERT_LINE"): LATER_PART,
    ("nc-systems/skills/walk-me-through/walk-me-through-pending-user-alerts-claim-and-insert-as-approval-walk-items-user-prompt-submit-hook.py", "CLAIM_FAILED_LINES"): HOOK_FAILED,
    ("nc-systems/skills/walk-me-through/walk-me-through-pending-user-alerts-claim-and-insert-as-approval-walk-items-user-prompt-submit-hook.py", "INSERTED_LINES"): LATER_PART,
    ("nc-systems/skills/walk-me-through/walk-me-through-pending-user-alerts-claim-and-insert-as-approval-walk-items-user-prompt-submit-hook.py", "INSERT_FAILED_LINES"): LATER_PART,
    ("nc-systems/skills/walk-me-through/walk-me-through-pending-user-alerts-claim-and-insert-as-approval-walk-items-user-prompt-submit-hook.py", "NO_WALK_LINES"): LATER_PART,
    ("nc-systems/skills/walk-me-through/walk-me-through-pending-user-alerts-claim-and-insert-as-approval-walk-items-user-prompt-submit-hook.py", "USER_ALERT_LINE"): LATER_PART,
    ("nc-systems/skills/walk-me-through/walk-me-through-pending-user-alerts-claim-and-insert-as-approval-walk-items-user-prompt-submit-hook.py", "WALK_OPEN_LINES"): LATER_PART,
    ("nc-systems/skills/walk-me-through/walk-me-through-pending-user-alerts-claim-and-insert-as-approval-walk-items-user-prompt-submit-hook.py", "WALK_UNKNOWN_LINE"): LATER_PART,
    ("nc-systems/skills/walk-me-through/walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook.py", "CONDITION_LINES"): LATER_PART,
    ("nc-systems/skills/walk-me-through/walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook.py", "ITEM_NOT_SHOWN_LINES"): LATER_PART,
    ("nc-systems/skills/walk-me-through/walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook.py", "ITEM_TEXT_UNREADABLE_LINES"): LATER_PART,
    ("nc-systems/skills/walk-me-through/walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook.py", "NEVER_SHOWN_REASON"): LATER_PART,
    ("nc-systems/skills/walk-me-through/walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook.py", "NUMBERED_ALL_NAMED_LINE"): LATER_PART,
    ("nc-systems/skills/walk-me-through/walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook.py", "NUMBERED_REFUSED_LINES"): LATER_PART,
    ("nc-systems/skills/walk-me-through/walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook.py", "NUMBERED_R_WAITING_ITEM_LINE"): LATER_PART,
    ("nc-systems/skills/walk-me-through/walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook.py", "NUMBERED_UNNAMED_LINE"): LATER_PART,
    ("nc-systems/skills/walk-me-through/walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook.py", "ONE_ITEM_AT_A_TIME_LINE"): LATER_PART,
    ("nc-systems/skills/walk-me-through/walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook.py", "PARTS_DIFFERENT_LETTERS_LINES"): LATER_PART,
    ("nc-systems/skills/walk-me-through/walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook.py", "PARTS_NOT_RECORDABLE_LINES"): LATER_PART,
    ("nc-systems/skills/walk-me-through/walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook.py", "PARTS_READ_LINE"): LATER_PART,
    ("nc-systems/skills/walk-me-through/walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook.py", "PARTS_REPEATED_LINES"): LATER_PART,
    ("nc-systems/skills/walk-me-through/walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook.py", "PARTS_SAME_LETTER_LINE"): LATER_PART,
    ("nc-systems/skills/walk-me-through/walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook.py", "PARTS_UNANSWERED_LINES"): LATER_PART,
    ("nc-systems/skills/walk-me-through/walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook.py", "RECOMMENDATION_UNKNOWN_LINE"): LATER_PART,
    ("nc-systems/skills/walk-me-through/walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook.py", "REPEAT_PAGE_LINE"): LATER_PART,
    ("nc-systems/skills/walk-me-through/walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook.py", "REPEAT_UNPUBLISHED_LINES"): LATER_PART,
    ("nc-systems/skills/walk-me-through/walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook.py", "RIDER_LINES"): LATER_PART,
    ("nc-systems/skills/walk-me-through/walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook.py", "SHOWN_DIFFERENT_REASON"): LATER_PART,
    ("nc-systems/skills/walk-me-through/walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook.py", "TRANSCRIPT_UNREADABLE_LINES"): LATER_PART,
    ("nc-systems/skills/walk-me-through/walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook.py", "USER_REPLY_LINE"): LATER_PART,
    ("scripts/agent-seat-due-task-prerequisites-recording-reminder-after-task-create-hook.py", "FAULT_LINE_TEMPLATE"): HOOK_FAILED,
    ("scripts/agent-seat-due-task-prerequisites-recording-reminder-after-task-create-hook.py", "TASK_ID_CLAUSE_TEMPLATE"): LATER_PART,
    ("scripts/agent-seat-due-task-raise-hook.py", "DEFER_INSTRUCTION"): LATER_PART,
    ("scripts/agent-seat-due-task-raise-hook.py", "NEXT_ACTION_HELD_TASKS_LINE"): LATER_PART,
    ("scripts/agent-seat-due-task-raise-hook.py", "NEXT_ACTION_MORE_LINE"): LATER_PART,
    ("scripts/agent-seat-due-task-raise-hook.py", "NEXT_ACTION_STOP_AGAIN_LINE"): LATER_PART,
    ("scripts/agent-seat-due-task-raise-hook.py", "PREREQUISITES_CORRECTION_INSTRUCTION"): LATER_PART,
    ("scripts/bare-number-citation-in-markdown-and-agent-reply-warning-hook.py", "EXCERPT_HIT_LINE"): LATER_PART,
    ("scripts/bare-number-citation-in-markdown-and-agent-reply-warning-hook.py", "EXCERPT_TITLE_HIT_LINE"): LATER_PART,
    ("scripts/bare-number-citation-in-markdown-and-agent-reply-warning-hook.py", "LINK_TITLES_RECHECK_GH_FAILED_MESSAGE_LINES"): COMMAND_MODE,
    ("scripts/bare-number-citation-in-markdown-and-agent-reply-warning-hook.py", "LINK_TITLES_RECHECK_NOTHING_TO_DO_LINE"): COMMAND_MODE,
    ("scripts/bare-number-citation-in-markdown-and-agent-reply-warning-hook.py", "LINK_TITLES_RECHECK_STOP_MEANS_ONLY_STOP_RERUNNING_LINE"): COMMAND_MODE,
    ("scripts/bare-number-citation-in-markdown-and-agent-reply-warning-hook.py", "LINK_TITLES_RECHECK_USAGE_LINES"): COMMAND_MODE,
    ("scripts/bare-number-citation-in-markdown-and-agent-reply-warning-hook.py", "MARKDOWN_WRONG_NUMBER_LINE"): LATER_PART,
    ("scripts/bare-number-citation-in-markdown-and-agent-reply-warning-hook.py", "MORE_HITS_LINE"): LATER_PART,
    ("scripts/bare-number-citation-in-markdown-and-agent-reply-warning-hook.py", "MORE_TITLE_HITS_LINE"): LATER_PART,
    ("scripts/bare-number-citation-in-markdown-and-agent-reply-warning-hook.py", "NOTE_RECORD_FAILED_LINE"): LATER_PART,
    ("scripts/bare-number-citation-in-markdown-and-agent-reply-warning-hook.py", "NO_CORRECTION_NOW_INSTRUCTION"): LATER_PART,
    ("scripts/bare-number-citation-in-markdown-and-agent-reply-warning-hook.py", "PREVIOUS_REPLY_WRONG_NUMBER_LINE"): LATER_PART,
    ("scripts/bare-number-citation-in-markdown-and-agent-reply-warning-hook.py", "TITLES_NOT_CHECKED_LINE"): HOOK_FAILED,
    ("scripts/bare-number-citation-in-markdown-and-agent-reply-warning-hook.py", "WRITE_HIT_LINE"): LATER_PART,
    ("scripts/bare-number-citation-in-markdown-and-agent-reply-warning-hook.py", "WRITE_TITLE_HIT_LINE"): LATER_PART,
    ("scripts/bare-number-citation-in-markdown-and-agent-reply-warning-hook.py", "WRONG_NUMBER_LINE_OPENING_INSTRUCTION"): LATER_PART,
    ("scripts/bare-number-citation-in-markdown-and-agent-reply-warning-hook.py", "WRONG_NUMBER_NOTE_TEMPLATE"): LATER_PART,
    ("scripts/bare-number-citation-in-markdown-and-agent-reply-warning-hook.py", "WRONG_NUMBER_TITLE_LINES_OVERRIDE_INSTRUCTION"): LATER_PART,
    ("scripts/checkout-freshness-catch-up.py", "AFTER_REBASE_ADVICE"): LATER_PART,
    ("scripts/checkout-freshness-catch-up.py", "DETACHED_FAST_FORWARD_REFUSED_LINES"): LATER_PART,
    ("scripts/checkout-freshness-catch-up.py", "DETACHED_MOVED_ADVICE"): LATER_PART,
    ("scripts/checkout-freshness-catch-up.py", "DETACHED_NOT_MOVED_ADVICE"): LATER_PART,
    ("scripts/checkout-freshness-catch-up.py", "DETACHED_OPERATION_IN_PROGRESS_LINE"): LATER_PART,
    ("scripts/checkout-freshness-catch-up.py", "DETACHED_WORK_OF_ITS_OWN_LINE"): LATER_PART,
    ("scripts/checkout-freshness-catch-up.py", "GIT_FAILED_CAUSE_LINE"): HOOK_FAILED,
    ("scripts/checkout-freshness-catch-up.py", "GIT_FAILED_NOTES_DELIVERY_AGENT_NEXT_STEP_LINES"): LATER_PART,
    ("scripts/checkout-freshness-catch-up.py", "GIT_FAILED_RERUN_NEXT_STEP_LINES"): LATER_PART,
    ("scripts/checkout-freshness-catch-up.py", "GIT_FAILED_STOP_HOOK_USER_NEXT_STEP_LINES"): LATER_PART,
    ("scripts/checkout-freshness-catch-up.py", "IGNORED_FILES_IN_THE_WAY_ADVICE"): LATER_PART,
    ("scripts/checkout-freshness-catch-up.py", "LEAVE_IT_ADVICE"): LATER_PART,
    ("scripts/checkout-freshness-catch-up.py", "NOTES_DID_NOT_FIT_LINE"): HOOK_FAILED,
    ("scripts/checkout-freshness-catch-up.py", "NOTES_NOT_CLEARED_LINE"): LATER_PART,
    ("scripts/checkout-freshness-catch-up.py", "NOTES_NOT_QUEUED_LINE"): LATER_PART,
    ("scripts/checkout-freshness-catch-up.py", "NOTES_UNREADABLE_LINE"): HOOK_FAILED,
    ("scripts/checkout-freshness-catch-up.py", "NOT_FOR_THE_USER_ADVICE"): LATER_PART,
    ("scripts/checkout-freshness-catch-up.py", "PUSHED_HISTORY_ADVICE"): LATER_PART,
    ("scripts/checkout-freshness-catch-up.py", "REBASE_ADVICE"): LATER_PART,
    ("scripts/checkout-freshness-catch-up.py", "SKILL_RELOAD_LINES"): LATER_PART,
    ("scripts/checkout-freshness-catch-up.py", "UNKNOWN_ADVICE"): LATER_PART,
    ("scripts/cold-read-fast-read-due-for-linked-document-reminder-hook.py", "REMINDER_INSTRUCTIONS"): LATER_PART,
    ("scripts/cold-read-fast-read-due-for-linked-document-reminder-hook.py", "SESSION_CHECKOUT_UNKNOWN_LINES"): HOOK_FAILED,
    ("scripts/cold-read-fast-read-due-for-linked-document-reminder-hook.py", "SESSION_CHECKOUT_UNKNOWN_STDERR_LINE"): HOOK_FAILED,
    ("scripts/cold-read-fast-read-due-for-linked-document-reminder-hook.py", "TRANSCRIPT_UNREADABLE_LINES"): HOOK_FAILED,
    ("scripts/cold-read-fast-read-due-for-linked-document-reminder-hook.py", "UNCHECKED_ALREADY_READ_NOTICE"): LATER_PART,
    ("scripts/cold-read-fast-read-due-for-linked-document-reminder-hook.py", "UNCHECKED_INSTRUCTION"): LATER_PART,
    ("scripts/cold-read-fast-read-due-for-linked-document-reminder-hook.py", "UNCHECKED_STDERR_LINE"): HOOK_FAILED,
    ("scripts/file-name-collision-warning-hook.py", "GIT_FAILURE_TEMPLATE"): HOOK_FAILED,
    ("scripts/handoff-context-threshold-hook.py", "MARKER_NOT_WRITTEN_LINE"): LATER_PART,
    ("scripts/handoff-context-threshold-hook.py", "MODEL_ID_NOT_IN_CONTEXT_WINDOW_TABLE_LINE"): LATER_PART,
    ("scripts/handoff-context-threshold-hook.py", "NEW_WORK_DURING_HANDOFF_DEFERRAL_INSTRUCTION"): LATER_PART,
    ("scripts/handoff-context-threshold-hook.py", "UNREADABLE_MARKER_REPLACED_LINE"): LATER_PART,
    ("scripts/markdown-edit-hard-wrapped-paragraph-reminder-hook-nbd.py", "PARSER_MISSING_BELOW_MINIMUM_PYTHON_MESSAGE"): HOOK_FAILED,
    ("scripts/markdown-edit-hard-wrapped-paragraph-reminder-hook-nbd.py", "PARSER_MISSING_MESSAGE"): HOOK_FAILED,
    ("scripts/ned-box-path-in-agent-reply-unclickable-on-mac-warning-hook.py", "FAULT_LINES"): HOOK_FAILED,
    ("scripts/ned-box-path-in-agent-reply-unclickable-on-mac-warning-hook.py", "HIT_LINE"): LATER_PART,
    ("scripts/ned-box-path-in-agent-reply-unclickable-on-mac-warning-hook.py", "MORE_HITS_LINE"): LATER_PART,
    ("scripts/ned-box-path-in-agent-reply-unclickable-on-mac-warning-hook.py", "NOTE_RECORD_FAILED_LINE"): LATER_PART,
    ("scripts/ned-box-path-in-agent-reply-unclickable-on-mac-warning-hook.py", "SUGGESTED_LINK_TEMPLATE"): LATER_PART,
    ("scripts/new-shared-names-reminder-hook.py", "FAILURE_TEMPLATE"): HOOK_FAILED,
    ("scripts/new-shared-names-reminder-hook.py", "GIT_FAILURE_TEMPLATE"): HOOK_FAILED,
    ("scripts/new-shared-names-reminder-hook.py", "MORE_NAMES_LINE"): LATER_PART,
    ("scripts/new-shared-names-reminder-hook.py", "RECORD_WRITE_FAILED_TEMPLATE"): HOOK_FAILED,
    ("scripts/new-shared-names-reminder-hook.py", "UNREADABLE_RECORD_MOVED_TEMPLATE"): HOOK_FAILED,
    ("scripts/new-shared-names-reminder-hook.py", "UNREADABLE_RECORD_NOT_MOVED_TEMPLATE"): HOOK_FAILED,
    ("scripts/obsolete-file-edit-warning-hook.py", "BEHIND_REMOTE_ADVICE"): LATER_PART,
    ("scripts/obsolete-file-edit-warning-hook.py", "BRANCH_STATE_UNKNOWN_LINE"): LATER_PART,
    ("scripts/obsolete-file-edit-warning-hook.py", "COMMIT_COUNT_FAILED_LINE"): LATER_PART,
    ("scripts/obsolete-file-edit-warning-hook.py", "DETACHED_HEAD_LINE"): LATER_PART,
    ("scripts/obsolete-file-edit-warning-hook.py", "DETACHED_PUSHED_HEAD_LINE"): LATER_PART,
    ("scripts/obsolete-file-edit-warning-hook.py", "DETACHED_PUSH_STATE_UNKNOWN_LINE"): LATER_PART,
    ("scripts/obsolete-file-edit-warning-hook.py", "DIVERGED_FROM_REMOTE_ADVICE"): LATER_PART,
    ("scripts/obsolete-file-edit-warning-hook.py", "GIT_FAILURE_CAUSE_LINE"): HOOK_FAILED,
    ("scripts/obsolete-file-edit-warning-hook.py", "GIT_OPERATION_IN_PROGRESS_LINE"): LATER_PART,
    ("scripts/obsolete-file-edit-warning-hook.py", "MAIN_CHECKOUT_ADVICE"): LATER_PART,
    ("scripts/obsolete-file-edit-warning-hook.py", "MAIN_COPY_UNREADABLE_LINE"): LATER_PART,
    ("scripts/obsolete-file-edit-warning-hook.py", "MAIN_DELETED_FILE_LINE"): LATER_PART,
    ("scripts/obsolete-file-edit-warning-hook.py", "MAIN_LOST_FILE_UNKNOWN_LINE"): LATER_PART,
    ("scripts/obsolete-file-edit-warning-hook.py", "MAIN_MOVED_AND_REWRITTEN_FILE_LINE"): LATER_PART,
    ("scripts/obsolete-file-edit-warning-hook.py", "MAIN_MOVED_AND_REWRITTEN_FILE_PUSHED_LINE"): LATER_PART,
    ("scripts/obsolete-file-edit-warning-hook.py", "MAIN_MOVED_FILE_LINE"): LATER_PART,
    ("scripts/obsolete-file-edit-warning-hook.py", "MAIN_MOVED_FILE_PUSHED_LINE"): LATER_PART,
    ("scripts/obsolete-file-edit-warning-hook.py", "NEVER_PUSHED_ADVICE"): LATER_PART,
    ("scripts/obsolete-file-edit-warning-hook.py", "NO_OVERLAP_LINE"): LATER_PART,
    ("scripts/obsolete-file-edit-warning-hook.py", "OVERLAP_LINE"): LATER_PART,
    ("scripts/obsolete-file-edit-warning-hook.py", "OVERLAP_UNKNOWN_LINE"): LATER_PART,
    ("scripts/obsolete-file-edit-warning-hook.py", "PUSHED_ADVICE"): LATER_PART,
    ("scripts/obsolete-file-edit-warning-hook.py", "PUSHED_NO_OVERLAP_LINE"): LATER_PART,
    ("scripts/obsolete-file-edit-warning-hook.py", "PUSHED_OVERLAP_LINE"): LATER_PART,
    ("scripts/obsolete-file-edit-warning-hook.py", "RECORD_WRITE_FAILED_LINE"): LATER_PART,
    ("scripts/post-compaction-session-continues-hook.py", "FAULT_LINE"): LATER_PART,
    ("scripts/post-compaction-session-continues-hook.py", "MARKER_PATH_NOT_CLEARED_INSTRUCTION"): LATER_PART,
    ("scripts/post-compaction-session-continues-hook.py", "MARKER_PATH_UNKNOWN_INSTRUCTION"): LATER_PART,
    ("scripts/style-guide-word-checker-markdown-edit-hook-nbd.py", "EDIT_HIT_LINE"): LATER_PART,
    ("scripts/style-guide-word-checker-markdown-edit-hook-nbd.py", "HIT_LINE"): LATER_PART,
    ("scripts/style-guide-word-checker-markdown-edit-hook-nbd.py", "MORE_HITS_LINE"): LATER_PART,
    ("scripts/uncommitted-work-snapshot-hook.py", "NOT_PROTECTED_MESSAGE"): HOOK_FAILED,
    ("scripts/uncommitted-work-snapshot-hook.py", "OWNER_FILE_NOT_WRITTEN_MESSAGE"): HOOK_FAILED,
}

# Hook path: why the hook prints no message for a rule.
HOOKS_THAT_PRINT_NO_RULE_MESSAGE = {
    "nc-systems/general-tools/agent-seat-worktree-create-with-owner-file-claude-code-worktree-create-hook.py": "prints only the worktree path Claude Code reads, or its own failure",
    "scripts/uncommitted-work-snapshot-hook.py": "it speaks only when it could not keep a work-snapshot or write a worktree's owner file, which reports its own failure",
}

# (hook path, rule ID): every message constant of that hook the ID opens, when it opens
# more than one; each is a variant of the one rule's message.
MESSAGE_VARIANTS_OF_ONE_RULE = {
    (".claude/guard-hooks/claude-code-tmux-kill-server-and-kill-session-missing-server-selection-refusal-hook.py", "bash-guard-tmux-kill-without-socket-option"): {"REFUSAL_WITHOUT_COMMAND_MESSAGE", "REFUSAL_WITH_COMMAND_TEMPLATE"},
    (".claude/guard-hooks/force-push-with-open-pull-request-guard-hook.py", "bash-guard-git-push-force"): {"DENY_REASON_TEMPLATE", "UNRESOLVED_REASON_TEMPLATE"},
    (".claude/guard-hooks/ghi-issue-write-hand-typed-gh-command-refusal.py", "bash-guard-gh-issue-body-or-title-set-by-hand"): {"EDIT_BODY_REFUSAL", "EDIT_TITLE_REFUSAL"},
    (".claude/guard-hooks/ghi-issue-write-hand-typed-gh-command-refusal.py", "bash-guard-gh-issue-comment"): {"CLOSE_WITH_COMMENT_REFUSAL", "COMMENT_REFUSAL", "NO_COMMENTS_LINE", "REOPEN_WITH_COMMENT_REFUSAL"},
    (".claude/guard-hooks/git-worktree-remove-cold-read-record-and-sanity-check-record-ship-to-log-store-first-guard-hook.py", "bash-guard-git-worktree-remove-record-being-written"): {"RECORD_BEING_WRITTEN_IN_REMOVED_WORKTREE_REFUSAL_TEMPLATE", "REMOVED_WORKTREE_UNRESOLVED_REFUSAL_TEMPLATE"},
    (".claude/guard-hooks/guarded-file-unapproved-change-afterward-backup-and-ask-hook.py", "guarded-file-changed-without-approval-ask-user-afterward"): {"ASK_HEADER_LINE", "UNAPPROVED_VERSION_REMINDER_MESSAGE"},
    (".claude/guard-hooks/handoff-deferral-cold-read-full-run-launch-refusal-hook.py", "bash-guard-cold-read-full-run-during-handoff-deferral"): {"COLD_READ_FULL_RUN_REFUSED_AND_SAVED_REASON", "COLD_READ_FULL_RUN_REFUSED_NOT_SAVED_REASON"},
    (".claude/guard-hooks/instruction-file-guard.py", "write-guard-claude-code-memory-directory-write"): {"MAIN_AGENT_MEMORY_WRITE_DENY_MESSAGE", "SUBAGENT_MEMORY_WRITE_DENY_MESSAGE"},
    (".claude/guard-hooks/instruction-file-guard.py", "write-guard-guarded-file-edit-needs-approval-marker"): {"DENY_MESSAGE", "MISSING_SESSION_DIRECTORY_DENY_MESSAGE", "PRE_APPROVED_CHANGE_MARKER_WITHOUT_REASON_DENY_MESSAGE", "REUSABLE_PROMPT_DENY_MESSAGE", "REVIEWED_DOCUMENT_DENY_MESSAGE"},
    (".claude/guard-hooks/search-file-argument-read-as-option-guard-hook.py", "bash-guard-search-file-name-read-as-option"): {"REFUSAL_OF_OPTION_VALUE_TEMPLATE", "REFUSAL_WITHOUT_COMMAND_TEMPLATE", "REFUSAL_WITH_COMMAND_TEMPLATE"},
    (".claude/guard-hooks/session-location-write-guard.py", "write-guard-checkout-without-branch"): {"DETACHED_DENY_MESSAGE", "UNBORN_DENY_MESSAGE"},
    (".claude/guard-hooks/session-location-write-guard.py", "write-guard-reference-checkout-write"): {"CROSS_REFERENCE_DENY_MESSAGE", "REFERENCE_DENY_MESSAGE"},
    (".claude/guard-hooks/synthetic-keystroke-guard-hook.py", "bash-guard-tmux-keys-into-attached-session"): {"ATTACHED_REASON", "NESTED_SSH_REASON", "NO_TARGET_REASON", "UNRESOLVED_TARGET_REASON", "UNVERIFIED_REASON"},
    ("nc-systems/general-tools/pull-request-follow-up-request-from-merge-lane-2-message-save-and-forked-subagent-brief-hand-over-user-prompt-submit-hook.py", "pull-request-follow-up-request-brief-handed-to-author"): {"FOLLOW_UP_BRIEF_OPENING_LINE", "UNREADABLE_BLOCK_LINES"},
    ("nc-systems/skills/emergency-stop/emergency-stop-file-shown-and-push-and-merge-refusal-hook.py", "emergency-stop-state-shown-to-every-agent-session"): {"IN_FORCE_RULES_NOTICE", "LIFTED_NOTICE"},
    ("nc-systems/skills/walk-me-through/walk-me-through-agent-reply-to-user-not-ending-with-waiting-item-closing-line-refusal-stop-hook.py", "walk-me-through-reply-ends-with-waiting-item-closing-line"): {"REPLY_LACKS_CLOSING_LINE_OPENING_TEMPLATE", "UNPUBLISHED_OPENING_TEMPLATE", "UNUSABLE_OPENING_TEMPLATE"},
    ("nc-systems/skills/walk-me-through/walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook.py", "walk-me-through-short-answer-expanded-into-instructions"): {"NO_WALK_OPENING_LINE", "OPEN_WALK_OPENING_LINE", "WALK_UNKNOWN_OPENING_LINE"},
    ("scripts/absence-claim-locator-reminder-hook.py", "absence-claim-run-locator-before-saying-missing"): {"REMINDER_TEMPLATE", "SUBAGENT_REMINDER_TEMPLATE"},
    ("scripts/bare-number-citation-in-markdown-and-agent-reply-warning-hook.py", "bare-number-pull-request-ghi-or-task-citation-in-markdown-and-reply-warning"): {"MARKDOWN_OPENING_LINES", "PREVIOUS_REPLY_OPENING_LINES", "PREVIOUS_REPLY_SHORT_OPENING_LINES"},
    ("scripts/bare-number-citation-in-markdown-and-agent-reply-warning-hook.py", "github-link-text-not-matching-item-title-warning"): {"MARKDOWN_TITLE_OPENING_LINES", "PREVIOUS_REPLY_TITLE_OPENING_LINES"},
    ("scripts/checkout-freshness-catch-up.py", "checkout-freshness-branch-behind-main-update"): {"BEHIND_MAIN_HEADING_TEMPLATE", "REBASED_ONTO_MAIN_TEMPLATE"},
    ("scripts/checkout-freshness-catch-up.py", "checkout-freshness-changed-instructions-read-again"): {"CLAUDE_MD_CHANGED_NOTICE", "CLAUDE_MD_CHANGED_SHORT_NOTICE", "CLAUDE_MD_CHANGE_UNREADABLE_NOTICE", "INSTRUCTION_FILE_CHANGED_NOTICE", "MOVED_WITHOUT_LIST_NOTICE", "STANDING_INSTRUCTION_DELETED_NOTICE"},
    ("scripts/handoff-context-threshold-hook.py", "handoff-context-threshold-deferred-while-work-runs"): {"HANDOFF_DEFERRED_NOTICE", "HANDOFF_DEFERRED_UNKNOWN_COUNT_NOTICE"},
}

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def message_constants(module):
    """{constant name: its text} for the module's message constants: names in capitals with a
    tool-message-to-agent suffix, holding a string or a tuple or list of strings."""
    texts = {}
    for name, value in vars(module).items():
        if not (name.isupper() and collector.variable_name_has_tool_message_to_agent_suffix(name)):
            continue
        if isinstance(value, str):
            texts[name] = value
        elif isinstance(value, (tuple, list)) and value and all(isinstance(part, str) for part in value):
            texts[name] = "\n".join(value)
    return texts


def unlisted_shared_rule_ids(relative_path, constants_of_each_opening_id, variants):
    """[(rule ID, constants it opens, constants listed for it)] for each ID that opens more than
    one message constant of the hook other than exactly as `variants` lists it."""
    return [(rule_id, sorted(names), sorted(variants.get((relative_path, rule_id), set())))
            for rule_id, names in sorted(constants_of_each_opening_id.items())
            if len(names) > 1 and set(names) != variants.get((relative_path, rule_id))]


check("an ID opening two constants as listed is one rule's variants",
      unlisted_shared_rule_ids("h.py", {"r": ["A_MESSAGE", "B_MESSAGE"], "s": ["C_MESSAGE"]},
                               {("h.py", "r"): {"A_MESSAGE", "B_MESSAGE"}}) == [])
check("a second rule's message given an existing ID fails",
      unlisted_shared_rule_ids("h.py", {"r": ["A_MESSAGE", "B_MESSAGE", "C_MESSAGE"]},
                               {("h.py", "r"): {"A_MESSAGE", "B_MESSAGE"}})
      == [("r", ["A_MESSAGE", "B_MESSAGE", "C_MESSAGE"], ["A_MESSAGE", "B_MESSAGE"])])
check("an ID opening two unlisted constants fails",
      unlisted_shared_rule_ids("h.py", {"r": ["A_MESSAGE", "B_MESSAGE"]}, {})
      == [("r", ["A_MESSAGE", "B_MESSAGE"], [])])

# The pattern, on texts whose answer is known.
for text, expected in (("[rule bash-guard-git-push-force] Refused on purpose", "bash-guard-git-push-force"),
                       ("[rule a1-b2] x", "a1-b2"),
                       ("[rule stop] x", "stop"),
                       ("Refused [rule bash-guard-git-push-force] x", None),
                       ("[rule Bash-guard] x", None),
                       ("[rule bash_guard] x", None),
                       ("[rule bash-guard]x", None),
                       ("[rule -bash] x", None),
                       ("[rule bash-] x", None),
                       ("[rule ] x", None)):
    check(f"rule ID at the opening of {text!r} is {expected!r}", rule_ids.rule_id_at_message_start(text) == expected,
          rule_ids.rule_id_at_message_start(text))
check("a malformed [rule is found in source",
      [text for _, text in rule_ids.malformed_rule_ids_in_source('X = "[rule Bad_id] y"\nY = "[rule ok-id] z"\n')]
      == ["[rule Bad_id]"],
      rule_ids.malformed_rule_ids_in_source('X = "[rule Bad_id] y"\nY = "[rule ok-id] z"\n'))
check("a regular expression matching a rule ID is neither a rule ID nor a malformed one",
      rule_ids.malformed_rule_ids_in_source('P = re.compile(r"\\[rule [a-z0-9-]+\\] ")\n') == []
      and rule_ids.rule_ids_in_source('P = re.compile(r"\\[rule [a-z0-9-]+\\] ")\n') == {},
      rule_ids.malformed_rule_ids_in_source('P = re.compile(r"\\[rule [a-z0-9-]+\\] ")\n'))
check("rule IDs are found with their lines",
      rule_ids.rule_ids_in_source('A = "[rule one] x"\n\nB = ("[rule two] y "\n     "[rule one] z")\n')
      == {"one": [1, 4], "two": [3]},
      rule_ids.rule_ids_in_source('A = "[rule one] x"\n\nB = ("[rule two] y "\n     "[rule one] z")\n'))

probe = type(sys)("probe")
probe.REFUSAL_MESSAGE = "[rule probe-rule] Refused"
probe.OPENING_LINES = ("[rule probe-rule] first", "second")
probe.BUDGET_SECONDS = 5
probe.lower_message = "not a constant"
probe.REFUSAL = "a bare name with no suffix"
check("message constants are the capitalized names with a suffix, a tuple's items joined",
      message_constants(probe) == {"REFUSAL_MESSAGE": "[rule probe-rule] Refused",
                                   "OPENING_LINES": "[rule probe-rule] first\nsecond"},
      message_constants(probe))

hook_paths = rule_ids.registered_hook_paths(SETTINGS)
check(".claude/settings.json registers hooks for this suite to read", len(hook_paths) > 5, hook_paths)

files_of_each_rule_id = {}
constants_seen = set()
variant_groups_seen = set()
for relative_path in hook_paths:
    source = (REPOSITORY / relative_path).read_text(encoding="utf-8")
    try:
        module = load_by_path("registered_hook_" + re.sub(r"\W", "_", relative_path), REPOSITORY / relative_path)
    except Exception as error:
        check(f"{relative_path} loads", False, f"{type(error).__name__}: {error}")
        continue
    constants_of_each_opening_id = {}
    for name, text in sorted(message_constants(module).items()):
        constants_seen.add((relative_path, name))
        opening_id = rule_ids.rule_id_at_message_start(text)
        listed = (relative_path, name) in CONSTANTS_THAT_OPEN_NO_RULE_MESSAGE
        if opening_id:
            constants_of_each_opening_id.setdefault(opening_id, []).append(name)
            variant_groups_seen.add((relative_path, opening_id))
            check(f"{relative_path} {name} starts with a rule ID and is not also listed as opening none",
                  not listed, CONSTANTS_THAT_OPEN_NO_RULE_MESSAGE.get((relative_path, name)))
        else:
            check(f"{relative_path} {name} starts with a rule ID, or is listed as opening no rule's message",
                  listed, f"its text starts {text[:80]!r}; start it with `[rule <id>] `, or, when it opens "
                          f"no message for a rule, add it to CONSTANTS_THAT_OPEN_NO_RULE_MESSAGE with the reason")
    opening_ids = set(constants_of_each_opening_id)
    check(f"{relative_path}: two rules never share an ID; an ID opening several message constants is "
          f"listed in MESSAGE_VARIANTS_OF_ONE_RULE with exactly those constants",
          not unlisted_shared_rule_ids(relative_path, constants_of_each_opening_id, MESSAGE_VARIANTS_OF_ONE_RULE),
          "(rule ID, constants it opens, constants listed): "
          f"{unlisted_shared_rule_ids(relative_path, constants_of_each_opening_id, MESSAGE_VARIANTS_OF_ONE_RULE)}; "
          "give a different rule its own ID, or, when the constants are variants of one rule's message, "
          "list them for the ID in MESSAGE_VARIANTS_OF_ONE_RULE")
    check(f"{relative_path} writes every `[rule` as a well-formed rule ID",
          rule_ids.malformed_rule_ids_in_source(source) == [], rule_ids.malformed_rule_ids_in_source(source))
    source_ids = rule_ids.rule_ids_in_source(source)
    for rule_id in source_ids:
        files_of_each_rule_id.setdefault(rule_id, []).append(relative_path)
    check(f"{relative_path}: each rule ID it writes opens one of its message constants",
          set(source_ids) <= opening_ids, sorted(set(source_ids) - opening_ids))
    if relative_path in HOOKS_THAT_PRINT_NO_RULE_MESSAGE:
        check(f"{relative_path} is listed as printing no rule's message and writes no rule ID",
              not source_ids, sorted(source_ids))
    else:
        check(f"{relative_path} has a rule ID, or is listed as printing no rule's message",
              bool(source_ids), "no `[rule <id>]` in its source")

for rule_id, paths in sorted(files_of_each_rule_id.items()):
    check(f"rule ID {rule_id} is written in one registered hook only", len(paths) == 1, paths)

for relative_path, name in sorted(CONSTANTS_THAT_OPEN_NO_RULE_MESSAGE):
    check(f"listed constant {relative_path} {name} is a message constant of a registered hook",
          (relative_path, name) in constants_seen, "remove the stale entry")
for relative_path, rule_id in sorted(MESSAGE_VARIANTS_OF_ONE_RULE):
    check(f"listed variants of {rule_id} in {relative_path} are a rule ID of a registered hook",
          (relative_path, rule_id) in variant_groups_seen, "remove the stale entry")
for relative_path in sorted(HOOKS_THAT_PRINT_NO_RULE_MESSAGE):
    check(f"listed hook {relative_path} is registered", relative_path in hook_paths, "remove the stale entry")

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
