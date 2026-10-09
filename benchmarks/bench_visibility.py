"""Benchmark: loop reference vs vectorised kernel, then a larger chunked run.

Shows the first step of the scaling path: vectorise before distributing.
"""
import time
from datetime import datetime, timezone

import numpy as np

from e2eps.orbit import J2CircularPropagator, Shell, walker
from e2eps.visibility import Terminal, TerminalSet, compute_visibility, elevation_reference, look_angles

EPOCH = datetime(2026, 1, 1, tzinfo=timezone.utc)
const = walker([Shell("POLAR", 1050, 88, 12, 24, pattern="star"), Shell("INCL", 1050, 65, 12, 24)])
prop = J2CircularPropagator(const, EPOCH)
rng = np.random.default_rng(0)


def terminals(g):
    return TerminalSet([Terminal(f"T{i}", float(rng.uniform(-60, 70)), float(rng.uniform(-180, 180)))
                        for i in range(g)])


def timed(f):
    t0 = time.perf_counter(); out = f(); return out, time.perf_counter() - t0


# 1) loop vs vectorised on the same small problem
ts, t = terminals(4), np.arange(0, 600, 30.0)
sat = prop.positions_ecef(t)
n_eval = sat.shape[0] * sat.shape[1] * len(ts)
ref, t_loop = timed(lambda: elevation_reference(sat, ts))
(_, vec), t_vec = timed(lambda: look_angles(sat, ts))
assert np.allclose(ref, vec)
print(f"[1] {n_eval:,} evaluations | loop {t_loop:.3f}s | vectorised {t_vec*1e3:.1f} ms "
      f"| speed-up x{t_loop / t_vec:,.0f}")

# 2) larger chunked run: 576 sats x 500 terminals x 6 h @ 30 s
ts, t = terminals(500), np.arange(0, 6 * 3600, 30.0)
res, dt = timed(lambda: compute_visibility(prop, ts, t, chunk_steps=60))
total = len(const) * len(ts) * len(t)
print(f"[2] {total:,} evaluations in {dt:.1f}s ({total / dt / 1e6:.0f} M/s) | "
      f"visible links kept: {len(res.links['t']):,} ({100 * len(res.links['t']) / total:.1f}% of the cube)")
print(f"    memory: one [T,G,N] float64 array per chunk ~ {60 * 500 * len(const) * 8 / 1e6:.0f} MB "
      f"vs {total * 8 / 1e9:.1f} GB for the whole run if not chunked")
