"""Frozen semantic profiles used by the hardware-free development workflow.

These profiles answer only one question: which named key or screen target
represents each supported character?  They intentionally contain no geometry,
robot poses, or controller values.  Geometry is supplied by a separately
versioned target catalog, and the catalog must explicitly bind back to these
profile IDs before a geometric simulation can run.
"""

from __future__ import annotations

import string

from rocell.models.actions import ActionPlan
from rocell.models.profiles import KeyboardProfile, PhoneKeySpec, PhoneProfile

from .keyboard_compiler import KeyboardCompiler
from .phone_compiler import PhoneCompiler


KEYBOARD_SEMANTIC_PROFILE_ID = "development/keyboard-us-lowercase-semantic-v1"
PHONE_SEMANTIC_PROFILE_ID = "development/phone-lowercase-semantic-v1"


def development_keyboard_profile() -> KeyboardProfile:
    """Build the supported lowercase US-keyboard semantic mapping.

    Lowercase text maps to the corresponding physical letter key.  Shifted
    characters are intentionally absent until modifier sequencing is modeled.
    """

    character_keys: dict[str, tuple[str, ...]] = {
        character: (character.upper(),) for character in string.ascii_lowercase
    }
    character_keys.update({character: (character,) for character in string.digits})
    character_keys.update(
        {
            " ": ("SPACE",),
            "\n": ("ENTER",),
            "\t": ("TAB",),
            ".": ("PERIOD",),
            ",": ("COMMA",),
            "-": ("MINUS",),
            "=": ("EQUAL",),
            "/": ("SLASH",),
            ";": ("SEMICOLON",),
            "'": ("APOSTROPHE",),
        }
    )
    return KeyboardProfile(
        profile_id=KEYBOARD_SEMANTIC_PROFILE_ID,
        character_keys=character_keys,
    )


def development_phone_profile() -> PhoneProfile:
    """Build the supported lowercase Gboard-like semantic mapping.

    The initial and required UI state are explicit so a future visual observer
    can reject a stale or changed Android keyboard before any tap is planned.
    """

    targets: dict[str, PhoneKeySpec] = {
        character: PhoneKeySpec(
            target_id=f"key_{character}",
            required_state="KEYBOARD_LOWER",
        )
        for character in string.ascii_lowercase
    }
    targets.update(
        {
            " ": PhoneKeySpec("key_space", "KEYBOARD_LOWER"),
            ".": PhoneKeySpec("key_period", "KEYBOARD_LOWER"),
            "\n": PhoneKeySpec("key_enter", "KEYBOARD_LOWER", verify_after=True),
        }
    )
    return PhoneProfile(
        profile_id=PHONE_SEMANTIC_PROFILE_ID,
        character_targets=targets,
        initial_state="KEYBOARD_LOWER",
    )


def compile_development_text(device: str, text: str) -> ActionPlan:
    """Compile text for one supported device without resolving coordinates."""

    if device == "keyboard":
        return KeyboardCompiler().compile(text, development_keyboard_profile())
    if device == "phone":
        return PhoneCompiler().compile(text, development_phone_profile())
    raise ValueError(f"Unsupported device {device!r}")

