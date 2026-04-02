#run_experiment.py
from ..scenarios.generate import scenario_generator
from ..scenarios.critical import critical_assets_identifier
from ..scenarios.stats import plot_failure_frequencies, avg_failures_per_scenario
from ..data_utils.structures import as_grid_data, GridData, as_damage_data, DamageData
from ..results.save_results import save_run_results
from ..data_utils.data_extract import load_wecc_data_raw
from ..opt.inv_opt import model_build_solve
from itertools import tee
import matplotlib.pyplot as plt
import pandas as pd, sys
sys.path.insert(0, "C:\\Users\\vdiazpa\\mpi-sppy")
import logging
logging.basicConfig(level=logging.INFO, force=True)

#=============================================================================== Load Data 

data = load_wecc_data_raw(r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\gen_data_raw.csv", 
               r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\bus_data_raw.csv", 
               r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\branch_data_raw_with_rateA_m_all.csv", 
                load_csv = r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\load_data_raw.csv" )

grid = as_grid_data(data)

#========================================================================== Experimental Parameters 

seed  = 63  # <--------------------- Random seed for scenario generation and critical asset identification
event_ids = list(range(1, 26)) # <-- pick which earthquakes to inspect (example: 1..9)
num_trials_files = 10 # <----------- pick how many trials per earthquake to inspect
hard_frac = 0.5 # <----------------- Percent of substation capital cost to consider as hardening cost
alpha = 0.975 # <------------------- For 'cvar_constr' formulation: 1-alpha confidence level for CVaR
lam = 1.0  # <---------------------- For 'cvar_constr' formulation: weight of CVaR in objective
tau   = 0.1  # <-------------------- For 'hard_resil'  formulation: Resilience parameter; percent of total load that must be served after earthquake realization
tee = False  # <-------------------- print solver output?
opt_gap = 0.01 # <------------------ MIP optimality gap for solver
max_invest = 2 # <------------------ max investment budget (optional)
patch = "patch"

cache_dir = r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\cache"  # directory to save/load cached scenarios
df = pd.read_csv(r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\buses_inside_polygon.csv")
bus_in_poly = df.iloc[:,0].dropna().astype(int).tolist()
generate_plots = False

def plot_hist(d, title:str, xlabel:str, nbins=30 ):
    plt.figure()
    plt.hist(d, bins=nbins)
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel("Count")
    plt.show()

# bgts = [1,2,3,4,5]
# patches = ["", "patch"]

# bgts = [None]
# patches = [""]

# lambdas = [0.1, 1.0, 10.0, 100.0]

# for lam in lambdas:   
#     for max_invest in bgts:
#         for patch in patches:
                
#             ## ============================================================================= MC Run 

#             #1) Read file data, will cache if possble
#             damage_state_files = scenario_generator(mode="files", data=data, event_ids=event_ids, 
#                                                                 num_trials=num_trials_files, seed=seed, 
#                                                                 cache_dir=cache_dir,
#                                                                 patch=patch,
#                                                                 cache_tag=f"files_e{len(event_ids)}_tr{num_trials_files}_seed{seed}_{patch}")
#             if generate_plots:
#                 # ---- A) Distribution of # failures per scenario (histogram)
#                 def failures_per_scenario(ds_dict):
#                     return [sum(v == 1 for v in state_map.values()) for state_map in ds_dict.values()]
                
#                 # ---- B) Failure frequencies per asset across all loaded file scenarios
#                 plot_failure_frequencies(damage_state_files.ds_gens, asset_type="Generator")
#                 plot_failure_frequencies(damage_state_files.ds_loads, asset_type="Load")
#                 plot_failure_frequencies(damage_state_files.ds_branch, asset_type="Branch")

#                 gen_fail_counts  = failures_per_scenario(damage_state_files.ds_gens)
#                 load_fail_counts = failures_per_scenario(damage_state_files.ds_loads)
#                 br_fail_counts   = failures_per_scenario(damage_state_files.ds_branch)

#                 plt_hist(gen_fail_counts, title ="Generators: # failures per scenario (from files)", xlabel = "# failed generators", nbins=30)
#                 plt_hist(load_fail_counts, title ="Loads: # failures per scenario (from files)", xlabel = "# failed loads", nbins=30)
#                 plt_hist(br_fail_counts, title ="Branches: # failures per scenario (from files)", xlabel = "# failed branches", nbins=30)

#             # 2) Pick critical assets
            # crit_assets_files = critical_assets_identifier(mode = "all_in_polygon", grid=grid, damage_states = damage_state_files, bus_in_poly=bus_in_poly)

#             # 3) Build & Solve
#             res_rn_f   = model_build_solve(
#                 form ="risk_neutral", grid = grid, hard_frac=hard_frac, 
#                 damage_states = damage_state_files, 
#                 crit_assets = crit_assets_files, 
#                 time_solve = True, tee = tee, print_vars = True, mip_gap=opt_gap,
#                 max_invest = max_invest)

#             results_dir = r"C:\Users\vdiazpa\Documents\quest_planning\results"

#             save_run_results(
#                 res_rn_f,
#                 base_dir=results_dir,

#                 # ---- identification ----
#                 dataset="files",
#                 patch=patch,
#                 n_events=len(event_ids),
#                 n_trials=num_trials_files,
#                 n_samples=None,
#                 seed=seed,
#                 crit_mode="all_in_polygon",

#                 # ---- model / solver ----
#                 form="risk_neutral",
#                 mipgap=opt_gap,
#                 max_invest=max_invest,
#                 hard_frac=hard_frac,
#                 alpha=alpha,
#                 lam=lam,
#                 tau=tau)

#             res_cvar_f = model_build_solve(form="cvar_only", grid=grid, hard_frac=hard_frac, damage_states=damage_state_files, crit_assets = crit_assets_files,
#                                             alpha=alpha, lam = lam, tee = tee, print_vars = True, mip_gap=opt_gap, max_invest = max_invest)

#             save_run_results(
#                 res_cvar_f,
#                 base_dir=results_dir,

#                 # ---- identification ----
#                 dataset="files",
#                 patch=patch,
#                 n_events=len(event_ids),
#                 n_trials=num_trials_files,
#                 n_samples=None,
#                 seed=seed,
#                 crit_mode="all_in_polygon",

#                 # ---- model / solver ----
#                 form="cvar_only",
#                 mipgap=opt_gap,
#                 max_invest=max_invest,
#                 hard_frac=hard_frac,
#                 alpha=alpha,
#                 lam=lam,
#                 tau=tau)


#             # # Get avg # of failures in fille data for random generation
#             # avg_k_g = math.ceil(avg_failures_per_scenario(damage_state_files.ds_gens)) 
#             # avg_k_l = math.ceil(avg_failures_per_scenario(damage_state_files.ds_loads))
#             # avg_k_t = math.ceil(avg_failures_per_scenario(damage_state_files.ds_trans))
#             # avg_k_b = math.ceil(avg_failures_per_scenario(damage_state_files.ds_branch))
#             # print( "Ceil(avg failures per scenario) from files:" ,"\n  avg_k_gens  =", avg_k_g,"\n  avg_k_loads =", avg_k_l, "\n  avg_k_trans =", avg_k_t, "\n  avg_k_branch=", avg_k_b)

#             # ## ============================================================================= Random-in-polygon Run

#             # #1)  call scenario_generator using random for validation. 
#             # damage_states_random = scenario_generator(
#             #     mode="rand_in_polygon", 
#             #     data=data,
#             #     num_rand_sc=len(event_ids)*num_trials_files, 
#             #     bus_in_poly=bus_in_poly, 
#             #     use_avg_k=True,
#             #     avg_k_gens=avg_k_g,avg_k_loads=avg_k_l, avg_k_trans=avg_k_t,avg_k_branch=avg_k_b,
#             #     seed=seed, 
#             #     cache_dir=cache_dir,
#             #     cache_tag=f"rand_inpoly_N{len(event_ids)*num_trials_files}_seed{seed}_{patch}")

#             # if generate_plots:
#             #     plot_failure_frequencies(damage_states_random.ds_gens, asset_type="Generator")
#             #     plot_failure_frequencies(damage_states_random.ds_loads, asset_type="Load")
#             #     plot_failure_frequencies(damage_states_random.ds_branch, asset_type="Branch")

#             #     gen_fail_counts  = failures_per_scenario(damage_states_random.ds_gens)
#             #     load_fail_counts = failures_per_scenario(damage_states_random.ds_loads)
#             #     br_fail_counts   = failures_per_scenario(damage_states_random.ds_branch)

#             #     plt_hist(gen_fail_counts, title ="Generators: # failures per scenario (from files)", xlabel = "# failed generators", nbins=30)
#             #     plt_hist(load_fail_counts, title ="Loads: # failures per scenario (from files)", xlabel = "# failed loads", nbins=30)
#             #     plt_hist(br_fail_counts, title ="Branches: # failures per scenario (from files)", xlabel = "# failed branches", nbins=30)

#             # # 2) Pick critical assets
#             # crit_assets_random = critical_assets_identifier(
#             #     mode = "all_in_polygon", 
#             #     grid=grid, 
#             #     damage_states=damage_states_random,
#             #     frac_gens=0.25, frac_loads=0.25, frac_trans=0.25,  bus_in_poly=bus_in_poly)

#             # # 3) Build & Solve
#             # res_rn_r   = model_build_solve(form ="risk_neutral", grid = grid, hard_frac=hard_frac, 
#             #                             damage_states = damage_states_random, 
#             #                             crit_assets = crit_assets_random, 
#             #                             tau=tau, 
#             #                             time_solve = True, tee = tee, print_vars = True, mip_gap=opt_gap, 
#             #                             max_invest=max_invest)

#             # save_run_results(
#             #     res_rn_r,
#             #     base_dir=results_dir,

#             #     # ---- identification ----
#             #     dataset="rand_in_polygon",
#             #     patch=patch,
#             #     n_events=len(event_ids),
#             #     n_trials=num_trials_files,
#             #     n_samples=None,
#             #     seed=seed,
#             #     crit_mode="all_in_polygon",

#             #     # ---- model / solver ----
#             #     form="risk_neutral",
#             #     mipgap=opt_gap,
#             #     max_invest=max_invest,
#             #     hard_frac=hard_frac,
#             #     alpha=alpha,
#             #     lam=lam,
#             #     tau=tau)

#             # res_cvar_r = model_build_solve(form ="cvar_only", grid = grid, hard_frac=hard_frac, 
#             #                             damage_states = damage_states_random, 
#             #                             crit_assets = crit_assets_random,
#             #                             alpha=alpha, lam=lam, 
#             #                             time_solve = True, tee = tee, print_vars = True, mip_gap=opt_gap, 
#             #                             max_invest=max_invest)

#             # save_run_results(
#             #     res_cvar_r,
#             #     base_dir=results_dir,

#             #     # ---- identification ----
#             #     dataset="rand_in_polygon",
#             #     patch=patch,
#             #     n_events=len(event_ids),
#             #     n_trials=num_trials_files,
#             #     n_samples=None,
#             #     seed=seed,
#             #     crit_mode="all_in_polygon",

#             #     # ---- model / solver ----
#             #     form="cvar_only",
#             #     mipgap=opt_gap,
#             #     max_invest=max_invest,
#             #     hard_frac=hard_frac,
#             #     alpha=alpha,
#             #     lam=lam,
#             #     tau=tau)

#1) Create/Load the damage states
damage_state_files = scenario_generator(mode="files", data=data, event_ids=event_ids, 
                                                    num_trials=num_trials_files, seed=seed, 
                                                    cache_dir=cache_dir,
                                                    patch=patch,
                                                    cache_tag=f"files_e{len(event_ids)}_tr{num_trials_files}_seed{seed}_{patch}")

if generate_plots:
    # ---- A) Distribution of # failures per scenario (histogram)
    def failures_per_scenario(ds_dict):
        return [sum(v == 1 for v in state_map.values()) for state_map in ds_dict.values()]
    
    # ---- B) Failure frequencies per asset across all loaded file scenarios
    plot_failure_frequencies(damage_state_files.ds_gens, asset_type="Generator")
    plot_failure_frequencies(damage_state_files.ds_loads, asset_type="Load")
    plot_failure_frequencies(damage_state_files.ds_branch, asset_type="Branch")

    gen_fail_counts  = failures_per_scenario(damage_state_files.ds_gens)
    load_fail_counts = failures_per_scenario(damage_state_files.ds_loads)
    br_fail_counts   = failures_per_scenario(damage_state_files.ds_branch)

    plot_hist(gen_fail_counts, title ="Generators: # failures per scenario (from files)", xlabel = "# failed generators", nbins=30)
    plot_hist(load_fail_counts, title ="Loads: # failures per scenario (from files)", xlabel = "# failed loads", nbins=30)
    plot_hist(br_fail_counts, title ="Branches: # failures per scenario (from files)", xlabel = "# failed branches", nbins=30)


# 2) Pick critical assets ==========================================
crit_assets_files = critical_assets_identifier(mode = "all", grid=grid, damage_states = damage_state_files, bus_in_poly=bus_in_poly)


# 3) Build & Solve ==================================================



from pyomo.environ import value


def _get_scenario_block(ef_model, sname: str):
    try:
        return getattr(ef_model, sname)
    except AttributeError as e:
        # Helpful debug: show a few candidate blocks
        cand = [c for c in dir(ef_model) if "scen" in c.lower()][:20]
        raise AttributeError(
            f"Could not find scenario block '{sname}' on ef_model. "
            f"Scenario name may not be a valid attribute. "
            f"First few ef_model attributes containing 'scen': {cand}"
        ) from e


def compute_physical_vs_operational_unserved(grid, damage_states, crit_assets, ef_model):

    # --- scenario names (use your DamageData keys; they match your EF scenario names)
    scenario_names = [str(s) for s in damage_states.ds_loads.keys()]
    if not scenario_names:
        raise ValueError("No scenarios found in damage_states.ds_loads")

    # --- read root investment decisions from ANY scenario (non-anticipative)
    any_s = scenario_names[0]
    any_blk = _get_scenario_block(ef_model, any_s)

    # DistSSInvest exists for critical load buses
    dist_inv = {b: int(round(value(any_blk.DistSSInvest[b]))) for b in crit_assets.loads}

    # --- compute per-scenario totals + decomposition
    rows = []
    for s in scenario_names:
        blk = _get_scenario_block(ef_model, s)

        # Total unserved from scenario expression (this is the key fix vs gather_var_values)
        total_unserved = float(value(blk.TotalShed))

        # Physical forced unserved from damage + whether you hardened that load bus
        ds_load_s = damage_states.ds_loads[s]  # dict: bus -> 0/1
        physical = 0.0
        for bus in grid.nodes_load:
            D = grid.demand[bus]
            ds = ds_load_s.get(bus, 0)
            if ds == 0:
                continue
            if bus in crit_assets.loads:
                inv = dist_inv.get(bus, 0)
                physical += D * ds * (1 - inv)
            else:
                physical += D * ds

        operational = total_unserved - physical
        # numerical noise clamp
        if operational < 0 and abs(operational) < 1e-6:
            operational = 0.0

        rows.append((s, total_unserved, physical, operational))

    return rows


def print_top_tail(rows, k=20):
    """
    Sort by total_unserved descending and print top-k.
    """
    rows_sorted = sorted(rows, key=lambda x: x[1], reverse=True)
    print("scenario | total_unserved(MW) | physical_forced(MW) | operational_residual(MW)")
    for s, tot, phys, oper in rows_sorted[:k]:
        print(f"{s:>15} | {tot:17.2f} | {phys:18.2f} | {oper:23.2f}")


def sanity_check_no_negative_oper(rows, tol=1e-4):
    """
    In your current model, TotalShed should be >= physical forced unserved (up to small tolerance).
    Prints violations if any.
    """
    bad = [(s, tot, phys, oper) for (s, tot, phys, oper) in rows if tot + tol < phys]
    print("Violations where total_unserved < physical_forced:", len(bad))
    if bad:
        print("Example violation:", bad[0])


# ---------------- Example usage ----------------
# rows = compute_physical_vs_operational_unserved(grid, damage_state_files, crit_assets_files, res_rn_f["ef"])
# print_top_tail(rows, k=20)
# sanity_check_no_negative_oper(rows)


res_rn_f = model_build_solve(
    form="risk_neutral",                  #cvar_only, risk_neutral, hard_resil
    grid=grid, hard_frac=hard_frac, 
    damage_states=damage_state_files, 
    crit_assets=crit_assets_files, 
    max_invest=5, 
    tee=tee, 
    print_vars=True,
    add_trans_fail=True,
    mip_gap=opt_gap, 
    add_DG=True)

res_rn_f = model_build_solve(
    form="cvar_only",                  #cvar_only, risk_neutral, hard_resil
    grid=grid, hard_frac=hard_frac, 
    damage_states=damage_state_files, 
    crit_assets=crit_assets_files, 
    max_invest=5, 
    tee=tee, 
    print_vars=True,
    add_trans_fail=True,
    mip_gap=opt_gap, 
    add_DG=True)

# rows = compute_physical_vs_operational_unserved(grid, damage_state_files, crit_assets_files, res_rn_f["ef"])
# print_top_tail(rows, k=20)
# sanity_check_no_negative_oper(rows)

res_rn_f = model_build_solve(
    form="risk_neutral",                  #cvar_only, risk_neutral, hard_resil
    grid=grid, hard_frac=hard_frac, 
    damage_states=damage_state_files, 
    crit_assets=crit_assets_files, 
    max_invest=15, 
    tee=tee, 
    print_vars=True,
    add_trans_fail=True,
    mip_gap=opt_gap, 
    add_DG=True)

res_rn_f = model_build_solve(
    form="cvar_only",                  #cvar_only, risk_neutral, hard_resil
    grid=grid, hard_frac=hard_frac, 
    damage_states=damage_state_files, 
    crit_assets=crit_assets_files, 
    max_invest=15, 
    tee=tee, 
    print_vars=True,
    add_trans_fail=True,
    mip_gap=opt_gap, 
    add_DG=True)

res_rn_f = model_build_solve(
    form="risk_neutral",                  #cvar_only, risk_neutral, hard_resil
    grid=grid, hard_frac=hard_frac, 
    damage_states=damage_state_files, 
    crit_assets=crit_assets_files, 
    max_invest=25, 
    tee=tee, 
    print_vars=True,
    add_trans_fail=True,
    mip_gap=opt_gap, 
    add_DG=True)

res_rn_f = model_build_solve(
    form="cvar_only",                  #cvar_only, risk_neutral, hard_resil
    grid=grid, hard_frac=hard_frac, 
    damage_states=damage_state_files, 
    crit_assets=crit_assets_files, 
    max_invest=25, 
    tee=tee, 
    print_vars=True,
    add_trans_fail=True,
    mip_gap=opt_gap, 
    add_DG=True)