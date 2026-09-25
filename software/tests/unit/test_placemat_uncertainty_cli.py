from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import rocell.application as application
import rocell.cli as cli
from rocell.cli import build_parser, main


WORKSPACE = Path(__file__).resolve().parents[3]


class _PlacematReport:
    status = "SENSITIVITY_GAPS_OBSERVED_NO_PHYSICAL_CONCLUSION"
    report_sha256 = "c" * 64

    def __init__(self, *, with_gap: bool) -> None:
        self.cases = tuple(range(59))
        self.targets = tuple(
            SimpleNamespace(
                device="keyboard",
                sensitivity_gap_observed=False,
                worst_xy_margin_mm=2.75,
            )
            for _ in range(46)
        ) + tuple(
            SimpleNamespace(
                device="phone",
                sensitivity_gap_observed=with_gap and index < 27,
                worst_xy_margin_mm=-0.75 if with_gap else 0.25,
            )
            for index in range(29)
        )

    @property
    def sensitivity_gap_count(self) -> int:
        return sum(target.sensitivity_gap_observed for target in self.targets)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "rocell.placemat_geometry_sensitivity.v1",
            "status": self.status,
            "authority": {
                "hardware_accessed": False,
                "hardware_commands_generated": 0,
                "physical_release_effect": "NONE",
            },
            "counts": {
                "cases": len(self.cases),
                "targets": len(self.targets),
                "targets_with_sensitivity_gap": self.sensitivity_gap_count,
            },
            "report_sha256": self.report_sha256,
        }


def test_placemat_geometry_command_is_registered() -> None:
    args = build_parser().parse_args(("stress-placemat-geometry",))

    assert args.zero_bounds is False
    assert args.require_no_gaps is False


def test_placemat_geometry_cli_uses_default_unmeasured_bounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    emitted: list[dict[str, Any]] = []

    def fake_runner(context: object, bounds: object) -> _PlacematReport:
        captured["context"] = context
        captured["bounds"] = bounds
        return _PlacematReport(with_gap=True)

    monkeypatch.setattr(application, "run_placemat_uncertainty_simulation", fake_runner)
    monkeypatch.setattr(cli, "_json_dump", lambda document: emitted.append(dict(document)))

    status = main(
        (
            "--workspace",
            str(WORKSPACE),
            "stress-placemat-geometry",
            "--json",
        )
    )

    assert status == 0
    assert captured["bounds"].board_registration.x_mm == 1.0
    assert emitted[0]["counts"] == {
        "cases": 59,
        "targets": 75,
        "targets_with_sensitivity_gap": 27,
    }
    assert emitted[0]["authority"]["hardware_commands_generated"] == 0


def test_placemat_geometry_require_no_gaps_fails_on_diagnostic_gap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        application,
        "run_placemat_uncertainty_simulation",
        lambda *_args, **_kwargs: _PlacematReport(with_gap=True),
    )
    monkeypatch.setattr(cli, "_json_dump", lambda _document: None)

    status = main(
        (
            "--workspace",
            str(WORKSPACE),
            "stress-placemat-geometry",
            "--require-no-gaps",
            "--json",
        )
    )

    assert status != 0


def test_placemat_geometry_zero_bounds_selects_nominal_control(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_runner(context: object, bounds: object) -> _PlacematReport:
        captured["bounds"] = bounds
        report = _PlacematReport(with_gap=False)
        report.cases = (0,)
        return report

    monkeypatch.setattr(application, "run_placemat_uncertainty_simulation", fake_runner)
    monkeypatch.setattr(cli, "_json_dump", lambda _document: None)

    status = main(
        (
            "--workspace",
            str(WORKSPACE),
            "stress-placemat-geometry",
            "--zero-bounds",
            "--require-no-gaps",
            "--json",
        )
    )

    assert status == 0
    assert captured["bounds"].to_dict() == application.PlacematUncertaintyBounds.zero().to_dict()
