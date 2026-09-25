"""Actual compound depth/redaction under unchanged general export limits."""

from copy import deepcopy

from rocell.application.camera_operating_submission import CameraOperatingSubmission
from rocell.application.wizard_diagnostic_export import sanitize_diagnostic_record
from test_camera_operating_submission import seed, build


def test_full_compound_fits_flat_document_export_with_unchanged_limits(seed):
    subject = build(seed)
    packet = dict(
        documents={subject.sha256: subject.to_dict()},
        attempts=[],
        original_readback=None,
    )
    value = dict(diagnostics=packet, original_bytes_preserved=True)
    # A whole original compound, not a tiny display-only substitute.
    assert sanitize_diagnostic_record(value) == value
    assert CameraOperatingSubmission(subject.payload).sha256 == subject.sha256
