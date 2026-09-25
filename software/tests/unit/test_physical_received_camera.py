"""Pure completeness fixtures; every observation/reference is explicitly modeled."""

from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from threading import Event
import time

import pytest

from rocell.application import physical_received_camera as module
from rocell.application import physical_camera_prerequisites as prerequisites_module
from rocell.application.physical_intake_notebook import PhysicalIntakeNotebook
from rocell.application.physical_onboarding import (
    EvidenceReference,
    PhysicalOnboardingStage,
)
from rocell.application.physical_onboarding_receipts import (
    BoundEvidence,
    CameraReceiptInspection,
    InspectionCondition,
    ReceiptBinding,
)
from test_physical_camera_prerequisites import workspace, SOURCE, SESSION

ORIGIN = "wizard-" + "1" * 32
LAUNCH = "wizard-" + "2" * 32
CELL = "wizard-physical-camera-" + "3" * 16
HEADER = "4" * 64


@pytest.fixture
def prerequisites(workspace):
    return prerequisites_module.collect_physical_camera_prerequisites(
        workspace,
        source_sha256=SOURCE,
        session_id=SESSION,
        launch_session_id=ORIGIN,
        cancellation=Event(),
        deadline_ns=time.monotonic_ns() + 30_000_000_000,
    )


def original_reference(notebook, *, stage=PhysicalOnboardingStage.CAMERA_RECEIPT):
    return EvidenceReference(
        evidence_id="evidence-" + "a" * 64,
        stage=stage,
        package_sha256="a" * 64,
        manifest_sha256="b" * 64,
        payload_sha256=notebook.sha256,
        payload_bytes=len(notebook.payload),
    )


def fixture(prerequisites, *, observed=True, low="17.5", high="18.5", values=None):
    """Original question producer plus modeled observations and package hashes."""
    notebook = PhysicalIntakeNotebook.start(prerequisites, launch_session_id=LAUNCH)
    defaults = {"INT-003": low, "INT-004": high, "INT-005": "0"}
    defaults.update(values or {})
    if observed:
        for index, row in enumerate(notebook.to_dict()["rows"]):
            number = (
                "1"
                if row["unit"] in {"mm", "g"}
                else "Modeled narrative; not received hardware."
            )
            notebook = notebook.record(
                record_id=row["record_id"],
                observation_status="OBSERVED",
                observed_value=defaults.get(row["record_id"], number),
                method="Explicit modeled test observation, not measurement.",
                evidence_note="Modeled content-addressed references; no original bytes observed.",
                operator_id="modeled-operator",
                recorded_at_ns=index + 1,
            )
    reference = original_reference(notebook)
    evidence = [BoundEvidence.from_reference(reference)]
    for index, char in enumerate(("c", "d")):
        evidence.append(
            BoundEvidence(
                evidence_id="evidence-" + char * 64,
                stage=PhysicalOnboardingStage.CAMERA_RECEIPT,
                package_sha256=char * 64,
                manifest_sha256="e" * 64,
                payload_sha256="f" * 64,
                payload_bytes=100 + index,
            )
        )
    inspection = CameraReceiptInspection(
        binding=ReceiptBinding(
            source_binding_sha256=module.physical_camera_source_binding(SOURCE),
            session_header_sha256=HEADER,
            session_id=SESSION,
            cell_id=CELL,
            stage=PhysicalOnboardingStage.CAMERA_RECEIPT,
            evidence=tuple(evidence),
        ),
        operator_id="modeled-operator",
        observed_at_ns=20,
        observed_manufacturer="Arducam",
        observed_product_id="B0477",
        observed_camera_serial="MODELED-NOT-HARDWARE-001",
        observed_lens_focal_length_mm=16,
        body_condition=InspectionCondition.ACCEPTABLE,
        lens_condition=InspectionCondition.ACCEPTABLE,
        connector_condition=InspectionCondition.ACCEPTABLE,
        identity_label_legible=True,
        purchase_record_matches=True,
        package_contents_complete=True,
        inspection_uncertain=False,
        purchase_record_evidence_id=evidence[1].evidence_id,
        inspection_image_evidence_ids=(evidence[2].evidence_id,),
    )
    binding = dict(
        receipt_id="receivedcamera-" + "5" * 32,
        source_sha256=SOURCE,
        cell_id=CELL,
        session_id=SESSION,
        header_sha256=HEADER,
        origin_launch_id=ORIGIN,
        collection_launch_id=LAUNCH,
        operator_id="modeled-operator",
        prerequisites_sha256=prerequisites.evidence_sha256,
        static_contract={
            "receipt": "6" * 64,
            "assessment": "7" * 64,
            "review": "8" * 64,
        },
        camera_request_event_sha256="9" * 64,
    )
    return notebook, reference, inspection, binding


def assess(prerequisites, values):
    notebook, reference, inspection, binding = values
    return module.assess_received_camera_receipt(
        prerequisites,
        notebook,
        binding=binding,
        inspection=inspection,
        notebook_reference=reference,
    )


def verify(prerequisites, result, values, **changes):
    notebook, reference, inspection, binding = values
    kwargs = dict(
        prerequisites=prerequisites,
        expected_binding=binding,
        expected_notebook_sha256=notebook.sha256,
        expected_inspection_sha256=(
            None if inspection is None else inspection.receipt_sha256
        ),
        expected_notebook_reference=reference,
        expected_assessment_sha256=result.sha256,
    )
    kwargs.update(changes)
    return module.verify_received_camera_assessment(result.payload, **kwargs)


def test_complete_record_is_not_stage_pass_or_hardware_acceptance(prerequisites):
    values = fixture(prerequisites)
    result = assess(prerequisites, values)
    assert verify(prerequisites, result, values) == result
    data = result.to_dict()
    assert data["status"] == "RECEIPT_COMPLETE" and data["missing_requirements"] == []
    assert data["flatness_acceptance"] == "DEFERRED_LIMIT"
    assert data["inspection_assessment"]["diagnostic_ready"] is True
    assert all(data[key] is False for key in module.FLAGS)
    assert data["notebook"] == values[0].to_dict()
    assert data["inspection"] == values[2].to_dict()
    assert len(result.payload) < module.MAX_ASSESSMENT_BYTES
    assert len(module._canonical(result.safe_summary())) < module.MAX_SUMMARY_BYTES


def test_unknown_unrecorded_default_cannot_be_complete(prerequisites):
    notebook, _, _, binding = fixture(prerequisites, observed=False)
    result = module.assess_received_camera_receipt(
        prerequisites, notebook, binding=binding
    )
    data = result.to_dict()
    assert data["status"] == "RECEIPT_INCOMPLETE"
    assert data["coverage"]["unrecorded"] == 16
    assert data["thickness"]["status"] == "UNOBSERVED"
    assert "NOTEBOOK_CAMERA_STAGE_ORIGINAL_NOT_BOUND" in data["missing_requirements"]
    assert "STRUCTURED_CAMERA_INSPECTION_REQUIRED" in data["missing_requirements"]


@pytest.mark.parametrize(
    "low,high,complete",
    [
        ("17.5", "18.5", True),
        ("17.500000", "18.500000", True),
        ("18", "18", True),
        ("17.499999999999999999999", "18.5", False),
        ("17.5", "18.500000000000000000001", False),
        ("18.4", "18.3", False),
    ],
)
def test_exact_decimal_thickness_bounds_and_order(prerequisites, low, high, complete):
    result = assess(prerequisites, fixture(prerequisites, low=low, high=high))
    assert (result.to_dict()["status"] == "RECEIPT_COMPLETE") is complete


@pytest.mark.parametrize("record_id", module.RECORD_IDS)
def test_every_original_question_observation_is_required(prerequisites, record_id):
    notebook, _, inspection, binding = fixture(prerequisites)
    notebook = notebook.record(
        record_id=record_id,
        observation_status="UNKNOWN",
        observed_value="Not measured",
        method="Modeled unknown",
        evidence_note="No received hardware",
        operator_id="modeled-operator",
        recorded_at_ns=30,
    )
    ref = original_reference(notebook)
    inspection = replace(
        inspection,
        binding=replace(
            inspection.binding,
            evidence=(
                BoundEvidence.from_reference(ref),
                *inspection.binding.evidence[1:],
            ),
        ),
    )
    result = assess(prerequisites, (notebook, ref, inspection, binding))
    assert result.to_dict()["status"] == "RECEIPT_INCOMPLETE"
    assert (
        record_id + "_OBSERVATION_REQUIRED" in result.to_dict()["missing_requirements"]
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("observed_manufacturer", "Other"),
        ("observed_product_id", "B0000"),
        ("observed_lens_focal_length_mm", 8),
        ("observed_lens_focal_length_mm", None),
        ("body_condition", InspectionCondition.DAMAGED),
        ("lens_condition", InspectionCondition.UNCERTAIN),
        ("identity_label_legible", False),
        ("purchase_record_matches", False),
        ("package_contents_complete", False),
        ("inspection_uncertain", True),
    ],
)
def test_existing_structured_camera_checks_are_not_bypassed(
    prerequisites, field, value
):
    notebook, ref, inspection, binding = fixture(prerequisites)
    inspection = replace(inspection, **{field: value})
    result = assess(prerequisites, (notebook, ref, inspection, binding))
    assert result.to_dict()["status"] == "RECEIPT_INCOMPLETE"


def test_no_nominal_dimension_mass_or_flatness_threshold_is_invented(prerequisites):
    values = {
        key: "999999999.999"
        for key in (
            "INT-001",
            "INT-002",
            "INT-005",
            "INT-007",
            "INT-008",
            "INT-009",
            "INT-019",
            "INT-020",
            "INT-021",
            "INT-022",
        )
    }
    result = assess(prerequisites, fixture(prerequisites, values=values))
    assert result.to_dict()["status"] == "RECEIPT_COMPLETE"
    assert result.to_dict()["flatness_acceptance"] == "DEFERRED_LIMIT"
    assert all(result.to_dict()[key] is False for key in module.FLAGS)


@pytest.mark.parametrize("value", ["NaN", "inf", "-1", "1e3", "17.5mm", "0", "1,5"])
def test_original_notebook_numeric_validation_remains_strict(prerequisites, value):
    with pytest.raises(ValueError):
        fixture(prerequisites, low=value)


def test_source_stage_reference_never_relabels_stage3_original(prerequisites):
    notebook, ref, inspection, binding = fixture(prerequisites)
    with pytest.raises(ValueError, match="NOTEBOOK_ORIGINAL_STAGE_MISMATCH"):
        assess(
            prerequisites,
            (
                notebook,
                replace(ref, stage=PhysicalOnboardingStage.WORKSPACE_SOURCES),
                inspection,
                binding,
            ),
        )


def test_inspection_must_bind_the_same_camera_stage_notebook(prerequisites):
    notebook, ref, inspection, binding = fixture(prerequisites)
    inspection = replace(
        inspection,
        binding=replace(inspection.binding, evidence=inspection.binding.evidence[1:]),
    )
    result = assess(prerequisites, (notebook, ref, inspection, binding))
    assert result.to_dict()["status"] == "RECEIPT_INCOMPLETE"
    assert (
        "INSPECTION_NOTEBOOK_REFERENCE_NOT_BOUND"
        in result.to_dict()["missing_requirements"]
    )


@pytest.mark.parametrize(
    "field", ["payload_sha256", "manifest_sha256", "package_sha256"]
)
def test_expected_original_reference_is_independent(prerequisites, field):
    values = fixture(prerequisites)
    result = assess(prerequisites, values)
    with pytest.raises(ValueError):
        verify(
            prerequisites,
            result,
            values,
            expected_notebook_reference=replace(values[1], **{field: "1" * 64}),
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_binding_sha256", "b" * 64),
        ("session_header_sha256", "b" * 64),
        ("session_id", "other-session"),
        ("cell_id", "other-cell"),
    ],
)
def test_inspection_cannot_cross_original_context(prerequisites, field, value):
    notebook, ref, inspection, binding = fixture(prerequisites)
    inspection = replace(
        inspection, binding=replace(inspection.binding, **{field: value})
    )
    with pytest.raises(ValueError, match="CAMERA_INSPECTION_ORIGINAL_CONTEXT_MISMATCH"):
        assess(prerequisites, (notebook, ref, inspection, binding))


def test_pure_reassessment_no_source_or_file_access(prerequisites, monkeypatch):
    values = fixture(prerequisites)
    result = assess(prerequisites, values)

    def forbidden(*args, **kwargs):
        pytest.fail("Pure assessment accessed external state")

    for name in ("open", "read_bytes", "resolve", "stat"):
        monkeypatch.setattr(Path, name, forbidden)
    monkeypatch.setattr(prerequisites_module, "source_fingerprint", forbidden)
    assert verify(prerequisites, result, values).safe_summary() == result.safe_summary()
    assert assess(prerequisites, values).payload == result.payload


def test_rehashed_calculation_and_raw_original_tampering_are_rejected(prerequisites):
    values = fixture(prerequisites)
    result = assess(prerequisites, values)
    with pytest.raises(FrozenInstanceError):
        result.payload = b"{}"
    for mutate in (
        lambda data: data.update(status="PASS"),
        lambda data: data.update(attachment_bytes_verified=True),
        lambda data: data["thickness"].update(allowed_minimum_mm="17.0"),
        lambda data: data["notebook"].update(revision=True),
    ):
        data = result.to_dict()
        mutate(data)
        with pytest.raises(ValueError):
            module.ReceivedCameraAssessment(module._canonical(data), prerequisites)
    with pytest.raises(ValueError):
        module.ReceivedCameraAssessment(result.payload + b"\n", prerequisites)
    with pytest.raises(ValueError):
        module.ReceivedCameraAssessment(
            b"x" * (module.MAX_ASSESSMENT_BYTES + 1), prerequisites
        )
