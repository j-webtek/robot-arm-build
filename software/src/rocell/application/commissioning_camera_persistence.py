"""Distinct camera-acquisition storage; not native release qualification.

Reuses qualified immutable publication and exact consumed-attempt verification,
but never accepts a source-only or rehearsal store as camera permission. Actual
native dispatch remains independently held. No controller lease or energy
envelope is admitted by this camera-only composition.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
import json
import re
from typing import Any, TYPE_CHECKING

from .cell_commissioning_coordinator import (
    AttemptResult,
    PHYSICAL_CAMERA_COMPOSITION,
    ExactOperationPermit,
    RegisteredActionRequest,
)
from .commissioning_m1_persistence import (
    M1CommissioningPersistenceError,
    _HASH,
    _M1AdmissionFacts,
    _M1CoordinatorTransaction,
    _PHYSICAL_CAMERA_DOMAIN,
    _decode_domain_permit,
    _exact_dataclass,
    _freeze_document,
    _sha256,
)
from .physical_onboarding_attempts import AttemptState, canonical_json_bytes
from .physical_camera_mode_entry import CameraModeEntry, camera_mode_entry_label
from .physical_camera_usb_complete_constants import USB_COMPLETE_EVENT
from .physical_onboarding import EvidenceReference, MAX_EVIDENCE_BYTES, STAGE_ORDER
from .physical_onboarding_durability import read_bounded_regular_file
from .physical_onboarding_leases import LeaseLevel, LeaseSpec
from .physical_onboarding_v2 import (
    V2SessionSnapshot,
    V2StageState,
    _verify_evidence_directory,
)
from .wizard_diagnostic_export import _directory_guard

if TYPE_CHECKING:
    from .physical_onboarding_m1 import (
        M1RuntimeVerification,
        PhysicalOnboardingM1Runtime,
    )


SOURCE_SCHEMA = "rocell.physical_camera_acquisition_source.v1"
RECORD_SCHEMA = _PHYSICAL_CAMERA_DOMAIN.record_schema
ADMISSION_EVIDENCE_SCHEMA = "rocell.camera_original_admission_evidence.v1"
MAX_ADMISSION_EVIDENCE_BYTES = 256 * 1024


def physical_camera_source_binding(workspace_source_sha256: str) -> str:
    if (
        type(workspace_source_sha256) is not str
        or _HASH.fullmatch(workspace_source_sha256) is None
        or workspace_source_sha256 == "0" * 64
    ):
        raise M1CommissioningPersistenceError("exact nonzero workspace source required")
    return _sha256(
        canonical_json_bytes(
            {
                "schema": SOURCE_SCHEMA,
                "composition": PHYSICAL_CAMERA_COMPOSITION,
                "workspace_source_sha256": workspace_source_sha256,
            }
        )
    )


def decode_physical_camera_permit(value: object) -> ExactOperationPermit:
    """Audited data reconstruction only; a saved permit cannot be redeemed."""
    return _decode_domain_permit(value, _PHYSICAL_CAMERA_DOMAIN)


@dataclass(frozen=True, slots=True)
class PhysicalCameraAdmissionFacts(_M1AdmissionFacts):
    """Server-derived admission documents, never browser-authored proof hashes.

    The acquisition service still owns evidence provenance, operator conditions,
    runtime qualification and current stage admission. This type merely freezes
    those exact dependencies and excludes an arm energization envelope.
    """

    def __post_init__(self) -> None:
        _M1AdmissionFacts.__post_init__(self)
        if self.envelope is not None or self._identity is None:
            raise M1CommissioningPersistenceError(
                "camera acquisition requires selected identity and no energy envelope"
            )

    def retained_documents(self) -> dict[str, Any]:
        """Detached originals, not a new assessment or reconstructed live owner."""
        result = {
            "schema": ADMISSION_EVIDENCE_SCHEMA,
            "hazard_assessment": json.loads(self._hazard),
            "configuration_epochs": [json.loads(item) for item in self._epochs],
            "selected_identity": json.loads(self._identity or b"null"),
        }
        if len(canonical_json_bytes(result)) > MAX_ADMISSION_EVIDENCE_BYTES:
            raise M1CommissioningPersistenceError(
                "camera admission evidence exceeds bound"
            )
        return result


def verify_camera_admission_evidence(
    value: object, permit: ExactOperationPermit
) -> None:
    """Audit retained v2 facts against the independently ledger-bound permit.

    Older camera records without this optional family remain historical data.
    The new scoped-facts path requires these originals before result publication.
    Hash joins prove retention consistency, not substantive hazard assessment.
    """
    from .camera_activation_campaign_contract import validate_camera_activation_permit

    validate_camera_activation_permit(permit)
    if (
        type(value) is not dict
        or set(value)
        != {"schema", "hazard_assessment", "configuration_epochs", "selected_identity"}
        or value["schema"] != ADMISSION_EVIDENCE_SCHEMA
        or type(value["configuration_epochs"]) is not list
        or len(value["configuration_epochs"]) != 8
        or len(canonical_json_bytes(value)) > MAX_ADMISSION_EVIDENCE_BYTES
    ):
        raise M1CommissioningPersistenceError(
            "camera admission evidence schema differs"
        )
    admission = permit.admission
    if (
        _sha256(_freeze_document(value["hazard_assessment"]))
        != admission.hazard_assessment_sha256
        or tuple(
            _sha256(_freeze_document(item)) for item in value["configuration_epochs"]
        )
        != admission.configuration_epoch_hashes
        or _sha256(_freeze_document(value["selected_identity"]))
        != admission.selected_identity_sha256
    ):
        raise M1CommissioningPersistenceError(
            "camera original admission facts/hash joins differ"
        )


PhysicalCameraFactsProvider = Callable[
    [RegisteredActionRequest, V2SessionSnapshot], PhysicalCameraAdmissionFacts
]


class M1PhysicalCameraTransaction(_M1CoordinatorTransaction):
    """Stage storage or exact CELL→SESSION→CAMERA acquisition ownership."""

    def __init__(
        self,
        *,
        _fresh_snapshot_verification: (
            Callable[[], tuple[V2SessionSnapshot | None, M1RuntimeVerification]] | None
        ) = None,
        **kwargs: Any,
    ) -> None:
        self._fresh_snapshot_verification = _fresh_snapshot_verification
        self._retain_camera_admission_originals = False
        super().__init__(
            **kwargs,
            domain=_PHYSICAL_CAMERA_DOMAIN,
            facts_type=PhysicalCameraAdmissionFacts,
        )
        snapshot = self.snapshot()
        base = (
            LeaseSpec(LeaseLevel.CELL, snapshot.header.cell_id),
            LeaseSpec(LeaseLevel.SESSION, snapshot.header.session_id),
        )
        if self.held_leases not in (
            base,
            (*base, LeaseSpec(LeaseLevel.CAMERA, snapshot.header.cell_id)),
        ):
            raise M1CommissioningPersistenceError("camera-only lease set required")

    def _admission_observation(
        self,
    ) -> tuple[V2SessionSnapshot, M1RuntimeVerification]:
        # Only the actual M1 runtime supplies this fresh pair. Legacy test and
        # storage compositions keep their independent reads; no cached fallback.
        if self._fresh_snapshot_verification is None:
            return super()._admission_observation()
        return self._coherent_admission_observation(
            self._fresh_snapshot_verification,
            mismatch_message="fresh camera snapshot and runtime verification differ",
        )

    def _validate_admission_subjects(self, permit: ExactOperationPermit) -> None:
        if self._retain_camera_admission_originals:
            if type(self._facts) is not PhysicalCameraAdmissionFacts:
                raise M1CommissioningPersistenceError(
                    "exact camera admission facts required"
                )
            verify_camera_admission_evidence(self._facts.retained_documents(), permit)

    def _reservation_evidence(self) -> dict[str, Any]:
        if not self._retain_camera_admission_originals:
            return {}  # Preserve legacy reservation bytes.
        if type(self._facts) is not PhysicalCameraAdmissionFacts:
            raise M1CommissioningPersistenceError(
                "camera reservation lacks original facts"
            )
        # begin_intent validated these exact freshly read documents against its
        # permit before any write; this method cannot manufacture another set.
        return {"admission_evidence": self._facts.retained_documents()}

    def read_campaign_admission_evidence(self, attempt_id: str) -> dict[str, Any]:
        """Original, audited facts only; absent legacy data cannot be invented."""
        permit = self.read_campaign_permit(attempt_id)
        records = self._audit_records()
        selected = [
            record["data"].get("admission_evidence")
            for name, record in records.items()
            if name.startswith("request-")
            and record["data"]["attempt_id"] == permit.attempt_id
        ]
        if len(selected) != 1 or selected[0] is None:
            raise M1CommissioningPersistenceError(
                "camera original admission evidence unavailable"
            )
        verify_camera_admission_evidence(selected[0], permit)
        return json.loads(canonical_json_bytes(selected[0]))

    def store_camera_mode_entry(
        self,
        payload: bytes,
        *,
        captured_at_ns: int,
        expected_head_sha256: str,
    ) -> EvidenceReference:
        """Retain one closed, file-only camera entry before its opening event.

        Setup independently authenticates the complete original identity chain
        on this same leased transaction. This additional storage guard binds
        its entry to the current header and final review; it is not a substitute
        for that audit. No arbitrary stage, label, media type or device permit
        is accepted. Generic evidence storage keeps its reviewed-stage rule.
        """
        self._require_stage_mutation()
        snapshot = self.snapshot()
        if self.held_leases != (
            LeaseSpec(LeaseLevel.CELL, snapshot.header.cell_id),
            LeaseSpec(LeaseLevel.SESSION, snapshot.header.session_id),
        ):
            raise M1CommissioningPersistenceError(
                "camera entry requires stage-only leases"
            )
        entry = CameraModeEntry(payload)
        document = entry.to_dict()
        binding = document["binding"]
        last = snapshot.committed_events[-1] if snapshot.committed_events else None
        match = USB_COMPLETE_EVENT.fullmatch(last.detail_code) if last else None
        if (
            binding["header_sha256"] != snapshot.header.header_sha256
            or binding["cell_id"] != snapshot.header.cell_id
            or binding["session_id"] != snapshot.header.session_id
            or physical_camera_source_binding(binding["source_sha256"])
            != snapshot.header.source_binding_sha256
            or not all(row.state is V2StageState.PASS for row in snapshot.stages[:4])
            or last is None
            or last.stage is not STAGE_ORDER[3]
            or last.previous_state is not V2StageState.REVIEW_PENDING
            or last.state is not V2StageState.PASS
            or last.event_sha256 != binding["complete_review_event_sha256"]
            or match is None
            or match[1] != "REVIEWED"
            or document["recorded_at_utc_ns"] < last.occurred_at_ns
            or type(captured_at_ns) is not int
            or not document["recorded_at_utc_ns"] <= captured_at_ns < 2**63
        ):
            raise M1CommissioningPersistenceError(
                "camera entry differs from the current complete-review boundary"
            )
        return self._session._store_pending_stage_entry_evidence(
            STAGE_ORDER[4],
            entry.payload,
            label=camera_mode_entry_label(document["entry_id"]),
            media_type="application/json",
            captured_at_ns=captured_at_ns,
            expected_head_sha256=expected_head_sha256,
        )

    def store_camera_probe_review(
        self, payload: bytes, *, captured_at_ns: int, expected_head_sha256: str
    ) -> EvidenceReference:
        """Retain only a closed review of the exact original blocked preparation.

        Setup already authenticates all original predecessors in this same
        stage transaction. This second storage check binds the complete stage-5
        layout and current session before using V2's narrow private primitive.
        No uploaded evidence, arbitrary stage, media, label or permission bit.
        """
        from .camera_probe_preparation import (
            CameraProbePreparation,
            CameraProbePreparationReview,
            camera_probe_label,
            MAX_PREPARATION_BYTES,
        )
        from .physical_camera_mode_entry import MAX_ENTRY_BYTES
        from .camera_probe_preparation_layout import (
            verify_camera_probe_preparation_layout,
            _original_record,
        )

        self._require_stage_mutation()
        snapshot = self.snapshot()
        if self.held_leases != (
            LeaseSpec(LeaseLevel.CELL, snapshot.header.cell_id),
            LeaseSpec(LeaseLevel.SESSION, snapshot.header.session_id),
        ):
            raise M1CommissioningPersistenceError(
                "probe review requires stage-only leases"
            )
        review = CameraProbePreparationReview(payload)
        document = review.to_dict()
        references = [ref for ref in snapshot.evidence if ref.stage is STAGE_ORDER[4]]
        # References bind payload hashes, not labels. The full original reader
        # already checks package labels; select the exact review target by hash.
        prepared = [
            ref
            for ref in references
            if ref.payload_sha256 == document["preparation_sha256"]
        ]
        entries = [
            ref
            for ref in references
            if ref.payload_sha256 != document["preparation_sha256"]
        ]
        if len(references) != 2 or len(prepared) != 1 or len(entries) != 1:
            raise M1CommissioningPersistenceError(
                "exact entry and preparation required; partial review cannot be replayed"
            )
        if (
            not 0 < prepared[0].payload_bytes <= MAX_PREPARATION_BYTES
            or not 0 < entries[0].payload_bytes <= MAX_ENTRY_BYTES
        ):
            raise M1CommissioningPersistenceError(
                "probe review predecessor exceeds its role bound"
            )
        entry = CameraModeEntry(self.read_stage_evidence(entries[0]))
        preparation = CameraProbePreparation(self.read_stage_evidence(prepared[0]))
        data = preparation.to_dict()
        layout = verify_camera_probe_preparation_layout(
            snapshot,
            _original_record(entry, entries[0]),
            {
                prepared[0].evidence_id: dict(
                    kind="preparation",
                    preparation_id=data["preparation_id"],
                    record=_original_record(preparation, prepared[0]),
                )
            },
        )
        if (
            layout.state != "PREPARED_REVIEW_REQUIRED"
            or document["preparation_sha256"] != preparation.sha256
            or data["plan"]["cell_id"] != snapshot.header.cell_id
            or data["plan"]["session_id"] != snapshot.header.session_id
            or physical_camera_source_binding(data["plan"]["source_sha256"])
            != snapshot.header.source_binding_sha256
            or document["reviewed_at_utc_ns"]
            < snapshot.committed_events[-1].occurred_at_ns
            or type(captured_at_ns) is not int
            or not document["reviewed_at_utc_ns"] <= captured_at_ns < 2**63
        ):
            raise M1CommissioningPersistenceError(
                "probe review differs from the exact current preparation"
            )
        return self._session._store_camera_probe_review_evidence(
            review.payload,
            label=camera_probe_label("review", document["preparation_id"]),
            captured_at_ns=captured_at_ns,
            expected_head_sha256=expected_head_sha256,
        )

    def store_camera_operating_submission(
        self, payload: bytes, *, captured_at_ns: int, expected_head_sha256: str
    ) -> EvidenceReference:
        """Retain one closed, file-only proposal/assessment at the reviewed probe.

        The service must authenticate the complete original/native inputs in
        this stage transaction before calling. This additional storage guard
        independently binds the package to its current original inventory and
        exact v16 boundary. It does not approve content or commit a stage event.
        An existing partial submission is not a request to resume/replace it.
        """
        from .camera_operating_submission import (
            CameraOperatingSubmission,
            camera_operating_submission_label,
        )
        from .camera_probe_preparation import (
            CameraProbePreparation,
            CameraProbePreparationReview,
            MAX_PREPARATION_BYTES,
            MAX_REVIEW_BYTES,
        )
        from .camera_probe_preparation_layout import (
            _original_record,
            verify_camera_probe_preparation_layout,
        )
        from .physical_camera_mode_entry import MAX_ENTRY_BYTES
        from rocell.providers.windows.native_camera_protocol import canonical

        self._require_stage_mutation()
        subject = CameraOperatingSubmission(payload)
        document = subject.to_dict()
        binding = document["binding"]
        with self._original_evidence_readback(camera_scope=False) as (snapshot, read):
            references = [
                ref for ref in snapshot.evidence if ref.stage is STAGE_ORDER[4]
            ]
            if (
                len(references) != 3
                or binding["header_sha256"] != snapshot.header.header_sha256
                or binding["cell_id"] != snapshot.header.cell_id
                or binding["session_id"] != snapshot.header.session_id
                or physical_camera_source_binding(binding["source_sha256"])
                != snapshot.header.source_binding_sha256
                or binding["journal_head_sha256"] != snapshot.head.head_sha256
                or expected_head_sha256 != snapshot.head.head_sha256
                or binding["original_records_sha256"]
                != _sha256(canonical(self._audit_records(include_family=True)))
                or type(captured_at_ns) is not int
                or not document["recorded_at_utc_ns"] <= captured_at_ns < 2**63
            ):
                raise M1CommissioningPersistenceError(
                    "operating submission requires the exact current original boundary"
                )
            subjects, refs = {}, {}
            for kind, key, maximum, cls in (
                ("entry", "entry_sha256", MAX_ENTRY_BYTES, CameraModeEntry),
                (
                    "preparation",
                    "probe_preparation_sha256",
                    MAX_PREPARATION_BYTES,
                    CameraProbePreparation,
                ),
                (
                    "review",
                    "probe_review_sha256",
                    MAX_REVIEW_BYTES,
                    CameraProbePreparationReview,
                ),
            ):
                selected = [
                    ref for ref in references if ref.payload_sha256 == binding[key]
                ]
                if len(selected) != 1 or not 0 < selected[0].payload_bytes <= maximum:
                    raise M1CommissioningPersistenceError(
                        "operating submission predecessor is missing or oversized"
                    )
                refs[kind] = selected[0]
                subjects[kind] = cls(read(selected[0]))
            packages = {
                refs[kind].evidence_id: dict(
                    kind=kind,
                    preparation_id=subjects[kind].to_dict()["preparation_id"],
                    record=_original_record(subjects[kind], refs[kind]),
                )
                for kind in ("preparation", "review")
            }
            layout = verify_camera_probe_preparation_layout(
                snapshot, _original_record(subjects["entry"], refs["entry"]), packages
            )
            if (
                layout.state != "REVIEWED_FOR_ADMISSION"
                or len(layout.events) != 2
                or document["recorded_at_utc_ns"] < layout.events[-1].occurred_at_ns
                or canonical(document["proposal"]["entry_binding"])
                != canonical(subjects["entry"].to_dict()["binding"])
            ):
                raise M1CommissioningPersistenceError(
                    "operating submission requires the reviewed probe boundary"
                )
        # The batch has closed and independently rechecked its exact originals.
        # Existing immutable publication rechecks the head again around writing.
        return self._session.store_evidence(
            STAGE_ORDER[4],
            subject.payload,
            label=camera_operating_submission_label(document["submission_id"]),
            media_type="application/json",
            captured_at_ns=captured_at_ns,
            expected_head_sha256=expected_head_sha256,
        )

    def read_stage_evidence(self, reference: EvidenceReference) -> bytes:
        """Read original retained bytes under an active stage-only lease.

        This is not a path reader or evidence admission decision. A freshly
        verified session inventory supplies the only permitted package, and the
        package manifest, payload and ownership are checked again before return.
        The caller must still verify the substantive prerequisite report.
        """
        self._check_scope()
        if type(reference) is not EvidenceReference or (
            type(reference.payload_bytes) is not int
            or not 1 <= reference.payload_bytes <= MAX_EVIDENCE_BYTES
        ):
            raise M1CommissioningPersistenceError(
                "exact bounded evidence reference required"
            )
        snapshot = self.snapshot()
        if self.held_leases != (
            LeaseSpec(LeaseLevel.CELL, snapshot.header.cell_id),
            LeaseSpec(LeaseLevel.SESSION, snapshot.header.session_id),
        ):
            raise M1CommissioningPersistenceError(
                "evidence readback requires stage-only leases"
            )
        return self._read_original_evidence(reference, snapshot)

    @contextmanager
    def _original_evidence_readback(
        self, *, camera_scope: bool
    ) -> Iterator[tuple[V2SessionSnapshot, Callable[[EvidenceReference], bytes]]]:
        """Batch read-only originals under one unchanged, caller-owned scope.

        Whole-store audits bracket the batch, not each package. Each package
        still uses the unchanged guarded original-byte reader. The returned
        callable is deliberately process-local and unusable after context exit;
        its bytes are observations, never admission or permission to act.
        """
        self._check_scope()
        if type(camera_scope) is not bool or getattr(
            self, "_original_readback_active", False
        ):
            raise M1CommissioningPersistenceError(
                "exact non-nested original readback scope required"
            )
        self._original_readback_active = True
        active = False
        try:
            snapshot = self.snapshot()
            required: tuple[LeaseSpec, ...] = (
                LeaseSpec(LeaseLevel.CELL, snapshot.header.cell_id),
                LeaseSpec(LeaseLevel.SESSION, snapshot.header.session_id),
            )
            if camera_scope:
                required += (LeaseSpec(LeaseLevel.CAMERA, snapshot.header.cell_id),)

            def check() -> None:
                self._check_scope()
                if self.held_leases != required:
                    raise M1CommissioningPersistenceError(
                        "original readback requires unchanged exact leases"
                    )

            check()
            # Include sibling domains, not only camera-capture records. A
            # record-only change cannot hide behind unchanged session events.
            records = canonical_json_bytes(self._audit_records(include_family=True))
            attempts = self._attempts.snapshot()
            quarantine = self._quarantine.snapshot()
            check()
            seen: set[str] = set()
            active = True

            def read(reference: EvidenceReference) -> bytes:
                if not active:
                    raise M1CommissioningPersistenceError(
                        "original readback scope has ended"
                    )
                check()
                if (
                    type(reference) is not EvidenceReference
                    or type(reference.payload_bytes) is not int
                    or not 1 <= reference.payload_bytes <= MAX_EVIDENCE_BYTES
                    or reference.evidence_id in seen
                ):
                    raise M1CommissioningPersistenceError(
                        "exact bounded, unread evidence reference required"
                    )
                payload = self._read_original_evidence(reference, snapshot)
                check()
                seen.add(reference.evidence_id)
                return payload

            yield snapshot, read
            check()
            # Do not mask a body exception with another full audit. On normal
            # exit, no result is released until every closing check succeeds.
            ending_records = canonical_json_bytes(
                self._audit_records(include_family=True)
            )
            if (
                ending_records != records
                or self._attempts.snapshot() != attempts
                or self._quarantine.snapshot() != quarantine
                or self.snapshot() != snapshot
            ):
                raise M1CommissioningPersistenceError(
                    "original readback store changed during batch"
                )
            check()
        finally:
            active = False
            self._original_readback_active = False

    def read_camera_evidence(self, reference: EvidenceReference) -> bytes:
        """Read an original package while exact camera ownership remains held.

        This is a read-only, inventory-bound companion to read_stage_evidence,
        not a path reader, facts approval, permit consumption or native release.
        The caller must independently validate the retained document's meaning.
        """
        self._check_scope()
        if type(reference) is not EvidenceReference or (
            type(reference.payload_bytes) is not int
            or not 1 <= reference.payload_bytes <= MAX_EVIDENCE_BYTES
        ):
            raise M1CommissioningPersistenceError(
                "exact bounded evidence reference required"
            )
        snapshot = self.snapshot()
        required_leases = (
            LeaseSpec(LeaseLevel.CELL, snapshot.header.cell_id),
            LeaseSpec(LeaseLevel.SESSION, snapshot.header.session_id),
            LeaseSpec(LeaseLevel.CAMERA, snapshot.header.cell_id),
        )
        if self.held_leases != required_leases:
            raise M1CommissioningPersistenceError(
                "evidence readback requires exact camera leases"
            )
        self._audit_records()
        if self.held_leases != required_leases:
            raise M1CommissioningPersistenceError(
                "camera leases changed before evidence readback"
            )
        payload = self._read_original_evidence(reference, snapshot)
        if self.held_leases != required_leases:
            raise M1CommissioningPersistenceError(
                "camera leases changed during evidence readback"
            )
        return payload

    def _read_original_evidence(
        self, reference: EvidenceReference, snapshot: V2SessionSnapshot
    ) -> bytes:
        """Shared guarded original-byte checks after the public lease boundary."""
        selected = next((item for item in snapshot.evidence if item == reference), None)
        if selected is None or canonical_json_bytes(
            selected.to_dict()
        ) != canonical_json_bytes(reference.to_dict()):
            raise M1CommissioningPersistenceError(
                "evidence is not in the original session snapshot"
            )
        # Derive the path from the verified inventory, never a caller path.
        directory = self._session.directory / "evidence" / selected.evidence_id
        with _directory_guard(directory):
            if _verify_evidence_directory(directory, snapshot.header) != selected:
                raise M1CommissioningPersistenceError(
                    "evidence package changed before readback"
                )
            payload = read_bounded_regular_file(
                directory / "payload.bin",
                maximum_bytes=selected.payload_bytes,
                label="original camera stage evidence",
            )
            if (
                len(payload) != selected.payload_bytes
                or _sha256(payload) != selected.payload_sha256
            ):
                raise M1CommissioningPersistenceError(
                    "evidence payload changed during readback"
                )
            if _verify_evidence_directory(directory, snapshot.header) != selected:
                raise M1CommissioningPersistenceError(
                    "evidence package changed during readback"
                )
            self._check_scope()
        self._check_scope()
        return payload

    def read_campaign_result(self, attempt_id: str) -> AttemptResult:
        """Restore the exact latest durable terminal result; never redeem it.

        A result saved before a failed seal is not completed merely because its
        bytes exist. Original records and the latest attempt event must agree.
        Like the existing permit/evidence readers, this is scoped private data,
        not substantive camera qualification or a new admission decision.
        """
        self._check_scope()
        if (
            type(attempt_id) is not str
            or re.fullmatch(r"attempt-[0-9a-f]{32}", attempt_id) is None
        ):
            raise M1CommissioningPersistenceError("exact retained attempt ID required")
        leases = self.held_leases
        records = self._audit_records()
        latest = self._attempts.snapshot().latest_event(attempt_id)
        terminal = {
            AttemptState.SEALED_KNOWN,
            AttemptState.SEALED_UNCERTAIN,
            AttemptState.ABORTED_PRE_EFFECT,
        }
        if latest is None or latest.state not in terminal:
            raise M1CommissioningPersistenceError(
                "retained campaign has no matching durable terminal state"
            )
        requests = [
            record["data"]["permit"]
            for name, record in records.items()
            if name.startswith("request-")
            and record["data"]["attempt_id"] == attempt_id
        ]
        record = records.get(f"result-{attempt_id}-{latest.state.value.lower()}.json")
        if len(requests) != 1 or record is None:
            raise M1CommissioningPersistenceError(
                "retained campaign result is missing or ambiguous"
            )
        permit = _decode_domain_permit(requests[0], self._domain)
        data = _exact_dataclass(record["data"]["result"], AttemptResult)
        if (
            latest.operation_binding_sha256 != permit.permit_sha256
            or latest.session_id != permit.request.session_id
            or latest.cell_id != permit.request.cell_id
            or latest.source_binding_sha256 != permit.admission.source_binding_sha256
            or data["state"] != latest.state.value
            or data["attempt_id"] != permit.attempt_id
            or data["permit_sha256"] != permit.permit_sha256
            or data["composition"] != PHYSICAL_CAMERA_COMPOSITION
            or data["physical_authority"] != "NONE"
        ):
            raise M1CommissioningPersistenceError(
                "retained result differs from its original terminal attempt"
            )
        data["state"] = latest.state
        data["reason_codes"] = tuple(data["reason_codes"])
        if data["receipt"] is not None:
            data["receipt"] = self._decode_receipt(data["receipt"])
            receipt = data["receipt"]
            if (
                receipt.attempt_id != permit.attempt_id
                or receipt.permit_sha256 != permit.permit_sha256
                or receipt.composition != PHYSICAL_CAMERA_COMPOSITION
                or receipt.worker_executable_sha256
                != permit.registration.worker_executable_sha256
                or receipt.selected_identity_sha256
                != permit.admission.selected_identity_sha256
            ):
                raise M1CommissioningPersistenceError(
                    "retained result receipt differs from its original permit"
                )
        result = AttemptResult(**data)
        # Audit already validates the full known receipt and retained campaign
        # equality. Keep unsuccessful original cleanup/effect observations as-is.
        if self._attempts.snapshot().latest_event(attempt_id) != latest:
            raise M1CommissioningPersistenceError(
                "retained campaign terminal state changed during readback"
            )
        if self.held_leases != leases:
            raise M1CommissioningPersistenceError(
                "camera transaction leases changed during result readback"
            )
        return result


class M1PhysicalCameraPersistence:
    """Qualified storage composition, not a device provider or startup action."""

    composition = PHYSICAL_CAMERA_COMPOSITION

    def __init__(
        self,
        runtime: PhysicalOnboardingM1Runtime,
        *,
        workspace_source_sha256: str,
        admission_facts: PhysicalCameraFactsProvider | None = None,
        scoped_admission_facts: (
            Callable[
                [
                    M1PhysicalCameraTransaction,
                    RegisteredActionRequest,
                    V2SessionSnapshot,
                ],
                PhysicalCameraAdmissionFacts,
            ]
            | None
        ) = None,
    ) -> None:
        from .physical_onboarding_m1 import PhysicalOnboardingM1Runtime

        if (
            type(runtime) is not PhysicalOnboardingM1Runtime
            or re.fullmatch(_PHYSICAL_CAMERA_DOMAIN.cell_pattern, runtime.cell.cell_id)
            is None
            or runtime.source_binding_sha256
            != physical_camera_source_binding(workspace_source_sha256)
            or (admission_facts is None) == (scoped_admission_facts is None)
            or (admission_facts is not None and not callable(admission_facts))
            or (
                scoped_admission_facts is not None
                and not callable(scoped_admission_facts)
            )
        ):
            raise M1CommissioningPersistenceError(
                "camera persistence requires its exact M1 namespace/source and facts"
            )
        self._runtime, self._facts = runtime, admission_facts
        self._scoped_facts = scoped_admission_facts

    @property
    def requires_original_admission_evidence(self) -> bool:
        """Policy of this server-created composition, not a browser release flag."""
        return self._scoped_facts is not None

    def snapshot(self, session_id: str) -> V2SessionSnapshot:
        if (
            type(session_id) is not str
            or re.fullmatch(_PHYSICAL_CAMERA_DOMAIN.session_pattern, session_id) is None
        ):
            raise M1CommissioningPersistenceError("camera session namespace required")
        snapshot = self._runtime.session_snapshot(session_id)
        if snapshot.header.mode != "PHYSICAL_DIAGNOSTIC":
            raise M1CommissioningPersistenceError("camera session mode differs")
        return snapshot

    def verification(self, session_id: str) -> M1RuntimeVerification:
        self.snapshot(session_id)
        return self._runtime.verify(session_id)

    @contextmanager
    def stage_transaction(
        self, session_id: str, *, expected_challenge_sha256: str
    ) -> Iterator[M1PhysicalCameraTransaction]:
        with self._runtime.physical_camera_transaction(
            session_id, expected_challenge_sha256=expected_challenge_sha256
        ) as transaction:
            transaction._audit_records()
            yield transaction

    @contextmanager
    def transaction(
        self, leases: tuple[LeaseSpec, ...]
    ) -> Iterator[M1PhysicalCameraTransaction]:
        if (
            type(leases) is not tuple
            or len(leases) != 3
            or any(type(spec) is not LeaseSpec for spec in leases)
            or leases[0] != LeaseSpec(LeaseLevel.CELL, self._runtime.cell.cell_id)
            or leases[1].level is not LeaseLevel.SESSION
            or leases[2] != LeaseSpec(LeaseLevel.CAMERA, self._runtime.cell.cell_id)
        ):
            raise M1CommissioningPersistenceError(
                "acquisition requires exact CELL then SESSION then CAMERA leases"
            )
        with self._runtime.physical_camera_transaction(
            leases[1].resource_id, device_levels=(LeaseLevel.CAMERA,)
        ) as transaction:
            if transaction.held_leases != leases:
                raise M1CommissioningPersistenceError("actual camera leases differ")
            scoped_facts = self._scoped_facts
            if scoped_facts is None:
                transaction._facts_provider = self._facts
            else:
                # Capture THIS actual scope, never a previous transaction or a
                # synthetic snapshot owner. Existing core callback shape stays.
                def facts(request, snapshot):
                    transaction._check_scope()
                    result = scoped_facts(transaction, request, snapshot)
                    transaction._check_scope()
                    return result

                transaction._retain_camera_admission_originals = True
                transaction._facts_provider = facts
            yield transaction
