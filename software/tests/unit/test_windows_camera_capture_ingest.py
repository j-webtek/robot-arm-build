"""Native-receipt/file fixtures only: no camera/helper/serial/authorizer calls."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import io
import json
import os
from pathlib import Path
from types import MappingProxyType

from PIL import Image
import pytest

import rocell.application.windows_camera_capture_ingest as bridge

from rocell.application.camera_capture_dataset import (
    CameraDatasetCancelled,
    DatasetQuotas,
    FramePlan,
    PreviewTransform,
    VideoMode,
    iter_native_frame,
    verify_capture_dataset,
)
from rocell.application.windows_camera_capture_ingest import (
    CameraCaptureIngestError,
    COLOR_POLICY,
    ingest_windows_capture,
    prepare_windows_camera_ingest,
    render_yuy2_preview,
    verify_windows_capture_ingest,
)
from rocell.providers.windows.camera_worker_client import (
    CameraActivationRequest,
    CameraCampaignBudget,
    CameraCandidate,
    CameraEndpointBinding,
    NativeCameraMode,
    NativeCameraReceipt,
    NativeFrameArtifact,
)


ENDPOINT = r"\\?\incapable#camera-fixture-only"


def reverify(result, request, plan, **overrides):
    expected = {
        "expected_source_sha256": request.source_sha256,
        "expected_settings_epoch": plan.settings_epoch,
        "expected_campaign_id": request.campaign_id,
        "expected_endpoint_sha256": request.binding.endpoint_sha256,
    }
    expected.update(overrides)
    value = result.to_dict() if hasattr(result, "to_dict") else result
    return verify_windows_capture_ingest(value, **expected)


def fixture(tmp_path: Path, *, bottom_up=False, count=1, preview=True):
    capture = tmp_path / "native-input"
    output = tmp_path / "datasets"
    capture.mkdir()
    output.mkdir()
    stride = -10 if bottom_up else 10
    mode = NativeCameraMode(4, 3, 9, 1, stride_bytes=stride)
    binding = CameraEndpointBinding(
        ENDPOINT, hashlib.sha256(ENDPOINT.encode()).hexdigest(), "b" * 64
    )
    request = CameraActivationRequest(
        "fixture-campaign",
        "a" * 64,
        "capture",
        binding,
        mode,
        (),
        CameraCampaignBudget(max_frames=count),
        "c" * 64,
        "d" * 64,
        str(capture),
    )
    frame_plans = tuple(
        FramePlan(
            f"frame-{i:06d}",
            preview=(
                PreviewTransform(0, 0, 4, 3, 4, 3, maximum_bytes=1024)
                if preview and i == count - 1
                else None
            ),
        )
        for i in range(count)
    )
    plan = prepare_windows_camera_ingest(
        request,
        capture_directory=capture,
        dataset_root=output,
        source_sha256=request.source_sha256,
        settings_epoch="settings-fixture",
        domain="INCAPABLE_NATIVE_FIXTURE",
        frames=frame_plans,
        quotas=DatasetQuotas(disk_reserve_bytes=0),
    )
    rows = [
        bytes([16 + 20 * y, 128, 56 + 20 * y, 128, 96 + 20 * y, 128, 136 + 20 * y, 128])
        + b"\xff\xff"
        for y in range(3)
    ]
    raw = b"".join(reversed(rows) if bottom_up else rows)
    artifacts = []
    for i in range(count):
        name = f"frame-{i:06d}.yuy2"
        (capture / name).write_bytes(raw)
        artifacts.append(
            NativeFrameArtifact(
                name,
                len(raw),
                stride,
                20 if bottom_up else 0,
                i,
                i * 10_000,
                i * 1_000_000 + 1,
                10_000_000,
                None,
                hashlib.sha256(raw).hexdigest(),
            )
        )
    counts = {
        "source_activation_attempts": 1,
        "source_opened": 1,
        "control_set_attempts": 0,
        "samples_received": count,
        "frames_written": count,
        "source_shutdown_attempts": 1,
    }
    receipt = NativeCameraReceipt(
        "capture",
        "OK",
        None,
        ENDPOINT,
        (CameraCandidate(ENDPOINT, "Synthetic fixture"),),
        (mode,),
        mode,
        mode,
        (),
        tuple(artifacts),
        MappingProxyType(counts),
        True,
        (),
    )
    return request, receipt, plan, rows, raw


def expected_gray(y: int, x: int) -> int:
    return max(0, min(255, (298 * (20 * y + 40 * x) + 128) >> 8))


@pytest.mark.parametrize("bottom_up", [False, True])
def test_roundtrip_real_bytes_padding_roworder_and_latest_png(tmp_path, bottom_up):
    request, receipt, plan, rows, raw = fixture(tmp_path, bottom_up=bottom_up, count=2)
    result = ingest_windows_capture(request, receipt, plan=plan)
    assert result.dataset.frames == 2 and result.verification.content_verified
    assert not result.physical_authority and not result.m1_qualified
    assert result.domain == "INCAPABLE_NATIVE_FIXTURE"
    assert b"".join(iter_native_frame(result.dataset.path, "frame-000001")) == raw
    assert result.latest_preview is not None
    assert result.latest_preview.frame_id == "frame-000001"
    assert result.latest_preview.color_policy == COLOR_POLICY
    with Image.open(io.BytesIO(result.latest_preview.png_bytes)) as image:
        assert image.size == (4, 3)
        for y in range(3):
            for x in range(4):
                assert image.getpixel((x, y)) == (expected_gray(y, x),) * 3
    value = result.to_dict()
    assert value["dataset"]["path"] == str(result.dataset.path)
    assert value["dataset"]["manifest_sha256"] == result.dataset.manifest_sha256
    assert "png_bytes" not in value["latest_preview"]
    envelope = json.loads(result.envelope_path.read_bytes())
    assert envelope["physical_authority"] is envelope["m1_qualified"] is False
    assert (
        hashlib.sha256(result.envelope_path.read_bytes()).hexdigest()
        == result.envelope_sha256
    )
    source = json.loads(
        (result.envelope_path.parent / "source-contract.json").read_bytes()
    )
    assert source["native_receipt"]["frames"][0]["host_arrival_qpc"] == 1
    assert source["native_receipt"]["frames"][0]["qpc_frequency"] == 10_000_000
    assert source["activation_request"]["binding"]["symbolic_link"] == ENDPOINT
    manifest = json.loads((result.dataset.path / "manifest.json").read_bytes())
    assert manifest["frames"][0]["timing"]["host_arrival_start_ns"] == 100
    assert (
        manifest["frames"][0]["timing"]["sample_time_provenance"]
        == "SYNTHETIC_SAMPLE_TIME"
    )
    assert source["timing_conversion"].startswith("QPC_POINT")


def test_prepare_is_inert_and_can_precede_assigned_directory_creation(tmp_path):
    request, receipt, plan, _, _ = fixture(tmp_path)
    capture = tmp_path / "not-yet-captured"
    output = tmp_path / "not-yet-output"
    request = replace(request, output_directory=str(capture))
    prepared = prepare_windows_camera_ingest(
        request,
        capture_directory=capture,
        dataset_root=output,
        source_sha256=request.source_sha256,
        settings_epoch="epoch",
        domain="INCAPABLE_NATIVE_FIXTURE",
        frames=plan.frames,
    )
    assert not capture.exists() and not output.exists()
    assert prepared.capture_directory == capture


def test_declared_physical_receipt_stays_unverified(tmp_path):
    request, receipt, plan, _, _ = fixture(tmp_path)
    plan = replace(plan, domain="PHYSICAL_UNVERIFIED")
    result = ingest_windows_capture(request, receipt, plan=plan)
    assert result.verification.plan.binding.provenance == "PHYSICAL_UNVERIFIED"
    assert result.verification.plan.binding.device.serial is None
    assert result.verification.plan.binding.device.vid is None
    assert result.verification.plan.binding.device.persistent_id.startswith(
        "endpoint-sha256:"
    )
    assert result.to_dict()["received_hardware_accepted"] is False
    assert result.to_dict()["native_power_loss_qualification"] == "NOT_RUN"


@pytest.mark.parametrize("domain", ["INCAPABLE_NATIVE_FIXTURE", "PHYSICAL_UNVERIFIED"])
def test_reverify_checks_retained_chain_without_original_inputs(tmp_path, domain):
    request, receipt, plan, _, _ = fixture(tmp_path)
    plan = replace(plan, domain=domain)
    result = ingest_windows_capture(request, receipt, plan=plan)
    # Retained samples, not the original provider spool, are the evidence now.
    for path in plan.capture_directory.iterdir():
        path.unlink()
    plan.capture_directory.rmdir()
    before = {p: p.read_bytes() for p in plan.dataset_root.rglob("*") if p.is_file()}
    verified = reverify(MappingProxyType(result.to_dict()), request, plan)
    assert verified == result.verification
    assert not verified.physical_authority and not verified.m1_qualified
    assert before == {p: p.read_bytes() for p in before}


@pytest.mark.parametrize(
    "field,value",
    [
        ("expected_source_sha256", "f" * 64),
        ("expected_settings_epoch", "changed-settings"),
        ("expected_campaign_id", "different-campaign"),
        ("expected_endpoint_sha256", "e" * 64),
    ],
)
def test_reverify_rejects_current_binding_drift(tmp_path, field, value):
    request, receipt, plan, _, _ = fixture(tmp_path)
    result = ingest_windows_capture(request, receipt, plan=plan)
    with pytest.raises(ValueError, match="binding mismatch"):
        reverify(result, request, plan, **{field: value})


@pytest.mark.parametrize("name", ["ingest-receipt.json", "source-contract.json"])
@pytest.mark.parametrize("damage", ["missing", "changed", "oversized", "hardlink"])
def test_reverify_rejects_missing_corrupt_unbounded_or_linked_provenance(
    tmp_path, name, damage
):
    request, receipt, plan, _, _ = fixture(tmp_path)
    result = ingest_windows_capture(request, receipt, plan=plan)
    path = result.envelope_path.parent / name
    if damage == "missing":
        path.unlink()
    elif damage == "changed":
        raw = path.read_bytes()
        path.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
    elif damage == "oversized":
        path.write_bytes(b"x" * (bridge.MAX_CONTRACT_BYTES + 1))
    else:
        os.link(path, tmp_path / "linked-provenance.json")
    with pytest.raises((ValueError, OSError)):
        reverify(result, request, plan)


@pytest.mark.parametrize("kind", ["manifest", "chunk"])
def test_reverify_rejects_inner_dataset_corruption(tmp_path, kind):
    request, receipt, plan, _, _ = fixture(tmp_path)
    result = ingest_windows_capture(request, receipt, plan=plan)
    path = (
        result.dataset.path / "manifest.json"
        if kind == "manifest"
        else next((result.dataset.path / "chunks").glob("*.bin"))
    )
    raw = path.read_bytes()
    path.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
    with pytest.raises(ValueError):
        reverify(result, request, plan)


@pytest.mark.parametrize(
    "change",
    [
        lambda v, p: v.update(schema="rocell.windows_camera_capture_ingest.v2"),
        lambda v, p: v.update(physical_authority=True),
        lambda v, p: v.update(m1_qualified=1),
        lambda v, p: v.update(domain="PHYSICAL_QUALIFIED"),
        lambda v, p: v.update(envelope_path=str(p / "ingest-receipt.json")),
        lambda v, p: v["dataset"].update(path=str(p / ("capture-" + "a" * 32))),
        lambda v, p: v.update(envelope_sha256="e" * 64),
        lambda v, p: v.update(source_contract_sha256="e" * 64),
        lambda v, p: v["dataset"].update(manifest_sha256="e" * 64),
        lambda v, p: v["verification"].update(content_verified=False),
    ],
)
def test_reverify_rejects_receipt_schema_path_hash_or_authority_drift(tmp_path, change):
    request, receipt, plan, _, _ = fixture(tmp_path)
    result = ingest_windows_capture(request, receipt, plan=plan)
    value = result.to_dict()
    change(value, tmp_path)
    with pytest.raises((ValueError, OSError)):
        reverify(value, request, plan)


def test_reverify_rejects_bounded_but_deep_caller_record_before_io(tmp_path):
    nested = {}
    value = nested
    for _ in range(30):
        value["child"] = {}
        value = value["child"]
    with pytest.raises(ValueError, match="nesting"):
        verify_windows_capture_ingest(
            nested,
            expected_source_sha256="a" * 64,
            expected_settings_epoch="fixture",
            expected_campaign_id="fixture",
            expected_endpoint_sha256="b" * 64,
        )
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("kind", ["whitespace", "duplicate"])
def test_reverify_rejects_noncanonical_provenance_even_with_matching_hash(
    tmp_path, kind
):
    request, receipt, plan, _, _ = fixture(tmp_path)
    result = ingest_windows_capture(request, receipt, plan=plan)
    value = result.to_dict()
    raw = result.envelope_path.read_bytes()
    # Model a corrupt historical producer, not a frontend-authorized hash edit.
    raw = b" " + raw if kind == "whitespace" else b'{"schema":"duplicate",' + raw[1:]
    result.envelope_path.write_bytes(raw)
    value["envelope_sha256"] = hashlib.sha256(raw).hexdigest()
    with pytest.raises(ValueError):
        reverify(value, request, plan)


def test_reverify_compares_actual_inner_binding_not_only_outer_claims(tmp_path):
    request, receipt, plan, _, _ = fixture(tmp_path)
    result = ingest_windows_capture(request, receipt, plan=plan)
    value = result.to_dict()
    source_path = result.envelope_path.parent / "source-contract.json"
    source = json.loads(source_path.read_bytes())
    envelope = json.loads(result.envelope_path.read_bytes())
    source["plan"]["settings_epoch"] = "different-settings"
    source_bytes = bridge._json(source)
    source_path.write_bytes(source_bytes)
    value["source_contract_sha256"] = hashlib.sha256(source_bytes).hexdigest()
    envelope["source_contract_sha256"] = value["source_contract_sha256"]
    envelope_bytes = bridge._json(envelope)
    result.envelope_path.write_bytes(envelope_bytes)
    value["envelope_sha256"] = hashlib.sha256(envelope_bytes).hexdigest()
    with pytest.raises(ValueError, match="exact campaign/content binding"):
        reverify(value, request, plan, expected_settings_epoch="different-settings")


@pytest.mark.skipif(os.name != "nt", reason="Windows sharing is a platform guarantee")
def test_reverify_holds_provenance_read_locks_through_content_verification(
    tmp_path, monkeypatch
):
    request, receipt, plan, _, _ = fixture(tmp_path)
    result = ingest_windows_capture(request, receipt, plan=plan)
    paths = (
        result.envelope_path,
        result.envelope_path.parent / "source-contract.json",
        result.dataset.path / "capture-plan.json",
    )
    verifier = bridge.verify_capture_dataset
    observed = []

    def check_locked(*args, **kwargs):
        for path in paths:
            with pytest.raises(OSError):
                with path.open("r+b"):
                    pass
            observed.append(path)
        return verifier(*args, **kwargs)

    monkeypatch.setattr(bridge, "verify_capture_dataset", check_locked)
    assert reverify(result, request, plan).content_verified
    assert tuple(observed) == paths
    # The verifier owns and closes every handle, including after an exception.
    for path in paths:
        with path.open("r+b"):
            pass

    def failed(*args, **kwargs):
        raise ValueError("fixture content failure")

    monkeypatch.setattr(bridge, "verify_capture_dataset", failed)
    with pytest.raises(ValueError, match="fixture content failure"):
        reverify(result, request, plan)
    for path in paths:
        with path.open("r+b"):
            pass


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_renderer_crop_and_clockwise_rotation_are_actual_pixels(rotation):
    mode = VideoMode(4, 4, 9, 1)
    rows = [
        bytes([16 + 20 * y, 128, 56 + 20 * y, 128, 96 + 20 * y, 128, 136 + 20 * y, 128])
        for y in range(4)
    ]
    width, height = (2, 3) if rotation in {0, 180} else (3, 2)
    transform = PreviewTransform(
        1, 1, 2, 3, width, height, rotation_degrees=rotation, maximum_bytes=1024
    )
    encoded = render_yuy2_preview(lambda y: rows[y], mode=mode, transform=transform)
    base = Image.new("RGB", (2, 3))
    base.putdata([(expected_gray(y, x),) * 3 for y in range(1, 4) for x in range(1, 3)])
    expected = base.rotate(-rotation, expand=True)
    with Image.open(io.BytesIO(encoded)) as actual:
        assert actual.size == expected.size and actual.tobytes() == expected.tobytes()


def test_renderer_downsample_uses_predeclared_pixel_centers():
    mode = VideoMode(4, 4, 9, 1)
    rows = [
        bytes([16 + 20 * y, 128, 56 + 20 * y, 128, 96 + 20 * y, 128, 136 + 20 * y, 128])
        for y in range(4)
    ]
    encoded = render_yuy2_preview(
        lambda y: rows[y],
        mode=mode,
        transform=PreviewTransform(0, 0, 4, 4, 2, 2, maximum_bytes=1024),
    )
    with Image.open(io.BytesIO(encoded)) as image:
        assert [image.getpixel((x, y)) for y in range(2) for x in range(2)] == [
            (expected_gray(y, x),) * 3 for y in (1, 3) for x in (1, 3)
        ]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda r: replace(r, selected_endpoint="other-endpoint"),
        lambda r: replace(r, cleanup_confirmed=False),
        lambda r: replace(r, operation="probe"),
        lambda r: replace(r, status="FAILED", reason_code="INJECTED"),
        lambda r: replace(r, candidates=()),
        lambda r: replace(r, candidates=r.candidates * 2),
        lambda r: replace(r, modes=()),
        lambda r: replace(r, observed_mode=replace(r.observed_mode, fps_numerator=10)),
        lambda r: replace(r, counts={**r.counts, "source_opened": False}),
        lambda r: replace(r, counts={**r.counts, "frames_written": 2}),
        lambda r: replace(
            r, frames=(replace(r.frames[0], filename="../outside.yuy2"),)
        ),
        lambda r: replace(r, frames=(replace(r.frames[0], length_bytes=31),)),
        lambda r: replace(r, frames=(replace(r.frames[0], stride_bytes=4),)),
        lambda r: replace(r, frames=(replace(r.frames[0], row0_offset_bytes=2),)),
        lambda r: replace(r, frames=(replace(r.frames[0], host_sequence=1),)),
        lambda r: replace(r, frames=(replace(r.frames[0], media_timestamp_100ns=-1),)),
        lambda r: replace(
            r, frames=(replace(r.frames[0], media_timestamp_100ns=2**63 - 1),)
        ),
        lambda r: replace(r, frames=(replace(r.frames[0], qpc_frequency=0),)),
        lambda r: replace(r, frames=(replace(r.frames[0], discontinuity=True),)),
        lambda r: replace(r, frames=(replace(r.frames[0], sha256="f" * 64),)),
    ],
)
def test_receipt_drift_is_rejected_before_dataset_publication(tmp_path, mutate):
    request, receipt, plan, _, _ = fixture(tmp_path)
    with pytest.raises((ValueError, OSError)):
        ingest_windows_capture(request, mutate(receipt), plan=plan)
    assert not list(plan.dataset_root.iterdir())


@pytest.mark.parametrize(
    "field,value",
    [
        ("campaign_id", "substituted"),
        ("source_sha256", "f" * 64),
        ("helper_sha256", "e" * 64),
        ("arguments_sha256", "e" * 64),
    ],
)
def test_exact_prepared_request_cannot_be_substituted(tmp_path, field, value):
    request, receipt, plan, _, _ = fixture(tmp_path)
    with pytest.raises(CameraCaptureIngestError, match="changed"):
        ingest_windows_capture(replace(request, **{field: value}), receipt, plan=plan)
    assert not list(plan.dataset_root.iterdir())


@pytest.mark.parametrize(
    "mutation", ["extra", "missing", "short", "corrupt", "hardlink"]
)
def test_input_membership_length_hash_and_links_rechecked(tmp_path, mutation):
    request, receipt, plan, _, _ = fixture(tmp_path)
    path = plan.capture_directory / receipt.frames[0].filename
    if mutation == "extra":
        (plan.capture_directory / "unexpected.json").write_text("{}")
    elif mutation == "missing":
        path.unlink()
    elif mutation == "short":
        path.write_bytes(b"short")
    elif mutation == "corrupt":
        path.write_bytes(b"x" * receipt.frames[0].length_bytes)
    else:
        os.link(path, tmp_path / "extra-link")
    with pytest.raises((ValueError, OSError)):
        ingest_windows_capture(request, receipt, plan=plan)
    assert not list(plan.dataset_root.iterdir())


def test_pre_cancel_does_no_output_io(tmp_path):
    request, receipt, plan, _, _ = fixture(tmp_path)
    with pytest.raises(CameraDatasetCancelled):
        ingest_windows_capture(request, receipt, plan=plan, cancelled=lambda: True)
    assert not list(plan.dataset_root.iterdir())


def test_renderer_cancellation_stops_before_read_and_png_budget_is_enforced():
    def forbidden(_):
        raise AssertionError("Read occurred after cancellation")

    mode = VideoMode(4, 3, 9, 1)
    transform = PreviewTransform(0, 0, 4, 3, 4, 3, maximum_bytes=1024)
    with pytest.raises(CameraDatasetCancelled):
        render_yuy2_preview(
            forbidden, mode=mode, transform=transform, cancelled=lambda: True
        )
    with pytest.raises(CameraCaptureIngestError, match="PNG"):
        render_yuy2_preview(
            lambda _: bytes([16, 128, 235, 128] * 2),
            mode=mode,
            transform=replace(transform, maximum_bytes=1),
        )


def test_artifact_quotas_fail_before_input_publication(tmp_path):
    request, receipt, plan, _, _ = fixture(tmp_path)
    plan = replace(plan, quotas=DatasetQuotas(frame_bytes=29, disk_reserve_bytes=0))
    with pytest.raises(CameraCaptureIngestError, match="quotas"):
        ingest_windows_capture(request, receipt, plan=plan)
    assert not list(plan.dataset_root.iterdir())


def test_rational_qpc_rounding_preserves_a_labeled_bracket(tmp_path):
    request, receipt, plan, _, _ = fixture(tmp_path, preview=False)
    receipt = replace(receipt, frames=(replace(receipt.frames[0], qpc_frequency=3),))
    result = ingest_windows_capture(request, receipt, plan=plan)
    manifest = json.loads((result.dataset.path / "manifest.json").read_bytes())
    timing = manifest["frames"][0]["timing"]
    assert (timing["host_arrival_start_ns"], timing["host_arrival_end_ns"]) == (
        333333333,
        333333334,
    )
    assert verify_capture_dataset(result.dataset.path).content_verified


def test_cancel_after_preview_keeps_inputs_and_no_completion_receipt(
    tmp_path, monkeypatch
):
    request, receipt, plan, _, _ = fixture(tmp_path)
    original = bridge.render_yuy2_preview
    cancelled = False

    def render(*args, **kwargs):
        nonlocal cancelled
        result = original(*args, **kwargs)
        cancelled = True
        return result

    monkeypatch.setattr(bridge, "render_yuy2_preview", render)
    with pytest.raises(CameraDatasetCancelled):
        ingest_windows_capture(request, receipt, plan=plan, cancelled=lambda: cancelled)
    assert (plan.capture_directory / receipt.frames[0].filename).exists()
    assert list(plan.dataset_root.glob("*/source-contract.json"))
    assert not list(plan.dataset_root.glob("*/ingest-receipt.json"))


def test_cancel_after_dataset_commit_never_returns_ingest_completion(
    tmp_path, monkeypatch
):
    request, receipt, plan, _, _ = fixture(tmp_path)
    original = bridge.verify_capture_dataset
    cancelled = False

    def verify(*args, **kwargs):
        nonlocal cancelled
        result = original(*args, **kwargs)
        cancelled = True
        return result

    monkeypatch.setattr(bridge, "verify_capture_dataset", verify)
    with pytest.raises(CameraDatasetCancelled):
        ingest_windows_capture(request, receipt, plan=plan, cancelled=lambda: cancelled)
    assert list(plan.dataset_root.glob("*/capture-*/manifest.json"))
    assert not list(plan.dataset_root.glob("*/ingest-receipt.json"))


def test_final_receipt_flush_failure_has_no_completion_marker(tmp_path, monkeypatch):
    request, receipt, plan, _, _ = fixture(tmp_path)
    original = bridge._new_json

    def write(path, payload):
        original(path, payload)
        if path.name == "ingest-receipt.pending":
            raise OSError("injected flush uncertainty")

    monkeypatch.setattr(bridge, "_new_json", write)
    with pytest.raises(OSError, match="flush uncertainty"):
        ingest_windows_capture(request, receipt, plan=plan)
    assert list(plan.dataset_root.glob("*/ingest-receipt.pending"))
    assert not list(plan.dataset_root.glob("*/ingest-receipt.json"))


@pytest.mark.parametrize("failure_mode", ["flush", "cancel", "unlink"])
def test_complete_envelope_with_pending_sentinel_is_not_accepted(
    tmp_path, monkeypatch, failure_mode
):
    request, receipt, plan, _, _ = fixture(tmp_path)
    original = bridge._new_json
    original_unlink = Path.unlink
    cancelled = False

    def write(path, payload):
        nonlocal cancelled
        original(path, payload)
        if path.name == "ingest-receipt.json":
            if failure_mode == "flush":
                raise OSError("injected final flush uncertainty")
            cancelled = failure_mode == "cancel"

    def unlink(path, *args, **kwargs):
        if path.name == "ingest-receipt.pending" and failure_mode == "unlink":
            raise OSError("injected sentinel removal failure")
        original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(bridge, "_new_json", write)
    monkeypatch.setattr(Path, "unlink", unlink)
    expected_error = CameraDatasetCancelled if failure_mode == "cancel" else OSError
    with pytest.raises(expected_error):
        ingest_windows_capture(request, receipt, plan=plan, cancelled=lambda: cancelled)
    final = next(plan.dataset_root.glob("*/ingest-receipt.json"))
    payload = final.read_bytes()
    assert payload == final.with_suffix(".pending").read_bytes()
    # Even a self-consistent completion-shaped reference must not accept the
    # sentinel-bearing tree. This tests the retained verifier independently of
    # the interrupted publisher, which correctly returned no receipt.
    purported = json.loads(payload)
    purported.pop("activation_request_sha256")
    purported.pop("native_receipt_sha256")
    purported["envelope_path"] = str(final)
    purported["envelope_sha256"] = hashlib.sha256(payload).hexdigest()
    with pytest.raises(CameraCaptureIngestError, match="inventory"):
        reverify(purported, request, plan)


@pytest.mark.parametrize("extra_name", ["ingest-receipt.pending", "unexpected.txt"])
def test_retained_ingest_rejects_extra_root_entry(tmp_path, extra_name):
    request, receipt, plan, _, _ = fixture(tmp_path)
    result = ingest_windows_capture(request, receipt, plan=plan)
    (result.envelope_path.parent / extra_name).write_bytes(b"incomplete")
    with pytest.raises(CameraCaptureIngestError, match="inventory"):
        reverify(result, request, plan)


def test_ingest_never_overwrites_an_existing_uuid_directory(tmp_path, monkeypatch):
    from types import SimpleNamespace

    request, receipt, plan, _, _ = fixture(tmp_path)
    monkeypatch.setattr(bridge.uuid, "uuid4", lambda: SimpleNamespace(hex="e" * 32))
    result = ingest_windows_capture(request, receipt, plan=plan)
    before = result.envelope_path.read_bytes()
    with pytest.raises(FileExistsError):
        ingest_windows_capture(request, receipt, plan=plan)
    assert result.envelope_path.read_bytes() == before


def test_unreviewed_native_protocol_and_qualified_domain_rejected(tmp_path):
    _, _, plan, _, _ = fixture(tmp_path)
    with pytest.raises(CameraCaptureIngestError, match="version"):
        replace(plan, native_protocol_schema="rocell.windows_camera.v2")
    with pytest.raises(CameraCaptureIngestError, match="qualified"):
        replace(plan, domain="PHYSICAL_QUALIFIED")


@pytest.mark.skipif(os.name != "nt", reason="Windows regular-file sharing contract")
def test_input_windows_handle_blocks_mutation_until_ingestion_cleanup(
    tmp_path, monkeypatch
):
    request, receipt, plan, _, _ = fixture(tmp_path)
    original = bridge.render_yuy2_preview
    attempts = []

    def render(*args, **kwargs):
        path = plan.capture_directory / receipt.frames[0].filename
        with pytest.raises(OSError):
            path.open("wb")
        attempts.append(True)
        return original(*args, **kwargs)

    monkeypatch.setattr(bridge, "render_yuy2_preview", render)
    result = ingest_windows_capture(request, receipt, plan=plan)
    assert attempts == [True] and result.verification.content_verified
    path = plan.capture_directory / receipt.frames[0].filename
    with path.open("rb+"):
        pass
