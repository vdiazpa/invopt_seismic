#single_run.py

from ..data_utils.data_extract import load_wecc_data_raw
from ..data_utils.structures  import as_grid_data
from ..scenarios.generate import generate_from_MC, generate_from_bernoulli
from ..scenarios.critical import critical_assets_identifier
from ..opt.inv_opt import model_build_solve
from ..results.save_results import save_run_results
import pandas as pd
import math
import os

def main():

    # =============================================== Paths 
    results_dir = r"C:\Users\vdiazpa\Documents\quest_planning\results_fresh"
    cache_dir   = r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\cache"

    os.makedirs(results_dir, exist_ok=True)
    os.makedirs(cache_dir,   exist_ok=True)

  # =============================================== Data 
    data = load_wecc_data_raw(
        r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\gen_data_raw.csv",
        r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\bus_data_raw.csv",
        r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\branch_data_raw_with_rateA_m_all.csv",
        load_csv=r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\load_data_raw.csv",
    )
    grid = as_grid_data(data)
    df_poly = pd.read_csv(r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\buses_inside_polygon.csv")
    bus_in_poly = df_poly.iloc[:, 0].dropna().astype(int).tolist()


    # =============================================== Experiment settings 
    patch = "patch"   
    event_ids = list(range(1, 26))     # 1..25
    num_trials_files = 20
    hard_frac = 0.5
    tau = 0.1    
    max_inv = 5
    add_DG = True              # or False
    add_trans_fail = False     # IMPORTANT: keep False if want "no trans failures" consistent w/ file data
    DGcap = 50.0
    seed = 1
    form = "cvar_only"  # "risk_neutral" # #  #  

    print("\n===============================================")
    print("1) Generating/Loading FILES damage states")
    print("===============================================")

    ds_MC = generate_from_MC(data=data,event_ids=event_ids,num_trials=num_trials_files,
        cache_dir=cache_dir,
        patch=patch,
        cache_tag=f"files_e{len(event_ids)}_tr{num_trials_files}_{patch}",
        use_cache=True)

    ds_bern=generate_from_bernoulli(data=data,event_ids=event_ids,num_trials=num_trials_files,
        num_rand_sc= 500,
        cache_dir=cache_dir,
        patch=patch,
        cache_tag=f"files_e{len(event_ids)}_tr{num_trials_files}_{patch}",
        use_cache=True)
    
    crit = critical_assets_identifier(mode="all_in_polygon", grid=grid, bus_in_poly=bus_in_poly, damage_states=ds_MC)

    res_MC = model_build_solve(
            form=form,
            grid=grid,
            hard_frac=hard_frac,
            damage_states=ds_MC,
            crit_assets=crit,
            add_DG=add_DG,
            DGcap=DGcap,
            add_trans_fail=add_trans_fail,
            max_invest=max_inv,
            tee=False,
            print_vars=True,
            time_solve=True,
        )
    
    res_bern = model_build_solve(
            form=form,
            grid=grid,
            hard_frac=hard_frac,
            damage_states=ds_bern,
            crit_assets=crit,
            add_DG=add_DG,
            DGcap=DGcap,
            add_trans_fail=add_trans_fail,
            max_invest=max_inv,
            tee=False,
            print_vars=True,
            time_solve=True,
        )

if __name__ == "__main__":
    main()


