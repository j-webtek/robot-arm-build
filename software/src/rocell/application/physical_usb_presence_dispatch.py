"""One controlled USB action with post-lease original evidence readback.

This internal owner is not an HTTP endpoint. The wizard service must supply
originally authenticated stage/policy/runtime facts and a live context guard.
Cached views and diagnostics do no I/O. A successful query is not stage PASS.
"""

from __future__ import annotations

from dataclasses import asdict, replace
import json
from pathlib import Path
import re
from threading import Event, RLock
from typing import Any, Callable, cast

from .cell_commissioning_coordinator import (
    BoundedCommissioningWorker,
    ExactOperationPermit,
    PhysicalUsbPresenceCoordinator,
    RegisteredActionRequest,
)
from .commissioning_camera_persistence import physical_camera_source_binding
from .commissioning_usb_presence_persistence import M1PhysicalUsbPresencePersistence
from .physical_onboarding_attempts import AttemptState
from .physical_onboarding_leases import LeaseLevel, LeaseSpec
from .physical_usb_presence_campaign import (
    PhysicalUsbPresenceCampaign,
    verify_usb_presence_campaign_evidence,
)
from .wizard_diagnostic_coordinator import source_fingerprint
from rocell.providers.windows.usb_presence_protocol import canonical


class PhysicalUsbPresenceDispatchError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _require(ok: bool, code: str) -> None:
    if not ok:
        raise PhysicalUsbPresenceDispatchError(code)


def _json(value: Any) -> Any:
    """Trusted DTO boundary: preserve hashes while removing Enum/tuple types."""
    return json.loads(canonical(value))


class PhysicalUsbPresenceDispatchOwner:
    """Original M1-only, one-shot owner; no injectable physical backend."""

    def __init__(
        self,
        persistence: M1PhysicalUsbPresencePersistence,
        campaign: PhysicalUsbPresenceCampaign,
        *,
        revalidate_context: Callable[[], None],
    ):
        _require(
            type(persistence) is M1PhysicalUsbPresencePersistence
            and type(campaign) is PhysicalUsbPresenceCampaign
            and callable(revalidate_context),
            "EXACT_PRESENCE_DISPATCH_CONTEXT_REQUIRED",
        )
        op = campaign.operation.to_dict()
        runtime = persistence._runtime
        _require(
            runtime.cell.cell_id == op["cell_id"]
            and runtime.source_binding_sha256
            == physical_camera_source_binding(op["source_sha256"])
            and persistence._policy.sha256 == op["policy_sha256"],
            "PRESENCE_ORIGINAL_STORE_MISMATCH",
        )
        self._persistence, self._campaign, self._guard = (
            persistence,
            campaign,
            revalidate_context,
        )
        campaign._bind_application_guard(revalidate_context)
        registration = campaign.registration()
        self._core = PhysicalUsbPresenceCoordinator(
            usb_presence_policy_sha256=op["policy_sha256"],
            persistence=persistence,
            registrations=(registration,),
            workers={
                registration.worker_id: cast(BoundedCommissioningWorker, campaign)
            },
            retained_campaign_actions=(registration.action_id,),
            scoped_campaign_actions=(registration.action_id,),
        )
        self._lock = RLock()
        self._used = False
        self._phase = "NOT_STARTED"
        self._permit: ExactOperationPermit | None = None
        self._original: dict[str, Any] | None = None
        self._pending: bytes | None = None
        self._published_operation_id: str | None = None
        self._readback_scope = "NOT_READ"
        self._error_code: str | None = None

    def view(self) -> dict[str, Any]:
        """Cached bounded public status. Never reads files, leases or devices."""
        with self._lock:
            return dict(
                schema="rocell.usb_presence_dispatch_view.v1",
                phase=self._phase,
                used=self._used,
                attempt_id=None if self._permit is None else self._permit.attempt_id,
                original_evidence_sha256=(
                    None
                    if self._original is None
                    else self._original["evidence_sha256"]
                ),
                readback_scope=self._readback_scope,
                error_code=self._error_code,
                publication_operation_id=self._published_operation_id,
                physical_authority=False,
                camera_capture_authorized=False,
                arm_access_authorized=False,
                automatic_replay=False,
            )

    def retained_diagnostics(self) -> dict[str, Any]:
        """Full private original bytes/provenance for the assigned export path."""
        with self._lock:
            collected = self._campaign.retained_evidence
            fallback = (
                None
                if collected is None
                or (
                    self._original is not None
                    and self._original["evidence_sha256"] == collected.sha256
                )
                else dict(
                    document=collected.to_dict(),
                    evidence_sha256=collected.sha256,
                    retention="COLLECTED_NOT_M1_READ_BACK",
                )
            )
            return _json(
                dict(dispatch=self.view(), original=self._original, collected=fallback)
            )

    def _current(self, cancellation: Event) -> None:
        _require(not cancellation.is_set(), "PRESENCE_DISPATCH_CANCELLED")
        _require(self._guard() is None, "PRESENCE_GUARD_MUST_NOT_GRANT_AUTHORITY")
        op = self._campaign.operation.to_dict()
        _require(
            source_fingerprint(Path(op["workspace"])) == op["source_sha256"],
            "PRESENCE_DISPATCH_SOURCE_CHANGED",
        )
        _require(not cancellation.is_set(), "PRESENCE_DISPATCH_CANCELLED")
        _require(self._guard() is None, "PRESENCE_GUARD_MUST_NOT_GRANT_AUTHORITY")

    def perform(self, *, request_key: str, cancellation: Event) -> dict[str, Any]:
        """Prepare once, execute once, read sealed originals, then await UI log.

        Failed/uncertain originals remain diagnostics. No in-memory helper
        result can become a current observation before original readback and
        ownership exit. A second invocation is never a retry mechanism.
        """
        from rocell.providers.windows.owned_usb_presence_evidence import (
            OwnedUsbPresenceRunEvidence,
        )

        _require(isinstance(cancellation, Event), "PRESENCE_CANCELLATION_REQUIRED")
        with self._lock:
            _require(not self._used, "PRESENCE_DISPATCH_ALREADY_USED")
            self._used, self._phase = True, "CHECKING_ADMISSION"
        op = self._campaign.operation.to_dict()
        leases = (
            LeaseSpec(LeaseLevel.CELL, op["cell_id"]),
            LeaseSpec(LeaseLevel.SESSION, op["session_id"]),
            LeaseSpec(LeaseLevel.CAMERA, op["cell_id"]),
        )
        try:
            self._current(cancellation)
            request = RegisteredActionRequest(
                op["cell_id"],
                op["session_id"],
                self._campaign.registration().action_id,
                request_key,
                self._campaign.operation.sha256,
            )
            with self._persistence.transaction(leases) as tx:
                header = tx.snapshot().header
                identity = self._campaign.phase_binding.to_dict()["binding"]
                _require(
                    header.header_sha256 == identity["header_sha256"]
                    and header.session_id == op["session_id"]
                    and header.cell_id == op["cell_id"],
                    "PRESENCE_ORIGINAL_HEADER_MISMATCH",
                )
                challenge = tx.read_admission(request).challenge_sha256
            self._current(cancellation)
            permit = self._core.prepare(
                replace(request, expected_challenge_sha256=challenge)
            )
            with self._lock:
                self._permit, self._phase = permit, "PREPARING_EXACT_WORKER"
            # This immutable, full request/review/permit preflight happens before
            # any intent/arming. Oversize or mismatched subjects cannot consume
            # a physical attempt merely to discover they are not dispatchable.
            self._campaign.preparation_for_permit(permit)
            self._current(cancellation)
            with self._lock:
                self._phase = "EXECUTING"
            result = self._core.execute(permit, cancellation=cancellation)
            with self._lock:
                self._phase = "READING_ORIGINAL_ATTEMPT"
            # Stage-only readback stays possible under quarantine. Reacquiring
            # a device lease is unnecessary and would obstruct fault diagnosis.
            verified = self._persistence.verification(op["session_id"])
            with self._persistence.stage_transaction(
                op["session_id"], expected_challenge_sha256=verified.challenge_sha256
            ) as tx:
                saved_permit = tx.read_campaign_permit(permit.attempt_id)
                saved_result = tx.read_campaign_result(permit.attempt_id)
                saved_facts = tx.read_campaign_admission_evidence(permit.attempt_id)
                _require(
                    canonical(asdict(saved_permit)) == canonical(asdict(permit))
                    and canonical(asdict(saved_result)) == canonical(asdict(result)),
                    "PRESENCE_ORIGINAL_TERMINAL_MISMATCH",
                )
                # Keep genuine terminal/fact diagnostics even when the next
                # evidence read fails. Never substitute the worker's cache.
                with self._lock:
                    self._original = _json(
                        dict(
                            permit=asdict(saved_permit),
                            result=asdict(saved_result),
                            admission_evidence=saved_facts,
                            evidence=None,
                            evidence_sha256=None,
                            reference=None,
                            retention="M1_TERMINAL_READ_BACK_EVIDENCE_PENDING",
                        )
                    )
                    self._readback_scope = "VERIFIED_TERMINAL_EXIT_PENDING"
                artifacts = tx.read_optional_campaign_evidence(permit.attempt_id)
                _require(
                    type(artifacts) is tuple and len(artifacts) <= 1,
                    "PRESENCE_EXACT_ORIGINAL_ARTIFACT_REQUIRED",
                )
                evidence, reference = None, None
                if not artifacts:
                    _require(
                        result.receipt is None,
                        "PRESENCE_ORIGINAL_RECEIPT_WITHOUT_ARTIFACT",
                    )
                    with self._lock:
                        assert self._original is not None
                        self._original["retention"] = (
                            "M1_TERMINAL_READ_BACK_NO_EVIDENCE"
                        )
                else:
                    artifact = artifacts[0]
                    evidence = verify_usb_presence_campaign_evidence(
                        OwnedUsbPresenceRunEvidence(artifact.payload),
                        campaign=self._campaign,
                        permit=saved_permit,
                        expected_evidence_sha256=artifact.payload_sha256,
                    )
                    _require(
                        artifact.label == "physical-native-usb-presence"
                        and artifact.schema == evidence.to_dict()["schema"],
                        "PRESENCE_ORIGINAL_ARTIFACT_ROLE_MISMATCH",
                    )
                    if result.receipt is not None:
                        _require(
                            result.receipt.evidence_sha256s
                            == (artifact.payload_sha256,)
                            and result.receipt.output_bytes == len(artifact.payload),
                            "PRESENCE_ORIGINAL_RECEIPT_ARTIFACT_MISMATCH",
                        )
                    # An original campaign record is not a stage package.
                    # Transfer later under its own exact reference; never
                    # fabricate an EvidenceReference for the campaign ledger.
                    reference = dict(
                        schema="rocell.usb_presence_campaign_reference.v1",
                        cell_id=permit.request.cell_id,
                        session_id=permit.request.session_id,
                        attempt_id=permit.attempt_id,
                        permit_sha256=permit.permit_sha256,
                        evidence_sha256=artifact.payload_sha256,
                        payload_bytes=len(artifact.payload),
                        label=artifact.label,
                    )
                    with self._lock:
                        self._original = _json(
                            dict(
                                permit=asdict(saved_permit),
                                result=asdict(saved_result),
                                admission_evidence=saved_facts,
                                evidence=evidence.to_dict(),
                                evidence_sha256=artifact.payload_sha256,
                                reference=reference,
                                retention="M1_FULL_BYTES_READ_BACK",
                            )
                        )
                        self._readback_scope = "VERIFIED_BYTES_EXIT_PENDING"
            with self._lock:
                self._readback_scope = "EXITED"
            self._current(cancellation)
            # Even a sealed known query can report a known diagnostic failure.
            # That is not qualified identity or permission for the next stage.
            effect = None if evidence is None else evidence.bounded_effect_summary()
            observation = None if evidence is None else evidence.observation
            pending = dict(
                schema="rocell.usb_presence_dispatch_result.v1",
                attempt_id=permit.attempt_id,
                attempt_state=result.state.value,
                status=(
                    observation.to_dict()["outcome"]
                    if result.state is AttemptState.SEALED_KNOWN
                    and effect is not None
                    and effect["current_complete"]
                    and effect["process_cleanup_confirmed"]
                    and effect["native_cleanup_confirmed"]
                    and observation is not None
                    else "HELD"
                ),
                evidence_sha256=None if evidence is None else evidence.sha256,
                execution=None if evidence is None else evidence.safe_summary(),
                reference=reference,
                reason_codes=list(result.reason_codes),
                quarantine_latched=result.quarantine_latched,
                pending_completion_log=True,
                physical_authority=False,
                hardware_qualified=False,
                camera_capture_authorized=False,
                arm_access_authorized=False,
            )
            with self._lock:
                self._pending = canonical(pending)
                self._phase = "PENDING_COMPLETION_LOG"
            return _json(pending)
        except BaseException as error:
            with self._lock:
                self._phase = "FAILED_NO_REPLAY"
                self._pending = None
                code = getattr(error, "code", None)
                self._error_code = (
                    code
                    if type(code) is str
                    and re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", code) is not None
                    else "PRESENCE_DISPATCH_FAILED"
                )
                if self._readback_scope in {
                    "VERIFIED_BYTES_EXIT_PENDING",
                    "VERIFIED_TERMINAL_EXIT_PENDING",
                }:
                    self._readback_scope = "EXIT_OR_FINAL_VALIDATION_UNCONFIRMED"
            raise

    def validate_publication(self, result: dict[str, Any]) -> None:
        with self._lock:
            _require(
                self._phase == "PENDING_COMPLETION_LOG"
                and self._pending is not None
                and canonical(result) == self._pending,
                "EXACT_PRESENCE_PUBLICATION_REQUIRED",
            )

    def publication_completed(self, operation_id: str) -> None:
        with self._lock:
            _require(
                self._phase == "PENDING_COMPLETION_LOG"
                and self._pending is not None
                and type(operation_id) is str
                and 1 <= len(operation_id) <= 96,
                "PRESENCE_COMPLETION_LOG_REQUIRED",
            )
            self._published_operation_id = operation_id
            self._phase = "CURRENT"

    def invalidate(self) -> None:
        with self._lock:
            self._pending = None
            self._published_operation_id = None
            self._phase = "HISTORICAL_HELD"
