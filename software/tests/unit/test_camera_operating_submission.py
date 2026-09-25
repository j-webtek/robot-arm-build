"""Pure compound-record tests with modeled metadata, not original store proof.

One immutable metadata seed is built with incapable native owners. Pixel checks,
permit/checksum references and session hashes are explicitly fictional; no image,
original store, hardware connection, timing qualification or permission is made.
"""

from copy import deepcopy
import ctypes
import json
import subprocess

import pytest

from rocell.application import camera_operating_submission as module
from rocell.application.camera_operating_original_assessment import SEALED_MEANING
from rocell.application.camera_operating_stage_requirements import (
    RETENTION_HOLD,
    project_operating_requirements,
)
from rocell.providers.windows.camera_worker_client import WindowsCameraWorkerClient
from rocell.providers.windows.native_camera_protocol import canonical, digest
from test_camera_operating_evidence_preflight import case, assess


@pytest.fixture(scope="module")
def seed(tmp_path_factory):
    def forbidden(*args, **kwargs):
        pytest.fail("Submission codec test attempted native/device access")

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(subprocess, "Popen", forbidden)
        if hasattr(ctypes, "WinDLL"):
            patch.setattr(ctypes, "WinDLL", forbidden)
        for name in (
            "enumerate_metadata",
            "resolve_identity_metadata",
            "probe",
            "capture",
        ):
            patch.setattr(WindowsCameraWorkerClient, name, forbidden)
        inputs, capture = case(tmp_path_factory.mktemp("submission-metadata"), patch)
        preflight = assess(inputs, (capture("capture-one"), capture("capture-two")))
    proposal = json.loads(inputs["proposal_payload"])
    captures, pixels = [], []
    for index in range(2):
        row = dict(
            request_key="MODELED-request-" + str(index),
            attempt_id="MODELED-attempt-" + str(index),
            permit_sha256=digest(f"MODELED permit {index}".encode()),
            capture_checksum_sha256=digest(f"MODELED checksum {index}".encode()),
        )
        captures.append(row)
        pixels.append(
            dict(
                schema="rocell.camera_operating_pixel_check.v2",
                **{
                    k: row[k]
                    for k in ("request_key", "attempt_id", "capture_checksum_sha256")
                },
                status="VERIFIED_AT_READ",
                reference_scope="M1_SEALED_CAPTURE_CHECKSUM",
                result_sha256=None,
                native_frame_sha256=digest(b"MODELED pixels"),
                verified_bytes=5472 * 3648 * 2,
                content_verified_at_read=True,
                frame_freshness_assessed=False,
                original_stage_record_retained=False,
                physical_authority=False,
            )
        )
    unresolved = [
        k
        for k in preflight.to_dict()["owner_obligations"]
        if k
        not in (
            "ORIGINAL_STORE_AND_CURRENTNESS_NOT_AUTHENTICATED",
            "PIXEL_FILES_NOT_VERIFIED",
        )
    ] + [RETENTION_HOLD]
    report = dict(
        schema="rocell.camera_original_operating_assessment.v4",
        status="ORIGINAL_INPUTS_CHECKED_APPROVAL_HELD",
        original_inputs_authenticated_at_read=True,
        session_id=proposal["entry_binding"]["session_id"],
        header_sha256=proposal["entry_binding"]["header_sha256"],
        journal_head_sha256=digest(b"MODELED stage head"),
        original_records_sha256=digest(b"MODELED original inventory"),
        proposal_sha256=inputs["expected_proposal_sha256"],
        captures=captures,
        pixel_checks=pixels,
        pixel_reference_scope="PER_CAPTURE_ORIGINAL_OR_LEGACY_REFERENCE",
        preflight=preflight.to_dict(),
        preflight_sha256=preflight.sha256,
        unresolved_checks=unresolved,
        stage_requirements=project_operating_requirements(
            unresolved, preflight.to_dict()["failed_checks"]
        ),
        currentness_requires_revalidation=True,
        original_stage_record_retained=False,
        approved_operating_policy=False,
        physical_authority=False,
        hardware_qualified=False,
        connected=False,
        meaning=SEALED_MEANING,
    )
    binding = dict(
        **{
            k: proposal["entry_binding"][k]
            for k in ("cell_id", "session_id", "source_sha256", "header_sha256")
        },
        entry_sha256=proposal["subjects"]["entry_sha256"],
        probe_preparation_sha256=digest(b"MODELED preparation"),
        probe_review_sha256=digest(b"MODELED review"),
        **{k: report[k] for k in ("journal_head_sha256", "original_records_sha256")},
    )
    return dict(
        submission_id="cameraoperating-" + "9" * 32,
        operator_id="MODELED submitter",
        recorded_at_utc_ns=789,
        binding=binding,
        proposal_payload=inputs["proposal_payload"],
        assessment_payload=canonical(report),
    )


def build(seed):
    return module.build_camera_operating_submission(**deepcopy(seed))


def verify(subject, seed, **changes):
    inputs = dict(
        expected_sha256=subject.sha256,
        expected_binding=deepcopy(seed["binding"]),
        expected_proposal_payload=seed["proposal_payload"],
        expected_assessment_payload=seed["assessment_payload"],
    )
    inputs.update(changes)
    return module.verify_camera_operating_submission(subject.payload, **inputs)


def rehash(data):
    data["proposal_sha256"] = digest(canonical(data["proposal"]))
    data["assessment"]["preflight_sha256"] = digest(
        canonical(data["assessment"]["preflight"])
    )
    data["assessment_sha256"] = digest(canonical(data["assessment"]))
    return canonical(data)


def test_exact_inner_bytes_roundtrip_without_promoting_diagnostic_retention(seed):
    subject = build(seed)
    assert verify(subject, seed) == subject
    data = subject.to_dict()
    assert canonical(data["proposal"]) == seed["proposal_payload"]
    assert canonical(data["assessment"]) == seed["assessment_payload"]
    assert RETENTION_HOLD in data["assessment"]["unresolved_checks"]
    assert all(data[k] is False for k in module.FALSE_FIELDS)
    assert data["assessment"]["original_stage_record_retained"] is False
    assert len(subject.payload) < module.MAX_BYTES
    label = module.camera_operating_submission_label(data["submission_id"])
    event = module.camera_operating_submission_event(data["submission_id"])
    assert module.LABEL.fullmatch(label)[1] == data["submission_id"]
    assert module.EVENT.fullmatch(event)[1] == "9" * 32


@pytest.mark.parametrize("key", module.BINDING_FIELDS)
def test_independent_expected_binding_cannot_come_from_the_record(seed, key):
    subject = build(seed)
    expected = deepcopy(seed["binding"])
    expected[key] = "wrong-context" if key in ("cell_id", "session_id") else "f" * 64
    with pytest.raises(module.CameraOperatingSubmissionError):
        verify(subject, seed, expected_binding=expected)


@pytest.mark.parametrize("role", ["proposal", "assessment", "digest"])
def test_independent_expected_subjects_are_required_even_for_rehashed_records(
    seed, role
):
    subject = build(seed)
    if role == "digest":
        changes = dict(expected_sha256="f" * 64)
    else:
        data = json.loads(seed[role + "_payload"])
        if role == "proposal":
            data["rationale"] = "Different valid modeled proposal."
        else:
            data["original_records_sha256"] = "f" * 64
        changes = {"expected_" + role + "_payload": canonical(data)}
    with pytest.raises(module.CameraOperatingSubmissionError):
        verify(subject, seed, **changes)


@pytest.mark.parametrize("key", module.FALSE_FIELDS)
@pytest.mark.parametrize("value", [True, 0])
def test_outer_authority_flags_are_exact_false(seed, key, value):
    data = build(seed).to_dict()
    data[key] = value
    with pytest.raises(module.CameraOperatingSubmissionError):
        module.CameraOperatingSubmission(canonical(data))


@pytest.mark.parametrize(
    "fault",
    [
        "legacy",
        "mixed",
        "missing",
        "duplicate",
        "wrong-pixel",
        "pixel-authority",
        "tiny",
        "overflow",
        "bool-bytes",
        "integer-verified",
        "changed-status",
        "invented-log",
        "unknown-check",
        "missing-hold",
        "wrong-stage",
        "settings",
        "preflight-proposal",
        "report-proposal",
        "pixel-hash",
        "header",
        "entry",
        "wrong-schema",
        "meaning",
        "extra-field",
        "old-time",
        "bool-time",
        "bad-id",
    ],
)
def test_rehashed_internal_inconsistency_is_rejected(seed, fault):
    data = build(seed).to_dict()
    report = data["assessment"]
    pixel = report["pixel_checks"][0]
    if fault == "legacy":
        report["schema"] = "rocell.camera_original_operating_assessment.v3"
    elif fault == "mixed":
        pixel["schema"] = "rocell.camera_operating_pixel_check.v1"
    elif fault == "missing":
        report["captures"].pop()
        report["pixel_checks"].pop()
    elif fault == "duplicate":
        report["captures"][1] = deepcopy(report["captures"][0])
        report["pixel_checks"][1] = deepcopy(pixel)
    elif fault == "wrong-pixel":
        pixel["request_key"] = "another-request"
    elif fault == "pixel-authority":
        pixel["original_stage_record_retained"] = True
    elif fault in ("tiny", "overflow", "bool-bytes"):
        pixel["verified_bytes"] = {
            "tiny": 16,
            "overflow": module.MAX_FRAME_BYTES + 1,
            "bool-bytes": True,
        }[fault]
    elif fault == "integer-verified":
        pixel["content_verified_at_read"] = 1
    elif fault == "changed-status":
        pixel["status"] = "PIXEL_FILE_UNAVAILABLE_OR_CHANGED"
    elif fault == "invented-log":
        pixel["result_sha256"] = "f" * 64
    elif fault == "unknown-check":
        report["unresolved_checks"].append("UNKNOWN_HOLD")
    elif fault == "missing-hold":
        report["unresolved_checks"].remove(RETENTION_HOLD)
    elif fault == "wrong-stage":
        report["stage_requirements"]["requirements"][0]["owner_stages"] = [
            "static_registration"
        ]
    elif fault == "settings":
        report["preflight"]["settings_epoch"] = "f" * 64
    elif fault == "preflight-proposal":
        report["preflight"]["proposal_sha256"] = "f" * 64
    elif fault == "report-proposal":
        report["proposal_sha256"] = "f" * 64
    elif fault == "pixel-hash":
        pixel["capture_checksum_sha256"] = "f" * 64
    elif fault == "header":
        report["header_sha256"] = "f" * 64
    elif fault == "entry":
        data["binding"]["entry_sha256"] = "f" * 64
    elif fault == "wrong-schema":
        data["schema"] = "rocell.camera_operating_submission.v2"
    elif fault == "meaning":
        report["meaning"] = "Approved and connected"
    elif fault == "extra-field":
        data["approve"] = True
    elif fault == "old-time":
        data["recorded_at_utc_ns"] = 1
    elif fault == "bool-time":
        data["recorded_at_utc_ns"] = True
    else:
        data["submission_id"] = "uploaded-record"
    with pytest.raises(module.CameraOperatingSubmissionError):
        module.CameraOperatingSubmission(rehash(data))


@pytest.mark.parametrize(
    "status", ["REFERENCE_MISMATCH", "PIXEL_FILE_UNAVAILABLE_OR_CHANGED"]
)
def test_failed_pixel_observation_can_be_retained_without_erasing_its_hold(
    seed, status
):
    args = deepcopy(seed)
    report = json.loads(args["assessment_payload"])
    report["pixel_checks"][0].update(
        status=status, verified_bytes=0, content_verified_at_read=False
    )
    if status == "REFERENCE_MISMATCH":
        report["pixel_checks"][0]["native_frame_sha256"] = None
    unresolved = [
        k
        for k in report["preflight"]["owner_obligations"]
        if k != "ORIGINAL_STORE_AND_CURRENTNESS_NOT_AUTHENTICATED"
    ] + [RETENTION_HOLD]
    report["unresolved_checks"] = unresolved
    report["stage_requirements"] = project_operating_requirements(
        unresolved, report["preflight"]["failed_checks"]
    )
    args["assessment_payload"] = canonical(report)
    subject = build(args)
    assert verify(subject, args) == subject
    assert (
        "PIXEL_FILES_NOT_VERIFIED"
        in subject.to_dict()["assessment"]["unresolved_checks"]
    )


@pytest.mark.parametrize(
    "fault", ["oversize", "noncanonical", "mutable", "duplicate-key", "truncated"]
)
def test_wire_payload_is_closed_and_bounded(seed, fault):
    subject = build(seed)
    payload = subject.payload
    if fault == "oversize":
        payload = b" " * (module.MAX_BYTES + 1)
    elif fault == "noncanonical":
        payload += b"\n"
    elif fault == "mutable":
        payload = bytearray(payload)
    elif fault == "duplicate-key":
        payload = b'{"schema":"wrong",' + payload[1:]
    else:
        payload = payload[:-1]
    with pytest.raises(module.CameraOperatingSubmissionError):
        module.CameraOperatingSubmission(payload)


@pytest.mark.parametrize(
    "suffix", ["0123456789abcdef" * 2, "abcdef" * 5 + "ab", "1" * 32]
)
def test_event_uses_journal_uppercase_grammar_without_changing_payload_id(suffix):
    from rocell.application.physical_onboarding_v2 import _detail_code

    identifier = "cameraoperating-" + suffix
    event = module.camera_operating_submission_event(identifier)
    assert _detail_code(event) == event
    assert module.EVENT.fullmatch(event).group(1).lower() == suffix
    assert module.camera_operating_submission_label(identifier).endswith(identifier)
