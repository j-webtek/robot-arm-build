"""Rehearse native endpoint enrollment through normal wizard actions.

Only new diagnostic logs/exports are written. There is no OS device inventory,
native helper invocation, endpoint activation, arm power or motion. The generic
metadata action runs its fixed incapable Python diagnostic child. Native packets
use the actual strict wire parsers with a fixed incapable provider.

With --serve, the script prepares generic review and native inventory only;
the browser must explicitly select, resolve, review and export. Without it,
fixed fixture choices drive the complete API path and verify the export.
"""

from __future__ import annotations

import argparse
from contextlib import ExitStack
import json
from pathlib import Path
from unittest.mock import patch

from rocell.application.arrival_wizard_service import ArrivalWizardService
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.arm.serial_transport import SerialTransport
from rocell.providers.windows.camera_worker_client import WindowsCameraWorkerClient
from rocell.ui.server import create_wizard_server, run_wizard_server
from rocell.vision.usb_opencv import UsbOpenCvCamera
from wizard_reopen_rehearsal_smoke import action


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", action="store_true")
    parser.add_argument(
        "--helper-scenario",
        choices=("nominal", "missing-helper", "hash-drift"),
        help="Also exercise explicit incapable helper inspection/review before endpoint enrollment.",
    )
    parser.add_argument(
        "--scenario",
        choices=("nominal", "missing-mapping", "wrong-device", "duplicate-name"),
        default="nominal",
    )
    args = parser.parse_args()
    workspace = Path(__file__).resolve().parents[2]
    with ExitStack() as guards:
        for owner, method in (
            (WindowsCameraWorkerClient, "_registered_arguments"),
            (WindowsCameraWorkerClient, "probe"),
            (WindowsCameraWorkerClient, "capture"),
            (SerialTransport, "connect"),
            (UsbOpenCvCamera, "open"),
        ):
            guards.enter_context(
                patch.object(
                    owner,
                    method,
                    side_effect=AssertionError(
                        "Hardware/native access forbidden in rehearsal smoke"
                    ),
                )
            )
        service = ArrivalWizardService(workspace, mode="rehearsal")
        try:
            print("source", service.source_sha256, flush=True)
            print("session", service.session_id, flush=True)
            if args.helper_scenario is not None:
                action(
                    service,
                    "camera_helper_inspect",
                    scenario=args.helper_scenario,
                    operator_id="smoke-inspection-operator",
                    metadata_only=True,
                )
                action(
                    service,
                    "camera_helper_review",
                    reviewer_id="smoke-helper-reviewer",
                    metadata_only=True,
                )
                helper = service.view()["camera_helper_registration"]
                if args.helper_scenario != "nominal":
                    assert helper["status"] == "REVIEW_HELD", helper
                    assert service._native_camera_provider is None
                    action(service, "export_logs")
                    path = Path(service.view()["exports"]["items"][-1]["path"])
                    verified = verify_export(path)
                    assert (
                        verified["valid"] and verified["physical_authority"] == "NONE"
                    )
                    print(
                        json.dumps(
                            {
                                "helper_scenario": args.helper_scenario,
                                "helper_status": helper["status"],
                                "export": str(path),
                                "manifest_sha256": verified["manifest_sha256"],
                                "physical_authority": "NONE",
                                "physical_stages_pending": len(
                                    service.view()["stages"]
                                ),
                            },
                            sort_keys=True,
                        ),
                        flush=True,
                    )
                    return
                assert helper["status"] == "METADATA_HELPER_REGISTERED", helper
            action(service, "rehearse_device_inventory", scenario="nominal")
            generic = service.view()["device_selection"]["devices"]["CAMERA"][
                "candidates"
            ][0]
            action(
                service,
                "review_camera_candidate",
                choice_id=generic["choice_id"],
                reviewer_id="native-smoke-generic-reviewer",
                metadata_only=True,
            )
            action(
                service,
                "native_camera_inventory",
                scenario=args.scenario,
                metadata_only=True,
            )
            if args.serve:
                print(
                    "Prepared fixture inventory only. Browser selection/identity/review/export remain explicit.",
                    flush=True,
                )
                server = create_wizard_server(service)
                print("Browser QA:", server.launch_url, flush=True)
                run_wizard_server(server)
                return
            candidates = service.view()["native_camera_enrollment"]["candidates"]
            # Fixed automated test choice: the second same-name endpoint is
            # deliberately the wrong device. This is not an operator default.
            selected = candidates[1 if args.scenario == "duplicate-name" else 0][
                "choice_id"
            ]
            action(
                service,
                "native_camera_identity",
                choice_id=selected,
                metadata_only=True,
            )
            action(
                service,
                "native_camera_review",
                choice_id=selected,
                reviewer_id="native-smoke-endpoint-reviewer",
                metadata_only=True,
            )
            current = service.view()["native_camera_enrollment"]
            expected = (
                "ENDPOINT_METADATA_REVIEWED"
                if args.scenario == "nominal"
                else "REVIEW_HELD"
            )
            assert current["status"] == expected, current
            assert all(
                current[key] is False
                for key in (
                    "connected",
                    "qualified",
                    "persistent_binding",
                    "physical_authority",
                )
            )
            assert all(
                row["state"] == "PHYSICAL_PENDING" for row in service.view()["stages"]
            )
            action(service, "export_logs")
            path = Path(service.view()["exports"]["items"][-1]["path"])
            verified = verify_export(path)
            assert verified["valid"] and verified["physical_authority"] == "NONE"
            print(
                json.dumps(
                    {
                        "scenario": args.scenario,
                        "helper_scenario": args.helper_scenario,
                        "helper_status": service.view()["camera_helper_registration"][
                            "status"
                        ],
                        "status": current["status"],
                        "export": str(path),
                        "manifest_sha256": verified["manifest_sha256"],
                        "physical_authority": "NONE",
                        "physical_stages_pending": len(service.view()["stages"]),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
        finally:
            service.shutdown()


if __name__ == "__main__":
    main()
