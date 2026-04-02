# analyze_results.py
import os
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def scan_runs(base_dir: str) -> pd.DataFrame:
    """Scan base_dir for run folders containing summary.csv."""
    base = Path(base_dir)
    if not base.exists():
        raise FileNotFoundError(f"Base directory not found: {base_dir}")

    rows = []
    for run_dir in base.iterdir():
        if not run_dir.is_dir():
            continue
        summary_path = run_dir / "summary.csv"
        shed_path = run_dir / "shedvals.csv"
        if summary_path.exists() and shed_path.exists():
            try:
                s = pd.read_csv(summary_path)
                if len(s) != 1:
                    # Expect one-row summary; if not, keep first row
                    s = s.iloc[[0]].copy()
                s["run_dir"] = str(run_dir)
                s["run_name"] = run_dir.name
                rows.append(s)
            except Exception as e:
                print(f"Skipping {run_dir} (error reading summary.csv): {e}")

    if not rows:
        raise RuntimeError(f"No runs found in {base_dir} with summary.csv and shedvals.csv")

    df = pd.concat(rows, ignore_index=True)
    return df


def load_shedvals(run_dir: str) -> np.ndarray:
    """Load per-scenario shedding values from shedvals.csv."""
    shed_path = Path(run_dir) / "shedvals.csv"
    df = pd.read_csv(shed_path)
    if "shed" not in df.columns:
        raise ValueError(f"'shed' column not found in {shed_path}")
    return df["shed"].to_numpy(dtype=float)


def empirical_cvar(shed: np.ndarray, alpha: float) -> float:
    """Compute empirical CVaR_alpha from samples."""
    if len(shed) == 0:
        return np.nan
    var_a = np.quantile(shed, alpha)
    tail = shed[shed >= var_a]
    return float(tail.mean()) if len(tail) else float(var_a)


def empirical_quantile(shed: np.ndarray, q: float) -> float:
    if len(shed) == 0:
        return np.nan
    return float(np.quantile(shed, q))


def ensure_outdirs(base_dir: str) -> dict:
    analysis_dir = Path(base_dir).parent / "analysis"
    fig_dir = analysis_dir / "figures"
    table_dir = analysis_dir / "tables"
    fig_dir.mkdir(parents=True, exist_ok=True)
    table_dir.mkdir(parents=True, exist_ok=True)
    return {"analysis": analysis_dir, "fig": fig_dir, "tables": table_dir}


def apply_filters(df: pd.DataFrame, args) -> pd.DataFrame:
    out = df.copy()

    def _maybe_filter(col, val):
        nonlocal out
        if val is None:
            return
        if col not in out.columns:
            print(f"Warning: column '{col}' not in summary.csv; cannot filter by it.")
            return
        out = out[out[col].astype(str) == str(val)]

    _maybe_filter("dataset", args.dataset)
    _maybe_filter("patch", args.patch)
    _maybe_filter("crit_mode", args.crit_mode)
    _maybe_filter("n_events", args.n_events)
    _maybe_filter("n_trials", args.n_trials)

    # numeric filters
    for col, val in [("alpha", args.alpha), ("lam", args.lam), ("max_invest", args.max_invest)]:
        if val is None:
            continue
        if col not in out.columns:
            print(f"Warning: column '{col}' not in summary.csv; cannot filter by it.")
            continue
        # allow int/float compare
        out = out[pd.to_numeric(out[col], errors="coerce") == float(val)]

    # form filter (allow multiple)
    if args.forms:
        if "form" not in out.columns:
            print("Warning: column 'form' not in summary.csv; cannot filter by forms.")
        else:
            out = out[out["form"].isin(args.forms)]

    return out


def plot_cdf_overlay(runs_df: pd.DataFrame, out_fig_path: str, title: str, alpha_for_cvar: float):
    """
    For each budget (max_invest), overlay CDF curves for each form (risk_neutral vs cvar_only).
    One figure per budget for paper clarity.
    """
    if "max_invest" not in runs_df.columns:
        raise ValueError("summary.csv must include 'max_invest' column for budget grouping.")

    # budgets might be strings; normalize
    runs_df = runs_df.copy()
    runs_df["max_invest_num"] = pd.to_numeric(runs_df["max_invest"], errors="coerce")

    budgets = sorted([b for b in runs_df["max_invest_num"].dropna().unique()])
    if not budgets:
        # allow None budgets (if you ran without max_invest)
        budgets = [None]

    out_paths = []
    for b in budgets:
        if b is None:
            sub = runs_df[runs_df["max_invest"].isna() | (runs_df["max_invest"].astype(str) == "none")]
            b_label = "none"
        else:
            sub = runs_df[runs_df["max_invest_num"] == b]
            b_label = str(int(b)) if float(b).is_integer() else str(b)

        if sub.empty:
            continue

        plt.figure()

        for _, row in sub.iterrows():
            form = str(row.get("form", "unknown"))
            shed = load_shedvals(row["run_dir"])
            xs = np.sort(shed)
            ys = np.arange(1, len(xs) + 1) / len(xs)
            plt.plot(xs, ys, label=form)

        plt.title(f"{title}\nBudget (max_invest) = {b_label}")
        plt.xlabel("Total load shed (MW)")
        plt.ylabel("P(Shed ≤ x)")
        plt.grid(True)
        plt.legend()

        fig_path = Path(out_fig_path).with_name(f"{Path(out_fig_path).stem}__budget-{b_label}.png")
        plt.savefig(fig_path, dpi=300, bbox_inches="tight")
        plt.close()
        out_paths.append(str(fig_path))

    return out_paths


def make_aggregate_table(runs_df: pd.DataFrame, alpha_for_cvar: float) -> pd.DataFrame:
    """
    Build an aggregate table with consistent metrics computed from shedvals.csv:
    mean, median, p95, max, VaR_alpha, CVaR_alpha, etc.
    """
    records = []
    for _, row in runs_df.iterrows():
        shed = load_shedvals(row["run_dir"])
        rec = {
            "run_name": row["run_name"],
            "run_dir": row["run_dir"],
            "dataset": row.get("dataset", None),
            "patch": row.get("patch", None),
            "crit_mode": row.get("crit_mode", None),
            "form": row.get("form", None),
            "max_invest": row.get("max_invest", None),
            "alpha_obj": row.get("alpha", None),
            "lam": row.get("lam", None),
            "n_scenarios": len(shed),
            "mean_shed": float(np.mean(shed)) if len(shed) else np.nan,
            "median_shed": empirical_quantile(shed, 0.50),
            "p90_shed": empirical_quantile(shed, 0.90),
            "p95_shed": empirical_quantile(shed, 0.95),
            "p99_shed": empirical_quantile(shed, 0.99),
            "max_shed": float(np.max(shed)) if len(shed) else np.nan,
        }
        var_a = float(np.quantile(shed, alpha_for_cvar)) if len(shed) else np.nan
        rec[f"VaR_{alpha_for_cvar}"] = var_a
        rec[f"CVaR_{alpha_for_cvar}"] = empirical_cvar(shed, alpha_for_cvar)

        # bring over your saved summary fields if present (optional)
        for col in ["inv_cost", "expected_shed", "cvar", "n_gen_inv", "n_load_inv", "n_trans_inv", "n_dg_inv", "DGcap", "timestamp"]:
            if col in runs_df.columns:
                rec[col] = row.get(col, None)

        records.append(rec)

    return pd.DataFrame.from_records(records)


def plot_tail_bar(agg: pd.DataFrame, out_path: str, alpha_for_cvar: float, title: str):
    """
    Bar plot of CVaR_alpha per form per budget.
    """
    cvar_col = f"CVaR_{alpha_for_cvar}"
    if cvar_col not in agg.columns:
        raise ValueError(f"Missing {cvar_col} in aggregate table.")

    # normalize budget
    agg = agg.copy()
    agg["max_invest_num"] = pd.to_numeric(agg["max_invest"], errors="coerce")

    # keep only budgets that exist
    budgets = sorted([b for b in agg["max_invest_num"].dropna().unique()])
    if not budgets:
        budgets = [None]

    # For paper clarity: one plot, grouped by budget and colored by form
    forms = list(agg["form"].dropna().unique())

    # Build a consistent x-axis by budget, with offsets per form
    x = np.arange(len(budgets))
    width = 0.8 / max(1, len(forms))

    plt.figure()
    for i, form in enumerate(forms):
        vals = []
        for b in budgets:
            if b is None:
                sub = agg[(agg["form"] == form) & (agg["max_invest"].isna() | (agg["max_invest"].astype(str) == "none"))]
            else:
                sub = agg[(agg["form"] == form) & (agg["max_invest_num"] == b)]
            # if multiple runs match, take mean (or change to min/median)
            vals.append(float(sub[cvar_col].mean()) if not sub.empty else np.nan)
        plt.bar(x + i * width, vals, width=width, label=form)

    plt.title(title)
    plt.xlabel("Budget (max_invest)")
    plt.ylabel(f"Empirical CVaR_{alpha_for_cvar} of shed (MW)")
    plt.xticks(x + width * (len(forms) - 1) / 2,
               [str(int(b)) if (b is not None and float(b).is_integer()) else str(b) for b in budgets])
    plt.grid(True, axis="y")
    plt.legend()

    plt.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close()


def main():
    ap = argparse.ArgumentParser(description="Analyze and plot saved SEISMIC stochastic optimization runs.")
    ap.add_argument("--results_dir", required=True, help="Path to results directory containing run folders.")
    ap.add_argument("--dataset",    default=None, help="Filter: dataset (e.g., files, rand_in_polygon, rand_all)")
    ap.add_argument("--patch",      default=None, help="Filter: patch value (e.g., patch or nopatch)")
    ap.add_argument("--crit_mode",  default=None, help="Filter: crit_mode")
    ap.add_argument("--max_invest", default=None, type=float, help="Filter: max_invest (single value)")
    ap.add_argument("--alpha",      default=None, type=float, help="Filter: alpha stored in summary.csv (optional)")
    ap.add_argument("--lam",        default=None, type=float, help="Filter: lam stored in summary.csv (optional)")
    ap.add_argument("--forms", nargs="*", default=None, help="Filter: forms to include, e.g., risk_neutral cvar_only")
    ap.add_argument("--n_trials", default=None, type=int, help="Filter: number of trials per EQ ")
    ap.add_argument("--n_events", default=None, type=int, help="Filter: number of EQ events")
    ap.add_argument("--cvar_eval_alpha", default=0.95, type=float, help="Alpha used to compute empirical VaR/CVaR from shedvals.csv for plotting.")
    args = ap.parse_args()

    outdirs = ensure_outdirs(args.results_dir)
    runs = scan_runs(args.results_dir)
    runs_f = apply_filters(runs, args)

    if runs_f.empty:
        raise RuntimeError("No runs match the filters. Try relaxing filters or check summary.csv columns.")

    # Aggregate table
    agg = make_aggregate_table(runs_f, alpha_for_cvar=args.cvar_eval_alpha)
    agg_path = outdirs["tables"] / "aggregate_summary.csv"
    agg.to_csv(agg_path, index=False)
    print(f"Wrote: {agg_path}")

    # CDF overlay plots (one per budget)
    cdf_paths = plot_cdf_overlay(
        runs_f,
        out_fig_path=str(outdirs["fig"] / "cdf_overlay.png"),
        title="Load shedding CDF comparison",
        alpha_for_cvar=args.cvar_eval_alpha,
    )
    for p in cdf_paths:
        print(f"Wrote: {p}")

    # Tail bar plot
    tail_path = outdirs["fig"] / "tail_cvar_bar.png"
    plot_tail_bar(
        agg,
        out_path=str(tail_path),
        alpha_for_cvar=args.cvar_eval_alpha,
        title="Tail risk comparison (empirical CVaR of shedding)",
    )
    print(f"Wrote: {tail_path}")


if __name__ == "__main__":
    main()

