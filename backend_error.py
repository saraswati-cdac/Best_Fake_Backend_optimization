# ============================================================
# benchmark_circuits.py
#
# Standalone module: extracts REAL calibration data (CX error,
# readout error, T1, T2) from backend objects.
#
# Import this into any script with:
#   from benchmarks_run.backend_error_rates import get_all_backend_error_profiles
#
# Works with both BackendV1 (backend.properties()) and
# BackendV2 (backend.target) style backends.
# ============================================================

import pandas as pd


def get_avg_cx_error(backend):
    """
    Returns the average two-qubit (CX/ECR/CZ) gate error rate for
    a backend, pulled from real calibration data embedded in the
    backend object. Returns None if unavailable.
    """
    errors = []

    # BackendV2 style: calibration lives in backend.target
    if hasattr(backend, "target") and backend.target is not None:
        target = backend.target
        for op_name in target.operation_names:
            if op_name.lower() in ("cx", "ecr", "cz"):
                for qargs, props in target[op_name].items():
                    if props is not None and props.error is not None:
                        errors.append(props.error)

    # BackendV1 style: calibration lives in backend.properties()
    elif hasattr(backend, "properties") and callable(backend.properties):
        props = backend.properties()
        if props is not None:
            for gate in props.gates:
                if gate.gate.lower() in ("cx", "ecr", "cz"):
                    for param in gate.parameters:
                        if param.name == "gate_error":
                            errors.append(param.value)

    if not errors:
        return None

    return sum(errors) / len(errors)


def get_avg_readout_error(backend):
    """
    Returns the average readout (measurement) error rate for a
    backend, from real calibration data. Returns None if unavailable.
    """
    errors = []

    if hasattr(backend, "target") and backend.target is not None:
        target = backend.target
        if "measure" in target.operation_names:
            for qargs, props in target["measure"].items():
                if props is not None and props.error is not None:
                    errors.append(props.error)

    elif hasattr(backend, "properties") and callable(backend.properties):
        props = backend.properties()
        if props is not None:
            for qubit_idx in range(len(props.qubits)):
                try:
                    errors.append(props.readout_error(qubit_idx))
                except Exception:
                    pass

    if not errors:
        return None

    return sum(errors) / len(errors)


def get_avg_t1_t2(backend):
    """
    Returns (avg_t1_microseconds, avg_t2_microseconds) — coherence
    times — from real calibration data. Either value may be None
    if unavailable.
    """
    t1_values = []
    t2_values = []

    if hasattr(backend, "target") and backend.target is not None:
        for qubit_props in backend.target.qubit_properties or []:
            if qubit_props is not None:
                if qubit_props.t1 is not None:
                    t1_values.append(qubit_props.t1 * 1e6)  # s -> us
                if qubit_props.t2 is not None:
                    t2_values.append(qubit_props.t2 * 1e6)

    elif hasattr(backend, "properties") and callable(backend.properties):
        props = backend.properties()
        if props is not None:
            for qubit_idx in range(len(props.qubits)):
                try:
                    t1_values.append(props.t1(qubit_idx) * 1e6)
                    t2_values.append(props.t2(qubit_idx) * 1e6)
                except Exception:
                    pass

    avg_t1 = sum(t1_values) / len(t1_values) if t1_values else None
    avg_t2 = sum(t2_values) / len(t2_values) if t2_values else None

    return avg_t1, avg_t2


def get_backend_error_profile(backend):
    """
    Returns a dict of real calibration metrics for a single backend.
    """
    avg_cx_error = get_avg_cx_error(backend)
    avg_readout_error = get_avg_readout_error(backend)
    avg_t1, avg_t2 = get_avg_t1_t2(backend)

    return {
        "avg_cx_error": avg_cx_error,
        "avg_readout_error": avg_readout_error,
        "avg_t1_us": avg_t1,
        "avg_t2_us": avg_t2,
    }


def get_all_backend_error_profiles(backends):
    """
    Given a dict of {backend_name: backend_object} (as returned by
    get_backends()), returns a DataFrame with one row per backend
    containing its real calibration/error-rate data.
    """
    rows = []

    for bname, backend in backends.items():
        profile = get_backend_error_profile(backend)
        profile["backend"] = bname
        rows.append(profile)

    df = pd.DataFrame(rows)

    # Reorder so 'backend' is the first column
    cols = ["backend"] + [c for c in df.columns if c != "backend"]
    return df[cols]