"""Explicit text normalization and unsupported-character reporting."""

from __future__ import annotations


class UnsupportedCharacterError(ValueError):
    def __init__(self, character: str, index: int, profile_id: str) -> None:
        self.character = character
        self.index = index
        self.profile_id = profile_id
        display = character.encode("unicode_escape").decode("ascii")
        super().__init__(
            f"Character {display!r} at normalized index {index} is unsupported "
            f"by profile {profile_id!r}"
        )


def normalize_line_endings(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return text.replace("\r\n", "\n").replace("\r", "\n")
