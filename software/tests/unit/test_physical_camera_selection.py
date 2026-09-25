"""Physical-shaped metadata fixtures only; no received unit/provider is used."""

from copy import deepcopy
from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from rocell.application.physical_camera_selection import (
    MAX_SELECTION_BYTES,
    PhysicalCameraSelection,
    PhysicalCameraSelectionError,
    selection_from_enrollment,
)
from rocell.application.commissioning_m1_persistence import _freeze_document
from rocell.application.wizard_native_camera_enrollment import (
    WizardNativeCameraEnrollment,
)
from rocell.application.wizard_native_camera_metadata import (
    RehearsalNativeCameraMetadataProvider,
)
from rocell.providers.windows.camera_worker_client import CameraCandidate
from test_wizard_native_camera_enrollment import (
    SOURCE,
    SESSION,
    generic_review,
    identified,
)


def physical_enrollment(*, unicode=False, scenario="nominal"):
    """Actual pure registry/parser, explicitly injected physical-shaped packets.

    Provenance fields model the physical interface solely to test strict joins.
    Limitations continue to say INCAPABLE FIXTURE; no test is hardware evidence.
    """
    provider = RehearsalNativeCameraMetadataProvider(scenario)
    inventory = provider.inventory()
    candidate = CameraCandidate(**inventory["receipt"]["devices"][0])
    identity = provider.identity(candidate)
    descriptor = {"provenance": "WINDOWS_NATIVE_METADATA", "helper_sha256": "b" * 64}
    for packet in (inventory, identity):
        packet.update(descriptor)
    if unicode:
        endpoint = candidate.symbolic_link + "/caméra-測試"
        inventory["receipt"]["devices"][0]["symbolic_link"] = endpoint
        identity["receipt"]["requested_endpoint"] = endpoint
        identity["receipt"]["mapping"]["interface_path"]["value"] = endpoint
    model = WizardNativeCameraEnrollment("physical", SESSION, SOURCE, descriptor)
    model.ingest_inventory(
        inventory,
        operation_id="native-inventory",
        generic_review=generic_review(mode="physical"),
    )
    token = model.choices()[0]["value"]
    model.retain_identity(token, identity, operation_id="native-identity")
    model.review(token, "réviseur" if unicode else "reviewer")
    return model


def selected(model):
    return selection_from_enrollment(
        model, source_sha256=SOURCE, launch_session_id=SESSION
    )


@pytest.mark.parametrize("unicode", [False, True])
def test_actual_enrollment_to_ascii_m1_identity_preserves_original_review(unicode):
    model = physical_enrollment(unicode=unicode)
    before = model.export_snapshot()
    original = model.binding()
    result = selected(model)
    document = result.identity_document
    assert result.payload == _freeze_document(document)
    assert not result.payload.endswith(b"\n")
    result.payload.decode("ascii")
    assert result.sha256 == hashlib.sha256(result.payload).hexdigest()
    assert result.binding.binding_sha256 == result.sha256
    assert result.binding.symbolic_link == original.symbolic_link
    assert result.binding.endpoint_sha256 == original.endpoint_sha256
    assert result.sha256 != original.binding_sha256
    assert document["metadata_review_binding_sha256"] == original.binding_sha256
    original_bytes = json.dumps(
        document["metadata_review"],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    assert hashlib.sha256(original_bytes).hexdigest() == original.binding_sha256
    if unicode:
        assert (
            hashlib.sha256(_freeze_document(document["metadata_review"])).hexdigest()
            != original.binding_sha256
        )
    assert model.export_snapshot() == before
    assert result.safe_summary() == {
        "endpoint_sha256": original.endpoint_sha256,
        "identity_sha256": result.sha256,
        "metadata_review_binding_sha256": original.binding_sha256,
        "generic_candidate_sha256": before["view"]["generic_candidate_sha256"],
    }
    assert (
        document["native_identity_sha256"]
        == before["view"]["identity"]["identity_sha256"]
    )
    assert len(result.payload) < MAX_SELECTION_BYTES
    for value in (document, document["metadata_review"]):
        for key in (
            "qualified",
            "connected",
            "physical_authority",
            "persistent_binding",
        ):
            assert value[key] is False
    assert (
        "CAMERA_NEGOTIATED_LINK_SPEED_NOT_OBSERVED"
        in document["metadata_review"]["blockers"]
    )


@pytest.mark.parametrize(
    "source,session", [("c" * 64, SESSION), (SOURCE, "other-launch"), (False, SESSION)]
)
def test_current_launch_source_must_match(source, session):
    with pytest.raises(PhysicalCameraSelectionError):
        selection_from_enrollment(
            physical_enrollment(), source_sha256=source, launch_session_id=session
        )


@pytest.mark.parametrize("scenario", ["missing-mapping", "wrong-device"])
def test_held_identity_cannot_be_selected(scenario):
    with pytest.raises(PhysicalCameraSelectionError, match="current physical"):
        selected(physical_enrollment(scenario=scenario))


def test_rehearsal_and_unreviewed_or_invalidated_states_rejected():
    rehearsal, _, token = identified()
    rehearsal.review(token, "reviewer")
    with pytest.raises(PhysicalCameraSelectionError):
        selected(rehearsal)
    model = physical_enrollment()
    model.invalidate_review("REVIEW_CHANGED")
    with pytest.raises(PhysicalCameraSelectionError):
        selected(model)
    model.invalidate("SOURCE_CHANGED")
    with pytest.raises(PhysicalCameraSelectionError):
        selected(model)
    with pytest.raises(PhysicalCameraSelectionError):
        selected(model.export_snapshot())


@pytest.mark.parametrize(
    "path,value",
    [
        (("binding_artifact", "binding_sha256"), "0" * 64),
        (("binding_artifact", "payload", "symbolic_link"), "guessed-endpoint"),
        (("view", "identity", "container_match"), False),
        (("view", "identity", "exact_endpoint_observed"), 1),
        (("view", "review", "reviewer_id"), "another-reviewer"),
        (("view", "physical_authority"), True),
        (("view", "generic_report_sha256"), "0" * 64),
        (("identity_packet", "helper_sha256"), "0" * 64),
        (("generic_review", "report_sha256"), "0" * 64),
    ],
)
def test_detached_snapshot_tampering_is_rejected(monkeypatch, path, value):
    model = physical_enrollment()
    original = WizardNativeCameraEnrollment.export_snapshot

    def forged(self):
        snapshot = original(self)
        parent = snapshot
        for key in path[:-1]:
            parent = parent[key]
        parent[path[-1]] = value
        return snapshot

    monkeypatch.setattr(WizardNativeCameraEnrollment, "export_snapshot", forged)
    with pytest.raises(PhysicalCameraSelectionError):
        selected(model)


@pytest.mark.parametrize(
    "change",
    [
        "extra",
        "utf8",
        "newline",
        "reviewhash",
        "source",
        "authority",
        "over-limit",
        "endpoint",
    ],
)
def test_restored_selection_is_strict_canonical_bounded_and_cross_bound(change):
    selection = selected(physical_enrollment(unicode=True))
    document = selection.identity_document
    if change == "extra":
        document["extra"] = True
    elif change == "reviewhash":
        document["metadata_review_binding_sha256"] = "0" * 64
    elif change == "source":
        document["source_sha256"] = "0" * 64
    elif change == "authority":
        document["qualified"] = True
    elif change == "endpoint":
        document["symbolic_link"] = document["metadata_review"]["symbolic_link"] = (
            "guessed-endpoint"
        )
        document["metadata_review_binding_sha256"] = hashlib.sha256(
            json.dumps(
                document["metadata_review"],
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode()
        ).hexdigest()
    payload = _freeze_document(document)
    if change == "utf8":
        payload = json.dumps(
            document, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    elif change == "newline":
        payload += b"\n"
    elif change == "over-limit":
        payload = b" " * (MAX_SELECTION_BYTES + 1)
    with pytest.raises(PhysicalCameraSelectionError):
        PhysicalCameraSelection(payload)


def test_immutable_artifact_and_detached_identity_summary():
    model = physical_enrollment()
    result = selected(model)
    before = result.payload
    document = result.identity_document
    document["metadata_review"]["reviewer_id"] = "mutated"
    summary = result.safe_summary()
    summary["identity_sha256"] = "0" * 64
    assert result.payload == before
    assert result.identity_document["metadata_review"]["reviewer_id"] != "mutated"
    assert result.safe_summary()["identity_sha256"] != "0" * 64
    with pytest.raises(FrozenInstanceError):
        result.payload = b"{}"
    model.invalidate("LATER_SOURCE_CHANGE")
    assert result.payload == before  # Original history, not current permission.
    with pytest.raises(PhysicalCameraSelectionError):
        selected(model)


def test_conversion_and_restoration_never_use_files_processes_or_devices(monkeypatch):
    model = physical_enrollment()

    def forbidden(*args, **kwargs):
        raise AssertionError("Selection must remain pure")

    with monkeypatch.context() as blocked:
        blocked.setattr("builtins.open", forbidden)
        blocked.setattr(Path, "read_bytes", forbidden)
        blocked.setattr(Path, "stat", forbidden)
        blocked.setattr(subprocess, "run", forbidden)
        blocked.setattr(subprocess, "Popen", forbidden)
        blocked.setattr(
            "rocell.providers.windows.camera_worker_client.WindowsCameraWorkerClient.enumerate_metadata",
            forbidden,
        )
        blocked.setattr(
            "rocell.providers.windows.camera_worker_client.WindowsCameraWorkerClient.resolve_identity_metadata",
            forbidden,
        )
        result = selected(model)
        assert PhysicalCameraSelection(result.payload).binding == result.binding
        assert result.safe_summary()["identity_sha256"] == result.sha256
