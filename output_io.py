import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

def generate_boxplots(csv_file):
    # Load the data
    try:
        df = pd.read_csv(csv_file)
    except FileNotFoundError:
        print(f"Error: {csv_file} not found. Please run the benchmark script first.")
        return

    # Set the visual theme
    sns.set_theme(style="whitegrid")
    
    # Create a figure with 3 subplots (1 row, 3 columns)
    fig, axes = plt.subplots(1, 3, figsize=(20, 6))

    # 1. Boxplot for Execution Time
    sns.boxplot(x='Frequency_GHz', y='Time_Sec', data=df, ax=axes[0], palette="Blues")
    axes[0].set_title('Execution Time Stability', fontsize=14)
    axes[0].set_xlabel('CPU Frequency (GHz)')
    axes[0].set_ylabel('Time (Seconds)')
    y_max = df['Time_Sec'].max()
    axes[0].set_ylim(0, y_max * 1.1)

    # 2. Boxplot for Energy Consumption
    sns.boxplot(x='Frequency_GHz', y='Energy_Joules', data=df, ax=axes[1], palette="Reds")
    axes[1].set_title('Energy Consumption per Test', fontsize=14)
    axes[1].set_xlabel('CPU Frequency (GHz)')
    axes[1].set_ylabel('Energy (Joules)')
    y_max = df['Energy_Joules'].max()
    axes[1].set_ylim(0, y_max * 1.1)

    # 3. Boxplot for Write Rate (Throughput)
    sns.boxplot(x='Frequency_GHz', y='Rate_MBs', data=df, ax=axes[2], palette="Greens")
    axes[2].set_title('Throughput Distribution', fontsize=14)
    axes[2].set_xlabel('CPU Frequency (GHz)')
    axes[2].set_ylabel('Write Rate (MB/s)')
    y_max = df['Rate_MBs'].max()
    axes[2].set_ylim(0, y_max * 1.1)

    # Add a main title for the whole figure
    plt.suptitle('I/O Performance vs. CPU Frequency Analysis', fontsize=16, y=1.05)
    
    plt.tight_layout()
    plt.savefig('io_benchmark_boxplots.png', bbox_inches='tight')
    print("Detailed box plots saved as 'io_benchmark_boxplots.png'")

if __name__ == "__main__":
    generate_boxplots('benchmark_results.csv')