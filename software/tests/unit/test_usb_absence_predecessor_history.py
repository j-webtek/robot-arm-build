"""Earlier cards stay historical at a modeled v10/v11 successor boundary.

Only the version label is modeled here to isolate card adoption/eligibility;
the earlier subjects use existing real codecs over modeled storage and physical
facts. Authentic v11 grammar is tested separately by its original reader. This
test performs no actual M1, process, CIM or device operation.
"""

from copy import deepcopy

import pytest

from rocell.application import physical_source_qualification_service as source
from rocell.application import physical_static_camera_onboarding_service as static
from rocell.application import physical_received_camera_service as received_module
from rocell.application import physical_camera_identity_service as identity_module

from test_physical_camera_identity_service import identity
from test_physical_received_camera_service import received
from test_physical_static_camera_onboarding_service import static_service
from test_physical_source_qualification_service import modeled
from test_physical_camera_intake_setup import setup_flow
from test_physical_source_qualification_readback import source_model
from test_physical_camera_intake_session import intake_model
from test_physical_camera_session_readback import model, no_devices, workspace


@pytest.mark.parametrize("version", [10, 11])
@pytest.mark.parametrize(
    "module,owner_type",
    [
        (source, source.PhysicalSourceQualificationService),
        (static, static.PhysicalStaticCameraOnboardingService),
        (received_module, received_module.PhysicalReceivedCameraService),
        (identity_module, identity_module.PhysicalCameraIdentityService),
    ],
)
def test_audited_successor_keeps_prefix_historical_and_nonreplayable(
    identity, monkeypatch, version, module, owner_type
):
    current, _, _, _ = identity
    setup = current.setup
    original = setup.original_source_workflow()
    modeled_successor = deepcopy(original)
    modeled_successor["schema"] = (
        f"rocell.physical_camera_source_workflow_readback.v{version}"
    )
    before = deepcopy(modeled_successor)
    monkeypatch.setattr(
        setup, "original_source_workflow", lambda: deepcopy(modeled_successor)
    )
    owner = owner_type(setup)
    owner.observe_setup()
    view = owner.view()
    assert view["publication"] == dict(status="HISTORICAL_HELD", operation_id=None)
    assert view["next_action"] is None
    for action in module.ACTIONS:
        # Historical metadata exports remain permitted; they do not mutate the
        # commissioning original or reactivate an earlier collection/review.
        if "export" not in action:
            assert owner.blocked_reason(action) is not None, action
    assert owner.view() == view and modeled_successor == before
    assert original["schema"] != modeled_successor["schema"]
