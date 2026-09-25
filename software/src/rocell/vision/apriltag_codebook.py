"""Dependency-free released RC03 AprilTag code patterns.

The rows below are the same canonical OpenCV ``DICT_APRILTAG_36h11`` IDs 0-5
committed in ``active-project/RoCell_v0_3/scripts/generate_fiducials.py``.
They include the one-cell black marker border.  Row zero is the marked tag top
(board-local +Y before tag yaw), and columns run from marked left to right.
``0`` is black and ``1`` is white.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json


_RELEASED_36H11_ROWS: tuple[tuple[int, tuple[str, ...]], ...] = (
    (0, ("00000000", "00010000", "00110100", "00001010", "00001100", "01011100", "01010110", "00000000")),
    (1, ("00000000", "01001000", "01011010", "00001100", "00011110", "01110100", "00110110", "00000000")),
    (2, ("00000000", "00111000", "00010000", "01001000", "00000010", "00100100", "01110110", "00000000")),
    (3, ("00000000", "00001100", "00100110", "01001010", "01110010", "01110000", "01001110", "00000000")),
    (4, ("00000000", "00100010", "00000010", "00101000", "01111010", "00011110", "00101110", "00000000")),
    (5, ("00000000", "00011010", "00111000", "01101010", "00110110", "01000110", "00011110", "00000000")),
)


@dataclass(frozen=True, slots=True)
class AprilTagPatternCodebook:
    """Immutable explicit bit grid; neutral between renderer and detector."""

    family: str
    patterns: tuple[tuple[int, tuple[tuple[int, ...], ...]], ...]
    marked_corner_order: str = "TL_TR_BR_BL"
    marked_top_direction: str = "+LOCAL_Y"

    def __post_init__(self) -> None:
        if self.family != "tag36h11":
            raise ValueError("Only the released tag36h11 family is supported")
        parsed: list[tuple[int, tuple[tuple[int, ...], ...]]] = []
        seen: set[int] = set()
        for tag_id, raw_grid in tuple(self.patterns):
            if isinstance(tag_id, bool) or not isinstance(tag_id, int) or tag_id < 0:
                raise ValueError("AprilTag ids must be non-negative integers")
            if tag_id in seen:
                raise ValueError("AprilTag codebook ids must be unique")
            seen.add(tag_id)
            grid = tuple(tuple(row) for row in raw_grid)
            if len(grid) != 8 or any(len(row) != 8 for row in grid):
                raise ValueError("Released AprilTag patterns must be 8x8 grids")
            if any(bit not in (0, 1) for row in grid for bit in row):
                raise ValueError("AprilTag pattern cells must be zero or one")
            if any(grid[edge][index] != 0 for edge in (0, 7) for index in range(8)) or any(
                grid[index][edge] != 0 for edge in (0, 7) for index in range(8)
            ):
                raise ValueError("Released AprilTag patterns require a black border")
            parsed.append((tag_id, grid))
        if not parsed:
            raise ValueError("AprilTag codebook cannot be empty")
        if self.marked_corner_order != "TL_TR_BR_BL":
            raise ValueError("AprilTag marked corner order must be TL_TR_BR_BL")
        if self.marked_top_direction != "+LOCAL_Y":
            raise ValueError("AprilTag marked top must be +LOCAL_Y")
        object.__setattr__(self, "patterns", tuple(sorted(parsed)))

    @property
    def tag_ids(self) -> tuple[int, ...]:
        return tuple(tag_id for tag_id, _ in self.patterns)

    def pattern(self, tag_id: int) -> tuple[tuple[int, ...], ...]:
        if isinstance(tag_id, bool) or not isinstance(tag_id, int):
            raise TypeError("tag_id must be an integer")
        for candidate_id, grid in self.patterns:
            if candidate_id == tag_id:
                return grid
        raise KeyError(f"tag36h11 id {tag_id} is not in the released codebook")

    @property
    def codewords(self) -> tuple[tuple[int, int], ...]:
        """Return row-major 64-bit words where bit one denotes a white cell."""

        return tuple(
            (
                tag_id,
                sum(
                    bit << (63 - (row_index * 8 + column_index))
                    for row_index, row in enumerate(grid)
                    for column_index, bit in enumerate(row)
                ),
            )
            for tag_id, grid in self.patterns
        )

    @property
    def codebook_sha256(self) -> str:
        payload = json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "rocell.apriltag_pattern_codebook.v1",
            "family": self.family,
            "grid_size": 8,
            "black_bit": 0,
            "white_bit": 1,
            "marked_corner_order": self.marked_corner_order,
            "marked_top_direction": self.marked_top_direction,
            "patterns": [
                {
                    "tag_id": tag_id,
                    "rows": [list(row) for row in grid],
                }
                for tag_id, grid in self.patterns
            ],
        }


DEFAULT_APRILTAG_36H11_CODEBOOK = AprilTagPatternCodebook(
    family="tag36h11",
    patterns=tuple(
        (
            tag_id,
            tuple(tuple(int(cell) for cell in row) for row in rows),
        )
        for tag_id, rows in _RELEASED_36H11_ROWS
    ),
)


__all__ = [
    "AprilTagPatternCodebook",
    "DEFAULT_APRILTAG_36H11_CODEBOOK",
]
