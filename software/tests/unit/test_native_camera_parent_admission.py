"""Pure exact parent protocol: no processes, native libraries or device I/O."""

import threading

import pytest

from rocell.providers.windows.camera_worker_client import (
    CameraCampaignBudget,
    WindowsCameraWorkerClient,
)
from rocell.providers.windows.native_camera_parent_admission import (
    NativeCameraParentHandshake,
)
from rocell.providers.windows.native_camera_protocol import (
    FRAME_BYTES,
    READY_SCHEMA,
    RESULT_SCHEMA,
    canonical,
    digest,
)
from rocell.providers.windows.native_camera_registration import (
    HELPER_RELATIVE_PATH,
    PreparedOwnedNativeProbe,
    create_native_camera_runtime_registration,
    prepare_owned_native_probe,
)
from test_windows_camera_worker import BINDING, receipt


class Clock:
    now = 1_000_000_000

    def __call__(self):
        return self.now


def preparation(tmp_path):
    runtime = create_native_camera_runtime_registration(
        tmp_path,
        source_sha256="a" * 64,
        catalog_sha256="b" * 64,
        helper_sha256="c" * 64,
        build_record_sha256="d" * 64,
    )
    plan = WindowsCameraWorkerClient(
        tmp_path / HELPER_RELATIVE_PATH, "c" * 64
    ).prepare_probe(
        BINDING,
        source_sha256="a" * 64,
        campaign_id="attempt-unit",
        budget=CameraCampaignBudget(5000, 1, FRAME_BYTES, FRAME_BYTES),
    )
    return prepare_owned_native_probe(
        runtime,
        plan,
        session_id="session-unit",
        operation_sha256="e" * 64,
        permit_sha256="f" * 64,
        working_directory=tmp_path / "assigned",
    )


def setup(tmp_path, callback=None):
    prepared, clock, cancel, calls = (
        preparation(tmp_path),
        Clock(),
        threading.Event(),
        [],
    )

    def current(exact):
        assert exact.payload == prepared.payload
        assert exact is not prepared
        assert exact.registration.composition == "PHYSICAL_UNQUALIFIED"
        calls.append(exact.preparation_sha256)
        if callback is not None:
            return callback(exact, clock, cancel)

    parent = NativeCameraParentHandshake(
        prepared,
        cancellation=cancel,
        revalidate_consumed_permit=current,
        _clock=clock,
    )
    return parent, prepared, clock, cancel, calls


def ready(prepared, **changes):
    return (
        canonical(
            {
                "schema": READY_SCHEMA,
                "request_sha256": prepared.admission_request.request_sha256,
                "child_pid": 123,
                "challenge": "4" * 64,
                **changes,
            }
        )
        + b"\n"
    )


def begin_ready(parent, prepared, **changes):
    assert parent.begin(deadline_ns=13_000_000_000) == prepared.admission_request.wire()
    parent.check_start_boundary()
    return parent.accept_ready(ready(prepared, **changes), owned_child_pid=123)


def test_inert_constructor_and_exact_full_preparation_recheck(tmp_path):
    parent, prepared, clock, cancel, calls = setup(tmp_path)
    assert calls == [] and not (tmp_path / HELPER_RELATIVE_PATH).exists()
    assert parent.view()["state"] == "PREPARED_NO_DISPATCH"
    release = begin_ready(parent, prepared)
    assert calls == [prepared.preparation_sha256]
    assert b'"permit_sha256":"' + b"f" * 64 in release
    parent.check_release()
    assert calls == [prepared.preparation_sha256] * 2
    assert parent.view()["state"] == "RELEASE_CHECK_PASSED_DELIVERY_UNOBSERVED"
    assert not parent.view()["physical_authority"]
    assert not parent.view()["device_cleanup_confirmed"]


@pytest.mark.parametrize(
    "fault",
    [
        "pre-cancel",
        "short-window",
        "invalid-deadline",
        "denied",
        "slow-check",
        "cancel-in-check",
        "bool-check",
    ],
)
def test_begin_denial_consumes_without_retry(tmp_path, fault):
    def callback(exact, clock, cancel):
        if fault == "denied":
            raise PermissionError("Still-held exact attempt")
        if fault == "slow-check":
            clock.now += 1
        if fault == "cancel-in-check":
            cancel.set()
        if fault == "bool-check":
            return True

    parent, prepared, clock, cancel, calls = setup(tmp_path, callback)
    if fault == "pre-cancel":
        cancel.set()
    deadline = 12_999_999_999 if fault == "short-window" else 13_000_000_000
    if fault == "invalid-deadline":
        deadline = True
    with pytest.raises((ValueError, PermissionError)):
        parent.begin(deadline_ns=deadline)
    assert parent.view()["state"] == "FAILED_NO_RETRY"
    before = len(calls)
    with pytest.raises(ValueError):
        parent.begin(deadline_ns=100_000_000_000)
    assert len(calls) == before


@pytest.mark.parametrize(
    "changes",
    [
        {"request_sha256": "9" * 64},
        {"child_pid": 124},
        {"child_pid": True},
        {"challenge": "not-random-hex"},
        {"extra": "field"},
    ],
)
def test_wrong_ready_never_reaches_release_check(tmp_path, changes):
    parent, prepared, clock, cancel, calls = setup(tmp_path)
    with pytest.raises(ValueError):
        begin_ready(parent, prepared, **changes)
    with pytest.raises(ValueError):
        parent.check_release()
    assert len(calls) == 1


@pytest.mark.parametrize(
    "fault",
    [
        "deadline",
        "cancel",
        "denied",
        "mutated-callback-input",
        "bool-check",
        "time-reversal",
    ],
)
def test_final_check_denial_is_not_retryable(tmp_path, fault):
    invocations = []

    def callback(exact, clock, cancel):
        invocations.append(True)
        if len(invocations) != 2:
            return
        if fault == "deadline":
            clock.now = 3_000_000_000
        if fault == "time-reversal":
            clock.now = 1
        if fault == "cancel":
            cancel.set()
        if fault == "denied":
            raise PermissionError("Changed current permit")
        if fault == "mutated-callback-input":
            object.__setattr__(exact, "payload", b"{}")
        if fault == "bool-check":
            return False

    parent, prepared, clock, cancel, calls = setup(tmp_path, callback)
    begin_ready(parent, prepared)
    with pytest.raises((ValueError, PermissionError)):
        parent.check_release()
    with pytest.raises(ValueError):
        parent.check_release()
    assert len(calls) == 2 and parent.view()["state"] == "FAILED_NO_RETRY"


@pytest.mark.parametrize("stage", ["create", "ready", "release", "result"])
def test_original_deadline_not_refreshed_after_wait(tmp_path, stage):
    parent, prepared, clock, cancel, calls = setup(tmp_path)
    parent.begin(deadline_ns=13_000_000_000)
    if stage in {"release", "result"}:
        parent.accept_ready(ready(prepared), owned_child_pid=123)
    if stage == "result":
        parent.check_release()
    clock.now = 11_000_000_000 if stage == "result" else 3_000_000_000
    with pytest.raises(ValueError, match="DEADLINE"):
        if stage == "create":
            parent.check_start_boundary()
        elif stage == "ready":
            parent.accept_ready(ready(prepared), owned_child_pid=123)
        elif stage == "release":
            parent.check_release()
        else:
            parent.accept_result(b"{}", returncode=0)


@pytest.mark.parametrize("stage", ["start", "ready", "release"])
def test_mutated_original_preparation_cannot_substitute_cwd_or_budget(tmp_path, stage):
    parent, prepared, clock, cancel, calls = setup(tmp_path)
    parent.begin(deadline_ns=13_000_000_000)
    if stage == "release":
        parent.accept_ready(ready(prepared), owned_child_pid=123)
    data = prepared.to_dict()
    data["working_directory"] = str(tmp_path / "different-assignment")
    changed = PreparedOwnedNativeProbe(canonical(data))
    assert (
        changed.admission_request.request_sha256
        == prepared.admission_request.request_sha256
    )
    object.__setattr__(prepared, "payload", changed.payload)
    with pytest.raises(ValueError, match="PREPARATION_CHANGED"):
        if stage == "start":
            parent.check_start_boundary()
        elif stage == "ready":
            parent.accept_ready(ready(prepared), owned_child_pid=123)
        else:
            parent.check_release()
    assert len(calls) == 1


def result_document(prepared):
    return {
        "schema": RESULT_SCHEMA,
        "request_sha256": prepared.admission_request.request_sha256,
        "child_pid": 123,
        "challenge_sha256": digest(b"4" * 64),
        "permit_sha256": "f" * 64,
        "native_receipt": receipt("probe"),
    }


def test_typed_native_result_is_distinct_from_admission_and_cleanup(tmp_path):
    parent, prepared, clock, cancel, calls = setup(tmp_path)
    begin_ready(parent, prepared)
    parent.check_release()
    raw, native = parent.accept_result(
        canonical(result_document(prepared)), returncode=0
    )
    assert native.operation == "probe" and native.status == "OK"
    assert parent.view()["state"] == "RESULT_VALIDATED_NOT_QUALIFIED"
    assert not parent.view()["device_cleanup_confirmed"]
    with pytest.raises(ValueError, match="RESULT_NOT_EXPECTED"):
        parent.accept_result(canonical(raw), returncode=0)


@pytest.mark.parametrize(
    "field", ["request_sha256", "child_pid", "permit_sha256", "challenge_sha256"]
)
def test_wrong_final_binding_not_accepted(tmp_path, field):
    parent, prepared, clock, cancel, calls = setup(tmp_path)
    begin_ready(parent, prepared)
    parent.check_release()
    raw = result_document(prepared)
    raw[field] = 456 if field == "child_pid" else "9" * 64
    with pytest.raises(ValueError):
        parent.accept_result(canonical(raw), returncode=0)
    assert len(calls) == 2 and parent.view()["state"] == "FAILED_NO_RETRY"


def test_result_cannot_skip_actual_final_check(tmp_path):
    parent, prepared, clock, cancel, calls = setup(tmp_path)
    begin_ready(parent, prepared)
    with pytest.raises(ValueError, match="RESULT_NOT_EXPECTED"):
        parent.accept_result(canonical(result_document(prepared)), returncode=0)
    assert len(calls) == 1


def test_concurrent_or_reentrant_call_never_issues_release(tmp_path):
    parent, prepared, clock, cancel, calls = setup(tmp_path)
    begin_ready(parent, prepared)
    assert parent._lock.acquire(blocking=False)
    try:
        with pytest.raises(ValueError, match="CONCURRENT_HANDSHAKE_CALL"):
            parent.check_release()
    finally:
        parent._lock.release()
    assert len(calls) == 1
