"""Public-package checks for the newest zero-authority foundations."""

from __future__ import annotations

import rocell.application as application
import rocell.safety as safety

from rocell.application.multi_action_mission import (
    ActionOutcomeReceipt,
    AuthorizationV2MissionCursor,
    MissionCommandAuthorizationReceipt,
    MultiActionMissionSpec,
    ObservedSemanticOutcome,
    build_mission_authorization_schedule,
    run_zero_authority_multi_action_mission,
)
from rocell.safety.authorization_v2 import (
    AuthorizationEvidence,
    calibration_closure_from_registry,
    issue_ordered_simulation_permit,
)


def test_multi_action_foundation_is_exported() -> None:
    assert application.ActionOutcomeReceipt is ActionOutcomeReceipt
    assert application.AuthorizationV2MissionCursor is AuthorizationV2MissionCursor
    assert (
        application.MissionCommandAuthorizationReceipt
        is MissionCommandAuthorizationReceipt
    )
    assert application.MultiActionMissionSpec is MultiActionMissionSpec
    assert application.ObservedSemanticOutcome is ObservedSemanticOutcome
    assert (
        application.build_mission_authorization_schedule
        is build_mission_authorization_schedule
    )
    assert (
        application.run_zero_authority_multi_action_mission
        is run_zero_authority_multi_action_mission
    )


def test_authorization_v2_foundation_is_exported() -> None:
    assert safety.AuthorizationEvidence is AuthorizationEvidence
    assert (
        safety.calibration_closure_from_registry
        is calibration_closure_from_registry
    )
    assert safety.issue_ordered_simulation_permit is issue_ordered_simulation_permit
