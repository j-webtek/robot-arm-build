"""Physical-shaped metadata/permits test joins only; no device/helper runs."""

from dataclasses import asdict, replace
from pathlib import Path
from threading import Event

import pytest

from rocell.application import physical_usb_identity_campaign as m
from rocell.application.cell_commissioning_coordinator import (
    ExactOperationPermit,
    RegisteredActionRequest,
    UsbIdentityAdmissionSnapshot,
)
from rocell.application.physical_camera_selection import selection_from_enrollment
from rocell.application.usb_identity_stage_policy import (
    UsbIdentityAdmissionIdentity,
    IDENTITY_SCHEMA,
    usb_identity_stage_policy,
)
from rocell.providers.windows.usb_identity_registration import (
    usb_identity_runtime_candidate,
    review_usb_identity_runtime,
)
from test_physical_camera_selection import physical_enrollment
from test_wizard_native_camera_enrollment import SOURCE, SESSION as LAUNCH
from test_physical_camera_coordinator import admission, CELL, SESSION


def inputs(workspace=None):
    selected = selection_from_enrollment(
        physical_enrollment(), source_sha256=SOURCE, launch_session_id=LAUNCH
    )
    runtime = usb_identity_runtime_candidate(
        workspace or Path.cwd(), source_sha256=SOURCE
    )
    policy = usb_identity_stage_policy()
    operation = m.usb_identity_operation(
        cell_id=CELL,
        session_id=SESSION,
        selection=selected,
        runtime=runtime,
        policy=policy,
    )
    sd = selected.identity_document
    review = review_usb_identity_runtime(
        runtime,
        selection_sha256=selected.sha256,
        native_identity_sha256=sd["native_identity_sha256"],
        endpoint_sha256=sd["endpoint_sha256"],
        device_instance_id_sha256=m.digest(
            sd["metadata_review"]["observed_instance_id"].encode()
        ),
        operation_sha256=operation.sha256,
        operator_id="collector",
        reviewer_id="reviewer",
        launch_session_id=LAUNCH,
        reviewed_at_ns=1,
    )
    subjects = []
    for role, sha in (
        ("metadata", "1" * 64),
        ("policy_review", "2" * 64),
        ("runtime_review", review.sha256),
    ):
        subjects.append(
            dict(
                role=role,
                document_sha256=sha,
                reference=dict(
                    evidence_id="evidence-" + sha,
                    package_sha256=sha,
                    manifest_sha256=sha,
                    stage="camera_identity",
                    payload_sha256=sha,
                    payload_bytes=100,
                ),
            )
        )
    rd = review.to_dict()
    identity = UsbIdentityAdmissionIdentity(
        m.canonical(
            dict(
                schema=IDENTITY_SCHEMA,
                cell_id=CELL,
                session_id=SESSION,
                source_sha256=SOURCE,
                header_sha256="4" * 64,
                stage_policy_sha256=policy.sha256,
                policy_review_sha256="2" * 64,
                runtime_review_sha256=review.sha256,
                runtime_registration_sha256=runtime.sha256,
                original_subjects=subjects,
                **{
                    key: rd[key]
                    for key in (
                        "selection_sha256",
                        "native_identity_sha256",
                        "endpoint_sha256",
                        "device_instance_id_sha256",
                        "operation_sha256",
                    )
                },
            )
        )
    )
    return operation, identity, review


def campaign():
    op, identity, review = inputs()
    return m.PhysicalUsbIdentityCampaign(op, identity=identity, review=review)


def permit_for(c):
    base = asdict(admission())
    base.update(
        stage=c.registration().stage, selected_identity_sha256=c.identity.sha256
    )
    snapshot = UsbIdentityAdmissionSnapshot(
        **base, usb_query_policy_sha256=usb_identity_stage_policy().sha256
    )
    return ExactOperationPermit(
        "attempt-" + "8" * 32,
        RegisteredActionRequest(
            CELL,
            SESSION,
            c.registration().action_id,
            "one-model-request",
            snapshot.challenge_sha256,
        ),
        snapshot,
        c.registration(),
        1,
        25_000_000_001,
        "9" * 32,
    )


def test_constructor_and_preparation_inert(monkeypatch):
    import subprocess

    def forbidden(*args, **kwargs):
        pytest.fail("pure campaign accessed a file or started a process")

    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    c = campaign()
    p = permit_for(c)
    prepared = c.preparation_for_permit(p)
    assert prepared.request.to_dict()["permit_sha256"] == p.permit_sha256
    assert prepared.identity.sha256 == c.identity.sha256
    assert c.registration().budget.maximum_writes == 0
    assert c.registration().budget.maximum_frames == 0
    assert c.registration().budget.maximum_opens == 32


def test_operation_precedes_and_does_not_embed_reviews():
    op, identity, review = inputs()
    assert "review" not in op.to_dict() and "identity" not in op.to_dict()
    assert "permit" not in op.to_dict()
    assert (
        identity.to_dict()["operation_sha256"]
        == review.to_dict()["operation_sha256"]
        == op.sha256
    )
    assert m.UsbIdentityOperation(op.payload).payload == op.payload


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema", "other"),
        ("source_sha256", "f" * 64),
        ("policy_sha256", "f" * 64),
        ("cell_id", "other"),
        ("session_id", "other"),
        ("physical_authority", True),
        ("physical_authority", 0),
        ("workspace", "C:\\wrong"),
    ],
)
def test_operation_rejects_substitutions(field, value):
    op, _, _ = inputs()
    d = op.to_dict()
    d[field] = value
    with pytest.raises(ValueError):
        m.UsbIdentityOperation(m.canonical(d))


@pytest.mark.parametrize(
    "field",
    [
        "selection_sha256",
        "native_identity_sha256",
        "endpoint_sha256",
        "device_instance_id_sha256",
        "operation_sha256",
        "runtime_registration_sha256",
        "source_sha256",
        "cell_id",
        "session_id",
    ],
)
def test_campaign_rejects_identity_substitution(field):
    op, identity, review = inputs()
    d = identity.to_dict()
    d[field] = (
        "wizard-physical-camera-" + "7" * 16
        if field == "cell_id"
        else "physical-camera-" + "7" * 32 if field == "session_id" else "7" * 64
    )
    changed = UsbIdentityAdmissionIdentity(m.canonical(d))
    with pytest.raises(ValueError):
        m.PhysicalUsbIdentityCampaign(op, identity=changed, review=review)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda p: replace(
            p, registration=replace(p.registration, operation_sha256="f" * 64)
        ),
        lambda p: replace(
            p, registration=replace(p.registration, worker_executable_sha256="f" * 64)
        ),
        lambda p: replace(
            p, request=replace(p.request, expected_challenge_sha256="f" * 64)
        ),
        lambda p: replace(
            p, admission=replace(p.admission, selected_identity_sha256="f" * 64)
        ),
        lambda p: replace(
            p, admission=replace(p.admission, source_binding_sha256="f" * 64)
        ),
        lambda p: replace(
            p, admission=replace(p.admission, usb_query_policy_sha256="f" * 64)
        ),
        lambda p: replace(p, admission=admission()),
    ],
)
def test_permit_exact_new_domain_only(mutation):
    c = campaign()
    with pytest.raises(ValueError):
        c.preparation_for_permit(mutation(permit_for(c)))


def test_no_unscoped_or_repeat_guard_path():
    c = campaign()
    with pytest.raises(ValueError, match="SCOPED_USB"):
        c.run_campaign()
    with pytest.raises(ValueError, match="SCOPED_USB"):
        c.run_retained_campaign()
    c._bind_application_guard(lambda: None)
    with pytest.raises(ValueError, match="GUARD_REQUIRED_ONCE"):
        c._bind_application_guard(lambda: None)
