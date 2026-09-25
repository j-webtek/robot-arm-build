"""NC-01 retained gap report: actual source audits and zero-authority arithmetic.

Collection reads locked files and runs the existing readiness/calculator APIs.
Verification reconstructs retained typed inputs and checks structural coverage,
freshness and integer equations; it never reruns collection, IK or a device.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

from rocell.calibration.accuracy_budget import (
    AccuracyAssessmentContext,
    AccuracyBudgetDisposition,
    AccuracyBudgetObservation,
    AccuracyBudgetTermDefinition,
    AccuracyDependencyHash,
    AccuracyEvidenceProvenance,
    AccuracyEvidenceState,
    AccuracyTermEvidenceBinding,
    TargetAccuracyBudgetPolicy,
    TargetBudgetAssessment,
    TargetGeometryEvidence,
    assess_target_accuracy_budget,
    load_target_accuracy_budget_policy,
    _assessment_input_manifest_sha256,
)
from rocell.geometry import Point3Mm, parse_urdf
from rocell.simulation.collision import (
    audit_collision_geometry,
    build_roarm_m3_prehardware_collision_contract,
)
from rocell.simulation.scene import (
    AabbMm,
    NominalCalibrationTarget,
    NominalDevice,
    NominalWorkcellScene,
    PlanarFiducial,
)
from rocell.simulation.static_route_collision import (
    STATIC_ROUTE_BODY_REQUIREMENTS,
    REQUIRED_STATIC_ROUTE_SOURCE_KEYS,
)
from .collision_readiness import (
    CurrentCollisionReadinessReport,
    assess_current_collision_readiness,
)
from .context import load_simulation_context, revalidate_simulation_context
from .physical_onboarding import PhysicalOnboardingStage
from .rehearsal_noncontact_binding import (
    RehearsalNoncontactBinding,
    SOURCE_SCHEMA,
    MAX_SOURCE_CONTEXT_BYTES,
    canonical,
    digest,
)
from .rehearsal_reference_stage import read_reference_source_context

SCHEMA = "rocell.rehearsal_noncontact_stage.v1"
MAX_EVIDENCE_BYTES = 112 * 1024
_STAGE = "noncontact_acceptance"
_MEANING = "Retained noncontact gap diagnostic only. No power, movement or contact is authorized."
_DEPENDENCIES = (
    "application/rehearsal_noncontact_binding.py",
    "application/collision_readiness.py",
    "application/context.py",
    "calibration/accuracy_budget.py",
    "simulation/collision.py",
    "simulation/scene.py",
    "simulation/static_route_collision.py",
)
_NOT_EVALUATED = [
    "POSE",
    "ROUTE",
    "SENSITIVITY",
    "VISIBILITY",
    "DYNAMICS",
    "PHYSICAL_MOTION",
]
_CASES = (
    "real_unmeasured",
    "missing_term",
    "stale_term",
    "domain_term",
    "target_margin",
    "finite_control",
)
_PROVENANCE = {
    "source_domain": "NOMINAL_SOURCE_GEOMETRY",
    "historical_collision_scope": "HISTORICAL_EYE_ON_ARM",
    "accuracy_controls": "SYNTHETIC_REHEARSAL_NOT_PHYSICAL_MEASUREMENTS",
    "target_geometry": "SYNTHETIC_ARITHMETIC_BOUNDARY_NOT_KEYBOARD_OR_PHONE_CERTIFICATE",
    "camera_role": "DEPENDENCY_ONLY_NOT_NUMERIC_INPUT",
    "feedback_role": "TRANSPORT_ONLY_NOT_CALIBRATED_JOINT_INPUT",
    "final_power_dependency": "PREDECESSOR_SYNTHETIC_OBSERVATION_NOT_CURRENT_POWER_KNOWLEDGE",
}
_EFFECTS = {
    key: 0
    for key in (
        "device_enumerations",
        "device_opens",
        "camera_frames",
        "serial_writes",
        "hardware_commands",
        "power_changes",
        "robot_motions",
        "contacts",
        "physical_receipt_publications",
        "permit_publications",
    )
}


class RehearsalNoncontactError(ValueError):
    """A bounded source, retained input or calculation is inconsistent."""


def _same(actual: object, expected: object, label: str) -> None:
    equal = (
        actual == expected
        if type(actual) is bytes and type(expected) is bytes
        else canonical(actual) == canonical(expected)
    )
    if not equal:
        raise RehearsalNoncontactError(f"Noncontact {label} differs")


def _tree(value: object, depth: int = 0) -> None:
    if depth > 16:
        raise RehearsalNoncontactError("Noncontact nesting limit")
    if value is None or type(value) is bool:
        return
    if type(value) is str:
        if len(value.encode("utf-8")) > 16384:
            raise RehearsalNoncontactError("Noncontact string limit")
    elif type(value) in (int, float):
        if not math.isfinite(value) or abs(value) > 10**15:  # type: ignore[arg-type]
            raise RehearsalNoncontactError("Noncontact numeric limit")
    elif type(value) is list:
        if len(value) > 128:
            raise RehearsalNoncontactError("Noncontact list limit")
        for item in value:
            _tree(item, depth + 1)
    elif type(value) is dict:
        if len(value) > 128 or any(
            type(key) is not str or len(key) > 128 for key in value
        ):
            raise RehearsalNoncontactError("Noncontact object limit")
        for item in value.values():
            _tree(item, depth + 1)
    else:
        raise RehearsalNoncontactError("Noncontact plain JSON required")


def _encode(value: object) -> bytes:
    _tree(value)
    payload = canonical(value)
    if len(payload) > MAX_EVIDENCE_BYTES:
        raise RehearsalNoncontactError("Complete noncontact evidence exceeds its bound")
    return payload


def _decode(payload: bytes) -> dict[str, Any]:
    if type(payload) is not bytes or not 0 < len(payload) <= MAX_EVIDENCE_BYTES:
        raise RehearsalNoncontactError("Bounded immutable evidence bytes are required")
    try:
        value = json.loads(payload)
        if type(value) is not dict or _encode(value) != payload:
            raise RehearsalNoncontactError(
                "Exact canonical noncontact JSON is required"
            )
        return value
    except (ValueError, UnicodeError, TypeError, RecursionError) as error:
        raise RehearsalNoncontactError(
            "Invalid noncontact evidence encoding"
        ) from error


def _plain(value: object) -> Any:
    """Detach dataclass tuples/string enums into the exact JSON wire domain."""
    return json.loads(canonical(value))


def _read(path: Path, maximum: int) -> bytes:
    with path.open("rb") as stream:
        payload = stream.read(maximum + 1)
    if not payload or len(payload) > maximum:
        raise RehearsalNoncontactError("A fixed source exceeds its byte limit")
    return payload


def read_noncontact_source_context(workspace: Path) -> bytes:
    """Explicit source reads only: no collision evaluator, arithmetic campaign or IK."""
    root = Path(workspace).resolve()
    context = load_simulation_context(
        root, root / "software/config/system_manifest.json"
    )
    reference = read_reference_source_context(root)
    policy = load_target_accuracy_budget_policy(root)
    raw_policy = _read(policy.source_path, 16384)
    if hashlib.sha256(raw_policy).hexdigest() != policy.source_sha256:
        raise RehearsalNoncontactError("Accuracy policy changed during source capture")
    result = {
        "schema": SOURCE_SCHEMA,
        "reference_source_context_sha256": hashlib.sha256(
            canonical(reference)
        ).hexdigest(),
        "historical_context": {
            "manifest_id": context.snapshot.manifest_id,
            "manifest_sha256": context.snapshot.manifest_sha256,
            "build_snapshot_hash": context.snapshot.snapshot_hash,
            "design_revision": context.snapshot.design_revision,
            "active_build_id": context.snapshot.active_build_id,
            "snapshot_safe_to_power_robot": context.snapshot.safe_to_power_robot,
            "snapshot_contact_enabled": context.snapshot.contact_enabled,
            "bundle_id": context.bundle_lock.bundle_id,
            "bundle_lock_sha256": context.bundle_lock.source_lock_sha256,
            "bundle_artifact_hashes": {
                key: item.sha256 for key, item in context.bundle_lock.artifacts.items()
            },
            "alignment_status": context.alignment.status,
            "alignment_report_hash": context.alignment.report_hash,
            "urdf_relative_path": context.scenario.model_path.relative_to(
                root
            ).as_posix(),
        },
        "scene": context.scene.to_dict(),
        "accuracy_policy_utf8": raw_policy.decode("utf-8"),
        "accuracy_policy_sha256": policy.source_sha256,
        "dependency_source_sha256s": {
            name: hashlib.sha256(
                _read(root / "software/src/rocell" / name, 256 * 1024)
            ).hexdigest()
            for name in _DEPENDENCIES
        },
    }
    revalidate_simulation_context(context)
    _same(read_reference_source_context(root), reference, "source context after read")
    if _read(policy.source_path, 16384) != raw_policy:
        raise RehearsalNoncontactError("Accuracy policy changed after source capture")
    payload = _encode(result)
    if len(payload) > MAX_SOURCE_CONTEXT_BYTES:
        raise RehearsalNoncontactError(
            "Complete NC-01 source snapshot exceeds its bound"
        )
    return payload


def _scene(document: dict[str, Any]) -> NominalWorkcellScene:
    def box(item: dict[str, Any]) -> AabbMm:
        return AabbMm.from_bounds(
            item["obstacle_id"],
            item["frame"],
            tuple(item["minimum_mm"]),
            tuple(item["maximum_mm"]),
            kind=item["kind"],
            source=item["source"],
            conservative_proxy=item["conservative_proxy"],
        )

    target = document["tcp_calibration_target"]
    result = NominalWorkcellScene(
        design_revision=document["design_revision"],
        board_frame=document["board_frame"],
        board=box(document["board"]),
        devices={
            name: NominalDevice(
                item["device_id"],
                box(item["envelope"]),
                item["interaction_plane_z_mm"],
                item["interaction_plane_state"],
            )
            for name, item in document["devices"].items()
        },
        tcp_calibration_target=NominalCalibrationTarget(
            target["target_id"],
            Point3Mm(target["frame"], *target["center_mm"]),
            target["replaceable_part"],
        ),
        obstacles=tuple(box(item) for item in document["obstacles"]),
        fiducials=tuple(
            PlanarFiducial(
                item["name"],
                item["tag_id"],
                item["family"],
                item["role"],
                Point3Mm(document["board_frame"], *item["center_board_mm"]),
                item["detection_edge_mm"],
                item["tile_edge_mm"],
                item["yaw_rad"],
                item["coordinate_source"],
            )
            for item in document["fiducials"]
        ),
        source_hashes=document["source_hashes"],
        assumptions=tuple(document["assumptions"]),
        arm_clamp_rear_edge_x_range_mm=tuple(
            document["arm_clamp_rear_edge_x_range_mm"]
        ),
    )
    _same(result.to_dict(), document, "retained scene structure")
    return result


def _historical(binding: RehearsalNoncontactBinding) -> CurrentCollisionReadinessReport:
    """Pure reconstruction of the coverage audit, not a pose/collision query."""
    source = binding.source_context
    data = dict(source["historical_context"])
    geometry = binding.reference_binding.source_context["nominal_geometry"]
    raw = geometry["urdf_xml"].encode("utf-8")
    if (
        hashlib.sha256(raw).hexdigest() != geometry["urdf_sha256"]
        or len(raw) != geometry["urdf_bytes"]
    ):
        raise RehearsalNoncontactError("Retained pinned URDF hash/size mismatch")
    model = parse_urdf(raw.decode("utf-8"), source_name="retained-noncontact-urdf")
    xml = ET.fromstring(raw)
    local = lambda node: node.tag.rsplit("}", 1)[-1]
    total = sum(local(node) == "collision" for node in xml.iter())
    direct = []
    for link in xml:
        if local(link) == "link":
            direct.extend(
                [link.attrib.get("name", "").strip() or "__UNNAMED_LINK__"]
                * sum(local(child) == "collision" for child in link)
            )
    scene = _scene(source["scene"])
    contract = build_roarm_m3_prehardware_collision_contract(model, scene)
    data["bundle_artifact_hashes"] = tuple(
        sorted(data["bundle_artifact_hashes"].items())
    )
    return CurrentCollisionReadinessReport(
        **data,
        urdf_sha256=geometry["urdf_sha256"],
        urdf_byte_count=len(raw),
        urdf_collision_element_count=total,
        urdf_collision_link_names=tuple(sorted(direct)),
        urdf_collision_elements_outside_links=total - len(direct),
        scene_source_hashes=tuple(sorted(scene.source_hashes.items())),
        contract=contract,
        geometry_audit=audit_collision_geometry(contract),
    )


def _policy(binding: RehearsalNoncontactBinding) -> TargetAccuracyBudgetPolicy:
    source = binding.source_context
    raw = source["accuracy_policy_utf8"].encode("utf-8")
    _same(
        hashlib.sha256(raw).hexdigest(), source["accuracy_policy_sha256"], "policy hash"
    )
    policy = json.loads(raw)
    # Its complete bytes are independently pinned in expected_binding by the
    # explicit strict loader. The typed constructor rechecks term/owner/metadata
    # membership here without inventing a second policy-file parser.
    return TargetAccuracyBudgetPolicy(
        source_path=Path(__file__).absolute(),
        source_sha256=source["accuracy_policy_sha256"],
        policy_id=policy["policy_id"],
        terms=tuple(
            AccuracyBudgetTermDefinition(
                item["id"],
                PhysicalOnboardingStage(item["owner_stage"]),
                tuple(item["required_metadata"]),
            )
            for item in policy["noncontact_terms"]
        ),
        contact_addendum_terms=tuple(policy["contact_addendum_terms"]),
        open_blockers=tuple(policy["open_blockers"]),
    )


def _static_inventory(binding: RehearsalNoncontactBinding) -> dict[str, Any]:
    hashes = binding.reference_binding.source_context["static_phase1_context_hashes"]
    mappings = {
        "robot_model": "kinematic_model",
        "workcell_layout": "workcell_layout",
        "target_profile": "target_catalog",
        "static_support_design": "static_camera_support",
    }
    return {
        "schema": "rocell.noncontact_static_inventory.v1",
        "status": "NOT_EVALUATED",
        "requirements": [item.to_dict() for item in STATIC_ROUTE_BODY_REQUIREMENTS],
        "source_inventory": [
            {
                "source_key": key,
                "source_sha256": hashes[mappings[key]] if key in mappings else None,
                "state": (
                    "SOURCE_DESIGN_ONLY_NOT_INSTALLED_GEOMETRY"
                    if key in mappings
                    else "MISSING_REVIEWED_GEOMETRY_SOURCE"
                ),
            }
            for key in sorted(REQUIRED_STATIC_ROUTE_SOURCE_KEYS)
        ],
        "geometry": [
            {
                "body_id": item.body_id,
                "state": "MISSING_INSTALLED_GEOMETRY",
                "primitives": [],
            }
            for item in STATIC_ROUTE_BODY_REQUIREMENTS
        ],
        "pose_evaluation": "NOT_EVALUATED",
        "sweep_evaluation": "NOT_EVALUATED",
        "physical_authority": False,
        "meaning": "Source designs and body names do not supply complete installed envelopes. No guessed boxes or historical-proxy substitution.",
    }


def _accuracy_inputs(
    binding: RehearsalNoncontactBinding, policy: TargetAccuracyBudgetPolicy
) -> dict[str, Any]:
    def named(label: str) -> str:
        return hashlib.sha256(
            canonical(
                {
                    "schema": "rocell.noncontact_synthetic_input.v1",
                    "binding_sha256": binding.binding_sha256,
                    "label": label,
                }
            )
        ).hexdigest()

    epoch, clock = named("synthetic_epoch"), named("synthetic_clock")
    domain, epoch_id = "SYNTHETIC_REHEARSAL_ARITHMETIC_ONLY", "synthetic_nc01_epoch"
    context = AccuracyAssessmentContext(
        2000,
        domain,
        epoch_id,
        epoch,
        clock,
        (
            AccuracyDependencyHash("assessment_clock", clock),
            AccuracyDependencyHash("configuration_epoch", epoch),
        ),
    )
    geometry_digest = named("synthetic_geometry_5000_500_500_um")
    geometry = TargetGeometryEvidence(
        "synthetic_arithmetic_target",
        "board_target_plane",
        domain,
        epoch_id,
        epoch,
        "CERTIFIED_TARGET_CENTERED_SAFE_POLYGON_INRADIUS",
        "CERTIFIED_TOOL_FOOTPRINT_CIRCUMRADIUS",
        5000,
        500,
        500,
        geometry_digest,
        (
            AccuracyDependencyHash("configuration_epoch", epoch),
            AccuracyDependencyHash("target_geometry_bundle", geometry_digest),
        ),
        1000,
        3000,
    )
    bindings = []
    observations = []
    for term in policy.terms:
        evidence_digest = named("synthetic_term_" + term.term_id)
        dependencies = (
            AccuracyDependencyHash("configuration_epoch", epoch),
            AccuracyDependencyHash("term_evidence", evidence_digest),
        )
        selected = AccuracyTermEvidenceBinding(
            term.term_id,
            "board_target_plane",
            domain,
            epoch_id,
            epoch,
            "SYNTHETIC_FINITE_CONTROL_NO_RECEIVED_SAMPLES",
            "SYNTHETIC_CONSERVATIVE_BOUND",
            "SYNTHETIC_ARITHMETIC_DOMAIN_ONLY",
            evidence_digest,
            dependencies,
        )
        provenance = AccuracyEvidenceProvenance(
            selected.frame,
            selected.operating_domain,
            selected.sample_basis,
            selected.bound_method,
            selected.coverage,
            dependencies,
            1000,
            3000,
        )
        bindings.append(asdict(selected))
        observations.append(
            asdict(
                AccuracyBudgetObservation(
                    term.term_id,
                    AccuracyEvidenceState.MEASURED_IN_DOMAIN,
                    100,
                    evidence_digest,
                    provenance,
                )
            )
        )
    return _plain(
        {
            "schema": "rocell.noncontact_accuracy_common.v1",
            "origin": "SYNTHETIC_REHEARSAL_NOT_PHYSICAL_MEASUREMENTS",
            "assessment_context": asdict(context),
            "target_geometry": asdict(geometry),
            "term_bindings": bindings,
            "observations": observations,
        }
    )


def _case_deltas(common: dict[str, Any]) -> list[dict[str, Any]]:
    first = common["observations"][0]
    stale, domain = _plain(first), _plain(first)
    stale["provenance"]["valid_until_unix_ns"] = 1999
    domain["provenance"]["operating_domain"] = "OTHER_SYNTHETIC_DOMAIN"
    geometry = _plain(common["target_geometry"])
    geometry["target_safe_radius_micrometers"] = 500
    geometry_hash = hashlib.sha256(
        canonical(
            {
                "synthetic_target_radius_um": 500,
                "original_geometry_sha256": geometry["evidence_sha256"],
            }
        )
    ).hexdigest()
    geometry["evidence_sha256"] = geometry_hash
    geometry["dependency_hashes"][1]["sha256"] = geometry_hash
    changes: tuple[
        tuple[list[dict[str, Any]], list[Any] | None, dict[str, Any] | None, list[str]],
        ...,
    ] = (
        (
            [
                {
                    "term_id": item["term_id"],
                    "evidence_state": "UNMEASURED",
                    "bound_micrometers": None,
                    "evidence_sha256": None,
                    "provenance": None,
                }
                for item in common["observations"]
            ],
            [],
            None,
            [],
        ),
        ([], None, None, [first["term_id"]]),
        ([stale], None, None, []),
        ([domain], None, None, []),
        ([], None, geometry, []),
        ([], None, None, []),
    )
    # Fixed term-keyed complete replacements/omissions plus common inputs retain
    # every original argument without repeating the nine unchanged observations.
    # Null target/bindings means the exact common input, not an unknown input.
    return [
        {
            "case_id": name,
            "observation_replacements": obs,
            "omitted_term_ids": omitted,
            "term_bindings": bindings,
            "target_geometry": target,
        }
        for name, (obs, bindings, target, omitted) in zip(_CASES, changes)
    ]


def _typed_case(common: dict[str, Any], case: dict[str, Any]) -> tuple[
    AccuracyAssessmentContext,
    TargetGeometryEvidence,
    tuple[AccuracyTermEvidenceBinding, ...],
    tuple[AccuracyBudgetObservation, ...],
]:
    def deps(items: list[dict[str, Any]]) -> tuple[AccuracyDependencyHash, ...]:
        return tuple(AccuracyDependencyHash(**item) for item in items)

    def with_deps(item: dict[str, Any]) -> dict[str, Any]:
        return {**item, "dependency_hashes": deps(item["dependency_hashes"])}

    context = AccuracyAssessmentContext(**with_deps(common["assessment_context"]))
    target = TargetGeometryEvidence(
        **with_deps(
            case["target_geometry"]
            if case["target_geometry"] is not None
            else common["target_geometry"]
        )
    )
    selected = (
        case["term_bindings"]
        if case["term_bindings"] is not None
        else common["term_bindings"]
    )
    bindings = tuple(
        AccuracyTermEvidenceBinding(**with_deps(item)) for item in selected
    )
    replacements = {item["term_id"]: item for item in case["observation_replacements"]}
    raw_observations = [
        replacements.get(item["term_id"], item)
        for item in common["observations"]
        if item["term_id"] not in case["omitted_term_ids"]
    ]
    observations = tuple(
        AccuracyBudgetObservation(
            **{
                **item,
                "evidence_state": AccuracyEvidenceState(item["evidence_state"]),
                "provenance": (
                    None
                    if item["provenance"] is None
                    else AccuracyEvidenceProvenance(**with_deps(item["provenance"]))
                ),
            }
        )
        for item in raw_observations
    )
    return context, target, bindings, observations


def _arithmetic_verification(
    policy: TargetAccuracyBudgetPolicy,
    common: dict[str, Any],
    case: dict[str, Any],
    result: dict[str, Any],
) -> None:
    """Independent scalar/freshness proof; deliberately does not call assessor."""
    context, target, bindings, observations = _typed_case(common, case)
    observed = {item.term_id: item for item in observations}
    selected = {item.term_id: item for item in bindings}
    expected_terms = tuple(item.term_id for item in policy.terms)
    blocked = []
    expiries = [target.valid_until_unix_ns]
    total = 0
    for term in expected_terms:
        item, bound = observed.get(term), selected.get(term)
        p = item.provenance if item else None
        good = (
            item is not None
            and bound is not None
            and p is not None
            and item.evidence_state is AccuracyEvidenceState.MEASURED_IN_DOMAIN
        )
        if good:
            assert item is not None and bound is not None and p is not None
            good = (
                p.frame == bound.frame == target.frame
                and p.operating_domain
                == bound.operating_domain
                == context.operating_domain
                and bound.configuration_epoch_id == context.configuration_epoch_id
                and bound.configuration_epoch_sha256
                == context.configuration_epoch_sha256
                and p.sample_basis == bound.sample_basis
                and p.bound_method == bound.bound_method
                and p.coverage == bound.coverage
                and p.dependency_hashes == bound.dependency_hashes
                and item.evidence_sha256 == bound.evidence_sha256
                and p.observed_at_unix_ns
                <= context.as_of_unix_ns
                <= p.valid_until_unix_ns
            )
        if not good:
            blocked.append(term)
        else:
            assert (
                item is not None
                and p is not None
                and item.bound_micrometers is not None
            )
            total += item.bound_micrometers
            expiries.append(p.valid_until_unix_ns)
    erosion = (
        target.target_safe_radius_micrometers
        - target.tool_tip_radius_micrometers
        - target.guard_micrometers
    )
    margin = erosion - total
    disposition = (
        AccuracyBudgetDisposition.BLOCKED_UNBOUNDED
        if blocked
        else (
            AccuracyBudgetDisposition.DIAGNOSTIC_FITS_ZERO_AUTHORITY
            if erosion > 0 and margin >= 0
            else AccuracyBudgetDisposition.BLOCKED_TARGET_MARGIN
        )
    )
    expected = TargetBudgetAssessment(
        disposition,
        None if blocked else total,
        erosion,
        None if blocked else margin,
        tuple(blocked),
        context.as_of_unix_ns,
        None if blocked else min(expiries),
        context.operating_domain,
        context.configuration_epoch_id,
        context.configuration_epoch_sha256,
        context.clock_evidence_sha256,
        policy.source_sha256,
        _assessment_input_manifest_sha256(policy, observed, selected, context, target),
        target.target_id,
        target.evidence_sha256,
    )
    _same(
        result,
        _plain(asdict(expected)),
        "retained accuracy classifications, sums and signed margins",
    )


def _derive(
    document: dict[str, Any], binding: RehearsalNoncontactBinding
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    technical = document["technical_reports"]
    if type(technical) is not dict or set(technical) != {
        "historical_collision",
        "static_inventory",
        "accuracy_common",
        "accuracy_cases",
    }:
        raise RehearsalNoncontactError(
            "Complete closed technical report membership required"
        )
    historical = _historical(binding)
    _same(
        technical["historical_collision"],
        historical.to_dict(),
        "full historical collision report",
    )
    static = _static_inventory(binding)
    _same(
        technical["static_inventory"], static, "complete static body/source inventory"
    )
    policy = _policy(binding)
    common = _accuracy_inputs(binding, policy)
    _same(technical["accuracy_common"], common, "complete typed accuracy inputs")
    cases = technical["accuracy_cases"]
    if type(cases) is not list or len(cases) != len(_CASES):
        raise RehearsalNoncontactError("All closed accuracy cases must be retained")
    controls = []
    for expected_case, case in zip(_case_deltas(common), cases):
        if type(case) is not dict or set(case) != {*expected_case, "result"}:
            raise RehearsalNoncontactError("Exact accuracy case schema required")
        _same(
            {key: case[key] for key in expected_case},
            expected_case,
            "accuracy case inputs",
        )
        _arithmetic_verification(policy, common, case, case["result"])
        controls.append(
            {
                "case_id": case["case_id"],
                **{
                    key: case["result"][key]
                    for key in (
                        "disposition",
                        "blocking_term_ids",
                        "conservative_error_micrometers",
                        "eroded_target_radius_micrometers",
                        "remaining_margin_micrometers",
                    )
                },
            }
        )
    checks = []

    def check(
        key: str, kind: str, passed: bool, observed: dict[str, Any], meaning: str
    ) -> None:
        checks.append(
            {
                "check_id": key,
                "check_kind": kind,
                "passed": passed,
                "observed": observed,
                "meaning": meaning,
            }
        )

    check(
        "historical_collision_readiness",
        "NOMINAL",
        historical.geometry_audit.diagnostic_ready,
        {"status": historical.status},
        "Historical eye-on-arm geometry remains incomplete; six digital proxies are not installed clearance.",
    )
    missing_bodies = [
        row["body_id"]
        for row in static["geometry"]
        if row["state"] == "MISSING_INSTALLED_GEOMETRY"
    ]
    check(
        "static_installed_geometry",
        "NOMINAL",
        not missing_bodies,
        {"missing_bodies": len(missing_bodies)},
        "Static-camera body names and design hashes do not supply installed envelopes.",
    )
    check(
        "real_accuracy_readiness",
        "NOMINAL",
        controls[0]["disposition"] == "DIAGNOSTIC_FITS_ZERO_AUTHORITY",
        {
            "status": controls[0]["disposition"],
            "missing_terms": controls[0]["blocking_term_ids"],
        },
        "All physical terms remain unmeasured; synthetic target geometry is not a real safe-region certificate.",
    )
    for row in controls[1:]:
        desired = (
            "DIAGNOSTIC_FITS_ZERO_AUTHORITY"
            if row["case_id"] == "finite_control"
            else (
                "BLOCKED_TARGET_MARGIN"
                if row["case_id"] == "target_margin"
                else "BLOCKED_UNBOUNDED"
            )
        )
        check(
            "accuracy_" + row["case_id"],
            "INVARIANT" if row["case_id"] == "finite_control" else "EXPECTED_FAULT",
            row["disposition"] == desired,
            row,
            "Synthetic arithmetic/refusal check only; passing this check does not promote nominal readiness.",
        )
    geometry = binding.reference_binding.source_context["nominal_geometry"]
    selected = {
        item["device"]: item["catalog_total"] for item in geometry["selected_targets"]
    }
    summary = {
        "schema": "rocell.rehearsal_noncontact_summary.v1",
        "nominal_readiness": "BLOCKED",
        "collision_historical": {
            "scope": "HISTORICAL_EYE_ON_ARM",
            "status": historical.status,
            "required_body_count": historical.geometry_audit.required_body_count,
            "proxy_body_count": len(historical.geometry_audit.diagnostic_only_body_ids),
            "urdf_collision_element_count": historical.urdf_collision_element_count,
            "missing_body_ids": list(historical.missing_required_body_ids),
            "unknown_body_ids": list(historical.unknown_required_body_ids),
        },
        "static_geometry": {
            "status": "NOT_EVALUATED",
            "required_body_count": len(static["requirements"]),
            "required_source_count": len(static["source_inventory"]),
            "missing_geometry_body_ids": missing_bodies,
            "missing_source_keys": [
                row["source_key"]
                for row in static["source_inventory"]
                if row["source_sha256"] is None
            ],
        },
        "accuracy": {
            "status": controls[0]["disposition"],
            "unit": "micrometers",
            "unmeasured_term_ids": controls[0]["blocking_term_ids"],
            "conservative_error_micrometers": controls[0][
                "conservative_error_micrometers"
            ],
            "remaining_margin_micrometers": controls[0]["remaining_margin_micrometers"],
            "controls": controls,
        },
        "selection": {
            "domain": "NOMINAL_SOURCE_GEOMETRY",
            "tool_case_id": geometry["tool_case_id"],
            "target_scope": "NO_TARGET_REACHABILITY_EVALUATED",
            "keyboard_targets_evaluated": 0,
            "keyboard_catalog_total": selected["keyboard"],
            "phone_targets_evaluated": 0,
            "phone_catalog_total": selected["phone"],
        },
        "dependencies": {
            "reference_binding_sha256": binding.reference_binding.binding_sha256,
            "reference_evidence_sha256": binding.reference_evidence_sha256,
            "predecessor_receipt_sha256": binding.predecessor_receipt_sha256,
            "predecessor_assessment_sha256": binding.predecessor_assessment_sha256,
            "predecessor_review_sha256": binding.predecessor_review_sha256,
            "camera_role": _PROVENANCE["camera_role"],
            "feedback_role": _PROVENANCE["feedback_role"],
        },
        "not_evaluated": list(_NOT_EVALUATED),
        "physical_authority": False,
    }
    return checks, summary


@dataclass(frozen=True, slots=True)
class RehearsalNoncontactEvidence:
    _payload: bytes

    def __post_init__(self) -> None:
        _decode(self._payload)

    def canonical_bytes(self) -> bytes:
        return self._payload

    @property
    def evidence_sha256(self) -> str:
        return hashlib.sha256(self._payload).hexdigest()

    @property
    def evaluation_sha256(self) -> str:
        return self.evidence_sha256

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self._payload)

    def safe_summary(self) -> dict[str, Any]:
        return self.to_dict()["safe_summary"]

    @property
    def checks(self) -> tuple[dict[str, Any], ...]:
        return tuple(self.to_dict()["checks"])

    @property
    def outcome(self) -> str:
        return self.to_dict()["outcome"]


def verify_rehearsal_noncontact_evidence(
    payload: bytes,
    *,
    expected_binding: RehearsalNoncontactBinding,
    expected_evidence_sha256: str,
    expected_evaluator_source_sha256: str,
) -> RehearsalNoncontactEvidence:
    """Pure strict retained verification; no file, collector, assessor or solver calls."""
    if type(expected_binding) is not RehearsalNoncontactBinding:
        raise RehearsalNoncontactError("Exact server-bound NC-01 binding required")
    expected_binding.__post_init__()
    document = _decode(payload)
    _same(
        hashlib.sha256(payload).hexdigest(),
        digest(expected_evidence_sha256),
        "trusted retained hash",
    )
    expected = {
        "schema": SCHEMA,
        "stage": _STAGE,
        "binding": expected_binding.to_dict(),
        "evaluator_source_sha256": digest(expected_evaluator_source_sha256),
        "selected_inputs_sha256": expected_binding.binding_sha256,
        "provenance": _PROVENANCE,
        "physical_authority": False,
        "composition": "HARDWARE_INCAPABLE_REHEARSAL",
        "physical_release_effect": "NONE",
        "actual_physical_effects": _EFFECTS,
        "meaning": _MEANING,
    }
    if set(document) != {
        *expected,
        "technical_reports",
        "checks",
        "safe_summary",
        "outcome",
    }:
        raise RehearsalNoncontactError("Exact noncontact report schema required")
    for key, value in expected.items():
        _same(document[key], value, "identity/authority " + key)
    try:
        if set(expected_binding.source_context["dependency_source_sha256s"]) != set(
            _DEPENDENCIES
        ):
            raise RehearsalNoncontactError(
                "Closed dependency source membership changed"
            )
        checks, summary = _derive(document, expected_binding)
        _same(document["checks"], checks, "derived checks")
        _same(document["safe_summary"], summary, "derived summary")
        _same(
            document["outcome"],
            (
                "REHEARSAL_CHECKS_PASSED"
                if all(row["passed"] is True for row in checks)
                else "BLOCKED"
            ),
            "nominal outcome",
        )
    except (ValueError, TypeError, KeyError, IndexError, AttributeError) as error:
        raise RehearsalNoncontactError(
            "Retained noncontact source or calculation is inconsistent"
        ) from error
    return RehearsalNoncontactEvidence(payload)


def evaluate_rehearsal_noncontact_stage(
    workspace: Path, binding: RehearsalNoncontactBinding
) -> RehearsalNoncontactEvidence:
    """Run actual historical readiness and six closed typed arithmetic cases once."""
    if type(binding) is not RehearsalNoncontactBinding:
        raise RehearsalNoncontactError("Exact source-bound noncontact binding required")
    binding.__post_init__()
    root = Path(workspace).resolve()
    _same(
        read_noncontact_source_context(root),
        binding.source_context_json,
        "fresh source snapshot",
    )
    context = load_simulation_context(
        root, root / "software/config/system_manifest.json"
    )
    historical = assess_current_collision_readiness(context)
    policy = load_target_accuracy_budget_policy(root)
    common = _accuracy_inputs(binding, policy)
    cases = _case_deltas(common)
    for case in cases:
        clock, target, terms, observations = _typed_case(common, case)
        case["result"] = _plain(
            asdict(
                assess_target_accuracy_budget(
                    policy,
                    observations,
                    term_bindings=terms,
                    assessment_context=clock,
                    target_geometry=target,
                )
            )
        )
    document: dict[str, Any] = {
        "schema": SCHEMA,
        "stage": _STAGE,
        "binding": binding.to_dict(),
        "evaluator_source_sha256": hashlib.sha256(
            _read(Path(__file__), 128 * 1024)
        ).hexdigest(),
        "technical_reports": {
            "historical_collision": historical.to_dict(),
            "static_inventory": _static_inventory(binding),
            "accuracy_common": common,
            "accuracy_cases": cases,
        },
        "selected_inputs_sha256": binding.binding_sha256,
        "provenance": dict(_PROVENANCE),
        "physical_authority": False,
        "composition": "HARDWARE_INCAPABLE_REHEARSAL",
        "physical_release_effect": "NONE",
        "actual_physical_effects": dict(_EFFECTS),
        "meaning": _MEANING,
    }
    checks, summary = _derive(document, binding)
    document.update(
        checks=checks,
        safe_summary=summary,
        outcome=(
            "REHEARSAL_CHECKS_PASSED"
            if all(row["passed"] is True for row in checks)
            else "BLOCKED"
        ),
    )
    _same(
        read_noncontact_source_context(root),
        binding.source_context_json,
        "source snapshot after calculation",
    )
    return verify_rehearsal_noncontact_evidence(
        _encode(document),
        expected_binding=binding,
        expected_evidence_sha256=hashlib.sha256(_encode(document)).hexdigest(),
        expected_evaluator_source_sha256=document["evaluator_source_sha256"],
    )
