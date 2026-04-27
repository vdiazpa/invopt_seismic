#batch_runs.py

from ..scenarios.generate import generate_from_MC, generate_from_bernoulli
from ..scenarios.critical import critical_assets_identifier
from ..data_utils.data_extract import load_wecc_data_raw
from ..results.save_results import save_run_results
from ..data_utils.structures  import as_grid_data
from ..opt.inv_opt import model_build_solve
import pandas as pd
import os

def main():

    bar = "===============================================" # Paths 
    results_dir = r"C:\Users\vdiazpa\Documents\quest_planning\results_fresh"
    cache_dir   = r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\cache"
    os.makedirs(results_dir, exist_ok=True)
    os.makedirs(cache_dir,   exist_ok=True)

    # ================================================================= Data 
    data = load_wecc_data_raw(
        r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\gen_data_raw.csv",
        r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\bus_data_raw.csv",
        r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\branch_data_raw_with_rateA_m_all.csv",
        load_csv=r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\load_data_raw.csv",
    )
    grid = as_grid_data(data)
    df_poly = pd.read_csv(r"C:\Users\vdiazpa\Documents\SEISMIC\miniWECC_data\buses_inside_polygon.csv")
    bus_in_poly = df_poly.iloc[:, 0].dropna().astype(int).tolist()

    # ============================================================== Experiment settings 

    event_ids = list(range(1, 26))     # 1..25
    add_trans_fail = False   
    patch = "patch"   
    print(f"\n{bar}\nExperiment settings:\n{bar}")
    
    forms      = ["cvar_only"] #, "risk_neutral"]
    crit_modes = ["all_in_polygon"] #, "all"]
    inv_bgts   = [5.0] #, 10.0, 20.0, 35.0, 55.0]
    alphas     = [0.75] #, 0.95]
    N_trials   = [1] #, 5, 10]
    lam        = 1.0
    
    # ================================================================ Generate damage states

    all_rows = []

    for num_trial_files in N_trials:
        # Regenerate damage states with the new number of trials (overwriting cache, since we want to compare across different numbers of trials)
        ds_MC = generate_from_MC(
            data=data,event_ids=event_ids,num_trials=num_trial_files,cache_dir=cache_dir,patch=patch,
            cache_tag=f"files_e{len(event_ids)}_tr{num_trial_files}_{patch}",
            use_cache=True)

        ds_bern=generate_from_bernoulli(
            data=data,event_ids=event_ids,num_trials=num_trial_files,
            num_rand_sc= 500,
            cache_dir=cache_dir,patch=patch,
            cache_tag=f"files_e{len(event_ids)}_tr{num_trial_files}_{patch}",
            use_cache=True)
        
        datasets = [("MC", ds_MC), ("BERN", ds_bern)]

        for label, ds in datasets: 
            for crit_mode in crit_modes:
                crit = critical_assets_identifier(mode=crit_mode, grid=grid, bus_in_poly=bus_in_poly,damage_states=ds)

                for form in forms: 
                    for bgt in inv_bgts: 
                        for alpha in alphas:

                            print(f"\n{bar}\n Running: {label} - {form} - BGT: {bgt} - Crit Mode: {crit_mode} - Alpha: {alpha} - N Trials: {num_trial_files}\n{bar}")

                            res = model_build_solve(
                                form=form,grid=grid, damage_states=ds, crit_assets=crit, 
                                alpha=alpha, lam=lam,
                                save_inner_varvals=True, 
                                add_trans_fail=add_trans_fail,
                                max_invest=bgt, print_vars=True, time_solve=True)

                            run_dir = save_run_results(
                                res, base_dir=results_dir,
                                dataset=label,
                                alpha=alpha, lam=lam,
                                patch=patch,
                                n_events=len(event_ids), n_trials=num_trial_files, n_samples=len(res["shed_vals"]), form=form, crit_mode=crit_mode, max_invest=bgt)
                            
                            all_rows.append({
                                "dataset": label,
                                "num_trial_files": num_trial_files,
                                "form": form,
                                "alpha": alpha,
                                "max_invest": bgt, 
                                "expected_shed": res["expected_shed"],
                                "cvar": res["cvar"],
                                "inv_cost": res["inv_cost"],
                                "n_gen_inv":   int(sum(res["gen_inv"].values())),
                                "investments": [ key for key in res["gen_inv"] if res["gen_inv"][key] > 0.5 ] + [ key for key in res["load_inv"] if res["load_inv"][key] > 0.5 ] + [ key for key in res["DG_inv"] if res["DG_inv"][key] > 0.5 ],
                                "critical":  crit_mode,
                                "n_load_inv":  int(sum(res["load_inv"].values())),
                                "n_dg_inv":    int(sum(res["DG_inv"].values())),
                                "run_dir": run_dir, 
                            })

    pd.DataFrame(all_rows).to_csv(os.path.join(results_dir, f"summary_all_runs.csv"), index=False)
    print("\nDONE.")

if __name__ == "__main__":
    main()
