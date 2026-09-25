"""Deterministic absolute worker import-audit package; no launch registration."""
import io
from pathlib import Path
import zipfile

from .observational_native_package import expected_archive as observational_archive
from .owned_arm_feedback_package import _WORKSPACE, _read, _archive, MAX_FILE_BYTES, MAX_PACKAGE_BYTES
from rocell.application.physical_onboarding_durability import publish_bytes, PublicationMode

CHILD = Path(__file__).with_name('_absolute_wrist_native_child.py')
EXTRA = (
    'motion/absolute_wrist_diagnostic.py',
    'safety/absolute_wrist_review_authority.py',
    'safety/absolute_wrist_admission.py',
    'application/absolute_wrist_command_binding.py',
    'application/absolute_wrist_capture.py',
    'application/absolute_wrist_result_review.py',
    'application/absolute_wrist_owned_trial.py',
    'application/absolute_wrist_worker_claim.py',
    'application/absolute_wrist_reference_reader.py',
    'providers/windows/absolute_wrist_current_context.py',
    'providers/windows/absolute_wrist_serial_api.py',
    'providers/windows/absolute_wrist_serial_connection.py',
    'providers/windows/absolute_wrist_trial_execution.py',
    'providers/windows/absolute_wrist_native_protocol.py',
    'providers/windows/absolute_wrist_native_registration.py',
    'providers/windows/absolute_wrist_prelaunch.py',
    'providers/windows/absolute_wrist_child_execution.py',
    'providers/windows/absolute_wrist_native_result.py',
)


def expected_archive():
    # Extend an explicit shared dependency roster, never scan the workspace.
    with zipfile.ZipFile(io.BytesIO(observational_archive())) as source:
        entries = {name: source.read(name) for name in source.namelist()}
    for name in EXTRA:
        entries['rocell/' + name] = _read(_WORKSPACE/'software/src/rocell'/name, MAX_FILE_BYTES)
    return _archive(entries)


def prepare(directory):
    return publish_bytes(directory, 'absolute-wrist-native.zip', expected_archive(),
        mode=PublicationMode.IMMUTABLE, maximum_bytes=MAX_PACKAGE_BYTES)
