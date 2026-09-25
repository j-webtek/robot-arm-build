"""Explicit deterministic correction dependency archive; no live registration."""
import io
from pathlib import Path
import zipfile

from .absolute_wrist_native_package import expected_archive as absolute_archive
from .owned_arm_feedback_package import _WORKSPACE,_read,_archive,MAX_FILE_BYTES,MAX_PACKAGE_BYTES
from rocell.application.physical_onboarding_durability import publish_bytes,PublicationMode

CHILD=Path(__file__).with_name('_wrist_correction_native_child.py')
EXTRA=(
    'application/wrist_accuracy_analysis.py',
    'application/wrist_correction_proposal.py',
    'application/wrist_correction_preview.py',
    'application/wrist_correction_consumption.py',
    'application/wrist_correction_command_binding.py',
    'application/wrist_correction_capture.py',
    'application/wrist_correction_final_readback.py',
    'application/wrist_correction_final_capture.py',
    'application/wrist_correction_owned_final_capture.py',
    'application/wrist_correction_final_review.py',
    'application/wrist_correction_final_consumption.py',
    'application/wrist_correction_owned_trial.py',
    'application/wrist_correction_result_review.py',
    'application/wrist_correction_result_publication.py',
    'application/wrist_correction_worker_claim.py',
    'application/wrist_correction_reference_reader.py',
    'safety/wrist_correction_review_authority.py',
    'safety/wrist_correction_admission.py',
    'providers/windows/wrist_correction_current_context.py',
    'providers/windows/wrist_correction_serial_api.py',
    'providers/windows/wrist_correction_serial_connection.py',
    'providers/windows/wrist_correction_native_protocol.py',
    'providers/windows/wrist_correction_evidence_store.py',
    'providers/windows/wrist_correction_trial_execution.py',
    'providers/windows/wrist_correction_native_result.py',
    'providers/windows/wrist_correction_parent_review.py',
    'providers/windows/wrist_correction_native_registration.py',
    'providers/windows/wrist_correction_prelaunch.py',
    'providers/windows/wrist_correction_child_execution.py',
    'providers/windows/wrist_correction_invocation.py',
)


def expected_archive():
    with zipfile.ZipFile(io.BytesIO(absolute_archive())) as source:
        entries={name:source.read(name) for name in source.namelist()}
    for name in EXTRA:
        entries['rocell/'+name]=_read(_WORKSPACE/'software/src/rocell'/name,MAX_FILE_BYTES)
    return _archive(entries)


def prepare(directory):
    return publish_bytes(directory,'wrist-correction-native.zip',expected_archive(),
        mode=PublicationMode.IMMUTABLE,maximum_bytes=MAX_PACKAGE_BYTES)
