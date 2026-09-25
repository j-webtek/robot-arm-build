"""Internal bounded post-cleanup read, to be sealed by the owned capture campaign.

There is deliberately no filename, device-selection or export-import argument.
This code does not connect/recapture, create output, repair files, or issue a
permit. Only its owner can establish the immediate capture-time provenance and
retain the returned subject in the original attempt. Never expose it as a wizard
action for hashing arbitrary historical files into supposedly earlier evidence.
"""

from contextlib import ExitStack
import hashlib
from itertools import islice
from threading import Event
from time import monotonic_ns

from .camera_capture_checksum import (
    CameraCaptureChecksumError,
    build_capture_checksum,
    capture_metadata,
    _REQUEST,
)
from .physical_onboarding_durability import safe_root, PhysicalOnboardingDurabilityError
from .windows_camera_capture_ingest import _locked_file, BLOCK_BYTES
from .wizard_diagnostic_export import _directory_guard
from rocell.providers.windows.camera_worker_client import NativeFrameArtifact


class _ReadInterrupted(Exception):
    pass


def _collect_owned_capture_checksum(
    evidence, *, request_key, cancellation, deadline_ns
):
    """Hash at most the one bounded native output, within the original deadline.

    Native/process validation occurs first. Actual camera counts and failures
    remain unchanged even if this later file read fails. Chunk reads allocate no
    full-frame copy, and success is returned only after file/directory scope exit.
    Parent original-context checks must bracket this call under the consumed scope.
    """
    if (
        type(cancellation) is not Event
        or type(request_key) is not str
        or _REQUEST.fullmatch(request_key) is None
        or type(deadline_ns) is not int
    ):
        raise CameraCaptureChecksumError()
    checked, _, metadata = capture_metadata(evidence)
    native = checked.run.to_dict()
    if deadline_ns != native["parent_deadline_ns"]:
        raise CameraCaptureChecksumError()
    common = dict(evidence=evidence, request_key=request_key)
    if metadata is None:
        return build_capture_checksum(
            **common,
            status="NATIVE_CAPTURE_NOT_COMPLETE",
            frame=None,
            read_started_ns=None,
            read_finished_ns=None,
        )
    last = native["finished_ns"]
    start = None

    def now():
        nonlocal last
        current = monotonic_ns()
        if type(current) is not int or not last <= current < 2**63:
            # An invalid clock cannot be normalized into a plausible timestamp.
            raise CameraCaptureChecksumError()
        last = current
        return current

    def check():
        current = now()
        if cancellation.is_set() or current >= deadline_ns:
            raise _ReadInterrupted()
        return current

    status = "CAPTURE_BYTES_HASHED"
    frame = None
    try:
        start = check()
        request = checked.prepared.camera_plan.request
        work = checked.prepared.registration.working_directory
        capture = work / ("capture-" + request.campaign_id)
        if str(capture) != request.output_directory:
            raise CameraCaptureChecksumError()
        length = metadata["length_bytes"]
        filename = metadata["filename"]
        with ExitStack() as guards:
            # The directory guard pins all ancestors. The prepared registration,
            # not serialized checksum data or browser input, owns the path.
            guards.enter_context(
                _directory_guard(safe_root(work), confirm_handle_cleanup=True)
            )
            guards.enter_context(
                _directory_guard(safe_root(capture), confirm_handle_cleanup=True)
            )
            check()

            def inventory():
                if [p.name for p in islice(capture.iterdir(), 2)] != [filename]:
                    raise OSError("CAPTURE_CHECKSUM_INVENTORY_CHANGED")

            inventory()
            with _locked_file(capture / filename, length) as stream:
                checksum, remaining = hashlib.sha256(), length
                while remaining:
                    check()
                    chunk = stream.read(min(BLOCK_BYTES, remaining))
                    if not chunk or len(chunk) > remaining:
                        raise OSError("CAPTURE_CHECKSUM_LENGTH_CHANGED")
                    checksum.update(chunk)
                    remaining -= len(chunk)
                check()
                if stream.read(1) != b"":
                    raise OSError("CAPTURE_CHECKSUM_LENGTH_CHANGED")
                inventory()
                check()
            check()
        # Handle/ancestor cleanup is part of the read's deadline and outcome.
        check()
        frame = NativeFrameArtifact(**metadata, sha256=checksum.hexdigest())
    except _ReadInterrupted:
        status = "PIXEL_READ_INTERRUPTED"
    except CameraCaptureChecksumError:
        raise
    except (OSError, ValueError, PhysicalOnboardingDurabilityError):
        status = (
            "PIXEL_READ_INTERRUPTED"
            if cancellation.is_set() or now() >= deadline_ns
            else "PIXEL_READ_FAILED"
        )
    finished = now()
    if cancellation.is_set() or finished >= deadline_ns:
        status, frame = "PIXEL_READ_INTERRUPTED", None
    return build_capture_checksum(
        **common,
        status=status,
        frame=frame,
        read_started_ns=start,
        read_finished_ns=finished,
    )
