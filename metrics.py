
#Metric extraction module (very important)
def extract_metrics(qc):
    ops = qc.count_ops()
    return {
        "depth": qc.depth(),
        "gate_count": qc.size(),
        "cx_count": ops.get("cx", 0),
    }
