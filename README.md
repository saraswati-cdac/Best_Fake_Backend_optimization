# Best_Fake_Backend_optimization
Evaluating IBM Quantum fake backends across various quantum circuits and executions to identify the best backend for each circuit.
# Backend benchmark: QFT, GHZ and VQE ansatz circuits on IBM fake backends

Code and results for the paper "Optimization Comparison using QFT, GHZ and VQE Ansatz Circuit".

## What it does
Transpiles each circuit on every compatible IBM fake backend (Jakarta, Lagos,
Nairobi, Guadalupe, Singapore, Mumbai) at optimization_level=3 with 20 seeds
(0-19), and reports mean/std of depth, gate count and CX count. Backends are
ranked per circuit by the CX-only proxy = mean CX count x average CX error.

## Setup
Python 3.14.6, Qiskit 2.3.0 (all versions in requirements.txt)
pip install -r requirements.txt

## Run (from the project root)
python benchmarks_run/level3_multiseed.py            # all circuits, 20 seeds
python benchmarks_run/level3_multiseed.py --only QFT # one family
python benchmarks_run/level3_multiseed.py --summary-only
python check_backend.py                              # backend facts, pass list

## Output files
multiseed_summary.csv      mean/std/min/max per circuit and backend
multiseed_best_backend.csv best backend per circuit (mean proxy)
multiseed_win_rate.csv     % of seeds in which each backend wins
multiseed_*.png            figures
