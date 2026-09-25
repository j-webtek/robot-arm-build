"""Fixed USB-query runtime and review-bound preparation; construction performs no I/O.

This purpose-specific registration never accepts an executable, argv or working
directory from the caller. The native source/build pins are immutable reviewed
component inputs, not hashes learned from files at runtime. File agreement is
separate from an explicit review and from the consumed M1 admission capability.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import stat
from threading import Event
import time
from typing import Any, Callable, TYPE_CHECKING, cast

from .owned_worker_process import (
    PinnedWorkerFile,
    WorkerProcessBudget,
    WorkerProcessRegistration,
    decode_owned_json,
    owned_registration_document,
)
from .usb_identity_protocol import (
    UsbIdentityAdmissionRequest,
    REQUEST_SCHEMA,
    RESULT_SCHEMA,
    canonical,
    digest,
)

if TYPE_CHECKING:
    from rocell.application.usb_identity_stage_policy import (
        UsbIdentityAdmissionIdentity,
    )

RUNTIME_SCHEMA = "rocell.usb_identity_runtime_registration.v1"
REVIEW_SCHEMA = "rocell.usb_identity_runtime_review.v1"
PREPARATION_SCHEMA = "rocell.prepared_owned_usb_identity.v1"
INCAPABLE_PREPARATION_SCHEMA = "rocell.prepared_incapable_usb_identity.v1"
NATIVE_DIRECTORY = "software/native/windows_usb_identity"
BUILD_RECORD_PATH = "BUILD_RECORD.json"
BUILD_RECORD_SHA256 = "5e570a8d583eff9b8cb663a02f37bbcc15a0e915cee747b8bbe7785e3441135a"
HELPER_PATH = "build/Release/rocell_windows_usb_identity.exe"
HELPER_SHA256 = "0f5555ac77835cee3d21d969085b355128006c18b5c4819051137fa5b18ec8c1"
INCAPABLE_HELPER_PATH = "build/Release/rocell_usb_identity_entry_tests.exe"
INCAPABLE_HELPER_SHA256 = (
    "56d383b6f741eff6e11fdf8fa9c7f2e32eedc1b2d06d5aee1d6020b227a8d88c"
)
FIXED_SOURCE_PINS = (
    (
        ".clang-format",
        "ba34612b6489365401d6b785395b508110e7e6df6f863e5c3612d54cb28a9a81",
        196,
    ),
    (
        "admission_entry.cpp",
        "71792093f48a9f95a74bbe8171c9176a0408188623b952e30f9ae0a8f614afa4",
        3637,
    ),
    (
        "admission.cpp",
        "73307d377de8258d00f0173e3d97feeee77de1e586503250f7acdb0f618c6b24",
        10072,
    ),
    (
        "admission.h",
        "ef44380e4aeea889c4e27ac73da1ae5655c4a85818ee70a291f5fc1bb117d17d",
        1634,
    ),
    (
        "CMakeLists.txt",
        "af881fb54ed3b682f0f1df18ec2501104f58a483dd6cec7ceb5c778865db1e67",
        2245,
    ),
    (
        "entry_test.py",
        "2187bb1a1ebe8e13ade88093dba8dbb6554f9abdb39a42cb2a0441bdbc285804",
        3300,
    ),
    (
        "entry_tests.cpp",
        "e992032713a527a09d71180aef5bf1aa18d47193c7c31ed3b63c3c869bdafa1d",
        1019,
    ),
    (
        "fake_api.h",
        "4543d12958308bcc18bf210c02f377cd7b5735901cdacec0c50c872429b7f9ff",
        7274,
    ),
    (
        "main.cpp",
        "226dc5c3a449275ace2a1b1ccd95d691d77bb4d92a63e4d9b0a4db528df9cac4",
        1373,
    ),
    (
        "observation.cpp",
        "a2716ea39bd0d50dd0d4571423a89e520a50f0785bc6d0554a755fd1cade00d1",
        14890,
    ),
    (
        "observation.h",
        "4adc940ebd96abfd917459bdcb88b2efab0d025d6a7cf1d0089e73df38915e42",
        3128,
    ),
    (
        "README.md",
        "b003fc96cac92478f96635e91f2b6386add84b716781a76d3f3e9a405dbfc646",
        5976,
    ),
    (
        "serialize.cpp",
        "c760b1f15f256f7f92221bec7365617a61eb39abc5d45cc02170f98a6a2e8d83",
        12787,
    ),
    (
        "tests.cpp",
        "1614344c33bfedce7febe1dd0a689297c197dca1611232eadb07ed214cafd04c",
        5180,
    ),
    (
        "windows_api.cpp",
        "ca26eb68b9b229f50379efe12936b3de4734d7c8e40fdf7a5539f8a3e8c2a718",
        11962,
    ),
    (
        "windows_api.h",
        "02ff29f5f97fc4a49c06624f7cdfbc5ebb93aed9ea966ebbbf4ccb329720e077",
        427,
    ),
    (
        "wire_test.py",
        "35a0dc12b8eed2559774c8977cbf43a7a1c67b1fb10e00b8652aa1c3999c0fd2",
        2558,
    ),
    (
        "WIRE.md",
        "dbd41224b15f1c3d8f085ba24d48be4711ed6d02e559dea739dc9578b7fdf7b3",
        7874,
    ),
)
MAX_PREPARATION_BYTES = 24 * 1024
REQUIRED_LIFETIME_NS = 20_000_000_000
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\Z")
_REVIEW_SUBJECTS = (
    "selection_sha256",
    "native_identity_sha256",
    "endpoint_sha256",
    "device_instance_id_sha256",
    "operation_sha256",
)


class UsbIdentityRegistrationError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _need(ok: bool, code: str) -> None:
    if not ok:
        raise UsbIdentityRegistrationError(code)


def _sha(value: Any) -> None:
    _need(type(value) is str and bool(_SHA.fullmatch(value)), "EXACT_SHA256")


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


def _load(payload: bytes, maximum: int = MAX_PREPARATION_BYTES) -> dict[str, Any]:
    value = decode_owned_json(payload, maximum=maximum)
    _need(canonical(value) == payload, "EXACT_CANONICAL_USB_REGISTRATION")
    return value


def _runtime_document(
    workspace: Path, source: str, *, incapable: bool
) -> dict[str, Any]:
    _path(str(workspace))
    _sha(source)
    return {
        "schema": RUNTIME_SCHEMA,
        "workspace": str(workspace),
        "source_sha256": source,
        "purpose": "USB_IDENTITY_QUERY",
        "process_model": "DETACHED_PIPE_JOB_ONE_PROCESS",
        "composition": "INCAPABLE_USB_QUERY" if incapable else "PHYSICAL_USB_QUERY",
        "helper": {
            "path": INCAPABLE_HELPER_PATH if incapable else HELPER_PATH,
            "sha256": INCAPABLE_HELPER_SHA256 if incapable else HELPER_SHA256,
        },
        "build_record": {"path": BUILD_RECORD_PATH, "sha256": BUILD_RECORD_SHA256},
        "source_files": [
            {"path": p, "sha256": h, "bytes": n} for p, h, n in FIXED_SOURCE_PINS
        ],
        "request_schema": REQUEST_SCHEMA,
        "result_schema": RESULT_SCHEMA,
        "physical_authority": False,
        "hardware_qualified": False,
        "meaning": "Fixed intended USB-query runtime; not file agreement, review, admission or hardware qualification.",
    }


@dataclass(frozen=True, slots=True)
class UsbIdentityRuntimeRegistration:
    payload: bytes

    def __post_init__(self) -> None:
        value = _load(self.payload)
        _need(
            canonical(value)
            == canonical(
                _runtime_document(
                    _path(value.get("workspace")),
                    value["source_sha256"],
                    incapable=False,
                )
            ),
            "FIXED_USB_RUNTIME_REQUIRED",
        )

    @property
    def sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _load(self.payload)


@dataclass(frozen=True, slots=True)
class IncapableUsbIdentityRuntimeRegistration:
    """Separately named closed fixture; cannot select a physical executable."""

    payload: bytes

    def __post_init__(self) -> None:
        value = _load(self.payload)
        _need(
            canonical(value)
            == canonical(
                _runtime_document(
                    _path(value.get("workspace")),
                    value["source_sha256"],
                    incapable=True,
                )
            ),
            "FIXED_INCAPABLE_USB_RUNTIME_REQUIRED",
        )

    @property
    def sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _load(self.payload)


Runtime = UsbIdentityRuntimeRegistration | IncapableUsbIdentityRuntimeRegistration


def usb_identity_runtime_candidate(
    workspace: Path, *, source_sha256: str
) -> UsbIdentityRuntimeRegistration:
    return UsbIdentityRuntimeRegistration(
        canonical(_runtime_document(workspace, source_sha256, incapable=False))
    )


def incapable_usb_identity_runtime_candidate(
    workspace: Path, *, source_sha256: str
) -> IncapableUsbIdentityRuntimeRegistration:
    return IncapableUsbIdentityRuntimeRegistration(
        canonical(_runtime_document(workspace, source_sha256, incapable=True))
    )


def _runtime(value: dict[str, Any]) -> Runtime:
    cls = (
        IncapableUsbIdentityRuntimeRegistration
        if value.get("composition") == "INCAPABLE_USB_QUERY"
        else UsbIdentityRuntimeRegistration
    )
    return cls(canonical(value))


@dataclass(frozen=True, slots=True)
class UsbIdentityRuntimeReview:
    payload: bytes

    def __post_init__(self) -> None:
        v = _load(self.payload, 8 * 1024)
        _need(
            set(v)
            == {
                "schema",
                "runtime_registration_sha256",
                "source_sha256",
                *_REVIEW_SUBJECTS,
                "operator_id",
                "reviewer_id",
                "launch_session_id",
                "reviewed_at_ns",
                "decision",
                "physical_authority",
                "hardware_qualified",
            },
            "EXACT_USB_REVIEW_FIELDS",
        )
        _need(
            v["schema"] == REVIEW_SCHEMA
            and v["decision"] == "ACKNOWLEDGE_EXACT_USB_QUERY"
            and v["physical_authority"] is False
            and v["hardware_qualified"] is False,
            "USB_REVIEW_MEANING",
        )
        for field in (
            "runtime_registration_sha256",
            "source_sha256",
            *_REVIEW_SUBJECTS,
        ):
            _sha(v[field])
        _need(
            type(v["launch_session_id"]) is str
            and bool(_ID.fullmatch(v["launch_session_id"])),
            "EXACT_REVIEW_LAUNCH",
        )
        for key in ("operator_id", "reviewer_id"):
            label = v[key]
            _need(
                type(label) is str
                and label.strip() == label
                and bool(label)
                and len(label.encode("utf-8")) <= 128
                and not any(ord(c) < 32 or ord(c) == 127 for c in label),
                "EXACT_REVIEW_LABEL",
            )
        _need(
            v["operator_id"].casefold() != v["reviewer_id"].casefold(),
            "DISTINCT_REVIEW_LABEL_REQUIRED",
        )
        _need(
            type(v["reviewed_at_ns"]) is int and 0 < v["reviewed_at_ns"] < 2**63,
            "EXACT_REVIEW_TIME",
        )

    @property
    def sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _load(self.payload, 8 * 1024)


def review_usb_identity_runtime(
    runtime: Runtime,
    *,
    selection_sha256: str,
    native_identity_sha256: str,
    endpoint_sha256: str,
    device_instance_id_sha256: str,
    operation_sha256: str,
    operator_id: str,
    reviewer_id: str,
    launch_session_id: str,
    reviewed_at_ns: int,
) -> UsbIdentityRuntimeReview:
    _need(
        type(runtime)
        in (UsbIdentityRuntimeRegistration, IncapableUsbIdentityRuntimeRegistration),
        "EXACT_USB_RUNTIME",
    )
    type(runtime)(runtime.payload)
    return UsbIdentityRuntimeReview(
        canonical(
            {
                "schema": REVIEW_SCHEMA,
                "runtime_registration_sha256": runtime.sha256,
                "source_sha256": runtime.to_dict()["source_sha256"],
                "selection_sha256": selection_sha256,
                "native_identity_sha256": native_identity_sha256,
                "endpoint_sha256": endpoint_sha256,
                "device_instance_id_sha256": device_instance_id_sha256,
                "operation_sha256": operation_sha256,
                "operator_id": operator_id,
                "reviewer_id": reviewer_id,
                "launch_session_id": launch_session_id,
                "reviewed_at_ns": reviewed_at_ns,
                "decision": "ACKNOWLEDGE_EXACT_USB_QUERY",
                "physical_authority": False,
                "hardware_qualified": False,
            }
        )
    )


def verify_usb_identity_runtime_review(
    value: bytes | UsbIdentityRuntimeReview,
    *,
    runtime: Runtime,
    expected_review_sha256: str,
) -> UsbIdentityRuntimeReview:
    _sha(expected_review_sha256)
    review = UsbIdentityRuntimeReview(
        value.payload if type(value) is UsbIdentityRuntimeReview else cast(bytes, value)
    )
    _need(
        review.sha256 == expected_review_sha256
        and review.to_dict()["runtime_registration_sha256"] == runtime.sha256
        and review.to_dict()["source_sha256"] == runtime.to_dict()["source_sha256"],
        "TRUSTED_USB_REVIEW_MISMATCH",
    )
    return review


def _identity(value: dict[str, Any]) -> UsbIdentityAdmissionIdentity:
    from rocell.application.usb_identity_stage_policy import (
        UsbIdentityAdmissionIdentity,
    )

    return UsbIdentityAdmissionIdentity(canonical(value))


def _process(
    runtime: Runtime, request: UsbIdentityAdmissionRequest
) -> WorkerProcessRegistration:
    data = runtime.to_dict()
    native = _path(data["workspace"]) / NATIVE_DIRECTORY
    return WorkerProcessRegistration(
        (
            "incapable-usb-identity"
            if type(runtime) is IncapableUsbIdentityRuntimeRegistration
            else "physical-usb-identity"
        ),
        PinnedWorkerFile(
            native / data["helper"]["path"], data["helper"]["sha256"], 1024 * 1024
        ),
        ("--owned-usb-identity", "--request-sha256", request.request_sha256),
        (PinnedWorkerFile(native / BUILD_RECORD_PATH, BUILD_RECORD_SHA256, 32 * 1024),),
        native,
        WorkerProcessBudget(
            run_timeout_ms=18000,
            cleanup_timeout_ms=2000,
            stdin_bytes=18 * 1024,
            stdout_bytes=66 * 1024,
            stderr_bytes=4 * 1024,
            process_count=1,
            process_memory_bytes=128 * 1024 * 1024,
            job_memory_bytes=128 * 1024 * 1024,
            observed_handles_per_process=256,
        ),
        (
            "INCAPABLE_PROCESS_FIXTURE"
            if type(runtime) is IncapableUsbIdentityRuntimeRegistration
            else "PHYSICAL_UNQUALIFIED"
        ),
        REQUEST_SCHEMA,
        RESULT_SCHEMA,
    )


def _validate_prepared(payload: bytes, *, incapable: bool) -> dict[str, Any]:
    v = _load(payload)
    _need(
        set(v)
        == {
            "schema",
            "runtime",
            "review",
            "review_sha256",
            "identity",
            "request",
            "registration",
        }
        and v["schema"]
        == (INCAPABLE_PREPARATION_SCHEMA if incapable else PREPARATION_SCHEMA),
        "EXACT_USB_PREPARATION",
    )
    runtime = _runtime(v["runtime"])
    _need(
        (type(runtime) is IncapableUsbIdentityRuntimeRegistration) == incapable,
        "USB_COMPOSITION_MISMATCH",
    )
    review = verify_usb_identity_runtime_review(
        canonical(v["review"]),
        runtime=runtime,
        expected_review_sha256=v["review_sha256"],
    )
    identity = _identity(v["identity"])
    request = UsbIdentityAdmissionRequest(canonical(v["request"]))
    i, r, q = identity.to_dict(), review.to_dict(), request.to_dict()
    _need(
        i["runtime_review_sha256"] == review.sha256
        and i["runtime_registration_sha256"]
        == runtime.sha256
        == q["runtime_registration_sha256"]
        and i["source_sha256"] == r["source_sha256"] == q["source_sha256"]
        and i["session_id"] == q["session_id"]
        and identity.sha256 == q["selected_identity_sha256"]
        and q["helper_sha256"] == runtime.to_dict()["helper"]["sha256"],
        "USB_PREPARATION_CONTEXT",
    )
    for field in _REVIEW_SUBJECTS:
        _need(i[field] == r[field], "USB_REVIEW_TARGET_MISMATCH")
    for field in ("native_identity_sha256", "endpoint_sha256", "operation_sha256"):
        _need(q[field] == i[field], "USB_REQUEST_TARGET_MISMATCH")
    _need(
        q["expected_device_instance_id_sha256"] == i["device_instance_id_sha256"],
        "USB_REQUEST_INSTANCE_MISMATCH",
    )
    _need(
        canonical(v["registration"])
        == canonical(owned_registration_document(_process(runtime, request))),
        "FIXED_USB_PROCESS_REQUIRED",
    )
    return v


@dataclass(frozen=True, slots=True)
class PreparedOwnedUsbIdentity:
    payload: bytes

    def __post_init__(self) -> None:
        _validate_prepared(self.payload, incapable=False)

    @property
    def sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _validate_prepared(self.payload, incapable=False)

    @property
    def runtime(self) -> Runtime:
        return _runtime(self.to_dict()["runtime"])

    @property
    def review(self) -> UsbIdentityRuntimeReview:
        return UsbIdentityRuntimeReview(canonical(self.to_dict()["review"]))

    @property
    def identity(self) -> UsbIdentityAdmissionIdentity:
        return _identity(self.to_dict()["identity"])

    @property
    def request(self) -> UsbIdentityAdmissionRequest:
        return UsbIdentityAdmissionRequest(canonical(self.to_dict()["request"]))

    @property
    def registration(self) -> WorkerProcessRegistration:
        return _process(self.runtime, self.request)

    @property
    def required_lifetime_ns(self) -> int:
        return REQUIRED_LIFETIME_NS


@dataclass(frozen=True, slots=True)
class PreparedIncapableUsbIdentity:
    payload: bytes

    def __post_init__(self) -> None:
        _validate_prepared(self.payload, incapable=True)

    @property
    def sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _validate_prepared(self.payload, incapable=True)

    @property
    def runtime(self) -> Runtime:
        return _runtime(self.to_dict()["runtime"])

    @property
    def review(self) -> UsbIdentityRuntimeReview:
        return UsbIdentityRuntimeReview(canonical(self.to_dict()["review"]))

    @property
    def identity(self) -> UsbIdentityAdmissionIdentity:
        return _identity(self.to_dict()["identity"])

    @property
    def request(self) -> UsbIdentityAdmissionRequest:
        return UsbIdentityAdmissionRequest(canonical(self.to_dict()["request"]))

    @property
    def registration(self) -> WorkerProcessRegistration:
        return _process(self.runtime, self.request)

    @property
    def required_lifetime_ns(self) -> int:
        return REQUIRED_LIFETIME_NS


Preparation = PreparedOwnedUsbIdentity | PreparedIncapableUsbIdentity


def _prepare(
    runtime: Runtime,
    *,
    review: UsbIdentityRuntimeReview,
    expected_review_sha256: str,
    identity: UsbIdentityAdmissionIdentity,
    request: UsbIdentityAdmissionRequest,
    incapable: bool,
) -> Preparation:
    from rocell.application.usb_identity_stage_policy import (
        UsbIdentityAdmissionIdentity,
    )

    _need(
        type(identity) is UsbIdentityAdmissionIdentity
        and type(request) is UsbIdentityAdmissionRequest
        and type(review) is UsbIdentityRuntimeReview,
        "EXACT_USB_PREPARATION_INPUTS",
    )
    cls = PreparedIncapableUsbIdentity if incapable else PreparedOwnedUsbIdentity
    return cls(
        canonical(
            {
                "schema": (
                    INCAPABLE_PREPARATION_SCHEMA if incapable else PREPARATION_SCHEMA
                ),
                "runtime": runtime.to_dict(),
                "review": review.to_dict(),
                "review_sha256": expected_review_sha256,
                "identity": identity.to_dict(),
                "request": request.to_dict(),
                "registration": owned_registration_document(_process(runtime, request)),
            }
        )
    )


def prepare_owned_usb_identity(
    runtime: UsbIdentityRuntimeRegistration,
    *,
    review: UsbIdentityRuntimeReview,
    expected_review_sha256: str,
    identity: UsbIdentityAdmissionIdentity,
    request: UsbIdentityAdmissionRequest,
) -> PreparedOwnedUsbIdentity:
    _need(type(runtime) is UsbIdentityRuntimeRegistration, "EXACT_PHYSICAL_USB_RUNTIME")
    result = _prepare(
        runtime,
        review=review,
        expected_review_sha256=expected_review_sha256,
        identity=identity,
        request=request,
        incapable=False,
    )
    assert type(result) is PreparedOwnedUsbIdentity
    return result


def prepare_incapable_usb_identity(
    runtime: IncapableUsbIdentityRuntimeRegistration,
    *,
    review: UsbIdentityRuntimeReview,
    expected_review_sha256: str,
    identity: UsbIdentityAdmissionIdentity,
    request: UsbIdentityAdmissionRequest,
) -> PreparedIncapableUsbIdentity:
    _need(
        type(runtime) is IncapableUsbIdentityRuntimeRegistration,
        "EXACT_INCAPABLE_USB_RUNTIME",
    )
    result = _prepare(
        runtime,
        review=review,
        expected_review_sha256=expected_review_sha256,
        identity=identity,
        request=request,
        incapable=True,
    )
    assert type(result) is PreparedIncapableUsbIdentity
    return result


def inspect_usb_identity_runtime(
    runtime: Runtime,
    *,
    cancellation: Event,
    deadline_ns: int,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Explicit bounded file-only check, never a review or execution grant."""
    _need(
        type(runtime)
        in (UsbIdentityRuntimeRegistration, IncapableUsbIdentityRuntimeRegistration)
        and isinstance(cancellation, Event)
        and type(deadline_ns) is int,
        "EXACT_USB_INSPECTION_INPUTS",
    )
    data = type(runtime)(runtime.payload).to_dict()
    native = _path(data["workspace"]) / NATIVE_DIRECTORY
    rows = [(p, h, n) for p, h, n in FIXED_SOURCE_PINS]
    rows += [
        (BUILD_RECORD_PATH, BUILD_RECORD_SHA256, 32 * 1024),
        (data["helper"]["path"], data["helper"]["sha256"], 1024 * 1024),
    ]
    observed = []

    def current() -> None:
        _need(not cancellation.is_set(), "CANCELLED")
        _need(time.monotonic_ns() < deadline_ns, "TIMED_OUT")

    for name, expected, maximum in rows:
        current()
        path = native / name
        _need(len(path.parents) <= 128, "USB_PIN_PATH_DEPTH")
        for part in (path, *path.parents):
            info = part.stat(follow_symlinks=False)
            _need(
                not stat.S_ISLNK(info.st_mode)
                and not getattr(info, "st_file_attributes", 0) & 0x400,
                "USB_PIN_PATH_LINK",
            )
        before = path.stat(follow_symlinks=False)
        _need(
            stat.S_ISREG(before.st_mode)
            and before.st_nlink == 1
            and 0 < before.st_size <= maximum,
            "USB_PIN_FILE_BOUND",
        )
        hasher = hashlib.sha256()
        with path.open("rb") as stream:
            remaining = before.st_size
            while remaining:
                current()
                block = stream.read(min(128 * 1024, remaining))
                _need(bool(block), "USB_PIN_TRUNCATED")
                hasher.update(block)
                remaining -= len(block)
            _need(not stream.read(1), "USB_PIN_GREW")
        after = path.stat(follow_symlinks=False)
        _need(
            (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
            == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
            "USB_PIN_CHANGED",
        )
        actual = hasher.hexdigest()
        _need(actual == expected, "USB_PIN_HASH_MISMATCH")
        observed.append({"path": name, "sha256": actual, "bytes": before.st_size})
        if progress is not None:
            progress("Verified fixed USB runtime file")
        current()
    return {
        "schema": "rocell.usb_identity_runtime_file_check.v1",
        "runtime_registration_sha256": runtime.sha256,
        "source_sha256": data["source_sha256"],
        "status": "FILES_MATCHED",
        "files": observed,
        "physical_authority": False,
        "hardware_qualified": False,
    }
