#network_utils.py

from ..data_utils.structures import GridData, DamageData
from .metrics import islanding_count_by_bus, island_count_per_scenario
import matplotlib.pyplot as plt
import networkx as nx
import os

def plot_island_histogram(grid: GridData, ds: DamageData, bins=None):
    island_counts = island_count_per_scenario(grid, ds)
    values = list(island_counts.values())

    plt.figure()
    plt.hist(values, bins=bins if bins is not None else range(1, max(values) + 2))
    plt.xlabel("Number of islands (connected components)")
    plt.ylabel("Number of scenarios")
    plt.title("Island count distribution across damage scenarios")
    plt.show()

def plot_scenario_graph(
    grid: GridData,
    damage_states: DamageData,
    scenario,
    save_dir=None,
    tag=None,
    show=True,
):
    """
    Plot the network graph for a given damage scenario.
    If save_dir is provided, saves the figure instead of (or in addition to) showing it.
    """

    G = nx.Graph()
    G.add_nodes_from(grid.all_nodes)

    # 1 = failed, 0 = active
    active_lines = [ l for l, s in damage_states.ds_branch[scenario].items() if s == 0]

    for l in active_lines:
        i, j = grid.line_endpoints[l]
        G.add_edge(i, j)

    plt.figure(figsize=(8, 8))
    nx.draw( G,node_size=10,with_labels=False,width=0.5)
    plt.title(f"Scenario {scenario}")

    if save_dir is not None:
        os.makedirs(save_dir, exist_ok=True)
        fname = f"network_{scenario}"
        if tag is not None:
            fname += f"_{tag}"
        fname += ".png"
        plt.savefig(os.path.join(save_dir, fname), dpi=300, bbox_inches="tight")

    if show:
        plt.show()
    else:
        plt.close()

def plot_islanding_count_histogram(grid, damage_states, bus_in_poly, bins=30):
    counts = islanding_count_by_bus(grid, damage_states, bus_in_poly)
    values = list(counts.values())

    plt.figure(figsize=(7, 5))
    plt.hist(values, bins=bins, edgecolor="black")
    plt.xlabel("Number of scenarios bus is islanded")
    plt.ylabel("Number of buses (inside polygon)")
    plt.title("Islanding count per bus (polygon buses)")
    plt.grid(axis="y", alpha=0.3)
    plt.show()

    return counts

def print_top_islanded_buses_by_count(counts, top_k=20):
    items = sorted(counts.items(), key = lambda x: x[1], reverse=True)[:top_k]
    print(f"Top {top_k} polygon buses by isl;anding count:")
    for b, c in items:
        print(f"  bus {b}: islanded in {c} scenarios")




