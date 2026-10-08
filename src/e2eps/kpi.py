"""Geometry-level KPIs: what visibility alone can already tell Engineering.

Throughput/capacity need the RF module; these KPIs bound them:
no visible satellite => no service, regardless of the link budget.
"""
from __future__ import annotations

import numpy as np

from .frames import C_LIGHT
from .visibility import VisibilityResult


def _longest_run(flags: np.ndarray) -> int:
    """Longest run of True values in a 1-D bool array (vectorised)."""
    d = np.diff(np.r_[0, flags.astype(np.int8), 0])
    starts, ends = np.flatnonzero(d == 1), np.flatnonzero(d == -1)
    return int((ends - starts).max()) if len(starts) else 0


def terminal_kpis(res: VisibilityResult) -> list[dict]:
    step = float(np.median(np.diff(res.t_s))) if len(res.t_s) > 1 else 0.0
    rows = []
    for g, tid in enumerate(res.terminal_ids):
        nv, best = res.n_visible[:, g], res.best_sat[:, g]
        up = nv > 0
        delay_ms = res.best_range_m[up, g] / C_LIGHT * 1e3
        served = best[up]
        rows.append({
            "terminal": tid,
            "availability_pct": round(100.0 * up.mean(), 2),
            "mean_visible_sats": round(float(nv.mean()), 2),
            "min_visible_sats": int(nv.min()),
            "longest_outage_s": _longest_run(~up) * step,
            "mean_serving_el_deg": round(float(np.nanmean(res.best_el_deg[:, g])), 1) if up.any() else None,
            "access_delay_ms_mean": round(float(delay_ms.mean()), 2) if up.any() else None,
            "access_delay_ms_p95": round(float(np.percentile(delay_ms, 95)), 2) if up.any() else None,
            "handovers": int((served[1:] != served[:-1]).sum()),
        })
    return rows
