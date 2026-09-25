"""Load the explicitly static target catalog without changing legacy geometry.

This file-only loader joins static semantic IDs/hashes to every existing nominal
target. It is one input to the future static bundle/context, not a shortcut into
the legacy task route or a source of installed calibration/robot commands.
"""

from copy import deepcopy
import hashlib
import json
from pathlib import Path

from rocell.typing.static_development_profiles import (
    static_development_keyboard_profile,
    static_development_phone_profile,
    static_semantic_profile_binding,
)
from .nominal import NominalTargetCatalog, TargetMapError, load_nominal_target_catalog


STATIC_NOMINAL_TARGET_PATH = "software/config/static_nominal_target_profiles.json"
GEOMETRY_SOURCE_PATH = "software/config/nominal_target_profiles.json"
GEOMETRY_SOURCE_SHA256 = (
    "6779213e832ab27eeda1e7fb245f57ff8cb0d56707b5aa73a8f31ec483a620f2"
)
MAX_CATALOG_BYTES = 128 * 1024


def _read(root: Path, relative: str) -> bytes:
    candidate = root / relative
    resolved = candidate.resolve(strict=True)
    if resolved != candidate or not resolved.is_relative_to(root):
        raise TargetMapError("Static catalog path is redirected or outside workspace")
    with resolved.open("rb") as stream:
        payload = stream.read(MAX_CATALOG_BYTES + 1)
    if not payload or len(payload) > MAX_CATALOG_BYTES:
        raise TargetMapError("Static catalog exceeds its byte bound")
    return payload


def _unique_object(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise TargetMapError("Duplicate static catalog field")
        result[name] = value
    return result


def _document(payload: bytes) -> dict:
    def invalid_constant(value):
        raise TargetMapError("Static catalog contains non-finite JSON")

    value = json.loads(
        payload.decode("utf-8"),
        object_pairs_hook=_unique_object,
        parse_constant=invalid_constant,
    )
    if type(value) is not dict:
        raise TargetMapError("Static catalog must be an object")
    return value


def _canonical(value) -> bytes:
    # Canonical comparison rejects Boolean/integer substitutions as well as
    # extra/missing fields. Geometry is copied exactly, not rounded or rescaled.
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def load_static_nominal_target_catalog(workspace: Path) -> NominalTargetCatalog:
    """Join exact sources, reject mixed semantic identities and recheck reads.

    The legacy seed supplies *only* unchanged nominal target geometry. Loading
    it is not loading/patching a legacy simulation context or inheriting its
    camera calibration. A separate static bundle must bind this catalog's bytes
    together with the camera, graph, scenario, URDF and build inputs.
    """
    root = Path(workspace).resolve(strict=True)
    baseline = _read(root, GEOMETRY_SOURCE_PATH)
    if hashlib.sha256(baseline).hexdigest() != GEOMETRY_SOURCE_SHA256:
        raise TargetMapError("Static nominal geometry source changed")
    selected = _read(root, STATIC_NOMINAL_TARGET_PATH)
    expected = deepcopy(_document(baseline))
    bindings = {
        "keyboard": static_semantic_profile_binding(
            static_development_keyboard_profile()
        ),
        "phone": static_semantic_profile_binding(static_development_phone_profile()),
    }
    for device, binding in bindings.items():
        row = expected[device]
        row["profile_id"] += "-static-v1"
        row["semantic_profile_id"] = binding["profile_id"]
        row["semantic_profile_sha256"] = binding["semantic_content_sha256"]
    expected["static_binding"] = dict(
        schema="rocell.static_nominal_target_binding.v1",
        geometry_source=dict(
            path=GEOMETRY_SOURCE_PATH,
            sha256=GEOMETRY_SOURCE_SHA256,
            meaning="UNCHANGED_SYNTHETIC_TARGET_GEOMETRY_NOT_INSTALLED_MEASUREMENTS",
        ),
        semantic_profiles=bindings,
        physical_authority=False,
    )
    if _canonical(_document(selected)) != _canonical(expected):
        raise TargetMapError("Static target geometry/semantic/graph binding differs")
    # Reuse the numerical parser and its workcell-origin/dimensions/target checks.
    # It reads the new, explicit catalog rather than relabeling an old object.
    catalog = load_nominal_target_catalog(root, root / STATIC_NOMINAL_TARGET_PATH)
    if catalog.content_sha256 != hashlib.sha256(selected).hexdigest():
        raise TargetMapError("Static catalog changed during numerical parsing")
    if (
        _read(root, GEOMETRY_SOURCE_PATH) != baseline
        or _read(root, STATIC_NOMINAL_TARGET_PATH) != selected
    ):
        raise TargetMapError("Static target sources changed while loading")
    return catalog
