"""Shared passive lifecycle with separate rehearsal and physical entries.

Unlike the IPC fixture, this executes the actual non-purging lifecycle methods.
It is not a physical worker registration. The physical entry requires exact
request/binding/API types and a fresh metadata recheck. Ordinary native APIs
remain held; only the registered child's live-claim API admits serial loading.
"""

import base64
import hashlib
import time
from threading import Event

from rocell.application.arm_bench_qualification_contract import (
    PassiveBenchRequest,
    MAX_STARTUP_BYTES,
    _canonical,
)
from rocell.application.arm_bench_qualification_result import PassiveBenchResult, SCHEMA
from rocell.application.physical_connection_contracts import EvidenceOrigin
from .arm_feedback_worker import ReviewedControllerBinding
from .nonpurging_serial_api import IncapableWin32SerialApi, NativeSerialError
from .nonpurging_serial_backend import NonPurgingSerialConnection

# Observe for four seconds within the contract's five-second upper bound. The
# remaining second is not a guarantee that an OS call can be interrupted.
OBSERVE_NS = 4_000_000_000
MAX_POLLS = 1024


def observe_rehearsal(request, binding, api, cancellation):
    """One open, bounded reads, one cleanup attempt; never call write or purge.

    Real time is the default. Tests may model this module's clock explicitly;
    neither a modeled clock nor the memory provider qualifies real hardware.
    All outputs remain synthetic, including API handle-cleanup observations.
    """
    valid_binding = type(binding) is ReviewedControllerBinding
    if not valid_binding:
        # Only the new passive lane needs these additional dependencies; keep
        # the previously pinned feedback/rehearsal package roster unchanged.
        from .passive_serial_binding import PassiveSerialBinding

        valid_binding = type(binding) is PassiveSerialBinding
    if (
        type(request) is not PassiveBenchRequest
        or request.to_dict()["mode"] != "rehearsal"
        or not valid_binding
        or binding.origin is not EvidenceOrigin.SYNTHETIC_REHEARSAL
        or type(api) is not IncapableWin32SerialApi
        or type(cancellation) is not Event
    ):
        raise ValueError("Exact hardware-incapable rehearsal inputs required")
    return _observe(request, binding, api, cancellation)


def observe_physical(
    request,
    binding,
    api,
    cancellation,
    *,
    fresh_snapshot,
    generic_review,
    collection_not_before_ns,
    metadata_operation_id,
):
    """Native worker entry; an ordinary, unadmitted API still remains held.

    A caller cannot substitute a memory provider or feedback binding. Recheck
    the original selection just before opening, not a caller-provided PASS.
    Process registration, source pinning and consumed intent are parent/child
    responsibilities; this routine does not manufacture those permissions.
    """
    from .passive_serial_binding import PassiveSerialBinding
    from .passive_serial_api import WindowsPassiveSerialApi

    if (
        type(request) is not PassiveBenchRequest
        or request.to_dict()["mode"] != "physical"
        or type(binding) is not PassiveSerialBinding
        or binding.origin is not EvidenceOrigin.PHYSICAL_OBSERVATION
        or type(api) is not WindowsPassiveSerialApi
        or type(cancellation) is not Event
    ):
        raise ValueError("Exact physical passive inputs required")
    body = request.to_dict()
    if api.admitted_request_sha256 not in (None, request.request_sha256):
        raise ValueError("Native API belongs to a different passive request")
    if (
        hashlib.sha256(binding.selection.payload).hexdigest()
        != body["references"]["native_metadata_review_sha256"]
    ):
        raise ValueError("Passive request selection mismatch")
    recheck = binding.selection.recheck(
        fresh_snapshot,
        generic_review,
        mode="physical",
        session_id=body["launch_id"],
        source_sha256=body["references"]["source_sha256"],
        operation_id=metadata_operation_id,
        collection_not_before_ns=collection_not_before_ns,
        now_monotonic_ns=time.monotonic_ns(),
    )
    if recheck["status"] != "METADATA_RECHECK_MATCHED":
        raise ValueError("Fresh passive identity recheck held")
    observed = _observe(request, binding, api, cancellation)
    observed["identity_recheck"] = recheck
    return observed


def _observe(request, binding, api, cancellation):
    """One implementation for read limits, late bytes and finite cleanup."""
    started = time.monotonic_ns()
    request.require_time_available(started)
    expected = request.to_dict()
    owner = NonPurgingSerialConnection(binding, api=api)
    data = bytearray()
    errors = []
    complete = False
    unread = 0
    attempted = False
    stop_at = started + OBSERVE_NS
    try:
        if cancellation.is_set():
            errors.append("CANCELLED")
        else:
            attempted = True
            owner.open()
            for _ in range(MAX_POLLS):
                if cancellation.is_set():
                    errors.append("CANCELLED")
                    unread = None
                    break
                now = time.monotonic_ns()
                if now >= stop_at:
                    # One final queue observation; unread data is not discarded
                    # or inferred to be zero just because the interval ended.
                    unread = owner.in_waiting
                    complete = unread == 0
                    if unread:
                        errors.append("STARTUP_DATA_LIMIT")
                    break
                waiting = owner.in_waiting
                capacity = MAX_STARTUP_BYTES - len(data)
                if waiting and not capacity:
                    unread = waiting
                    errors.append("STARTUP_DATA_LIMIT")
                    break
                if waiting:
                    timeout = max(1, min(100, (stop_at - now) // 1_000_000))
                    data.extend(
                        owner.read(min(waiting, capacity, 1024), timeout_ms=timeout)
                    )
                else:
                    # Bounded polling rather than a hot spin on an empty queue.
                    time.sleep(min(0.01, (stop_at - now) / 1_000_000_000))
            else:
                unread = None
                errors.append("OBSERVATION_FAILED")
    except NativeSerialError:
        state = owner.status()
        unread = None if state["resource_counts"]["acquired"] else 0
        errors.append(
            "OBSERVATION_FAILED"
            if state["settings_readback_verified"]
            else (
                "CONFIGURATION_FAILED"
                if state["resource_counts"]["acquired"]
                else "OPEN_FAILED"
            )
        )
    finally:
        observation_finished = time.monotonic_ns()
        try:
            owner.close()
        except NativeSerialError:
            errors.append("CLOSE_FAILED")
        finished = time.monotonic_ns()
    # Cancellation can complete a read after its normal return path failed.
    # Preserve these bytes separately supplied by the lifecycle, within quota.
    late = owner.late_read_bytes
    room = MAX_STARTUP_BYTES - len(data)
    data.extend(late[:room])
    if len(late) > room:
        unread = None
        if "STARTUP_DATA_LIMIT" not in errors:
            errors.append("STARTUP_DATA_LIMIT")
    state = owner.status()
    acquired = state["resource_counts"]["acquired"] > 0
    value = dict(
        schema=SCHEMA,
        request_sha256=request.request_sha256,
        attempt_id=expected["attempt_id"],
        launch_id=expected["launch_id"],
        origin=binding.origin.value,
        runtime_sha256=expected["references"]["runtime_sha256"],
        open_state=(
            "SUCCEEDED" if acquired else "FAILED" if attempted else "NOT_ATTEMPTED"
        ),
        close_state=(
            ("CONFIRMED" if state["cleanup_confirmed"] else "UNKNOWN")
            if acquired
            else "NOT_REQUIRED"
        ),
        settings_verified=state["settings_readback_verified"],
        observation_complete=complete,
        started_monotonic_ns=started,
        observation_finished_monotonic_ns=observation_finished,
        finished_monotonic_ns=finished,
        outbound_bytes=state["confirmed_write_bytes"],
        startup=dict(
            base64=base64.b64encode(data).decode("ascii"),
            bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
            unretained_bytes=unread,
        ),
        errors=errors,
    )
    result = PassiveBenchResult(_canonical(value), request)
    return {
        "result": result.to_dict(),
        "summary": result.summary(),
        "lifecycle": state,
        "provenance": (
            "IN_MEMORY_WIN32_LIFECYCLE_NOT_DEVICE_QUALIFICATION"
            if type(api) is IncapableWin32SerialApi
            else "NATIVE_LIFECYCLE_RESULT_NOT_COMMISSIONING_ACCEPTANCE"
        ),
        "physical_authority": False,
        "connected": False,
    }
