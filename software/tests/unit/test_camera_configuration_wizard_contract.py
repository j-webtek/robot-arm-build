"""Pure sizing policy over typed modeled native capabilities; no device I/O."""

from copy import deepcopy
from dataclasses import asdict

import pytest

from rocell.application.camera_configuration_wizard_contract import (
    configuration_capture_budget,
)
from rocell.providers.windows.camera_worker_client import MAX_FRAME_BYTES
import test_physical_camera_configuration as fixtures
from test_physical_camera_configuration import forbid_process_and_devices


@pytest.mark.parametrize(
    "stride,expected", [(8, 16), (12, 24), (-12, 24), (None, MAX_FRAME_BYTES)]
)
def test_server_budget_uses_reported_rows_or_explicit_unknown_allowance(
    tmp_path, monkeypatch, stride, expected
):
    raw = fixtures.receipt("probe")
    raw["modes"][0]["stride_bytes"] = stride
    monkeypatch.setattr(fixtures, "receipt", lambda _: deepcopy(raw))
    _, _, caps = fixtures.capabilities_fixture(tmp_path)
    candidate = fixtures.staged(caps)
    budget = configuration_capture_budget(candidate)
    assert asdict(budget) == dict(
        duration_ms=5000,
        max_frames=1,
        max_frame_bytes=expected,
        max_total_bytes=expected,
    )
    assert (
        candidate.mode.stride_bytes is stride or candidate.mode.stride_bytes == stride
    )


def test_untrusted_configuration_shape_does_not_become_budget():
    for value in (None, {}, {"max_frames": 1}, True):
        with pytest.raises(ValueError, match="EXACT_STAGED"):
            configuration_capture_budget(value)


@pytest.mark.parametrize(
    "width,height,stride", [(3, 2, 8), (4, 2, 4), (4, 128, 1048576)]
)
def test_unsupported_row_or_oversized_frame_cannot_be_admitted(
    tmp_path, monkeypatch, width, height, stride
):
    raw = fixtures.receipt("probe")
    raw["modes"][0].update(width=width, height=height, stride_bytes=stride)
    monkeypatch.setattr(fixtures, "receipt", lambda _: deepcopy(raw))
    # Either the strict native mode decoder or sizing policy must refuse it.
    with pytest.raises(ValueError):
        _, _, caps = fixtures.capabilities_fixture(tmp_path)
        configuration_capture_budget(fixtures.staged(caps))
