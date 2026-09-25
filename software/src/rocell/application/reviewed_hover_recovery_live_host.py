"""Release-pinned r91 recovery runner. Construction performs no device I/O.

The caller must independently verify installed app, fresh boot, current
A_HOVER source pose, clearance, and the consequences of startup torque loss.
This module exposes no CLI and never retries uncertain delivery.
"""
from pathlib import Path

from .characterization_http import CharacterizationHTTP
from .first_motion_contract import canonical
from .physical_onboarding_durability import publish_reservation_bytes
from .reviewed_hover_recovery_simulated_host import (
    ReviewedHoverRecoverySimulatedHost,
)
from .reviewed_hover_recovery_admission import (
    recovery_manifest, validate_recovery_manifest,
)
from .wizard_diagnostic_export import verify_export


R91_APP_SHA = "d69438a1a3483ba6105e2bc5f939dd04c58ee9a197bb28332cb42dc627b7e65f"
R91_RELEASE_SHA = "376f50bb4b372608bbb5eb488229d883fc0ff802cf47b1a53dbccad2cf4942d6"


class ReviewedHoverRecoveryLiveHost(ReviewedHoverRecoverySimulatedHost):
    source_kind = "live_controller"
    completed_status = "REVIEWED_HOVER_RECOVERY_LIVE_COMPLETE"
    leg_export_mode = "reviewed-hover-recovery-live-leg"
    fault_export_mode = "reviewed-hover-recovery-live-fault"
    fault_schema = "rocell.reviewed_hover_recovery_live_fault.v1"
    hardware_access = True
    motion_authorized = True
    stopped_message = "Live recovery stopped; evidence: "
    receipt_count_field = "receipts_sent"

    def __init__(self, client: CharacterizationHTTP, *, boot: str,
                 export_root: Path, authorize_noncontact_motion: bool,
                 app_sha256: str = R91_APP_SHA,
                 release_sha256: str = R91_RELEASE_SHA):
        if (authorize_noncontact_motion is not True or
                type(client) is not CharacterizationHTTP or
                client.read_only_only or client.session.stopped or
                client.session._pending or client.session._sequence != 0 or
                client.session._boot != boot or
                app_sha256 != R91_APP_SHA or release_sha256 != R91_RELEASE_SHA or
                client.recovery_hover_live_release_sha256 != R91_RELEASE_SHA or
                client.reviewed_hover_live_release_sha256 is not None):
            raise ValueError("Fresh exact r91 app/release/session required")
        self._verified_socket = client
        self.transport = None
        self.manifest = recovery_manifest()
        self.reviewed = dict(
            manifest_sha256=validate_recovery_manifest(self.manifest),
            pose_ids=self.manifest["pose_ids"], leg_count=5)
        self.boot = boot
        self.release_sha256 = R91_RELEASE_SHA
        self.app_sha256 = R91_APP_SHA
        self.root = Path(export_root).resolve()
        self.session = client.session
        self.used = False
        self._start_body()

    def _reserve_before_start(self, exporter) -> None:
        marker = self.root / f"recovery-hover-live-{self.boot}.json"
        if marker.exists():
            raise ValueError("Live recovery boot already claimed")
        intent = dict(schema="rocell.reviewed_hover_recovery_live_intent.v1",
                      boot_id=self.boot, app_sha256=self.app_sha256,
                      release_sha256=self.release_sha256,
                      manifest_sha256=self.reviewed["manifest_sha256"],
                      leg_count=5, source_pose="A_HOVER",
                      noncontact_only=True, retry_allowed=False)
        saved = exporter.export({"mode": "reviewed-hover-recovery-live-intent"}, [],
            attachments={"reviewed-hover-recovery-live-intent.json": canonical(intent)})
        if not verify_export(Path(saved["path"]))["valid"]:
            raise ValueError("Live recovery intent export failed")
        publish_reservation_bytes(self.root, marker.name,
            canonical(dict(intent_export=Path(saved["path"]).name, **intent)),
            maximum_bytes=2048)
