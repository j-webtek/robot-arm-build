"""Actual pure codecs with explicitly modeled observations/original references."""

from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from rocell.application import physical_received_camera_submission as module
from rocell.application.physical_intake_notebook import PhysicalIntakeNotebook
from rocell.application.physical_onboarding import (
    EvidenceReference,
    PhysicalOnboardingStage,
)
from rocell.application.physical_onboarding_receipts import BoundEvidence
from test_physical_received_camera import fixture, prerequisites, workspace


def submission_fixture(
    prerequisites,
    *,
    observed=True,
    cycle=1,
    predecessor=None,
    revise=False,
    changes=None,
    decision="ACKNOWLEDGE_EXACT",
):
    """No real M1 claim: actual foundation builder, modeled media/inventory."""
    original, _, inspection, binding = fixture(prerequisites, observed=observed)
    launch = f"wizard-{200 + cycle:032x}"
    book = PhysicalIntakeNotebook.start(prerequisites, launch_session_id=launch)
    if revise:
        original = PhysicalIntakeNotebook.from_payload(
            module._canonical(predecessor[0].to_dict()["notebook"]),
            prerequisites=prerequisites,
            expected_sha256=predecessor[0].to_dict()["notebook_sha256"],
        )
    for index, row in enumerate(original.to_dict()["rows"]):
        if row["observation"] is not None:
            value = dict(row["observation"])
            if not revise:
                value["recorded_at_ns"] = cycle * 100 + index
            if changes and row["record_id"] in changes:
                value.update(changes[row["record_id"]])
            book = book.record(
                record_id=row["record_id"],
                observation_status=value.pop("status"),
                **value,
            )
    refs = []
    for index in range(3):
        package = f"{cycle * 1000 + index:064x}"
        refs.append(
            EvidenceReference(
                evidence_id="evidence-" + package,
                stage=PhysicalOnboardingStage.CAMERA_RECEIPT,
                package_sha256=package,
                manifest_sha256="b" * 64,
                payload_sha256=book.sha256 if index == 0 else f"{index + 10:064x}",
                payload_bytes=len(book.payload) if index == 0 else 120 + index,
            )
        )
    bound = tuple(BoundEvidence.from_reference(ref) for ref in refs)
    inspection = replace(
        inspection,
        binding=replace(inspection.binding, evidence=bound),
        purchase_record_evidence_id=refs[1].evidence_id,
        inspection_image_evidence_ids=(refs[2].evidence_id,),
        observed_at_ns=cycle * 100 + 20,
    )
    if not observed:
        inspection = None
    attachments = (
        module.ReceivedCameraAttachment(refs[1], "modeled-purchase.txt", "text/plain"),
        module.ReceivedCameraAttachment(refs[2], "modeled-inspection.png", "image/png"),
    )
    links = tuple(
        module.ReceivedCameraRowLink(
            row["record_id"],
            (
                refs[1].evidence_id
                if row["observation"] is not None
                and row["observation"]["status"] == "OBSERVED"
                else None
            ),
        )
        for row in book.to_dict()["rows"]
    )
    binding.update(
        receipt_id=f"receivedcamera-{50 + cycle:032x}", collection_launch_id=launch
    )
    kwargs = dict(
        binding=binding,
        notebook_reference=refs[0],
        inspection=inspection,
        attachments=attachments,
        row_links=links,
        submitted_at_ns=cycle * 1000,
        evidence_inventory=tuple(refs),
        predecessor=predecessor,
        draft_origin_notebook_sha256=None if not revise else original.sha256,
    )
    submission = module.build_received_camera_submission(prerequisites, book, **kwargs)
    assessment = module.assess_received_camera_submission(submission)
    review = module.review_received_camera_submission(
        submission,
        assessment,
        decision=decision,
        reviewer_id="modeled-reviewer",
        review_launch_id=launch,
        reviewed_at_ns=cycle * 1000 + 1,
    )
    return dict(
        prerequisites=prerequisites,
        notebook=book,
        kwargs=kwargs,
        submission=submission,
        assessment=assessment,
        review=review,
    )


def trio(value):
    return tuple(value[key] for key in ("submission", "assessment", "review"))


def rebuild(value, **changes):
    kwargs = {**value["kwargs"], **changes}
    return module.build_received_camera_submission(
        value["prerequisites"], value["notebook"], **kwargs
    )


def verify(value, **changes):
    kwargs = dict(
        prerequisites=value["prerequisites"],
        expected_binding=value["kwargs"]["binding"],
        evidence_inventory=value["kwargs"]["evidence_inventory"],
        expected_submission_sha256=value["submission"].sha256,
        predecessor=value["kwargs"]["predecessor"],
    )
    return module.verify_received_camera_submission(
        value["submission"].payload, **{**kwargs, **changes}
    )


def test_strict_originals_foundation_and_exact_review(prerequisites):
    value = submission_fixture(prerequisites)
    submission, assessment, review = trio(value)
    assert verify(value) == submission
    assert assessment.to_dict()["verdict"] == review.to_dict()["verdict"] == "PASS"
    assert assessment.to_dict()["foundation"]["status"] == "RECEIPT_COMPLETE"
    assert assessment.to_dict()["foundation"]["canonical_stage_pass"] is False
    assert (
        module.verify_received_camera_submission_assessment(
            assessment,
            submission=submission,
            expected_assessment_sha256=assessment.sha256,
        )
        == assessment
    )
    assert (
        module.verify_received_camera_submission_review(
            review,
            submission=submission,
            assessment=assessment,
            expected_review_sha256=review.sha256,
        )
        == review
    )
    for record in trio(value):
        assert all(record.to_dict()[key] is False for key in module.FLAGS)
        assert len(module._canonical(record.safe_summary())) <= module.MAX_SUMMARY_BYTES
    assert submission.to_dict()["notebook"] == value["notebook"].to_dict()
    assert submission.to_dict()["inspection"] == value["kwargs"]["inspection"].to_dict()


def test_unknown_submission_is_retained_blocked_not_a_fake_inspection(prerequisites):
    value = submission_fixture(prerequisites, observed=False)
    assert value["submission"].to_dict()["inspection"] is None
    assert (
        value["assessment"].to_dict()["verdict"]
        == value["review"].to_dict()["verdict"]
        == "BLOCKED"
    )
    assert value["assessment"].to_dict()["foundation"]["coverage"]["unrecorded"] == 16
    assert verify(value) == value["submission"]


def test_rejection_cannot_upgrade_or_rewrite_assessment(prerequisites):
    value = submission_fixture(prerequisites, decision="REJECT")
    assert value["assessment"].to_dict()["verdict"] == "PASS"
    assert value["review"].to_dict()["verdict"] == "BLOCKED"
    second = submission_fixture(prerequisites, cycle=2, predecessor=trio(value))
    assert second["submission"].to_dict()["sequence"] == 2
    with pytest.raises(ValueError, match="PREDECESSOR_NOT_BLOCKED"):
        submission_fixture(prerequisites, cycle=3, predecessor=trio(second))


def test_four_reviewed_blocked_cycles_only(prerequisites):
    previous = None
    for cycle in range(1, 5):
        value = submission_fixture(
            prerequisites, cycle=cycle, predecessor=previous, decision="REJECT"
        )
        assert verify(value) == value["submission"]
        previous = trio(value)
    with pytest.raises(ValueError):
        submission_fixture(prerequisites, cycle=5, predecessor=previous)


def test_explicit_revision_retains_unchanged_observation_provenance(prerequisites):
    first = submission_fixture(prerequisites, decision="REJECT")
    second = submission_fixture(
        prerequisites,
        cycle=2,
        predecessor=trio(first),
        revise=True,
        changes={"INT-001": {"observed_value": "620", "recorded_at_ns": 230}},
    )
    data = second["submission"].to_dict()
    assert data["draft_origin_notebook_sha256"] == first["notebook"].sha256
    assert data["carried_forward_record_ids"] == list(module.RECORD_IDS[1:])
    for row, old in zip(
        data["notebook"]["rows"][1:], first["notebook"].to_dict()["rows"][1:]
    ):
        assert row["observation"] == old["observation"]
    assert verify(second) == second["submission"]


def test_no_implicit_revision_or_caller_authored_carried_ids(prerequisites):
    first = submission_fixture(prerequisites, decision="REJECT")
    second = submission_fixture(prerequisites, cycle=2, predecessor=trio(first))
    assert second["submission"].to_dict()["draft_origin_notebook_sha256"] is None
    assert second["submission"].to_dict()["carried_forward_record_ids"] == []
    with pytest.raises(ValueError):
        rebuild(first, draft_origin_notebook_sha256=first["notebook"].sha256)
    with pytest.raises(ValueError):
        rebuild(second, draft_origin_notebook_sha256="c" * 64)
    revised = submission_fixture(
        prerequisites, cycle=2, predecessor=trio(first), revise=True
    )
    data = revised["submission"].to_dict()
    data["carried_forward_record_ids"] = []
    changed = module.ReceivedCameraSubmission(module._canonical(data), prerequisites)
    with pytest.raises(ValueError):
        module.verify_received_camera_submission(
            changed,
            prerequisites=prerequisites,
            expected_binding=data["binding"],
            evidence_inventory=revised["kwargs"]["evidence_inventory"],
            expected_submission_sha256=changed.sha256,
            predecessor=trio(first),
        )


@pytest.mark.parametrize(
    "field",
    [
        "source_sha256",
        "header_sha256",
        "cell_id",
        "session_id",
        "prerequisites_sha256",
        "camera_request_event_sha256",
        "receipt_id",
        "operator_id",
    ],
)
def test_external_expected_binding_is_not_learned_from_record(prerequisites, field):
    value = submission_fixture(prerequisites)
    binding = {**value["kwargs"]["binding"], field: "changed"}
    with pytest.raises(ValueError):
        verify(value, expected_binding=binding)


@pytest.mark.parametrize(
    "change",
    [
        "missing-notebook",
        "missing-media",
        "wrong-hash",
        "wrong-stage",
        "unsorted",
        "duplicate",
    ],
)
def test_exact_audited_inventory_is_required(prerequisites, change):
    value = submission_fixture(prerequisites)
    inventory = list(value["kwargs"]["evidence_inventory"])
    if change == "missing-notebook":
        inventory.pop(0)
    elif change == "missing-media":
        inventory.pop(1)
    elif change == "wrong-hash":
        inventory[1] = replace(inventory[1], manifest_sha256="1" * 64)
    elif change == "wrong-stage":
        inventory[1] = replace(
            inventory[1], stage=PhysicalOnboardingStage.WORKSPACE_SOURCES
        )
    elif change == "unsorted":
        inventory.reverse()
    else:
        inventory.append(inventory[-1])
    with pytest.raises(ValueError):
        verify(value, evidence_inventory=tuple(inventory))


@pytest.mark.parametrize(
    "change", ["missing", "duplicate", "unknown", "foreign", "observed-null"]
)
def test_all_sixteen_row_links_are_closed_and_observed_requires_original(
    prerequisites, change
):
    value = submission_fixture(prerequisites)
    links = list(value["kwargs"]["row_links"])
    if change == "missing":
        links.pop()
    elif change == "duplicate":
        links[1] = links[0]
    elif change == "unknown":
        with pytest.raises(ValueError):
            module.ReceivedCameraRowLink("INT-018", links[0].evidence_id)
        return
    else:
        links[0] = replace(
            links[0],
            evidence_id=None if change == "observed-null" else "evidence-" + "f" * 64,
        )
    with pytest.raises(ValueError):
        rebuild(value, row_links=tuple(links))


@pytest.mark.parametrize(
    "name,media",
    [
        ("../camera.png", "image/png"),
        ("camera.exe", "application/octet-stream"),
        ("CON.txt", "text/plain"),
        ("camera.png", "text/plain"),
        ("camera..png", "image/png"),
    ],
)
def test_media_names_and_types_closed(prerequisites, name, media):
    value = submission_fixture(prerequisites)
    with pytest.raises(ValueError):
        module.ReceivedCameraAttachment(
            value["kwargs"]["attachments"][0].reference, name, media
        )


def test_unknown_with_optional_link_is_linked_not_observed(prerequisites):
    value = submission_fixture(prerequisites, observed=False)
    link = module.ReceivedCameraRowLink(
        "INT-001", value["kwargs"]["attachments"][0].reference.evidence_id
    )
    result = rebuild(value, row_links=(link, *value["kwargs"]["row_links"][1:]))
    assert result.safe_summary()["linked_row_count"] == 1
    assert result.safe_summary()["coverage"]["observed"] == 0


def test_per_original_selected_count_and_total_budgets(prerequisites):
    value = submission_fixture(prerequisites, observed=False)
    first = value["kwargs"]["attachments"][0]
    with pytest.raises(ValueError):
        replace(
            first,
            reference=replace(
                first.reference, payload_bytes=module.MAX_ORIGINAL_BYTES + 1
            ),
        )
    attachments = []
    for index in range(17):
        package = f"{3000 + index:064x}"
        reference = replace(
            first.reference,
            evidence_id="evidence-" + package,
            package_sha256=package,
            payload_bytes=module.MAX_ORIGINAL_BYTES,
        )
        attachments.append(
            module.ReceivedCameraAttachment(
                reference, f"modeled-{index}.txt", "text/plain"
            )
        )
    originals = (value["kwargs"]["notebook_reference"],)
    allowed = rebuild(
        value,
        attachments=tuple(attachments[:2]),
        evidence_inventory=originals
        + tuple(item.reference for item in attachments[:2]),
    )
    assert allowed.safe_summary()["attachment_bytes"] == module.MAX_SELECTED_BYTES
    for selected in (attachments[:3], attachments):
        with pytest.raises(ValueError):
            rebuild(
                value,
                attachments=tuple(selected),
                evidence_inventory=originals
                + tuple(item.reference for item in selected),
            )


def test_previous_originals_cannot_be_reused_in_new_cycle(prerequisites):
    first = submission_fixture(prerequisites, observed=False)
    second = submission_fixture(
        prerequisites, observed=False, cycle=2, predecessor=trio(first)
    )
    old_attachment = first["kwargs"]["attachments"][0]
    with pytest.raises(ValueError, match="ORIGINAL_REUSE"):
        rebuild(
            second,
            attachments=(old_attachment,),
            evidence_inventory=tuple(
                sorted(
                    (second["kwargs"]["notebook_reference"], old_attachment.reference),
                    key=lambda ref: ref.evidence_id,
                )
            ),
        )


def test_timing_and_foundation_verdict_are_rederived(prerequisites):
    value = submission_fixture(prerequisites)
    with pytest.raises(ValueError):
        rebuild(value, submitted_at_ns=1)
    with pytest.raises(ValueError):
        module.review_received_camera_submission(
            value["submission"],
            value["assessment"],
            decision="ACKNOWLEDGE_EXACT",
            reviewer_id="independent",
            review_launch_id="wizard-" + "d" * 32,
            reviewed_at_ns=1,
        )
    held = submission_fixture(prerequisites, observed=False)
    data = held["assessment"].to_dict()
    data["verdict"] = "PASS"
    with pytest.raises(ValueError):
        module.ReceivedCameraSubmissionAssessment(
            module._canonical(data), prerequisites
        )


@pytest.mark.parametrize(
    "change",
    [
        "source-notebook",
        "source-media",
        "false-image",
        "purchase-is-notebook",
        "foreign-inspection",
    ],
)
def test_original_stage_and_inspection_roles_are_not_relabelled(prerequisites, change):
    value = submission_fixture(prerequisites)
    kwargs = value["kwargs"]
    with pytest.raises(ValueError):
        if change == "source-notebook":
            rebuild(
                value,
                notebook_reference=replace(
                    kwargs["notebook_reference"],
                    stage=PhysicalOnboardingStage.WORKSPACE_SOURCES,
                ),
            )
        elif change == "source-media":
            replace(
                kwargs["attachments"][0],
                reference=replace(
                    kwargs["attachments"][0].reference,
                    stage=PhysicalOnboardingStage.WORKSPACE_SOURCES,
                ),
            )
        elif change == "false-image":
            item = replace(
                kwargs["attachments"][1],
                basename="not-an-image.txt",
                media_type="text/plain",
            )
            rebuild(value, attachments=(kwargs["attachments"][0], item))
        else:
            inspection = kwargs["inspection"]
            if change == "purchase-is-notebook":
                inspection = replace(
                    inspection,
                    purchase_record_evidence_id=kwargs[
                        "notebook_reference"
                    ].evidence_id,
                )
            else:
                refs = inspection.binding.evidence
                inspection = replace(
                    inspection,
                    binding=replace(
                        inspection.binding,
                        evidence=(
                            refs[0],
                            replace(refs[1], payload_sha256="e" * 64),
                            refs[2],
                        ),
                    ),
                )
            rebuild(value, inspection=inspection)


@pytest.mark.parametrize("role", ["submission", "assessment", "review"])
def test_canonical_bounds_immutability_and_copy_isolation(prerequisites, role):
    record = submission_fixture(prerequisites)[role]
    with pytest.raises(FrozenInstanceError):
        record.payload = b"{}"
    value = record.to_dict()
    value["binding"]["operator_id"] = "mutated"
    assert record.to_dict()["binding"]["operator_id"] == "modeled-operator"
    for raw in (
        record.payload + b"\n",
        bytearray(record.payload),
        b"x" * (module.MAX_ASSESSMENT_BYTES + 1),
        record.payload[:-1] + b',"hardware_qualified":false}',
    ):
        with pytest.raises(ValueError):
            type(record)(raw, prerequisites)


@pytest.mark.parametrize(
    "actor", ["modeled-operator", "MODELED-OPERATOR", "bad\nactor", "é", "x" * 65]
)
def test_review_requires_distinct_bounded_actor(prerequisites, actor):
    value = submission_fixture(prerequisites)
    with pytest.raises(ValueError):
        module.review_received_camera_submission(
            value["submission"],
            value["assessment"],
            decision="ACKNOWLEDGE_EXACT",
            reviewer_id=actor,
            review_launch_id="wizard-" + "d" * 32,
            reviewed_at_ns=2000,
        )


def test_exact_review_cannot_change_subject_or_decision(prerequisites):
    value = submission_fixture(prerequisites)
    other = submission_fixture(prerequisites, observed=False)
    with pytest.raises(ValueError):
        module.review_received_camera_submission(
            value["submission"],
            other["assessment"],
            decision="ACKNOWLEDGE_EXACT",
            reviewer_id="independent",
            review_launch_id="wizard-" + "d" * 32,
            reviewed_at_ns=2000,
        )
    with pytest.raises(ValueError):
        module.review_received_camera_submission(
            value["submission"],
            value["assessment"],
            decision="FORCE_PASS",
            reviewer_id="independent",
            review_launch_id="wizard-" + "d" * 32,
            reviewed_at_ns=2000,
        )


def test_pure_chain_reads_no_paths_or_original_bytes(prerequisites, monkeypatch):
    value = submission_fixture(prerequisites)

    def forbidden(*args, **kwargs):
        pytest.fail("Pure submission chain attempted I/O")

    for name in ("open", "read_bytes", "resolve", "stat"):
        monkeypatch.setattr(Path, name, forbidden)
    assert verify(value).safe_summary() == value["submission"].safe_summary()
    assert (
        module.verify_received_camera_submission_review(
            value["review"],
            submission=value["submission"],
            assessment=value["assessment"],
            expected_review_sha256=value["review"].sha256,
        )
        == value["review"]
    )
