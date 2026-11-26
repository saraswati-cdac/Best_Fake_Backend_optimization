# ============================================================
# Multi-seed version of level3_final.py  (reviewer point 4)
#
# Put this file in the benchmarks_run/ folder, next to level3_final.py.
# Run from anywhere:   python benchmarks_run/level3_multiseed.py
#                      python benchmarks_run/level3_multiseed.py --seeds 5     (quick test)
#                      python benchmarks_run/level3_multiseed.py --summary-only
#
# For every (circuit, backend) pair that fits, transpiles N times at
# optimization_level=3 with seed_transpiler = 0..N-1, and reports
# mean / std / min / max of depth, gate count and two-qubit count.
# The ranking criterion is unchanged from level3_final.py:
#     CX-only error proxy = cx_count x avg_cx_error
# but now computed from the MEAN cx_count over seeds.
#
# Outputs (written to the current folder):
#   multiseed_raw_runs.csv          every single run (resumes if interrupted)
#   multiseed_summary.csv           mean/std/min/max per circuit x backend  -> Tables 3, 5, 7
#   multiseed_best_backend.csv      best backend per circuit by mean proxy  -> Tables 4, 6, 8
#   multiseed_win_rate.csv          % of seeds in which each backend wins   (robustness)
#   multiseed_matrix.csv            which circuit x backend pairs were run  (reviewer point 3)
#   multiseed_layouts_seed0.csv     physical qubits chosen for seed 0       (reviewer point 3)
#   multiseed_circuit_info.csv      qubits, parameter count, input gate counts (reviewer point 7)
#   multiseed_<FAMILY>.png          bar charts with std error bars          -> Figures 1-3
# ============================================================

import argparse
import csv
import os
import sys

sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

import pandas as pd
import matplotlib.pyplot as plt
from qiskit import transpile

from circuits.benchmark_circuits import get_benchmark_circuits
from benchmarks_run.backends import get_backends
from benchmarks_run.metrics import extract_metrics
from benchmarks_run.backend_error import get_all_backend_error_profiles

OPT_LEVEL = 3
TWO_Q_GATES = ("cx", "ecr", "cz")

RAW_CSV = "multiseed_raw_runs.csv"
LAYOUT_CSV = "multiseed_layouts_seed0.csv"
RAW_COLUMNS = ["circuit", "backend", "qubits", "seed",
               "depth", "gate_count", "cx_count", "two_q_count"]


def two_q_count(tqc):
    """All native two-qubit gates (cx, ecr or cz), so it stays correct on any backend."""
    ops = tqc.count_ops()
    return sum(ops.get(g, 0) for g in TWO_Q_GATES)


# ------------------------------------------------------------
# 1) run all transpilations
# ------------------------------------------------------------
def keep(cname, only):
    """True if the circuit is selected. only = ['VQE'] keeps all VQE_*, ['QFT_10'] keeps just that one."""
    return not only or any(cname == o or cname.startswith(o + "_") for o in only)


def run_raw(n_seeds, only=None):
    circuits = {c: qc for c, qc in get_benchmark_circuits().items() if keep(c, only)}
    backends = get_backends()

    # circuit info for the paper (parameter count, input gate counts)
    info = []
    for cname, qc in circuits.items():
        info.append({
            "circuit": cname,
            "qubits": qc.num_qubits,
            "num_parameters": qc.num_parameters,
            "input_depth": qc.decompose().depth(),
            "input_ops": str(dict(qc.decompose().count_ops())),
        })
    pd.DataFrame(info).to_csv("multiseed_circuit_info.csv", index=False)

    # resume support
    done = set()
    if os.path.exists(RAW_CSV):
        old = pd.read_csv(RAW_CSV)
        done = set(zip(old["circuit"], old["backend"], old["seed"]))
    new_raw = not os.path.exists(RAW_CSV)
    new_layout = not os.path.exists(LAYOUT_CSV)

    with open(RAW_CSV, "a", newline="") as fr, open(LAYOUT_CSV, "a", newline="") as fl:
        wr, wl = csv.writer(fr), csv.writer(fl)
        if new_raw:
            wr.writerow(RAW_COLUMNS)
        if new_layout:
            wl.writerow(["circuit", "backend", "initial_layout_logical_to_physical"])

        for cname, qc in circuits.items():
            for bname, backend in backends.items():
                if qc.num_qubits > backend.num_qubits:
                    continue
                for seed in range(n_seeds):
                    if (cname, bname, seed) in done:
                        continue
                    tqc = transpile(qc, backend=backend,
                                    optimization_level=OPT_LEVEL,
                                    seed_transpiler=seed)
                    m = extract_metrics(tqc)
                    wr.writerow([cname, bname, qc.num_qubits, seed,
                                 m["depth"], m["gate_count"], m["cx_count"],
                                 two_q_count(tqc)])
                    fr.flush()
                    if seed == 0:
                        try:
                            lay = tqc.layout.initial_index_layout(filter_ancillas=True)
                        except Exception:
                            lay = "n/a"
                        wl.writerow([cname, bname, lay])
                        fl.flush()
                print(f"done {cname} on {bname}")


# ------------------------------------------------------------
# 2) summaries
# ------------------------------------------------------------
def summarise(backends, only=None):
    df = pd.read_csv(RAW_CSV)
    # only summarise circuits that are currently active in get_benchmark_circuits()
    # (so commenting a circuit out there also removes it from the tables) and match --only
    active = set(get_benchmark_circuits().keys())
    df = df[df["circuit"].isin(active)]
    df = df[df["circuit"].apply(lambda c: keep(c, only))]

    mismatch = (df["cx_count"] != df["two_q_count"]).sum()
    if mismatch:
        print(f"WARNING: {mismatch} runs where metrics.py cx_count != all two-qubit gates "
              f"(a backend uses ecr/cz?). The summary uses two_q_count.")

    err = get_all_backend_error_profiles(backends)[["backend", "avg_cx_error"]]

    agg = (df.groupby(["circuit", "backend", "qubits"])
             .agg(runs=("seed", "count"),
                  depth_mean=("depth", "mean"), depth_std=("depth", "std"),
                  depth_min=("depth", "min"), depth_max=("depth", "max"),
                  gates_mean=("gate_count", "mean"), gates_std=("gate_count", "std"),
                  cx_mean=("two_q_count", "mean"), cx_std=("two_q_count", "std"),
                  cx_min=("two_q_count", "min"), cx_max=("two_q_count", "max"))
             .reset_index()
             .merge(err, on="backend", how="left"))
    agg["est_mean"] = agg["cx_mean"] * agg["avg_cx_error"]
    agg["est_std"] = agg["cx_std"].fillna(0) * agg["avg_cx_error"]
    agg = agg.sort_values(["qubits", "circuit", "est_mean"])
    agg.round(4).to_csv("multiseed_summary.csv", index=False)

    # best backend per circuit, by the mean proxy
    best = agg.loc[agg.groupby("circuit")["est_mean"].idxmin()].sort_values(["circuit"])
    best = best.rename(columns={"backend": "best_backend"})
    best[["circuit", "qubits", "best_backend", "cx_mean", "cx_std",
          "avg_cx_error", "est_mean", "est_std"]].round(4).to_csv(
        "multiseed_best_backend.csv", index=False)

    print("\n=== Best backend per circuit (mean CX-only proxy over seeds) ===")
    print(best[["circuit", "best_backend", "cx_mean", "cx_std", "est_mean"]]
          .round(4).to_string(index=False))
    print("\n=== Wins per backend (use for the tally in the Conclusion) ===")
    print(best["best_backend"].value_counts().to_string())

    # robustness: in how many seeds does each backend win a circuit?
    d = df.merge(err, on="backend", how="left")
    d["est"] = d["two_q_count"] * d["avg_cx_error"]
    win = d.loc[d.groupby(["circuit", "seed"])["est"].idxmin()]
    rate = (win.groupby(["circuit", "backend"]).size()
               .div(df["seed"].nunique()).mul(100).round(1)
               .rename("win_percent_of_seeds").reset_index())
    rate.to_csv("multiseed_win_rate.csv", index=False)
    print("\n=== Seed-by-seed win rate (a close race shows up here) ===")
    print(rate.to_string(index=False))

    # backend x circuit matrix (which pairs were evaluated)
    matrix = agg.pivot(index="circuit", columns="backend", values="runs").notna()
    matrix = matrix.replace({True: "yes", False: "-"})
    matrix.to_csv("multiseed_matrix.csv")

    return agg


# ------------------------------------------------------------
# 3) figures (one per circuit family, like Figs 1-3)
# ------------------------------------------------------------
def plot_family(agg, family):
    names = sorted(
        [c for c in agg["circuit"].unique() if c.startswith(family + "_")],
        key=lambda c: agg[agg["circuit"] == c]["qubits"].iloc[0])
    if not names:
        return
    fig, axes = plt.subplots(1, len(names), figsize=(min(3.4 * len(names), 20), 5),
                             squeeze=False)
    for ax, cname in zip(axes[0], names):
        sub = agg[agg["circuit"] == cname].sort_values("est_mean")
        best = sub.iloc[0]["backend"]
        colors = ["seagreen" if b == best else "steelblue" for b in sub["backend"]]
        ax.bar(sub["backend"], sub["est_mean"], yerr=sub["est_std"],
               color=colors, capsize=3)
        ax.set_title(cname, fontsize=11, fontweight="bold")
        ax.set_xlabel("Backend", fontsize=9)
        ax.set_ylabel("CX-only error proxy (mean ± std)", fontsize=8)
        ax.tick_params(axis="x", rotation=45, labelsize=8)
        ax.tick_params(axis="y", labelsize=8)
        ax.annotate("best", xy=(best, sub.iloc[0]["est_mean"]), xytext=(0, 8),
                    textcoords="offset points", ha="center", fontsize=8,
                    fontweight="bold", color="seagreen")
    fig.suptitle(f"{family}: CX-only error proxy by backend "
                 f"(mean ± std over seeds, optimization_level={OPT_LEVEL})",
                 fontsize=12, y=1.03)
    plt.tight_layout()
    out = f"multiseed_{family}.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--summary-only", action="store_true",
                    help="skip transpiling, just rebuild tables/figures from the raw CSV")
    ap.add_argument("--only", default="",
                    help="comma-separated circuits or families, e.g. VQE  or  VQE,QFT_10")
    args = ap.parse_args()
    only = [o.strip() for o in args.only.split(",") if o.strip()]

    if not args.summary_only:
        run_raw(args.seeds, only)
    agg = summarise(get_backends(), only)
    for family in sorted({c.split("_")[0] for c in agg["circuit"].unique()}):
        plot_family(agg, family)


if __name__ == "__main__":
    main()