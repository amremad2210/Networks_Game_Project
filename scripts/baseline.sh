#!/bin/bash
#change dir to project directory
PYTHON_DIR=~/networks_project/Networks_Game_Project
IFACE="lo"

safe_tc_qdisc_del() {
    local iface=$1
    if sudo tc qdisc show dev "$iface" | grep -q "netem"; then
        sudo tc qdisc del dev "$iface" root
    fi
}

echo "-------------------------------"
echo " Running scenario: Baseline"
echo "-------------------------------"

safe_tc_qdisc_del "$IFACE"

cd "$PYTHON_DIR" || exit 1

# Start tcpdump
sudo tcpdump -i lo -w "pcap_baseline.pcap" &
TCPDUMP_PID=$!
sleep 2  # ensure tcpdump is ready

# Start server
python3 server/server.py &
SERVER_PID=$!
sleep 2

# Start client in automation mode
AUTO_USERNAME="testuser" AUTOMATE=1 python3 client/start_game.py &
CLIENT1_PID=$!

AUTO_USERNAME="testuser2" AUTOMATE=1 python3 client/start_game.py &
CLIENT2_PID=$!
#AUTO_USERNAME="testuser2" AUTOMATE=1 python3 client/start_game.py &
#CLIENT2_PID=$!
# Wait for client automation duration (match automated_play duration in Python!)
sleep 10
kill $CLIENT1_PID 2>/dev/null
kill $CLIENT2_PID 2>/dev/null
kill $SERVER_PID 2>/dev/null
kill $TCPDUMP_PID 2>/dev/null
sleep 1
# Remove netem rule
safe_tc_qdisc_del "$IFACE"

# process collected logs
python3 scripts/calculate_metrics.py > metrics_summary.txt 2>&1

METRICS_PID=$!
sleep 5
kill $METRICS_PID 2>/dev/null
sleep 1

echo " Completed: baseline test"
echo ""

echo "All scenarios complete."

