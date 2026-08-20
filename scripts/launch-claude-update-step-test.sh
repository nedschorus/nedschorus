#!/bin/sh
# Tests for the launchers' update-at-launch step (nedschorus#62): every
# launch checks for an update first, a hanging or failing update warns and
# never blocks the launch, and the ubuntu twin carries the same step inside
# its box-side command. Every external binary the step touches is stubbed
# onto PATH, so no seat, session, or update actually happens.
set -u

SCRIPT_DIRECTORY=$(cd "$(dirname "$0")" && pwd)
FAILURES=0

check() {
    name="$1"; shift
    if [ "$1" -eq 0 ]; then echo "PASS  $name"; else echo "FAIL  $name"; FAILURES=$((FAILURES + 1)); fi
}

WORKSPACE=$(mktemp -d)
trap 'rm -rf "$WORKSPACE"' EXIT
STUBS="$WORKSPACE/stubs"
mkdir -p "$STUBS" "$WORKSPACE/home" "$WORKSPACE/agents"

# Stubs. `claude update` behavior comes from CLAUDE_UPDATE_MODE: hang, fail,
# or ok — each leaves a marker so a test can assert whether update ran.
cat > "$STUBS/claude" << 'EOF'
#!/bin/sh
[ "${1:-}" = "update" ] || exit 0
touch "${CLAUDE_UPDATE_MARKER:?}"
case "${CLAUDE_UPDATE_MODE:-ok}" in
    (hang) sleep 600 ;;
    (fail) exit 1 ;;
    (ok) echo "stub: up to date" ;;
esac
EOF
cat > "$STUBS/tmux" << 'EOF'
#!/bin/sh
echo "tmux $*" >> "${TMUX_CALL_LOG:?}"
exit 0
EOF
cat > "$STUBS/git" << 'EOF'
#!/bin/sh
exit 0
EOF
chmod +x "$STUBS/claude" "$STUBS/tmux" "$STUBS/git"

run_mac_launcher() {
    update_mode="$1"; label="$2"
    CLAUDE_UPDATE_MARKER="$WORKSPACE/update-ran-$label"
    TMUX_CALL_LOG="$WORKSPACE/tmux-calls-$label"
    : > "$TMUX_CALL_LOG"
    HOME="$WORKSPACE/home" NEDSCHORUS_AGENTS_ROOT="$WORKSPACE/agents" \
        PATH="$STUBS:$PATH" \
        CLAUDE_UPDATE_MARKER="$CLAUDE_UPDATE_MARKER" CLAUDE_UPDATE_MODE="$update_mode" \
        TMUX_CALL_LOG="$TMUX_CALL_LOG" LAUNCH_CLAUDE_UPDATE_TIMEOUT_SECONDS=2 \
        sh "$SCRIPT_DIRECTORY/launch-claude-mac" "seat-$label" --no-attach \
        > "$WORKSPACE/out-$label" 2> "$WORKSPACE/err-$label"
    echo $?
}

# A HANGING update: the launch must still complete, fast, with the warning
# on stderr.
start=$(date +%s)
status=$(run_mac_launcher hang hangcase)
elapsed=$(( $(date +%s) - start ))
check "a hanging update does not block the launch" "$([ "$status" -eq 0 ]; echo $?)"
check "the hang is cut off by the timeout, not waited out" "$([ "$elapsed" -lt 15 ]; echo $?)"
grep -q "failed or timed out" "$WORKSPACE/err-hangcase"; check "the hang warns on stderr" $?
grep -q "new-session" "$WORKSPACE/tmux-calls-hangcase"; check "the seat is still created after the hang" $?

# A FAILING update: warn and proceed.
status=$(run_mac_launcher fail failcase)
check "a failing update does not block the launch" "$([ "$status" -eq 0 ]; echo $?)"
grep -q "failed or timed out" "$WORKSPACE/err-failcase"; check "the failure warns on stderr" $?

# A WORKING update: it runs on every launch, before the seat is created.
status=$(run_mac_launcher ok okcase)
check "a working update still launches" "$([ "$status" -eq 0 ]; echo $?)"
check "every launch invokes claude update" "$([ -f "$WORKSPACE/update-ran-okcase" ]; echo $?)"

# The ubuntu twin: its box-side command carries the same step, update before
# seat creation. Asserted on the command string it hands ssh, with ssh
# stubbed to print rather than connect.
cat > "$STUBS/ssh" << 'EOF'
#!/bin/sh
while [ $# -gt 1 ]; do shift; done
printf '%s\n' "$1"
EOF
chmod +x "$STUBS/ssh"
PATH="$STUBS:$PATH" sh "$SCRIPT_DIRECTORY/launch-claude-ubuntu" seatub --no-attach > "$WORKSPACE/out-ubuntu" 2>&1
box_command=$(cat "$WORKSPACE/out-ubuntu")
case "$box_command" in
    (*"claude update"*mkdir*) check "ubuntu box command updates, then prepares the seat" 0 ;;
    (*) check "ubuntu box command updates, then prepares the seat" 1 ;;
esac
case "$box_command" in
    (*"failed or timed out"*) check "ubuntu box command carries the warn-and-proceed branch" 0 ;;
    (*) check "ubuntu box command carries the warn-and-proceed branch" 1 ;;
esac

# The after-exit prompt, both twins. When a supervisor exits, its shell offers
# the operator a choice, and the ordering is load-bearing: `claude --continue`
# runs but starts NO supervisor, so the seat it resumes can never recycle. It
# was listed first until 2026-08-19, and on 2026-08-18 two seats ran
# unsupervised for about 25 hours because it was the only listed option that
# worked (nedschorus#45). Asserted on the emitted command text of both
# launchers -- the box twin's shell text only ever exists as the string it
# hands ssh, so the string is the only place the box's prompt can be checked
# from this Mac.
assert_supervised_option_is_first() {
    twin_name="$1"
    # Collapse to one line first: these command strings span several lines, and
    # a per-line index would compare offsets within different lines.
    emitted=$(printf '%s' "$2" | tr '\n' ' ')
    supervised_position=$(awk -v haystack="$emitted" \
        'BEGIN { print index(haystack, "fresh supervised seat") }')
    continue_position=$(awk -v haystack="$emitted" \
        'BEGIN { print index(haystack, "resume this dialog") }')
    if [ "$supervised_position" -gt 0 ] && [ "$continue_position" -gt 0 ] \
       && [ "$supervised_position" -lt "$continue_position" ]; then
        check "$twin_name lists the supervised relaunch before claude --continue" 0
    else
        check "$twin_name lists the supervised relaunch before claude --continue" 1
    fi
    case "$emitted" in
        (*"never recycle"*) check "$twin_name states what claude --continue costs" 0 ;;
        (*) check "$twin_name states what claude --continue costs" 1 ;;
    esac
}

# The ATTACHED form is the one to inspect: a --no-attach seat deliberately keeps
# close-on-exit and never reaches the after-exit shell, so its box command
# carries no prompt at all. Asserting on the detached string would pass an empty
# haystack for a prompt that does not exist there.
PATH="$STUBS:$PATH" sh "$SCRIPT_DIRECTORY/launch-claude-ubuntu" seatub \
    > "$WORKSPACE/out-ubuntu-attached" 2>&1
assert_supervised_option_is_first "ubuntu box command" "$(cat "$WORKSPACE/out-ubuntu-attached")"

# The Mac twin's prompt rides in the command it hands tmux, which the tmux stub
# logs. --no-attach never reaches the after-exit shell (a detached seat keeps
# close-on-exit), so the attached form is the one to inspect; the tmux stub
# returns immediately rather than seating anything.
: > "$WORKSPACE/tmux-calls-afterexit"
TMUX_CALL_LOG="$WORKSPACE/tmux-calls-afterexit" \
CLAUDE_UPDATE_MARKER="$WORKSPACE/update-ran-afterexit" \
NEDSCHORUS_AGENTS_ROOT="$WORKSPACE/agents" \
PATH="$STUBS:$PATH" sh "$SCRIPT_DIRECTORY/launch-claude-mac" seatprompt \
    > "$WORKSPACE/out-mac-prompt" 2>&1
assert_supervised_option_is_first "mac tmux command" "$(cat "$WORKSPACE/tmux-calls-afterexit")"

echo
if [ "$FAILURES" -gt 0 ]; then echo "$FAILURES case(s) failed"; exit 1; fi
echo "all cases passed"
