# E2EPS core — Orbit Propagator & Visibility Engine

Two foundation modules of the **End-to-End Performance Simulator (E2EPS)** for a
~600-satellite LEO constellation, plus a thin CLI and geometry-level KPIs.

Architecture, workflow and Digital Twin diagrams: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
Open questions for Engineering and the assumptions made to move forward:
[`docs/QUESTIONS_AND_ASSUMPTIONS.md`](docs/QUESTIONS_AND_ASSUMPTIONS.md).

## Inputs → outputs

| Module | Inputs | Outputs | Consumed by |
|---|---|---|---|
| `orbit` | Walker shells (altitude, inclination, planes, sats/plane, phasing, delta/star), epoch, time grid | Sat positions ECI/ECEF `[T,N,3]` m | Visibility, ISL/latency, 3D viz |
| `visibility` | Sat ECEF, terminals (WGS84 lat/lon/alt, **per-terminal min elevation**), chunk size | Dense `[T,G]`: #visible, serving sat, its elevation & range. Sparse: every visible link (t, terminal, sat, az, el, range). Pass windows. | RF link budget (el + range → path loss, atmospheric loss), resource allocation, latency, handover analysis |
| `kpi` | Visibility result | Per terminal: availability %, mean/min visible sats, longest outage, serving elevation, access delay mean/p95, handovers | Systems / Network / RF reporting |

## Quick start

```bash
pip install -e ".[dev]"
e2eps --scenario scenarios/illustrative_600.json --out out/          # 576 sats, 8 terminals, 2 h @ 30 s
e2eps --scenario scenarios/what_if_polar_only.json --out out/polar   # phased-deployment what-if
pytest -q
python benchmarks/bench_visibility.py
```

Outputs in `out/`: `kpi_per_terminal.csv`, `passes.csv`, `serving_timeseries.csv`,
`run_meta.json` (scenario hash + version + runtime, for reproducibility). Sample outputs are in `examples/`.

**Executable:** `pip install .` installs the `e2eps` command. For a single-file
binary on your OS: `pip install pyinstaller && pyinstaller -F -n e2eps src/e2eps/cli.py`.

## Limitations (honest list)

- No precession/nutation/polar motion. This gives sub-km error, fine for coverage, not for pointing.
- Earth is treated as WGS84 with no terrain masking.
- The serving-satellite policy is "highest elevation", which over-counts handovers. A real allocator adds hysteresis.
- No RF, beams or ISLs yet. Those are the next modules, and they consume these outputs.
- The scenario's orbital parameters are **illustrative**, not official Rivada values.

## Repo layout

```
src/e2eps/   frames.py  orbit.py  visibility.py  kpi.py  scenario.py  cli.py
scenarios/   illustrative_600.json  what_if_polar_only.json
tests/       test_core.py        
benchmarks/  bench_visibility.py
docs/        ARCHITECTURE.md  QUESTIONS_AND_ASSUMPTIONS.md
```
