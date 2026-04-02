#plot_shed_hists.py

import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def scan_runs(results_dir: str) -> pd.DataFrame:
    """
    Find run folders that contain both summary.csv and shedvals.csv.
    Returns a dataframe with one row per run (from summary.csv + run_dir/run_name).
    """
    base = Path(results_dir)
    if not base.exists():
        raise FileNotFoundError(f"results_dir not found: {results_dir}")

    rows = []
    for run_dir in base.iterdir():
        if not run_dir.is_dir():
            continue
        summary_path = run_dir / "summary.csv"
        shed_path = run_dir / "shedvals.csv"
        if not (summary_path.exists() and shed_path.exists()):
            continue

        s = pd.read_csv(summary_path)
        if len(s) != 1:
            s = s.iloc[[0]].copy()
        s["run_dir"] = str(run_dir)
        s["run_name"] = run_dir.name
        rows.append(s)

    if not rows:
        raise RuntimeError(f"No run folders found in {results_dir} with summary.csv + shedvals.csv")

    return pd.concat(rows, ignore_index=True)


def load_shedvals(run_dir: str) -> np.ndarray:
    shed_path = Path(run_dir) / "shedvals.csv"
    df = pd.read_csv(shed_path)
    if "shed" not in df.columns:
        raise ValueError(f"'shed' column not found in {shed_path}")
    return df["shed"].to_numpy(dtype=float)


def binned_mode(x: np.ndarray, bins) -> float:
    """Approx mode via the most frequent histogram bin center."""
    if len(x) == 0:
        return np.nan
    counts, edges = np.histogram(x, bins=bins)
    k = int(np.argmax(counts))
    return float(0.5 * (edges[k] + edges[k + 1]))


def maybe_filter(df: pd.DataFrame, col: str, val):
    if val is None:
        return df
    if col not in df.columns:
        print(f"Warning: column '{col}' not found; skipping filter {col}={val}")
        return df
    return df[df[col].astype(str) == str(val)]


def plot_histograms(
    runs: pd.DataFrame,
    out_dir: str,
    bins: int = 30,
    same_bins_within_budget: bool = True,
):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = runs.copy()
    df["max_invest_num"] = pd.to_numeric(df.get("max_invest", np.nan), errors="coerce")

    # Optional: make bin edges consistent across forms at the same budget
    budget_edges = {}
    if same_bins_within_budget and "max_invest_num" in df.columns:
        for b in sorted(df["max_invest_num"].dropna().unique()):
            sub = df[df["max_invest_num"] == b]
            all_shed = []
            for _, row in sub.iterrows():
                all_shed.append(load_shedvals(row["run_dir"]))
            all_shed = np.concatenate(all_shed) if all_shed else np.array([])
            if len(all_shed):
                _, edges = np.histogram(all_shed, bins=bins)
                budget_edges[b] = edges

    out_paths = []
    for _, row in df.iterrows():
        run_dir = row["run_dir"]
        shed = load_shedvals(run_dir)
        if len(shed) == 0:
            continue

        alpha = float(row["alpha"])
        N = len(shed)
        nominal_tail = int(np.ceil((1-alpha) * N))

        var_alpha = np.quantile(shed, alpha, method="higher")
        actual_tail = int((shed >= var_alpha).sum())
        tail_k = int(np.ceil((1-alpha) * len(shed)))
        cvar_alpha = float(np.mean(np.sort(shed)[-tail_k:]))

        print(f"{row.get('run_name', '')}:")
        print("  N=", N)
        print("  nominal tail size=", nominal_tail)
        print("  VaR alpha =", var_alpha)
        print("  scenarios at/above VaR =", actual_tail)

        form = str(row.get("form", "unknown"))
        dataset = str(row.get("dataset", ""))
        patch = str(row.get("patch", ""))
        crit_mode = str(row.get("crit_mode", ""))

        max_inv = row.get("max_invest", None)
        max_inv_num = row.get("max_invest_num", np.nan)

        edges = None
        if same_bins_within_budget and not np.isnan(max_inv_num) and max_inv_num in budget_edges:
            edges = budget_edges[max_inv_num]

        mn = float(np.min(shed))
        mx = float(np.max(shed))
        mean = float(np.mean(shed))
        mode = binned_mode(shed, bins=(edges if edges is not None else bins))

        # ---- Figure
        plt.figure(figsize=(12, 6))

        if edges is None:
            plt.hist(shed, bins=bins)
        else:
            plt.hist(shed, bins=edges)

        plt.axvline(var_alpha, linestyle="--", color="darkorange", linewidth=2)
        plt.title("Post-Hardening Load Shed Distribution (per-scenario load-shed)")
        plt.xlabel("Load Shed (MW)")
        plt.ylabel("Frequency")
        plt.grid(True, axis="y")
        plt.ylim(0,100)

        # Right-side stats
        stats_txt = (
            f"Min:   {mn:.3f}  MW\n"
            f"Mode:  {mode:.3f}  MW\n"
            f"Mean:  {mean:.3f}  MW\n"
            f"Max:   {mx:.3f}  MW\n"
            f"CVaR:  {cvar_alpha:.3f}  MW"
        )
        plt.gcf().text(0.78, 0.70, stats_txt, fontsize=12, va="top")


        # Footer run id
        plt.gcf().text(0.02, 0.02, f"Run ID: {row.get('run_name','')}", fontsize=9)

        # Save
        b_label = "none" if (max_inv is None or (isinstance(max_inv, float) and np.isnan(max_inv))) else str(max_inv)
        safe = lambda s: "".join(c if c.isalnum() or c in "._-=" else "_" for c in str(s))
        fname = f"hist__form-{safe(form)}__budget-{safe(b_label)}__dataset-{safe(dataset)}__patch-{safe(patch)}.png"
        fpath = out_dir / fname

        plt.savefig(fpath, dpi=300, bbox_inches="tight")
        plt.close()

        out_paths.append(str(fpath))

    return out_paths


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results_dir", required=True, help="Path to results directory containing run folders")
    ap.add_argument("--out_dir", default=None, help="Where to write histogram pngs (default: <results_dir>/../analysis/figures/hists)")
    ap.add_argument("--bins", type=int, default=30)
    ap.add_argument("--same_bins_within_budget", action="store_true")

    # optional filters
    ap.add_argument("--dataset", default=None)
    ap.add_argument("--patch", default=None)
    ap.add_argument("--crit_mode", default=None)
    ap.add_argument("--forms", nargs="*", default=None)
    ap.add_argument("--n_events", default=None)
    ap.add_argument("--n_trials", default=None)
    ap.add_argument("--alpha",    default=None)
    ap.add_argument("--lam",   default=None)
    ap.add_argument("--max_invest", default=None)

    args = ap.parse_args()

    runs = scan_runs(args.results_dir)

    runs = maybe_filter(runs, "dataset", args.dataset)
    runs = maybe_filter(runs, "patch", args.patch)
    runs = maybe_filter(runs, "crit_mode", args.crit_mode)
    runs = maybe_filter(runs, "max_invest", args.max_invest)
    runs = maybe_filter(runs, "n_events", args.n_events)
    runs = maybe_filter(runs, "n_trials", args.n_trials)
    runs = maybe_filter(runs, "alpha", args.alpha)
    runs = maybe_filter(runs, "lam", args.lam)

    if args.forms is not None:
        if "form" in runs.columns:
            runs = runs[runs["form"].isin(args.forms)]
        else:
            print("Warning: no 'form' column; cannot filter by --forms")

    if runs.empty:
        raise RuntimeError("No runs left after filtering.")

    if args.out_dir is None:
        analysis_dir = Path(args.results_dir).parent / "analysis"
        out_dir = analysis_dir / "figures" / "hists"
    else:
        out_dir = Path(args.out_dir)

    out_paths = plot_histograms(
        runs,
        out_dir=str(out_dir),
        bins=args.bins,
        same_bins_within_budget=args.same_bins_within_budget,
    )

    print(f"Wrote {len(out_paths)} histogram(s) to: {out_dir}")
    for p in out_paths[:10]:
        print("  ", p)


if __name__ == "__main__":
    main()

