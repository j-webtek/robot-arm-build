"""One r89 acquisition-only pose capture; no reset, flash, or motion target."""

import argparse
import json
from pathlib import Path

from preflight_r89_live_campaign import current_capabilities, local_install_review
from rocell.application.pose_observation_capture import capture_pose
from rocell.application.product_ghost_export_review import _read


RELEASE_SHA = "653729599a9ba29baed5095b3ed156810b38396065a0b6a3a06fe6c7dd74ab1a"
RESET_EXPORT = "wizard-20260925T114424765909Z-0306d824772049bcbafc0f56069145c3"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight-only", action="store_true")
    mode.add_argument("--capture-no-motion", action="store_true")
    parser.add_argument("--address", default="192.168.0.225")
    parser.add_argument("--reset-export", default=RESET_EXPORT)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    exports = root / "runs/wizard-exports"
    installation = local_install_review(root)
    reset, _ = _read(exports, args.reset_export,
                     "attachment-r89-pose-observation-reset.json")
    old_boot = installation["previous_boot_id"]
    if (reset.get("schema") != "rocell.r89_pose_observation_reset.v1"
            or reset.get("status") != "ONE_RESET_SENT_STARTUP_NOT_YET_VERIFIED"
            or reset.get("old_boot_id") != old_boot
            or reset.get("installation_journal_sha256") != installation["installed_journal_sha256"]
            or reset.get("flash_written") is not False
            or reset.get("movement_command_sent") is not False
            or reset.get("retry_allowed") is not False
            or not (exports / f"r89-pose-observation-reset-{old_boot}.json").exists()):
        raise ValueError("Pinned one-startup record differs")
    current = current_capabilities(args.address)
    boot = current["boot_id"]
    if (boot == old_boot or current.get("stamped_release_sha256") != RELEASE_SHA
            or current.get("motion_authorized") is not False
            or current.get("live_release_available") is not True):
        raise ValueError("Current boot/release differs from reset and installation")
    marker = exports / f"pose-observation-{boot}.json"
    if marker.exists():
        raise ValueError("This boot's pose capture already attempted")
    if args.preflight_only:
        print(json.dumps(dict(status="R89_POSE_PREFLIGHT_VERIFIED", boot_id=boot,
                              hardware_access="public_capabilities_get",
                              motion_command_sent=False)))
        return
    result = capture_pose(exports, address=args.address, expected_boot=boot,
                          scan_id="r89-pose-2", authorized=True)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
