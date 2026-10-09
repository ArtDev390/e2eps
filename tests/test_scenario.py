import copy
import json

import pytest

from e2eps.scenario import load_scenario

BASE = {
    "name": "mini",
    "epoch": "2026-01-01T00:00:00+00:00",
    "time": {"duration_h": 1, "step_s": 60},
    "shells": [{"name": "P", "altitude_km": 1050, "inclination_deg": 88,
                "planes": 4, "sats_per_plane": 6, "pattern": "star"}],
    "terminals": [{"id": "UT-1", "lat_deg": 51.5, "lon_deg": -0.1},
                  {"id": "GW-1", "lat_deg": 50.1, "lon_deg": 8.7, "min_el_deg": 10, "kind": "gateway"}],
}


def _write(tmp_path, d, name="scenario.json"):
    p = tmp_path / name
    p.write_text(json.dumps(d))
    return p


def test_loads_valid_scenario(tmp_path):
    sc = load_scenario(_write(tmp_path, BASE))
    assert sc.name == "mini"
    assert sc.duration_h == 1.0 and sc.step_s == 60.0
    assert sc.shells[0].size == 24
    assert [t.id for t in sc.terminals] == ["UT-1", "GW-1"]
    assert sc.terminals[0].min_el_deg == 25.0            # default user mask
    assert len(sc.sha256) == 12


def test_defaults_name_and_time(tmp_path):
    d = {k: v for k, v in BASE.items() if k not in ("name", "time")}
    sc = load_scenario(_write(tmp_path, d, "what_if.json"))
    assert sc.name == "what_if"
    assert (sc.duration_h, sc.step_s) == (2.0, 30.0)


def test_hash_changes_with_content(tmp_path):
    d = copy.deepcopy(BASE)
    d["shells"][0]["planes"] = 5
    a = load_scenario(_write(tmp_path, BASE, "a.json"))
    b = load_scenario(_write(tmp_path, d, "b.json"))
    assert a.sha256 != b.sha256


@pytest.mark.parametrize("path, value, match", [
    (("shells", 0, "pattern"), "walker", "pattern"),
    (("shells", 0, "altitude_km"), 100, "LEO"),
    (("shells", 0, "altitude_km"), 36000, "LEO"),
    (("terminals", 0, "lat_deg"), 95, "latitude"),
    (("terminals", 0, "min_el_deg"), 90, "elevation"),
    (("terminals", 0, "min_el_deg"), -5, "elevation"),
    (("terminals", 1, "id"), "UT-1", "unique"),
])
def test_rejects_invalid_scenario(tmp_path, path, value, match):
    d = copy.deepcopy(BASE)
    *keys, last = path
    node = d
    for k in keys:
        node = node[k]
    node[last] = value
    with pytest.raises(ValueError, match=match):
        load_scenario(_write(tmp_path, d))
