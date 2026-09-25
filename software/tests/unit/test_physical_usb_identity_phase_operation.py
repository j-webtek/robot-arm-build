"""Pure phase subjects over actual codecs and explicitly MODELED unit facts.

No original-store admission, file inspection, process or device operation is
performed. The retained HELD packet is the existing modeled cancellation fixture,
not an observed USB query or an assertion of received-hardware qualification.
"""

from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import subprocess

import pytest

from rocell.application import physical_usb_identity_campaign as m
from rocell.application.physical_camera_selection import PhysicalCameraSelection
from rocell.application.physical_camera_usb_qualification import UsbQualificationPlan
from rocell.application.usb_identity_stage_policy import UsbIdentityAdmissionIdentity
from rocell.providers.windows.usb_identity_registration import (
    UsbIdentityRuntimeRegistration,
    review_usb_identity_runtime,
)
from test_physical_camera_usb_qualification import plan_fixture
from test_physical_camera_usb_readback import modeled_clean_held_evidence
from test_physical_received_camera import prerequisites, workspace
from test_physical_usb_identity_campaign import inputs, permit_for


@pytest.fixture
def phase_inputs(prerequisites):
    plan, _, _ = plan_fixture(prerequisites)
    legacy, _, _ = inputs()
    d = legacy.to_dict()
    return dict(
        plan=plan,
        phase="BASELINE",
        operation_id="usbphase-" + "1" * 32,
        predecessor_sha256=None,
        selection=PhysicalCameraSelection(m.canonical(d["selection"])),
        runtime=UsbIdentityRuntimeRegistration(m.canonical(d["runtime"])),
        policy=m.usb_identity_stage_policy(),
    )


def phase_campaign(operation):
    """Actual review/identity producers; their original references are modeled."""
    _, identity, old_review = inputs()
    op, rd = operation.to_dict(), old_review.to_dict()
    selection = PhysicalCameraSelection(m.canonical(op["selection"]))
    selected = selection.identity_document
    runtime = UsbIdentityRuntimeRegistration(m.canonical(op["runtime"]))
    review = review_usb_identity_runtime(
        runtime,
        selection_sha256=selection.sha256,
        native_identity_sha256=selected["native_identity_sha256"],
        endpoint_sha256=selected["endpoint_sha256"],
        device_instance_id_sha256=m.digest(
            selected["metadata_review"]["observed_instance_id"].encode("utf-8")
        ),
        **{
            key: rd[key]
            for key in (
                "operator_id",
                "reviewer_id",
                "launch_session_id",
                "reviewed_at_ns",
            )
        },
        operation_sha256=operation.sha256,
    )
    document = identity.to_dict()
    document.update(
        cell_id=op["cell_id"],
        session_id=op["session_id"],
        header_sha256=op["phase_binding"]["header_sha256"],
        operation_sha256=operation.sha256,
        runtime_review_sha256=review.sha256,
        **{
            key: review.to_dict()[key]
            for key in (
                "selection_sha256",
                "native_identity_sha256",
                "endpoint_sha256",
                "device_instance_id_sha256",
            )
        },
    )
    subject = document["original_subjects"][2]
    subject["document_sha256"] = review.sha256
    subject["reference"].update(
        evidence_id="evidence-" + review.sha256,
        package_sha256=review.sha256,
        manifest_sha256=review.sha256,
        payload_sha256=review.sha256,
        payload_bytes=len(review.payload),
    )
    return m.PhysicalUsbIdentityCampaign(
        operation,
        identity=UsbIdentityAdmissionIdentity(m.canonical(document)),
        review=review,
    )


def phase_permit(campaign):
    permit = permit_for(campaign)
    op = campaign.operation.to_dict()
    admission = replace(
        permit.admission, cell_id=op["cell_id"], session_id=op["session_id"]
    )
    return replace(
        permit,
        admission=admission,
        request=replace(
            permit.request,
            cell_id=op["cell_id"],
            session_id=op["session_id"],
            expected_challenge_sha256=admission.challenge_sha256,
        ),
        expires_at_ns=30_000_000_001,
    )


def test_phase_builder_is_inert_and_exactly_retains_plan(phase_inputs, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("pure phase operation performed I/O")

    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    operation = m.usb_identity_phase_operation(**phase_inputs)
    d = operation.to_dict()
    plan = phase_inputs["plan"]
    assert d["schema"] == "rocell.physical_usb_identity_operation.v2"
    assert m.canonical(d["qualification_plan"]) == plan.payload
    assert d["phase_binding"] == dict(
        plan_sha256=plan.sha256,
        header_sha256=plan.to_dict()["binding"]["header_sha256"],
        trial_id=plan.to_dict()["binding"]["trial_id"],
        phase="BASELINE",
        ordinal=0,
        operation_id=phase_inputs["operation_id"],
        predecessor_sha256=None,
    )
    assert not d["physical_authority"]
    assert len(operation.payload) <= m.MAX_OPERATION_BYTES == 80 * 1024
    for forbidden_key in ("review", "permit", "identity", "created_at_utc_ns"):
        assert forbidden_key not in d
    with pytest.raises(FrozenInstanceError):
        operation.payload = b"{}"
    d["phase_binding"]["operation_id"] = "changed"
    assert operation.to_dict()["phase_binding"]["operation_id"] != "changed"


@pytest.mark.parametrize(
    "phase,ordinal,predecessor",
    [
        ("BASELINE", 0, None),
        ("AFTER_RECONNECT", 2, "2" * 64),
        ("AFTER_REBOOT", 3, "3" * 64),
    ],
)
def test_each_observed_phase_prepares_exact_review_request_and_evidence(
    phase_inputs, phase, ordinal, predecessor
):
    args = dict(
        phase_inputs,
        phase=phase,
        operation_id="usbphase-" + str(ordinal + 1) * 32,
        predecessor_sha256=predecessor,
    )
    operation = m.usb_identity_phase_operation(**args)
    assert operation.to_dict()["phase_binding"]["ordinal"] == ordinal
    assert (
        m.verify_phase_operation_context(
            operation, args["plan"], phase, args["operation_id"], predecessor
        ).payload
        == operation.payload
    )
    campaign = phase_campaign(operation)
    permit = phase_permit(campaign)
    preparation = campaign.preparation_for_permit(permit)
    assert campaign.operation.payload == operation.payload
    assert campaign.registration().operation_sha256 == operation.sha256
    prepared = preparation.to_dict()
    assert prepared["review"]["operation_sha256"] == operation.sha256
    assert prepared["request"]["operation_sha256"] == operation.sha256
    assert prepared["identity"]["operation_sha256"] == operation.sha256
    assert prepared["request"]["permit_sha256"] == permit.permit_sha256
    evidence = modeled_clean_held_evidence(preparation)
    assert evidence.status == "HELD"
    checked = m.verify_usb_identity_campaign_evidence(
        evidence,
        campaign=campaign,
        permit=permit,
        expected_evidence_sha256=evidence.sha256,
    )
    assert checked.payload == evidence.payload
    # Adding phase context does not widen the existing descriptor effect budget.
    assert campaign.registration().budget == m.CampaignBudget(
        25000, 128 * 1024, 32, 128, 0, 0, 32
    )
    assert prepared["request"]["native_duration_ms"] == 10000
    assert prepared["request"]["admission_timeout_ms"] == 5000


def test_three_subjects_and_native_requests_are_distinct(phase_inputs):
    operations, requests = [], []
    for phase, ordinal in (
        ("BASELINE", 0),
        ("AFTER_RECONNECT", 2),
        ("AFTER_REBOOT", 3),
    ):
        op = m.usb_identity_phase_operation(
            **dict(
                phase_inputs,
                phase=phase,
                operation_id="usbphase-" + str(ordinal + 1) * 32,
                predecessor_sha256=None if ordinal == 0 else str(ordinal) * 64,
            )
        )
        c = phase_campaign(op)
        operations.append(op)
        requests.append(c.preparation_for_permit(phase_permit(c)).request)
    assert (
        len({op.sha256 for op in operations})
        == len({r.request_sha256 for r in requests})
        == 3
    )
    for other in operations[1:]:
        with pytest.raises(ValueError, match="CONTEXT_MISMATCH"):
            m.verify_phase_operation_context(
                other,
                phase_inputs["plan"],
                "BASELINE",
                phase_inputs["operation_id"],
                None,
            )


@pytest.mark.parametrize(
    "field,value",
    [
        ("plan_sha256", "f" * 64),
        ("header_sha256", "f" * 64),
        ("trial_id", "usbtrial-" + "f" * 32),
        ("trial_id", "generic-trial"),
        ("operation_id", "standalone-diagnostic"),
        ("operation_id", "usbphase-" + "F" * 32),
        ("operation_id", None),
        ("ordinal", False),
        ("ordinal", 0.0),
        ("ordinal", 1),
        ("phase", "RECONNECT_ABSENCE"),
        ("phase", []),
        ("predecessor_sha256", "1" * 64),
        ("unexpected", False),
    ],
)
def test_phase_binding_rejects_substitution_and_noncanonical_types(
    phase_inputs, field, value
):
    d = m.usb_identity_phase_operation(**phase_inputs).to_dict()
    d["phase_binding"][field] = value
    with pytest.raises(ValueError):
        m.UsbIdentityOperation(m.canonical(d))


@pytest.mark.parametrize("predecessor", [None, "", "e" * 63, True, 0, {}])
def test_later_phase_requires_preceding_original_hash(phase_inputs, predecessor):
    with pytest.raises(ValueError, match="PREDECESSOR"):
        m.usb_identity_phase_operation(
            **dict(
                phase_inputs, phase="AFTER_RECONNECT", predecessor_sha256=predecessor
            )
        )


@pytest.mark.parametrize("field", ["cell_id", "session_id", "source_sha256"])
def test_plan_context_cannot_replace_base_original_context(phase_inputs, field):
    d = m.usb_identity_phase_operation(**phase_inputs).to_dict()
    plan = d["qualification_plan"]
    old = plan["binding"][field]
    plan["binding"][field] = old[:-1] + ("f" if old[-1] != "f" else "e")
    d["phase_binding"]["plan_sha256"] = m.digest(m.canonical(plan))
    with pytest.raises(ValueError, match="PLAN_CONTEXT"):
        m.UsbIdentityOperation(m.canonical(d))


@pytest.mark.parametrize("change", ["plan", "phase", "operation_id", "predecessor"])
def test_independent_phase_context_rejects_rehashed_or_wrong_original(
    phase_inputs, change
):
    operation = m.usb_identity_phase_operation(**phase_inputs)
    plan, phase, op_id, previous = (
        phase_inputs["plan"],
        "BASELINE",
        phase_inputs["operation_id"],
        None,
    )
    if change == "plan":
        d = plan.to_dict()
        d["cable_label"] = "different-declared-cable"
        plan = UsbQualificationPlan(m.canonical(d))
    elif change == "phase":
        phase, previous = "AFTER_RECONNECT", "2" * 64
    elif change == "operation_id":
        op_id = "usbphase-" + "e" * 32
    else:
        operation = m.usb_identity_phase_operation(
            **dict(phase_inputs, phase="AFTER_RECONNECT", predecessor_sha256="2" * 64)
        )
        phase, previous = "AFTER_RECONNECT", "3" * 64
    with pytest.raises(ValueError, match="CONTEXT_MISMATCH"):
        m.verify_phase_operation_context(operation, plan, phase, op_id, previous)


def test_original_header_is_also_bound_to_admission_identity(phase_inputs):
    operation = m.usb_identity_phase_operation(**phase_inputs)
    c = phase_campaign(operation)
    d = c.identity.to_dict()
    d["header_sha256"] = "f" * 64
    prepared = c.preparation_for_permit(phase_permit(c))
    with pytest.raises(ValueError, match="ORIGINAL_HEADER"):
        m.PhysicalUsbIdentityCampaign(
            operation,
            identity=UsbIdentityAdmissionIdentity(m.canonical(d)),
            review=prepared.review,
        )


def test_previous_phase_review_or_retained_evidence_cannot_be_reused(phase_inputs):
    op = m.usb_identity_phase_operation(**phase_inputs)
    original = phase_campaign(op)
    permit = phase_permit(original)
    prepared = original.preparation_for_permit(permit)
    evidence = modeled_clean_held_evidence(prepared)
    new_op = m.usb_identity_phase_operation(
        **dict(phase_inputs, operation_id="usbphase-" + "2" * 32)
    )
    with pytest.raises(ValueError, match="IDENTITY_MISMATCH"):
        m.PhysicalUsbIdentityCampaign(
            new_op, identity=original.identity, review=prepared.review
        )
    successor = phase_campaign(new_op)
    with pytest.raises(ValueError):
        successor.preparation_for_permit(permit)
    with pytest.raises(ValueError, match="ORIGINAL_CAMPAIGN_EVIDENCE_MISMATCH"):
        m.verify_usb_identity_campaign_evidence(
            evidence,
            campaign=successor,
            permit=phase_permit(successor),
            expected_evidence_sha256=evidence.sha256,
        )


def test_legacy_bytes_remain_v1_and_never_become_phase_data(phase_inputs):
    args = phase_inputs
    plan = args["plan"].to_dict()["binding"]
    legacy = m.usb_identity_operation(
        cell_id=plan["cell_id"],
        session_id=plan["session_id"],
        selection=args["selection"],
        runtime=args["runtime"],
        policy=args["policy"],
    )
    # Exact historical field roster and encoding, not a current-schema upgrade.
    expected = m.canonical(
        dict(
            schema="rocell.physical_usb_identity_operation.v1",
            cell_id=plan["cell_id"],
            session_id=plan["session_id"],
            source_sha256=plan["source_sha256"],
            workspace=args["runtime"].to_dict()["workspace"],
            policy_sha256=args["policy"].sha256,
            selection=args["selection"].identity_document,
            runtime=args["runtime"].to_dict(),
            physical_authority=False,
        )
    )
    assert legacy.payload == m.UsbIdentityOperation(expected).payload == expected
    with pytest.raises(ValueError, match="PHASE_BOUND"):
        m.verify_phase_operation_context(
            legacy, args["plan"], "BASELINE", args["operation_id"], None
        )
    changed = m.usb_identity_phase_operation(**args).to_dict()
    changed["schema"] = m.OPERATION_SCHEMA
    with pytest.raises(ValueError):
        m.UsbIdentityOperation(m.canonical(changed))


@pytest.mark.parametrize(
    "change", ["extra", "missing-plan", "missing-binding", "authority", "schema"]
)
def test_v2_outer_envelope_remains_closed(phase_inputs, change):
    d = m.usb_identity_phase_operation(**phase_inputs).to_dict()
    if change == "extra":
        d["review"] = {}
    elif change.startswith("missing"):
        del d["qualification_plan" if change == "missing-plan" else "phase_binding"]
    elif change == "authority":
        d["physical_authority"] = 0
    else:
        d["schema"] = "rocell.physical_usb_identity_operation.v3"
    with pytest.raises(ValueError):
        m.UsbIdentityOperation(m.canonical(d))
