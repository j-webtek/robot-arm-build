"""Cross-source workcell alignment contracts."""

from .alignment import (
    PlacematAlignmentCheck,
    PlacematAlignmentReport,
    validate_placemat_alignment,
)
from .camera_architecture import (
    CAMERA_ARCHITECTURE_PLAN_SCHEMA,
    DEFAULT_CAMERA_ARCHITECTURE_PLAN,
    MAX_CAMERA_ARCHITECTURE_PLAN_BYTES,
    CameraArchitecturePlan,
    CameraArchitecturePlanError,
    OpticalFovScreen,
    load_camera_architecture_plan,
)
from .static_camera_support import (
    DEFAULT_STATIC_CAMERA_SUPPORT_DESIGN,
    MAX_STATIC_CAMERA_SUPPORT_BYTES,
    STATIC_CAMERA_SUPPORT_SCHEMA,
    StaticCameraSupportDesign,
    StaticCameraSupportError,
    StaticCameraSupportMetrics,
    load_static_camera_support_design,
)

__all__ = [
    "CAMERA_ARCHITECTURE_PLAN_SCHEMA",
    "DEFAULT_CAMERA_ARCHITECTURE_PLAN",
    "MAX_CAMERA_ARCHITECTURE_PLAN_BYTES",
    "CameraArchitecturePlan",
    "CameraArchitecturePlanError",
    "OpticalFovScreen",
    "DEFAULT_STATIC_CAMERA_SUPPORT_DESIGN",
    "MAX_STATIC_CAMERA_SUPPORT_BYTES",
    "STATIC_CAMERA_SUPPORT_SCHEMA",
    "StaticCameraSupportDesign",
    "StaticCameraSupportError",
    "StaticCameraSupportMetrics",
    "PlacematAlignmentCheck",
    "PlacematAlignmentReport",
    "load_camera_architecture_plan",
    "load_static_camera_support_design",
    "validate_placemat_alignment",
]
