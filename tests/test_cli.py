import csv
import json
from pathlib import Path

from e2eps import __version__
from e2eps.cli import main
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
