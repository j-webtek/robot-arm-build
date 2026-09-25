"""Server-owned stage-12 plan and derived, raw-free assessment projection.

The complete exchange remains in the coordinator's immutable evidence record.
This small report is derived only after the caller verifies that record against
the exact consumed permit, known attempt result and reviewed predecessors.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

from rocell.application.cell_commissioning_coordinator import ObservedPowerState
from rocell.application.physical_connection_contracts import canonical_sha256
from rocell.application.rehearsal_feedback_binding import RehearsalFeedbackBinding


def feedback_plan(binding: RehearsalFeedbackBinding) -> Any:
    """The UI cannot select a controller, protocol, power state or fault here."""
    from rocell.application.arm_feedback_rehearsal_campaign import (
        ArmFeedbackRehearsalPlan,
        SyntheticFinalPowerObservationSpec,
    )

    # A procedural memory fixture, never a claimed second human or power sensor.
    observer = "synthetic-post-feedback-observer"
    if binding.operator_id == observer:
        observer = "synthetic-post-feedback-observer-2"
    return ArmFeedbackRehearsalPlan(
        binding_sha256=binding.binding_sha256,
        source_sha256=binding.workspace_source_sha256,
        controller=binding.controller,
        power_event_observation_sha256=binding.predecessors[2].evaluation_sha256,
        scenario="nominal",
        final_power_observation=SyntheticFinalPowerObservationSpec(
            observer, ObservedPowerState.DEENERGIZED
        ),
    )


def feedback_power_dependencies(binding: RehearsalFeedbackBinding) -> dict[str, str]:
    """Named, explicitly unmeasured fixture dependencies of the energy envelope."""
    return {
        "power_topology_sha256": canonical_sha256(
            {"binding": binding.binding_sha256, "fixture": "UNMEASURED_POWER_TOPOLOGY"}
        ),
        "safety_review_sha256": canonical_sha256(
            {
                "review": binding.predecessors[1].review_sha256,
                "evaluation": binding.predecessors[1].evaluation_sha256,
            }
        ),
        "installed_object_inventory_sha256": canonical_sha256(
            {
                "binding": binding.binding_sha256,
                "fixture": "UNMEASURED_INSTALLED_OBJECT_INVENTORY",
            }
        ),
    }


@dataclass(frozen=True, slots=True)
class RehearsalFeedbackEvaluation:
    _payload: bytes

    @property
    def evidence_sha256(self) -> str:
        return hashlib.sha256(self._payload).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self._payload)

    @property
    def outcome(self) -> str:
        return self.to_dict()["outcome"]

    @property
    def checks(self) -> tuple[dict[str, Any], ...]:
        return tuple(self.to_dict()["checks"])


def feedback_evaluation(
    binding: RehearsalFeedbackBinding, verified: Any, *, coordinator_known: bool = True
) -> RehearsalFeedbackEvaluation:
    """Derive independent predicates from an already-verified campaign artifact.

    This internal adapter is not a pure-verification substitute: its caller must
    compare the exact M1 attempt/result/evidence first. No worker is replayed.
    """
    from rocell.application.arm_feedback_rehearsal_campaign import (
        VerifiedArmFeedbackCampaign,
    )
    from rocell.application.owned_arm_feedback_rehearsal_campaign import (
        VerifiedOwnedArmFeedbackCampaign,
        owned_feedback_checks,
    )

    if (
        type(binding) is not RehearsalFeedbackBinding
        or type(verified)
        not in (VerifiedArmFeedbackCampaign, VerifiedOwnedArmFeedbackCampaign)
        or type(coordinator_known) is not bool
    ):
        raise ValueError(
            "Exact verified campaign/binding and Boolean coordinator disposition required"
        )
    summary = verified.safe_summary()
    if (
        verified.to_dict()["plan"]["binding_sha256"] != binding.binding_sha256
        or summary["source_sha256"] != binding.workspace_source_sha256
        or verified.request.controller != binding.controller
        or verified.request.feedback.power_event_observation_sha256
        != binding.predecessors[2].evaluation_sha256
    ):
        raise ValueError(
            "The verified campaign cannot be relabeled with another reviewed stage binding"
        )
    observation = verified.final_power_observation
    checks = [
        {
            "check_id": check_id,
            "check_kind": "NOMINAL" if index < 3 else "INVARIANT",
            "passed": passed,
            "observed": {"result": passed},
            "meaning": meaning,
        }
        for index, (check_id, passed, meaning) in enumerate(
            (
                (
                    "technical_response",
                    summary["technical_response_valid"] is True,
                    "The bounded simulated response packet passed wire and typed field checks; complete transaction acceptance is separate.",
                ),
                (
                    "serial_cleanup",
                    summary["serial_cleanup_confirmed"] is True,
                    "The in-memory serial connection closed; this is not power-off evidence.",
                ),
                (
                    "independent_synthetic_final_power",
                    observation is not None
                    and observation["observed_power_state"] == "DEENERGIZED",
                    "A separate post-campaign fixture modeled de-energization. No physical power was observed.",
                ),
                (
                    "complete_feedback_transaction",
                    summary["feedback_receipt_valid"] is True
                    and summary["worker_outcome"] == "SUCCEEDED_DIAGNOSTIC"
                    and summary["effect_uncertain"] is False,
                    "The complete one-shot transaction succeeded with its ordered receipt, not merely a valid packet prefix.",
                ),
                (
                    "coordinator_retained_known",
                    coordinator_known is True,
                    "The coordinator retained the complete exchange and sealed this exact attempt known; missing retention or uncertainty cannot pass.",
                ),
                (
                    "worker_power_not_inferred",
                    summary["final_power_state"]
                    == "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION",
                    "The serial worker cannot establish the arm's final power state.",
                ),
                (
                    "physical_authority_held",
                    summary["physical_authority"] is False,
                    "Received hardware, physical power, serial activation, motion and contact remain unqualified.",
                ),
            )
        )
    ]
    owned = type(verified) is VerifiedOwnedArmFeedbackCampaign
    if owned:
        meanings = {
            "owned_process_cleanup": "The actual child process tree exited and owned process resources closed; this is not serial or power evidence.",
            "owned_process_completed": "The bounded owned child returned a complete verified result without a process error.",
            "owned_release_handshake": "The retained actual-PID challenge and exact RELEASE bound this one child to the consumed attempt.",
            "nonpurging_native_cleanup": "The actual non-purging backend closed its incapable serial-owner resources with no unresolved pending I/O.",
            "controller_resolution_before_open_and_write": "Two fresh modeled Windows metadata snapshots matched the exact reviewed controller before open and before write; no physical metadata or handle identity was observed.",
        }
        checks.extend(
            {
                "check_id": key,
                "check_kind": "INVARIANT",
                "passed": passed,
                "observed": {"result": passed},
                "meaning": meanings[key],
            }
            for key, passed in owned_feedback_checks(verified.process_summary()).items()
        )
    report = {
        "stage": "feedback_only_connection",
        "outcome": (
            "REHEARSAL_CHECKS_PASSED"
            if all(row["passed"] for row in checks)
            else "BLOCKED"
        ),
        "evaluation_sha256": verified.evidence_sha256,
        "selected_inputs_sha256": binding.binding_sha256,
        "checks": checks,
        "safe_summary": summary,
        "final_power_observation": observation,
        "provenance": {
            "controller": "EXACT_REVIEWED_STAGE_NINE_MEMORY_FIXTURE",
            "serial": (
                "OWNED_CHILD_EXISTING_ARM_FEEDBACK_WORKER_NONPURGING_INCAPABLE_API"
                if owned
                else "EXISTING_ARM_FEEDBACK_WORKER_INCAPABLE_SERIAL_BACKEND"
            ),
            "retention": (
                "COMPLETE_CAMPAIGN_BYTES_BEFORE_KNOWN_SEAL"
                if coordinator_known
                else "RETENTION_OR_KNOWN_SEAL_UNCONFIRMED"
            ),
            "final_power": "INDEPENDENT_POST_CAMPAIGN_FIXTURE_NOT_MEASUREMENT",
            "physical_observation": False,
        },
        "physical_authority": False,
        "meaning": "Coordinator-backed memory-only feedback rehearsal. Technical response, serial cleanup and synthetic final-power observation are separate; no received hardware or physical motion/contact authority is established.",
    }
    if owned:
        report["meaning"] = (
            "Coordinator-backed owned-process feedback rehearsal. The actual feedback worker and non-purging backend use an incapable serial API inside an isolated child. Process cleanup, serial cleanup and synthetic power observations remain separate; physical connection, motion and contact remain held."
        )
    return RehearsalFeedbackEvaluation(
        json.dumps(
            report,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    )
