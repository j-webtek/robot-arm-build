"""Deterministic campaign archive for isolated import validation, not release."""
import io
from pathlib import Path
import zipfile

from .observational_native_package import expected_archive as shared_archive
from .owned_arm_feedback_package import _WORKSPACE, _read, _archive, MAX_FILE_BYTES, MAX_PACKAGE_BYTES
from rocell.application.physical_onboarding_durability import publish_bytes, PublicationMode

CHILD = Path(__file__).with_name('_positional_campaign_native_child.py')
EXTRA = (
    'application/base_speed_experiment.py',
    'application/base_reported_timing.py',
    'arm/campaign_stream_sync.py',
    'arm/cross_window_framing.py',
    'arm/joint_endpoint_verification.py',
    'arm/endpoint_persistence.py',
    'safety/positional_campaign_authority.py',
    'safety/positional_campaign_admission.py',
    'application/positional_campaign_launch.py',
    'application/positional_campaign_reference_reader.py',
    'application/positional_campaign_capture.py',
    'application/positional_campaign_reconstruction.py',
    'application/positional_campaign_native_review.py',
    'application/positional_campaign_native_retention.py',
    'providers/windows/positional_current_context.py',
    'providers/windows/positional_campaign_native_protocol.py',
    'providers/windows/positional_campaign_invocation.py',
    'providers/windows/positional_campaign_bootstrap.py',
    'providers/windows/positional_campaign_prelaunch.py',
    'providers/windows/positional_campaign_serial_api.py',
    'providers/windows/positional_campaign_serial_connection.py',
    'providers/windows/positional_campaign_execution.py',
    'providers/windows/positional_campaign_child_execution.py',
)


def expected_archive():
    # An explicit roster keeps tests, recordings and unrelated application
    # bootstraps out of the child; namespace initializers remain inert.
    with zipfile.ZipFile(io.BytesIO(shared_archive())) as source:
        entries = {name: source.read(name) for name in source.namelist()}
    for name in EXTRA:
        entries['rocell/' + name] = _read(_WORKSPACE/'software/src/rocell'/name, MAX_FILE_BYTES)
    return _archive(entries)


def prepare(directory):
    return publish_bytes(directory, 'positional-campaign-native.zip', expected_archive(),
        mode=PublicationMode.IMMUTABLE, maximum_bytes=MAX_PACKAGE_BYTES)
