"""Pure original-input boundary tests; no real transaction or native acquisition.

These tests cover closed context/request/pixel-reference comparisons. They are
not acceptance of the complete three-attempt original reader or its public UI.
"""

from copy import deepcopy
from types import SimpleNamespace

import pytest

from rocell.application import camera_operating_submission_native as module
from rocell.providers.windows.native_camera_protocol import canonical, digest


def context():
    binding = dict(
        source_sha256="a" * 64,
        cell_id="cell",
        session_id="session",
        header_sha256="b" * 64,
        journal_head_sha256="c" * 64,
        probe_preparation_sha256="d" * 64,
        probe_review_sha256="e" * 64,
    )
    plan = {"launch_session_id": "launch"}
    args = dict(binding=binding, plan=plan, workflow_sha256="f" * 64)
    data = dict(
        schema="rocell.camera_probe_original_scope_summary.v1",
        source_sha256=binding["source_sha256"],
        launch_session_id="launch",
        session_id="session",
        cell_id="cell",
        header_sha256="b" * 64,
        journal_head_sha256="c" * 64,
        original_workflow_sha256="f" * 64,
        preparation_sha256="d" * 64,
        review_sha256="e" * 64,
        authenticated_at_read=True,
        currentness_requires_revalidation=True,
        physical_authority=False,
        hardware_qualified=False,
        connected=False,
        meaning="Original setup was authenticated under CAMERA ownership. This cached summary cannot authorize device access or restore the in-process guard.",
    )
    return data, args


def test_exact_historical_context_has_no_restore_side_effect():
    data, args = context()
    before = canonical(data)
    assert module._setup_context(data, **args) is None
    assert canonical(data) == before


@pytest.mark.parametrize("field", tuple(context()[0]))
def test_every_historical_scope_field_is_independently_bound(field):
    data, args = context()
    data[field] = 0 if type(data[field]) is bool else "substituted"
    with pytest.raises(ValueError, match="SETUP_CONTEXT"):
        module._setup_context(data, **args)


@pytest.mark.parametrize("value", [None, [], {}, {"extra": True}])
def test_unknown_context_is_not_a_guard(value):
    with pytest.raises(ValueError, match="SETUP_CONTEXT"):
        module._setup_context(value, **context()[1])


def test_explicit_request_cannot_select_latest_or_multiple():
    records = {
        "request-first.json": {
            "data": {
                "attempt_id": "first",
                "permit": {"request": {"request_key": "first-key"}},
            }
        },
        "request-second.json": {
            "data": {
                "attempt_id": "second",
                "permit": {"request": {"request_key": "second-key"}},
            }
        },
    }
    assert module._resolve_request(records, "first-key") == "first"
    with pytest.raises(ValueError, match="EXACT_CAPTURE_REQUEST"):
        module._resolve_request(records, "missing")
    records["request-duplicate.json"] = deepcopy(records["request-first.json"])
    with pytest.raises(ValueError, match="EXACT_CAPTURE_REQUEST"):
        module._resolve_request(records, "first-key")


@pytest.mark.parametrize(
    "status",
    ["VERIFIED_AT_READ", "PIXEL_FILE_UNAVAILABLE_OR_CHANGED", "REFERENCE_MISMATCH"],
)
def test_historical_pixel_verdict_joins_old_reference_without_current_file_read(status):
    sha = digest(b"MODELED earlier checksum")
    checksum = SimpleNamespace(
        sha256=sha,
        to_dict=lambda: dict(
            status="CAPTURE_BYTES_HASHED",
            frame={"sha256": "a" * 64},
            verified_pixel_bytes=40,
        ),
    )
    pixel = dict(
        status=status,
        capture_checksum_sha256=sha,
        native_frame_sha256=None if status == "REFERENCE_MISMATCH" else "a" * 64,
        content_verified_at_read=status == "VERIFIED_AT_READ",
        verified_bytes=40,
    )
    before = deepcopy(pixel)
    module._historical_pixels(pixel, checksum)
    assert pixel == before
    pixel["capture_checksum_sha256"] = "b" * 64
    with pytest.raises(ValueError, match="PIXEL_REFERENCE_HASH"):
        module._historical_pixels(pixel, checksum)
    pixel = before
    if status != "REFERENCE_MISMATCH":
        pixel["native_frame_sha256"] = "b" * 64
        with pytest.raises(ValueError, match="PIXEL_HASH"):
            module._historical_pixels(pixel, checksum)
    if status == "VERIFIED_AT_READ":
        pixel["native_frame_sha256"] = "a" * 64
        pixel["verified_bytes"] += 1
        with pytest.raises(ValueError, match="PIXEL_LENGTH"):
            module._historical_pixels(pixel, checksum)


def test_arbitrary_transaction_rejected_before_subject_or_file_access():
    with pytest.raises(ValueError, match="ORIGINAL_TRANSACTION"):
        module.verify_operating_submission_native_inputs(
            object(),
            submission=None,
            expected_binding={},
            entry=None,
            preparation=None,
            review=None,
            creation_workflow_sha256="a" * 64,
            purchase_profile_payload=b"",
        )
