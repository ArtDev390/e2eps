import csv
import json
from pathlib import Path

import pytest

from e2eps import __version__
from e2eps.cli import PASS_FIELDS, main
from e2eps.scenario import load_scenario

SCENARIO = Path(__file__).resolve().parents[1] / "scenarios" / "illustrative_600.json"


def test_cli_writes_all_outputs(tmp_path, capsys):
    main(["--scenario", str(SCENARIO), "--hours", "0.25", "--step", "60", "--out", str(tmp_path)])

    for name in ("kpi_per_terminal.csv", "passes.csv", "serving_timeseries.csv", "run_meta.json"):
        assert (tmp_path / name).is_file(), name

    sc = load_scenario(SCENARIO)
    with (tmp_path / "kpi_per_terminal.csv").open() as f:
        rows = list(csv.DictReader(f))
    assert [r["terminal"] for r in rows] == [t.id for t in sc.terminals]

    meta = json.loads((tmp_path / "run_meta.json").read_text())
    assert meta["e2eps_version"] == __version__
    assert meta["scenario_sha256"] == sc.sha256
    assert meta["time_steps"] == 16                      # 0..900 s every 60 s
    assert meta["satellites"] == 576

    assert f"E2EPS {__version__}" in capsys.readouterr().out


@pytest.mark.parametrize("flag, value", [
    ("--hours", "0"), ("--hours", "-1"),     # 0 used to be silently replaced by the scenario value
    ("--step", "0"), ("--step", "-30"),      # negative used to crash deep in numpy
    ("--chunk", "0"), ("--chunk", "-5"),
])
def test_cli_rejects_non_positive_overrides(tmp_path, capsys, flag, value):
    with pytest.raises(SystemExit) as e:
        main(["--scenario", str(SCENARIO), flag, value, "--out", str(tmp_path)])
    assert e.value.code == 2                             # argparse usage error
    assert "must be > 0" in capsys.readouterr().err
    assert not any(tmp_path.iterdir())                   # nothing written


def test_cli_writes_passes_header_when_nothing_visible(tmp_path):
    d = json.loads(SCENARIO.read_text())
    for t in d["terminals"]:
        t["min_el_deg"] = 89.9                           # practically never satisfied
    sc_path = tmp_path / "never_visible.json"
    sc_path.write_text(json.dumps(d))
    out = tmp_path / "out"
    main(["--scenario", str(sc_path), "--hours", "0.1", "--out", str(out)])
    with (out / "passes.csv").open() as f:
        reader = csv.DictReader(f)
        assert list(reader) == []
        assert reader.fieldnames == PASS_FIELDS
