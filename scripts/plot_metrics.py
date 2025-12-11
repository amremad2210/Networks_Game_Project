#!/usr/bin/env python3
"""
plot_metrics.py

Generates plots comparing network metrics across different test scenarios.
Reads final_metrics CSV files from metrics_results/ directory and creates
comparison plots for latency, jitter, position error, and CPU usage.
"""

import pandas as pd
import matplotlib.pyplot as plt
import sys
from pathlib import Path

def load_metrics(results_dir='metrics_results'):
    """Load all final_metrics CSV files from results directory"""
    results_path = Path(results_dir)
    
    if not results_path.exists():
        print(f"Error: Results directory '{results_dir}' not found")
        return None
    
    metrics_files = list(results_path.glob('final_metrics_*.csv'))
    
    if not metrics_files:
        print(f"No final_metrics CSV files found in {results_dir}")
        return None
    
    scenarios_data = {}
    
    for file_path in metrics_files:
        # Extract scenario name from filename
        scenario = file_path.stem.replace('final_metrics_', '')
        
        try:
            df = pd.read_csv(file_path)
            scenarios_data[scenario] = df
            print(f"Loaded {len(df)} records for scenario: {scenario}")
        except Exception as e:
            print(f"Error loading {file_path}: {e}")
    
    return scenarios_data

def plot_latency_comparison(scenarios_data, output_dir='metrics_results'):
    """Create latency comparison plot"""
    plt.figure(figsize=(12, 6))
    
    for scenario, df in scenarios_data.items():
        plt.plot(df['snapshot_id'].values, df['latency_ms'].values, label=scenario, alpha=0.7)
    
    plt.xlabel('Snapshot ID')
    plt.ylabel('Latency (ms)')
    plt.title('Latency Comparison Across Scenarios')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    
    output_path = Path(output_dir) / 'plot_latency_comparison.png'
    plt.savefig(output_path, dpi=300)
    print(f"Saved: {output_path}")
    plt.close()

def plot_jitter_comparison(scenarios_data, output_dir='metrics_results'):
    """Create jitter comparison plot"""
    plt.figure(figsize=(12, 6))
    
    for scenario, df in scenarios_data.items():
        plt.plot(df['snapshot_id'].values, df['jitter_ms'].values, label=scenario, alpha=0.7)
    
    plt.xlabel('Snapshot ID')
    plt.ylabel('Jitter (ms)')
    plt.title('Jitter Comparison Across Scenarios')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    
    output_path = Path(output_dir) / 'plot_jitter_comparison.png'
    plt.savefig(output_path, dpi=300)
    print(f"Saved: {output_path}")
    plt.close()

def plot_position_error_comparison(scenarios_data, output_dir='metrics_results'):
    """Create position error comparison plot"""
    plt.figure(figsize=(12, 6))
    
    for scenario, df in scenarios_data.items():
        plt.plot(df['snapshot_id'].values, df['perceived_position_error'].values, 
                label=scenario, alpha=0.7)
    
    plt.xlabel('Snapshot ID')
    plt.ylabel('Position Error (units)')
    plt.title('Perceived Position Error Comparison Across Scenarios')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    
    output_path = Path(output_dir) / 'plot_position_error_comparison.png'
    plt.savefig(output_path, dpi=300)
    print(f"Saved: {output_path}")
    plt.close()

def plot_cpu_usage_comparison(scenarios_data, output_dir='metrics_results'):
    """Create CPU usage comparison plot"""
    plt.figure(figsize=(12, 6))
    
    for scenario, df in scenarios_data.items():
        # Group by snapshot_id and take mean (since multiple clients)
        cpu_data = df.groupby('snapshot_id')['cpu_percent'].mean()
        plt.plot(cpu_data.index.values, cpu_data.values, label=scenario, alpha=0.7)
    
    plt.xlabel('Snapshot ID')
    plt.ylabel('CPU Usage (%)')
    plt.title('Server CPU Usage Comparison Across Scenarios')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    
    output_path = Path(output_dir) / 'plot_cpu_usage_comparison.png'
    plt.savefig(output_path, dpi=300)
    print(f"Saved: {output_path}")
    plt.close()

def plot_summary_statistics(scenarios_data, output_dir='metrics_results'):
    """Create bar chart comparing mean metrics across scenarios"""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    scenarios = list(scenarios_data.keys())
    
    # Latency statistics
    latency_means = [scenarios_data[s]['latency_ms'].mean() for s in scenarios]
    axes[0, 0].bar(scenarios, latency_means, color='skyblue')
    axes[0, 0].set_ylabel('Mean Latency (ms)')
    axes[0, 0].set_title('Mean Latency by Scenario')
    axes[0, 0].grid(True, alpha=0.3, axis='y')
    
    # Jitter statistics
    jitter_means = [scenarios_data[s]['jitter_ms'].mean() for s in scenarios]
    axes[0, 1].bar(scenarios, jitter_means, color='lightcoral')
    axes[0, 1].set_ylabel('Mean Jitter (ms)')
    axes[0, 1].set_title('Mean Jitter by Scenario')
    axes[0, 1].grid(True, alpha=0.3, axis='y')
    
    # Position error statistics
    error_means = [scenarios_data[s]['perceived_position_error'].mean() for s in scenarios]
    axes[1, 0].bar(scenarios, error_means, color='lightgreen')
    axes[1, 0].set_ylabel('Mean Position Error')
    axes[1, 0].set_title('Mean Position Error by Scenario')
    axes[1, 0].grid(True, alpha=0.3, axis='y')
    
    # CPU usage statistics
    cpu_means = [scenarios_data[s]['cpu_percent'].mean() for s in scenarios]
    axes[1, 1].bar(scenarios, cpu_means, color='gold')
    axes[1, 1].set_ylabel('Mean CPU Usage (%)')
    axes[1, 1].set_title('Mean CPU Usage by Scenario')
    axes[1, 1].grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    
    output_path = Path(output_dir) / 'plot_summary_statistics.png'
    plt.savefig(output_path, dpi=300)
    print(f"Saved: {output_path}")
    plt.close()

def plot_median_statistics(scenarios_data, output_dir='metrics_results'):
    """Create bar chart comparing median metrics across scenarios"""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    scenarios = list(scenarios_data.keys())
    
    # Latency statistics
    latency_medians = [scenarios_data[s]['latency_ms'].median() for s in scenarios]
    axes[0, 0].bar(scenarios, latency_medians, color='steelblue')
    axes[0, 0].set_ylabel('Median Latency (ms)')
    axes[0, 0].set_title('Median Latency by Scenario')
    axes[0, 0].grid(True, alpha=0.3, axis='y')
    
    # Jitter statistics
    jitter_medians = [scenarios_data[s]['jitter_ms'].median() for s in scenarios]
    axes[0, 1].bar(scenarios, jitter_medians, color='indianred')
    axes[0, 1].set_ylabel('Median Jitter (ms)')
    axes[0, 1].set_title('Median Jitter by Scenario')
    axes[0, 1].grid(True, alpha=0.3, axis='y')
    
    # Position error statistics
    error_medians = [scenarios_data[s]['perceived_position_error'].median() for s in scenarios]
    axes[1, 0].bar(scenarios, error_medians, color='mediumseagreen')
    axes[1, 0].set_ylabel('Median Position Error')
    axes[1, 0].set_title('Median Position Error by Scenario')
    axes[1, 0].grid(True, alpha=0.3, axis='y')
    
    # CPU usage statistics
    cpu_medians = [scenarios_data[s]['cpu_percent'].median() for s in scenarios]
    axes[1, 1].bar(scenarios, cpu_medians, color='goldenrod')
    axes[1, 1].set_ylabel('Median CPU Usage (%)')
    axes[1, 1].set_title('Median CPU Usage by Scenario')
    axes[1, 1].grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    
    output_path = Path(output_dir) / 'plot_median_statistics.png'
    plt.savefig(output_path, dpi=300)
    print(f"Saved: {output_path}")
    plt.close()

def plot_95th_percentile_statistics(scenarios_data, output_dir='metrics_results'):
    """Create bar chart comparing 95th percentile metrics across scenarios"""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    scenarios = list(scenarios_data.keys())
    
    # Latency statistics
    latency_95th = [scenarios_data[s]['latency_ms'].quantile(0.95) for s in scenarios]
    axes[0, 0].bar(scenarios, latency_95th, color='royalblue')
    axes[0, 0].set_ylabel('95th Percentile Latency (ms)')
    axes[0, 0].set_title('95th Percentile Latency by Scenario')
    axes[0, 0].grid(True, alpha=0.3, axis='y')
    
    # Jitter statistics
    jitter_95th = [scenarios_data[s]['jitter_ms'].quantile(0.95) for s in scenarios]
    axes[0, 1].bar(scenarios, jitter_95th, color='crimson')
    axes[0, 1].set_ylabel('95th Percentile Jitter (ms)')
    axes[0, 1].set_title('95th Percentile Jitter by Scenario')
    axes[0, 1].grid(True, alpha=0.3, axis='y')
    
    # Position error statistics
    error_95th = [scenarios_data[s]['perceived_position_error'].quantile(0.95) for s in scenarios]
    axes[1, 0].bar(scenarios, error_95th, color='forestgreen')
    axes[1, 0].set_ylabel('95th Percentile Position Error')
    axes[1, 0].set_title('95th Percentile Position Error by Scenario')
    axes[1, 0].grid(True, alpha=0.3, axis='y')
    
    # CPU usage statistics
    cpu_95th = [scenarios_data[s]['cpu_percent'].quantile(0.95) for s in scenarios]
    axes[1, 1].bar(scenarios, cpu_95th, color='darkgoldenrod')
    axes[1, 1].set_ylabel('95th Percentile CPU Usage (%)')
    axes[1, 1].set_title('95th Percentile CPU Usage by Scenario')
    axes[1, 1].grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    
    output_path = Path(output_dir) / 'plot_95th_percentile_statistics.png'
    plt.savefig(output_path, dpi=300)
    print(f"Saved: {output_path}")
    plt.close()

def main():
    """Main function to generate all plots"""
    print("="*60)
    print("GENERATING METRICS PLOTS")
    print("="*60)
    
    # Allow custom results directory
    results_dir = sys.argv[1] if len(sys.argv) > 1 else 'metrics_results'
    
    # Load all metrics
    print(f"\nLoading metrics from: {results_dir}")
    scenarios_data = load_metrics(results_dir)
    
    if not scenarios_data:
        print("\nNo data to plot")
        sys.exit(1)
    
    # Generate plots
    print("\nGenerating plots...")
    plot_latency_comparison(scenarios_data, results_dir)
    plot_jitter_comparison(scenarios_data, results_dir)
    plot_position_error_comparison(scenarios_data, results_dir)
    plot_cpu_usage_comparison(scenarios_data, results_dir)
    plot_summary_statistics(scenarios_data, results_dir)
    plot_median_statistics(scenarios_data, results_dir)
    plot_95th_percentile_statistics(scenarios_data, results_dir)
    
    print("\n" + "="*60)
    print("All plots generated successfully!")
    print("="*60)

if __name__ == '__main__':
    main()
