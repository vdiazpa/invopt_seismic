#save_results.py
import os
import pandas as pd
import numpy as np
from datetime import datetime
import matplotlib.pyplot as plt


def save_shed_hist(res, run_dir, bins=30, alpha=None):
    shed = np.asarray(res["shed_vals"], dtype=float)
    if len(shed) == 0:
        print("No shedding values to save histogram for.")
        return
    
    cvar = res.get("cvar", None)

    plt.figure(figsize=(12,6))
    plt.hist(shed, bins=bins)

    if alpha is not None: 
        var_alpha = np.quantile(shed, float(alpha), method="higher")
        plt.axvline(var_alpha, linestyle="--", color="red", linewidth=2)

    plt.title("Load Shedding Distribution Across Scenarios")
    plt.xlabel("LoadShed (MW)")
    plt.ylabel("Frequency")
    plt.grid(True, axis="y")

    stats_txt = (
        f"Min: {np.min(shed):.3f} MW\n"
        f"Max: {np.max(shed):.3f} MW\n"
        f"Mean: {np.mean(shed):.3f} MW\n"
        f"Std: {np.std(shed):.3f} MW\n"
    )

    if cvar is not None: 
        stats_txt += f"CVaR: {cvar:.3f} MW\n"

    plt.gcf().text(0.78, 0.70, stats_txt, fontsize=12, va="top")
    plt.savefig(os.path.join(run_dir, "shed_histogram.png"), dpi=300, bbox_inches="tight")
    plt.close()

def save_shed_boxplot(res, run_dir): 
    shed = np.asarray(res["shed_vals"], dtype=float)
    if len(shed) ==0: 
        print("No shedding vlaues for boxplot")
        return
    plt.figure(figsize=(10,4))
    plt.boxplot(shed, vert=False)
    plt.title("Load Shedding Boxplot Across Scenarios")
    plt.xlabel("Load Shed (MW)")
    plt.grid(True, axis="x")
    plt.savefig(os.path.join(run_dir, "shed_boxplot.png"), dpi=300)
    plt.close()


def save_run_results(
    res, *,
    base_dir,
    dataset,          # "files" or "rand_in_polygon"
    patch,            # "patch" or "nopatch"
    n_events=None,
    n_trials=None,
    n_samples=None,
    seed=None,
    form=None,
    crit_mode=None,
    mipgap=None,
    max_invest=None,
    hard_frac=None,
    alpha=None,
    lam=None,
    tau=None,
):
    """
    Creates one folder per run and saves:
      - summary.csv
      - decisions.csv
      - shedvals.csv
      - run_info.txt
    """

    # ---- folder name 
    parts = [
        dataset,
        f"patch-{patch}",
        f"nev-{n_events}" if n_events is not None else None,
        f"ntr-{n_trials}" if n_trials is not None else None,
        f"nsamp-{n_samples}" if n_samples is not None else None,
        f"seed-{seed}",
        f"crit-{crit_mode}",
        f"form-{form}",
        f"alpha-{alpha}",
        f"DGcap-{res.get('DGcap', 0.0)}",
        f"lam-{lam}",
        f"gap-{mipgap}",
        f"maxinv-{max_invest if max_invest is not None else 'none'}",
    ]
    parts = [str(p) for p in parts if p]
    run_name = "__".join(parts)

    run_dir = os.path.join(base_dir, run_name)
    os.makedirs(run_dir, exist_ok=True)

    # ============================================================
    # 1) summary.csv  
    # ============================================================
    summary = {
        "dataset": dataset,
        "patch": patch,
        "n_events": n_events,
        "n_trials": n_trials,
        "n_samples": n_samples,
        "seed": seed,
        "crit_mode": crit_mode,
        "form": res["form"],
        "mipgap": mipgap,
        "max_invest": max_invest,
        "hard_frac": hard_frac,
        "alpha": alpha,
        "DGcap": res["DGcap"],
        "lam": lam,
        "tau": tau,
        "inv_cost": res["inv_cost"],
        "expected_shed": res["expected_shed"],
        "cvar": res["cvar"],
        "n_gen_inv":   int(sum(res["gen_inv"].values())),
        "n_load_inv":  int(sum(res["load_inv"].values())),
        "n_dg_inv":    int(sum(res["DG_inv"].values())),
        "n_trans_inv": int(sum(res["trans_inv"].values())),
        "n_scenarios": len(res["shed_vals"]),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }

    pd.DataFrame([summary]).to_csv(os.path.join(run_dir, "summary.csv"), index=False)

    # ============================================================
    # 2) decisions.csv  (long table: asset_type, asset_id, invest)
    # ============================================================
    rows = []
    for asset_id, v in res["gen_inv"].items():
        rows.append({"asset_type": "gen", "asset_id": asset_id, "invest": int(v)})
    for asset_id, v in res["load_inv"].items():
        rows.append({"asset_type": "load", "asset_id": asset_id, "invest": int(v)})
    for asset_id, v in res["trans_inv"].items():
        rows.append({"asset_type": "trans", "asset_id": asset_id, "invest": int(v)})
    for asset_id, v in res.get("DG_inv", {}).items():
        rows.append({"asset_type": "DG", "asset_id": asset_id, "invest": int(v)})   

    pd.DataFrame(rows).to_csv(os.path.join(run_dir, "decisions.csv"), index=False)

    # ============================================================
    # 3) shedvals.csv  (per-scenario shedding) & Histogram
    # ============================================================
    pd.DataFrame({
        "scenario_index": list(range(len(res["shed_vals"]))),
        "shed": res["shed_vals"],
    }).to_csv(os.path.join(run_dir, "shedvals.csv"), index=False)

    save_shed_hist(res, run_dir, alpha=alpha)
    save_shed_boxplot(res, run_dir)

    # ============================================================
    # 4) run_info.txt  (FULL experiment description)
    # ============================================================
    with open(os.path.join(run_dir, "run_info.txt"), "w") as f:
        f.write("=== DATASET INFO ===\n")
        f.write(f"dataset        : {dataset}\n")
        f.write(f"patch          : {patch}\n")
        f.write(f"n_events       : {n_events}\n")
        f.write(f"n_trials       : {n_trials}\n")
        f.write(f"n_samples      : {n_samples}\n")
        f.write(f"seed           : {seed}\n\n")

        f.write("=== MODEL FORMULATION ===\n")
        f.write(f"form           : {form}\n")
        f.write(f"crit_mode      : {crit_mode}\n")
        f.write(f"hard_frac      : {hard_frac}\n")
        f.write(f"tau            : {tau}\n")
        f.write(f"alpha          : {alpha}\n")
        f.write(f"lam            : {lam}\n")
        f.write(f"DG Capacity    : {summary['DGcap']}\n\n")

        f.write("=== SOLVER SETTINGS ===\n")
        f.write(f"mipgap         : {mipgap}\n")
        f.write(f"max_invest     : {max_invest}\n\n")

        f.write("=== RESULTS SUMMARY ===\n")
        f.write(f"Investment cost   : {res['inv_cost']}\n")
        f.write(f"Expected shed     : {res['expected_shed']}\n")
        f.write(f"CVaR              : {res['cvar']}\n")
        f.write(f"#Gen invested     : {summary['n_gen_inv']}\n")
        f.write(f"#Load invested    : {summary['n_load_inv']}\n")
        f.write(f"#Trans invested   : {summary['n_trans_inv']}\n")
        f.write(f"#Scenarios        : {summary['n_scenarios']}\n")


    #5) Inner-level results to CSV

    if "inner_var_vals" in res:
        inner_results = res["inner_var_vals"]
        for s, results in inner_results.items():
            for result_name, result_df in results.items(): 
                result_df.to_csv(os.path.join(run_dir, f"worst_case{result_name}.csv"), index=False)

    print("\nSaved run results to:")
    print(" ", run_dir)

    return run_dir