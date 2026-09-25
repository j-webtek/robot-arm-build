from __future__ import annotations

import pytest

from rocell.cli import build_parser


@pytest.mark.parametrize(
    "operation",
    ("init-v2-storage", "new-v2", "verify-v2-runtime"),
)
def test_m1_commands_are_explicit_cell_scoped_and_have_no_device_arguments(
    operation: str,
) -> None:
    parsed = build_parser().parse_args(
        ("physical-onboard", operation, "--cell-id", "cell-a")
    )

    assert parsed.command == "physical-onboard"
    assert parsed.physical_operation == operation
    assert parsed.cell_id == "cell-a"
    assert parsed.json is False
    assert not hasattr(parsed, "port")
    assert not hasattr(parsed, "camera")
    assert not hasattr(parsed, "execute")


def test_m1_session_creation_and_verification_parse_session_scope_separately() -> None:
    created = build_parser().parse_args(
        (
            "physical-onboard",
            "new-v2",
            "--cell-id",
            "cell-a",
            "--session-id",
            "arrival-v2-001",
            "--json",
        )
    )
    verified = build_parser().parse_args(
        (
            "physical-onboard",
            "verify-v2-runtime",
            "--cell-id",
            "cell-a",
            "--session-id",
            "arrival-v2-001",
            "--json",
        )
    )

    assert created.session_id == "arrival-v2-001"
    assert verified.session_id == "arrival-v2-001"
    assert created.json is True
    assert verified.json is True


def test_m1_storage_initialization_cannot_accept_a_session_id() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(
            (
                "physical-onboard",
                "init-v2-storage",
                "--cell-id",
                "cell-a",
                "--session-id",
                "must-not-create",
            )
        )
