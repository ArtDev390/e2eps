from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .orbit import Shell
from .visibility import Terminal


@dataclass(frozen=True)
class Scenario:
    name: str
    epoch: datetime
    duration_h: float
    step_s: float
    shells: list[Shell]
    terminals: list[Terminal]
    sha256: str


def load_scenario(path: str | Path) -> Scenario:
    raw = Path(path).read_bytes()
    d = json.loads(raw)
    if "epoch" not in d:
        raise ValueError("epoch is required, e.g. \"2026-01-01T00:00:00+00:00\"")
    epoch = datetime.fromisoformat(d["epoch"])
    if epoch.utcoffset() is None:        # naive -> machine-local time -> results differ per machine
        raise ValueError(f"epoch {d['epoch']!r} has no timezone; add one, e.g. +00:00")
    shells = [Shell(**s) for s in d.get("shells", [])]
    terms = [Terminal(**t) for t in d.get("terminals", [])]
    if not shells or not terms:
        raise ValueError("scenario needs at least one shell and one terminal")
    for s in shells:
        if s.pattern not in ("delta", "star"):
            raise ValueError(f"{s.name}: pattern must be 'delta' or 'star'")
        if not (200 <= s.altitude_km <= 2000):
            raise ValueError(f"{s.name}: altitude {s.altitude_km} km outside LEO range")
        if not (0 <= s.inclination_deg <= 180):
            raise ValueError(f"{s.name}: inclination {s.inclination_deg} deg outside [0, 180]")
        if not all(isinstance(v, int) and v >= 1 for v in (s.planes, s.sats_per_plane)):
            raise ValueError(f"{s.name}: planes and sats_per_plane must be integers >= 1")
        if not (isinstance(s.phasing, int) and 0 <= s.phasing < s.planes):   # Walker F in [0, P-1]
            raise ValueError(f"{s.name}: phasing {s.phasing} outside [0, planes-1]")
    for t in terms:
        if not (-90 <= t.lat_deg <= 90 and 0 <= t.min_el_deg < 90):
            raise ValueError(f"{t.id}: invalid latitude or elevation mask")
        if not (-180 <= t.lon_deg <= 180):
            raise ValueError(f"{t.id}: longitude {t.lon_deg} deg outside [-180, 180]")
        if t.kind not in ("user", "gateway"):
            raise ValueError(f"{t.id}: kind must be 'user' or 'gateway', got {t.kind!r}")
    if len({t.id for t in terms}) != len(terms):
        raise ValueError("terminal ids must be unique")
    time = d.get("time", {})
    duration_h, step_s = float(time.get("duration_h", 2)), float(time.get("step_s", 30))
    if not (duration_h > 0 and step_s > 0):
        raise ValueError("time.duration_h and time.step_s must be > 0")
    return Scenario(d.get("name", Path(path).stem), epoch,
                    duration_h, step_s, shells, terms, hashlib.sha256(raw).hexdigest()[:12])
