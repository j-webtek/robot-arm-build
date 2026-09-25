"""Deterministic commissioning dependency bundle; not live launch admission."""
import io
from pathlib import Path
import zipfile

from .endpoint_native_package import expected_archive as endpoint_archive
from .owned_arm_feedback_package import _WORKSPACE, _read, _archive, MAX_FILE_BYTES, MAX_PACKAGE_BYTES
from rocell.application.physical_onboarding_durability import publish_bytes, PublicationMode

CHILD=Path(__file__).with_name('_first_motion_native_child.py')
EXTRA=(
    'providers/windows/first_motion_native_result.py',
    'providers/windows/first_motion_child_execution.py',
    'providers/windows/first_motion_native_registration.py',
    'application/first_motion_evidence_snapshot.py',
    'providers/windows/first_motion_native_protocol.py',
    'application/first_motion_contract.py',
    'application/first_motion_measurements.py',
    'application/first_motion_capture.py',
    'application/first_motion_capture_validation.py',
    'application/first_motion_owned_trial.py',
    'application/first_motion_worker_claim.py',
    'application/first_motion_reference_reader.py',
    'application/first_motion_result_retention.py',
    'application/first_motion_result_review.py',
    'arm/first_motion_analysis.py',
    'safety/first_motion_admission.py',
    'safety/first_motion_review_authority.py',
    'providers/windows/first_motion_current_context.py',
    'providers/windows/first_motion_serial_api.py',
    'providers/windows/first_motion_serial_connection.py',
    'providers/windows/first_motion_trial_execution.py',
)


def expected_archive():
    # Explicit roster only: do not pick up wizard servers, arbitrary scripts or
    # unreviewed source files through recursive filesystem inclusion.
    with zipfile.ZipFile(io.BytesIO(endpoint_archive())) as source:
        entries={name:source.read(name) for name in source.namelist()}
    for name in EXTRA:
        entries['rocell/'+name]=_read(_WORKSPACE/'software/src/rocell'/name,MAX_FILE_BYTES)
    return _archive(entries)


def prepare(directory):
    return publish_bytes(directory,'first-motion-native.zip',expected_archive(),
        mode=PublicationMode.IMMUTABLE,maximum_bytes=MAX_PACKAGE_BYTES)
