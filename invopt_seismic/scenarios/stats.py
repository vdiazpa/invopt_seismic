#stats.py
import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd

def plot_failure_frequencies(
        ds_df, 
        asset_type: str, 
        freq_df=None):
    
    """Plot failure frequencies for a given asset type.ds_df is a dict with keys as scenario names and values as dicts of asset states (0/1)."""

    if not ds_df:
        print("No data to plot.")
        return

    if freq_df is None:

        fail_count = {g: 0 for g in next(iter(ds_df.values())).keys()}

        for _, asset_state in ds_df.items():
            for g, state in asset_state.items():
                if state == 1:
                    fail_count[g] += 1

        freq_df = pd.DataFrame(list(fail_count.items()), columns=[f'{asset_type}', 'Count'])
        freq_df = freq_df.sort_values(by='Count', ascending=False)

    plt.figure(figsize=(10, 6))
    plt.bar(range(len(freq_df)), freq_df['Count'])
    plt.xlabel(f'{asset_type} (bus_fueltype)')
    plt.ylabel('Failure Count')
    plt.title(f'{asset_type} Failure Frequencies Across {len(ds_df)} Samples')
    plt.xticks(ticks=range(len(freq_df)),labels=[str(g).replace('_', '-') for g in freq_df[asset_type]],rotation=90)
    plt.tight_layout()
    plt.show()

def avg_failures_per_scenario(ds_dict):

    """Calculate average number of failures per scenario from damage state dictionary."""

    if not ds_dict:
        return 0
    
    totals = []
    for _, st_map in ds_dict.items():
        totals.append(sum(1 for _, v in st_map.items() if v == 1))

    return sum(totals) / len(totals) if totals else 0

#For DER in inv_opt
def compute_islanded_undamaged_map(grid, damage_states):
    """
    Returns islanded[sname][bus] = 1 if bus is UNDAMAGED (ds_load=0)
    and NOT connected to ref bus using UNDAMAGED branches (ds_branch=0).
    """
    islanded = {}

    for sname in damage_states.ds_branch.keys():
        G = nx.Graph()
        G.add_nodes_from([int(b) for b in grid.all_nodes])

        for l in grid.lines:
            if damage_states.ds_branch[sname].get(l, 0) == 1:
                continue
            i, j = grid.line_endpoints[l]
            G.add_edge(int(i), int(j))

        ref = int(grid.ref_bus)
        connected = set(nx.node_connected_component(G, ref)) if ref in G else set()

        islanded[sname] = {}
        for b in grid.nodes_load:
            b = int(b)
            undamaged = (damage_states.ds_loads[sname].get(b, 0) == 0)
            islanded[sname][b] = int(undamaged and (b not in connected))

    return islanded

