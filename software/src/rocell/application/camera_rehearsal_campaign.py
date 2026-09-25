"""Finite B0477-sized binary fixtures through the native ingestion contract.

No device API or executable is called. Existing source-bound placemat pixels
are enlarged to exercise byte/stride/storage contracts, not to claim measured
20 MP optics. Only a preview derived from the retained YUY2 bytes is returned.
"""

from __future__ import annotations

from dataclasses import replace
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import shutil
import threading
import time
from typing import Any
import uuid

from rocell.application.cell_commissioning_coordinator import (
    ExactOperationPermit,
    INCAPABLE_COMPOSITION,
    ObservedPowerState,
    WorkerReceipt,
)
from rocell.application.camera_capture_dataset import FramePlan, PreviewTransform
from rocell.application.wizard_diagnostic_export import _directory_guard
from rocell.application.wizard_diagnostic_coordinator import require_regular_path
from rocell.providers.windows.camera_worker_client import (
    CameraActivationRequest,
    CameraCandidate,
    CameraCampaignBudget,
    CameraEndpointBinding,
    NativeCameraMode,
    NativeCameraReceipt,
    NativeFrameArtifact,
)
from rocell.safety.effects import EffectCertainty

MODE = NativeCameraMode(5472, 3648, 9, 1, stride_bytes=10944)
FRAME_BYTES = 39_923_712


def _hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("ascii")
    ).hexdigest()


def camera_settings(brightness_offset: object) -> dict[str, Any]:
    """This finite fixture knob is deliberately not a purported UVC value."""
    if type(brightness_offset) is not int or not -64 <= brightness_offset <= 64:
        raise ValueError("Synthetic brightness offset must be an integer -64..64")
    return {
        "brightness_offset": brightness_offset,
        "exposure_policy": "SYNTHETIC_LUMA_OFFSET_NOT_DRIVER_CONTROL",
        "mode": {
            "width": 5472,
            "height": 3648,
            "fps_numerator": 9,
            "fps_denominator": 1,
            "pixel_format": "YUY2",
        },
    }


class SyntheticBinaryCameraWorker:
    """Sealed incapable composition; native counters below are simulated only."""

    composition = INCAPABLE_COMPOSITION

    def __init__(
        self,
        workspace: Path,
        root: Path,
        *,
        executable_sha256: str,
        source_sha256: str,
        frame_count: int,
        fault: str,
        settings: dict[str, Any],
        settings_epoch: str,
    ) -> None:
        if type(frame_count) is not int or not 1 <= frame_count <= 4:
            raise ValueError("One to four finite fixture frames are permitted")
        if fault not in {"none", "identity-mismatch", "cleanup-uncertain"}:
            raise ValueError("Unknown incapable camera scenario")
        if (
            settings != camera_settings(settings.get("brightness_offset"))
            or _hash(settings) != settings_epoch
        ):
            raise ValueError("Settings differ from their prepared epoch")
        if not root.is_absolute() or ".." in root.parts:
            raise ValueError("Assign an absolute server-owned artifact root")
        self.workspace, self.root = workspace, root
        self.worker_executable_sha256 = executable_sha256
        self.source_sha256, self.frame_count, self.fault = (
            source_sha256,
            frame_count,
            fault,
        )
        self.settings = json.loads(json.dumps(settings))
        self.settings_epoch = settings_epoch
        self.capture: Any = None

    def run_campaign(
        self,
        permit: ExactOperationPermit,
        *,
        deadline_ns: int,
        cancellation: threading.Event,
    ) -> WorkerReceipt:
        def cancelled() -> bool:
            return cancellation.is_set() or time.monotonic_ns() >= deadline_ns

        def check() -> None:
            if cancelled():
                raise RuntimeError(
                    "Synthetic binary campaign cancelled or deadline exceeded; retain partial artifacts"
                )

        check()
        hashes: tuple[str, ...] = ()
        if self.fault == "none":
            self.capture = self._capture(permit, check, cancelled)
            hashes = (
                self.capture.envelope_sha256,
                self.capture.dataset.manifest_sha256,
            )
        receipt = WorkerReceipt(
            attempt_id=permit.attempt_id,
            permit_sha256=permit.permit_sha256,
            worker_executable_sha256=self.worker_executable_sha256,
            selected_identity_sha256=permit.admission.selected_identity_sha256,
            effect_certainty=EffectCertainty.CONFIRMED,
            cleanup_confirmed=True,
            final_power_state=ObservedPowerState.DEENERGIZED,
            opens=1,
            reads=self.frame_count,
            writes=0,
            frames=self.frame_count,
            closes=1,
            output_bytes=1024,
            evidence_sha256s=hashes,
        )
        if self.fault == "identity-mismatch":
            receipt = replace(
                receipt, selected_identity_sha256=_hash("wrong-synthetic-unit")
            )
        elif self.fault == "cleanup-uncertain":
            receipt = replace(receipt, cleanup_confirmed=False, closes=0)
        check()
        return receipt

    def _capture(self, permit: ExactOperationPermit, check: Any, cancelled: Any) -> Any:
        from PIL import Image
        from rocell.application.b0477_static_vision import (
            run_b0477_static_vision_capture_rehearsal,
        )
        from rocell.application.windows_camera_capture_ingest import (
            prepare_windows_camera_ingest,
            ingest_windows_capture,
        )

        # This helper path is only a synthetic identity hash; it is never run.
        destination = self.root / ("binary-fixture-" + uuid.uuid4().hex)
        raw = destination / "native"
        datasets = destination / "datasets"
        endpoint = "incapable-fixture-only"
        if permit.admission.selected_identity_sha256 is None:
            raise ValueError("A reviewed synthetic camera identity is required")
        binding = CameraEndpointBinding(
            endpoint,
            hashlib.sha256(endpoint.encode()).hexdigest(),
            permit.admission.selected_identity_sha256,
        )
        request = CameraActivationRequest(
            permit.attempt_id,
            self.source_sha256,
            "capture",
            binding,
            MODE,
            (),
            CameraCampaignBudget(
                duration_ms=60_000,
                max_frames=self.frame_count,
                max_frame_bytes=FRAME_BYTES,
                max_total_bytes=FRAME_BYTES * self.frame_count,
            ),
            self.worker_executable_sha256,
            _hash({"fixture": True, "settings_epoch": self.settings_epoch}),
            str(raw),
        )
        frame_plans = tuple(
            FramePlan(
                f"frame-{i:06d}",
                preview=(
                    PreviewTransform(0, 0, 5472, 3648, 912, 608)
                    if i == self.frame_count - 1
                    else None
                ),
            )
            for i in range(self.frame_count)
        )
        plan = prepare_windows_camera_ingest(
            request,
            capture_directory=raw,
            dataset_root=datasets,
            source_sha256=self.source_sha256,
            settings_epoch=self.settings_epoch,
            domain="INCAPABLE_NATIVE_FIXTURE",
            frames=frame_plans,
            retention_timeout_ms=60_000,
        )
        require_regular_path(self.root, directory=True)
        with _directory_guard(self.root):
            check()
            # Reserve raw + retained samples + diagnostic previews + free margin.
            required = 2 * FRAME_BYTES * self.frame_count + 128 * 1024 * 1024
            if shutil.disk_usage(self.root).free < required:
                raise RuntimeError("Insufficient space for finite binary rehearsal")
            destination.mkdir(exist_ok=False)
            raw.mkdir(exist_ok=False)
            datasets.mkdir(exist_ok=False)
            artifacts = []
            for index in range(self.frame_count):
                check()
                capture = run_b0477_static_vision_capture_rehearsal(
                    self.workspace, sequence=index
                )
                check()
                # Preserve source-bound geometry. Upsampling is NOT native detail.
                with Image.open(BytesIO(capture.jpeg_bytes)) as encoded:
                    gray = encoded.convert("L")
                if gray.size != (2736, 1824):
                    raise ValueError(
                        "Synthetic raster dimensions differ from the pinned half-resolution profile"
                    )
                offset = self.settings["brightness_offset"]
                lut = bytes(
                    16 + (max(0, min(255, value + offset)) * 219 + 127) // 255
                    for value in range(256)
                )
                digest = hashlib.sha256()
                filename = f"frame-{index:06d}.yuy2"
                with (raw / filename).open("xb") as stream:
                    for row in range(1824):
                        check()
                        values = (
                            gray.crop((0, row, 2736, row + 1)).tobytes().translate(lut)
                        )
                        wire = bytearray(10944)
                        wire[0::4] = values
                        wire[2::4] = values
                        wire[1::2] = b"\x80" * 5472
                        # Two identical expanded rows; bounded allocation per row.
                        stream.write(wire)
                        stream.write(wire)
                        digest.update(wire)
                        digest.update(wire)
                    stream.flush()
                    os.fsync(stream.fileno())
                gray.close()
                artifacts.append(
                    NativeFrameArtifact(
                        filename,
                        FRAME_BYTES,
                        10944,
                        0,
                        index,
                        index * 1_111_111,
                        time.monotonic_ns(),
                        1_000_000_000,
                        None,
                        digest.hexdigest(),
                    )
                )
            native = NativeCameraReceipt(
                "capture",
                "OK",
                None,
                endpoint,
                (CameraCandidate(endpoint, "SYNTHETIC B0477 fixture, not enumerated"),),
                (MODE,),
                MODE,
                MODE,
                (),
                tuple(artifacts),
                {
                    "source_activation_attempts": 1,
                    "source_opened": 1,
                    "control_set_attempts": 0,
                    "samples_received": self.frame_count,
                    "frames_written": self.frame_count,
                    "source_shutdown_attempts": 1,
                },
                True,
                (
                    "INCAPABLE_NATIVE_FIXTURE",
                    "UPSCALED_SYNTHETIC_PIXELS_NOT_NATIVE_DETAIL",
                    "MEDIA_TIMESTAMP_IS_NOT_EXPOSURE_TIME",
                    "SENSOR_SEQUENCE_UNAVAILABLE",
                ),
            )
            check()
            return ingest_windows_capture(
                request, native, plan=plan, cancelled=cancelled
            )
