#!/bin/bash
# Test the application with forwarded serial data from target device
# Usage: ./test-with-forwarded-serial.sh <target_host> [target_user] [target_password]

TARGET_HOST="${1:-}"
TARGET_USER="${2:-fio}"
TARGET_PASSWORD="${3:-fio}"

if [ -z "$TARGET_HOST" ]; then
    echo "Usage: $0 <target_host> [target_user] [target_password]"
    echo "Example: $0 192.168.2.218 fio fio"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Testing with Forwarded UWB Serial Data ==="
echo "Target: $TARGET_USER@$TARGET_HOST"
echo ""

# Start forwarding in background
echo "[1/4] Starting serial forwarding..."
"$SCRIPT_DIR/forward-uwb-simple.sh" "$TARGET_HOST" "$TARGET_USER" "$TARGET_PASSWORD" > /tmp/uwb-forward.log 2>&1 &
FORWARD_PID=$!

# Wait for forwarding to establish
sleep 3

# Find the PTY
ACTUAL_PTY=$(find /tmp -name "uwb-*" -type l 2>/dev/null | head -1)

if [ -z "$ACTUAL_PTY" ] || [ ! -e "$ACTUAL_PTY" ]; then
    echo "✗ Failed to create local PTY"
    echo "Check /tmp/uwb-forward.log for details"
    kill $FORWARD_PID 2>/dev/null
    exit 1
fi

echo "✓ Using local device: $ACTUAL_PTY"
echo ""

# Run the application
echo "[2/4] Starting UWB MQTT Publisher..."
echo ""

cd "$PROJECT_DIR"
python3 src/mqtt-live-publisher.py "$ACTUAL_PTY" \
    --disable-mqtt \
    --verbose \
    --cga-format \
    --anchor-config config/uwb_anchors_hw_lab.json \
    --dev-eui-mapping config/dev_eui_to_uwb_mappings.json \
    --enable-lora-cache \
    --lora-broker localhost \
    --lora-port 1883 \
    --lora-username test \
    --lora-password test \
    --lora-topic "#" \
    --enable-validation \
    --enable-confidence-scoring

# Cleanup
echo ""
echo "[3/4] Cleaning up..."
kill $FORWARD_PID 2>/dev/null
rm -f "$ACTUAL_PTY" /tmp/uwb-* 2>/dev/null
echo "✓ Cleanup complete"

