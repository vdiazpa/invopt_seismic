# run_batch.py
# Batch runner: generates scenarios, solves risk-neutral vs CVaR across budgets,
# saves one folder per run using save_run_results().

import os
import math
import pandas as pd

from ..data_utils.data_extract import load_wecc_data_raw
from ..data_utils.structures  import as_grid_data
from ..scenarios.generate import scenario_generator
from ..scenarios.critical import critical_assets_identifier
from ..opt.inv_opt import model_build_solve
from ..results.save_results import save_run_results


# -----------------------------
# Helpers
# -----------------------------
def avg_failures_per_scenario(ds_dict: dict) -> float:
    """
    ds_dict: mapping scenario_name -> {asset_id: 0/1}
    Returns average count of failures per scenario.
    """
    if not ds_dict:
        return 0.0
    counts = []
    for _, state_map in ds_dict.items():
        counts.append(sum(1 for v in state_map.values() if int(v) == 1))
    return float(sum(counts)) / float(len(counts)) if counts else 0.0


def ceil_avg_failures(damage_states) -> dict:
    """
    damage_states is DamageData with ds_gens/ds_loads/ds_trans/ds_branch dict-of-dicts
    Returns integer avg_k_* for use_avg_k=True mode.
    """
    avg_k_g = int(math.ceil(avg_failures_per_scenario(damage_states.ds_gens)))
    avg_k_l = int(math.ceil(avg_failures_per_scenario(damage_states.ds_loads)))
    avg_k_b = int(math.ceil(avg_failures_per_scenario(damage_states.ds_branch)))

    # IMPORTANT: your file data has no transmission node failures => keep it 0
    avg_k_t = 0

    return {
        "avg_k_gens": avg_k_g,
        "avg_k_loads": avg_k_l,
        "avg_k_trans": avg_k_t,
        "avg_k_branch": avg_k_b,
    }


# -----------------------------
# Main batch
# -----------------------------
def main():
    # ========= Paths 
    results_dir = r"C:\Users\vdiazpa\Documents\quest_planning\results_fresh"
    cache_dir   = r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\cache"

    os.makedirs(results_dir, exist_ok=True)
    os.makedirs(cache_dir, exist_ok=True)

    # ========= Data 
    data = load_wecc_data_raw(
        r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\gen_data_raw.csv",
        r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\bus_data_raw.csv",
        r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\branch_data_raw_with_rateA_m_all.csv",
        load_csv=r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\load_data_raw.csv",
    )
    grid = as_grid_data(data)

    df_poly = pd.read_csv(r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\buses_inside_polygon.csv")
    bus_in_poly = df_poly.iloc[:, 0].dropna().astype(int).tolist()

    # ========= Experiment settings 
    patch = "patch"                    
    event_ids = list(range(1, 26))     # 1..25
    num_trials_files = 20

    # Core sweeps
    budgets = [5, 10, 15, 20]              # interpret as "investment budget" 
    forms = ["risk_neutral", "cvar_only"]

    # For random sampling, do a few seeds
    rand_seeds = [1]

    # Model params
    hard_frac = 0.5
    tau = 0.1
    alpha = 0.95
    lam = 100.0
    mipgap = 0.01

    # Keep these consistent for Phase 1 (you can expand later)
    add_DG = True              # or False
    add_trans_fail = False     # IMPORTANT: keep False if want "no trans failures" consistent w/ file data
    DGcap = 50.0

    # ========= 1) FILES scenario set (one scenario set, then solve multiple budgets/forms)
    print("\n==============================")
    print("1) Generating/Loading FILES damage states")
    print("==============================")

    ds_files = scenario_generator(
        mode="files",
        data=data,
        event_ids=event_ids,
        num_trials=num_trials_files,
        seed=63,                         # only used for caching/consistency; files are deterministic
        cache_dir=cache_dir,
        patch=patch,
        cache_tag=f"files_e{len(event_ids)}_tr{num_trials_files}_{patch}",
        use_cache=True)

    # Critical assets based on file scenarios
    crit_files = critical_assets_identifier(
        mode="all_in_polygon",                      
        grid=grid,
        damage_states=ds_files,         # all_in_polygon, #all, etc.
        bus_in_poly=bus_in_poly)

    # Compute avg failures from FILES to parameterize RAND_IN_POLYGON
    avgk = ceil_avg_failures(ds_files)
    print("\nAvg failures per scenario from FILES (ceiling):")
    print(avgk)

    # Solve batch for FILES
    for maxinv in budgets:
        for form in forms:
            print("\n--------------------------------------------------")
            print(f"FILES | form={form} | max_invest={maxinv}")
            print("--------------------------------------------------")

            res = model_build_solve(
                form=form,
                grid=grid,
                hard_frac=hard_frac,
                damage_states=ds_files,
                crit_assets=crit_files,
                tau=tau,
                alpha=alpha,
                lam=lam,
                add_DG=add_DG,
                DGcap = DGcap,
                add_trans_fail=add_trans_fail,
                max_invest=maxinv,
                tee=False,
                print_vars=False,
                mip_gap=mipgap,
                time_solve=True,
            )

            save_run_results(
                res,
                base_dir=results_dir,
                dataset="files",
                patch=patch,
                n_events=len(event_ids),
                n_trials=num_trials_files,
                n_samples=None,
                seed=63,
                crit_mode="all",
                form=form,
                mipgap=mipgap,
                max_invest=maxinv,
                hard_frac=hard_frac,
                alpha=alpha,
                lam=lam,
                tau=tau,
            )

    # ========= 2) RAND_IN_POLYGON scenario sets (one per seed), matched to FILES avg failures
    print("\n==============================")
    print("2) Generating/Loading RAND_IN_POLYGON damage states")
    print("==============================")

    # Choose number of random scenarios to match file scenario count
    n_rand = len(ds_files.ds_gens.keys())

    for seed in rand_seeds:
        ds_rand = scenario_generator(
            mode="rand_in_polygon",
            data=data,
            num_rand_sc=n_rand,
            bus_in_poly=bus_in_poly,
            use_avg_k=True,
            avg_k_gens=avgk["avg_k_gens"],
            avg_k_loads=avgk["avg_k_loads"],
            avg_k_trans=0,                 # IMPORTANT: enforce no trans failures
            avg_k_branch=avgk["avg_k_branch"],
            seed=seed,
            cache_dir=cache_dir,
            cache_tag=f"rand_inpoly_N{n_rand}_seed{seed}_{patch}_matchFilesAvg",
            use_cache=True)

        crit_rand = critical_assets_identifier(
            mode="all_in_polygon",
            grid=grid,
            damage_states=ds_rand,
            bus_in_poly=bus_in_poly)

        for maxinv in budgets:
            for form in forms:
                print("\n--------------------------------------------------")
                print(f"RAND_IN_POLYGON | seed={seed} | form={form} | max_invest={maxinv}")
                print("--------------------------------------------------")

                res = model_build_solve(
                    form=form,
                    grid=grid,
                    hard_frac=hard_frac,
                    damage_states=ds_rand,
                    crit_assets=crit_rand,
                    tau=tau,
                    alpha=alpha,
                    lam=lam,
                    add_DG=add_DG,
                    DGcap = DGcap,
                    add_trans_fail=add_trans_fail,
                    max_invest=maxinv,
                    tee=False,
                    print_vars=False,
                    mip_gap=mipgap,
                    time_solve=True,
                )

                save_run_results(
                    res,
                    base_dir=results_dir,
                    dataset="rand_in_polygon",
                    patch=patch,
                    n_events=len(event_ids),
                    n_trials=num_trials_files,
                    n_samples=n_rand,
                    seed=seed,
                    crit_mode="all",
                    form=form,
                    mipgap=mipgap,
                    max_invest=maxinv,
                    hard_frac=hard_frac,
                    alpha=alpha,
                    lam=lam,
                    tau=tau,
                )

    print("\nDONE. Results written under:")
    print(" ", results_dir)


if __name__ == "__main__":
    main()
