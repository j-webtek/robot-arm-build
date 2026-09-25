"""One-use reviewed-hover host runner; construction performs no device I/O.

This library does not expose a CLI. A caller must independently verify the
installed image, fresh controller boot, physical clearance, and source pose
before constructing a live transport and authorizing noncontact motion.
"""

from pathlib import Path

from .characterization_http import CharacterizationHTTP
from .first_motion_contract import canonical
from .physical_onboarding_durability import publish_reservation_bytes
from .reviewed_hover_live_admission import encode_live_admission
from .reviewed_hover_manifest import ghost_key_manifest, validate_manifest
from .reviewed_hover_simulated_host import ReviewedHoverSimulatedHost
from .wizard_diagnostic_export import verify_export


R89_APP_SHA = "89c0d91334ab4362d392a3e3e66433c216d7e1740842dbba1b87881b722236b0"
R89_RELEASE_SHA = "653729599a9ba29baed5095b3ed156810b38396065a0b6a3a06fe6c7dd74ab1a"
R90_APP_SHA = "f3d5705b16eedfd49b11fec668da1709eee71d50345ceb07eadf26f0384fe129"
R90_RELEASE_SHA = "65f0106f05de4e8edf68fbd7729a807ebab179c4b86b9e5e37bba5dca9d7a538"
REVIEWED_RELEASES = {R89_RELEASE_SHA: R89_APP_SHA,
                     R90_RELEASE_SHA: R90_APP_SHA}


class ReviewedHoverLiveHost(ReviewedHoverSimulatedHost):
    source_kind = "live_controller"
    completed_status = "REVIEWED_HOVER_LIVE_COMPLETE"
    leg_export_mode = "reviewed-hover-live-leg"
    fault_export_mode = "reviewed-hover-live-fault"
    fault_schema = "rocell.reviewed_hover_live_fault.v1"
    hardware_access = True
    motion_authorized = True
    stopped_message = "Live campaign stopped; evidence: "
    receipt_count_field = "receipts_sent"

    def run_first_leg_only(self, *, clock=None, pause=None) -> dict:
        """One physical leg, verified export, no receipt or continuation.

        The controller remains in AWAITING_EXPORT for this consumed boot. A
        subsequent campaign requires a separately reviewed startup.
        """
        import time
        return self._run_once(clock=clock or time.monotonic,
                              pause=pause or time.sleep,
                              stop_after_leg=1)

    def run_a_cycle_only(self, *, clock=None, pause=None) -> dict:
        """Four noncontact A legs, ending at A_CLEAR without a fourth receipt."""
        import time
        return self._run_once(clock=clock or time.monotonic,
                              pause=pause or time.sleep,
                              stop_after_leg=4)

    def __init__(self, client: CharacterizationHTTP, *, boot: str,
                 export_root: Path, authorize_noncontact_motion: bool,
                 release_sha256: str = R89_RELEASE_SHA):
        manifest = ghost_key_manifest()
        reviewed = validate_manifest(manifest)
        if (authorize_noncontact_motion is not True or
                type(client) is not CharacterizationHTTP or
                client.read_only_only or client.session.stopped or
                client.session._pending or client.session._sequence != 0 or
                client.session._boot != boot or
                release_sha256 not in REVIEWED_RELEASES or
                client.reviewed_hover_live_release_sha256 != release_sha256):
            raise ValueError("Fresh reviewed live release/session and authorization required")
        self._verified_socket = client
        self.transport = None
        self.manifest = manifest
        self.reviewed = reviewed
        self.boot = boot
        self.root = Path(export_root).resolve()
        self.release_sha256 = release_sha256
        self.app_sha256 = REVIEWED_RELEASES[release_sha256]
        self.session = client.session
        self.used = False

    def _start_body(self) -> bytes:
        return encode_live_admission(self.manifest, boot=self.boot,
            release_sha256=self.release_sha256, authorize_noncontact_motion=True)

    def _reserve_before_start(self, exporter) -> None:
        marker = self.root / f"reviewed-hover-live-{self.boot}.json"
        if marker.exists():
            raise ValueError("Live boot already claimed")
        intent = dict(schema="rocell.reviewed_hover_live_intent.v1",
                      boot_id=self.boot, app_sha256=self.app_sha256,
                      release_sha256=self.release_sha256,
                      manifest_sha256=self.reviewed["manifest_sha256"],
                      leg_count=self.reviewed["leg_count"],
                      noncontact_only=True, retry_allowed=False)
        saved = exporter.export({"mode": "reviewed-hover-live-intent"}, [],
                                attachments={"reviewed-hover-live-intent.json":
                                             canonical(intent)})
        if not verify_export(Path(saved["path"]))["valid"]:
            raise ValueError("Live intent export failed")
        publish_reservation_bytes(self.root, marker.name,
                                  canonical(dict(intent_export=Path(saved["path"]).name,
                                                 **intent)), maximum_bytes=2048)
