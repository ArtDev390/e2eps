# E2EPS core — Orbit Propagator & Visibility Engine

Two foundation modules of the **End-to-End Performance Simulator (E2EPS)** for a
~600-satellite LEO constellation, plus a thin CLI and geometry-level KPIs.

Architecture, workflow and Digital Twin diagrams: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
Open questions for Engineering and the assumptions made to move forward:
[`docs/QUESTIONS_AND_ASSUMPTIONS.md`](docs/QUESTIONS_AND_ASSUMPTIONS.md).
Why these modules, and why their inputs/outputs matter: [`docs/MODULES.md`](docs/MODULES.md).

## Inputs → outputs

| Module | Inputs | Outputs | Consumed by |
|---|---|---|---|
| `orbit` | Walker shells (altitude, inclination, planes, sats/plane, phasing, delta/star), epoch, time grid | Sat positions ECI/ECEF `[T,N,3]` m | Visibility, ISL/latency, 3D viz |
| `visibility` | Sat ECEF, terminals (WGS84 lat/lon/alt, **per-terminal min elevation**), chunk size | Dense `[T,G]`: #visible, serving sat, its elevation & range. Sparse: every visible link (t, terminal, sat, az, el, range). Pass windows. | RF link budget (el + range → path loss, atmospheric loss), resource allocation, latency, handover analysis |
| `kpi` | Visibility result | Per terminal: availability %, mean/min visible sats, longest outage, serving elevation, access delay mean/p95, handovers | Systems / Network / RF reporting |

## Quick start

Requires **Python ≥ 3.10** (macOS ships 3.9 as `python3`; check with `python3 --version`
and use e.g. `python3.13` from Homebrew or pyenv if needed).

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
e2eps --scenario scenarios/illustrative_600.json --out out/          # 576 sats, 8 terminals, 2 h @ 30 s
e2eps --scenario scenarios/what_if_polar_only.json --out out/polar   # phased-deployment what-if
pytest -q
python benchmarks/bench_visibility.py
```

Outputs in `out/`: `kpi_per_terminal.csv`, `passes.csv`, `serving_timeseries.csv`,
`run_meta.json` (scenario hash + version + runtime, for reproducibility). Sample outputs are in `examples/`.

**Executable:** `pip install .` installs the `e2eps` command (`python -m e2eps` also works).
For a single-file binary on your OS (~12 MB):

```bash
pip install pyinstaller && pyinstaller -F -n e2eps --paths src src/e2eps/__main__.py   # -> dist/e2eps
```

## Performance

`python benchmarks/bench_visibility.py` on an Apple M5 laptop (16 GB, NumPy 2.5), 3 runs:

| Case | Size | Result |
|---|---|---|
| Loop reference vs vectorised kernel | 576 sats × 4 terminals × 20 steps | **~30–70× faster** (the vectorised run takes ~1 ms, so timer noise dominates the ratio) |
| Chunked full run | 576 sats × 500 terminals × 6 h @ 30 s = **207 M** geometry evaluations | **5.1–5.6 s** (37–41 M evaluations/s, single process) |
| Memory | same run, `chunk_steps=60` | ~138 MB per chunk vs 1.7 GB if not chunked; only **1.5%** of links are visible and kept |

Time chunks are independent, so the next step is spreading them across Dask/Ray compute workers
(see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)).

## Limitations (honest list)

- No precession/nutation/polar motion. For the synthetic Walker constellation this only rotates the
  whole pattern, so coverage statistics are unaffected. Against real J2000 ephemerides it is ~47 km
  (precession since 2000), so it must be added before validating with Flight Dynamics data (A3 in
  [`docs/QUESTIONS_AND_ASSUMPTIONS.md`](docs/QUESTIONS_AND_ASSUMPTIONS.md)).
- Earth is treated as WGS84 with no terrain masking.
- The serving-satellite policy is "highest elevation", which over-counts handovers. A real allocator adds hysteresis.
- No RF, beams or ISLs yet. Those are the next modules, and they consume these outputs.
- The scenario's orbital parameters are **illustrative**, not official Rivada values.

## Repo layout

```
src/e2eps/   frames.py  orbit.py  visibility.py  kpi.py  scenario.py  cli.py  __main__.py
scenarios/   illustrative_600.json  what_if_polar_only.json
tests/       test_core.py  test_kpi.py  test_scenario.py  test_cli.py
benchmarks/  bench_visibility.py
docs/        ARCHITECTURE.md  QUESTIONS_AND_ASSUMPTIONS.md  MODULES.md
```
