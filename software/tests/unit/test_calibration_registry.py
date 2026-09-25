from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

import pytest

import rocell.calibration.registry as registry_module
from rocell.calibration.artifacts import (
    ArtifactAssessment,
    ArtifactState,
    CalibrationArtifact,
    CalibrationResolution,
)
from rocell.calibration.registry import CalibrationRegistry, CalibrationRegistryError


def _artifact(
    *,
    artifact_id: str = "camera_intrinsics",
    version: int = 1,
    state: ArtifactState = ArtifactState.VALID,
    dependency_hash: str = "a" * 64,
) -> CalibrationArtifact:
    return CalibrationArtifact(
        artifact_id=artifact_id,
        version=version,
        state=state,
        created_utc="2026-09-01T12:00:00Z",
        manifest_id="freeze-released",
        active_build_id="BUILD-001",
        dependency_hashes={"camera_identity": dependency_hash},
        parent_artifact_hashes={},
        payload={"rms_px": 0.4, "matrix": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]},
    )


def _canonical_write(path: Path, document: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        (
            json.dumps(document, sort_keys=True, indent=2, allow_nan=False) + "\n"
        ).encode("utf-8")
    )


def _stage_publication(
    registry: CalibrationRegistry,
    artifact: CalibrationArtifact,
    previous_digest: str | None,
) -> str:
    """Write a self-consistent history node without exercising install guards."""

    digest = artifact.content_hash
    _canonical_write(
        registry.artifact_root / artifact.artifact_id / f"{digest}.json",
        artifact.to_dict(),
    )
    _canonical_write(
        registry.publication_root / artifact.artifact_id / f"{digest}.json",
        registry._publication_document(artifact, digest, previous_digest),
    )
    return digest


def _point_index(
    registry: CalibrationRegistry, artifact_id: str, digest: str
) -> None:
    _canonical_write(
        registry.index_path,
        {
            "schema": registry.INDEX_SCHEMA,
            "current": {artifact_id: digest},
        },
    )


def test_registry_round_trip_and_immutable_versions(tmp_path: Path) -> None:
    registry = CalibrationRegistry(tmp_path / "calibrations")
    first = _artifact()
    first_hash = registry.install(first)
    second = _artifact(version=2)
    second_hash = registry.install(second)
    assert first_hash != second_hash
    assert registry.get_current("camera_intrinsics") == second
    assert (registry.artifact_root / "camera_intrinsics" / f"{first_hash}.json").is_file()
    assert (registry.artifact_root / "camera_intrinsics" / f"{second_hash}.json").is_file()


def test_registry_rejects_nonincreasing_version(tmp_path: Path) -> None:
    registry = CalibrationRegistry(tmp_path / "calibrations")
    registry.install(_artifact(version=2))
    with pytest.raises(RuntimeError, match="version must increase"):
        registry.install(_artifact(version=1, dependency_hash="b" * 64))


def test_registry_assesses_valid_and_stale_dependencies(tmp_path: Path) -> None:
    registry = CalibrationRegistry(tmp_path / "calibrations")
    registry.install(_artifact())
    valid = registry.assess(
        "camera_intrinsics",
        {"camera_identity": "a" * 64},
        manifest_id="freeze-released",
        active_build_id="BUILD-001",
    )
    assert valid.valid
    stale = registry.assess(
        "camera_intrinsics",
        {"camera_identity": "b" * 64},
        manifest_id="freeze-released",
        active_build_id="BUILD-001",
    )
    assert stale.state is ArtifactState.STALE_DEPENDENCY
    assert any("camera_identity" in reason for reason in stale.reasons)


def test_registry_rejects_wrong_build_and_nominal_artifact(tmp_path: Path) -> None:
    registry = CalibrationRegistry(tmp_path / "calibrations")
    registry.install(_artifact(state=ArtifactState.NOMINAL_ONLY))
    assessment = registry.assess(
        "camera_intrinsics",
        {"camera_identity": "a" * 64},
        manifest_id="freeze-released",
        active_build_id="OTHER-BUILD",
    )
    assert not assessment.valid
    assert assessment.state is ArtifactState.NOMINAL_ONLY
    assert any("BUILD_MISMATCH" in reason for reason in assessment.reasons)


def test_registry_reports_missing_and_affected_artifacts(tmp_path: Path) -> None:
    registry = CalibrationRegistry(tmp_path / "calibrations")
    missing = registry.assess(
        "phone_screen",
        {},
        manifest_id="freeze-released",
        active_build_id="BUILD-001",
    )
    assert missing.state is ArtifactState.MISSING
    registry.install(_artifact(artifact_id="camera_intrinsics"))
    assert registry.affected_by(["camera_identity"]) == ("camera_intrinsics",)


def test_artifact_payload_is_deeply_immutable() -> None:
    artifact = _artifact()
    with pytest.raises(TypeError):
        artifact.payload["rms_px"] = 2.0  # type: ignore[index]
    with pytest.raises(TypeError):
        artifact.payload["matrix"][0][0] = 2  # type: ignore[index]


def test_artifact_rejects_nonfinite_json() -> None:
    with pytest.raises(ValueError):
        CalibrationArtifact(
            artifact_id="bad",
            version=1,
            state=ArtifactState.VALID,
            created_utc="2026-09-01T12:00:00Z",
            manifest_id="freeze",
            active_build_id="build",
            dependency_hashes={},
            parent_artifact_hashes={},
            payload={"bad": float("nan")},
        )


def test_artifact_requires_explicit_utc_timestamp() -> None:
    with pytest.raises(ValueError, match="UTC"):
        CalibrationArtifact(
            artifact_id="bad_time",
            version=1,
            state=ArtifactState.VALID,
            created_utc="2026-09-01T12:00:00",
            manifest_id="freeze",
            active_build_id="build",
            dependency_hashes={},
            parent_artifact_hashes={},
            payload={},
        )


def test_assessment_and_resolution_cannot_forge_a_valid_calibration() -> None:
    with pytest.raises(ValueError, match="lowercase SHA-256"):
        ArtifactAssessment("required", ArtifactState.VALID, "wrong", ())
    with pytest.raises(ValueError, match="cannot carry reasons"):
        ArtifactAssessment(
            "required", ArtifactState.VALID, "a" * 64, ("FORGED_REASON",)
        )
    with pytest.raises(ValueError, match="requires a reason"):
        ArtifactAssessment("required", ArtifactState.NOMINAL_ONLY, "a" * 64, ())
    with pytest.raises(ValueError, match="must equal"):
        CalibrationResolution(
            {
                "required": ArtifactAssessment(
                    "different", ArtifactState.VALID, "a" * 64, ()
                )
            }
        )

    assert CalibrationResolution({}).all_valid is False


@pytest.mark.parametrize("mutation", ["missing", "unexpected"])
def test_artifact_parser_requires_the_exact_field_set(mutation: str) -> None:
    document = _artifact().to_dict()
    if mutation == "missing":
        del document["payload"]
    else:
        document["unexpected"] = "must-not-be-ignored"

    with pytest.raises(ValueError, match="exact schema"):
        CalibrationArtifact.from_dict(document)


def test_artifact_rejects_self_parent_and_nonobject_hash_maps() -> None:
    document = _artifact().to_dict()
    document["parent_artifact_hashes"] = {
        "camera_intrinsics": "a" * 64
    }
    with pytest.raises(ValueError, match="itself as a parent"):
        CalibrationArtifact.from_dict(document)

    document = _artifact().to_dict()
    document["dependency_hashes"] = []
    with pytest.raises(TypeError, match="JSON object"):
        CalibrationArtifact.from_dict(document)


def test_registry_rejects_unknown_index_fields_and_invalid_ids(tmp_path: Path) -> None:
    registry = CalibrationRegistry(tmp_path / "calibrations")
    _canonical_write(
        registry.index_path,
        {
            "schema": registry.INDEX_SCHEMA,
            "current": {},
            "unreviewed": True,
        },
    )
    with pytest.raises(CalibrationRegistryError, match="exact schema"):
        registry.get_current("camera_intrinsics")

    _canonical_write(
        registry.index_path,
        {
            "schema": registry.INDEX_SCHEMA,
            "current": {"../escape": "a" * 64},
        },
    )
    with pytest.raises(CalibrationRegistryError, match="must match"):
        registry.get_current("camera_intrinsics")


def test_registry_rejects_noncanonical_owned_json(tmp_path: Path) -> None:
    registry = CalibrationRegistry(tmp_path / "calibrations")
    registry.install(_artifact())
    document = json.loads(registry.index_path.read_text(encoding="utf-8"))
    registry.index_path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(CalibrationRegistryError, match="not canonical"):
        registry.get_current("camera_intrinsics")


def test_registry_bounds_file_reads_before_loading_the_whole_document(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = CalibrationRegistry(tmp_path / "calibrations")
    registry.index_path.parent.mkdir(parents=True)
    monkeypatch.setattr(registry_module, "_MAX_INDEX_BYTES", 64)
    registry.index_path.write_bytes(b"{" + b" " * 128 + b"}")

    with pytest.raises(CalibrationRegistryError, match="exceeds 64 bytes"):
        registry.get_current("camera_intrinsics")


def test_install_size_preflight_does_not_leave_immutable_orphans(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = CalibrationRegistry(tmp_path / "calibrations")
    monkeypatch.setattr(registry_module, "_MAX_INDEX_BYTES", 64)
    with pytest.raises(CalibrationRegistryError, match="index exceeds 64 bytes"):
        registry.install(_artifact())

    assert not tuple(registry.artifact_root.rglob("*.json"))
    assert not tuple(registry.publication_root.rglob("*.json"))


def test_registry_rejects_unknown_artifact_fields_even_if_canonical(
    tmp_path: Path,
) -> None:
    registry = CalibrationRegistry(tmp_path / "calibrations")
    digest = registry.install(_artifact())
    artifact_path = (
        registry.artifact_root / "camera_intrinsics" / f"{digest}.json"
    )
    document = json.loads(artifact_path.read_text(encoding="utf-8"))
    document["unreviewed"] = "field"
    _canonical_write(artifact_path, document)

    with pytest.raises(CalibrationRegistryError, match="exact schema"):
        registry.get_current("camera_intrinsics")


def test_publication_receipt_rejects_self_consistent_uninstalled_tamper(
    tmp_path: Path,
) -> None:
    registry = CalibrationRegistry(tmp_path / "calibrations")
    original_digest = registry.install(_artifact())
    original_path = (
        registry.artifact_root
        / "camera_intrinsics"
        / f"{original_digest}.json"
    )
    document = json.loads(original_path.read_text(encoding="utf-8"))
    document["payload"]["rms_px"] = 0.1
    tampered = CalibrationArtifact.from_dict(document)
    tampered_digest = tampered.content_hash
    tampered_path = (
        registry.artifact_root
        / "camera_intrinsics"
        / f"{tampered_digest}.json"
    )
    _canonical_write(tampered_path, tampered.to_dict())
    _canonical_write(
        registry.index_path,
        {
            "schema": registry.INDEX_SCHEMA,
            "current": {"camera_intrinsics": tampered_digest},
        },
    )

    with pytest.raises(CalibrationRegistryError, match="publication receipt"):
        registry.get_current("camera_intrinsics")


def test_publication_chain_rejects_an_unknown_predecessor(tmp_path: Path) -> None:
    registry = CalibrationRegistry(tmp_path / "calibrations")
    registry.install(_artifact())
    current_digest = registry.install(_artifact(version=2))
    publication_path = (
        registry.publication_root
        / "camera_intrinsics"
        / f"{current_digest}.json"
    )
    publication = json.loads(publication_path.read_text(encoding="utf-8"))
    publication["previous_artifact_hash"] = "f" * 64
    _canonical_write(publication_path, publication)

    with pytest.raises(CalibrationRegistryError, match="missing predecessor"):
        registry.get_current("camera_intrinsics")


def test_registry_rejects_a_canonical_index_rollback(tmp_path: Path) -> None:
    registry = CalibrationRegistry(tmp_path / "calibrations")
    first = registry.install(_artifact(version=1))
    registry.install(_artifact(version=2))
    _canonical_write(
        registry.index_path,
        {
            "schema": registry.INDEX_SCHEMA,
            "current": {"camera_intrinsics": first},
        },
    )

    with pytest.raises(CalibrationRegistryError, match="published version head"):
        registry.get_current("camera_intrinsics")


def test_registry_reads_each_publication_and_artifact_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = CalibrationRegistry(tmp_path / "calibrations")
    publication_count = 12
    for version in range(1, publication_count + 1):
        registry.install(_artifact(version=version))

    original_load_object = registry_module._load_object
    loaded_paths: list[Path] = []

    def counted_load_object(path: Path, *, maximum_bytes: int) -> dict[str, object]:
        loaded_paths.append(path)
        return original_load_object(path, maximum_bytes=maximum_bytes)

    monkeypatch.setattr(registry_module, "_load_object", counted_load_object)
    current = registry.get_current("camera_intrinsics")

    assert current is not None
    assert current.version == publication_count
    assert loaded_paths.count(registry.index_path) == 1
    artifact_reads = [
        path for path in loaded_paths if registry.artifact_root in path.parents
    ]
    publication_reads = [
        path for path in loaded_paths if registry.publication_root in path.parents
    ]
    assert len(artifact_reads) == publication_count
    assert len(publication_reads) == publication_count
    assert len(set(artifact_reads)) == publication_count
    assert len(set(publication_reads)) == publication_count
    assert len(loaded_paths) == 1 + 2 * publication_count


def test_registry_stops_directory_scan_at_limit_plus_one_before_parsing_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = CalibrationRegistry(tmp_path / "calibrations")
    for version in range(1, 5):
        registry.install(_artifact(version=version))

    original_load_object = registry_module._load_object
    loaded_paths: list[Path] = []

    def counted_load_object(path: Path, *, maximum_bytes: int) -> dict[str, object]:
        loaded_paths.append(path)
        return original_load_object(path, maximum_bytes=maximum_bytes)

    monkeypatch.setattr(registry_module, "_MAX_PUBLICATIONS_PER_ARTIFACT", 3)
    monkeypatch.setattr(registry_module, "_load_object", counted_load_object)

    with pytest.raises(CalibrationRegistryError, match="bounded limit"):
        registry.get_current("camera_intrinsics")

    # The index must be parsed to select the artifact ID, but the over-limit
    # history is rejected during bounded enumeration before any owned history
    # document is parsed.
    assert loaded_paths == [registry.index_path]


def test_registry_rejects_a_branched_publication_graph(tmp_path: Path) -> None:
    registry = CalibrationRegistry(tmp_path / "calibrations")
    genesis = _artifact(version=1)
    first_child = _artifact(version=2, dependency_hash="b" * 64)
    second_child = _artifact(version=3, dependency_hash="c" * 64)
    genesis_digest = _stage_publication(registry, genesis, None)
    _stage_publication(registry, first_child, genesis_digest)
    second_child_digest = _stage_publication(
        registry, second_child, genesis_digest
    )
    _point_index(registry, "camera_intrinsics", second_child_digest)

    with pytest.raises(CalibrationRegistryError, match="branches"):
        registry.get_current("camera_intrinsics")


def test_registry_rejects_multiple_publication_geneses(tmp_path: Path) -> None:
    registry = CalibrationRegistry(tmp_path / "calibrations")
    _stage_publication(registry, _artifact(version=1), None)
    second_digest = _stage_publication(
        registry,
        _artifact(version=2, dependency_hash="b" * 64),
        None,
    )
    _point_index(registry, "camera_intrinsics", second_digest)

    with pytest.raises(CalibrationRegistryError, match="exactly one genesis"):
        registry.get_current("camera_intrinsics")


def test_registry_rejects_a_disconnected_publication_cycle(tmp_path: Path) -> None:
    registry = CalibrationRegistry(tmp_path / "calibrations")
    genesis = _artifact(version=1)
    cycle_a = _artifact(version=2, dependency_hash="b" * 64)
    cycle_b = _artifact(version=3, dependency_hash="c" * 64)
    genesis_digest = genesis.content_hash
    cycle_a_digest = cycle_a.content_hash
    cycle_b_digest = cycle_b.content_hash
    _stage_publication(registry, genesis, None)
    _stage_publication(registry, cycle_a, cycle_b_digest)
    _stage_publication(registry, cycle_b, cycle_a_digest)
    _point_index(registry, "camera_intrinsics", genesis_digest)

    with pytest.raises(CalibrationRegistryError, match="Cyclic"):
        registry.get_current("camera_intrinsics")


def test_registry_rejects_nonincreasing_versions_in_publication_graph(
    tmp_path: Path,
) -> None:
    registry = CalibrationRegistry(tmp_path / "calibrations")
    predecessor = _artifact(version=2)
    successor = _artifact(version=1, dependency_hash="b" * 64)
    predecessor_digest = _stage_publication(registry, predecessor, None)
    successor_digest = _stage_publication(
        registry, successor, predecessor_digest
    )
    _point_index(registry, "camera_intrinsics", successor_digest)

    with pytest.raises(CalibrationRegistryError, match="strictly increase"):
        registry.get_current("camera_intrinsics")


def test_registry_rejects_crash_orphaned_published_successor(
    tmp_path: Path,
) -> None:
    registry = CalibrationRegistry(tmp_path / "calibrations")
    current_digest = registry.install(_artifact(version=1))
    # Model a process interruption after artifact + receipt durability but
    # before the atomic index replacement.
    _stage_publication(
        registry,
        _artifact(version=2, dependency_hash="b" * 64),
        current_digest,
    )

    with pytest.raises(CalibrationRegistryError, match="published version head"):
        registry.get_current("camera_intrinsics")


def test_registry_rejects_removing_a_published_artifact_from_index(
    tmp_path: Path,
) -> None:
    registry = CalibrationRegistry(tmp_path / "calibrations")
    registry.install(_artifact())
    _canonical_write(
        registry.index_path,
        {"schema": registry.INDEX_SCHEMA, "current": {}},
    )

    with pytest.raises(CalibrationRegistryError, match="omits an artifact"):
        registry.get_current("camera_intrinsics")


def test_child_assessment_requires_transitively_valid_parent(tmp_path: Path) -> None:
    registry = CalibrationRegistry(tmp_path / "calibrations")
    parent = _artifact(
        artifact_id="parent",
        state=ArtifactState.NOMINAL_ONLY,
    )
    parent_digest = registry.install(parent)
    child = CalibrationArtifact(
        artifact_id="child",
        version=1,
        state=ArtifactState.VALID,
        created_utc="2026-09-01T12:00:00Z",
        manifest_id="freeze-released",
        active_build_id="BUILD-001",
        dependency_hashes={},
        parent_artifact_hashes={"parent": parent_digest},
        payload={},
    )
    registry.install(child)

    assessment = registry.assess(
        "child",
        {"camera_identity": "a" * 64},
        manifest_id="freeze-released",
        active_build_id="BUILD-001",
    )
    assert assessment.state is ArtifactState.STALE_DEPENDENCY
    assert assessment.reasons == ("INVALID_PARENT_CALIBRATION:child:parent",)


def test_registry_rejects_an_artifact_symlink(tmp_path: Path) -> None:
    registry = CalibrationRegistry(tmp_path / "calibrations")
    digest = registry.install(_artifact())
    artifact_path = (
        registry.artifact_root / "camera_intrinsics" / f"{digest}.json"
    )
    external = tmp_path / "outside-registry.json"
    external.write_bytes(artifact_path.read_bytes())
    artifact_path.unlink()
    try:
        artifact_path.symlink_to(external)
    except OSError as exc:
        pytest.skip(f"Artifact symlinks are unavailable on this platform: {exc}")

    with pytest.raises(CalibrationRegistryError, match="cannot traverse a symlink"):
        registry.get_current("camera_intrinsics")


def test_registry_rejects_a_publication_symlink(tmp_path: Path) -> None:
    registry = CalibrationRegistry(tmp_path / "calibrations")
    digest = registry.install(_artifact())
    publication_path = (
        registry.publication_root / "camera_intrinsics" / f"{digest}.json"
    )
    external = tmp_path / "outside-publication.json"
    external.write_bytes(publication_path.read_bytes())
    publication_path.unlink()
    try:
        publication_path.symlink_to(external)
    except OSError as exc:
        pytest.skip(f"Publication symlinks are unavailable on this platform: {exc}")

    with pytest.raises(CalibrationRegistryError, match="cannot traverse a symlink"):
        registry.get_current("camera_intrinsics")


def test_concurrent_writers_do_not_lose_unrelated_index_entries(
    tmp_path: Path,
) -> None:
    root = tmp_path / "calibrations"
    artifact_ids = tuple(f"camera_{index:02d}" for index in range(24))

    def publish(artifact_id: str) -> str:
        # Separate instances exercise both the process-wide and filesystem
        # coordination boundaries used by independent application services.
        return CalibrationRegistry(root).install(_artifact(artifact_id=artifact_id))

    with ThreadPoolExecutor(max_workers=8) as executor:
        digests = tuple(executor.map(publish, artifact_ids))

    registry = CalibrationRegistry(root)
    for artifact_id, digest in zip(artifact_ids, digests, strict=True):
        current = registry.get_current(artifact_id)
        assert current is not None
        assert current.content_hash == digest

    index = json.loads(registry.index_path.read_text(encoding="utf-8"))
    assert tuple(index["current"]) == tuple(sorted(artifact_ids))
