#inspect_network.py

from ..data_utils.data_extract import load_wecc_data_m, load_wecc_data_raw
from ..data_utils.structures import as_grid_data, GridData, as_damage_data, DamageData
from ..scenarios.generate import scenario_generator
from collections import defaultdict
from ..network.metrics import *
import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd

# =============================================================== Load data and scenarios
data = load_wecc_data_raw(r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\gen_data_raw.csv", 
               r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\bus_data_raw.csv", 
               r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\branch_data_raw_with_rateA_m_all.csv", 
                load_csv = r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\load_data_raw.csv" )

grid = as_grid_data(data) #Convert to GridData object
bus_in_poly = pd.read_csv(r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\buses_inside_polygon.csv").iloc[:,0].dropna().astype(int).tolist()
cache_dir = r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\cache"  # directory to save/load cached scenarios
seed  = 63  # <--------------------- Random seed for scenario generation and critical asset identification
patch = ""
event_ids = list(range(1, 26)) # <-- pick which earthquakes to inspect (example: 1..9)
num_trials_files = 10 # <----------- pick how many trials per earthquake to inspect

damage_state_files = scenario_generator(mode="files", data=data, event_ids=event_ids, 
                                        num_trials=num_trials_files, seed=seed, 
                                        cache_dir=cache_dir,
                                        cache_tag=f"files_e{len(event_ids)}_tr{num_trials_files}_seed{seed}_{patch}", 
                                        use_cache= True)

#================================================================== Analyze undamaged but disconnected loads (wrt ref)
pct_any_u, per_scen_count_u, bus_freq_u = summarize_undamaged_ref_disconnections(grid, damage_state_files)

print("\nUNDAMAGED but disconnected (wrt ref) — ALL load buses:")
print(f"Share of scenarios with >=1 undamaged disconnected load: {pct_any_u:.2%}") 

vals = list(per_scen_count_u.values())
plt.figure()
plt.hist(vals, bins=range(0, max(vals)+2))
plt.xlabel("# undamaged disconnected load buses (wrt ref)")
plt.ylabel("# scenarios")
plt.title("Undamaged-but-disconnected load buses per scenario")
plt.show()

print("\nTop 10 load buses most frequently UNDAMAGED+DISCONNECTED (wrt ref):")
for b, c in bus_freq_u.most_common(10):
    print(f"  bus {b}: {c} scenarios")

#=========================================================================To check if damage states are unique
def scen_signature(ds, s):
    # Turn each damage map into a tuple of failed asset IDs (order-independent)
    fail_loads   = tuple(sorted([k for k,v in ds.ds_loads[s].items()  if v==1]))
    fail_branch  = tuple(sorted([k for k,v in ds.ds_branch[s].items() if v==1]))
    fail_gens    = tuple(sorted([k for k,v in ds.ds_gens[s].items()   if v==1]))
    return (fail_loads, fail_branch, fail_gens)

sigs = [scen_signature(damage_state_files, s) for s in damage_state_files.ds_branch.keys()]
cnt = Counter(sigs)
print("Total scenarios:", len(sigs), "\nUnique damage states:", len(cnt), "\nMost common damage state occurs:", cnt.most_common(1)[0][1], "times" )

for sig, c in cnt.most_common(10):   # show top 10 repeated
    if c > 1:
        print("count=", c,"n_fail_loads=", len(sig[0]), "n_fail_branch=", len(sig[1]),"n_fail_gens=", len(sig[2]))

# =====================================================================To inspect scenarios with undamaged but disconnected loads
damage_states = damage_state_files

hits = []
for sname in damage_states.ds_branch.keys():

    #================ Build graph with ONLY undamaged branches (ds_branch == 0)
    G = nx.Graph()
    G.add_nodes_from([int(b) for b in grid.all_nodes])

    for l, st in damage_states.ds_branch[sname].items():
        if st == 1:  # failed branch
            continue
        i, j = grid.line_endpoints[l]
        G.add_edge(int(i), int(j))

    #==================Connected component of reference bus
    ref = int(grid.ref_bus)
    connected_to_ref = set(nx.node_connected_component(G, ref)) if ref in G else set()

    #================Precompute gen capacity per connected component
    # Map each node -> component id, and component id -> surviving gen capacity
    node_to_comp = {}
    comp_caps = {}
    comps = list(nx.connected_components(G))
    for k, comp in enumerate(comps):
        comp = set(int(x) for x in comp)

        cap = 0.0
        for n in comp:
            for g in grid.gens_by_bus.get(int(n), ()):
                if damage_states.ds_gens[sname].get(g, 0) == 0:  # surviving gen
                    cap += float(grid.unit_capacity[g])

        comp_caps[k] = cap
        for n in comp:
            node_to_comp[n] = k

    # ---- Find load buses that are:
    #   (1) undamaged load bus, (2) positive demand, (3) NOT connected to ref,  (4) in a component with ZERO surviving gen capacity
    disc_zero_gen = []
    for b in grid.nodes_load:
        b = int(b)

        if damage_states.ds_loads[sname].get(b, 0) == 1:   # damaged load -> skip
            continue
        if grid.demand.get(b, 0.0) <= 1e-6:               # no demand -> skip
            continue
        if b in connected_to_ref:                         # connected to ref -> skip
            continue

        k = node_to_comp.get(b, None)
        if k is None:
            continue

        if comp_caps[k] <= 1e-9:
            disc_zero_gen.append(b)

    if disc_zero_gen:
        disc_mw = sum(grid.demand[b] for b in disc_zero_gen)
        hits.append((sname, len(disc_zero_gen), disc_mw, disc_zero_gen))

# ======================= Print 5 scens with largest disconnected MW
hits.sort(key=lambda x: x[2], reverse=True)

print(f"Found {len(hits)} scenarios with >=1 UNDAMAGED, positive-demand load that is")
print("DISCONNECTED-from-ref AND in an island with ZERO surviving generation.\n")

for sname, nbus, mw, buses in hits[:37]:
    print(f"{sname}: {nbus} buses, {mw:.2f} MW disconnected-demand")
    print("  buses:", buses[:30], "..." if len(buses) > 30 else "")

#=====================================================================To check if failing assets are inside the polygon
# ds = damage_state_files
# S = list(ds.ds_loads.keys())

# bus_in_poly_set = set(int(b) for b in bus_in_poly)

# # -------------------------
# # 1) Loads
# # -------------------------
# nodes_load = set(int(b) for b in grid.nodes_load)
# poly_loads = nodes_load & bus_in_poly_set

# fail_loads = set()
# for b in nodes_load:
#     if any(ds.ds_loads[s].get(b, 0) == 1 for s in S):
#         fail_loads.add(b)

# print("\nLOADS:")
# print("  # load buses:", len(nodes_load))
# print("  # inside polygon:", len(poly_loads))
# print("  # ever fail:", len(fail_loads))
# print("  fail OUTSIDE polygon:", len(fail_loads - poly_loads))
# print("  inside polygon but NEVER fail:", len(poly_loads - fail_loads))
# print("  examples fail outside:", list(sorted(fail_loads - poly_loads))[:20])
# print("  examples inside never fail:", list(sorted(poly_loads - fail_loads))[:20])

# # -------------------------
# # 2) Generators (compare by bus)
# # -------------------------
# gens = list(grid.gens)

# def gen_bus(g):
#     # g is like "123_GAS" etc
#     return int(str(g).split("_")[0])

# fail_gens = set()
# for g in gens:
#     if any(ds.ds_gens[s].get(g, 0) == 1 for s in S):
#         fail_gens.add(g)

# fail_gen_buses = set(gen_bus(g) for g in fail_gens)
# poly_gen_buses = bus_in_poly_set  # buses inside polygon

# print("\nGENS:")
# print("  # gens:", len(gens))
# print("  # gens ever fail:", len(fail_gens))
# print("  # gen buses ever fail:", len(fail_gen_buses))
# print("  failing gen buses OUTSIDE polygon:", len(fail_gen_buses - poly_gen_buses))
# print("  inside polygon but NO gen bus ever fails:", len(poly_gen_buses - fail_gen_buses))
# print("  examples failing gen buses outside:", list(sorted(fail_gen_buses - poly_gen_buses))[:20])

# # -------------------------
# # 3) Branches (by endpoints)
# # -------------------------
# lines = list(grid.lines)
# line_endpoints = grid.line_endpoints

# fail_lines = set()
# for l in lines:
#     if any(ds.ds_branch[s].get(l, 0) == 1 for s in S):
#         fail_lines.add(l)

# def line_in_poly(l):
#     i, j = line_endpoints[l]
#     return (int(i) in bus_in_poly_set) or (int(j) in bus_in_poly_set)

# poly_lines = set(l for l in lines if line_in_poly(l))

# print("\nLINES:")
# print("  # lines:", len(lines))
# print("  # lines ever fail:", len(fail_lines))
# print("  # lines touching polygon:", len(poly_lines))
# print("  failing lines OUTSIDE polygon:", len(fail_lines - poly_lines))
# print("  polygon lines but NEVER fail:", len(poly_lines - fail_lines))
# print("  examples failing lines outside:", list(sorted(fail_lines - poly_lines))[:10])