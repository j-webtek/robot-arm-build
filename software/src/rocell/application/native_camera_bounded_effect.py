"""Pure accounting of an already retained, exactly bound native camera run.

This is not an admission decision. Confirmed bounded effects do not approve a
stage, qualify a driver, observe actuator power or validate capture file bytes.
The independently held native registration/runner remain the release boundary.
"""

from __future__ import annotations

from dataclasses import dataclass

from rocell.providers.windows.native_camera_activation_evidence import (
    OwnedNativeCameraActivationRunEvidence,
    verify_activation_run,
)
from rocell.providers.windows.native_camera_activation_registration import (
    PreparedOwnedNativeActivation,
)
from rocell.providers.windows.native_camera_capture_registration import (
    PreparedOwnedNativeCapture,
)
from rocell.providers.windows.native_camera_registration import PreparedOwnedNativeProbe
from rocell.providers.windows.owned_native_camera_evidence import (
    OwnedNativeCameraRunEvidence,
    verify_owned_native_camera_run_evidence,
)
from rocell.safety.effects import EffectCertainty


@dataclass(frozen=True, slots=True)
class NativeCameraEffectCounts:
    """Exact reported native counts, including unsuccessful attempts."""

    source_activation_attempts: int
    source_opened: int
    control_set_attempts: int
    samples_received: int
    frames_written: int
    source_shutdown_attempts: int


@dataclass(frozen=True, slots=True)
class NativeCameraBoundedEffect:
    effect_certainty: EffectCertainty
    process_cleanup_confirmed: bool
    native_cleanup_confirmed: bool
    counts: NativeCameraEffectCounts | None
    reasons: tuple[str, ...]

    @property
    def cleanup_confirmed(self) -> bool:
        return self.process_cleanup_confirmed and self.native_cleanup_confirmed


def assess_activation_camera_bounded_effect(
    evidence: OwnedNativeCameraActivationRunEvidence,
    *,
    expected_preparation: PreparedOwnedNativeActivation,
    expected_evidence_sha256: str,
    expected_started_ns: int,
    expected_deadline_ns: int,
    maximum_elapsed_ns: int,
) -> NativeCameraBoundedEffect:
    """Account for v2 observations against the caller's original invocation.

    This uses the same application effect model without converting the new
    record to the legacy v1 schema. The caller must independently retain the
    original start, deadline, preparation and evidence digest. Self-consistency
    alone is not proof of original-store provenance or current permission.

    Missing native counters remain None, including a pre-owner hold. A complete
    native receipt can survive a failed process cleanup for diagnosis, but that
    failure must never become confirmed bounded execution. Capture metadata
    validation does not inspect image bytes or prove their freshness/quality.
    """
    if (
        type(evidence) is not OwnedNativeCameraActivationRunEvidence
        or type(expected_preparation) is not PreparedOwnedNativeActivation
        or type(expected_started_ns) is not int
        or type(expected_deadline_ns) is not int
        or not 0 <= expected_started_ns < expected_deadline_ns < 2**63
        or type(maximum_elapsed_ns) is not int
        or not 0 < maximum_elapsed_ns <= 25_000_000_000
    ):
        raise ValueError("EXACT_ACTIVATION_EFFECT_CONTEXT_REQUIRED")
    checked = verify_activation_run(
        evidence,
        expected_preparation=expected_preparation,
        expected_evidence_sha256=expected_evidence_sha256,
    )
    data, assessed = checked.to_dict(), checked.assessment()
    native = assessed.native
    finished = data["finished_ns"]
    reasons = list(assessed.reasons)
    for passed, reason in (
        (data["started_ns"] == expected_started_ns, "ORIGINAL_START_MISMATCH"),
        (
            data["parent_deadline_ns"] == expected_deadline_ns,
            "ORIGINAL_DEADLINE_MISMATCH",
        ),
        (
            type(finished) is int
            and 0 <= finished - expected_started_ns < maximum_elapsed_ns,
            "CAMPAIGN_DURATION_UNCONFIRMED_OR_EXCEEDED",
        ),
        (
            assessed.status == "SUCCEEDED_NATIVE_DIAGNOSTIC",
            "RUN_NOT_SUCCESSFUL",
        ),
    ):
        if not passed and reason not in reasons:
            reasons.append(reason)
    return NativeCameraBoundedEffect(
        EffectCertainty.UNCERTAIN if reasons else EffectCertainty.CONFIRMED,
        assessed.process_cleanup_confirmed,
        native is not None and native.receipt.cleanup_confirmed,
        None if native is None else NativeCameraEffectCounts(**native.receipt.counts),
        tuple(reasons),
    )


def assess_native_camera_bounded_effect(
    evidence: OwnedNativeCameraRunEvidence,
    *,
    expected_preparation: PreparedOwnedNativeProbe | PreparedOwnedNativeCapture,
    expected_evidence_sha256: str,
    expected_deadline_ns: int,
    maximum_elapsed_ns: int,
) -> NativeCameraBoundedEffect:
    """Assess original evidence, without source/file/device reads or a new clock.

    The caller supplies the original invocation deadline and registered campaign
    duration. Elapsed accounting cannot independently establish an absolute end
    timestamp; current cancellation/deadline enforcement remains with the owned
    supervisor and consumed coordinator scope. A failed run is never upgraded
    merely because its process exited or its available counters are bounded.
    """
    if (
        type(evidence) is not OwnedNativeCameraRunEvidence
        or type(expected_preparation)
        not in (PreparedOwnedNativeProbe, PreparedOwnedNativeCapture)
        or type(expected_deadline_ns) is not int
        or not 0 < expected_deadline_ns < 2**63
        or type(maximum_elapsed_ns) is not int
        or not 0 < maximum_elapsed_ns <= 25_000_000_000
    ):
        raise ValueError("EXACT_NATIVE_EFFECT_ASSESSMENT_CONTEXT_REQUIRED")
    # Reconstruct the immutable preparation, then require independent retained
    # evidence/subject hashes. Self-consistent caller bytes alone are not trust.
    prepared = type(expected_preparation)(expected_preparation.payload)
    checked = verify_owned_native_camera_run_evidence(
        evidence,
        expected_preparation_sha256=prepared.preparation_sha256,
        expected_evidence_sha256=expected_evidence_sha256,
    )
    data, native = checked.to_dict(), checked.native_receipt
    process = data["process"]
    process_cleanup = (
        data["owner_constructed"]
        and not data["cleanup_errors"]
        and (not process["created"] or process["tree_exited"])
        and not any(
            process[key]
            for key in (
                "pending",
                "handles_remaining",
                "unclosed_handles_remaining",
                "pins_remaining",
            )
        )
    )
    native_cleanup = native is not None and native.cleanup_confirmed
    counts = None if native is None else NativeCameraEffectCounts(**native.counts)
    if (
        native is None
        and data["primary_error"] == "PHYSICAL_PROVIDER_QUALIFICATION_HELD"
        and not data["owner_constructed"]
    ):
        # This specific observed pre-owner hold cannot have activated a source.
        # Other absent receipts leave counters unknown, never zero by default.
        counts = NativeCameraEffectCounts(0, 0, 0, 0, 0, 0)

    handshake = data["handshake"]
    checks = (
        (
            data["parent_deadline_ns"] == expected_deadline_ns,
            "ORIGINAL_DEADLINE_MISMATCH",
        ),
        (data["elapsed_ns"] < maximum_elapsed_ns, "CAMPAIGN_DURATION_EXCEEDED"),
        (
            native is not None
            and data["native_validated"]
            and not data["admission_only_validated"]
            and data["fixture_preparation"] is None,
            "COMPLETE_NATIVE_RESULT_REQUIRED",
        ),
        (
            native is not None and native.status == "OK",
            "NATIVE_DIAGNOSTIC_NOT_SUCCESSFUL",
        ),
        (
            data["owner_constructed"]
            and process["created"]
            and process["resumed"]
            and process["tree_exited"]
            and process["returncode"] == 0,
            "OWNER_LIFECYCLE_INCOMPLETE",
        ),
        (
            process["peak_handles"]
            <= prepared.registration.budget.observed_handles_per_process,
            "PROCESS_HANDLE_BUDGET_EXCEEDED",
        ),
        (process_cleanup, "PROCESS_CLEANUP_UNCONFIRMED"),
        (native_cleanup, "NATIVE_CLEANUP_UNCONFIRMED"),
        (
            handshake is not None
            and handshake["state"] == "RESULT_VALIDATED_NOT_QUALIFIED"
            and data["release_check_passed"],
            "PARENT_HANDSHAKE_INCOMPLETE",
        ),
        (
            all(data[name]["capture_complete"] for name in ("stdout", "stderr"))
            and process["stdout_eof"]
            and process["stderr_eof"],
            "PIPE_CAPTURE_INCOMPLETE",
        ),
        (
            data["status"] == "SUCCEEDED_NATIVE_DIAGNOSTIC"
            and data["primary_error"] is None
            and not data["cleanup_errors"],
            "RUN_ERROR_RETAINED",
        ),
    )
    reasons = tuple(reason for passed, reason in checks if not passed)
    return NativeCameraBoundedEffect(
        EffectCertainty.UNCERTAIN if reasons else EffectCertainty.CONFIRMED,
        process_cleanup,
        native_cleanup,
        counts,
        reasons,
    )
