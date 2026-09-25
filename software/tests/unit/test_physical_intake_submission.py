"""Pure codecs over actual requirements and explicitly modeled observations.

The reference helper constructs typed test references, not retained M1 storage.
No file observation, native/device invocation or qualification is modeled as real.
"""

from dataclasses import replace
import ctypes
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from rocell.application import physical_intake_submission as module
from rocell.application.physical_intake_notebook import PhysicalIntakeNotebook
from rocell.application.physical_onboarding import PhysicalOnboardingStage
from test_physical_configuration_epochs import epoch_fixture, reference


def canonical(value):
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("ascii")


def intake_fixture(*, observed=False):
    """Actual codecs, explicit modeled draft/reference; no acquired hardware."""
    prerequisites, snapshot, _ = epoch_fixture()
    notebook = PhysicalIntakeNotebook.start(
        prerequisites, launch_session_id="wizard-current-intake"
    )
    for index, row in enumerate(notebook.to_dict()["rows"], 1):
        notebook = notebook.record(
            record_id=row["record_id"],
            observation_status="OBSERVED" if observed else "UNKNOWN",
            observed_value=(
                ("1" if row["unit"] in {"mm", "g"} else "MODELED TEST OBSERVATION")
                if observed
                else "Hardware not received; explicit test-only unknown"
            ),
            method="Modeled test method; no hardware inspected",
            evidence_note="Modeled codec evidence; no received-unit qualification",
            operator_id="Operator_A",
            recorded_at_ns=index,
        )
    payload = b"MODELED TEST ATTACHMENT; NOT HARDWARE EVIDENCE\n"
    ref = reference(
        PhysicalOnboardingStage.WORKSPACE_SOURCES, payload, salt="intake-original"
    )
    attachment = module.IntakeAttachment(ref, "modeled-observation.txt", "text/plain")
    links = (
        tuple(
            module.IntakeRowAttachment(row["record_id"], ref.evidence_id)
            for row in notebook.to_dict()["rows"]
        )
        if observed
        else ()
    )
    kwargs = dict(
        cell_id=snapshot.header.cell_id,
        header_sha256=snapshot.header.header_sha256,
        collection_id="intake-" + "1" * 32,
        operator_id="Operator_A",
        submitted_at_ns=100,
        attachments=(attachment,) if observed else (),
        row_attachments=links,
        evidence_inventory=tuple(
            sorted((*snapshot.evidence, ref), key=lambda v: v.evidence_id)
        ),
    )
    submission = module.build_physical_intake_submission(
        prerequisites, notebook, **kwargs
    )
    assessment = module.assess_physical_intake_submission(submission)
    review = module.review_physical_intake_submission(
        submission,
        assessment,
        reviewer_id="Reviewer_B",
        review_launch_id="wizard-review",
        reviewed_at_ns=101,
        decision="ACKNOWLEDGE_FOR_LATER_STAGE_REVIEW",
    )
    return SimpleNamespace(
        prerequisites=prerequisites,
        snapshot=snapshot,
        notebook=notebook,
        payload=payload,
        reference=ref,
        attachment=attachment,
        kwargs=kwargs,
        submission=submission,
        assessment=assessment,
        review=review,
    )


@pytest.fixture(scope="module")
def unknown():
    return intake_fixture()


@pytest.fixture(scope="module")
def observed():
    return intake_fixture(observed=True)


def verify(fixture, payload=None, **changes):
    bound = fixture.submission.to_dict()["binding"]
    kwargs = dict(
        prerequisites=fixture.prerequisites,
        evidence_inventory=fixture.kwargs["evidence_inventory"],
        expected_source_sha256=bound["source_sha256"],
        expected_session_id=bound["session_id"],
        expected_cell_id=bound["cell_id"],
        expected_origin_launch_id=bound["origin_launch_id"],
        expected_header_sha256=bound["header_sha256"],
        expected_submission_sha256=fixture.submission.sha256,
    )
    kwargs.update(changes)
    return module.verify_physical_intake_submission(
        fixture.submission.payload if payload is None else payload, **kwargs
    )


def test_all_unknown_is_explicit_structural_review_not_physical_readiness(unknown):
    assert verify(unknown).payload == unknown.submission.payload
    assert unknown.submission.to_dict()["coverage"] == dict(
        total=16,
        observed=0,
        unknown=16,
        attached_rows=0,
        attachment_count=0,
        attachment_bytes=0,
    )
    assert (
        unknown.assessment.to_dict()["observation_completeness"]
        == "UNKNOWN_ROWS_REMAIN"
    )
    assert unknown.assessment.to_dict()["physical_readiness"] is False
    assert len(unknown.assessment.to_dict()["unknown_record_ids"]) == 16
    assert all(unknown.submission.to_dict()[key] is False for key in module._FLAGS)
    assert unknown.review.to_dict()["status"] == "ACKNOWLEDGED_FOR_LATER_STAGE_REVIEW"
    assert unknown.review.to_dict()["authenticated_independent_people"] is False


def test_one_file_can_support_all_rows_without_duplicate_retention(observed):
    data = verify(observed).to_dict()
    assert len(data["attachments"]) == 1 and len(data["row_attachments"]) == 16
    assert data["coverage"]["attachment_bytes"] == len(observed.payload)
    assert (
        observed.assessment.to_dict()["observation_completeness"] == "ALL_ROWS_OBSERVED"
    )
    assert data["attachments"][0]["reference"] == observed.reference.to_dict()
    assert observed.payload not in observed.submission.payload
    summary = observed.submission.safe_summary()
    flatness = next(row for row in summary["rows"] if row["record_id"] == "INT-005")
    assert flatness["acceptance_status"] == "DEFERRED_LIMIT"
    assert flatness["acceptance_owner_stage"] == "noncontact_acceptance"
    assert "submitted_at_ns" not in summary and "notebook" not in summary
    assert "reviewed_at_ns" not in observed.review.safe_summary()


@pytest.mark.parametrize(
    "changed",
    [
        dict(attachments=(), row_attachments=()),
        dict(row_attachments=()),
        dict(attachments="x"),
        dict(row_attachments={}),
        dict(evidence_inventory=()),
        dict(operator_id="unsafe/name"),
        dict(collection_id="arbitrary"),
        dict(submitted_at_ns=True),
        dict(submitted_at_ns=1),
    ],
)
def test_closed_builder_refuses_missing_or_untrusted_context(observed, changed):
    with pytest.raises(ValueError):
        module.build_physical_intake_submission(
            observed.prerequisites, observed.notebook, **{**observed.kwargs, **changed}
        )


def test_incomplete_notebook_cannot_be_submitted(unknown):
    blank = PhysicalIntakeNotebook.start(
        unknown.prerequisites, launch_session_id="wizard-current-intake"
    )
    with pytest.raises(ValueError):
        module.build_physical_intake_submission(
            unknown.prerequisites, blank, **unknown.kwargs
        )


@pytest.mark.parametrize(
    "name,media",
    [
        ("../photo.png", "image/png"),
        ("C:\\photo.png", "image/png"),
        ("hidden:stream.txt", "text/plain"),
        ("CON.txt", "text/plain"),
        ("COM1.json", "application/json"),
        ("foo.exe", "application/octet-stream"),
        ("foo.zip", "application/zip"),
        ("foo.png", "text/plain"),
        (".photo.png", "image/png"),
        ("x" * 129 + ".txt", "text/plain"),
        ("line\n.txt", "text/plain"),
    ],
)
def test_attachment_name_and_media_are_closed(observed, name, media):
    with pytest.raises(ValueError):
        module.IntakeAttachment(observed.reference, name, media)


@pytest.mark.parametrize(
    "name,media",
    [
        ("a.txt", "text/plain"),
        ("a.json", "application/json"),
        ("a.png", "image/png"),
        ("a.jpg", "image/jpeg"),
        ("a.jpeg", "image/jpeg"),
        ("a.pdf", "application/pdf"),
        ("Camera Label.PNG", "image/png"),
    ],
)
def test_supported_metadata_does_not_claim_content_validation(observed, name, media):
    assert module.IntakeAttachment(observed.reference, name, media).media_type == media


@pytest.mark.parametrize(
    "field",
    [
        "expected_source_sha256",
        "expected_session_id",
        "expected_cell_id",
        "expected_origin_launch_id",
        "expected_header_sha256",
        "expected_submission_sha256",
    ],
)
def test_independent_binding_mismatch_denied(unknown, field):
    value = "f" * 64 if field.endswith("sha256") else "wrong-context"
    with pytest.raises(ValueError):
        verify(unknown, **{field: value})


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(physical_authority=True),
        lambda d: d.update(extra="forged"),
        lambda d: d.update(sequence=True),
        lambda d: d["coverage"].update(observed=0),
        lambda d: d["attachments"].append(d["attachments"][0]),
        lambda d: d["row_attachments"].reverse(),
        lambda d: d["row_attachments"][0].update(evidence_id="evidence-" + "f" * 64),
        lambda d: d["notebook"]["rows"][0]["observation"].update(observed_value="1e9"),
        lambda d: d["notebook"]["rows"][4]["acceptance"].update(status="PASS"),
    ],
)
def test_rehashed_malformed_submission_denied(observed, mutate):
    data = observed.submission.to_dict()
    mutate(data)
    data["binding"]["notebook_sha256"] = hashlib.sha256(
        canonical(data["notebook"])
    ).hexdigest()
    raw = canonical(data)
    with pytest.raises(ValueError):
        verify(
            observed, raw, expected_submission_sha256=hashlib.sha256(raw).hexdigest()
        )


def test_context_verifier_uses_original_notebook_question_codec(observed):
    data = observed.submission.to_dict()
    data["notebook"]["rows"][0]["measurement"] = "changed original question"
    data["binding"]["notebook_sha256"] = hashlib.sha256(
        canonical(data["notebook"])
    ).hexdigest()
    raw = canonical(data)
    # Bytes-only parsing cannot authenticate an absent external prerequisite.
    module.PhysicalIntakeSubmission(raw)
    with pytest.raises(ValueError):
        verify(
            observed, raw, expected_submission_sha256=hashlib.sha256(raw).hexdigest()
        )


@pytest.mark.parametrize(
    "change",
    [
        dict(reviewer_id="operator_a"),
        dict(reviewer_id="Reviewer Name"),
        dict(reviewed_at_ns=99),
        dict(decision="PASS"),
        dict(decision=True),
    ],
)
def test_review_cannot_self_approve_or_upgrade_subject(unknown, change):
    values = dict(
        reviewer_id="Reviewer_B",
        review_launch_id="wizard-review",
        reviewed_at_ns=101,
        decision="ACKNOWLEDGE_FOR_LATER_STAGE_REVIEW",
    )
    with pytest.raises(ValueError):
        module.review_physical_intake_submission(
            unknown.submission, unknown.assessment, **{**values, **change}
        )


def test_rejection_and_exact_subject_verification(unknown, observed):
    rejected = module.review_physical_intake_submission(
        unknown.submission,
        unknown.assessment,
        reviewer_id="Reviewer_B",
        review_launch_id="wizard-review",
        reviewed_at_ns=102,
        decision="REJECT",
    )
    assert rejected.to_dict()["status"] == "REJECTED"
    assert (
        module.verify_physical_intake_review(
            rejected.payload,
            submission=unknown.submission,
            assessment=unknown.assessment,
            expected_review_sha256=rejected.sha256,
        ).payload
        == rejected.payload
    )
    with pytest.raises(ValueError):
        module.verify_physical_intake_review(
            rejected.payload,
            submission=observed.submission,
            assessment=observed.assessment,
            expected_review_sha256=rejected.sha256,
        )
    with pytest.raises(ValueError):
        module.verify_physical_intake_assessment(
            unknown.assessment.payload,
            submission=observed.submission,
            expected_assessment_sha256=unknown.assessment.sha256,
        )


def test_append_only_successor_preserves_context_and_exact_predecessor(unknown):
    previous = unknown.submission
    for index in range(2, 9):
        next_value = module.build_physical_intake_submission(
            unknown.prerequisites,
            unknown.notebook,
            **{
                **unknown.kwargs,
                "collection_id": "intake-" + f"{index:032x}",
                "submitted_at_ns": 100 + index,
                "predecessor": previous,
            },
        )
        assert next_value.to_dict()["sequence"] == index
        assert next_value.to_dict()["predecessor_submission_sha256"] == previous.sha256
        assert (
            verify(
                unknown,
                next_value.payload,
                expected_submission_sha256=next_value.sha256,
                predecessor=previous,
            ).payload
            == next_value.payload
        )
        with pytest.raises(ValueError):
            verify(
                unknown,
                next_value.payload,
                expected_submission_sha256=next_value.sha256,
            )
        previous = next_value
    with pytest.raises(ValueError):
        module.build_physical_intake_submission(
            unknown.prerequisites,
            unknown.notebook,
            **{
                **unknown.kwargs,
                "collection_id": "intake-" + "f" * 32,
                "submitted_at_ns": 200,
                "predecessor": previous,
            },
        )


def test_defensive_views_and_canonical_byte_limits(unknown):
    for artifact, exact in [
        (unknown.submission, module.PhysicalIntakeSubmission),
        (unknown.assessment, module.PhysicalIntakeAssessment),
        (unknown.review, module.PhysicalIntakeReview),
    ]:
        original = artifact.payload
        artifact.to_dict().clear()
        artifact.safe_summary().clear()
        assert (
            artifact.payload == original
            and artifact.sha256 == hashlib.sha256(original).hexdigest()
        )
        for bad in [
            bytearray(original),
            original + b"\n",
            b'{"schema":1,"schema":2}',
            b"x" * (module.MAX_RECORD_BYTES + 1),
        ]:
            with pytest.raises(ValueError):
                exact(bad)


def test_core_functions_are_pure_with_existing_inputs(observed, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("pure intake codec attempted file/device I/O")

    with monkeypatch.context() as patcher:
        patcher.setattr(Path, "open", forbidden)
        patcher.setattr(Path, "stat", forbidden)
        patcher.setattr(ctypes, "WinDLL", forbidden, raising=False)
        value = verify(observed)
        assessment = module.assess_physical_intake_submission(value)
        assert (
            module.verify_physical_intake_assessment(
                assessment.payload,
                submission=value,
                expected_assessment_sha256=assessment.sha256,
            ).sha256
            == assessment.sha256
        )
        assert value.safe_summary() == observed.submission.safe_summary()


@pytest.mark.parametrize(
    "changed",
    [
        {"header_sha256": "e" * 64},
        {"cell_id": "wizard-physical-camera-" + "e" * 16},
        {"submitted_at_ns": 100},
        {"collection_id": "intake-" + "1" * 32},
    ],
)
def test_successor_cannot_rebind_origin_or_reuse_collection(unknown, changed):
    values = {
        **unknown.kwargs,
        "collection_id": "intake-" + "2" * 32,
        "submitted_at_ns": 102,
        "predecessor": unknown.submission,
        **changed,
    }
    with pytest.raises(ValueError):
        module.build_physical_intake_submission(
            unknown.prerequisites, unknown.notebook, **values
        )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(reviewer_id="operator_a"),
        lambda d: d.update(reviewed_at_ns=99),
        lambda d: d.update(assessment_sha256="a" * 64),
        lambda d: d.update(authenticated_independent_people=True),
    ],
)
def test_rehashed_review_cannot_change_exact_subject_or_separation(unknown, mutate):
    value = unknown.review.to_dict()
    mutate(value)
    raw = canonical(value)
    with pytest.raises(ValueError):
        module.verify_physical_intake_review(
            raw,
            submission=unknown.submission,
            assessment=unknown.assessment,
            expected_review_sha256=hashlib.sha256(raw).hexdigest(),
        )
