from __future__ import annotations

from dataclasses import replace
import hashlib
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable

from PIL import Image
import pytest

import rocell.application.camera_capture_dataset as dataset_module
from rocell.application.camera_capture_dataset import (
    CameraCaptureDatasetStore,
    CameraDatasetCancelled,
    CameraDatasetError,
    CaptureBinding,
    CapturePlan,
    DatasetQuotas,
    DeviceIdentity,
    FramePlan,
    NativeFrameInput,
    PreviewInput,
    PreviewTransform,
    SampleLayout,
    SampleTiming,
    VideoMode,
    iter_native_frame,
    verify_capture_dataset,
)


def plan(
    *, count: int = 1, padded: bool = False, preview: PreviewTransform | None = None
) -> CapturePlan:
    mode = VideoMode(4, 3, 9, 1)
    binding = CaptureBinding(
        "SYNTHETIC",
        "a" * 64,
        "campaign-test",
        "settings-1",
        DeviceIdentity("SYNTHETIC", "synthetic-camera-1"),
        mode,
        mode,
    )
    return CapturePlan(
        binding,
        SampleLayout(10 if padded else 8),
        tuple(FramePlan(f"frame-{index}", preview=preview) for index in range(count)),
    )


def frame(
    index: int = 0,
    *,
    data: bytes = bytes(range(24)),
    preview: PreviewInput | None = None,
) -> NativeFrameInput:
    return NativeFrameInput(
        f"frame-{index}",
        SampleTiming(index, index * 100, index * 100 + 50),
        (data[:5], data[5:]),
        preview,
    )


def store(root: Path, *, chunk_bytes: int = 8) -> CameraCaptureDatasetStore:
    return CameraCaptureDatasetStore(
        root, quotas=DatasetQuotas(chunk_bytes=chunk_bytes, disk_reserve_bytes=0)
    )


def read_manifest(path: Path) -> dict[str, Any]:
    return json.loads((path / "manifest.json").read_text(encoding="ascii"))


def rewrite(path: Path, document: dict[str, Any]) -> None:
    # Deliberate corruption of this test's isolated publication, never a user
    # dataset or operational evidence repair.
    path.write_bytes(dataset_module._json(document))


def test_constructor_and_status_do_not_touch_filesystem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "missing"

    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("status performed filesystem I/O")

    monkeypatch.setattr(dataset_module, "safe_root", forbidden)
    monkeypatch.setattr(dataset_module.shutil, "disk_usage", forbidden)
    writer = store(root)
    assert writer.status()["hardware_io_available"] is False
    assert writer.status()["m1_qualified"] is False
    assert not root.exists()


def test_round_trip_streams_padded_native_bytes_and_exact_bindings(
    tmp_path: Path,
) -> None:
    planned = plan(padded=True)
    data = bytes(range(30))
    receipt = store(tmp_path).publish(planned, [frame(data=data)])
    verified = verify_capture_dataset(
        receipt.path,
        expected_manifest_sha256=receipt.manifest_sha256,
        expected_binding=planned.binding,
    )
    assert verified.content_verified is True
    assert verified.plan == planned
    assert verified.logical_bytes == 30
    assert verified.requested_mode_matches is True
    assert verified.physical_authority is verified.m1_qualified is False
    assert b"".join(iter_native_frame(receipt.path, "frame-0")) == data
    assert set(item.name for item in receipt.path.iterdir()) == {
        "capture-plan.json",
        "manifest.json",
        "chunks",
    }
    assert all(item.stat().st_size <= 8 for item in (receipt.path / "chunks").iterdir())
    assert (receipt.path / "manifest.json").stat().st_nlink == 1


def test_requested_mode_mismatch_is_retained_not_calibration_success(
    tmp_path: Path,
) -> None:
    selected = plan()
    selected = replace(
        selected,
        binding=replace(selected.binding, requested_mode=VideoMode(8, 6, 9, 1)),
    )
    receipt = store(tmp_path).publish(selected, [frame()])
    verified = verify_capture_dataset(receipt.path)
    assert verified.requested_mode_matches is False
    assert verified.physical_authority is False


def test_thirty_two_frame_dataset_has_precommitted_disjoint_partitions(
    tmp_path: Path,
) -> None:
    selected = plan(count=32)
    selected = replace(
        selected,
        frames=tuple(
            replace(
                item,
                partition="CALIBRATION_TRAIN" if index < 24 else "CALIBRATION_HOLDOUT",
            )
            for index, item in enumerate(selected.frames)
        ),
    )
    receipt = store(tmp_path).publish(selected, (frame(index) for index in range(32)))
    verified = verify_capture_dataset(receipt.path)
    assert verified.frames == 32
    assert verified.logical_bytes == 24 * 32
    assert (
        len(read_manifest(receipt.path)["chunks"]) == 3
    )  # shared content, distinct frame provenance
    assert (
        sum(item.partition == "CALIBRATION_HOLDOUT" for item in verified.plan.frames)
        == 8
    )


@pytest.mark.parametrize("count", [0, 33])
def test_zero_or_excessive_planned_frames_rejected(count: int) -> None:
    with pytest.raises(CameraDatasetError):
        plan(count=count)


def test_partition_assignment_and_frame_ids_are_strict() -> None:
    selected = plan(count=2)
    with pytest.raises(CameraDatasetError, match="unique"):
        replace(selected, frames=(FramePlan("same"), FramePlan("same")))
    with pytest.raises(CameraDatasetError, match="both train and holdout"):
        replace(selected, frames=(FramePlan("train", "CALIBRATION_TRAIN"),))
    with pytest.raises(CameraDatasetError):
        FramePlan("../../outside")


@pytest.mark.parametrize("items", [[], [frame(), frame(1)]])
def test_iterator_underrun_or_overrun_never_commits(
    tmp_path: Path, items: list[NativeFrameInput]
) -> None:
    with pytest.raises(CameraDatasetError, match="count"):
        store(tmp_path).publish(plan(), items)
    partial = next(tmp_path.iterdir())
    assert not (partial / "manifest.json").exists()
    with pytest.raises(CameraDatasetError):
        verify_capture_dataset(partial)


@pytest.mark.parametrize("data", [b"a" * 23, b"a" * 25])
def test_sample_length_must_equal_stride_times_height(
    tmp_path: Path, data: bytes
) -> None:
    with pytest.raises(CameraDatasetError):
        store(tmp_path).publish(plan(), [frame(data=data)])
    assert not list(tmp_path.glob("*/manifest.json"))


@pytest.mark.parametrize(
    "blocks",
    [[b""], [bytearray(b"a" * 24)], [b"a" * (dataset_module.MAX_CHUNK_BYTES + 1)]],
)
def test_stream_blocks_are_bounded_immutable_bytes(
    tmp_path: Path, blocks: Iterable[bytes]
) -> None:
    supplied = replace(frame(), chunks=blocks)
    with pytest.raises(CameraDatasetError):
        store(tmp_path).publish(plan(), [supplied])
    assert not list(tmp_path.glob("*/manifest.json"))


def test_cancel_after_last_frame_before_manifest_leaves_uncommitted_tree(
    tmp_path: Path,
) -> None:
    canceled = False

    def frames() -> Iterable[NativeFrameInput]:
        nonlocal canceled
        yield frame()
        canceled = True  # iterator exhaustion occurs before final publication

    with pytest.raises(CameraDatasetCancelled):
        store(tmp_path).publish(plan(), frames(), cancelled=lambda: canceled)
    partial = next(tmp_path.iterdir())
    assert not (partial / "manifest.json").exists()
    with pytest.raises(CameraDatasetError):
        verify_capture_dataset(partial)


def test_cancel_after_first_chunk_stops_rechunking_one_large_input_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = dataset_module._new_file
    canceled = False
    writes: list[Path] = []

    def cancel_after_first_write(path: Path, payload: bytes) -> None:
        nonlocal canceled
        if path.suffix == ".bin":
            writes.append(path)
            # Fail immediately if the checkpoint regresses, instead of allowing
            # thousands of slow fsync operations during this regression test.
            assert len(writes) == 1, "Payload write continued after cancellation"
            original(path, payload)
            canceled = True
        else:
            original(path, payload)

    monkeypatch.setattr(dataset_module, "_new_file", cancel_after_first_write)
    mode = VideoMode(1024, 512, 9, 1)
    selected = plan()
    selected = replace(
        selected,
        binding=replace(selected.binding, requested_mode=mode, observed_mode=mode),
        layout=SampleLayout(2048),
    )
    # One maximum-sized producer block contains 4096 distinct planned chunks.
    block = b"".join(index.to_bytes(4, "little") + bytes(252) for index in range(4096))
    assert len(block) == dataset_module.MAX_CHUNK_BYTES
    with pytest.raises(CameraDatasetCancelled):
        store(tmp_path, chunk_bytes=256).publish(
            selected,
            [replace(frame(), chunks=(block,))],
            cancelled=lambda: canceled,
        )
    partial = next(tmp_path.iterdir())
    assert len(writes) == len(list((partial / "chunks").iterdir())) == 1
    assert not (partial / "manifest.json").exists()
    with pytest.raises(CameraDatasetError):
        verify_capture_dataset(partial)


def test_cancel_after_manifest_staging_still_does_not_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = dataset_module._new_file
    canceled = False

    def stage(path: Path, payload: bytes) -> None:
        nonlocal canceled
        original(path, payload)
        if path.name == "manifest.pending":
            canceled = True

    monkeypatch.setattr(dataset_module, "_new_file", stage)
    with pytest.raises(CameraDatasetCancelled):
        store(tmp_path).publish(plan(), [frame()], cancelled=lambda: canceled)
    partial = next(tmp_path.iterdir())
    assert (partial / "manifest.pending").exists()
    assert not (partial / "manifest.json").exists()
    with pytest.raises(CameraDatasetError):
        verify_capture_dataset(partial)


def test_manifest_fsync_failure_never_leaves_valid_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = dataset_module._new_file

    def failure(path: Path, payload: bytes) -> None:
        original(path, payload)
        if path.name == "manifest.pending":
            raise OSError("injected flush uncertainty")

    monkeypatch.setattr(dataset_module, "_new_file", failure)
    with pytest.raises(OSError):
        store(tmp_path).publish(plan(), [frame()])
    partial = next(tmp_path.iterdir())
    with pytest.raises(CameraDatasetError):
        verify_capture_dataset(partial)


@pytest.mark.parametrize("failure_mode", ["flush", "cancel", "unlink"])
def test_complete_manifest_with_pending_sentinel_is_not_accepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure_mode: str
) -> None:
    original = dataset_module._new_file
    original_unlink = Path.unlink
    canceled = False

    def write(path: Path, payload: bytes) -> None:
        nonlocal canceled
        original(path, payload)
        if path.name == "manifest.json":
            if failure_mode == "flush":
                raise OSError("injected final flush uncertainty")
            canceled = failure_mode == "cancel"

    def unlink(path: Path, *args, **kwargs) -> None:
        if path.name == "manifest.pending" and failure_mode == "unlink":
            raise OSError("injected sentinel removal failure")
        original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(dataset_module, "_new_file", write)
    monkeypatch.setattr(Path, "unlink", unlink)
    expected_error = CameraDatasetCancelled if failure_mode == "cancel" else OSError
    with pytest.raises(expected_error):
        store(tmp_path).publish(plan(), [frame()], cancelled=lambda: canceled)
    partial = next(tmp_path.iterdir())
    assert (partial / "manifest.json").read_bytes() == (
        partial / "manifest.pending"
    ).read_bytes()
    with pytest.raises(CameraDatasetError):
        verify_capture_dataset(partial)


def test_writer_does_not_overwrite_even_if_dataset_uuid_collides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        dataset_module.uuid, "uuid4", lambda: SimpleNamespace(hex="f" * 32)
    )
    writer = store(tmp_path)
    first = writer.publish(plan(), [frame()])
    before = (first.path / "manifest.json").read_bytes()
    with pytest.raises(FileExistsError):
        writer.publish(plan(), [frame()])
    assert (first.path / "manifest.json").read_bytes() == before
    assert verify_capture_dataset(first.path).content_verified


def test_disk_preflight_and_quotas_do_not_begin_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        dataset_module.shutil, "disk_usage", lambda _: SimpleNamespace(free=0)
    )
    with pytest.raises(CameraDatasetError, match="disk"):
        store(tmp_path).publish(plan(), [frame()])
    assert list(tmp_path.iterdir()) == []
    bounded = CameraCaptureDatasetStore(tmp_path, quotas=DatasetQuotas(frame_bytes=20))
    with pytest.raises(CameraDatasetError, match="quota"):
        bounded.publish(plan(), [frame()])
    assert list(tmp_path.iterdir()) == []


def test_missing_destination_is_not_created_implicitly(tmp_path: Path) -> None:
    root = tmp_path / "not-assigned-yet"
    with pytest.raises(CameraDatasetError, match="already exist"):
        store(root).publish(plan(), [frame()])
    assert not root.exists()


def test_derived_preview_has_explicit_transform_and_native_digest(
    tmp_path: Path,
) -> None:
    encoded = io.BytesIO()
    Image.new("RGB", (4, 3), "green").save(encoded, format="PNG")
    data = bytes(range(24))
    transform = PreviewTransform(0, 0, 4, 3, 4, 3, maximum_bytes=1024)
    preview = PreviewInput(hashlib.sha256(data).hexdigest(), [encoded.getvalue()])
    receipt = store(tmp_path, chunk_bytes=64).publish(
        plan(preview=transform), [frame(preview=preview)]
    )
    verified = verify_capture_dataset(receipt.path)
    assert verified.plan.frames[0].preview == transform
    record = read_manifest(receipt.path)["frames"][0]
    assert record["preview"]["native_sha256"] == record["native"]["sha256"]
    assert verified.physical_authority is False


def test_wrong_preview_native_hash_never_commits(tmp_path: Path) -> None:
    transform = PreviewTransform(0, 0, 4, 3, 4, 3, maximum_bytes=1024)
    with pytest.raises(CameraDatasetError, match="different native"):
        store(tmp_path, chunk_bytes=64).publish(
            plan(preview=transform),
            [frame(preview=PreviewInput("0" * 64, [b"not used"]))],
        )
    assert not list(tmp_path.glob("*/manifest.json"))


def test_wrong_encoded_preview_dimensions_never_commit(tmp_path: Path) -> None:
    encoded = io.BytesIO()
    Image.new("RGB", (2, 2), "green").save(encoded, format="PNG")
    transform = PreviewTransform(0, 0, 4, 3, 4, 3, maximum_bytes=1024)
    with pytest.raises(CameraDatasetError, match="declared encoded image"):
        store(tmp_path, chunk_bytes=64).publish(
            plan(preview=transform),
            [
                frame(
                    preview=PreviewInput(
                        hashlib.sha256(bytes(range(24))).hexdigest(),
                        [encoded.getvalue()],
                    )
                )
            ],
        )


@pytest.mark.parametrize(
    "transform",
    [
        PreviewTransform(1, 0, 4, 3, 4, 3),
        PreviewTransform(0, 0, 4, 3, 8, 6),
        PreviewTransform(0, 0, 4, 3, 2, 2),
        PreviewTransform(0, 0, 4, 3, 4, 3, rotation_degrees=90),
    ],
)
def test_preview_transform_cannot_crop_outside_upscale_or_distort(
    transform: PreviewTransform,
) -> None:
    with pytest.raises(CameraDatasetError):
        plan(preview=transform)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value.update(status="VERIFIED_ON_RECEIVED_UNIT"),
        lambda value: value.update(status="IN_PROGRESS"),
        lambda value: value["declarations"].update(physical_authority=True),
        lambda value: value["declarations"].update(physical_authority=0),
        lambda value: value["declarations"].update(m1_qualified=True),
        lambda value: value.update(logical_bytes=25),
        lambda value: value["frames"][0].update(partition="CALIBRATION_HOLDOUT"),
        lambda value: value["frames"][0]["native"].update(bytes=23),
        lambda value: value["chunks"].append(value["chunks"][0].copy()),
        lambda value: value["frames"][0]["native"]["chunks"].append("a" * 64),
        lambda value: value["frames"][0]["native"]["chunks"].__setitem__(
            0, "../../outside"
        ),
        lambda value: value["frames"][0]["timing"].update(host_sequence=True),
        lambda value: value["frames"][0]["timing"].update(
            sample_time_provenance="SENSOR_EXPOSURE"
        ),
        lambda value: value.update(extra="unexpected"),
    ],
)
def test_manifest_mutations_fail_closed(tmp_path: Path, mutate: Any) -> None:
    receipt = store(tmp_path).publish(plan(), [frame()])
    manifest = read_manifest(receipt.path)
    mutate(manifest)
    rewrite(receipt.path / "manifest.json", manifest)
    with pytest.raises(CameraDatasetError):
        verify_capture_dataset(receipt.path)


def test_duplicate_json_fields_are_rejected(tmp_path: Path) -> None:
    receipt = store(tmp_path).publish(plan(), [frame()])
    path = receipt.path / "manifest.json"
    payload = path.read_bytes()
    path.write_bytes(
        payload.replace(b'{"chunk_bytes":8,', b'{"chunk_bytes":8,"chunk_bytes":8,', 1)
    )
    with pytest.raises(CameraDatasetError):
        verify_capture_dataset(receipt.path)


def test_content_tier_detects_corruption_metadata_tier_makes_no_content_claim(
    tmp_path: Path,
) -> None:
    receipt = store(tmp_path).publish(plan(), [frame()])
    chunk = next((receipt.path / "chunks").iterdir())
    chunk.write_bytes(b"x" * chunk.stat().st_size)
    assert (
        verify_capture_dataset(receipt.path, tier="metadata").content_verified is False
    )
    with pytest.raises(CameraDatasetError, match="digest"):
        verify_capture_dataset(receipt.path)


@pytest.mark.parametrize("second_blob", ["native", "preview"])
def test_cumulative_budget_rejects_second_blob_before_its_content_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, second_blob: str
) -> None:
    if second_blob == "native":
        receipt = store(tmp_path).publish(
            plan(count=2), [frame(), frame(1, data=bytes(range(24, 48)))]
        )
    else:
        encoded = io.BytesIO()
        Image.new("RGB", (4, 3), "green").save(encoded, format="PNG")
        preview = PreviewInput(
            hashlib.sha256(bytes(range(24))).hexdigest(), [encoded.getvalue()]
        )
        receipt = store(tmp_path).publish(
            plan(preview=PreviewTransform(0, 0, 4, 3, 4, 3, maximum_bytes=1024)),
            [frame(preview=preview)],
        )
    manifest = read_manifest(receipt.path)
    first_frame_chunks = manifest["frames"][0]["native"]["chunks"]
    # Scale the global ceiling instead of allocating two huge frames. The false
    # total passes the manifest field bound, but the actual native/preview blobs
    # exceed it. Neither kind of second blob may begin its content reads.
    manifest["logical_bytes"] = 32
    rewrite(receipt.path / "manifest.json", manifest)
    monkeypatch.setattr(dataset_module, "MAX_DATASET_BYTES", 32)
    original_read = dataset_module.read_bounded_regular_file
    content_reads: list[str] = []

    def tracked_read(path: Path, *, maximum_bytes: int) -> bytes:
        if path.parent.name == "chunks":
            content_reads.append(path.stem)
        return original_read(path, maximum_bytes=maximum_bytes)

    monkeypatch.setattr(dataset_module, "read_bounded_regular_file", tracked_read)
    with pytest.raises(CameraDatasetError, match="cumulative byte budget"):
        verify_capture_dataset(receipt.path)
    assert content_reads == first_frame_chunks


def test_expected_external_manifest_and_binding_are_checked(tmp_path: Path) -> None:
    selected = plan()
    receipt = store(tmp_path).publish(selected, [frame()])
    with pytest.raises(CameraDatasetError, match="externally retained"):
        verify_capture_dataset(receipt.path, expected_manifest_sha256="b" * 64)
    with pytest.raises(CameraDatasetError, match="expected device"):
        verify_capture_dataset(
            receipt.path,
            expected_binding=replace(
                selected.binding, campaign_id="different-campaign"
            ),
        )


def test_declared_physical_source_is_not_hardware_acceptance(tmp_path: Path) -> None:
    selected = plan()
    selected = replace(
        selected,
        binding=replace(
            selected.binding,
            provenance="PHYSICAL_UNVERIFIED",
            device=DeviceIdentity(
                "WINDOWS_MEDIA_FOUNDATION", "opaque-device-id", 1234, 5678, "observed"
            ),
        ),
    )
    # These are caller-supplied fixture bytes, not an actual capture. Even this
    # declared physical provenance must never become qualified hardware evidence.
    supplied = replace(frame(), timing=SampleTiming(0, 0, 50, 10, "MEDIA_SAMPLE_TIME"))
    receipt = store(tmp_path).publish(selected, [supplied])
    verified = verify_capture_dataset(receipt.path, expected_binding=selected.binding)
    assert verified.plan.binding.provenance == "PHYSICAL_UNVERIFIED"
    assert verified.physical_authority is verified.m1_qualified is False
    manifest = read_manifest(receipt.path)
    manifest["frames"][0]["timing"]["sample_time_provenance"] = "SYNTHETIC_SAMPLE_TIME"
    rewrite(receipt.path / "manifest.json", manifest)
    with pytest.raises(CameraDatasetError, match="provenance"):
        verify_capture_dataset(receipt.path)


def test_repeated_sequence_or_synthetic_media_timing_never_commits(
    tmp_path: Path,
) -> None:
    with pytest.raises(CameraDatasetError, match="regressed"):
        store(tmp_path).publish(
            plan(count=2), [frame(), replace(frame(1), timing=frame().timing)]
        )
    with pytest.raises(CameraDatasetError, match="provenance"):
        store(tmp_path).publish(
            plan(),
            [replace(frame(), timing=SampleTiming(0, 0, 50, 10, "MEDIA_SAMPLE_TIME"))],
        )
    assert not list(tmp_path.glob("*/manifest.json"))


def test_missing_chunk_and_reordered_chunks_are_detected(tmp_path: Path) -> None:
    receipt = store(tmp_path).publish(plan(), [frame()])
    manifest = read_manifest(receipt.path)
    manifest["frames"][0]["native"]["chunks"].reverse()
    rewrite(receipt.path / "manifest.json", manifest)
    with pytest.raises(CameraDatasetError, match="sample digest"):
        verify_capture_dataset(receipt.path)
    next((receipt.path / "chunks").iterdir()).unlink()
    with pytest.raises(CameraDatasetError, match="missing"):
        verify_capture_dataset(receipt.path, tier="metadata")


def test_plan_mutation_does_not_match_committed_plan_digest(tmp_path: Path) -> None:
    receipt = store(tmp_path).publish(plan(), [frame()])
    path = receipt.path / "capture-plan.json"
    document = json.loads(path.read_text(encoding="ascii"))
    document["plan"]["binding"]["source_sha256"] = "f" * 64
    rewrite(path, document)
    with pytest.raises(CameraDatasetError, match="plan digest"):
        verify_capture_dataset(receipt.path)


def test_disk_full_during_chunk_write_never_commits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = dataset_module._new_file

    def disk_full(path: Path, payload: bytes) -> None:
        original(path, payload)
        if path.suffix == ".bin":
            raise OSError("injected disk full after partial payload")

    monkeypatch.setattr(dataset_module, "_new_file", disk_full)
    with pytest.raises(OSError, match="disk full"):
        store(tmp_path).publish(plan(), [frame()])
    partial = next(tmp_path.iterdir())
    assert not (partial / "manifest.json").exists()
    with pytest.raises(CameraDatasetError):
        verify_capture_dataset(partial)


def test_unknown_frame_and_untyped_quotas_fail_closed(tmp_path: Path) -> None:
    receipt = store(tmp_path).publish(plan(), [frame()])
    with pytest.raises(CameraDatasetError, match="Unknown frame"):
        list(iter_native_frame(receipt.path, "not-planned"))
    with pytest.raises(CameraDatasetError, match="explicitly typed"):
        CameraCaptureDatasetStore(tmp_path, quotas={})  # type: ignore[arg-type]


@pytest.mark.parametrize("where", ["root", "chunks"])
def test_unexpected_files_are_rejected(tmp_path: Path, where: str) -> None:
    receipt = store(tmp_path).publish(plan(), [frame()])
    selected = receipt.path if where == "root" else receipt.path / "chunks"
    (selected / "extra.txt").write_text("unexpected", encoding="ascii")
    with pytest.raises(CameraDatasetError):
        verify_capture_dataset(receipt.path)


def test_chunk_hardlink_is_rejected(tmp_path: Path) -> None:
    receipt = store(tmp_path).publish(plan(), [frame()])
    chunk = next((receipt.path / "chunks").iterdir())
    alternate = tmp_path / "extra-link.bin"
    try:
        os.link(chunk, alternate)
    except OSError as error:
        pytest.skip(f"Hard links unavailable: {error}")
    with pytest.raises(CameraDatasetError):
        verify_capture_dataset(receipt.path)


def test_chunk_symlink_is_rejected_even_by_metadata_tier(tmp_path: Path) -> None:
    receipt = store(tmp_path).publish(plan(), [frame()])
    chunk = next((receipt.path / "chunks").iterdir())
    alternate = tmp_path / "outside.bin"
    alternate.write_bytes(chunk.read_bytes())
    chunk.unlink()
    try:
        chunk.symlink_to(alternate)
    except OSError as error:
        pytest.skip(f"Symlinks unavailable: {error}")
    with pytest.raises(CameraDatasetError):
        verify_capture_dataset(receipt.path, tier="metadata")


def test_symlink_dataset_root_is_rejected_before_writing(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    linked = tmp_path / "linked"
    try:
        linked.symlink_to(real, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"Symlinks unavailable: {error}")
    with pytest.raises(CameraDatasetError):
        store(linked).publish(plan(), [frame()])
    assert list(real.iterdir()) == []


@pytest.mark.slow
def test_full_b0477_native_frame_over_32mib_is_streamed_without_large_allocation(
    tmp_path: Path,
) -> None:
    import tracemalloc

    mode = VideoMode(5472, 3648, 9, 1)
    selected = plan()
    selected = replace(
        selected,
        binding=replace(selected.binding, requested_mode=mode, observed_mode=mode),
        layout=SampleLayout(5472 * 2),
    )
    expected = 39_923_712
    assert selected.layout.sample_bytes(mode) == expected
    block = b"\x7f" * (1024 * 1024)

    def stream() -> Iterable[bytes]:
        remaining = expected
        while remaining:
            amount = min(len(block), remaining)
            yield block if amount == len(block) else block[:amount]
            remaining -= amount

    tracemalloc.start()
    try:
        receipt = store(tmp_path, chunk_bytes=len(block)).publish(
            selected, [replace(frame(), chunks=stream())]
        )
        verified = verify_capture_dataset(receipt.path)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert verified.logical_bytes == expected
    assert (
        sum(len(part) for part in iter_native_frame(receipt.path, "frame-0"))
        == expected
    )
    assert peak < 12 * 1024 * 1024
