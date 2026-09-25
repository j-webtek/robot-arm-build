"""Deterministic closed endpoint dependency bundle; packaging is not admission."""

import io
from pathlib import Path
import zipfile

from .powered_feedback_native_package import expected_archive as feedback_archive
from .owned_arm_feedback_package import _WORKSPACE, _read, _archive, _STUB, MAX_FILE_BYTES, MAX_PACKAGE_BYTES
from rocell.application.physical_onboarding_durability import publish_bytes, PublicationMode

CHILD = Path(__file__).with_name('_endpoint_native_child.py')
EXTRA = (
    'providers/windows/endpoint_native_registration.py',
    'providers/windows/endpoint_native_wire.py',
    'providers/windows/endpoint_native_result.py',
    'providers/windows/bench_review_key.py',
    'providers/windows/endpoint_current_context.py',
    'providers/windows/endpoint_child_execution.py',
    'application/endpoint_trial_contract.py',
    'application/endpoint_trial_draft.py',
    'application/endpoint_engineering_review.py',
    'application/endpoint_reference_reader.py',
    'application/endpoint_evidence_snapshot.py',
    'application/endpoint_attempt_reservation.py',
    'application/endpoint_worker_claim.py',
    'application/endpoint_capture.py',
    'application/endpoint_write_boundary.py',
    'application/endpoint_owned_trial.py',
    'arm/telemetry_coverage.py',
    'arm/movement_analysis.py',
    'motion/characterization_plan.py',
    'rc03/build_snapshot.py',
    'rc03/importer.py',
    'rc03/integrity.py',
    'safety/permit.py',
    'safety/bench_endpoint.py',
    'safety/bench_review_authority.py',
    'providers/windows/endpoint_serial_api.py',
    'providers/windows/endpoint_serial_connection.py',
    'providers/windows/endpoint_trial_execution.py',
)


def expected_archive():
    # Reuse the reviewed closed feedback dependency roster, not a source-tree
    # glob. Namespace bootstraps stay inert; each additional module is explicit.
    with zipfile.ZipFile(io.BytesIO(feedback_archive())) as source:
        entries = {name:source.read(name) for name in source.namelist()}
    for namespace in ('motion','safety','rc03'):
        entries['rocell/'+namespace+'/__init__.py'] = _STUB
    for name in EXTRA:
        entries['rocell/'+name] = _read(_WORKSPACE/'software/src/rocell'/name,MAX_FILE_BYTES)
    return _archive(entries)


def prepare(directory):
    return publish_bytes(directory,'endpoint-native.zip',expected_archive(),
                         mode=PublicationMode.IMMUTABLE,maximum_bytes=MAX_PACKAGE_BYTES)
