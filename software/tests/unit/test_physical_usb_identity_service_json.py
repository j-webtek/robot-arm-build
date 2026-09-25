"""Actual service JSON projection/export with modeled typed campaign originals.

No original-store or worker execution is claimed here. The same actual permit
and result dataclasses used by dispatch are placed at its retained cache seam;
the service and strict file exporter then run unmodified.
"""

from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from threading import Event
import subprocess

import pytest

from rocell.application import physical_usb_identity_service as module
from rocell.application import physical_usb_identity_export as exporter
from rocell.application.cell_commissioning_coordinator import AttemptResult
from rocell.application.physical_camera_acquisition_service import (
    PhysicalCameraAcquisitionService,
)
from rocell.application.physical_camera_setup_service import PhysicalCameraSetupService
from rocell.application.physical_onboarding_attempts import AttemptState
from rocell.providers.windows import owned_usb_identity_runner
from rocell.providers.windows.usb_identity_protocol import canonical
from test_physical_usb_identity_campaign import campaign, permit_for
from test_physical_usb_identity_export import read_receipt


@pytest.fixture
def retained_typed_original(monkeypatch, request):
    def forbidden(*a, **k):
        pytest.fail("cached metadata export attempted source/process/device I/O")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(owned_usb_identity_runner, "_new_owner", forbidden)
    monkeypatch.setattr(module, "source_fingerprint", forbidden)
    c = campaign()
    permit = permit_for(c)
    result = AttemptResult(
        permit.attempt_id,
        AttemptState.SEALED_UNCERTAIN,
        permit.permit_sha256,
        ("USB_ACCOUNTING_UNAVAILABLE",),
        None,
        True,
        composition=c.composition,
    )
    setup = PhysicalCameraSetupService(
        PhysicalCameraAcquisitionService(
            Path(c.operation.to_dict()["runtime"]["workspace"]),
            launch_id="wizard-" + "1" * 32,
            source_sha256=c.operation.to_dict()["source_sha256"],
            mode="physical",
        )
    )
    owner = module.PhysicalUsbIdentityService(setup)
    original = dict(
        permit=asdict(permit),
        result=asdict(result) if getattr(request, "param", True) else None,
        admission_evidence=None,
        evidence=None,
        evidence_sha256=None,
        reference=None,
        retention="M1_TERMINAL_READ_BACK_EVIDENCE_PENDING",
    )
    owner._attempt = dict(
        action_id=module.COLLECT,
        usb_id="usbidentity-" + "1" * 32,
        records={},
        dispatch=dict(dispatch=None, original=original),
    )
    owner.invalidate()
    return owner, original


@pytest.mark.parametrize("retained_typed_original", [True, False], indirect=True)
def test_actual_dataclass_projection_survives_strict_export(
    retained_typed_original, tmp_path
):
    owner, original = retained_typed_original
    before = canonical(original)
    assert type(original["permit"]["registration"]["resources"]) is tuple
    assert type(original["permit"]["registration"]["stage"]) is not str
    projected = owner.retained_diagnostics()
    saved = projected["attempt"]["dispatch"]["original"]
    assert type(saved["permit"]["registration"]["resources"]) is list
    assert type(saved["permit"]["registration"]["stage"]) is str
    if original["result"] is not None:
        assert type(saved["result"]["state"]) is str
        assert type(saved["result"]["reason_codes"]) is list
    assert canonical(saved) == before
    assert canonical(original) == before  # Projection never mutates retained DTOs.

    malformed = deepcopy(projected)
    malformed["attempt"]["dispatch"]["original"] = original
    with pytest.raises(ValueError):
        exporter.prepare_usb_identity_diagnostics_export(
            malformed, source_sha256=owner.source_sha256, launch_id=owner.launch_id
        )  # The strict external boundary still rejects Enum/tuple objects.

    result = owner.perform(
        module.EXPORT,
        dict(confirm_metadata_export=True),
        expected_context_sha256="f" * 64,  # Historical housekeeping, not admission.
        cancellation=Event(),
        progress=lambda _: None,
        export_parent=tmp_path / "metadata-exports",
    )
    owner.validate_publication(result)
    owner.publication_completed("modeled-export-log")
    assert result["counter_coverage"] == "NO_DEVICE_IO"
    assert result["device_open_count"] == 0
    snapshot, parts = read_receipt(owner.export_metadata())
    restored = exporter.restore_usb_identity_diagnostics(snapshot, parts)
    assert canonical(restored["attempt"]["dispatch"]["original"]) == before
    assert restored["attempt"]["dispatch"]["original"]["evidence"] is None
    assert owner.view()["publication"]["status"] == "HISTORICAL_HELD"


def test_internal_json_projection_does_not_stringify_arbitrary_objects(
    retained_typed_original,
):
    owner, _ = retained_typed_original
    owner._attempt["dispatch"]["original"]["unexpected"] = object()
    with pytest.raises(ValueError, match="INVALID_JSON_VALUE"):
        owner.retained_diagnostics()
