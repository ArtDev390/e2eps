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
    shells = [Shell(**s) for s in d["shells"]]
    terms = [Terminal(**t) for t in d["terminals"]]
    for s in shells:
        if s.pattern not in ("delta", "star"):
            raise ValueError(f"{s.name}: pattern must be 'delta' or 'star'")
        if not (200 <= s.altitude_km <= 2000):
            raise ValueError(f"{s.name}: altitude {s.altitude_km} km outside LEO range")
    for t in terms:
        if not (-90 <= t.lat_deg <= 90 and 0 <= t.min_el_deg < 90):
            raise ValueError(f"{t.id}: invalid latitude or elevation mask")
    if len({t.id for t in terms}) != len(terms):
        raise ValueError("terminal ids must be unique")
    time = d.get("time", {})
    return Scenario(d.get("name", Path(path).stem), datetime.fromisoformat(d["epoch"]),
                    float(time.get("duration_h", 2)), float(time.get("step_s", 30)),
                    shells, terms, hashlib.sha256(raw).hexdigest()[:12])
