#!/usr/bin/env python3
"""Build the --settings JSON for a headless `claude -p` run, new or resumed, with the advisor turned off.

The user-wide ~/.claude/settings.json turns the advisor tool on, and a run started with
--settings '{"advisorModel": ""}' has none. Every program that starts `claude -p` builds its
--settings here; nc-systems/general-tools/tests/claude-headless-run-settings-with-advisor-turned-off-common-test.py
fails for one that does not.

Load by path with importlib.util under the module name
claude_headless_run_settings_with_advisor_turned_off_common.
"""

import json

ADVISOR_TURNED_OFF_SETTINGS = {"advisorModel": ""}


def claude_headless_run_settings_json_with_advisor_turned_off(own_settings=None) -> str:
    return json.dumps({**(own_settings or {}), **ADVISOR_TURNED_OFF_SETTINGS})
