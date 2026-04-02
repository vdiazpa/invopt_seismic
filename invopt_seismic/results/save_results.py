#save_results.py
import os
import pandas as pd
from datetime import datetime

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
        f"DGcap-{res.get('DGcap', 0.0)}"
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
    # 3) shedvals.csv  (per-scenario shedding)
    # ============================================================
    pd.DataFrame({
        "scenario_index": list(range(len(res["shed_vals"]))),
        "shed": res["shed_vals"],
    }).to_csv(os.path.join(run_dir, "shedvals.csv"), index=False)

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

    print("\nSaved run results to:")
    print(" ", run_dir)

    return run_dir