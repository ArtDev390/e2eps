"""Command-line entry point: scenario in -> KPI tables, passes, time series out."""
from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

import numpy as np

from . import __version__
from .kpi import terminal_kpis
from .orbit import J2CircularPropagator, walker
from .scenario import load_scenario
from .visibility import TerminalSet, compute_visibility, passes


PASS_FIELDS = ["terminal", "satellite", "start_s", "end_s", "duration_s", "max_el_deg"]


def _write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    """Write rows; with `fields` given, an empty table still gets its header (stable output set)."""
    if not rows and fields is None:
        return
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields or list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def _positive(kind):
    """argparse type: a number > 0 (0 must not silently mean 'use the scenario value')."""
    def parse(s: str):
        v = kind(s)
        if not v > 0:
            raise argparse.ArgumentTypeError(f"must be > 0, got {s}")
        return v
    return parse


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="e2eps", description=__doc__)
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--hours", type=_positive(float), help="override scenario duration")
    ap.add_argument("--step", type=_positive(float), help="override time step [s]")
    ap.add_argument("--chunk", type=_positive(int), default=120, help="time steps per chunk (memory bound)")
    ap.add_argument("--out", default="out")
    a = ap.parse_args(argv)

    sc = load_scenario(a.scenario)
    hours = a.hours if a.hours is not None else sc.duration_h
    step = a.step if a.step is not None else sc.step_s
    t_s = np.arange(0.0, hours * 3600.0 + 1e-9, step)

    t0 = time.perf_counter()
    const = walker(sc.shells)
    prop = J2CircularPropagator(const, sc.epoch)
    ts = TerminalSet(sc.terminals)
    res = compute_visibility(prop, ts, t_s, chunk_steps=a.chunk)
    kpis = terminal_kpis(res)
    p = passes(res)
    runtime = time.perf_counter() - t0

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    _write_csv(out / "kpi_per_terminal.csv", kpis)
    _write_csv(out / "passes.csv", [
        {"terminal": res.terminal_ids[g], "satellite": res.sat_ids[n], "start_s": s, "end_s": e,
         "duration_s": e - s + step, "max_el_deg": round(float(m), 2)}
        for g, n, s, e, m in zip(p["g"], p["n"], p["start_s"], p["end_s"], p["max_el_deg"])], PASS_FIELDS)
    _write_csv(out / "serving_timeseries.csv", [
        {"t_s": res.t_s[t], "terminal": tid, "n_visible": int(res.n_visible[t, g]),
         "serving_sat": res.sat_ids[res.best_sat[t, g]] if res.best_sat[t, g] >= 0 else "",
         "el_deg": round(float(res.best_el_deg[t, g]), 2) if res.best_sat[t, g] >= 0 else "",
         "range_km": round(float(res.best_range_m[t, g]) / 1e3, 1) if res.best_sat[t, g] >= 0 else ""}
        for t in range(len(res.t_s)) for g, tid in enumerate(res.terminal_ids)])
    meta = {"e2eps_version": __version__, "scenario": sc.name, "scenario_sha256": sc.sha256,
            "satellites": len(const), "terminals": len(ts), "time_steps": len(t_s), "step_s": step,
            "geometry_evaluations": len(const) * len(ts) * len(t_s),
            "visible_links": int(len(res.links["t"])), "runtime_s": round(runtime, 3)}
    (out / "run_meta.json").write_text(json.dumps(meta, indent=2))

    print(f"E2EPS {__version__} | {sc.name} ({sc.sha256}) | {len(const)} sats x {len(ts)} terminals "
          f"x {len(t_s)} steps = {meta['geometry_evaluations']:,} evaluations in {runtime:.2f}s")
    hdr = f"{'terminal':<19}{'avail%':>7}{'meanVis':>8}{'minVis':>7}{'maxOut_s':>9}{'el°':>6}{'delay_ms':>9}{'p95_ms':>8}{'HOs':>5}"
    print(hdr + "\n" + "-" * len(hdr))
    for r in kpis:
        print(f"{r['terminal']:<19}{r['availability_pct']:>7}{r['mean_visible_sats']:>8}{r['min_visible_sats']:>7}"
              f"{r['longest_outage_s']:>9.0f}{r['mean_serving_el_deg'] or '-':>6}{r['access_delay_ms_mean'] or '-':>9}"
              f"{r['access_delay_ms_p95'] or '-':>8}{r['handovers']:>5}")
    print(f"\nOutputs written to {out.resolve()}")


if __name__ == "__main__":
    main()
