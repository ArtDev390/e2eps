import numpy as np
import pytest

from e2eps.frames import C_LIGHT
from e2eps.kpi import terminal_kpis
from e2eps.visibility import VisibilityResult

RANGE_M = 1200e3


def _result() -> VisibilityResult:
    """Hand-built result: terminal A has a 2-step outage and 2 handovers, B is never served."""
    nan = np.nan
    return VisibilityResult(
        t_s=np.arange(0.0, 60.0, 10.0),
        terminal_ids=["A", "B"],
        sat_ids=("S0", "S1"),
        n_visible=np.array([[1, 0], [1, 0], [0, 0], [0, 0], [2, 0], [2, 0]]),
        best_sat=np.array([[0, -1], [0, -1], [-1, -1], [-1, -1], [1, -1], [0, -1]]),
        best_el_deg=np.array([[50, nan], [50, nan], [nan, nan], [nan, nan], [60, nan], [70, nan]]),
        best_range_m=np.array([[RANGE_M, nan]] * 2 + [[nan, nan]] * 2 + [[RANGE_M, nan]] * 2),
        links={},
    )


def test_kpis_for_terminal_with_outage_and_handovers():
    a = terminal_kpis(_result())[0]
    assert a["terminal"] == "A"
    assert a["availability_pct"] == pytest.approx(66.67)
    assert a["mean_visible_sats"] == 1.0
    assert a["min_visible_sats"] == 0
    assert a["longest_outage_s"] == 20.0                 # 2 steps x 10 s
    assert a["mean_serving_el_deg"] == 57.5
    delay = round(RANGE_M / C_LIGHT * 1e3, 2)
    assert a["access_delay_ms_mean"] == delay
    assert a["access_delay_ms_p95"] == delay
    assert a["handovers"] == 2                           # S0 -> S1 -> S0, outage not counted


def test_kpis_for_terminal_never_served():
    b = terminal_kpis(_result())[1]
    assert b["availability_pct"] == 0.0
    assert b["longest_outage_s"] == 60.0                 # whole window
    assert b["mean_serving_el_deg"] is None
    assert b["access_delay_ms_mean"] is None
    assert b["access_delay_ms_p95"] is None
    assert b["handovers"] == 0
