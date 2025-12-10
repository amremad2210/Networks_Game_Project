#!/usr/bin/env python3
"""
calculate_metrics.py

This script reads the separate server and client log files and calculates
the required network performance metrics for each client, outputting them
to a final metrics CSV file.

Required columns in final metrics CSV:
- client_id: Client identifier
- snapshot_id: Snapshot identifier  
- seq_num: Packet sequence number
- server_timestamp_ms: Timestamp at server send
- recv_time_ms: Timestamp at client receive
- latency_ms: recv_time - server_timestamp
- jitter_ms: Variation in inter-arrival times
- perceived_position_error: Euclidean distance between server's authoritative position and client's displayed position
- cpu_percent: Server CPU utilization
- bandwidth_per_client_kbps: Average measured bandwidth per client

The script also calculates and prints:
- Mean, median, and 95th percentile for latency, jitter, and error
"""

import csv
import json
import math
import sys
from pathlib import Path
from statistics import mean, median
from collections import defaultdict
import bisect

def load_server_logs(server_log_path='server_log.csv'):
    """
    Load server log file.
    
    Expected columns:
    - snapshot_id
    - seq_num
    - server_timestamp_ms
    - cpu_percent
    - players_pos (JSON string)
    
    Returns: dict mapping snapshot_id -> row data
    """
    server_data = {}
    
    try:
        with open(server_log_path, 'r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                snapshot_id = int(row['snapshot_id'])
                server_data[snapshot_id] = {
                    'seq_num': int(row['seq_num']),
                    'server_timestamp_ms': int(row['server_timestamp_ms']),
                    'cpu_percent': float(row['cpu_percent']),
                    'players_pos': json.loads(row['players_pos']) if row['players_pos'] else {}
                }
        print(f"Loaded {len(server_data)} server log entries from {server_log_path}")
        return server_data
    except FileNotFoundError:
        print(f"Error: Server log file '{server_log_path}' not found")
        return None
    except Exception as e:
        print(f"Error loading server logs: {e}")
        return None

def load_client_logs(client_log_path):
    """
    Load client log file.
    
    Expected columns:
    - client_id
    - snapshot_id
    - seq_num
    - recv_time_ms
    - player_position (JSON string)
    - bandwidth_per_client_kbps
    
    Returns: list of row dictionaries
    """
    client_data = []
    
    try:
        with open(client_log_path, 'r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                client_data.append({
                    'client_id': row['client_id'],
                    'snapshot_id': int(row['snapshot_id']),
                    'seq_num': int(row['seq_num']),
                    'recv_time_ms': int(row['recv_time_ms']),
                    'player_position': json.loads(row['player_position']) if row['player_position'] and row['player_position'] != '{}' else None,
                    'bandwidth_per_client_kbps': float(row['bandwidth_per_client_kbps'])
                })
        print(f"Loaded {len(client_data)} client log entries from {client_log_path}")
        return client_data
    except FileNotFoundError:
        print(f"Error: Client log file '{client_log_path}' not found")
        return None
    except Exception as e:
        print(f"Error loading client logs: {e}")
        return None

def calculate_euclidean_distance(pos1, pos2):
    """Calculate Euclidean distance between two positions"""
    if not pos1 or not pos2:
        return 0.0
    
    try:
        x1, y1 = pos1.get('x', 0), pos1.get('y', 0)
        x2, y2 = pos2.get('x', 0), pos2.get('y', 0)
        return round(math.sqrt((x2 - x1)**2 + (y2 - y1)**2), 4)
    except Exception:
        return 0.0

def calculate_metrics(server_data, client_data_list, output_path='final_metrics.csv'):
    """
    Calculate all required metrics by joining server and client data.
    
    For each client snapshot:
    1. Match with corresponding server snapshot by snapshot_id
    2. Calculate latency (recv_time - server_timestamp)
    3. Calculate jitter (variation in latency)
    4. Calculate perceived position error (distance between server's authoritative position and client's displayed position)
    5. Get CPU and bandwidth from respective logs
    """
    
    # Group client data by client_id
    clients = defaultdict(list)
    for entry in client_data_list:
        clients[entry['client_id']].append(entry)
    
    # Output rows
    output_rows = []
    
    # Track metrics for statistics
    all_latencies = []
    all_jitters = []
    all_errors = []
    server_cpu_usage = []
    # Process each client
    for client_id, client_entries in clients.items():
        print(f"\nProcessing client: {client_id}")
        # Sort by receive time to support interpolation
        client_entries.sort(key=lambda x: x['recv_time_ms'])

        # Prepare arrays for interpolation: times and positions
        times = [e['recv_time_ms'] for e in client_entries]
        positions = [e['player_position'] for e in client_entries]

        last_latency = None
        
        for client_entry in client_entries:
            snapshot_id = client_entry['snapshot_id']
            
            # Find matching server entry
            if snapshot_id not in server_data:
                print(f"Warning: No server data for snapshot_id {snapshot_id}")
                continue
            
            server_entry = server_data[snapshot_id]
            
            # Calculate latency
            recv_time_ms = client_entry['recv_time_ms']
            server_timestamp_ms = server_entry['server_timestamp_ms']
            latency_ms = recv_time_ms - server_timestamp_ms
            
            # Calculate jitter (variation in inter-arrival times)
            if last_latency is None:
                jitter_ms = 0
            else:
                jitter_ms = abs(latency_ms - last_latency)
            last_latency = latency_ms
            
            # Calculate perceived position error using interpolation to server timestamp
            server_positions = server_entry['players_pos']
            server_position = server_positions.get(client_id)

            client_interp_pos = None
            # Interpolate client position to server timestamp (ms)
            try:
                t = server_timestamp_ms
                if times:
                    if t <= times[0]:
                        client_interp_pos = positions[0]
                    elif t >= times[-1]:
                        client_interp_pos = positions[-1]
                    else:
                        i = bisect.bisect_right(times, t)
                        t0 = times[i-1]
                        t1 = times[i]
                        p0 = positions[i-1]
                        p1 = positions[i]
                        if p0 and p1 and t1 != t0:
                            # linear interpolation on x and y
                            x0 = p0.get('x', 0)
                            y0 = p0.get('y', 0)
                            x1 = p1.get('x', 0)
                            y1 = p1.get('y', 0)
                            ratio = (t - t0) / (t1 - t0)
                            xi = x0 + (x1 - x0) * ratio
                            yi = y0 + (y1 - y0) * ratio
                            client_interp_pos = {'x': xi, 'y': yi}
                        else:
                            client_interp_pos = p0 or p1
                else:
                    client_interp_pos = None
            except Exception:
                client_interp_pos = None

            perceived_position_error = calculate_euclidean_distance(server_position, client_interp_pos)
            
            # Get other metrics
            cpu_percent = server_entry['cpu_percent']
            bandwidth_per_client_kbps = client_entry['bandwidth_per_client_kbps']
            seq_num = client_entry['seq_num']
            
            # Create output row
            row = {
                'client_id': client_id,
                'snapshot_id': snapshot_id,
                'seq_num': seq_num,
                'server_timestamp_ms': server_timestamp_ms,
                'recv_time_ms': recv_time_ms,
                'latency_ms': latency_ms,
                'jitter_ms': jitter_ms,
                'perceived_position_error': perceived_position_error,
                'cpu_percent': cpu_percent,
                'bandwidth_per_client_kbps': bandwidth_per_client_kbps
            }
            
            output_rows.append(row)
            
            # Track for statistics
            all_latencies.append(latency_ms)
            all_jitters.append(jitter_ms)
            all_errors.append(perceived_position_error)
            server_cpu_usage.append(cpu_percent)
    
    # Write output CSV
    if output_rows:
        with open(output_path, 'w', newline='') as f:
            fieldnames = [
                'client_id', 'snapshot_id', 'seq_num', 'server_timestamp_ms',
                'recv_time_ms', 'latency_ms', 'jitter_ms', 
                'perceived_position_error', 'cpu_percent', 'bandwidth_per_client_kbps'
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(output_rows)
        
        print(f"\nSuccessfully wrote {len(output_rows)} metric rows to {output_path}")
    else:
        print("\nNo metrics to write")
        return
    
    # Calculate and print statistics
    print("\n" + "="*60)
    print("STATISTICS SUMMARY")
    print("="*60)
    
    if all_latencies:
        print(f"\nLatency (ms):")
        print(f"  Mean:           {mean(all_latencies):.2f}")
        print(f"  Median:         {median(all_latencies):.2f}")
        print(f"  95th percentile: {percentile(all_latencies, 95):.2f}")
    
    if all_jitters:
        print(f"\nJitter (ms):")
        print(f"  Mean:           {mean(all_jitters):.2f}")
        print(f"  Median:         {median(all_jitters):.2f}")
        print(f"  95th percentile: {percentile(all_jitters, 95):.2f}")
    
    if all_errors:
        print(f"\nPerceived Position Error:")
        print(f"  Mean:           {mean(all_errors):.4f}")
        print(f"  Median:         {median(all_errors):.4f}")
        print(f"  95th percentile: {percentile(all_errors, 95):.4f}")
    
    print(f"\nMean Server CPU Usage: {mean(server_cpu_usage):.4f}")
    print("\n" + "="*60)

    # Event delivery statistics: look for client_events_*.csv files
    print("\nEvent delivery statistics:")
    event_files = list(Path('.').glob('client_events_*.csv'))
    if event_files:
        for ef in event_files:
            try:
                with open(ef, 'r', newline='') as f:
                    r = csv.DictReader(f)
                    total = 0
                    delivered = 0
                    within_200 = 0
                    for row in r:
                        total += 1
                        delivered_flag = row.get('delivered', 'False')
                        if delivered_flag.lower() in ['true', '1', 'yes']:
                            delivered += 1
                            try:
                                d = row.get('ack_delay_ms')
                                if d is not None and d != '':
                                    if float(d) <= 200.0:
                                        within_200 += 1
                            except Exception:
                                pass
                    pct_delivered = (delivered / total * 100.0) if total else 0.0
                    pct_within_200 = (within_200 / total * 100.0) if total else 0.0
                    print(f"  {ef.name}: total_events={total}, delivered={delivered} ({pct_delivered:.2f}%), within_200ms={within_200} ({pct_within_200:.2f}%)")
            except Exception as e:
                print(f"  Failed to read {ef}: {e}")
    else:
        print("  No client_events_*.csv files found; event delivery stats unavailable.")

def percentile(data, p):
    """Calculate the p-th percentile of data"""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_data[int(k)]
    d0 = sorted_data[int(f)] * (c - k)
    d1 = sorted_data[int(c)] * (k - f)
    return d0 + d1

def main():
    """Main function to organize metric calculation"""
    print("="*60)
    print("NETWORK METRICS CALCULATIONS")
    print("="*60)
    
    # Check for command line arguments
    if len(sys.argv) > 1:
        client_log_paths = sys.argv[1:]
    else:
        # Auto-detect client log files
        client_log_paths = sorted(Path('.').glob('client_metric*.csv'))
        if not client_log_paths:
            print("\nNo client log files found. Please specify client log file(s) as arguments.")
            print("\nUsage: python calculate_metrics.py <client_metrics.csv> [client_log_2.csv] ...")
            sys.exit(1)
        client_log_paths = [str(p) for p in client_log_paths]
    
    print(f"\nFound {len(client_log_paths)} client log file(s):")
    for path in client_log_paths:
        print(f"  - {path}")
    
    # Load server logs
    print("\nLoading server logs...")
    server_data = load_server_logs('server_metrics.csv')
    if server_data is None:
        sys.exit(1)
    
    # Load all client logs
    print("\nLoading client logs...")
    all_client_data = []
    for client_log_path in client_log_paths:
        client_data = load_client_logs(client_log_path)
        if client_data is None:
            print(f"  Skipping {client_log_path}")
            continue
        all_client_data.extend(client_data)
    
    if not all_client_data:
        print("\nNo valid client data loaded")
        sys.exit(1)
    
    # Calculate metrics
    print("\nCalculating metrics...")
    calculate_metrics(server_data, all_client_data, 'final_metrics.csv')
    
    print("\nDone!")

if __name__ == '__main__':
    main()
