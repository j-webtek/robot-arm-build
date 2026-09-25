"""Deterministic explicit observational-worker dependency roster."""
import io
from pathlib import Path
import zipfile

from .first_motion_native_package import expected_archive as commissioning_archive
from .owned_arm_feedback_package import _WORKSPACE, _read, _archive, MAX_FILE_BYTES, MAX_PACKAGE_BYTES
from rocell.application.physical_onboarding_durability import publish_bytes, PublicationMode

CHILD = Path(__file__).with_name('_observational_native_child.py')
EXTRA = (
    'motion/observational_wrist_plan.py',
    'arm/observational_wrist_analysis.py',
    'arm/wrist_endpoint_verification.py',
    'application/observational_capture_preview.py',
    'application/observational_command_binding.py',
    'application/observational_capture.py',
    'application/observational_owned_trial.py',
    'application/observational_result_review.py',
    'application/observational_worker_claim.py',
    'application/observational_reference_reader.py',
    'safety/observational_review_authority.py',
    'safety/observational_admission.py',
    'providers/windows/observational_current_context.py',
    'providers/windows/observational_serial_api.py',
    'providers/windows/observational_serial_connection.py',
    'providers/windows/observational_trial_execution.py',
    'providers/windows/observational_native_protocol.py',
    'providers/windows/observational_native_result.py',
    'providers/windows/observational_native_registration.py',
    'providers/windows/observational_prelaunch.py',
    'providers/windows/observational_child_execution.py',
)


def expected_archive():
    # Reuse the explicit shared-I/O dependency roster, not a recursive source
    # directory scan that could accidentally include servers or local scripts.
    with zipfile.ZipFile(io.BytesIO(commissioning_archive())) as source:
        entries = {name: source.read(name) for name in source.namelist()}
    for name in EXTRA:
        entries['rocell/'+name] = _read(_WORKSPACE/'software/src/rocell'/name, MAX_FILE_BYTES)
    return _archive(entries)


def prepare(directory):
    return publish_bytes(directory, 'observational-native.zip', expected_archive(),
        mode=PublicationMode.IMMUTABLE, maximum_bytes=MAX_PACKAGE_BYTES)
