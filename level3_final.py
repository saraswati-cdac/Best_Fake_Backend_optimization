# ============================================================
# Per-Circuit Backend Comparison (optimization_level=3)
# REAL-ERROR-ONLY VERSION
#
# For EACH circuit individually (e.g. GHZ_5, GHZ_7, GHZ_10,
# GHZ_16, GHZ_20), compares only the backends that circuit
# actually ran on, and reports which backend is best for THAT
# specific circuit/qubit size.
#
# No cross-circuit averaging is done (different circuits run on
# different numbers of backends, so comparing only within a
# circuit avoids that bias).
#
# NO ARBITRARY WEIGHTS ANYWHERE IN THIS SCRIPT.
# The only ranking criterion is:
#
#     estimated_cx_error_contribution = cx_count x avg_cx_error
#
# where:
#   - cx_count     = REAL, measured from the actual transpiled
#                    circuit on that backend (via transpile() +
#                    extract_metrics())
#   - avg_cx_error = REAL, measured from the backend's own
#                    calibration data (via backend_error_rates.py)
#
# Lower estimated_cx_error_contribution = better (less expected
# two-qubit gate error) = best backend for that circuit.
# ============================================================

import sys
import os

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


def run():

    circuits = get_benchmark_circuits()
    backends = get_backends()

    # --------------------------------------------------------
    # Real backend calibration data (from backend_error_rates.py)
    # --------------------------------------------------------
    error_df = get_all_backend_error_profiles(backends)

    print("\n============================================================")
    print("          REAL BACKEND CALIBRATION DATA (measured)")
    print("============================================================\n")
    print(error_df.to_string(index=False))
    error_df.to_csv("backend_real_calibration_data.csv", index=False)

    # --------------------------------------------------------
    # Transpile each circuit on each compatible backend
    # (this is where REAL circuit-specific cx_count comes from)
    # --------------------------------------------------------
    results = []

    for cname, qc in circuits.items():

        for bname, backend in backends.items():

            if qc.num_qubits > backend.num_qubits:
                continue

            tqc = transpile(qc, backend=backend, optimization_level=OPT_LEVEL)
            metrics = extract_metrics(tqc)

            results.append({
                "circuit": cname,
                "backend": bname,
                "qubits": qc.num_qubits,
                "depth": metrics["depth"],
                "gate_count": metrics["gate_count"],
                "cx_count": metrics["cx_count"],
            })

    df = pd.DataFrame(results)

    if df.empty:
        print("\nNo compatible circuit/backend combinations found.")
        return

    # --------------------------------------------------------
    # Merge real backend error rate with real circuit cx_count,
    # and compute the single real-data-based metric
    # --------------------------------------------------------
    df = df.merge(error_df[["backend", "avg_cx_error"]], on="backend", how="left")
    df["estimated_cx_error_contribution"] = df["cx_count"] * df["avg_cx_error"]

    df.to_csv("qiskit_level3_backend_results.csv", index=False)

    # ============================================================
    # PER-CIRCUIT COMPARISON — ranked ONLY by real error contribution
    # Each circuit's backends are ranked ONLY against each other,
    # never against backends from a different circuit.
    # ============================================================

    circuit_names = sorted(
        df["circuit"].unique(),
        key=lambda c: df[df["circuit"] == c]["qubits"].iloc[0]
    )

    all_best_rows = []

    for cname in circuit_names:

        sub = df[df["circuit"] == cname].copy()
        n_qubits = sub["qubits"].iloc[0]

        sub = sub.sort_values("estimated_cx_error_contribution")

        print(f"\n============================================================")
        print(f"   {cname}  ({n_qubits} qubits) — BACKEND COMPARISON")
        print(f"   (ranked by REAL estimated CX-error contribution)")
        print(f"============================================================\n")
        print(sub[[
            "backend", "depth", "gate_count", "cx_count",
            "avg_cx_error", "estimated_cx_error_contribution"
        ]].to_string(index=False))

        best_row = sub.iloc[0]

        print(f"\n  -> Best backend (lowest real estimated error): "
              f"{best_row['backend']} "
              f"(estimated_cx_error_contribution="
              f"{best_row['estimated_cx_error_contribution']:.6f})")

        all_best_rows.append({
            "circuit": cname,
            "qubits": n_qubits,
            "best_backend": best_row["backend"],
            "cx_count": best_row["cx_count"],
            "avg_cx_error": best_row["avg_cx_error"],
            "estimated_cx_error_contribution":
                best_row["estimated_cx_error_contribution"],
        })

    # --------------------------------------------------------
    # Summary table across circuits (still per-circuit — no
    # averaging across circuits, no weights anywhere)
    # --------------------------------------------------------
    summary_df = pd.DataFrame(all_best_rows)

    print("\n============================================================")
    print("   SUMMARY: BEST BACKEND PER CIRCUIT (real error rate only)")
    print("============================================================\n")
    print(summary_df.to_string(index=False))

    summary_df.to_csv("best_backend_per_circuit_real_error_summary.csv", index=False)
    print("\nSaved to: best_backend_per_circuit_real_error_summary.csv")

    # ============================================================
    # HISTOGRAM: one subplot per circuit, showing the REAL
    # estimated CX-error contribution by backend (not depth,
    # since the ranking criterion is now error, not depth)
    # ============================================================

    n_circuits = len(circuit_names)
    fig_width = min(3.2 * n_circuits, 20)

    fig, axes = plt.subplots(1, n_circuits, figsize=(fig_width, 5), squeeze=False)
    axes_list = axes[0]

    for i, cname in enumerate(circuit_names):
        ax = axes_list[i]
        sub = df[df["circuit"] == cname].sort_values(
            "estimated_cx_error_contribution"
        )
        best_backend = sub.iloc[0]["backend"]
        colors = [
            "seagreen" if b == best_backend else "steelblue"
            for b in sub["backend"]
        ]

        ax.bar(sub["backend"], sub["estimated_cx_error_contribution"], color=colors)
        ax.set_title(str(cname), fontsize=11, fontweight="bold")
        ax.set_xlabel("Backend", fontsize=9)
        ax.set_ylabel("Est. CX Error Contribution", fontsize=8)
        ax.tick_params(axis="x", rotation=45, labelsize=8)
        ax.tick_params(axis="y", labelsize=8)

        best_val = sub["estimated_cx_error_contribution"].min()
        ax.annotate("best", xy=(best_backend, best_val), xytext=(0, 8),
                    textcoords="offset points", ha="center",
                    fontsize=8, fontweight="bold", color="seagreen")

    fig.suptitle(
        "Estimated CX-Error Contribution by Backend, per Circuit\n"
        "(cx_count x real measured avg_cx_error, optimization_level=3)",
        fontsize=12, y=1.05
    )

    plt.tight_layout()
    plt.savefig(
        "qiskit_real_error_by_backend_per_circuit.png",
        dpi=150, bbox_inches="tight"
    )
    print("\nHistogram saved to: qiskit_real_error_by_backend_per_circuit.png")

    plt.show()


if __name__ == "__main__":
    run()