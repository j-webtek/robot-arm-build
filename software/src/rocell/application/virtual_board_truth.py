"""One opaque, immutable board-pose truth shared by virtual plant sensors.

The synthetic camera and truth-referenced contact projector must observe the
same simulated physical board.  This holder gives them a common content digest
without exposing ``Wv_T_board`` in evidence or offering the planner a raw
registration.  Its transform operations are deliberately narrow: derive what
an arm camera sees, or express an achieved tool transform in the truth board.

Python object privacy is not a security boundary.  This is a data-flow contract
that makes accidental use of plant truth by planning code visible in review.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json

from rocell.geometry import RigidTransform


HIDDEN_VIRTUAL_BOARD_TRUTH_SCHEMA = "rocell.hidden_virtual_board_truth.v1"


class VirtualBoardTruthError(ValueError):
    """A private virtual board truth or requested transform is invalid."""


def _stable_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _transform_dict(transform: RigidTransform) -> dict[str, object]:
    return {
        "to_frame": transform.parent_frame,
        "from_frame": transform.child_frame,
        "rotation_row_major": list(transform.rotation.matrix),
        "translation_mm": [
            transform.translation_mm.x,
            transform.translation_mm.y,
            transform.translation_mm.z,
        ],
    }


@dataclass(frozen=True, slots=True)
class HiddenVirtualBoardTruth:
    """Plant-only ``Wv_T_board`` whose public representation is hash-only."""

    _Wv_T_board: RigidTransform = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self._Wv_T_board, RigidTransform):
            raise TypeError("Wv_T_board must be a RigidTransform")
        if (
            self._Wv_T_board.parent_frame != "Wv"
            or self._Wv_T_board.child_frame != "board"
        ):
            raise VirtualBoardTruthError(
                "private virtual truth must be exactly Wv_T_board"
            )

    @property
    def board_frame(self) -> str:
        return "board"

    @property
    def content_hash(self) -> str:
        # Hashing occurs inside the holder; the transform is never returned by
        # an evidence method or serialized into a result.
        return _stable_hash(
            {
                "schema": HIDDEN_VIRTUAL_BOARD_TRUTH_SCHEMA,
                "Wv_T_board": _transform_dict(self._Wv_T_board),
                "simulation_only": True,
            }
        )

    def camera_T_board(self, Wv_T_camera: RigidTransform) -> RigidTransform:
        """Return what one explicitly framed virtual camera observes."""

        if not isinstance(Wv_T_camera, RigidTransform):
            raise TypeError("Wv_T_camera must be a RigidTransform")
        if Wv_T_camera.parent_frame != "Wv":
            raise VirtualBoardTruthError("camera transform parent must be Wv")
        return Wv_T_camera.inverse().compose(self._Wv_T_board)

    def board_T_achieved(self, Wv_T_achieved: RigidTransform) -> RigidTransform:
        """Express one achieved plant transform in the hidden truth board."""

        if not isinstance(Wv_T_achieved, RigidTransform):
            raise TypeError("Wv_T_achieved must be a RigidTransform")
        if Wv_T_achieved.parent_frame != "Wv":
            raise VirtualBoardTruthError("achieved transform parent must be Wv")
        return self._Wv_T_board.inverse().compose(Wv_T_achieved)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": HIDDEN_VIRTUAL_BOARD_TRUTH_SCHEMA,
            "world_frame": "Wv",
            "board_frame": self.board_frame,
            "truth_registration_sha256": self.content_hash,
            "truth_transform_serialized": False,
            "simulation_only": True,
            "can_release_physical_gates": False,
        }


__all__ = [
    "HIDDEN_VIRTUAL_BOARD_TRUTH_SCHEMA",
    "HiddenVirtualBoardTruth",
    "VirtualBoardTruthError",
]
