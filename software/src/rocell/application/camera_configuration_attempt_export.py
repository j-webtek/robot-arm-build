"""Distinct settings-capture diagnostics, using the existing bounded codec.

This module only exports/decodes cached data. It opens no device or original
store and never constructs live Session/admission/permit objects. Partial and
unknown outcomes are preserved; image pixels are not part of this packet.
"""

from pathlib import Path
from threading import Event

from .camera_probe_attempt_export import (
    CameraProbeAttemptExportError,
    _CONFIGURATION,
    _prepare_attempt_export,
    _restore_attempt_export,
    _export_attempt,
    MAX_INPUT_BYTES,
    TIMEOUT_NS,
)

SCHEMA = _CONFIGURATION.snapshot_schema
DIAGNOSTICS_SCHEMA = _CONFIGURATION.diagnostics_schema
PART_SCHEMA = _CONFIGURATION.part_schema


class CameraConfigurationAttemptExportError(ValueError):
    pass


def _run_codec(callback, *args, **kwargs):
    try:
        return callback(*args, **kwargs, profile=_CONFIGURATION)
    except CameraProbeAttemptExportError as error:
        raise CameraConfigurationAttemptExportError(
            "CAMERA_CONFIGURATION_ATTEMPT_EXPORT_INVALID_OR_OVER_CAPACITY"
        ) from error


def prepare_configuration_attempt_export(diagnostics):
    """Validate bounded reconstruction before creating an export directory."""
    return _run_codec(_prepare_attempt_export, diagnostics)


def restore_configuration_attempt_export(snapshot, attachments):
    """Return diagnostic dictionaries only, never a restored connection."""
    return _run_codec(_restore_attempt_export, snapshot, attachments)


def export_configuration_attempt(
    diagnostics, *, export_parent: Path, cancellation: Event, deadline_ns: int
):
    """Copy one cached attempt into the operator-assigned local export parent."""
    return _run_codec(
        _export_attempt,
        diagnostics,
        export_parent=export_parent,
        cancellation=cancellation,
        deadline_ns=deadline_ns,
    )
