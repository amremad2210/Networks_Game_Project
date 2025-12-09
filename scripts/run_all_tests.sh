#!/bin/bash

# source ~/myenv/bin/activate

#for my linux machine (maybe change this path accordingly -amr)
#source .venv/bin/activate
#pip install pygame psutil


PYTHON_DIR=/home/amremad2210/Documents/Networks_Game_Project #change 3la 7asab el project fen -aya
IFACE="lo"
scenarios=("none" "loss_2" "loss_5" "delay_100")

# 🔹 Directory to store metrics and pcap files
RESULTS_DIR="$PYTHON_DIR/metrics_results"

# 🔹 Create the directory if it doesn't exist
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
    sudo tcpdump -i lo -w "$RESULTS_DIR/pcap_${scenario}.pcap" &
    TCPDUMP_PID=$!
    sleep 2  # ensure tcpdump is ready

    # Kill any leftover server on port 9999
    fuser -k 9999/tcp 2>/dev/null || true


    # Start server
    python3 server/server.py &
    SERVER_PID=$!
    sleep 2

    # Start multiple clients in automation mode
    AUTO_USERNAME="testuser1" AUTOMATE=1 python3 client/start_game.py &
    CLIENT1_PID=$!
    
    AUTO_USERNAME="testuser2" AUTOMATE=1 python3 client/start_game.py &
    CLIENT2_PID=$!

    # Wait for client automation duration (match automated_play duration in Python!)
    sleep 20

    kill $CLIENT1_PID 2>/dev/null
    kill $CLIENT2_PID 2>/dev/null
    kill $SERVER_PID 2>/dev/null
    kill $TCPDUMP_PID 2>/dev/null
    sleep 1

    # Remove netem rule
    safe_tc_qdisc_del "$IFACE"

    # 🔹 Process collected logs and calculate metrics
    python3 scripts/calculate_metrics.py > "$RESULTS_DIR/metrics_summary_${scenario}.txt" 2>&1
    
    # 🔹 Move final metrics CSV to results folder
    if [ -f final_metrics.csv ]; then
        mv final_metrics.csv "$RESULTS_DIR/final_metrics_${scenario}.csv"
        echo "Saved final_metrics_${scenario}.csv to $RESULTS_DIR"
    fi

    # 🔹 Move metrics CSV to the results folder
    if [ -f metrics.csv ]; then
        mv metrics.csv "$RESULTS_DIR/metrics_${scenario}.csv"
        echo "Saved metrics_${scenario}.csv to $RESULTS_DIR"
    else
        echo "Warning: metrics.csv not found for scenario $scenario"
    fi

    echo " Completed: $scenario"
    echo ""
done

# 🔹 Generate comparison plots
echo ""
echo "Generating comparison plots..."
python3 scripts/plot_metrics.py "$RESULTS_DIR"

deactivate
echo "All scenarios complete. Results saved in: $RESULTS_DIR"
