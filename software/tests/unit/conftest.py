from __future__ import annotations

import pytest

from rocell.rc03.build_snapshot import BuildSnapshot


@pytest.fixture
def blocked_snapshot() -> BuildSnapshot:
    return BuildSnapshot(
        manifest_id="freeze-blocked",
        manifest_sha256="a" * 64,
        design_revision="RC03-TEST",
        active_build_id=None,
        source_hashes={"source.json": "b" * 64},
        selected_routes={
            "keyboard_rod_route": True,
            "phone_stylus_route": True,
        },
        gate_statuses={"physical_gate": "NOT_TESTED"},
        hard_blockers=("ACTIVE_BUILD_ID_NULL", "PHYSICAL_RELEASE_UNRELEASED"),
        physical_release_status="UNRELEASED",
        tag_coordinate_source="nominal_layout",
        camera_exact_model=None,
        camera_state="OPEN_BLOCKING",
        safe_to_power_robot=False,
        contact_enabled=False,
    )


@pytest.fixture
def released_snapshot() -> BuildSnapshot:
    return BuildSnapshot(
        manifest_id="freeze-released",
        manifest_sha256="c" * 64,
        design_revision="RC03-TEST",
        active_build_id="BUILD-001",
        source_hashes={"source.json": "d" * 64},
        selected_routes={
            "keyboard_rod_route": True,
            "phone_stylus_route": True,
        },
        gate_statuses={"physical_gate": "PASS"},
        hard_blockers=(),
        physical_release_status="RELEASED",
        tag_coordinate_source="measured_installation",
        camera_exact_model="qualified-camera",
        camera_state="QUALIFIED",
        safe_to_power_robot=True,
        contact_enabled=True,
    )
