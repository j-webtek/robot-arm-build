"""Simulation-only five-leg recovery flow with raw-record export-before-receipt."""
from pathlib import Path

from .characterization_http_session import CharacterizationHTTPSession
from .reviewed_hover_recovery_admission import (
    encode_recovery_admission, recovery_manifest, validate_recovery_manifest,
)
from .reviewed_hover_recovery_record import assess_recovery_leg
from .reviewed_hover_simulated_host import ReviewedHoverSimulatedHost


class ReviewedHoverRecoverySimulatedHost(ReviewedHoverSimulatedHost):
    route = "/rocell/recovery-hover/"
    completed_status = "REVIEWED_HOVER_RECOVERY_SIMULATED_COMPLETE"
    leg_export_mode = "reviewed-hover-recovery-simulated-leg"
    fault_export_mode = "reviewed-hover-recovery-simulated-fault"
    fault_schema = "rocell.reviewed_hover_recovery_simulated_fault.v1"
    stopped_message = "Simulated recovery stopped; evidence: "

    def __init__(self, transport, *, boot: str, key: bytes,
                 release_sha256: str, export_root: Path):
        if getattr(transport, "simulation_only", False) is not True:
            raise ValueError("Simulation-only transport required")
        self.transport = transport
        self.manifest = recovery_manifest()
        self.reviewed = dict(manifest_sha256=validate_recovery_manifest(self.manifest),
                             pose_ids=self.manifest["pose_ids"], leg_count=5)
        self.boot = boot
        self.release_sha256 = release_sha256
        self.root = Path(export_root).resolve()
        self.session = CharacterizationHTTPSession(key=key, boot=boot)
        self.used = False
        # Validate all admission fields before any write or export.
        self._start_body()

    def _start_body(self) -> bytes:
        return encode_recovery_admission(self.manifest, boot=self.boot,
            release_sha256=self.release_sha256, authorize_noncontact_motion=True)

    def _assess_leg(self, raw: bytes, leg: int, previous: dict | None) -> dict:
        return assess_recovery_leg(raw, boot=self.boot, leg=leg, previous=previous)
