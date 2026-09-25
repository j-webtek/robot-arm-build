"""Exact-port, zero-write native facade for the passive engineering worker.

Ordinary construction and the shared general API remain held. Only the fixed
registered worker's live claim and fresh identity can admit this facade. Its
restrictions also reject the otherwise permitted T105 query.
"""

from threading import Lock
import time
import hashlib
import base64

from .nonpurging_serial_api import (
    IoToken,
    NativeSerialError,
    WindowsNativeSerialApi,
    _validate_com_path,
)


class WindowsPassiveSerialApi(WindowsNativeSerialApi):
    """One exact endpoint, one open attempt, read I/O only; no runtime switches."""

    __slots__ = (
        "_expected_path",
        "_open_attempted",
        "_open_lock",
        "_request",
        "_fresh_until",
    )

    def __init__(self, port_name: str):
        if type(port_name) is not str:
            raise NativeSerialError("EXACT_COM_PATH_REQUIRED", "passive_construction")
        path = "\\\\.\\" + port_name
        _validate_com_path(path)
        super().__init__()
        self._expected_path = path
        self._open_attempted = False
        self._open_lock = Lock()
        self._request = None
        self._fresh_until = 0

    @classmethod
    def from_live_claim(
        cls,
        *,
        root,
        claim,
        request,
        binding,
        fresh_snapshot,
        generic_review,
        collection_not_before_ns,
        metadata_operation_id,
    ):
        """Compose only a live child claim and a fresh exact identity recheck.

        This is a trusted in-process composition boundary, not a sandbox against
        hostile Python code. No persisted receipt, boolean or callback releases
        the ordinary constructor. A failed admission burns the live claim.
        """
        from rocell.application.passive_arm_child_claim import consume_live_claim
        from rocell.application.passive_arm_attempt_store import inspect_attempt
        from rocell.application.arm_bench_qualification_contract import _canonical
        from .passive_serial_binding import PassiveSerialBinding

        if (
            cls is not WindowsPassiveSerialApi
            or type(binding) is not PassiveSerialBinding
        ):
            raise ValueError("Exact passive native composition required")
        consume_live_claim(claim, request)
        now = time.monotonic_ns()
        request.require_time_available(now)
        body = request.to_dict()
        records = inspect_attempt(root, body["attempt_id"])["records"]
        if (
            records["claimed"] is None
            or records["outcome"] is not None
            or hashlib.sha256(_canonical(records["claimed"])).hexdigest()
            != claim.claim_sha256
            or hashlib.sha256(binding.selection.payload).hexdigest()
            != body["references"]["native_metadata_review_sha256"]
        ):
            raise ValueError("Native claim or selection changed")
        originals = {
            key: base64.b64decode(value, validate=True)
            for key, value in records["prepared"]["body"]["originals_base64"].items()
        }
        if claim.evidence.assess(request, originals, now_monotonic_ns=now)["blockers"]:
            raise ValueError("Native setup evidence expired or changed")
        recheck = binding.selection.recheck(
            fresh_snapshot,
            generic_review,
            mode="physical",
            session_id=body["launch_id"],
            source_sha256=body["references"]["source_sha256"],
            operation_id=metadata_operation_id,
            collection_not_before_ns=collection_not_before_ns,
            now_monotonic_ns=now,
        )
        if recheck["status"] != "METADATA_RECHECK_MATCHED":
            raise ValueError("Fresh native identity recheck required")
        instance = cls(binding.identity.port_name)
        instance._request = request
        instance._fresh_until = fresh_snapshot["finished_monotonic_ns"] + 1_000_000_000
        return instance

    def status(self):
        if self._request is None:
            return super().status()
        return {
            "native_api_loaded": self._dll is not None,
            "physical_hold": "COMMAND_COMMISSIONING_REQUIRED",
            "passive_admission": "LIVE_CHILD_CLAIM_CONSUMED",
            "physical_authority": False,
        }

    def _kernel(self):
        if self._request is None:
            return super()._kernel()
        if self._dll is None:
            self._require_fresh_open()
        # Once loaded, cleanup must remain possible even after a deadline.
        return self._load_kernel()

    def _require_fresh_open(self):
        now = time.monotonic_ns()
        self._request.require_time_available(now)
        if now > self._fresh_until:
            raise NativeSerialError("PASSIVE_IDENTITY_EXPIRED", "create_file")

    @property
    def expected_path(self):
        return self._expected_path

    @property
    def admitted_request_sha256(self):
        return None if self._request is None else self._request.request_sha256

    def create_file(self, path: str) -> int:
        # Consume BEFORE calling the OS, including wrong-path and failed-open
        # attempts. An uncertain outcome cannot be converted into an API retry.
        with self._open_lock:
            if self._open_attempted:
                raise NativeSerialError("ONE_USE_PASSIVE_API", "create_file")
            self._open_attempted = True
            if path != self._expected_path:
                raise NativeSerialError("PASSIVE_ENDPOINT_CHANGED", "create_file")
            if self._request is not None:
                self._require_fresh_open()
            return super().create_file(path)

    @staticmethod
    def _read_only(token):
        if type(token) is not IoToken or token.kind != "read" or token.payload != b"":
            raise NativeSerialError("PASSIVE_WRITES_FORBIDDEN", "native_io_admission")

    def submit_io(self, handle, token):
        self._read_only(token)
        return super().submit_io(handle, token)

    def complete_io(self, handle, token, timeout_ms):
        self._read_only(token)
        return super().complete_io(handle, token, timeout_ms)

    def cancel_io(self, handle, token):
        self._read_only(token)
        return super().cancel_io(handle, token)
