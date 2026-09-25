"""Full-sized modeled B0477 pixels through the real file/dataset/preview bridge.

Published nominal mode: 5472 x 3648 YUY2 at 9 fps (Arducam B0477 datasheet).
No camera, Windows device API, helper process, serial port or hardware producer
is used. A constructed native receipt is explicitly incapable fixture evidence;
this test proves byte handling, not receipt authenticity or received-unit modes.
"""

from dataclasses import replace
import hashlib
import io

from PIL import Image
import pytest

from rocell.application.camera_capture_dataset import (
    FramePlan,
    PreviewTransform,
    iter_native_frame,
)
from rocell.application.windows_camera_capture_ingest import (
    ingest_windows_capture,
    prepare_windows_camera_ingest,
)
from rocell.providers.windows.camera_worker_client import NativeCameraMode
from test_windows_camera_capture_ingest import fixture, reverify


WIDTH, HEIGHT = 5472, 3648
RAW_BYTES = WIDTH * HEIGHT * 2


def gray(luma):
    return max(0, min(255, (298 * (luma - 16) + 128) >> 8))


@pytest.mark.parametrize("bottom_up", [False, True])
def test_catalog_sized_yuy2_roundtrip_and_corner_preview(tmp_path, bottom_up):
    # Reuse only the incapable request/receipt construction, retaining its tiny
    # sample unchanged. The full frame has a separate fresh input/output pair.
    request, receipt, _, _, _ = fixture(tmp_path)
    capture = tmp_path / "full-native-input"
    dataset = tmp_path / "full-datasets"
    capture.mkdir()
    dataset.mkdir()
    row_bytes = WIDTH * 2
    stride = -row_bytes if bottom_up else row_bytes
    mode = NativeCameraMode(WIDTH, HEIGHT, 9, 1, stride_bytes=stride)
    request = replace(request, mode=mode, output_directory=str(capture))
    assert RAW_BYTES == 39_923_712
    assert RAW_BYTES <= request.budget.max_frame_bytes
    assert request.budget.max_frames == 1

    # Four known quadrants detect crop/scale/row-order errors without holding a
    # second 40 MB frame in memory. YUY2 pairs have neutral chroma throughout.
    def row(left, right):
        return bytes((left, 128, left, 128)) * (WIDTH // 4) + bytes(
            (right, 128, right, 128)
        ) * (WIDTH // 4)

    top, bottom = row(16, 81), row(235, 145)
    source_sha = hashlib.sha256()
    frame_name = receipt.frames[0].filename
    with (capture / frame_name).open("xb") as stream:
        for y in range(HEIGHT):
            logical_y = HEIGHT - 1 - y if bottom_up else y
            payload = top if logical_y < HEIGHT // 2 else bottom
            assert len(payload) == row_bytes
            stream.write(payload)
            source_sha.update(payload)
    frame = replace(
        receipt.frames[0],
        length_bytes=RAW_BYTES,
        stride_bytes=stride,
        row0_offset_bytes=(HEIGHT - 1) * row_bytes if bottom_up else 0,
        sha256=source_sha.hexdigest(),
    )
    receipt = replace(
        receipt,
        modes=(mode,),
        requested_mode=mode,
        observed_mode=mode,
        frames=(frame,),
    )
    plan = prepare_windows_camera_ingest(
        request,
        capture_directory=capture,
        dataset_root=dataset,
        source_sha256=request.source_sha256,
        settings_epoch="MODELED-full-resolution-settings",
        domain="INCAPABLE_NATIVE_FIXTURE",
        frames=(
            FramePlan(
                "frame-000000",
                preview=PreviewTransform(
                    0, 0, WIDTH, HEIGHT, 912, 608, maximum_bytes=2 * 1024 * 1024
                ),
            ),
        ),
    )
    result = ingest_windows_capture(request, receipt, plan=plan)
    assert result.verification.content_verified and result.dataset.frames == 1
    assert result.domain == "INCAPABLE_NATIVE_FIXTURE"
    assert not result.physical_authority and not result.m1_qualified
    retained_sha = hashlib.sha256()
    retained_bytes = 0
    for block in iter_native_frame(result.dataset.path, "frame-000000"):
        retained_sha.update(block)
        retained_bytes += len(block)
    assert retained_bytes == RAW_BYTES
    assert retained_sha.hexdigest() == source_sha.hexdigest()
    assert result.latest_preview is not None
    with Image.open(io.BytesIO(result.latest_preview.png_bytes)) as preview:
        assert preview.size == (912, 608)
        for point, luma in (
            ((0, 0), 16),
            ((911, 0), 81),
            ((0, 607), 235),
            ((911, 607), 145),
        ):
            assert preview.getpixel(point) == (gray(luma),) * 3
    checked = reverify(result, request, plan)
    assert checked.content_verified
