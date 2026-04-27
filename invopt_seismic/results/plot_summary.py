#plot_summary.py

import os
import pandas as pd
import matplotlib.pyplot as plt

results_dir = r"C:\Users\vdiazpa\Documents\quest_planning\results_fresh"
summary_path = os.path.join(results_dir, "summary_all_runs.csv")
out_dir = os.path.join(results_dir, "budget_curve_plots")
os.makedirs(out_dir, exist_ok=True)

df = pd.read_csv(summary_path)

df["max_invest"] = pd.to_numeric(df["max_invest"], errors="coerce")
df["alpha"] = pd.to_numeric(df["alpha"], errors="coerce")
df["cvar"] = pd.to_numeric(df["cvar"], errors="coerce")
df["expected_shed"] = pd.to_numeric(df["expected_shed"], errors="coerce")

if "seed" not in df.columns:
    df["seed"] = "none"

group_cols_base = ["alpha", "seed", "critical", "num_trial_files"]

# ============================================================
# 1) CVaR vs budget, cvar_only only
# ============================================================

cvar_df = df[df["form"] == "cvar_only"].copy()

for keys, sub in cvar_df.groupby(group_cols_base):
    alpha, seed, critical, ntr = keys

    plt.figure(figsize=(8, 5))

    for dataset, dsub in sub.groupby("dataset"):
        dsub = dsub.sort_values("max_invest")
        plt.plot(
            dsub["max_invest"],
            dsub["cvar"],
            marker="o",
            label=dataset,
        )

    plt.xlabel("Investment Budget")
    plt.ylabel("CVaR Load Shed (MW)")
    plt.title(f"CVaR vs Budget | alpha={alpha}, seed={seed}, {critical}, ntr={ntr}")
    plt.grid(True)
    plt.legend()

    fname = f"cvar_vs_budget__alpha-{alpha}__seed-{seed}__crit-{critical}__ntr-{ntr}.png"
    plt.savefig(os.path.join(out_dir, fname), dpi=300, bbox_inches="tight")
    plt.close()


# ============================================================
# 2) Expected shed vs budget, one plot per form
# ============================================================

group_cols_expected = ["form"] + group_cols_base

for keys, sub in df.groupby(group_cols_expected):
    form, alpha, seed, critical, ntr = keys

    plt.figure(figsize=(8, 5))

    for dataset, dsub in sub.groupby("dataset"):
        dsub = dsub.sort_values("max_invest")
        plt.plot(
            dsub["max_invest"],
            dsub["expected_shed"],
            marker="o",
            label=dataset,
        )

    plt.xlabel("Investment Budget")
    plt.ylabel("Expected Load Shed (MW)")
    plt.title(f"Expected Shed vs Budget | {form}, alpha={alpha}, seed={seed}, {critical}, ntr={ntr}")
    plt.grid(True)
    plt.legend()

    fname = f"expected_shed_vs_budget__form-{form}__alpha-{alpha}__seed-{seed}__crit-{critical}__ntr-{ntr}.png"
    plt.savefig(os.path.join(out_dir, fname), dpi=300, bbox_inches="tight")
    plt.close()

print(f"Saved plots to: {out_dir}")
