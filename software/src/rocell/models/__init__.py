"""Strict, side-effect-free domain models used across the RoCell runtime."""

from .actions import (
    ActionPlan,
    Device,
    PressKey,
    TapPhoneTarget,
    VerifyPhoneState,
)
from .frames import FrameMismatchError, Point3Mm, Transform
from .motion_proposal import (
    Interaction,
    ModelMotionProposal,
    MotionProposalError,
    ProposalDevice,
    ProposalFrame,
    ProposalSource,
    SpeedClass,
)
from .model_motion_batch import (
    MAX_BATCH_PROPOSALS,
    MAX_BATCH_BYTES,
    ModelMotionBatch,
    ModelMotionBatchError,
    decode_model_motion_batch_json,
)
from .model_motion_batch_v2 import (
    COORDINATE_PROFILE_V2,
    MAX_BATCH_BYTES_V2,
    MAX_BATCH_PROPOSALS_V2,
    ModelMotionBatchV2,
    ModelMotionBatchV2Error,
    ModelMotionProposalV2,
    MotionCapabilityV2,
    MotionEvidenceV2,
    MotionGeometryV2,
    MotionUncertaintyV2,
    UncertaintyBoundType,
    decode_model_motion_batch_v2_json,
)
from .profiles import KeyboardProfile, PhoneKeySpec, PhoneProfile
from .units import Millimetres, Radians, finite_real

__all__ = [
    "ActionPlan",
    "Device",
    "FrameMismatchError",
    "KeyboardProfile",
    "Millimetres",
    "ModelMotionProposal",
    "ModelMotionBatch",
    "ModelMotionBatchError",
    "MAX_BATCH_PROPOSALS",
    "MAX_BATCH_BYTES",
    "decode_model_motion_batch_json",
    "ModelMotionBatchV2",
    "ModelMotionBatchV2Error",
    "ModelMotionProposalV2",
    "MotionCapabilityV2",
    "MotionEvidenceV2",
    "MotionGeometryV2",
    "MotionUncertaintyV2",
    "UncertaintyBoundType",
    "MAX_BATCH_BYTES_V2",
    "MAX_BATCH_PROPOSALS_V2",
    "COORDINATE_PROFILE_V2",
    "decode_model_motion_batch_v2_json",
    "MotionProposalError",
    "PhoneKeySpec",
    "PhoneProfile",
    "Point3Mm",
    "ProposalDevice",
    "ProposalFrame",
    "ProposalSource",
    "PressKey",
    "Radians",
    "TapPhoneTarget",
    "Transform",
    "Interaction",
    "SpeedClass",
    "VerifyPhoneState",
    "finite_real",
]
