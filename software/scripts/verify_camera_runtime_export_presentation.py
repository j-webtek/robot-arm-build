"""Read-only verification of one exact runtime-file inspection/review export.

Verifies retained bytes with the pure codec and renders the exact exported view
through the real app.js in a Node fake DOM and the real terminal frontend. This
is not a browser, native-runtime, received-camera or physical-acceptance test.
No application, inspector, M1 session, campaign or native helper is constructed
or run. Only source/export files are read; the sole child is the Node harness.
Requires development test helpers and Node. --report is the canonical retained
inspection report SHA256, not the outer report.json SHA256.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys


WORKSPACE = Path(__file__).resolve().parents[2]
sys.path[:0] = [
    str(WORKSPACE / "software/src"),
    str(WORKSPACE / "software/tests/unit"),
]

from rocell.application.physical_camera_runtime_inspection import (  # noqa: E402
    verify_physical_camera_runtime_inspection,
)
from rocell.application.physical_onboarding_durability import (  # noqa: E402
    read_bounded_regular_file,
)
from rocell.application.wizard_diagnostic_coordinator import (  # noqa: E402
    source_fingerprint,
)
from rocell.application.wizard_diagnostic_export import verify_export  # noqa: E402
from rocell.providers.windows.native_camera_capture_registration import (  # noqa: E402
    NativeCameraCaptureRuntimeRegistration,
)
from rocell.providers.windows.native_camera_registration import (  # noqa: E402
    NativeCameraRuntimeRegistration,
)
from rocell.ui.terminal import _PhysicalCameraRuntimeDisplay  # noqa: E402
from test_arrival_wizard_device_selection_ui import browser  # noqa: E402
from test_arrival_wizard_terminal import Service, run  # noqa: E402


FALSE_FLAGS = (
    "dispatch_enabled",
    "driver_qualified",
    "hardware_qualified",
    "connected",
    "physical_authority",
)
ATTACHMENT = "attachment-camera-runtime-inspection.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def read(path: Path, maximum: int) -> bytes:
    return read_bounded_regular_file(path, maximum_bytes=maximum)


def verify(directory: Path, *, source: str, report: str, attachment: str) -> dict:
    for value in (source, report, attachment):
        require(
            type(value) is str
            and re.fullmatch(r"[0-9a-f]{64}", value) is not None
            and value != "0" * 64,
            "Supply exact nonzero lowercase source/report/attachment SHA256 values",
        )
    require(shutil.which("node") is not None, "Node is required for the fake DOM")
    integrity = verify_export(directory)
    require(integrity["valid"] is True, "Export integrity verification failed")
    source_before = source_fingerprint(WORKSPACE)
    require(source_before == source, "Current source differs from the supplied source")
    original = {
        "manifest.json": read(directory / "manifest.json", 64 * 1024),
        "report.json": read(directory / "report.json", 8 * 1024 * 1024),
        ATTACHMENT: read(directory / ATTACHMENT, 1024 * 1024),
    }
    require(sha(original[ATTACHMENT]) == attachment, "Attachment digest differs")
    envelope = json.loads(original[ATTACHMENT])
    require(
        set(envelope)
        == {
            "schema",
            "publication",
            "original_bytes_preserved",
            "inspection",
            "inspection_sha256",
            "review",
            "physical_authority",
            "meaning",
        }
        and envelope["schema"] == "rocell.physical_camera_runtime_inspection_export.v1"
        and envelope["publication"] == "CURRENT_FILE_REPORT"
        and envelope["original_bytes_preserved"] is True
        and envelope["physical_authority"] is False,
        "Expected an exact, current diagnostic file-report export",
    )
    document = envelope["inspection"]
    require(
        sha(canonical(document)) == report == envelope["inspection_sha256"],
        "Canonical inspection report digest differs",
    )
    snapshot = json.loads(original["report.json"])["snapshot"]
    require(
        snapshot["source_binding_sha256"] == source
        and document["binding"]["source_sha256"] == source
        and document["binding"]["workspace"] == str(WORKSPACE),
        "Retained source/workspace binding differs",
    )
    launch = snapshot["session_id"]
    # Typed registration decoding is pure. The report verifier independently
    # checks its closed path/purpose roster and fixed development catalog pins;
    # nothing reads or approves the currently installed executable here.
    probe = NativeCameraRuntimeRegistration(canonical(document["candidates"]["probe"]))
    capture = NativeCameraCaptureRuntimeRegistration(
        canonical(document["candidates"]["capture"])
    )
    verified = verify_physical_camera_runtime_inspection(
        document,
        expected_source_sha256=source,
        expected_launch_session_id=launch,
        expected_probe_candidate=probe,
        expected_capture_candidate=capture,
        expected_report_sha256=report,
    )
    camera = snapshot["physical_camera"]
    wrapper = camera["runtime_inspection"]
    require(
        camera["source_sha256"] == source
        and _PhysicalCameraRuntimeDisplay.projection(wrapper, source, launch) == wrapper
        and wrapper["status"] == "REVIEW_RECORDED"
        and wrapper["publication"]["status"] == "CURRENT"
        and wrapper["inspection"] == verified.safe_summary()
        and wrapper["review"] == envelope["review"]
        and envelope["review"] is not None,
        "Exact retained inspection/review does not match the current snapshot",
    )
    require(
        all(wrapper[key] is False and document[key] is False for key in FALSE_FLAGS)
        and all(type(n) is int and n == 0 for n in document["effects"].values()),
        "Inspection claims an effect or authority",
    )
    require(
        len(snapshot["stages"]) == 15
        and all(row["state"] == "PHYSICAL_PENDING" for row in snapshot["stages"]),
        "Physical stage status was unexpectedly promoted",
    )
    page = browser(
        snapshot.get("device_selection"), "camera", snapshot=deepcopy(snapshot)
    )
    require(page["status"] == "Local service connected", "JS rendering failed")
    require(
        page["requests"] == [{"path": "/api/view", "method": "GET", "body": None}]
        and page["dialogOpen"] is False,
        "Rendering attempted an unexpected request or action dialog",
    )

    class ExportView(Service):
        def view(self):
            self.calls.append(("view",))
            return deepcopy(snapshot)

    service = ExportView()
    code, output, _ = run(service, ["quit"])
    require(
        code == 0 and service.calls == [("view",)] and service.shutdown_count == 0,
        "Terminal attempted an action instead of one view and quit",
    )
    expected_text = [
        "Runtime pair file inspection and review",
        "NOT_CONNECTED / NOT_QUALIFIED / DISPATCH_DISABLED",
        "File agreement is not runtime admission",
        "No executable was launched",
        "Labels record procedure, not authenticated independent people",
        "File result: " + document["status"],
        report,
        document["binding"]["operator_id"],
        envelope["review"]["reviewer_id"],
        envelope["review"]["status"],
    ]
    for purpose, row in document["purposes"].items():
        expected_text.extend(
            [
                f"{purpose}: executable pin {row['binary_status']}; build-record pin {row['build_status']}",
                f"{purpose}: source closure {row['source_status']}; declared artifacts {row['artifact_status']}",
                *(f"{gap['relative_path']}: {gap['reason']}" for gap in row["gaps"]),
            ]
        )
    for rendered in (page["text"], "\n".join(output)):
        require(
            "RUNTIME_INSPECTION_NOT_VERIFIED" not in rendered
            and all(text in rendered for text in expected_text),
            "Renderer withheld or misrepresented the exact file inspection/review",
        )
    # A second full manifest-bounded verification covers every original export
    # file, including older generic results. No inspector or file evaluator is
    # rerun; only retained byte integrity and pure derived-report checks occur.
    after = verify_export(directory)
    require(
        after["valid"] is True
        and after["manifest_sha256"] == integrity["manifest_sha256"]
        and all(
            read(directory / name, len(payload) + 1) == payload
            for name, payload in original.items()
        )
        and source_fingerprint(WORKSPACE) == source_before,
        "Original export or production source changed during read-only verification",
    )
    return {
        "verification": "PASSED_READ_ONLY_RUNTIME_EXPORT_AND_PRESENTATION",
        "source_sha256": source,
        "inspection_sha256": report,
        "attachment_sha256": attachment,
        "outer_report_sha256": sha(original["report.json"]),
        "manifest_sha256": integrity["manifest_sha256"],
        "inspection_bytes": len(verified.payload),
        "attachment_bytes": len(original[ATTACHMENT]),
        "report_bytes": len(original["report.json"]),
        "launch_session_id": launch,
        "inspection_status": document["status"],
        "review_status": envelope["review"]["status"],
        "purposes": document["purposes"],
        "coverage": document["coverage"],
        "browser_check": "REAL_APP_JS_IN_FAKE_DOM_NOT_REAL_BROWSER",
        "browser_requests": page["requests"],
        "terminal_exit_code": code,
        "terminal_calls": [list(call) for call in service.calls],
        "physical_stages_pending": 15,
        "original_export_unchanged": True,
        **dict.fromkeys(FALSE_FLAGS, False),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    for name in ("source", "report", "attachment"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    result = verify(
        args.directory.absolute(),
        source=args.source,
        report=args.report,
        attachment=args.attachment,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
