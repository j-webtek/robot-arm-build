"""Closed UI names and data-only one-frame sizing; never capture authority."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .physical_camera_configuration import StagedPhysicalCameraConfiguration
    from rocell.providers.windows.camera_worker_client import CameraCampaignBudget

CAPTURE_ACTION_ID = "physical_camera_configuration_capture"
EXPORT_ACTION_ID = "physical_camera_configuration_attempt_export"
VIEW_SCHEMA = "rocell.wizard_camera_configuration_attempt.v1"
SETTINGS_PUBLICATION_SCHEMA = "rocell.wizard_logged_camera_settings.v1"
MAX_CAPTURE_ATTEMPTS = 8


def configuration_capture_budget(
    configuration: StagedPhysicalCameraConfiguration,
) -> CameraCampaignBudget:
    """Size from explicit verified intent, not a browser numeric override.

    A reported stride bounds complete rows, including the last row's padding.
    Missing stride remains unknown: allow the existing finite 64 MiB maximum,
    not an invented driver observation. Actual readback/ingestion still check
    the observed mode, stride, bytes and every existing per-frame limit.
    """
    from .physical_camera_configuration import StagedPhysicalCameraConfiguration
    from rocell.providers.windows.camera_worker_client import (
        CameraCampaignBudget,
        MAX_FRAME_BYTES,
    )

    if type(configuration) is not StagedPhysicalCameraConfiguration:
        raise ValueError("EXACT_STAGED_CAMERA_CONFIGURATION_REQUIRED")
    configuration = StagedPhysicalCameraConfiguration(configuration.payload)
    mode = configuration.mode
    if mode.subtype != "YUY2" or mode.width < 2 or mode.width % 2:
        raise ValueError("UNSUPPORTED_SETTINGS_CAPTURE_PIXEL_FORMAT")
    if mode.stride_bytes is None:
        limit = MAX_FRAME_BYTES
    else:
        if abs(mode.stride_bytes) < 2 * mode.width:
            raise ValueError("UNSUPPORTED_SETTINGS_CAPTURE_STRIDE")
        limit = abs(mode.stride_bytes) * mode.height
    if not 0 < limit <= MAX_FRAME_BYTES:
        raise ValueError("SETTINGS_CAPTURE_FRAME_BUDGET_EXCEEDED")
    return CameraCampaignBudget(5000, 1, limit, limit)
