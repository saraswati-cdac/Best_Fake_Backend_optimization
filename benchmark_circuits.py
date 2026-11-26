import random

from qiskit import QuantumCircuit
from qiskit.circuit.library import QFT, TwoLocal


# -------------------------
# GHZ
# -------------------------
def ghz(n):
      qc = QuantumCircuit(n)
      qc.h(0)

      for i in range(n - 1):
          qc.cx(i, i + 1)

      return qc


# # -------------------------
# # Quantum Fourier Transform
# # -------------------------
# def qft_circuit(n):
#       return QFT(n, do_swaps=True)


# -------------------------
# Hardware Efficient VQE
# -------------------------
# def vqe_ansatz(n):
#     return TwoLocal(
#         num_qubits=n,
#         rotation_blocks="ry",
#         entanglement_blocks="cx",
#         reps=3,
#      )



# -------------------------
# Benchmark Set
# -------------------------
def get_benchmark_circuits():

    circuits = {}

    for n in [5,7,10,16,20]:

        circuits[f"GHZ_{n}"] = ghz(n)

        #circuits[f"QFT_{n}"] = qft_circuit(n)

        #circuits[f"VQE_{n}"] = vqe_ansatz(n)

        

    return circuits