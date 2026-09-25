"""Fixed additive presence runtime; file agreement is not review or admission.

Constructors and codecs are inert. Only ``inspect_usb_presence_runtime`` reads
files, under the caller's original deadline and Stop. It never launches a helper
or opens a device. Request-bound preparation, original review and consumed scope
are separate application contracts; this module cannot manufacture them.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import os
from pathlib import Path
import re
import stat
from threading import Event
import time
from typing import TYPE_CHECKING, Any, Callable

from rocell.application.wizard_diagnostic_coordinator import source_fingerprint
from .owned_worker_process import (
    PinnedWorkerFile,
    WorkerProcessBudget,
    WorkerProcessRegistration,
    decode_owned_json,
)
from .usb_presence_protocol import (
    REQUEST_SCHEMA,
    RESULT_SCHEMA,
    UsbPresenceRequest,
    build_usb_presence_request,
    canonical,
    digest,
)

if TYPE_CHECKING:
    from rocell.application.cell_commissioning_coordinator import ExactOperationPermit
    from rocell.application.physical_usb_presence_binding import UsbPresencePhaseBinding
    from rocell.application.usb_presence_stage_policy import UsbPresenceStagePolicy
    from .usb_presence_review import UsbPresenceRuntimeReview

RUNTIME_SCHEMA = "rocell.usb_presence_runtime_registration.v1"
INSPECTION_SCHEMA = "rocell.usb_presence_runtime_file_check.v1"
NATIVE_DIRECTORY = "software/native/windows_usb_presence"
BUILD_RECORD_PATH = "BUILD_RECORD.json"
BUILD_RECORD_SHA256 = "6955b5f750212615fd2a9b24acac127af70407d2524ae7ac5a031de7f6e599d8"
BUILD_RECORD_BYTES = 2104
HELPER_PATH = "build/Release/rocell_windows_usb_presence.exe"
HELPER_SHA256 = "98e997b09f3343dd20caa1da4391bb19556ad212be6b2128e858ec32167fec4c"
HELPER_BYTES = 84992
INCAPABLE_HELPER_PATH = "build/Release/rocell_usb_presence_entry_tests.exe"
INCAPABLE_HELPER_SHA256 = (
    "6e98572194a04d82b4e79d22c8ba63f9afd08ad5044d70a34d4c2b35aefc9739"
)
INCAPABLE_HELPER_BYTES = 90624
FIXED_SOURCE_PINS = (
    (
        "CMakeLists.txt",
        "7969bdbd4407957811b825faabbf20a174b67d813491f9b78eb741b2f9aaaea2",
        2324,
    ),
    (
        "entry.cpp",
        "2d00ada6f62536bc0647db08c8b85e7481bbce03b07be06eeaeb2f62b7fb03d4",
        5040,
    ),
    (
        "fixture_api.h",
        "f6fc2781222713037fe8642af5212d60529cf93129de3644e8fc0008b44c7495",
        2326,
    ),
    (
        "fixture_main.cpp",
        "0f5e0b6c53beb19aa0da9b41aa1ea2c62fe2cfca5c22588e0aa80ae1ab9317d0",
        617,
    ),
    (
        "main.cpp",
        "bf96560748b01684e4c6888a8a038c4bcdcad986884856fb693b02f9809eaac1",
        673,
    ),
    (
        "presence.cpp",
        "c86589ac1d6df90464b36bed5a67bff9d8e6ec2f0d26061300d5f7e9c49bf6b2",
        10909,
    ),
    (
        "presence.h",
        "7e485bac19683688f9af79b7f3ef16038f87111ecceac3999a29e796ef3f5ef6",
        2192,
    ),
    (
        "tests.cpp",
        "f94ff1c34c4725f5497918d34449ae18ac53be140681c81c541adfe39c610d49",
        4593,
    ),
    (
        "windows_api.cpp",
        "f97f70267f8950bc1ffa655c6cb5b0991cca0393b0a8d1123004d10ff72ff5d0",
        1478,
    ),
    (
        "windows_api.h",
        "03e4c40172852a08397267081e70164bcf2c1c5c353d8151ffaca04c5e29c990",
        280,
    ),
    (
        "../windows_usb_identity/admission.cpp",
        "73307d377de8258d00f0173e3d97feeee77de1e586503250f7acdb0f618c6b24",
        10072,
    ),
    (
        "../windows_usb_identity/admission.h",
        "ef44380e4aeea889c4e27ac73da1ae5655c4a85818ee70a291f5fc1bb117d17d",
        1634,
    ),
)
PROCESS_MODEL = "DETACHED_PIPE_JOB_ONE_PROCESS"
ARGV_PREFIX = ("--owned-usb-presence", "--request-sha256")
PROCESS_BUDGET = WorkerProcessBudget(
    run_timeout_ms=13000,
    cleanup_timeout_ms=2000,
    stdin_bytes=10 * 1024,
    stdout_bytes=66 * 1024,
    stderr_bytes=4096,
    process_count=1,
    process_memory_bytes=128 * 1024 * 1024,
    job_memory_bytes=128 * 1024 * 1024,
    observed_handles_per_process=256,
)
REQUIRED_LIFETIME_NS = 15_000_000_000
MAX_RUNTIME_BYTES = 16 * 1024
PREPARATION_SCHEMA = "rocell.owned_usb_presence_preparation.v1"
INCAPABLE_PREPARATION_SCHEMA = "rocell.incapable_usb_presence_preparation.v1"
# Leaves a proved envelope for full bounded stdout/stderr/handshake bytes inside
# the unchanged 128KiB campaign retention budget. Oversized input is refused
# before a process or a device-list call, never silently clipped after release.
MAX_PREPARATION_BYTES = 24 * 1024
_SHA = re.compile(r"[0-9a-f]{64}\Z")


class UsbPresenceRegistrationError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _need(ok: bool, code: str) -> None:
    if not ok:
        raise UsbPresenceRegistrationError(code)


def _path(value: Any) -> Path:
    _need(type(value) is str, "EXACT_LOCAL_WORKSPACE")
    path = Path(value)
    _need(
        path.is_absolute()
        and str(path) == value
        and path != Path(path.anchor)
        and not value.startswith(("\\\\", "//"))
        and ".." not in path.parts
        and len(value.encode("utf-8")) <= 1024
        and not any(ord(c) < 32 for c in value),
        "EXACT_LOCAL_WORKSPACE",
    )
    return path


def _load(payload: bytes) -> dict[str, Any]:
    value = decode_owned_json(payload, maximum=MAX_RUNTIME_BYTES)
    _need(canonical(value) == payload, "CANONICAL_PRESENCE_RUNTIME_REQUIRED")
    return value


def _runtime_document(
    workspace: Path, source: Any, *, incapable: bool
) -> dict[str, Any]:
    _need(isinstance(workspace, Path), "EXACT_LOCAL_WORKSPACE")
    _path(str(workspace))
    _need(type(source) is str and bool(_SHA.fullmatch(source)), "EXACT_SOURCE_SHA256")
    return {
        "schema": RUNTIME_SCHEMA,
        "workspace": str(workspace),
        "source_sha256": source,
        "purpose": "PHYSICAL_USB_NODE_PRESENCE",
        "composition": (
            "INCAPABLE_USB_PRESENCE" if incapable else "PHYSICAL_USB_PRESENCE"
        ),
        "helper": {
            "path": INCAPABLE_HELPER_PATH if incapable else HELPER_PATH,
            "sha256": INCAPABLE_HELPER_SHA256 if incapable else HELPER_SHA256,
            "bytes": INCAPABLE_HELPER_BYTES if incapable else HELPER_BYTES,
        },
        "build_record": {
            "path": BUILD_RECORD_PATH,
            "sha256": BUILD_RECORD_SHA256,
            "bytes": BUILD_RECORD_BYTES,
        },
        "source_files": [
            {"path": p, "sha256": h, "bytes": n} for p, h, n in FIXED_SOURCE_PINS
        ],
        "process_model": PROCESS_MODEL,
        "argv_prefix": list(ARGV_PREFIX),
        "request_hash_argument": "EXACT_REQUEST_SHA256",
        "working_directory": NATIVE_DIRECTORY,
        "budget": asdict(PROCESS_BUDGET),
        "required_lifetime_ns": REQUIRED_LIFETIME_NS,
        "request_schema": REQUEST_SCHEMA,
        "result_schema": RESULT_SCHEMA,
        "physical_authority": False,
        "hardware_qualified": False,
        "meaning": "Fixed intended presence runtime; not file agreement, review, admission, original absence or hardware qualification.",
    }


def _validate(payload: bytes, *, incapable: bool) -> dict[str, Any]:
    value = _load(payload)
    _need(
        canonical(value)
        == canonical(
            _runtime_document(
                _path(value.get("workspace")),
                value.get("source_sha256"),
                incapable=incapable,
            )
        ),
        "FIXED_PRESENCE_RUNTIME_REQUIRED",
    )
    return value


@dataclass(frozen=True, slots=True)
class UsbPresenceRuntimeRegistration:
    payload: bytes

    def __post_init__(self) -> None:
        _validate(self.payload, incapable=False)

    @property
    def sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _validate(self.payload, incapable=False)


@dataclass(frozen=True, slots=True)
class IncapableUsbPresenceRuntimeRegistration:
    """Separate exact type, never a boolean switch selecting the real helper."""

    payload: bytes

    def __post_init__(self) -> None:
        _validate(self.payload, incapable=True)

    @property
    def sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _validate(self.payload, incapable=True)


Runtime = UsbPresenceRuntimeRegistration | IncapableUsbPresenceRuntimeRegistration


def usb_presence_runtime_candidate(
    workspace: Path, *, source_sha256: str
) -> UsbPresenceRuntimeRegistration:
    return UsbPresenceRuntimeRegistration(
        canonical(_runtime_document(workspace, source_sha256, incapable=False))
    )


def incapable_usb_presence_runtime_candidate(
    workspace: Path, *, source_sha256: str
) -> IncapableUsbPresenceRuntimeRegistration:
    return IncapableUsbPresenceRuntimeRegistration(
        canonical(_runtime_document(workspace, source_sha256, incapable=True))
    )


def _file_path(workspace: Path, name: str) -> Path:
    native = workspace / NATIVE_DIRECTORY
    # These two historical dependencies are fixed source inputs, not generic
    # caller-supplied traversal. Construct normalized paths without resolving
    # links or consulting the filesystem during registration construction.
    shared = {
        "../windows_usb_identity/admission.cpp": "admission.cpp",
        "../windows_usb_identity/admission.h": "admission.h",
    }
    if name in shared:
        return native.parent / "windows_usb_identity" / shared[name]
    _need(
        name
        in {p for p, _, _ in FIXED_SOURCE_PINS}
        | {BUILD_RECORD_PATH, HELPER_PATH, INCAPABLE_HELPER_PATH},
        "FIXED_PRESENCE_FILE_REQUIRED",
    )
    return native / name


def _identity(info: os.stat_result) -> tuple[int, int, int, int]:
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def inspect_usb_presence_runtime(
    runtime: Runtime,
    *,
    cancellation: Event,
    deadline_ns: int,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Bounded actual-file inspection; never approval or a process launch.

    Stop/deadline is checked before and after synchronous source hashing and
    every bounded file read. A late source/read cannot publish FILES_MATCHED.
    Pins are immutable code constants; observed bytes cannot repin themselves.
    """
    _need(
        type(runtime)
        in (UsbPresenceRuntimeRegistration, IncapableUsbPresenceRuntimeRegistration)
        and isinstance(cancellation, Event)
        and type(deadline_ns) is int
        and 0 < deadline_ns < 2**63
        and (progress is None or callable(progress)),
        "EXACT_PRESENCE_INSPECTION_INPUTS",
    )
    data = type(runtime)(runtime.payload).to_dict()
    workspace = _path(data["workspace"])

    def current() -> None:
        _need(not cancellation.is_set(), "CANCELLED")
        _need(time.monotonic_ns() < deadline_ns, "TIMED_OUT")

    def source_current() -> None:
        current()
        observed = source_fingerprint(workspace)
        current()
        _need(observed == data["source_sha256"], "SOURCE_CHANGED")

    source_current()
    rows = list(FIXED_SOURCE_PINS) + [
        (BUILD_RECORD_PATH, BUILD_RECORD_SHA256, BUILD_RECORD_BYTES),
        (data["helper"]["path"], data["helper"]["sha256"], data["helper"]["bytes"]),
    ]
    observed = []
    for name, expected, exact_bytes in rows:
        current()
        path = _file_path(workspace, name)
        _need(len(path.parents) <= 128, "PRESENCE_PIN_PATH_DEPTH")
        for index, part in enumerate((path, *path.parents)):
            current()
            info = part.stat(follow_symlinks=False)
            _need(
                not stat.S_ISLNK(info.st_mode)
                and not getattr(info, "st_file_attributes", 0) & 0x400,
                "PRESENCE_PIN_PATH_LINK",
            )
            _need(
                index == 0 or stat.S_ISDIR(info.st_mode),
                "PRESENCE_PIN_PARENT_DIRECTORY",
            )
        before = path.stat(follow_symlinks=False)
        _need(
            stat.S_ISREG(before.st_mode)
            and before.st_nlink == 1
            and before.st_size == exact_bytes,
            "PRESENCE_PIN_FILE_BOUND",
        )
        hasher = hashlib.sha256()
        with path.open("rb") as stream:
            # Bind the opened file to the sampled path; a path swap cannot make
            # an unrelated handle's bytes appear to verify that original path.
            _need(
                _identity(os.fstat(stream.fileno())) == _identity(before),
                "PRESENCE_PIN_CHANGED",
            )
            remaining = exact_bytes
            while remaining:
                current()
                block = stream.read(min(32 * 1024, remaining))
                current()
                _need(bool(block), "PRESENCE_PIN_TRUNCATED")
                hasher.update(block)
                remaining -= len(block)
            _need(not stream.read(1), "PRESENCE_PIN_GREW")
            current()
            _need(
                _identity(os.fstat(stream.fileno())) == _identity(before),
                "PRESENCE_PIN_CHANGED",
            )
        after = path.stat(follow_symlinks=False)
        _need(
            _identity(before) == _identity(after)
            and stat.S_ISREG(after.st_mode)
            and after.st_nlink == 1
            and not getattr(after, "st_file_attributes", 0) & 0x400,
            "PRESENCE_PIN_CHANGED",
        )
        current()
        _need(hasher.hexdigest() == expected, "PRESENCE_PIN_HASH_MISMATCH")
        observed.append({"path": name, "sha256": expected, "bytes": exact_bytes})
        if progress is not None:
            progress("Verified fixed USB presence runtime file")
        current()
    source_current()
    return {
        "schema": INSPECTION_SCHEMA,
        "runtime_registration_sha256": runtime.sha256,
        "source_sha256": data["source_sha256"],
        "status": "FILES_MATCHED",
        "files": observed,
        "physical_authority": False,
        "hardware_qualified": False,
        "device_io_performed": False,
    }


def _runtime(value: dict[str, Any]) -> Runtime:
    cls = (
        IncapableUsbPresenceRuntimeRegistration
        if value.get("composition") == "INCAPABLE_USB_PRESENCE"
        else UsbPresenceRuntimeRegistration
    )
    return cls(canonical(value))


def _presence_permit(value: Any) -> ExactOperationPermit:
    from rocell.application.commissioning_m1_persistence import (
        M1CommissioningPersistenceError,
    )
    from rocell.application.commissioning_usb_presence_persistence import (
        decode_physical_usb_presence_permit,
    )

    try:
        return decode_physical_usb_presence_permit(value)
    except M1CommissioningPersistenceError as exc:
        raise UsbPresenceRegistrationError(
            "EXACT_ORIGINAL_PRESENCE_PERMIT_REQUIRED"
        ) from exc


def _phase(value: dict[str, Any]) -> UsbPresencePhaseBinding:
    from rocell.application.physical_usb_presence_binding import UsbPresencePhaseBinding

    return UsbPresencePhaseBinding(canonical(value))


def _policy(value: dict[str, Any]) -> UsbPresenceStagePolicy:
    from rocell.application.usb_presence_stage_policy import UsbPresenceStagePolicy

    return UsbPresenceStagePolicy(canonical(value))


def _process(
    runtime: Runtime, request: UsbPresenceRequest
) -> WorkerProcessRegistration:
    r = runtime.to_dict()
    workspace = _path(r["workspace"])
    return WorkerProcessRegistration(
        (
            "incapable-usb-presence"
            if type(runtime) is IncapableUsbPresenceRuntimeRegistration
            else "physical-usb-presence"
        ),
        PinnedWorkerFile(
            _file_path(workspace, r["helper"]["path"]),
            r["helper"]["sha256"],
            r["helper"]["bytes"],
        ),
        (*ARGV_PREFIX, request.sha256),
        # Only executable code and its fixed build record are child runtime
        # inputs. The complete source roster is independently inspected before
        # start; it is not a caller-controlled import graph or extra argv.
        (
            PinnedWorkerFile(
                _file_path(workspace, BUILD_RECORD_PATH),
                BUILD_RECORD_SHA256,
                BUILD_RECORD_BYTES,
            ),
        ),
        workspace / NATIVE_DIRECTORY,
        PROCESS_BUDGET,
        (
            "INCAPABLE_PROCESS_FIXTURE"
            if type(runtime) is IncapableUsbPresenceRuntimeRegistration
            else "PHYSICAL_UNQUALIFIED"
        ),
        REQUEST_SCHEMA,
        RESULT_SCHEMA,
    )


def _request(
    runtime: Runtime,
    phase: UsbPresencePhaseBinding,
    permit: ExactOperationPermit,
    nonce: str,
) -> UsbPresenceRequest:
    binding = phase.to_dict()
    return build_usb_presence_request(
        attempt_id=permit.attempt_id,
        session_id=binding["binding"]["session_id"],
        source_sha256=binding["binding"]["source_sha256"],
        phase_binding_sha256=phase.sha256,
        target_instance_id=binding["target"]["physical_usb_instance_id"],
        selected_identity_sha256=phase.sha256,
        operation_sha256=permit.registration.operation_sha256,
        permit_sha256=permit.permit_sha256,
        helper_sha256=runtime.to_dict()["helper"]["sha256"],
        runtime_registration_sha256=runtime.sha256,
        request_nonce=nonce,
    )


def _validate_prepared(payload: bytes, *, incapable: bool) -> dict[str, Any]:
    from rocell.application.cell_commissioning_coordinator import (
        UsbPresenceAdmissionSnapshot,
        CommissioningMode,
    )
    from rocell.application.commissioning_camera_persistence import (
        physical_camera_source_binding,
    )
    from rocell.application.physical_onboarding import PhysicalOnboardingStage
    from rocell.application.physical_onboarding_leases import LeaseLevel
    from rocell.application.physical_onboarding_v2 import V2StageState
    from rocell.application.usb_presence_stage_policy import POLICY_ACTION, WORKER_ID
    from rocell.safety.effects import EffectClass
    from .usb_presence_review import verify_usb_presence_runtime_review

    v = decode_owned_json(payload, maximum=MAX_PREPARATION_BYTES)
    _need(
        canonical(v) == payload
        and set(v)
        == {
            "schema",
            "runtime",
            "phase_binding",
            "policy",
            "review",
            "permit",
            "request",
        }
        and v["schema"]
        == (INCAPABLE_PREPARATION_SCHEMA if incapable else PREPARATION_SCHEMA),
        "EXACT_PRESENCE_PREPARATION",
    )
    runtime, phase, policy = (
        _runtime(v["runtime"]),
        _phase(v["phase_binding"]),
        _policy(v["policy"]),
    )
    _need(
        (type(runtime) is IncapableUsbPresenceRuntimeRegistration) == incapable,
        "PRESENCE_COMPOSITION_MISMATCH",
    )
    permit = _presence_permit(v["permit"])
    _need(
        type(permit.admission) is UsbPresenceAdmissionSnapshot,
        "EXACT_PRESENCE_DOMAIN_PERMIT",
    )
    a, r, binding = permit.admission, permit.registration, phase.to_dict()["binding"]
    assert isinstance(a, UsbPresenceAdmissionSnapshot)
    _need(
        permit.request.cell_id == a.cell_id == binding["cell_id"]
        and permit.request.session_id == a.session_id == binding["session_id"]
        and permit.request.action_id == r.action_id == POLICY_ACTION
        and permit.request.expected_challenge_sha256 == a.challenge_sha256
        and a.mode is CommissioningMode.PHYSICAL_DIAGNOSTIC
        and a.stage is r.stage is PhysicalOnboardingStage.CAMERA_IDENTITY
        and a.stage_state is V2StageState.WAITING_OPERATOR
        and r.effect_class is EffectClass.BOUNDED_CAMERA_CAMPAIGN
        and r.worker_id == WORKER_ID
        and r.resources == (LeaseLevel.CAMERA,)
        and a.source_binding_sha256
        == physical_camera_source_binding(binding["source_sha256"])
        and a.selected_identity_sha256 == a.phase_binding_sha256 == phase.sha256
        and a.usb_presence_policy_sha256 == policy.sha256
        and r.worker_executable_sha256 == runtime.to_dict()["helper"]["sha256"]
        and canonical(asdict(r.budget)) == canonical(policy.to_dict()["budget"])
        and not a.quarantine_latched
        and a.unresolved_attempts == 0
        and not a.open_blocker_ids
        and permit.envelope is None,
        "PRESENCE_PERMIT_SUBJECT_MISMATCH",
    )
    # The expected review hash is from the immutable admission, not copied from
    # untrusted review bytes. M1 independently authenticated that original review.
    verify_usb_presence_runtime_review(
        canonical(v["review"]),
        runtime=runtime,
        phase_binding=phase,
        policy=policy,
        operation_sha256=r.operation_sha256,
        expected_review_sha256=a.runtime_review_sha256,
    )
    request = UsbPresenceRequest(canonical(v["request"]))
    _need(
        request.payload
        == _request(runtime, phase, permit, request.to_dict()["request_nonce"]).payload,
        "PRESENCE_REQUEST_SUBJECT_MISMATCH",
    )
    _process(runtime, request)
    return v


@dataclass(frozen=True, slots=True)
class _PreparedPresence:
    payload: bytes

    def __post_init__(self) -> None:
        _need(
            type(self) in (PreparedOwnedUsbPresence, PreparedIncapableUsbPresence),
            "EXACT_PRESENCE_PREPARED_TYPE",
        )
        _validate_prepared(
            self.payload, incapable=type(self) is PreparedIncapableUsbPresence
        )

    @property
    def sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _validate_prepared(
            self.payload, incapable=type(self) is PreparedIncapableUsbPresence
        )

    @property
    def runtime(self) -> Runtime:
        return _runtime(self.to_dict()["runtime"])

    @property
    def phase_binding(self) -> UsbPresencePhaseBinding:
        return _phase(self.to_dict()["phase_binding"])

    @property
    def policy(self) -> UsbPresenceStagePolicy:
        return _policy(self.to_dict()["policy"])

    @property
    def review(self) -> UsbPresenceRuntimeReview:
        from .usb_presence_review import UsbPresenceRuntimeReview

        return UsbPresenceRuntimeReview(canonical(self.to_dict()["review"]))

    @property
    def permit(self) -> ExactOperationPermit:
        return _presence_permit(self.to_dict()["permit"])

    @property
    def request(self) -> UsbPresenceRequest:
        return UsbPresenceRequest(canonical(self.to_dict()["request"]))

    @property
    def registration(self) -> WorkerProcessRegistration:
        return _process(self.runtime, self.request)

    @property
    def required_lifetime_ns(self) -> int:
        return REQUIRED_LIFETIME_NS


@dataclass(frozen=True, slots=True)
class PreparedOwnedUsbPresence(_PreparedPresence):
    """Physical present-node preparation, not an executable authority token."""


@dataclass(frozen=True, slots=True)
class PreparedIncapableUsbPresence(_PreparedPresence):
    """Separate fixed incapable preparation; cannot select the physical helper."""


Preparation = PreparedOwnedUsbPresence | PreparedIncapableUsbPresence


def _prepare(
    runtime: Runtime,
    *,
    phase_binding: UsbPresencePhaseBinding,
    policy: UsbPresenceStagePolicy,
    review: UsbPresenceRuntimeReview,
    permit: ExactOperationPermit,
    request_nonce: str,
    incapable: bool,
) -> Preparation:
    from rocell.application.cell_commissioning_coordinator import ExactOperationPermit
    from rocell.application.physical_usb_presence_binding import UsbPresencePhaseBinding
    from rocell.application.usb_presence_stage_policy import UsbPresenceStagePolicy
    from .usb_presence_review import UsbPresenceRuntimeReview

    _need(
        type(phase_binding) is UsbPresencePhaseBinding
        and type(policy) is UsbPresenceStagePolicy
        and type(review) is UsbPresenceRuntimeReview
        and type(permit) is ExactOperationPermit,
        "EXACT_PRESENCE_PREPARATION_INPUTS",
    )
    cls = PreparedIncapableUsbPresence if incapable else PreparedOwnedUsbPresence
    return cls(
        canonical(
            dict(
                schema=(
                    INCAPABLE_PREPARATION_SCHEMA if incapable else PREPARATION_SCHEMA
                ),
                runtime=runtime.to_dict(),
                phase_binding=phase_binding.to_dict(),
                policy=policy.to_dict(),
                review=review.to_dict(),
                permit=asdict(permit),
                request=_request(
                    runtime, phase_binding, permit, request_nonce
                ).to_dict(),
            )
        )
    )


def prepare_owned_usb_presence(
    runtime: UsbPresenceRuntimeRegistration,
    *,
    phase_binding: UsbPresencePhaseBinding,
    policy: UsbPresenceStagePolicy,
    review: UsbPresenceRuntimeReview,
    permit: ExactOperationPermit,
    request_nonce: str,
) -> PreparedOwnedUsbPresence:
    _need(
        type(runtime) is UsbPresenceRuntimeRegistration,
        "EXACT_PHYSICAL_PRESENCE_RUNTIME",
    )
    result = _prepare(
        runtime,
        phase_binding=phase_binding,
        policy=policy,
        review=review,
        permit=permit,
        request_nonce=request_nonce,
        incapable=False,
    )
    assert type(result) is PreparedOwnedUsbPresence
    return result


def prepare_incapable_usb_presence(
    runtime: IncapableUsbPresenceRuntimeRegistration,
    *,
    phase_binding: UsbPresencePhaseBinding,
    policy: UsbPresenceStagePolicy,
    review: UsbPresenceRuntimeReview,
    permit: ExactOperationPermit,
    request_nonce: str,
) -> PreparedIncapableUsbPresence:
    _need(
        type(runtime) is IncapableUsbPresenceRuntimeRegistration,
        "EXACT_INCAPABLE_PRESENCE_RUNTIME",
    )
    result = _prepare(
        runtime,
        phase_binding=phase_binding,
        policy=policy,
        review=review,
        permit=permit,
        request_nonce=request_nonce,
        incapable=True,
    )
    assert type(result) is PreparedIncapableUsbPresence
    return result
