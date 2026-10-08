"""Orbit Propagator module.

Inputs : constellation design (Walker shells) + epoch + time grid.
Outputs: satellite positions [T, N, 3] in ECI and ECEF (metres).

Model: circular orbits with J2 secular perturbations (RAAN regression and
argument-of-latitude rate). This is the standard design-phase model for
constellation coverage studies: fast, closed-form, fully vectorised.
A higher-fidelity propagator (e.g. SGP4 from real TLEs) can be plugged in
through the `Propagator` protocol without changing downstream modules.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

import numpy as np

from .frames import J2, MU_EARTH, R_EARTH, eci_to_ecef, gmst_rad


@dataclass(frozen=True)
class Shell:
    """One Walker shell. pattern='delta' spreads planes over 360°, 'star' over 180° (polar)."""
    name: str
    altitude_km: float
    inclination_deg: float
    planes: int
    sats_per_plane: int
    phasing: int = 1
    pattern: str = "delta"

    @property
    def size(self) -> int:
        return self.planes * self.sats_per_plane


@dataclass(frozen=True)
class Constellation:
    """Flat arrays of mean elements at epoch, one entry per satellite."""
    ids: tuple[str, ...]
    shell: np.ndarray        # [N] shell index
    sma_m: np.ndarray        # [N] semi-major axis
    inc_rad: np.ndarray      # [N]
    raan0_rad: np.ndarray    # [N]
    u0_rad: np.ndarray       # [N] argument of latitude at epoch

    def __len__(self) -> int:
        return len(self.ids)


def walker(shells: list[Shell]) -> Constellation:
    """Generate a Walker constellation (vectorised per shell)."""
    ids, sh, a, i, raan, u = [], [], [], [], [], []
    for k, s in enumerate(shells):
        p, q = np.meshgrid(np.arange(s.planes), np.arange(s.sats_per_plane), indexing="ij")
        p, q = p.ravel(), q.ravel()
        spread = np.pi if s.pattern == "star" else 2 * np.pi
        raan.append(spread * p / s.planes)
        u.append(2 * np.pi * q / s.sats_per_plane + 2 * np.pi * s.phasing * p / s.size)
        a.append(np.full(s.size, R_EARTH + s.altitude_km * 1e3))
        i.append(np.full(s.size, np.deg2rad(s.inclination_deg)))
        sh.append(np.full(s.size, k))
        ids += [f"{s.name}-P{pp:02d}S{qq:02d}" for pp, qq in zip(p, q)]
    cat = lambda xs: np.concatenate(xs)
    return Constellation(tuple(ids), cat(sh), cat(a), cat(i), cat(raan), np.mod(cat(u), 2 * np.pi))


class Propagator(Protocol):
    def positions_eci(self, t_s: np.ndarray) -> np.ndarray: ...
    def positions_ecef(self, t_s: np.ndarray) -> np.ndarray: ...


class J2CircularPropagator:
    """Closed-form circular-orbit propagator with J2 secular rates."""

    def __init__(self, constellation: Constellation, epoch: datetime, j2: bool = True):
        self.c, self.epoch = constellation, epoch
        a, inc = constellation.sma_m, constellation.inc_rad
        n = np.sqrt(MU_EARTH / a**3)
        k = 0.75 * J2 * (R_EARTH / a) ** 2 * n if j2 else np.zeros_like(n)
        cos_i = np.cos(inc)
        self.raan_dot = -2.0 * k * cos_i                      # = -1.5 n J2 (Re/a)^2 cos i
        self.u_dot = n + k * (8.0 * cos_i**2 - 2.0)            # n + ω̇ + δṀ for e = 0

    def positions_eci(self, t_s: np.ndarray) -> np.ndarray:
        t = np.asarray(t_s, dtype=float)[:, None]             # [T, 1]
        c = self.c
        raan = c.raan0_rad + self.raan_dot * t                # [T, N]
        u = c.u0_rad + self.u_dot * t
        cu, su, cO, sO = np.cos(u), np.sin(u), np.cos(raan), np.sin(raan)
        ci, si = np.cos(c.inc_rad), np.sin(c.inc_rad)
        r = np.stack((cu * cO - su * ci * sO, cu * sO + su * ci * cO, su * si), axis=-1)
        return r * c.sma_m[None, :, None]

    def positions_ecef(self, t_s: np.ndarray) -> np.ndarray:
        return eci_to_ecef(self.positions_eci(t_s), gmst_rad(self.epoch, t_s))


def orbital_period_s(altitude_km: float) -> float:
    a = R_EARTH + altitude_km * 1e3
    return 2 * np.pi * np.sqrt(a**3 / MU_EARTH)
