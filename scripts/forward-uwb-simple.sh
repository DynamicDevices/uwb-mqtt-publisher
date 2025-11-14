#!/bin/bash
# Simple method: Forward UWB serial port from target device to local machine
# Usage: ./forward-uwb-simple.sh <target_host> [target_user] [target_password]

TARGET_HOST="${1:-}"
TARGET_USER="${2:-fio}"
TARGET_PASSWORD="${3:-fio}"
REMOTE_DEVICE="/dev/ttyUSB0"

if [ -z "$TARGET_HOST" ]; then
    echo "Usage: $0 <target_host> [target_user] [target_password]"
    echo "Example: $0 192.168.2.218 fio fio"
    exit 1
fi

# Check for sshpass
if ! command -v sshpass >/dev/null 2>&1; then
    echo "Error: sshpass not found. Install with: sudo apt-get install sshpass"
    exit 1
fi

# Setup SSH multiplexing for faster connections
SSH_CONTROL_DIR="$HOME/.ssh/uwb-forward"
mkdir -p "$SSH_CONTROL_DIR"
SSH_CONTROL_PATH="$SSH_CONTROL_DIR/$TARGET_HOST"
SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ControlMaster=auto -o ControlPath=$SSH_CONTROL_PATH -o ControlPersist=300"

# SSH command with sshpass and multiplexing
# Use eval to properly handle the command with options
ssh_cmd() {
    sshpass -p "$TARGET_PASSWORD" ssh $SSH_OPTS "$@"
}

# Cleanup function to close master connection
cleanup_ssh() {
    if [ -S "$SSH_CONTROL_PATH" ]; then
        sshpass -p "$TARGET_PASSWORD" ssh -o ControlPath="$SSH_CONTROL_PATH" -O exit "$TARGET_USER@$TARGET_HOST" 2>/dev/null || true
        rm -f "$SSH_CONTROL_PATH"
    fi
}

# Replace all $SSH_CMD calls with ssh_cmd function
trap cleanup_ssh EXIT INT TERM

echo "=== UWB Serial Port Forwarding ==="
echo "Target: $TARGET_USER@$TARGET_HOST"
echo "Remote device: $REMOTE_DEVICE"
echo ""

# Stop container if running
echo "[1/3] Checking for running container..."
CONTAINER_RUNNING=$(ssh_cmd "$TARGET_USER@$TARGET_HOST" "docker ps --filter 'name=uwb-mqtt-publisher' --format '{{.Names}}' 2>/dev/null" || echo "")

if [ -n "$CONTAINER_RUNNING" ]; then
    echo "⚠️  Container 'uwb-mqtt-publisher' is running"
    echo "Stopping container..."
    ssh_cmd "$TARGET_USER@$TARGET_HOST" "docker stop uwb-mqtt-publisher" 2>/dev/null || echo "Container already stopped"
    sleep 1
else
    echo "✓ No container running"
fi

# Check if device exists
echo ""
echo "[2/4] Checking if $REMOTE_DEVICE exists on target..."
# Check if device exists (as file or character device)
DEVICE_EXISTS=$(ssh_cmd "$TARGET_USER@$TARGET_HOST" "test -e $REMOTE_DEVICE -o -c $REMOTE_DEVICE 2>/dev/null && echo 'yes' || echo 'no'")

if [ "$DEVICE_EXISTS" != "yes" ]; then
    # Try with sudo in case of permission issues
    DEVICE_EXISTS=$(ssh_cmd "$TARGET_USER@$TARGET_HOST" "sudo test -e $REMOTE_DEVICE -o -c $REMOTE_DEVICE 2>/dev/null && echo 'yes' || echo 'no'")
fi

if [ "$DEVICE_EXISTS" != "yes" ]; then
    echo "✗ Device $REMOTE_DEVICE not found on target"
    echo "Attempting to list available devices..."
    ssh_cmd "$TARGET_USER@$TARGET_HOST" "ls -l /dev/ttyUSB* /dev/ttyACM* 2>/dev/null | head -5" || true
    exit 1
else
    echo "✓ Device found"
fi

# Check for socat on target
echo ""
echo "[3/4] Checking for socat on target..."
SOCAT_AVAILABLE=$(ssh_cmd "$TARGET_USER@$TARGET_HOST" "which socat >/dev/null 2>&1 && echo 'yes' || echo 'no'")

if [ "$SOCAT_AVAILABLE" != "yes" ]; then
    echo "⚠️  socat not found on target - attempting to install..."
    ssh_cmd "$TARGET_USER@$TARGET_HOST" "opkg update && opkg install socat" 2>&1 || {
        echo "✗ Failed to install socat automatically"
        echo "Please install socat on the target manually:"
        echo "  ssh $TARGET_USER@$TARGET_HOST"
        echo "  opkg update && opkg install socat"
        exit 1
    }
    echo "✓ socat installed"
else
    echo "✓ socat available"
fi

# Check for socat locally
if ! command -v socat >/dev/null 2>&1; then
    echo "✗ socat not found locally. Install with: sudo apt-get install socat"
    exit 1
fi

echo ""
echo "[4/4] Starting forwarding..."
echo "Press Ctrl+C to stop"
echo ""

# Create local PTY
LOCAL_PTY=$(mktemp -u /tmp/uwb-XXXXXX)

# Start forwarding: SSH reads serial and pipes to local socat
# Remote: socat reads serial device and outputs to stdout
# Local: socat reads from stdin and creates PTY
ssh_cmd "$TARGET_USER@$TARGET_HOST" "socat $REMOTE_DEVICE,raw,echo=0,b115200 -" 2>/dev/null | \
    socat -d -d pty,raw,echo=0,link="$LOCAL_PTY" - 2>&1 | grep -E "PTY is|N PTY" | head -1 &

FORWARD_PID=$!

# Wait for PTY to be created
sleep 2

# Find the actual PTY
ACTUAL_PTY=$(find /tmp -name "uwb-*" -type l 2>/dev/null | head -1)

if [ -z "$ACTUAL_PTY" ] || [ ! -e "$ACTUAL_PTY" ]; then
    echo "⚠️  Could not determine PTY path, trying $LOCAL_PTY"
    ACTUAL_PTY="$LOCAL_PTY"
fi

echo ""
echo "✅ Forwarding active!"
echo "Local device: $ACTUAL_PTY"
echo "Use this in your application: $ACTUAL_PTY"
echo "PID: $FORWARD_PID"
echo ""

trap "echo ''; echo 'Stopping forwarding...'; kill $FORWARD_PID 2>/dev/null; rm -f $LOCAL_PTY /tmp/uwb-* 2>/dev/null; cleanup_ssh; exit" INT TERM
wait $FORWARD_PID
cleanup_ssh

