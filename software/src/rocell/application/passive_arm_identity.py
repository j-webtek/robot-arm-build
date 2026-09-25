"""Exact metadata recheck for the USB-only bench lane, not firmware identity.

Reuse the wizard's full correlation instead of constructing the stronger
ReviewedControllerBinding with invented firmware/boot evidence. This module
performs no enumeration or serial I/O; its caller owns collection, provenance,
one-use admission and the final check immediately before opening.
"""

from dataclasses import dataclass
import json

from . import wizard_native_arm_metadata as metadata


MAX_RECHECK_AGE_NS = 1_000_000_000


@dataclass(frozen=True, slots=True)
class PassiveControllerSelection:
    """Immutable original metadata selection, explicitly not an open permit."""

    payload: bytes

    def __post_init__(self):
        # Fully reconstruct the report: a caller-modified PASS flag is not enough.
        value = metadata._owned(self.payload, metadata.MAX_REPORT_BYTES)
        summary = metadata.summarize_native_arm_metadata(value)
        if summary["status"] != "METADATA_CORRELATED":
            raise ValueError("Correlated original metadata required")
        object.__setattr__(self, "payload", metadata._canonical(value))

    def recheck(
        self,
        snapshot,
        generic_review,
        *,
        mode,
        session_id,
        source_sha256,
        operation_id,
        collection_not_before_ns,
        now_monotonic_ns,
    ) -> dict:
        """Compare a fresh collection to the exact original mapping and driver.

        COM changes require a new explicit selection, not a fallback. This still
        cannot atomically tie a later Windows handle to a USB device. A matching
        synthetic collection always remains rehearsal-only.
        """
        for value in (collection_not_before_ns, now_monotonic_ns):
            if type(value) is not int or not 0 < value < 2**63:
                raise ValueError("Valid live-launch clock observations required")
        original = json.loads(self.payload)
        fresh = metadata.correlate_native_arm_metadata(
            snapshot,
            generic_review,
            mode=mode,
            session_id=session_id,
            source_sha256=source_sha256,
            operation_id=operation_id,
        )
        blockers = list(fresh["blockers"])
        for field in ("mode", "session_id", "source_sha256", "generic_review_sha256"):
            if original["binding"][field] != fresh["binding"][field]:
                blockers.append("ORIGINAL_" + field.upper() + "_MISMATCH")
        if original["native_observation_sha256"] != fresh["native_observation_sha256"]:
            blockers.append("NATIVE_MAPPING_OR_DRIVER_CHANGED")
        observed = fresh["snapshot"]
        started, finished = (
            observed["started_monotonic_ns"],
            observed["finished_monotonic_ns"],
        )
        if not (
            collection_not_before_ns <= started <= finished <= now_monotonic_ns
            and now_monotonic_ns - finished <= MAX_RECHECK_AGE_NS
        ):
            blockers.append("FRESH_COLLECTION_REQUIRED")
        # The old selection must not be passed off as a newly acquired snapshot.
        if started <= original["snapshot"]["finished_monotonic_ns"]:
            blockers.append("COLLECTION_NOT_AFTER_ORIGINAL")
        if operation_id == original["binding"]["operation_id"]:
            blockers.append("NEW_OPERATION_REQUIRED")
        blockers = sorted(set(blockers))
        return {
            "schema": "rocell.passive_arm_identity_recheck.v1",
            "status": "HELD" if blockers else "METADATA_RECHECK_MATCHED",
            "mode": mode,
            "blockers": blockers,
            "original_report_sha256": original["report_sha256"],
            "fresh_report": fresh,
            # No endpoint is exposed on mismatch, even if COM alone still exists.
            "candidate_port": (
                None
                if blockers
                else fresh["reviewed_generic_candidate"][
                    "ephemeral_locator_observation"
                ]
            ),
            "firmware": "UNKNOWN",
            "model_verification": "NOT_PERFORMED_BY_USB_METADATA",
            "atomic_handle_identity": False,
            "references_authenticated": False,
            "physical_authority": False,
            "connected": False,
            "physical_dispatch_available": False,
        }
