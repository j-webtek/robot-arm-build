"""Create one immutable runtime snapshot from controlled RC03 artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .build_snapshot import BuildSnapshot
from .integrity import (
    BuildIntegrityError,
    load_json_object,
    resolve_beneath,
    sha256_file,
    verify_snapshot_sources,
)


class BuildImportError(RuntimeError):
    """Controlled sources are individually valid but mutually inconsistent."""

    def __init__(self, errors: list[str] | tuple[str, ...]) -> None:
        self.errors = tuple(errors)
        super().__init__("; ".join(self.errors))


def _as_mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise BuildImportError([f"{name} must be an object"])
    return value


def _source_json(rc03_root: Path, relative: str) -> dict[str, Any]:
    return load_json_object(resolve_beneath(rc03_root, relative))


def import_build_snapshot(
    workspace: Path,
    manifest_path: Path | None = None,
) -> BuildSnapshot:
    """Verify hashes and import RC03 state without modifying the hardware tree."""

    workspace = workspace.resolve()
    manifest_path = (
        manifest_path.resolve()
        if manifest_path is not None
        else workspace / "software" / "config" / "system_manifest.json"
    )
    try:
        manifest_path.relative_to(workspace)
    except ValueError as exc:
        raise BuildIntegrityError(("System manifest escapes the workspace",)) from exc
    manifest = load_json_object(manifest_path)
    errors: list[str] = []

    rc03 = _as_mapping(manifest.get("rc03"), "manifest.rc03")
    root_value = rc03.get("root")
    if not isinstance(root_value, str) or not root_value:
        raise BuildImportError(["manifest.rc03.root must be a non-empty path"])
    rc03_root = (workspace / root_value).resolve()
    try:
        rc03_root.relative_to(workspace)
    except ValueError as exc:
        raise BuildIntegrityError(("RC03 root escapes the workspace",)) from exc
    if not rc03_root.is_dir():
        raise BuildIntegrityError((f"Missing RC03 root: {rc03_root}",))

    source_entries = rc03.get("source_snapshot")
    if not isinstance(source_entries, list):
        raise BuildImportError(["manifest.rc03.source_snapshot must be an array"])
    source_hashes = verify_snapshot_sources(rc03_root, source_entries)

    required = {
        "config/measurement_record.json",
        "fiducials/apriltag_map.json",
        "BUILD_BY_STEP/ACTIVE_BUILD.json",
    }
    absent = sorted(required - set(source_hashes))
    if absent:
        raise BuildImportError([f"Frozen snapshot omits required runtime source {path}" for path in absent])

    measurement = _source_json(rc03_root, "config/measurement_record.json")
    tag_map = _source_json(rc03_root, "fiducials/apriltag_map.json")
    active_build = _source_json(rc03_root, "BUILD_BY_STEP/ACTIVE_BUILD.json")

    expected_revision = rc03.get("design_revision")
    if not isinstance(expected_revision, str) or not expected_revision:
        errors.append("manifest.rc03.design_revision is missing")
    for label, revision in (
        ("measurement record", measurement.get("design_revision")),
        ("tag map", tag_map.get("design_revision")),
    ):
        if revision != expected_revision:
            errors.append(
                f"{label} revision is {revision!r}, expected {expected_revision!r}"
            )

    mission_routes = _as_mapping(manifest.get("mission_routes", {}), "mission_routes")
    selected_routes: dict[str, bool] = {}
    measured_routes = _as_mapping(measurement.get("selected_routes", {}), "selected_routes")
    for route, contract_value in mission_routes.items():
        contract = _as_mapping(contract_value, f"mission_routes.{route}")
        selected = contract.get("selected")
        measured = measured_routes.get(route)
        if not isinstance(selected, bool):
            errors.append(f"Manifest route {route} does not contain a boolean selection")
            continue
        if measured is not selected:
            errors.append(
                f"Route {route} is {measured!r} in measurement record, expected {selected!r}"
            )
        selected_routes[route] = selected

    gates_value = _as_mapping(measurement.get("gates", {}), "measurement.gates")
    gate_statuses: dict[str, str] = {}
    for gate_id, gate_value in gates_value.items():
        gate = _as_mapping(gate_value, f"measurement.gates.{gate_id}")
        status = gate.get("status")
        if not isinstance(status, str) or not status:
            errors.append(f"Gate {gate_id} has no status")
        else:
            gate_statuses[gate_id] = status

    manifest_active_id = rc03.get("active_build_id")
    source_active_id = active_build.get("active_build_id")
    if manifest_active_id != source_active_id:
        errors.append(
            f"Active build mismatch: manifest {manifest_active_id!r}, source {source_active_id!r}"
        )

    current_state = _as_mapping(manifest.get("current_build_state", {}), "current_build_state")
    hardware = _as_mapping(manifest.get("hardware", {}), "hardware")
    camera = _as_mapping(hardware.get("camera", {}), "hardware.camera")
    fiducials = _as_mapping(manifest.get("fiducials", {}), "fiducials")
    if fiducials.get("coordinate_source") != tag_map.get("coordinate_source"):
        errors.append("Manifest and RC03 tag-map coordinate sources disagree")

    if errors:
        raise BuildImportError(errors)

    blockers_value = manifest.get("hard_blockers", [])
    if not isinstance(blockers_value, list) or any(
        not isinstance(blocker, str) or not blocker.strip()
        for blocker in blockers_value
    ):
        raise BuildImportError(
            ["manifest.hard_blockers must be an array of non-empty strings"]
        )
    blockers = list(blockers_value)
    if source_active_id is None and "ACTIVE_BUILD_ID_NULL" not in blockers:
        blockers.append("ACTIVE_BUILD_ID_NULL")
    if tag_map.get("coordinate_source") != "measured_installation":
        blockers.append("MEASURED_TAG_MAP_MISSING")
    if any(status != "PASS" for status in gate_statuses.values()):
        blockers.append("PHYSICAL_GATES_INCOMPLETE")

    return BuildSnapshot(
        manifest_id=str(manifest.get("manifest_id", "")),
        manifest_sha256=sha256_file(manifest_path),
        design_revision=str(expected_revision),
        active_build_id=source_active_id,
        source_hashes=source_hashes,
        selected_routes=selected_routes,
        gate_statuses=gate_statuses,
        hard_blockers=tuple(blockers),
        physical_release_status=str(rc03.get("physical_release_status", "UNKNOWN")),
        tag_coordinate_source=str(tag_map.get("coordinate_source", "unknown")),
        camera_exact_model=(
            camera.get("exact_model") if isinstance(camera.get("exact_model"), str) else None
        ),
        camera_state=str(camera.get("state", "OPEN_BLOCKING")),
        safe_to_power_robot=current_state.get("safe_to_power_robot") is True,
        contact_enabled=current_state.get("contact_enabled") is True,
    )
