"""One signed noncontact B-hover movement on an installed, reviewed r76 boot."""
import argparse
import json
import os
from pathlib import Path

from observe_r33_campaign import load_reviewed_key
from rocell.application.air_typing_b_hover import BHoverHost
from rocell.application.air_typing_b_hover_release import review_release
from rocell.application.characterization_http import CharacterizationHTTP
from rocell.application.hold_transport_snapshot import HoldHTTPReader, STATUS
from rocell.application.product_ghost_export_review import _read
from rocell.application.supported_recovery_installation import review_recovery_startup
from rocell.application.wizard_diagnostic_coordinator import decode_diagnostic_json


POSE = "wizard-20260924T221646916450Z-89afb8ef3c6041cdafa23e899c271bf3"


def preflight(root: Path, startup_export: str):
    root = Path(root).resolve()
    review_release(root)
    binding = review_recovery_startup(root, startup_export, revision=76)
    exports = root / "runs/wizard-exports"
    pose, _ = _read(exports, POSE, "attachment-pose-assessment.json")
    if (pose["category"] != "STABLE_SAMPLED_POSE" or pose["origin"] != "DEVICE_CAPTURE"
            or [row["last_goal"] for row in pose["joints"]] != [1941,2080,2034,2591,2236,2040,2047]
            or [row["last_position"] for row in pose["joints"]] != [1949,2082,2033,2600,2235,2041,2047]
            or any(row["torque"] != 1 or row["position_span"] != 0
                   or row["controls_unchanged"] is not True for row in pose["joints"])):
        raise ValueError("Retained post-fault pose differs")
    claim = exports / f'r76-b-hover-{binding["expected_boot"]}.json'
    if claim.exists() or (exports / f'pose-observation-{binding["expected_boot"]}.json').exists():
        raise ValueError("Boot already claimed")
    return binding, exports, claim


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--startup-export", required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight-only", action="store_true")
    mode.add_argument("--authorized-once", action="store_true")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    binding, exports, claim = preflight(root, args.startup_export)
    if args.preflight_only:
        print(json.dumps(dict(status="R76_B_HOVER_BINDING_VERIFIED",
                              boot=binding["expected_boot"], hardware_access=False)))
        return
    status = decode_diagnostic_json(HoldHTTPReader(binding["address"])(
        STATUS, maximum_bytes=512, timeout_seconds=3), maximum=512)
    if (status.get("instance_id") != binding["expected_boot"] or status.get("state") != "IDLE"
            or status.get("storage_fault") is not False):
        raise ValueError("Reviewed r76 startup no longer idle live boot")
    key = load_reviewed_key(root)
    with claim.open("x", encoding="utf-8") as stream:
        json.dump(dict(boot=binding["expected_boot"], startup_export=args.startup_export,
                       source_export=POSE, scope="one-fixed-noncontact-AIRB1",
                       retry_allowed=False), stream)
        stream.flush()
        os.fsync(stream.fileno())
    client = CharacterizationHTTP(binding["address"], key=key, boot=binding["expected_boot"])
    result = BHoverHost(client, boot=binding["expected_boot"], export_root=exports,
                        source_kind="controller_feedback").run_once()
    print(json.dumps(result))


if __name__ == "__main__":
    main()
