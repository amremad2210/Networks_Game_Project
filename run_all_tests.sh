#!/bin/bash

source ~/myenv/bin/activate

PYTHON_DIR=~
IFACE="lo"
scenarios=("none" "loss_2" "loss_5" "delay_100")

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
        sudo tc qdisc del dev "$iface" root
    fi
}

for scenario in "${scenarios[@]}"; do
    echo "-------------------------------"
    echo " Running scenario: $scenario"
    echo "-------------------------------"

    safe_tc_qdisc_del "$IFACE"

    netem_cmd=$(get_netem_command $scenario)
    if [[ -n "$netem_cmd" ]]; then
        sudo tc qdisc add dev "$IFACE" root netem $netem_cmd
    fi

    cd "$PYTHON_DIR" || exit 1

    # Start tcpdump
    sudo tcpdump -i lo -w "pcap_${scenario}.pcap" &
    TCPDUMP_PID=$!
    sleep 2  # ensure tcpdump is ready

    # Start server
    python3 server.py &
    SERVER_PID=$!
    sleep 2

    # Start client in automation mode
    AUTO_USERNAME="testuser" AUTOMATE=1 python3 start_game.py &
    CLIENT_PID=$!

    # Wait for client automation duration (match automated_play duration in Python!)
    sleep 20

    kill $CLIENT_PID 2>/dev/null
    kill $SERVER_PID 2>/dev/null
    kill $TCPDUMP_PID 2>/dev/null
    sleep 1

    safe_tc_qdisc_del "$IFACE"
    echo " Completed: $scenario"
    echo ""
done

deactivate
echo "All scenarios complete."

