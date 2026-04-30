import pandas as pd

df = pd.read_csv('../book1_dump.csv', skiprows=31)
df = df.dropna(subset=['rank_count'])
df['rank_count'] = df['rank_count'].astype(int)

ranks = sorted(df['rank_count'].unique())

print("test_b = {")
for r in ranks:
    print(f"    {r}: [")
    sub = df[df['rank_count'] == r]
    for _, row in sub.iterrows():
        # energy, time, perf, power
        energy = row['baseline_energy_j']
        time = row['baseline_runtime_s']
        power = row['baseline_avg_power_w']
        perf = 0 # dummy
        print(f"        ({energy:.3f}, {time:.3f}, {perf:.3f}, {power:.3f}, 0, 0, 0),")
    print("    ],")
print("}")

print("test_c = {")
for r in ranks:
    print(f"    {r}: [")
    sub = df[df['rank_count'] == r]
    for _, row in sub.iterrows():
        energy = row['controlled_energy_j']
        time = row['controlled_runtime_s']
        power = row['controlled_avg_power_w']
        perf = 0 # dummy
        print(f"        ({energy:.3f}, {time:.3f}, {perf:.3f}, {power:.3f}, 0, 0, 0),")
    print("    ],")
print("}")
