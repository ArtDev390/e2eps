"""Visibility & Geometry module.

Inputs : satellite ECEF positions (from any Propagator), ground terminals
         (WGS84 lat/lon/alt + minimum elevation mask), time grid.
Outputs:
  * per (t, terminal): number of visible sats, serving sat (highest elevation),
    its elevation and slant range                              -> dense [T, G]
  * every visible link (t, terminal, sat, az, el, range)       -> sparse lists
  * pass windows per (terminal, sat): start, end, max elevation

Why sparse: the full [T, G, N] cube is the E2EPS memory hot spot, yet only a
few % of links are above the mask. We evaluate it chunk by chunk over time and
keep only visible links, so memory scales with *visible* links, not T*G*N.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .frames import enu_rotation, geodetic_to_ecef
from .orbit import Propagator


@dataclass(frozen=True)
class Terminal:
    id: str
    lat_deg: float
    lon_deg: float
    alt_m: float = 0.0
    min_el_deg: float = 25.0
    kind: str = "user"          # user | gateway


class TerminalSet:
    """Terminal list converted once to the arrays the geometry kernel needs."""

    def __init__(self, terminals: list[Terminal]):
        self.items = terminals
        lat = np.array([t.lat_deg for t in terminals])
        lon = np.array([t.lon_deg for t in terminals])
        alt = np.array([t.alt_m for t in terminals])
        self.ecef = geodetic_to_ecef(lat, lon, alt)              # [G, 3]
        self.rot = enu_rotation(lat, lon)                         # [G, 3, 3]
        self.min_el_rad = np.deg2rad([t.min_el_deg for t in terminals])
        self.ids = [t.id for t in terminals]

    def __len__(self) -> int:
        return len(self.items)


def look_angles(sat_ecef: np.ndarray, ts: TerminalSet):
    """Vectorised kernel: sat_ecef [T, N, 3] -> range [T, G, N] (m), elevation [T, G, N] (rad).

    Avoids materialising the [T, G, N, 3] line-of-sight cube: elevation and range
    are rewritten as dot products, so the heavy work is two BLAS matrix multiplies
      up    = sat . u_g - gs . u_g          (u_g = local "up" unit vector)
      |r|^2 = |sat|^2 + |gs|^2 - 2 sat . gs
    Azimuth is only needed for visible links, so it is computed later on the sparse set.
    """
    U = ts.rot[:, 2, :]                                              # [G, 3]
    up = (sat_ecef @ U.T).transpose(0, 2, 1) - np.einsum("gj,gj->g", ts.ecef, U)[None, :, None]
    sg = (sat_ecef @ ts.ecef.T).transpose(0, 2, 1)                  # [T, G, N]
    r2 = (sat_ecef**2).sum(-1)[:, None, :] + (ts.ecef**2).sum(-1)[None, :, None] - 2.0 * sg
    rng = np.sqrt(r2)
    el = np.arcsin(np.clip(up / rng, -1.0, 1.0))
    return rng, el


def azimuth_deg(sat_ecef: np.ndarray, ts: TerminalSet, ti, gi, ni) -> np.ndarray:
    """Azimuth (deg, from North, clockwise) for a sparse set of (t, terminal, sat) links."""
    rho = sat_ecef[ti, ni] - ts.ecef[gi]
    e = np.einsum("kj,kj->k", rho, ts.rot[gi, 0])
    n = np.einsum("kj,kj->k", rho, ts.rot[gi, 1])
    return np.rad2deg(np.mod(np.arctan2(e, n), 2 * np.pi))


def elevation_reference(sat_ecef: np.ndarray, ts: TerminalSet) -> np.ndarray:
    """Slow, loop-based reference used to validate the vectorised kernel (tests + benchmark)."""
    T, N, _ = sat_ecef.shape
    G = len(ts)
    out = np.empty((T, G, N))
    for t in range(T):
        for g in range(G):
            up = ts.rot[g, 2]
            for n in range(N):
                d = sat_ecef[t, n] - ts.ecef[g]
                out[t, g, n] = np.arcsin(float(up @ d) / float(np.sqrt(d @ d)))
    return out


@dataclass
class VisibilityResult:
    t_s: np.ndarray
    terminal_ids: list[str]
    sat_ids: tuple[str, ...]
    n_visible: np.ndarray        # [T, G] int
    best_sat: np.ndarray         # [T, G] int, -1 = outage
    best_el_deg: np.ndarray      # [T, G] float, nan = outage
    best_range_m: np.ndarray     # [T, G] float, nan = outage
    links: dict                  # sparse visible links: t, g, n, az_deg, el_deg, range_m


def compute_visibility(prop: Propagator, ts: TerminalSet, t_s: np.ndarray,
                       chunk_steps: int = 120) -> VisibilityResult:
    """Run propagation + geometry over the time grid in chunks (bounded memory)."""
    t_s = np.asarray(t_s, dtype=float)
    T, G = len(t_s), len(ts)
    n_vis = np.zeros((T, G), dtype=np.int32)
    best = np.full((T, G), -1, dtype=np.int32)
    best_el = np.full((T, G), np.nan)
    best_rng = np.full((T, G), np.nan)
    parts = {k: [] for k in ("t", "g", "n", "az_deg", "el_deg", "range_m")}

    for s in range(0, T, chunk_steps):
        sl = slice(s, min(s + chunk_steps, T))
        sat = prop.positions_ecef(t_s[sl])
        rng, el = look_angles(sat, ts)
        mask = el >= ts.min_el_rad[None, :, None]                 # per-terminal mask
        n_vis[sl] = mask.sum(axis=2)
        el_masked = np.where(mask, el, -np.inf)
        b = el_masked.argmax(axis=2)                              # serving sat = highest elevation
        has = n_vis[sl] > 0
        best[sl] = np.where(has, b, -1)
        bel = np.take_along_axis(el, b[..., None], 2)[..., 0]
        brg = np.take_along_axis(rng, b[..., None], 2)[..., 0]
        best_el[sl] = np.where(has, np.rad2deg(bel), np.nan)
        best_rng[sl] = np.where(has, brg, np.nan)

        ti, gi, ni = np.nonzero(mask)                             # sparsify
        parts["t"].append(ti + s); parts["g"].append(gi); parts["n"].append(ni)
        parts["az_deg"].append(azimuth_deg(sat, ts, ti, gi, ni))
        parts["el_deg"].append(np.rad2deg(el[ti, gi, ni]))
        parts["range_m"].append(rng[ti, gi, ni])

    links = {k: np.concatenate(v) for k, v in parts.items()}
    return VisibilityResult(t_s, ts.ids, prop.c.ids, n_vis, best, best_el, best_rng, links)


def passes(res: VisibilityResult) -> dict:
    """Group sparse visible links into contiguous pass windows per (terminal, sat)."""
    L = res.links
    if len(L["t"]) == 0:
        return {k: np.array([]) for k in ("g", "n", "start_s", "end_s", "max_el_deg")}
    order = np.lexsort((L["t"], L["n"], L["g"]))
    t, g, n, el = L["t"][order], L["g"][order], L["n"][order], L["el_deg"][order]
    new = np.ones(len(t), dtype=bool)
    new[1:] = (g[1:] != g[:-1]) | (n[1:] != n[:-1]) | (t[1:] != t[:-1] + 1)
    starts = np.flatnonzero(new)
    ends = np.r_[starts[1:], len(t)] - 1
    return {
        "g": g[starts], "n": n[starts],
        "start_s": res.t_s[t[starts]], "end_s": res.t_s[t[ends]],
        "max_el_deg": np.maximum.reduceat(el, starts),
    }
