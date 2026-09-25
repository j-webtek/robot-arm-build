"""Stage-12 projection checks using actual workers and memory-only persistence.

The fixture imports provide a virtual clock and a transaction-store test double,
not a transport mock: the closed ArmFeedbackWorker lifecycle and both retained
evidence verifiers run. No port inventory, serial device or camera is touched.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from rocell.application import arm_feedback_rehearsal_campaign as campaign
from rocell.application import cell_commissioning_coordinator as core
from rocell.application import rehearsal_arm_identity_stage as identity_stage
from rocell.application import rehearsal_feedback_stage as stage
from rocell.application.commissioning_m1_persistence import rehearsal_source_binding
from rocell.application.physical_connection_contracts import EvidenceOrigin
from rocell.application.physical_onboarding import PhysicalOnboardingStage
from rocell.application.physical_onboarding_attempts import AttemptState
from rocell.application.rehearsal_feedback_binding import (
    RehearsalFeedbackBinding,
    ReviewedFeedbackPredecessor,
    controller_from_verified_arm_identity,
)
from test_arm_feedback_rehearsal_campaign import Clock, RetainingMemoryStore
from test_commissioning_coordinator import _components


WORKSPACE = Path(__file__).resolve().parents[3]


def _hash(label: str) -> str:
    return hashlib.sha256(label.encode("ascii")).hexdigest()


@pytest.fixture(scope="module")
def identity_report() -> dict[str, Any]:
    binding = identity_stage.RehearsalArmIdentityBinding(
        "a" * 64,
        "b" * 64,
        "CELL-A",
        "session-1",
        "operator-1",
        "c" * 64,
        "d" * 64,
        "e" * 64,
        "f" * 64,
    )
    retained = identity_stage.evaluate_rehearsal_arm_identity_stage(WORKSPACE, binding)
    # This really loads the local profile and injected inventory fixture, then
    # independently verifies it without replaying inventory or model checks.
    verified = identity_stage.verify_rehearsal_arm_identity_evidence(
        retained.canonical_bytes(),
        expected_binding=binding,
        expected_evidence_sha256=retained.evidence_sha256,
        expected_evaluator_source_sha256=hashlib.sha256(
            Path(identity_stage.__file__).read_bytes()
        ).hexdigest(),
    )
    return verified.to_dict()


@pytest.fixture(scope="module")
def binding(identity_report) -> RehearsalFeedbackBinding:
    predecessors = tuple(
        ReviewedFeedbackPredecessor(
            name,
            _hash(name + " receipt"),
            _hash(name + " assessment"),
            _hash(name + " review"),
            _hash(name + " evaluation"),
        )
        for name in ("arm_identity", "power_safety", "power_on_observation")
    )
    return RehearsalFeedbackBinding(
        "a" * 64,
        "b" * 64,
        "CELL-A",
        "session-1",
        "operator-1",
        predecessors,
        controller_from_verified_arm_identity(
            identity_report, identity_receipt_sha256=predecessors[0].receipt_sha256
        ),
    )


def _run(
    binding,
    *,
    scenario="nominal",
    final_state=core.ObservedPowerState.DEENERGIZED,
    fail=None,
    plan_override=None,
):
    """Execute only the sealed incapable serial worker through real coordinator."""
    _, old_store, _, _, _ = _components(serial=True)
    clock = Clock()
    nominal = stage.feedback_plan(binding)
    plan = plan_override or replace(
        nominal,
        scenario=scenario,
        final_power_observation=(
            None
            if final_state is None
            else replace(
                nominal.final_power_observation, observed_power_state=final_state
            )
        ),
    )
    worker = campaign.ArmFeedbackRehearsalCampaign(
        plan,
        worker_executable_sha256=hashlib.sha256(
            Path(campaign.__file__).read_bytes()
        ).hexdigest(),
        monotonic_ns=clock,
        wait=clock.wait,
    )
    registration = worker.registration()
    snapshot = replace(
        old_store.snapshot,
        cell_id=binding.cell_id,
        session_id=binding.session_id,
        stage=PhysicalOnboardingStage.FEEDBACK_ONLY_CONNECTION,
        source_binding_sha256=rehearsal_source_binding(plan.source_sha256),
        selected_identity_sha256=plan.controller.identity.identity_sha256,
    )
    store = RetainingMemoryStore(snapshot)
    store.fail = fail
    store.envelope = replace(
        old_store.envelope,
        operation_sha256=registration.operation_sha256,
        operator_id=binding.operator_id,
        observer_id=nominal.final_power_observation.observer_id,
        issued_at_ns=clock.value,
        expires_at_ns=clock.value + core.MAX_PERMIT_TTL_NS,
        **stage.feedback_power_dependencies(binding),
    )
    coordinator = core.CellCommissioningCoordinator(
        persistence=store,
        registrations=(registration,),
        workers={registration.worker_id: worker},
        retained_campaign_actions=(registration.action_id,),
        monotonic_ns=clock,
    )
    request = core.RegisteredActionRequest(
        snapshot.cell_id,
        snapshot.session_id,
        registration.action_id,
        "feedback-stage-test",
        snapshot.challenge_sha256,
    )
    permit = coordinator.prepare(request)
    result = coordinator.execute(permit)
    assert worker.evidence is not None, result.reason_codes
    # Reopen-style pure verification consumes the complete bytes and trusted
    # expected plan/permit/hash. It must not call the worker again.
    verified = campaign.verify_retained_arm_feedback_campaign(
        worker.evidence.canonical_bytes(),
        expected_plan=plan,
        expected_permit=permit,
        expected_evidence_sha256=worker.evidence.evidence_sha256,
    )
    return result, verified, store


@pytest.fixture(scope="module")
def nominal(binding):
    return _run(binding)


def _checks(report):
    return {row["check_id"]: row for row in report.checks}


def test_nominal_uses_distinct_stage_and_campaign_context_bindings(binding, nominal):
    result, verified, store = nominal
    assert result.state is AttemptState.SEALED_KNOWN
    assert verified.to_dict()["plan"]["binding_sha256"] == binding.binding_sha256
    assert verified.safe_summary()["binding_sha256"] != binding.binding_sha256
    evaluated = stage.feedback_evaluation(binding, verified, coordinator_known=True)
    report = evaluated.to_dict()
    assert evaluated.outcome == "REHEARSAL_CHECKS_PASSED"
    assert len(evaluated.checks) == 7
    assert all(row["passed"] is True for row in evaluated.checks)
    assert report["selected_inputs_sha256"] == binding.binding_sha256
    assert report["evaluation_sha256"] == verified.evidence_sha256
    assert report["physical_authority"] is False
    assert report["provenance"]["physical_observation"] is False
    assert store.trace.index("FULL_EVIDENCE_RETAINED") < store.trace.index(
        "SEALED_KNOWN"
    )
    assert report["safe_summary"]["final_power_state"] == (
        "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION"
    )
    assert report["final_power_observation"]["physical_observation"] is False
    assert (
        report["final_power_observation"]["serial_close_used_to_infer_power"] is False
    )


@pytest.mark.parametrize(
    "scenario",
    [
        "boot-bytes",
        "short-write",
        "timeout",
        "identity-change",
        "close-failure",
        "malformed-response",
        "wrong-response",
        "extra-response",
    ],
)
def test_actual_faults_do_not_become_expected_fault_stage_passes(binding, scenario):
    result, verified, _ = _run(binding, scenario=scenario)
    assert result.state is AttemptState.SEALED_UNCERTAIN
    evaluated = stage.feedback_evaluation(binding, verified, coordinator_known=False)
    assert evaluated.outcome == "BLOCKED"
    checks = _checks(evaluated)
    assert checks["complete_feedback_transaction"]["passed"] is False
    assert checks["coordinator_retained_known"]["passed"] is False
    assert all(row["check_kind"] != "EXPECTED_FAULT" for row in evaluated.checks)
    assert checks["independent_synthetic_final_power"]["passed"] is True
    assert checks["worker_power_not_inferred"]["passed"] is True
    assert checks["physical_authority_held"]["passed"] is True
    if scenario == "close-failure":
        assert checks["technical_response"]["passed"] is True
        assert checks["serial_cleanup"]["passed"] is False
    # Even a caller's wrong known flag cannot turn an incomplete exchange green.
    assert stage.feedback_evaluation(binding, verified).outcome == "BLOCKED"


@pytest.mark.parametrize(
    "final_state",
    [None, core.ObservedPowerState.UNKNOWN, core.ObservedPowerState.ENERGIZED],
)
def test_worker_success_and_close_cannot_infer_final_power(binding, final_state):
    result, verified, _ = _run(binding, final_state=final_state)
    assert result.state is AttemptState.SEALED_UNCERTAIN
    evaluated = stage.feedback_evaluation(binding, verified, coordinator_known=False)
    checks = _checks(evaluated)
    assert evaluated.outcome == "BLOCKED"
    assert checks["technical_response"]["passed"] is True
    assert checks["serial_cleanup"]["passed"] is True
    assert checks["complete_feedback_transaction"]["passed"] is True
    assert checks["independent_synthetic_final_power"]["passed"] is False
    assert checks["worker_power_not_inferred"]["passed"] is True


def test_retention_failure_is_not_hidden_by_successful_serial_worker(binding):
    result, verified, store = _run(binding, fail="FULL_EVIDENCE_RETAINED")
    assert result.state is AttemptState.SEALED_UNCERTAIN
    assert store.evidence == {}
    evaluated = stage.feedback_evaluation(binding, verified, coordinator_known=False)
    checks = _checks(evaluated)
    assert evaluated.outcome == "BLOCKED"
    assert checks["technical_response"]["passed"] is True
    assert checks["serial_cleanup"]["passed"] is True
    assert checks["complete_feedback_transaction"]["passed"] is True
    assert checks["independent_synthetic_final_power"]["passed"] is True
    assert checks["coordinator_retained_known"]["passed"] is False
    assert evaluated.to_dict()["provenance"]["retention"] != (
        "COMPLETE_CAMPAIGN_BYTES_BEFORE_KNOWN_SEAL"
    )


@pytest.mark.parametrize("flag", [None, 0, 1, "true", [], {}])
def test_known_disposition_requires_literal_boolean(binding, nominal, flag):
    with pytest.raises(ValueError):
        stage.feedback_evaluation(binding, nominal[1], coordinator_known=flag)


def test_unknown_coordinator_disposition_blocks_an_otherwise_nominal_result(
    binding, nominal
):
    evaluated = stage.feedback_evaluation(binding, nominal[1], coordinator_known=False)
    assert evaluated.outcome == "BLOCKED"
    assert [row["check_id"] for row in evaluated.checks if not row["passed"]] == [
        "coordinator_retained_known"
    ]


@pytest.mark.parametrize(
    "field,new_value",
    [
        ("workspace_source_sha256", "c" * 64),
        ("catalog_sha256", "d" * 64),
        ("cell_id", "other-cell"),
        ("session_id", "other-session"),
        ("operator_id", "other-operator"),
    ],
)
def test_verified_campaign_cannot_be_relabelled(binding, nominal, field, new_value):
    with pytest.raises(ValueError, match="relabeled"):
        stage.feedback_evaluation(replace(binding, **{field: new_value}), nominal[1])


@pytest.mark.parametrize("index", range(3))
@pytest.mark.parametrize(
    "field",
    ["receipt_sha256", "assessment_sha256", "review_sha256", "evaluation_sha256"],
)
def test_every_predecessor_document_hash_changes_binding(
    binding, nominal, index, field
):
    predecessors = list(binding.predecessors)
    predecessors[index] = replace(predecessors[index], **{field: "f" * 64})
    controller = binding.controller
    if index == 0 and field == "receipt_sha256":
        controller = replace(controller, identity_receipt_sha256="f" * 64)
    changed = replace(binding, predecessors=tuple(predecessors), controller=controller)
    assert changed.binding_sha256 != binding.binding_sha256
    with pytest.raises(ValueError, match="relabeled"):
        stage.feedback_evaluation(changed, nominal[1])


@pytest.mark.parametrize("field", ["source_sha256", "controller", "power_event"])
def test_plan_binding_hash_alone_does_not_substitute_other_request_inputs(
    binding, field
):
    plan = stage.feedback_plan(binding)
    if field == "source_sha256":
        altered = replace(plan, source_sha256="e" * 64)
    elif field == "controller":
        altered = replace(
            plan,
            controller=replace(
                plan.controller,
                identity=replace(plan.controller.identity, port_name="COM43"),
            ),
        )
    else:
        altered = replace(plan, power_event_observation_sha256="e" * 64)
    result, verified, _ = _run(binding, plan_override=altered)
    assert result.state is AttemptState.SEALED_KNOWN
    assert verified.to_dict()["plan"]["binding_sha256"] == binding.binding_sha256
    with pytest.raises(ValueError, match="relabeled"):
        stage.feedback_evaluation(binding, verified)


@pytest.mark.parametrize("value", [{}, None, object()])
def test_unverified_summary_duck_type_is_not_accepted(binding, value):
    with pytest.raises(ValueError, match="Exact verified"):
        stage.feedback_evaluation(binding, value)


def test_report_and_binding_projections_are_mutation_isolated(binding, nominal):
    evaluated = stage.feedback_evaluation(binding, nominal[1])
    digest = evaluated.evidence_sha256
    pristine = evaluated.to_dict()
    changed = evaluated.to_dict()
    changed["safe_summary"]["api_counts"]["open_attempts"] = 900
    changed["final_power_observation"]["physical_observation"] = True
    changed["checks"][0]["passed"] = False
    changed["provenance"]["physical_observation"] = True
    evaluated.checks[0]["observed"]["result"] = False
    assert evaluated.to_dict() == pristine
    assert evaluated.evidence_sha256 == digest
    initial = binding.binding_sha256
    binding.to_dict()["predecessors"][0]["receipt_sha256"] = "f" * 64
    binding.selected_identity_document["port_name"] = "COM999"
    assert binding.binding_sha256 == initial


def test_ordinary_report_excludes_private_wire_ports_and_settings(binding, nominal):
    report = stage.feedback_evaluation(binding, nominal[1]).to_dict()
    text = json.dumps(report)
    for forbidden in (
        "COM42",
        "bytes_hex",
        "response_bytes",
        "wire_request_hex",
        "settings_before_open",
        "settings_after_open",
        "port_name",
        '"request":',
        '"T":',
    ):
        assert forbidden not in text
    assert len(text) < 12_000
    assert all(
        set(row) == {"check_id", "check_kind", "passed", "observed", "meaning"}
        for row in report["checks"]
    )


def test_plan_binds_reviewed_controller_and_power_and_has_distinct_fixture_observer(
    binding,
):
    plan = stage.feedback_plan(binding)
    assert plan.scenario == "nominal"
    assert plan.controller is binding.controller
    assert plan.source_sha256 == binding.workspace_source_sha256
    assert (
        plan.power_event_observation_sha256 == binding.predecessors[2].evaluation_sha256
    )
    assert plan.final_power_observation.observer_id != binding.operator_id
    special = replace(binding, operator_id="synthetic-post-feedback-observer")
    assert stage.feedback_plan(special).final_power_observation.observer_id != (
        special.operator_id
    )
    assert plan.to_dict()["physical_authority"] is False
    assert plan.controller.origin is EvidenceOrigin.SYNTHETIC_REHEARSAL
    assert plan.controller.identity.driver.version == "UNMEASURED"


@pytest.mark.parametrize("bad", [None, False, "0" * 64, "A" * 64, "x" * 64, "a" * 63])
def test_binding_rejects_nonexact_source_and_predecessor_hashes(binding, bad):
    with pytest.raises(ValueError):
        replace(binding, workspace_source_sha256=bad)
    with pytest.raises(ValueError):
        replace(binding.predecessors[0], review_sha256=bad)


def test_binding_requires_exact_order_and_controller_identity_receipt(binding):
    for predecessors in (
        list(binding.predecessors),
        tuple(reversed(binding.predecessors)),
        binding.predecessors[:2],
        (binding.predecessors[0],) * 3,
    ):
        with pytest.raises(ValueError):
            replace(binding, predecessors=predecessors)
    with pytest.raises(ValueError):
        replace(
            binding,
            controller=replace(binding.controller, identity_receipt_sha256="e" * 64),
        )


@pytest.mark.parametrize(
    "field,bad",
    [
        ("ephemeral_locator_observation", "COM43"),
        ("os_instance_id", "different-instance"),
        ("persistent_ids", []),
        ("identity_blockers", ["ambiguous"]),
        ("qualified", True),
        ("qualified", 0),
        ("selection_performed", True),
        ("selection_performed", 0),
        ("usb_identity", {"vid": "1234", "pid": "5678", "unit_serial": "OTHER"}),
    ],
)
def test_controller_adapter_accepts_only_exact_unqualified_memory_identity(
    identity_report, field, bad
):
    altered = deepcopy(identity_report)
    altered["reports"]["selection_baseline"]["candidate"][field] = bad
    with pytest.raises(ValueError):
        controller_from_verified_arm_identity(altered, identity_receipt_sha256="c" * 64)


def test_controller_adapter_keeps_model_firmware_and_driver_unmeasured(identity_report):
    selected = controller_from_verified_arm_identity(
        identity_report, identity_receipt_sha256="c" * 64
    )
    assert selected.origin is EvidenceOrigin.SYNTHETIC_REHEARSAL
    assert selected.identity.driver.version == "UNMEASURED"
    assert selected.identity.driver.provider == "SYNTHETIC_UNMEASURED"
    assert (
        selected.serial_profile_sha256
        == identity_report["reports"]["profile"]["profile_file_sha256"]
    )
    altered = deepcopy(identity_report)
    altered["outcome"] = "BLOCKED"
    with pytest.raises(ValueError):
        controller_from_verified_arm_identity(altered, identity_receipt_sha256="c" * 64)
