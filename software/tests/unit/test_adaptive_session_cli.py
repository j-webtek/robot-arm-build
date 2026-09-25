from __future__ import annotations

from pathlib import Path

import pytest

from rocell.cli import build_parser


def test_adaptive_session_parser_exposes_only_explicit_simulation_controls() -> None:
    parsed = build_parser().parse_args(
        (
            "simulate-adaptive-session",
            "--device",
            "phone",
            "--text",
            "a",
            "--runtime",
            "software/config/runtime.json",
            "--truth-offset-x-mm",
            "12",
            "--truth-offset-y-mm",
            "-2.5",
            "--truth-offset-z-mm",
            "0.25",
            "--truth-yaw-deg",
            "1.5",
            "--require-pass",
            "--json",
        )
    )

    assert parsed.command == "simulate-adaptive-session"
    assert parsed.device == "phone"
    assert parsed.text == "a"
    assert parsed.runtime == Path("software/config/runtime.json")
    assert parsed.truth_offset_x_mm == 12.0
    assert parsed.truth_offset_y_mm == -2.5
    assert parsed.truth_offset_z_mm == 0.25
    assert parsed.truth_yaw_deg == 1.5
    assert parsed.require_pass is True
    assert parsed.json is True
    assert not hasattr(parsed, "port")


def test_adaptive_session_truth_controls_default_to_identity() -> None:
    parsed = build_parser().parse_args(
        (
            "simulate-adaptive-session",
            "--device",
            "keyboard",
            "--text",
            "a",
        )
    )

    assert (
        parsed.truth_offset_x_mm,
        parsed.truth_offset_y_mm,
        parsed.truth_offset_z_mm,
        parsed.truth_yaw_deg,
    ) == (0.0, 0.0, 0.0, 0.0)
    assert parsed.require_pass is False
    assert parsed.json is False


@pytest.mark.parametrize(
    ("flag", "value"),
    (
        ("--truth-offset-x-mm", "NaN"),
        ("--truth-offset-y-mm", "Infinity"),
        ("--truth-offset-z-mm", "-Infinity"),
        ("--truth-yaw-deg", "not-a-number"),
    ),
)
def test_adaptive_session_parser_rejects_nonfinite_truth_controls(
    flag: str,
    value: str,
) -> None:
    with pytest.raises(SystemExit) as raised:
        build_parser().parse_args(
            (
                "simulate-adaptive-session",
                "--device",
                "keyboard",
                "--text",
                "a",
                flag,
                value,
            )
        )

    assert raised.value.code == 2
