from datetime import datetime, timezone

import numpy as np
import pytest

from e2eps.frames import R_EARTH, geodetic_to_ecef
from e2eps.orbit import J2CircularPropagator, Shell, orbital_period_s, walker
from e2eps.visibility import (Terminal, TerminalSet, compute_visibility,
                              elevation_reference, look_angles, passes)

EPOCH = datetime(2026, 1, 1, tzinfo=timezone.utc)
SHELL = Shell("t", 1050, 88, planes=6, sats_per_plane=10, pattern="star")


def test_walker_size_and_spacing():
    c = walker([SHELL])
    assert len(c) == 60
    raans = np.unique(np.round(np.rad2deg(c.raan0_rad), 6))
    assert np.allclose(np.diff(raans), 30.0)          # star: 180° / 6 planes


def test_radius_is_constant():
    prop = J2CircularPropagator(walker([SHELL]), EPOCH)
    r = np.linalg.norm(prop.positions_eci(np.linspace(0, 7200, 50)), axis=-1)
    assert np.allclose(r, R_EARTH + 1050e3)


def test_period_returns_to_start_without_j2():
    prop = J2CircularPropagator(walker([SHELL]), EPOCH, j2=False)
    p = prop.positions_eci(np.array([0.0, orbital_period_s(1050)]))
    assert np.allclose(p[0], p[1], atol=1e-3)


def test_j2_regresses_raan_for_prograde_orbit():
    prop = J2CircularPropagator(walker([Shell("i", 550, 53, 1, 1)]), EPOCH)
    deg_per_day = np.rad2deg(prop.raan_dot[0]) * 86400
    # hand calc: -1.5 n J2 (Re/a)^2 cos i = -4.49 deg/day at 550 km, 53 deg
    assert deg_per_day == pytest.approx(-4.49, abs=0.02)


def test_geodetic_equator():
    assert np.allclose(geodetic_to_ecef(0, 0, 0), [R_EARTH, 0, 0])


def test_satellite_overhead_is_90_deg_and_range_equals_altitude():
    ts = TerminalSet([Terminal("gs", 0.0, 0.0)])
    sat = geodetic_to_ecef(0.0, 0.0, 1050e3)[None, None, :]
    _, rng, el = look_angles(sat, ts)
    assert np.isclose(np.rad2deg(el[0, 0, 0]), 90.0)
    assert np.isclose(rng[0, 0, 0], 1050e3)


def test_vectorised_matches_loop_reference():
    prop = J2CircularPropagator(walker([SHELL]), EPOCH)
    ts = TerminalSet([Terminal("a", 50.06, 19.94), Terminal("b", -33.9, 18.4)])
    sat = prop.positions_ecef(np.arange(0, 600, 60.0))
    _, _, el = look_angles(sat, ts)
    assert np.allclose(el, elevation_reference(sat, ts))


@pytest.mark.parametrize("chunk", [1, 7, 1000])
def test_chunking_does_not_change_results(chunk):
    prop = J2CircularPropagator(walker([SHELL]), EPOCH)
    ts = TerminalSet([Terminal("a", 50.06, 19.94, min_el_deg=10)])
    t = np.arange(0, 3600, 30.0)
    a = compute_visibility(prop, ts, t, chunk_steps=chunk)
    b = compute_visibility(prop, ts, t, chunk_steps=len(t))
    assert np.array_equal(a.n_visible, b.n_visible)
    assert np.array_equal(a.best_sat, b.best_sat)


def test_passes_are_consistent_with_links():
    prop = J2CircularPropagator(walker([SHELL]), EPOCH)
    ts = TerminalSet([Terminal("a", 50.06, 19.94, min_el_deg=10)])
    res = compute_visibility(prop, ts, np.arange(0, 7200, 30.0))
    p = passes(res)
    assert len(p["g"]) > 0
    assert np.all(p["end_s"] >= p["start_s"])
    assert np.all(p["max_el_deg"] >= 10)
