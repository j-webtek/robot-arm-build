"""Shared signed, no-retry reviewed-hover campaign flow.

The base accepts only a simulation-declared transport; the loopback subclass
uses a local authenticated socket. A separately gated live subclass reuses
the per-leg verification and export-before-receipt sequence.
"""
from __future__ import annotations

import time
from pathlib import Path

from .characterization_http_session import CharacterizationHTTPSession
from .characterization_http import CharacterizationHTTP
from .first_motion_contract import canonical
from .reviewed_hover_manifest import encode_reviewed_hover_start, validate_manifest
from .reviewed_hover_record import RECORD_BYTES, assess_reviewed_hover_leg
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


class ReviewedHoverSimulatedHost:
    route = "/rocell/reviewed-hover/"
    source_kind = "simulation"
    completed_status = "REVIEWED_HOVER_SIMULATED_COMPLETE"
    leg_export_mode = "reviewed-hover-simulated-leg"
    fault_export_mode = "reviewed-hover-simulated-fault"
    fault_schema = "rocell.reviewed_hover_simulated_fault.v1"
    hardware_access = False
    motion_authorized = False
    stopped_message = "Simulated campaign stopped; evidence: "
    receipt_count_field = "simulated_receipts_sent"

    def __init__(self, transport, *, manifest: dict, boot: str, key: bytes,
                 export_root: Path):
        if getattr(transport, "simulation_only", False) is not True:
            raise ValueError("Simulation-only transport required")
        self.transport = transport
        self.manifest = manifest
        self.reviewed = validate_manifest(manifest)
        self.boot = boot
        self.root = Path(export_root).resolve()
        self.session = CharacterizationHTTPSession(key=key, boot=boot)
        self.used = False

    def _start_body(self) -> bytes:
        return encode_reviewed_hover_start(self.manifest)

    def _assess_leg(self, raw: bytes, leg: int, previous: dict | None) -> dict:
        return assess_reviewed_hover_leg(raw, manifest=self.manifest,
            boot=self.boot, leg=leg, previous=previous)

    def _reserve_before_start(self, exporter: WizardDiagnosticExporter) -> None:
        pass

    def run_once(self, *, clock=time.monotonic, pause=time.sleep) -> dict:
        return self._run_once(clock=clock, pause=pause, stop_after_leg=None)

    def _run_once(self, *, clock, pause, stop_after_leg: int | None) -> dict:
        if stop_after_leg is not None and stop_after_leg not in (1, 4):
            raise ValueError("Only reviewed first-leg or A-cycle stop allowed")
        if self.used:
            raise ValueError("One-use reviewed-hover host consumed")
        self.used = True
        exporter = WizardDiagnosticExporter(self.root)
        exporter.prepare(create=True)
        self._reserve_before_start(exporter)
        rows: list[dict] = []
        exports: list[str] = []
        raw = b""
        leg = 0
        last_status = None

        def call(method: str, suffix: str, body: bytes = b"") -> bytes:
            verified_socket = getattr(self, "_verified_socket", None)
            if verified_socket is not None:
                return verified_socket(method, self.route + suffix, body)
            request = self.session.request(method, self.route + suffix, body)
            try:
                response = self.transport(request)
                if type(response) is not dict or set(response) != {
                        "status", "body", "sequence", "signature"}:
                    raise ValueError("Invalid signed response envelope")
                return self.session.response(**response)
            except Exception:
                self.session.delivery_uncertain()
                raise

        try:
            if call("POST", "start", self._start_body()) != b"CAPTURING_START":
                raise ValueError("Start response uncertain; no retry")
            for leg in range(1, self.reviewed["leg_count"] + 1):
                raw = b""
                deadline = clock() + 14
                while True:
                    if clock() >= deadline:
                        raise TimeoutError("Leg status deadline")
                    status = call("GET", "status")
                    last_status = status.decode("ascii", "replace")
                    if status == f"AWAITING_EXPORT|{leg}".encode():
                        break
                    if status not in (f"CAPTURING_START|{leg}".encode(),
                                      f"PREWRITE|{leg}".encode(),
                                      f"CAPTURING_ENDPOINT|{leg}".encode()):
                        raise ValueError("Unexpected reviewed-hover status")
                    pause(0.1)
                encoded = call("GET", "record")
                if (type(encoded) is not bytes or len(encoded) != 2 * RECORD_BYTES):
                    raise ValueError("Record framing invalid")
                try:
                    raw = bytes.fromhex(encoded.decode("ascii"))
                except (UnicodeError, ValueError) as error:
                    raise ValueError("Record hex invalid") from error
                if encoded != raw.hex().encode("ascii"):
                    raise ValueError("Noncanonical record hex")
                row = self._assess_leg(raw, leg, rows[-1] if rows else None)
                row["source_kind"] = self.source_kind
                # Poll count is timing-dependent. Preserve the verified next
                # sequence with every exported leg; never ask a later process
                # to guess it after an interruption.
                row["authenticated_next_sequence"] = self.session._sequence
                row["last_controller_status"] = last_status
                saved = exporter.export({"mode": self.leg_export_mode}, [],
                    attachments={
                        "reviewed-hover-record.hex.txt": encoded,
                        "reviewed-hover-assessment.json": canonical(row),
                    })
                if not verify_export(Path(saved["path"]))["valid"]:
                    raise ValueError("Leg export invalid")
                exports.append(saved["path"])
                if stop_after_leg == leg:
                    rows.append(row)
                    status = ("FIRST_LEG_EXPORTED_AWAITING_RECEIPT" if leg == 1 else
                              "A_CYCLE_EXPORTED_AWAITING_RECEIPT")
                    return dict(status=status,
                                rows=rows, exports=exports,
                                **{self.receipt_count_field: leg - 1},
                                hardware_access=self.hardware_access,
                                motion_authorized=self.motion_authorized,
                                continuation_allowed=False,
                                authenticated_next_sequence=self.session._sequence,
                                last_controller_status=last_status)
                receipt = f'{leg}:{row["record_sha256"]}'.encode("ascii")
                expected = (b"COMPLETE" if leg == self.reviewed["leg_count"]
                            else f"READY|{leg + 1}".encode())
                if call("POST", "receipt", receipt) != expected:
                    raise ValueError("Receipt response uncertain; no retry")
                rows.append(row)
                if leg < self.reviewed["leg_count"]:
                    if call("POST", "next", str(leg + 1).encode()) != b"CAPTURING_START":
                        raise ValueError("Next admission uncertain; no retry")
            return dict(status=self.completed_status, rows=rows,
                        exports=exports, **{self.receipt_count_field: len(rows)},
                        hardware_access=self.hardware_access,
                        motion_authorized=self.motion_authorized)
        except Exception as error:
            saved = exporter.export({"mode": self.fault_export_mode}, [],
                attachments={
                    "reviewed-hover-fault.json": canonical(dict(
                        schema=self.fault_schema,
                        failed_leg=leg, completed_legs=len(rows),
                        prior_exports=exports, last_status=last_status,
                        error_type=type(error).__name__,
                        transport_uncertainty=self.session.uncertainty,
                        retry_allowed=False, source_kind=self.source_kind)),
                    "reviewed-hover-fault-record.hex.txt": raw.hex().encode("ascii"),
                })
            if not verify_export(Path(saved["path"]))["valid"]:
                raise ValueError("Fault export invalid") from error
            raise ValueError(self.stopped_message + saved["path"]) from error


class ReviewedHoverLoopbackHost(ReviewedHoverSimulatedHost):
    """Full campaign over authenticated HTTP, restricted to loopback tests."""

    def __init__(self, client: CharacterizationHTTP, *, manifest: dict,
                 boot: str, export_root: Path):
        if (type(client) is not CharacterizationHTTP or client.address != "127.0.0.1"
                or client.read_only_only or client.session.stopped
                or client.session._sequence != 0 or client.session._pending
                or client.session._boot != boot):
            raise ValueError("Fresh authenticated loopback client required")
        self._verified_socket = client
        self.transport = None
        self.manifest = manifest
        self.reviewed = validate_manifest(manifest)
        self.boot = boot
        self.root = Path(export_root).resolve()
        self.session = client.session
        self.used = False
