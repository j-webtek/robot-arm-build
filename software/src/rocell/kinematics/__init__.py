"""Simulation-only RoArm-M3 kinematics.

This package contains no transport, controller protocol, permit, or live-motion
integration.  Its outputs are diagnostic simulation artifacts only.
"""

from .ik import (
    ARM_JOINT_NAMES,
    GRIPPER_JOINT_NAME,
    HAND_TCP_LINK_NAME,
    MAX_TASK_JACOBIAN_FK_EVALUATIONS,
    BoardToolTipTarget,
    IkAttemptReport,
    IkContractError,
    IkOptions,
    IkResult,
    IkStatus,
    NamedJointPosition,
    PoseResidual,
    RoArmM3NumericalIk,
    WeightedTaskJacobianConditioning,
)

__all__ = [
    "ARM_JOINT_NAMES",
    "GRIPPER_JOINT_NAME",
    "HAND_TCP_LINK_NAME",
    "MAX_TASK_JACOBIAN_FK_EVALUATIONS",
    "BoardToolTipTarget",
    "IkAttemptReport",
    "IkContractError",
    "IkOptions",
    "IkResult",
    "IkStatus",
    "NamedJointPosition",
    "PoseResidual",
    "RoArmM3NumericalIk",
    "WeightedTaskJacobianConditioning",
]
