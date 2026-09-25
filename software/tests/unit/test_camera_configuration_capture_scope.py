"""Adding a known stage-5 capture action must not widen original probe scope."""

from dataclasses import replace

import pytest

from rocell.application.camera_activation_campaign_contract import (
    ACTION_IDS,
    CONFIGURATION_CAPTURE_ACTION_ID,
)
from rocell.application.camera_probe_original_scope import CameraProbeOriginalScopeError
from test_camera_probe_original_scope import modeled, case, entry, binding, no_devices


@pytest.mark.parametrize(
    "action_id", [CONFIGURATION_CAPTURE_ACTION_ID, ACTION_IDS["capture"]]
)
def test_authenticated_probe_context_cannot_admit_either_capture(modeled, action_id):
    handle = modeled.read()
    with pytest.raises(CameraProbeOriginalScopeError, match="REQUEST_CHANGED"):
        handle.assert_current(
            modeled.tx, replace(modeled.request, action_id=action_id), modeled.snapshot
        )
    assert modeled.reads == 1
