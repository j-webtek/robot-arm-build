from rocell.application.visible_interval_campaign import plan_visible_interval_campaign
from rocell.application.visible_interval_runner import VisibleIntervalRunner


def _load_cli(monkeypatch):
    import importlib.util
    from pathlib import Path

    scripts = Path(__file__).resolve().parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location(
        "visible_interval_cli_test", scripts / "run_visible_interval_campaign.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_visible_interval_plan_is_frozen_and_bounded():
    plan = plan_visible_interval_campaign()
    assert plan["manifest"]["goals"] == [
        [2401, 1713], [2389, 1725], [2401, 1713], [2413, 1701],
    ]
    assert plan["initial_gate"] == {
        "goals": [2413, 1701],
        "positions": [2415, 1700],
        "position_tolerance_counts": 1,
    }
    assert plan["limits"]["maximum_writes"] == 4
    assert plan["limits"]["automatic_retry"] is False
    assert plan["claims"]["movement_authorized"] is False
    assert all(sum(pair) == 4114 for pair in plan["manifest"]["goals"])
    assert all(abs(pair[0] - 2415) <= 32 for pair in plan["manifest"]["goals"])


def test_visible_interval_runner_binds_exact_plan():
    runner = object.__new__(VisibleIntervalRunner)
    assert runner.targets == [[2401, 1713], [2389, 1725], [2401, 1713], [2413, 1701]]
    assert runner.initial_goals == (2413, 1701)
    assert runner.initial_positions == (2415, 1700)


def test_visible_interval_cli_preflight_binds_plan_and_one_use_boot(tmp_path, monkeypatch):
    cli = _load_cli(monkeypatch)
    boot = "ab" * 16
    monkeypatch.setattr(
        cli,
        "review_recovery_startup",
        lambda *args, **kwargs: {"expected_boot": boot, "address": "127.0.0.1"},
    )
    monkeypatch.setattr(cli, "_read", lambda *args: (plan_visible_interval_campaign(), "ok"))
    exports = tmp_path / "runs/wizard-exports"
    exports.mkdir(parents=True)
    binding, root, claim = cli.preflight(tmp_path, "startup")
    assert binding["mapping_plan"] == plan_visible_interval_campaign()
    assert root == exports
    assert claim.name == f"r61-visible-interval-{boot}.json"


def test_visible_interval_cli_rejects_plan_drift_and_consumed_boot(tmp_path, monkeypatch):
    cli = _load_cli(monkeypatch)
    boot = "cd" * 16
    monkeypatch.setattr(
        cli,
        "review_recovery_startup",
        lambda *args, **kwargs: {"expected_boot": boot, "address": "127.0.0.1"},
    )
    exports = tmp_path / "runs/wizard-exports"
    exports.mkdir(parents=True)
    drifted = plan_visible_interval_campaign()
    drifted["manifest"]["goals"][0][0] += 1
    monkeypatch.setattr(cli, "_read", lambda *args: (drifted, "ok"))
    import pytest

    with pytest.raises(ValueError, match="plan binding"):
        cli.preflight(tmp_path, "startup")
    monkeypatch.setattr(cli, "_read", lambda *args: (plan_visible_interval_campaign(), "ok"))
    (exports / f"pose-observation-{boot}.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="already reserved"):
        cli.preflight(tmp_path, "startup")
