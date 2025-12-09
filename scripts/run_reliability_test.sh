#!/usr/bin/env bash
# run_reliability_test.sh
# Orchestrate server + multiple automated clients, optional network impairment (tc/netem),
# capture pcap, and collect metrics for post-processing.

set -eu

# Base project directory (one level up from scripts/)
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IFACE="lo"

usage() {
    cat <<EOF
Usage: $0 [-s scenario] [-d duration] [-n clients]

Options:
  -s scenario   Scenario name: none (default), loss_2, loss_5, delay_100
  -d duration   Test duration in seconds (default: 20)
  -n clients    Number of automated clients to launch (default: 2)
  -h            Show this help

Example:
  $0 -s loss_5 -d 30 -n 3

EOF
}

SCENARIO="none"
DURATION=20
CLIENTS=2

while getopts ":s:d:n:h" opt; do
  case ${opt} in
    s ) SCENARIO=$OPTARG ;;
    d ) DURATION=$OPTARG ;;
    n ) CLIENTS=$OPTARG ;;
    h ) usage; exit 0 ;;
    \? ) echo "Invalid option: -$OPTARG"; usage; exit 1 ;;
  esac
done

RESULTS_DIR="$BASE_DIR/metrics_results/$(date +%Y%m%d_%H%M%S)_${SCENARIO}"
mkdir -p "$RESULTS_DIR"

get_netem_command() {
    case "$1" in
        "none") echo "" ;;
        "loss_2") echo "loss 2%" ;;
        "loss_5") echo "loss 5%" ;;
        "delay_100") echo "delay 100ms" ;;
        *) echo "" ;;
    esac
}

safe_tc_qdisc_del() {
    local iface=$1
    if sudo tc qdisc show dev "$iface" | grep -q "netem"; then
        sudo tc qdisc del dev "$iface" root || true
    fi
}

# Apply netem rule if requested
netem_cmd=$(get_netem_command "$SCENARIO")
if [[ -n "$netem_cmd" ]]; then
    echo "Applying netem: $netem_cmd on $IFACE"
    sudo tc qdisc add dev "$IFACE" root netem $netem_cmd
else
    echo "No netem impairment requested"
fi

cd "$BASE_DIR"

# Start tcpdump to capture traffic
PCAP_PATH="$RESULTS_DIR/pcap_${SCENARIO}.pcap"
sudo tcpdump -i "$IFACE" -w "$PCAP_PATH" &
TCPDUMP_PID=$!
sleep 1

# Ensure no server is running on UDP 9999
# fuser for UDP
if command -v fuser >/dev/null 2>&1; then
    fuser -k 9999/udp 2>/dev/null || true
fi

# Start server
echo "Starting server..."
python3 server/server.py > "$RESULTS_DIR/server_stdout.log" 2> "$RESULTS_DIR/server_stderr.log" &
SERVER_PID=$!
sleep 2

# Start automated clients
echo "Launching ${CLIENTS} automated client(s)..."
CLIENT_PIDS=()
for i in $(seq 1 $CLIENTS); do
    USERNAME="auto_user_${i}"
    echo "Starting client #$i as $USERNAME"
    # Use dummy video driver so pygame works headless if DISPLAY not available
    env SDL_VIDEODRIVER=dummy AUTO_USERNAME="$USERNAME" AUTOMATE=1 python3 client/start_game.py > "$RESULTS_DIR/client_${i}_stdout.log" 2> "$RESULTS_DIR/client_${i}_stderr.log" &
    PID=$!
    CLIENT_PIDS+=("$PID")
    sleep 0.5
done

# Wait for the requested duration while clients run automation
echo "Test running for ${DURATION}s..."
sleep "$DURATION"

echo "Test duration complete — shutting down processes..."

# Kill clients
for pid in "${CLIENT_PIDS[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then
        kill "$pid" || true
    fi
done

# Kill server
if kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID" || true
fi

# Stop tcpdump
if kill -0 "$TCPDUMP_PID" 2>/dev/null; then
    kill "$TCPDUMP_PID" || true
fi
sleep 1

# Remove netem rule
safe_tc_qdisc_del "$IFACE"

# Gather metric files
echo "Collecting metric files..."
# Move server metrics
if [ -f server_metrics.csv ]; then
    mv server_metrics.csv "$RESULTS_DIR/"
    echo "Moved server_metrics.csv -> $RESULTS_DIR/"
else
    echo "Warning: server_metrics.csv not found"
fi

# Move client metric files (client_metrics_<pid>.csv)
shopt -s nullglob
CLIENT_METRICS=(client_metrics_*.csv client_metrics_*.CSV client_log_*.csv client_log_*.CSV)
if [ ${#CLIENT_METRICS[@]} -gt 0 ]; then
    i=1
    for f in "${CLIENT_METRICS[@]}"; do
        mv "$f" "$RESULTS_DIR/"
        echo "Moved $f -> $RESULTS_DIR/"
        i=$((i+1))
    done
else
    echo "Warning: No client metrics found matching client_metrics_*.csv or client_log_*.csv"
fi

# Run metrics calculation (if server metrics present)
if [ -f "$RESULTS_DIR/server_metrics.csv" ]; then
    echo "Calculating metrics..."
    # Pass any client metrics in the results dir to the calculate_metrics script
    pushd "$RESULTS_DIR" >/dev/null
    CLIENT_FILES=(client_metrics_*.csv client_log_*.csv)
    # Filter existing files
    ARGS=()
    for cf in "${CLIENT_FILES[@]}"; do
        if [ -f "$cf" ]; then
            ARGS+=("$cf")
        fi
    done
    if [ ${#ARGS[@]} -gt 0 ]; then
        python3 "$BASE_DIR/scripts/calculate_metrics.py" "${ARGS[@]}" > metrics_summary.txt 2>&1 || true
        echo "Metrics calculation complete; results in $RESULTS_DIR/final_metrics.csv and metrics_summary.txt"
    else
        echo "No client metrics to pass to calculate_metrics.py"
    fi
    popd >/dev/null
else
    echo "Skipping metrics calculation: server_metrics.csv missing"
fi

# Final summary
echo "Test complete. Results stored in: $RESULTS_DIR"
ls -l "$RESULTS_DIR"

exit 0
