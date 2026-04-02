#metrics.py

from .graph import build_nx_graph_from_ds
from ..data_utils.structures import GridData, DamageData
from collections import Counter
import networkx as nx


def island_count_per_scenario(grid: GridData, ds: DamageData):
    """
    Returns a dict: scenario -> number of connected components
    """
    island_counts = {}

    for scen in ds.ds_branch:
        G = build_nx_graph_from_ds(grid, ds, scenario=scen)
        island_counts[scen] = nx.number_connected_components(G)

    return island_counts

def count_islanded_scenarios(grid: GridData, ds:DamageData):
    zero_count = 0
    total = 0

    for scen in ds.ds_branch:
        total+=1
        G = build_nx_graph_from_ds(grid, ds, scenario=scen)

        if nx.number_connected_components(G) > 1:
            zero_count+=1

    return zero_count, total

def disconnected_undamaged_loads_wrt_ref(grid: GridData, ds: DamageData, scen: str, restrict_to=None):
    """
    Returns a list of load buses that:
      (i) are NOT connected to the ref bus component, AND
      (ii) have ds_loads[bus] == 0 (i.e., load is NOT damaged / should be serviceable)
    """
    G = build_nx_graph_from_ds(grid, ds, scenario=scen)

    reachable = nx.node_connected_component(G, grid.ref_bus)

    loads = grid.nodes_load
    if restrict_to is not None:
        restrict_to = set(restrict_to)
        loads = [b for b in loads if b in restrict_to]

    undamaged_disconnected = []
    for b in loads:
        if b in reachable:
            continue
        # NOTE: in your damage object ds.ds_loads[scen] is a dict bus->0/1
        if ds.ds_loads[scen].get(b, 0) == 0:
            undamaged_disconnected.append(b)

    return undamaged_disconnected

def disconnected_loads_wrt_ref(grid: GridData, ds: DamageData, scen: str, restrict_to=None):
    """
    Returns a list of load buses that are NOT connected to grid.ref_bus
    in scenario `scen`, after removing failed branches (using your existing graph builder).
   
    restrict_to: optional set/list of buses; if given, only check those buses.
                (useful if you only care about polygon buses)
    """
    G = build_nx_graph_from_ds(grid, ds, scenario=scen)

    # nodes reachable from the reference bus
    # (if ref_bus exists as a node, this always works even if isolated)
    reachable = nx.node_connected_component(G, grid.ref_bus)

    loads = grid.nodes_load
    if restrict_to is not None:
        restrict_to = set(restrict_to)
        loads = [b for b in loads if b in restrict_to]

    disconnected = [b for b in loads if b not in reachable]
    return disconnected

def summarize_ref_disconnections(grid: GridData, ds: DamageData, restrict_to=None):
    """
    Loop all scenarios and compute:
      - % scenarios with >=1 disconnected load bus (wrt ref)
      - histogram of number of disconnected load buses per scenario
      - top buses most frequently disconnected
    """
    scen_names = list(ds.ds_branch.keys())

    per_scen_count = {}
    bus_freq = Counter()
    scenarios_with_any = 0

    for s in scen_names:
        disc = disconnected_loads_wrt_ref(grid, ds, s, restrict_to=restrict_to)
        per_scen_count[s] = len(disc)
        if len(disc) > 0:
            scenarios_with_any += 1
        bus_freq.update(disc)

    pct_any = scenarios_with_any / len(scen_names) if scen_names else 0.0
    return pct_any, per_scen_count, bus_freq

def islanding_count_by_bus(grid, damage_states, bus_in_poly):
    """
    Returns a dict: bus_id -> number of scenarios where the bus is islanded
    (i.e., NOT in the largest connected component).
    """

    islanded_count = {b: 0 for b in bus_in_poly}

    for sc in damage_states.ds_branch:
        # Build graph for this scenario
        G = nx.Graph()
        G.add_nodes_from(grid.all_nodes)

        # 0 = active line, 1 = failed
        for l, s in damage_states.ds_branch[sc].items():
            if s == 0:
                i, j = grid.line_endpoints[l]
                G.add_edge(i, j)

        # Largest connected component
        components = list(nx.connected_components(G))
        main_comp = max(components, key=len)

        # Count islanding for polygon buses
        for b in bus_in_poly:
            if b not in main_comp:
                islanded_count[b] += 1

    return islanded_count

def summarize_undamaged_ref_disconnections(grid: GridData, ds: DamageData, restrict_to=None):
    """
    Summarize undamaged-but-disconnected load buses (wrt ref bus).
    """
    scen_names = list(ds.ds_branch.keys())

    per_scen_count = {}
    bus_freq = Counter()
    scenarios_with_any = 0

    for s in scen_names:
        disc = disconnected_undamaged_loads_wrt_ref(grid, ds, s, restrict_to=restrict_to)
        per_scen_count[s] = len(disc)
        if len(disc) > 0:
            scenarios_with_any += 1
        bus_freq.update(disc)

    pct_any = scenarios_with_any / len(scen_names) if scen_names else 0.0
    return pct_any, per_scen_count, bus_freq

