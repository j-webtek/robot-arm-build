"""One-endpoint, one-query Win32 facade for the future supervised live worker.

Construction is inert and held. Entry requires a live child claim, unchanged
originals and fresh endpoint correlation. The source-pinned supervisor must
independently admit its runtime before invoking this trusted-process boundary.
It is not a sandbox against arbitrary Python running in the same process.
"""

import base64
import hashlib
import time
from threading import Lock

from .nonpurging_serial_api import (
    WindowsNativeSerialApi,
    NativeSerialError,
    _validate_com_path,
    validate_native_io_token,
    validate_owned_pending_io,
)


class WindowsPoweredFeedbackSerialApi(WindowsNativeSerialApi):
    __slots__ = (
        "_expected_path",
        "_request",
        "_fresh_until",
        "_open_attempted",
        "_open_lock",
        "_write_lock",
        "_write_token",
    )

    def __init__(self, port_name):
        if type(port_name) is not str:
            raise NativeSerialError("EXACT_COM_PATH_REQUIRED", "powered_construction")
        self._expected_path = "\\\\.\\" + port_name
        _validate_com_path(self._expected_path)
        super().__init__()
        self._request = None
        self._fresh_until = 0
        self._open_attempted = False
        self._open_lock = Lock()
        self._write_lock = Lock()
        self._write_token = None

    @classmethod
    def from_live_claim(
        cls,
        *,
        root,
        claim,
        binding,
        fresh_snapshot,
        collection_not_before_ns,
        metadata_operation_id,
        current_source_sha256,
    ):
        from rocell.application.powered_feedback_child_claim import (
            consume_live_claim,
            _read,
        )
        from rocell.application.powered_feedback_attempt_store import attempt_path
        from rocell.application.powered_arm_feedback_preparation import (
            prepare_powered_feedback,
        )
        from rocell.application.arm_bench_qualification_contract import _canonical
        from rocell.application.wizard_diagnostic_coordinator import (
            decode_diagnostic_json,
        )
        from .powered_feedback_binding import PoweredFeedbackBinding

        if (
            cls is not WindowsPoweredFeedbackSerialApi
            or type(binding) is not PoweredFeedbackBinding
        ):
            raise ValueError("Exact powered native composition required")
        intent = binding.intent
        consume_live_claim(claim, intent)  # Failure after this cannot retry the claim.
        now = time.monotonic_ns()
        intent.require_time_available(now)
        body = intent.to_dict()
        if body["mode"] != "physical":
            raise ValueError("Physical powered intent required")
        try:
            attempt_path(root, body["attempt_id"], "outcome").lstat()
        except FileNotFoundError:
            pass
        else:
            raise ValueError("Powered outcome already exists")
        claimed, claim_sha = _read(root, body["attempt_id"], "claimed")
        consumed, consumption_sha = _read(root, body["attempt_id"], "consumed")
        saved, prepared_sha = _read(root, body["attempt_id"], "prepared")
        originals = dict(claim.prepared.originals)
        if (
            claim_sha != claim.claim_sha256
            or claimed.get("consumption_sha256") != consumption_sha
            or consumed.get("prepared_sha256") != prepared_sha
            or claimed.get("request_sha256") != intent.request_sha256
            or _canonical(saved.get("intent")) != intent.payload
            or saved.get("originals_base64")
            != {
                key: base64.b64encode(raw).decode("ascii")
                for key, raw in originals.items()
            }
            or originals["native_identity_original_sha256"] != binding.selection.payload
        ):
            raise ValueError("Powered claim/intent/original chain changed")
        generic = decode_diagnostic_json(
            originals["generic_review_original"], maximum=262144
        )
        rebuilt = prepare_powered_feedback(
            intent=intent,
            root=root,
            startup_operation_id=saved["startup_operation_id"],
            current_source_sha256=current_source_sha256,
            native_original=binding.selection.payload,
            generic_review=generic,
            runtime_original=originals["runtime_sha256"],
            serial_profile_original=originals["serial_profile_sha256"],
            protocol_review_original=originals["protocol_review_sha256"],
            firmware_review_original=originals["firmware_compatibility_review_sha256"],
            now_monotonic_ns=now,
        )
        if rebuilt != claim.prepared:
            raise ValueError("Powered evidence association changed")
        recheck = binding.selection.recheck(
            fresh_snapshot,
            generic,
            mode="physical",
            session_id=body["session_id"],
            source_sha256=current_source_sha256,
            operation_id=metadata_operation_id,
            collection_not_before_ns=collection_not_before_ns,
            now_monotonic_ns=now,
        )
        if recheck["status"] != "METADATA_RECHECK_MATCHED":
            raise ValueError("Fresh powered endpoint identity required")
        instance = cls(binding.identity.port_name)
        instance._request = intent
        instance._fresh_until = fresh_snapshot["finished_monotonic_ns"] + 1_000_000_000
        return instance

    @property
    def expected_path(self):
        return self._expected_path

    @property
    def admitted_request_sha256(self):
        return None if self._request is None else self._request.request_sha256

    def status(self):
        if self._request is None:
            return super().status()
        return {
            "native_api_loaded": self._dll is not None,
            "physical_hold": "MOTION_COMMISSIONING_REQUIRED",
            "powered_admission": "LIVE_CHILD_CLAIM_CONSUMED",
            "physical_authority": False,
        }

    def _require_fresh_open(self):
        self._request.require_time_available(time.monotonic_ns())
        if time.monotonic_ns() > self._fresh_until:
            raise NativeSerialError("POWERED_IDENTITY_EXPIRED", "create_file")

    def _kernel(self):
        if self._request is None:
            return super()._kernel()
        if self._dll is None:
            self._require_fresh_open()
        # Cleanup stays available after deadlines once resources may be owned.
        return self._load_kernel()

    def create_file(self, path):
        with self._open_lock:
            if self._open_attempted:
                raise NativeSerialError("ONE_USE_POWERED_API", "create_file")
            self._open_attempted = True
            if path != self._expected_path:
                raise NativeSerialError("POWERED_ENDPOINT_CHANGED", "create_file")
            if self._request is not None:
                self._require_fresh_open()
            return super().create_file(path)

    def submit_io(self, handle, token):
        validate_native_io_token(token)  # Only exact fixed T105 write payload exists.
        if (
            token.kind == "write"
            and self._request is not None
            and self._request.to_dict()["limits"]["maximum_write_attempts"] == 0
        ):
            raise NativeSerialError("TELEMETRY_WRITES_FORBIDDEN", "submit_io")
        if token.kind == "write":
            with self._write_lock:
                if self._write_token is not None:
                    raise NativeSerialError("ONE_QUERY_NO_RETRY", "submit_io")
                self._write_token = token
        return super().submit_io(handle, token)

    def complete_io(self, handle, token, timeout_ms):
        validate_owned_pending_io(self, token)
        if token.kind == "write" and token is not self._write_token:
            raise NativeSerialError("UNOWNED_POWERED_WRITE", "complete_io")
        return super().complete_io(handle, token, timeout_ms)

    def cancel_io(self, handle, token):
        validate_owned_pending_io(self, token)
        if token.kind == "write" and token is not self._write_token:
            raise NativeSerialError("UNOWNED_POWERED_WRITE", "cancel_io")
        return super().cancel_io(handle, token)
