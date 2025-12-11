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
        
        # Sort by snapshot_id to ensure proper jitter calculation
        client_entries.sort(key=lambda x: x['snapshot_id'])
        
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
            
            # Calculate perceived position error
            # Server's authoritative position for this client
            server_positions = server_entry['players_pos']
            server_position = server_positions.get(client_id)
            
            # Client's displayed position
            client_position = client_entry['player_position']
            #print(f"[DEBUG] client pos= {client_position}  server_pos = {server_position}")
            perceived_position_error = calculate_euclidean_distance(server_position, client_position)
            
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
        # Auto-detect client log files in logs/client_logs directory
        client_log_paths = sorted(Path('logs/client_logs').glob('client_metric*.csv'))
        if not client_log_paths:
            print("\nNo client log files found in logs/client_logs/. Please specify client log file(s) as arguments.")
            print("\nUsage: python calculate_metrics.py <client_metrics.csv> [client_log_2.csv] ...")
            sys.exit(1)
        client_log_paths = [str(p) for p in client_log_paths]
    
    print(f"\nFound {len(client_log_paths)} client log file(s):")
    for path in client_log_paths:
        print(f"  - {path}")
    
    # Load server logs
    print("\nLoading server logs...")
    server_data = load_server_logs('logs/server_logs/server_metrics.csv')
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
