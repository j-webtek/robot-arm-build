"""Pure complete v2 preparation and shared-parent lifecycle tests; no device I/O."""

from copy import deepcopy
from dataclasses import asdict, replace
from pathlib import Path
import threading

import pytest

from rocell.providers.windows.camera_worker_client import (
    CameraCampaignBudget,
    CameraEndpointBinding,
    CameraWorkerError,
    NativeCameraMode,
    WindowsCameraWorkerClient,
)
from rocell.providers.windows.native_camera_activation_registration import (
    NativeCameraActivationRuntime,
    PreparedOwnedNativeActivation,
    create_activation_runtime,
    prepare_owned_activation,
    helper_relative_path,
    process_budget,
)
from rocell.providers.windows.native_camera_parent_admission import (
    NativeCameraParentHandshake,
)
from rocell.providers.windows.native_camera_protocol import (
    FRAME_BYTES,
    canonical,
    digest,
    READY_SCHEMA,
)
from rocell.providers.windows.native_camera_registration import PreparedOwnedNativeProbe
from rocell.providers.windows.native_camera_capture_registration import (
    PreparedOwnedNativeCapture,
)
from test_native_camera_activation_expectation import build, enrollment
from test_native_camera_activation_protocol import fixture as result_fixture
from test_native_camera_parent_admission import Clock


def inputs(directory, purpose="probe", helper_sha="c" * 64):
    expectation = build(enrollment())
    runtime = create_activation_runtime(
        directory,
        purpose=purpose,
        source_sha256="a" * 64,
        catalog_sha256="b" * 64,
        helper_sha256=helper_sha,
        build_record_sha256="d" * 64,
    )
    endpoint = expectation.to_dict()["endpoint"]
    binding = CameraEndpointBinding(endpoint, digest(endpoint.encode()), "b" * 64)
    client = WindowsCameraWorkerClient(
        directory / helper_relative_path(purpose), helper_sha
    )
    common = dict(source_sha256="a" * 64, campaign_id="attempt-1")
    plan = (
        client.prepare_probe(
            binding,
            budget=CameraCampaignBudget(5000, 1, FRAME_BYTES, FRAME_BYTES),
            **common,
        )
        if purpose == "probe"
        else client.prepare_capture(
            binding,
            NativeCameraMode(4, 2, 9, 1, "YUY2", 8),
            directory / "capture-attempt-1",
            budget=CameraCampaignBudget(5000, 1, 16, 16),
            **common,
        )
    )
    args = dict(
        session_id="modeled-session",
        operation_sha256="e" * 64,
        permit_sha256="f" * 64,
        working_directory=directory,
    )
    return runtime, plan, expectation, args


def preparation(directory, purpose="probe", helper_sha="c" * 64):
    runtime, plan, expectation, args = inputs(directory, purpose, helper_sha)
    return prepare_owned_activation(runtime, plan, expectation, **args)


def setup(directory, purpose, callback=None):
    prepared, clock, cancel, calls = (
        preparation(directory, purpose),
        Clock(),
        threading.Event(),
        [],
    )

    def current(exact):
        assert (
            type(exact) is PreparedOwnedNativeActivation
            and exact.payload == prepared.payload
            and exact is not prepared
        )
        calls.append(exact.preparation_sha256)
        if callback:
            return callback(exact, clock, cancel, len(calls))

    parent = NativeCameraParentHandshake(
        prepared, cancellation=cancel, revalidate_consumed_permit=current, _clock=clock
    )
    return parent, prepared, clock, cancel, calls


def ready(prepared, pid=123):
    return (
        canonical(
            dict(
                schema=READY_SCHEMA,
                request_sha256=prepared.admission_request.request_sha256,
                child_pid=pid,
                challenge="1" * 64,
            )
        )
        + b"\n"
    )


def begin_ready(parent, prepared):
    assert parent.begin(deadline_ns=30_000_000_000) == prepared.admission_request.wire()
    parent.check_start_boundary()
    return parent.accept_ready(ready(prepared), owned_child_pid=123)


@pytest.mark.parametrize("purpose", ["probe", "capture"])
def test_preparation_shared_parent_and_result_are_inert_and_fully_bound(
    tmp_path, monkeypatch, purpose
):
    def forbidden(*args, **kwargs):
        pytest.fail("Inert v2 lifecycle attempted I/O")

    with monkeypatch.context() as patch:
        for name in ("open", "stat", "lstat", "mkdir", "resolve"):
            patch.setattr(Path, name, forbidden)
        for name in (
            "probe",
            "capture",
            "enumerate_metadata",
            "resolve_identity_metadata",
        ):
            patch.setattr(WindowsCameraWorkerClient, name, forbidden)
        parent, prepared, clock, cancel, calls = setup(tmp_path, purpose)
        assert (
            not calls
            and parent.view()["schema"] == "rocell.native_camera_parent_handshake.v2"
        )
        assert prepared.registration.argv == (
            "--owned-" + purpose + "-v2",
            "--request-sha256",
            prepared.admission_request.request_sha256,
        )
        assert (
            prepared.required_lifetime_ns
            == (12 if purpose == "probe" else 17) * 1_000_000_000
        )
        assert prepared.registration.budget.stdout_bytes == 256 * 1024
        assert prepared.registration.budget.process_count == 1
        assert prepared.runtime.to_dict()["dispatch_enabled"] is False
        release = begin_ready(parent, prepared)
        assert calls == [prepared.preparation_sha256]
        assert b'"permit_sha256":"' + b"f" * 64 in release
        parent.check_release()
        _, _, raw = result_fixture(purpose)
        raw.update(
            request_sha256=prepared.admission_request.request_sha256,
            permit_sha256="f" * 64,
        )
        result, metadata = parent.accept_result(canonical(raw), returncode=0)
        assert metadata.status == "OK" and result == raw
        assert calls == [prepared.preparation_sha256] * 2
        assert parent.view()["state"] == "RESULT_VALIDATED_NOT_QUALIFIED"
        assert parent.view()["physical_authority"] is False
        assert parent.view()["device_cleanup_confirmed"] is False
        with pytest.raises(ValueError):
            parent.accept_result(canonical(raw), returncode=0)


@pytest.mark.parametrize("purpose", ["probe", "capture"])
@pytest.mark.parametrize(
    "field,value",
    [
        ("schema", "legacy"),
        ("purpose", "inventory"),
        ("purpose", "CAPTURE"),
        ("dispatch_enabled", True),
        ("status", "APPROVED"),
        ("result_schema", "rocell.owned_native_camera_result.v1"),
        ("source_sha256", "0" * 64),
        ("catalog_sha256", "A" * 64),
        ("physical_authority", True),
    ],
)
def test_runtime_candidate_cannot_be_relabelled_as_authority(
    tmp_path, purpose, field, value
):
    data = inputs(tmp_path, purpose)[0].to_dict()
    data[field] = value
    with pytest.raises(ValueError):
        NativeCameraActivationRuntime(canonical(data))


@pytest.mark.parametrize("purpose", ["probe", "capture"])
@pytest.mark.parametrize(
    "fault",
    [
        "helper-path",
        "legacy-path",
        "record-path",
        "source",
        "helper-hash",
        "request-runtime",
        "intent-hash",
        "budget-process",
        "budget-stdout",
        "budget-bool",
        "cwd",
        "schema",
        "extra",
        "wrong-purpose",
    ],
)
def test_complete_preparation_denies_substitution(tmp_path, purpose, fault):
    prepared = preparation(tmp_path, purpose)
    data = prepared.to_dict()
    if fault == "helper-path":
        data["runtime"]["helper"]["path"] = str(tmp_path / "other.exe")
    elif fault == "legacy-path":
        data["runtime"]["helper"]["path"] = str(
            tmp_path
            / "software/native/windows_camera/build-owned/Release/rocell_windows_camera.exe"
        )
    elif fault == "record-path":
        data["runtime"]["build_record"]["path"] = str(tmp_path / "old-manifest.json")
    elif fault == "source":
        data["admission_request"]["source_sha256"] = "9" * 64
    elif fault == "helper-hash":
        data["admission_request"]["helper_sha256"] = "9" * 64
    elif fault == "request-runtime":
        data["admission_request"]["runtime_registration_sha256"] = "9" * 64
    elif fault == "intent-hash":
        data["admission_request"]["camera_request_sha256"] = "9" * 64
    elif fault == "budget-process":
        data["process_budget"]["process_count"] = 2
    elif fault == "budget-stdout":
        data["process_budget"]["stdout_bytes"] -= 1
    elif fault == "budget-bool":
        data["process_budget"]["process_count"] = True
    elif fault == "cwd":
        data["working_directory"] = "relative"
    elif fault == "schema":
        data["schema"] = "rocell.prepared_owned_native_probe.v1"
    elif fault == "extra":
        data["allow_hardware"] = True
    elif fault == "wrong-purpose":
        data["runtime"]["purpose"] = "capture" if purpose == "probe" else "probe"
    with pytest.raises((ValueError, CameraWorkerError)):
        PreparedOwnedNativeActivation(canonical(data))


@pytest.mark.parametrize("purpose", ["probe", "capture"])
@pytest.mark.parametrize(
    "fault",
    [
        "arguments",
        "request-extra",
        "list-controls",
        "wrong-helper",
        "changed-mode",
        "short-native-budget",
        "changed-binding",
    ],
)
def test_intent_is_reconstructed_not_trusted_from_echoed_hash(tmp_path, purpose, fault):
    runtime, plan, expectation, args = inputs(tmp_path, purpose)
    if fault == "arguments":
        plan = replace(plan, arguments=("--anything",))
    elif fault == "request-extra":
        object.__setattr__(plan.request, "extra", True)
    elif fault == "list-controls":
        plan = replace(plan, request=replace(plan.request, controls=[]))
    elif fault == "wrong-helper":
        plan = replace(plan, request=replace(plan.request, helper_sha256="9" * 64))
    elif fault == "changed-mode":
        plan = replace(
            plan, request=replace(plan.request, mode=NativeCameraMode(8, 2, 9, 1))
        )
    elif fault == "short-native-budget":
        plan = replace(
            plan,
            request=replace(
                plan.request, budget=replace(plan.request.budget, duration_ms=4999)
            ),
        )
    elif fault == "changed-binding":
        plan = replace(
            plan,
            request=replace(
                plan.request,
                binding=replace(
                    plan.request.binding,
                    symbolic_link="other",
                    endpoint_sha256=digest(b"other"),
                ),
            ),
        )
    with pytest.raises((ValueError, CameraWorkerError)):
        prepare_owned_activation(runtime, plan, expectation, **args)


@pytest.mark.parametrize("purpose", ["probe", "capture"])
@pytest.mark.parametrize("boundary", ["begin", "release"])
@pytest.mark.parametrize(
    "fault", ["cancel", "deny", "boolean", "slow", "mutate", "reverse"]
)
def test_stop_stale_scope_and_deadline_prevent_one_use_release(
    tmp_path, purpose, boundary, fault
):
    def callback(exact, clock, cancel, count):
        if count != (1 if boundary == "begin" else 2):
            return
        if fault == "cancel":
            cancel.set()
        elif fault == "deny":
            raise PermissionError("Original consumed scope changed")
        elif fault == "boolean":
            return True
        elif fault == "slow":
            clock.now += 31_000_000_000
        elif fault == "mutate":
            object.__setattr__(exact, "payload", b"{}")
        elif fault == "reverse":
            clock.now = 1

    parent, prepared, clock, cancel, calls = setup(tmp_path, purpose, callback)
    if boundary == "begin":
        with pytest.raises((ValueError, PermissionError)):
            parent.begin(deadline_ns=30_000_000_000)
    else:
        begin_ready(parent, prepared)
        with pytest.raises((ValueError, PermissionError)):
            parent.check_release()
    assert parent.view()["state"] == "FAILED_NO_RETRY"
    count = len(calls)
    with pytest.raises(ValueError):
        parent.begin(deadline_ns=100_000_000_000)
    assert len(calls) == count


@pytest.mark.parametrize("purpose", ["probe", "capture"])
def test_v1_preparation_readers_do_not_accept_v2(tmp_path, purpose):
    prepared = preparation(tmp_path, purpose)
    for previous in (PreparedOwnedNativeProbe, PreparedOwnedNativeCapture):
        with pytest.raises(ValueError):
            previous(prepared.payload)


def test_capture_output_is_exactly_the_assigned_child_of_cwd(tmp_path):
    data = preparation(tmp_path, "capture").to_dict()
    data["working_directory"] = str(tmp_path / "another")
    with pytest.raises(ValueError, match="PRIVATE_CAPTURE_DIRECTORY"):
        PreparedOwnedNativeActivation(canonical(data))


@pytest.mark.parametrize("purpose", ["probe", "capture"])
def test_v2_parent_counts_ready_and_result_against_one_stdout_cap(tmp_path, purpose):
    parent, prepared, clock, cancel, calls = setup(tmp_path, purpose)
    begin_ready(parent, prepared)
    parent.check_release()
    _, _, raw = result_fixture(purpose)
    raw.update(
        request_sha256=prepared.admission_request.request_sha256, permit_sha256="f" * 64
    )
    wire = canonical(raw)
    # Still within the result codec's cap, but not the complete process stream.
    wire += b" " * (256 * 1024 - len(wire))
    with pytest.raises(ValueError, match="RESULT_COMBINED_STDOUT_LIMIT"):
        parent.accept_result(wire, returncode=0)
    assert parent.view()["state"] == "FAILED_NO_RETRY"
