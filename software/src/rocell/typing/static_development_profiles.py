"""Explicit static-overhead semantic profiles; no geometry or device effects.

This is the semantic edge of the S1 migration, not a migrated simulation context.
The separately versioned static bundle must bind the profile content AND graph
hash returned here. Historical factories/defaults and target catalogs remain
unchanged; a static profile must never be relabeled as a legacy profile to get
past their alignment checks.
"""

from __future__ import annotations

import hashlib
import json

from rocell.calibration.static_phase1_requirements import STATIC_OVERHEAD_PHASE1_GRAPH
from rocell.models.actions import ActionPlan
from rocell.models.profiles import KeyboardProfile, PhoneProfile

from .development_profiles import (
    development_keyboard_profile,
    development_phone_profile,
)
from .keyboard_compiler import KeyboardCompiler
from .phone_compiler import PhoneCompiler


STATIC_KEYBOARD_SEMANTIC_PROFILE_ID = (
    "development/static-overhead-b0477-keyboard-semantic-v1"
)
STATIC_PHONE_SEMANTIC_PROFILE_ID = "development/static-overhead-b0477-phone-semantic-v1"
STATIC_SEMANTIC_BINDING_SCHEMA = "rocell.static_development_semantic_binding.v1"


def static_development_keyboard_profile() -> KeyboardProfile:
    """Reuse exact supported key behavior with an explicit static dependency set."""
    legacy = development_keyboard_profile()
    return KeyboardProfile(
        profile_id=STATIC_KEYBOARD_SEMANTIC_PROFILE_ID,
        character_keys=legacy.character_keys,
        required_calibrations=STATIC_OVERHEAD_PHASE1_GRAPH.device_closure("keyboard"),
    )


def static_development_phone_profile() -> PhoneProfile:
    """Preserve Gboard state/verification semantics; change only identity/closure."""
    legacy = development_phone_profile()
    return PhoneProfile(
        profile_id=STATIC_PHONE_SEMANTIC_PROFILE_ID,
        character_targets=legacy.character_targets,
        initial_state=legacy.initial_state,
        required_calibrations=STATIC_OVERHEAD_PHASE1_GRAPH.device_closure("phone"),
    )


def static_semantic_profile_binding(profile: KeyboardProfile | PhoneProfile) -> dict:
    """Validate the exact named profile and return detached, zero-authority data.

    Dependencies participate in semantic_content_sha256; graph purpose/context
    edges also participate in graph_sha256. A future bundle must pin both, so
    changing graph semantics without changing terminal IDs still invalidates it.
    This function validates semantic data only, never a caller's physical state.
    """
    expected: KeyboardProfile | PhoneProfile
    if type(profile) is KeyboardProfile:
        device, expected = "keyboard", static_development_keyboard_profile()
    elif type(profile) is PhoneProfile:
        device, expected = "phone", static_development_phone_profile()
    else:
        raise TypeError("An exact KeyboardProfile or PhoneProfile is required")
    if profile != expected:
        raise ValueError("Profile differs from the explicit static semantic contract")
    graph = STATIC_OVERHEAD_PHASE1_GRAPH.to_dict()
    core = dict(
        schema=STATIC_SEMANTIC_BINDING_SCHEMA,
        device=device,
        profile_id=profile.profile_id,
        semantic_content_sha256=profile.semantic_content_sha256,
        required_calibrations=list(profile.required_calibrations),
        graph_id=graph["graph_id"],
        graph_sha256=STATIC_OVERHEAD_PHASE1_GRAPH.graph_hash,
        architecture=graph["architecture"],
        camera_catalog_configuration=graph["camera_catalog_configuration"],
        geometry_bound=False,
        installed_calibration_bound=False,
        physical_authority=False,
        hardware_commands_generated=0,
    )
    encoded = json.dumps(
        core, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return {**core, "binding_sha256": hashlib.sha256(encoded).hexdigest()}


def compile_static_development_text(device: str, text: str) -> ActionPlan:
    """Compile only named static targets; callers cannot inject a legacy profile.

    The result contains no positions/controller values and cannot be sent to an
    arm. Keep it out of the default task route until the static target catalog,
    source lock, context and geometric simulator are integrated and verified.
    """
    if device == "keyboard":
        return KeyboardCompiler().compile(text, static_development_keyboard_profile())
    if device == "phone":
        return PhoneCompiler().compile(text, static_development_phone_profile())
    raise ValueError(f"Unsupported static development device {device!r}")
