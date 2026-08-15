#!/bin/sh
# Tests for the launchers' update-at-launch step (nedschorus#62): updating
# happens only on a machine with no live claude sessions, a hanging or
# failing update warns and never blocks the launch, and the ubuntu twin
# carries the same guarded step inside its box-side command. Every external
# binary the step touches is stubbed onto PATH, so no seat, session, or
# update actually happens.
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
printf '#!/bin/sh\nexit %s\n' 1 > "$STUBS/pgrep-quiet"
printf '#!/bin/sh\nexit %s\n' 0 > "$STUBS/pgrep-busy"
chmod +x "$STUBS/claude" "$STUBS/tmux" "$STUBS/git" "$STUBS/pgrep-quiet" "$STUBS/pgrep-busy"

run_mac_launcher() {
    pgrep_mode="$1"; update_mode="$2"; label="$3"
    cp "$STUBS/pgrep-$pgrep_mode" "$STUBS/pgrep"
    chmod +x "$STUBS/pgrep"
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

# A quiet machine with a HANGING update: the launch must still complete, fast,
# with the warning on stderr.
start=$(date +%s)
status=$(run_mac_launcher quiet hang hangcase)
elapsed=$(( $(date +%s) - start ))
check "a hanging update does not block the launch" "$([ "$status" -eq 0 ]; echo $?)"
check "the hang is cut off by the timeout, not waited out" "$([ "$elapsed" -lt 15 ]; echo $?)"
grep -q "failed or timed out" "$WORKSPACE/err-hangcase"; check "the hang warns on stderr" $?
grep -q "new-session" "$WORKSPACE/tmux-calls-hangcase"; check "the seat is still created after the hang" $?

# A quiet machine with a FAILING update: warn and proceed.
status=$(run_mac_launcher quiet fail failcase)
check "a failing update does not block the launch" "$([ "$status" -eq 0 ]; echo $?)"
grep -q "failed or timed out" "$WORKSPACE/err-failcase"; check "the failure warns on stderr" $?

# A BUSY machine: the update must not run at all — swapping the version under
# live sessions is the exact killer this step exists to prevent.
status=$(run_mac_launcher busy ok busycase)
check "a busy machine still launches" "$([ "$status" -eq 0 ]; echo $?)"
check "a busy machine never invokes claude update" "$([ ! -f "$WORKSPACE/update-ran-busycase" ]; echo $?)"
grep -q "skipping the update check" "$WORKSPACE/out-busycase"; check "the busy skip says why" $?

# A quiet machine with a WORKING update: it runs before the seat is created.
status=$(run_mac_launcher quiet ok okcase)
check "a working update still launches" "$([ "$status" -eq 0 ]; echo $?)"
check "a quiet machine does invoke claude update" "$([ -f "$WORKSPACE/update-ran-okcase" ]; echo $?)"

# The ubuntu twin: its box-side command carries the same guarded step, update
# before seat creation. Asserted on the command string it hands ssh, with ssh
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
    (*"pgrep -x claude"*"claude update"*mkdir*) check "ubuntu box command guards, updates, then prepares the seat" 0 ;;
    (*) check "ubuntu box command guards, updates, then prepares the seat" 1 ;;
esac
case "$box_command" in
    (*"failed or timed out"*) check "ubuntu box command carries the warn-and-proceed branch" 0 ;;
    (*) check "ubuntu box command carries the warn-and-proceed branch" 1 ;;
esac

echo
if [ "$FAILURES" -gt 0 ]; then echo "$FAILURES case(s) failed"; exit 1; fi
echo "all cases passed"
