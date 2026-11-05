"""The session-handoff's field names, shared by the program that writes it and every program that reads it.

handoff-write-and-check-supervisor.py writes a session-handoff as `key: value` lines,
and handoff-supervisor.py's parse_handoff_file reads them back; renaming a field is
an edit here. A reader that must still accept a retired name takes it from the
LEGACY_ names below.
"""

WRITTEN_AT_FIELD = "written-at"
NEXT_STEP_FIELD = "next-step"
SESSION_HANDOFF_SEQUENCE_NUMBER_FIELD = "session-handoff-sequence-number"
# Session-handoffs written before the rename carry only this name, and the writer still writes it beside the new one for handoff-supervisors running pre-rename code; readers accept it until none is left on either machine.
LEGACY_RESTART_COUNTER_FIELD = "restart-counter"
WRITTEN_IN_FIELD = "written-in"
WRITTEN_BY_SESSION_FIELD = "written-by-session"
DONT_RESTART_FIELD = "dont-restart"
# Numbered by the writer, because the reader keeps only a key's first occurrence.
SPAWNED_SUBAGENT_FIELD_PREFIX = "spawned-subagent-"
NEXT_STEP_VERBATIM_FIELD = "next-step-verbatim"
NEXT_STEP_BLOCK_OPENING_MARKER = "<<END-OF-NEXT-STEP"
NEXT_STEP_BLOCK_TERMINATOR = "END-OF-NEXT-STEP"
# Set by the reader, never written: the verbatim block had no terminator.
NEXT_STEP_BLOCK_UNTERMINATED_FIELD = "next-step-verbatim-unterminated"
