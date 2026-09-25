"""Pure retained snapshots; physical-shaped inputs are injected, never observed."""

from copy import deepcopy
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from rocell.application.physical_camera_selection import (
    PhysicalCameraSelectionError,
    selection_from_enrollment,
    selection_from_enrollment_snapshot,
)
from rocell.application.wizard_native_camera_enrollment import (
    NativeCameraEnrollmentError,
    verify_native_camera_enrollment_snapshot,
)
from test_physical_camera_selection import physical_enrollment
from test_wizard_native_camera_enrollment import (
    SOURCE,
    SESSION,
    identified,
    generic_review,
)
from test_wizard_native_camera_integration import (
    setup as service_setup,
    discover,
    resolve_review,
)


def verify(snapshot, **kwargs):
    return verify_native_camera_enrollment_snapshot(
        snapshot,
        source_sha256=kwargs.get("source", SOURCE),
        launch_session_id=kwargs.get("session", SESSION),
    )


def selection(snapshot):
    return selection_from_enrollment_snapshot(
        snapshot, source_sha256=SOURCE, launch_session_id=SESSION
    )


@pytest.mark.parametrize("mode", ["physical", "rehearsal"])
@pytest.mark.parametrize("scenario", ["nominal", "missing-mapping", "wrong-device"])
def test_actual_full_review_recomputes_without_changing_original_context(
    mode, scenario
):
    if mode == "physical":
        owner = physical_enrollment(
            scenario=scenario, unicode=scenario != "missing-mapping"
        )
    else:
        owner, _, token = identified(scenario)
        owner.review(token, "reviewer")
    original = owner.export_snapshot()
    assert verify(original) == original
    if mode == "rehearsal":
        with pytest.raises(PhysicalCameraSelectionError):
            selection(original)
    elif scenario != "nominal":
        assert selection(original) is None
        with pytest.raises(PhysicalCameraSelectionError):
            selection_from_enrollment(
                owner, source_sha256=SOURCE, launch_session_id=SESSION
            )
    else:
        assert (
            selection(original).payload
            == selection_from_enrollment(
                owner, source_sha256=SOURCE, launch_session_id=SESSION
            ).payload
        )
    detached = verify(original)
    detached["view"]["candidates"].clear()
    assert owner.export_snapshot() == original
    assert verify(original) == original


@pytest.mark.parametrize("scenario", ["missing-identity", "duplicate-identity"])
def test_actual_generic_identity_holds_are_retained_not_promoted(scenario):
    owner, _, token = identified(generic=generic_review(scenario))
    report = owner.review(token, "reviewer")
    assert verify(report) == report
    assert report["binding_artifact"] is None
    assert report["view"]["review"]["status"] == "METADATA_ACKNOWLEDGED_BUT_HELD"


@pytest.mark.parametrize(
    "source,session",
    [
        ("b" * 64, SESSION),
        (SOURCE, "other-launch"),
        (False, SESSION),
        (SOURCE, False),
    ],
)
def test_explicit_expected_source_and_launch_are_not_rebound(source, session):
    with pytest.raises(NativeCameraEnrollmentError):
        verify(physical_enrollment().export_snapshot(), source=source, session=session)


@pytest.mark.parametrize(
    "path,value",
    [
        (("extra",), True),
        (("schema",), "wrong"),
        (("view", "extra"), True),
        (("view", "status"), "REVIEW_HELD"),
        (("view", "physical_authority"), 0),
        (("view", "connected"), True),
        (("view", "invalidation_reason"), "SOURCE_CHANGED"),
        (("view", "provenance", "source_sha256"), "b" * 64),
        (("view", "provenance", "scope"), "ACTIVATION"),
        (("view", "inventory_operation_id"), "changed-operation"),
        (("view", "inventory_sha256"), "0" * 64),
        (("view", "generic_candidate_sha256"), "0" * 64),
        (("view", "candidates", 0, "choice_id"), "endpoint-0-" + "1" * 32),
        (("view", "candidates", 0, "friendly_name"), "changed display"),
        (("view", "candidates", 0, "endpoint_sha256"), "0" * 64),
        (("view", "identity", "choice_id"), "endpoint-1-" + "0" * 32),
        (("view", "identity", "operation_id"), "changed-identity-operation"),
        (("view", "identity", "generic_device_match"), False),
        (("view", "identity", "exact_endpoint_observed"), 1),
        (("view", "identity", "identity_sha256"), "0" * 64),
        (("view", "review", "reviewer_id"), "different-reviewer"),
        (("view", "review", "choice_id"), "endpoint-1-" + "0" * 32),
        (("view", "review", "status"), "METADATA_ACKNOWLEDGED_BUT_HELD"),
        (("binding_artifact", "binding_sha256"), "0" * 64),
        (("identity_packet", "helper_sha256"), "0" * 64),
        (("identity_packet", "receipt", "camera_activation_count"), 1),
        (("inventory_packet", "receipt", "cleanup_confirmed"), False),
        (("generic_review", "report_sha256"), "0" * 64),
        (("generic_review", "candidate_record", "os_instance_id"), "changed-instance"),
    ],
)
def test_extra_stale_hash_wrong_choice_or_modified_projection_rejected(path, value):
    snapshot = physical_enrollment().export_snapshot()
    cursor = snapshot
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = value
    with pytest.raises(NativeCameraEnrollmentError):
        verify(snapshot)
    with pytest.raises(PhysicalCameraSelectionError):
        selection(snapshot)


@pytest.mark.parametrize(
    "role", ["generic_review", "inventory_packet", "identity_packet"]
)
def test_full_packet_family_required_for_held_review(role):
    snapshot = physical_enrollment(scenario="wrong-device").export_snapshot()
    snapshot[role] = None
    with pytest.raises(NativeCameraEnrollmentError):
        verify(snapshot)


def test_held_flags_and_missing_binding_are_recomputed():
    original = physical_enrollment(scenario="wrong-device").export_snapshot()
    for mutate in (
        lambda s: s["view"]["identity"].update(generic_device_match=True),
        lambda s: s["view"]["identity"].update(blockers=[]),
        lambda s: s["view"]["review"].update(binding_sha256="1" * 64),
        lambda s: s.update(
            binding_artifact=physical_enrollment().export_snapshot()["binding_artifact"]
        ),
    ):
        snapshot = deepcopy(original)
        mutate(snapshot)
        with pytest.raises(NativeCameraEnrollmentError):
            verify(snapshot)


def test_ordered_inventory_occurrences_tokens_and_generations_stay_exact():
    owner, _, token = identified("duplicate-name")
    original = owner.review(token, "reviewer")
    assert verify(original) == original
    for mutation in ("reverse", "duplicate", "missing", "generation"):
        snapshot = deepcopy(original)
        rows = snapshot["view"]["candidates"]
        if mutation == "reverse":
            rows.reverse()
        elif mutation == "duplicate":
            rows[1]["choice_id"] = rows[0]["choice_id"]
        elif mutation == "missing":
            rows.pop()
        else:
            rows[1]["choice_id"] = "endpoint-2-" + "1" * 32
        with pytest.raises(NativeCameraEnrollmentError):
            verify(snapshot)


def test_no_file_process_native_calls_or_new_native_choices_and_uuid_independent_output(
    monkeypatch,
):
    snapshot = physical_enrollment(unicode=True).export_snapshot()

    def forbidden(*args, **kwargs):
        raise AssertionError(
            "Retained verification must not perform I/O or issue endpoint choices"
        )

    with monkeypatch.context() as blocked:
        blocked.setattr("builtins.open", forbidden)
        blocked.setattr(Path, "read_bytes", forbidden)
        blocked.setattr(Path, "stat", forbidden)
        blocked.setattr(subprocess, "run", forbidden)
        blocked.setattr(subprocess, "Popen", forbidden)
        blocked.setattr(
            "rocell.application.wizard_native_camera_enrollment.uuid4", forbidden
        )
        for offset in (100, 200):
            choices = iter(range(offset, offset + 50))
            blocked.setattr(
                "rocell.application.wizard_device_selection.uuid4",
                lambda: SimpleNamespace(hex=f"{next(choices):032x}"),
            )
            assert verify(snapshot) == snapshot
            assert (
                selection(snapshot).identity_document["metadata_review"]
                == snapshot["binding_artifact"]["payload"]
            )


@pytest.mark.parametrize("mode", ["physical", "rehearsal"])
@pytest.mark.parametrize("scenario", ["nominal", "missing-mapping", "wrong-device"])
@pytest.mark.parametrize("version", [1, 2])
def test_actual_arrival_published_producer_roundtrip_without_replay(
    service_setup, monkeypatch, mode, scenario, version
):
    # Explicit host model avoids platform.py's cold Windows `ver` subprocess.
    monkeypatch.setattr(
        "rocell.application.arrival_wizard_service.sys.platform", "win32"
    )
    service, provider, _ = service_setup(mode, scenario)
    if version == 2:
        from test_windows_camera_driver_metadata import driver_fixture

        def driver_packet(kind, packet):
            if kind != "identity":
                return
            receipt = packet["receipt"]
            receipt["schema"] = "rocell.windows_camera_identity.v2"
            receipt["driver"] = None
            if receipt["device"] is not None:
                receipt["driver"] = driver_fixture()["driver"]
                receipt["driver"]["devnode"] = receipt["device"]["devnode"]
                receipt["api_calls"] += 4
                receipt["observed_property_bytes"] += 512

        provider.mutate = driver_packet
    token = discover(service)
    resolve_review(service, token)
    snapshot = service._native_camera.export_snapshot()
    before = list(provider.calls)
    assert (
        verify(snapshot, source=service.source_sha256, session=service.session_id)
        == snapshot
    )
    assert provider.calls == before == ["inventory", "identity"]
    assert snapshot["view"] == service.view()["native_camera_enrollment"]
    assert (
        snapshot["identity_packet"]["receipt"]["schema"]
        == f"rocell.windows_camera_identity.v{version}"
    )
