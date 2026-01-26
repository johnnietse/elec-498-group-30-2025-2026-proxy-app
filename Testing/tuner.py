import pandas as pd
import numpy as np
from scipy.optimize import differential_evolution
from collections import deque, Counter
import statistics

# ---------------- CONFIGURATION ----------------
# MERGED MAPPING (The Nuclear Option for High-Speed Apps)
PHASE_MAP = {
    "COMPUTE": 0,
    "COMMUNICATION": 1,
    "MEMORY_BOUND": 0, # <--- MAP TO 0 (Treat as COMPUTE)
    "IDLE": 3
}
REVERSE_MAP = {v: k for k, v in PHASE_MAP.items()}

# ---------------- SIMULATION ENGINE ----------------
class FastPhaseSimulator:
    def __init__(self, data_df):
        self.data = data_df.to_dict('records')
        
    def run_with_params(self, params):
        # Unpack parameters
        W_COMP_PWR  = params[0]
        W_COMP_IPC  = params[1]
        W_COMP_UTIL = params[2]
        W_COMM_NET  = params[3]
        W_COMM_LOW_U= params[4]
        W_COMM_VAR  = params[5]
        W_MEM_MISS  = params[6]
        W_MEM_DRAM  = params[7]
        
        T_NET_MBPS  = params[8]
        T_EFF_UTIL  = params[9]
        T_SYNC_VAR  = params[10]
        
        history_power = deque(maxlen=20)
        history_ipc = deque(maxlen=20)
        history_miss = deque(maxlen=20)
        phase_seq = deque(maxlen=3)
        
        predictions = []
        
        # Initial Dynamic Thresholds
        dyn_pwr_comp = 180.0
        dyn_ipc_target = 1.6
        dyn_miss_target = 0.30
        
        for row in self.data:
            # Update History
            pwr = row['pkg_power']
            ipc = row['ipc']
            miss = row['miss_rate']
            
            history_power.append(pwr)
            history_ipc.append(ipc)
            history_miss.append(miss)
            
            if len(history_power) >= 20:
                dyn_pwr_comp = np.percentile(history_power, 75) * 0.90
                dyn_ipc_target = np.percentile(history_ipc, 75)
                dyn_miss_target = np.percentile(history_miss, 75)

            # Calculate Scores
            comp_score = 0.0
            comm_score = 0.0
            mem_score = 0.0
            
            if pwr > dyn_pwr_comp: comp_score += W_COMP_PWR
            if ipc > dyn_ipc_target: comp_score += W_COMP_IPC
            if row['cpu_util_eff'] > T_EFF_UTIL: comp_score += W_COMP_UTIL
            
            total_net = row['net_rx'] + row['net_tx']
            if total_net > T_NET_MBPS: comm_score += W_COMM_NET
            
            if row['cpu_util_eff'] < 40.0 and pwr > 50: comm_score += W_COMM_LOW_U
            
            if row['sync_var'] > T_SYNC_VAR: comm_score += W_COMM_VAR
            
            if ipc < 1.0 and miss > dyn_miss_target: mem_score += W_MEM_MISS
            if row['dram_power'] > 10.0: mem_score += W_MEM_DRAM
            
            # Decision
            if pwr < 50.0 and row['cpu_util_eff'] < 10:
                raw_phase = PHASE_MAP["IDLE"]
            elif mem_score > 2.0:
                raw_phase = PHASE_MAP["MEMORY_BOUND"]
            elif comm_score > comp_score:
                raw_phase = PHASE_MAP["COMMUNICATION"]
            else:
                raw_phase = PHASE_MAP["COMPUTE"]
                
            # Stabilization
            phase_seq.append(raw_phase)
            final_phase = raw_phase
            if len(phase_seq) >= 3:
                counts = Counter(list(phase_seq))
                most_common = counts.most_common(1)[0]
                if most_common[1] >= 2 and most_common[0] != raw_phase:
                    final_phase = most_common[0]
            
            predictions.append(final_phase)
            
        return predictions

# ---------------- OPTIMIZATION LOOP ----------------

def load_data():
    print("Loading data...")
    try:
        df_log = pd.read_csv("monitor_new.csv")
        df_truth = pd.read_csv("ground_truth.csv")
    except FileNotFoundError:
        print("[ERROR] Files not found! Check directory.")
        return pd.DataFrame()

    # 1. Force numeric and Sort
    df_log['timestamp'] = pd.to_numeric(df_log['timestamp'])
    df_truth['timestamp'] = pd.to_numeric(df_truth['timestamp'])
    df_log = df_log.sort_values('timestamp')
    df_truth = df_truth.sort_values('timestamp')

    # 2. DEBUG: Check raw data density
    print(f"  Raw Log Samples: {len(df_log)}")
    print(f"  Raw Truth Samples: {len(df_truth)}")
    
    if len(df_truth) > 0:
        duration = df_truth['timestamp'].iloc[-1] - df_truth['timestamp'].iloc[0]
        print(f"  Ground Truth Duration: {duration:.2f}s")

    # 3. ALIGNMENT (Relaxed: No Stability Filter)
    # We simply look backward to find the state active at the sampling moment.
    # We still shift -0.1s to center the 0.2s window.
    df_log['ts_aligned'] = df_log['timestamp'] - 0.1
    
    df_merged = pd.merge_asof(df_log, 
                              df_truth, 
                              left_on='ts_aligned',
                              right_on='timestamp', 
                              direction='backward',
                              suffixes=('_log', '_truth'))
    
    # 4. Cleanup
    df_merged = df_merged.dropna(subset=['actual_phase'])
    df_merged['truth_encoded'] = df_merged['actual_phase'].map(PHASE_MAP)
    df_merged = df_merged.dropna(subset=['truth_encoded'])
    
    print(f"Alignment: Successfully matched {len(df_merged)} samples.")
    
    # 5. Debug Sample
    if len(df_merged) > 0:
        print("\n--- DATA SAMPLE ---")
        print(df_merged[['phase', 'actual_phase', 'pkg_power', 'net_rx']].head(5))
    
    return df_merged
def objective_function(params, simulator, ground_truth):
    preds = simulator.run_with_params(params)
    correct = np.sum(np.array(preds) == ground_truth)
    accuracy = correct / len(ground_truth)
    return -accuracy 

def run_optimization():
    df = load_data()
    if df.empty or len(df) < 10:
        print("[ERROR] Not enough data after purification. Check if miniMD ran long enough.")
        return

    simulator = FastPhaseSimulator(df)
    ground_truth = df['truth_encoded'].values
    
    bounds = [
        (0.5, 5.0), (0.5, 5.0), (0.5, 5.0), # Weights Comp
        (0.5, 5.0), (0.5, 5.0), (0.5, 5.0), # Weights Comm
        (0.5, 5.0), (0.5, 5.0),             # Weights Mem
        (5.0, 100.0), # T_NET_MBPS 
        (50.0, 95.0), # T_EFF_UTIL 
        (2.0, 50.0),  # T_SYNC_VAR 
    ]
    
    print("Starting Optimization...")
    
    result = differential_evolution(
        objective_function, 
        bounds, 
        args=(simulator, ground_truth),
        strategy='best1bin',
        maxiter=50,       
        popsize=20,       
        polish=False,     # Disable polish to handle integer logic better
        disp=True,
        workers=-1
    )
    
    print("\n---------------- RESULTS ----------------")
    acc = -result.fun * 100
    print(f"Best Accuracy Achieved: {acc:.2f}%")
    
    print("\nOptimal Parameters (Copy these to your IntelligentMonitorv17.py):")
    names = [
        "W_COMP_PWR", "W_COMP_IPC", "W_COMP_UTIL", 
        "W_COMM_NET", "W_COMM_LOW_U", "W_COMM_VAR", 
        "W_MEM_MISS", "W_MEM_DRAM", "T_NET_MBPS", 
        "T_EFF_UTIL", "T_SYNC_VAR"
    ]
    for name, val in zip(names, result.x):
        print(f"  {name}: {val:.4f}")

    if acc < 60.0:
        print("\n[NOTE] Accuracy is still low. This implies 'Memory Bound' and 'Compute' phases")
        print("       look identical on this hardware. Consider mapping them to the same phase.")

if __name__ == "__main__":
    run_optimization()