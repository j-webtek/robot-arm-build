"""One authenticated noncontact fixed A-B-A campaign on reviewed r75 boot."""
import argparse
import json
import os
from pathlib import Path

from observe_r33_campaign import load_reviewed_key
from rocell.application.air_typing_campaign import AirTypingHost
from rocell.application.air_typing_release import review_release
from rocell.application.air_typing_scoring import score_exported_campaign
from rocell.application.characterization_http import CharacterizationHTTP
from rocell.application.first_motion_contract import canonical
from rocell.application.hold_transport_snapshot import HoldHTTPReader, STATUS
from rocell.application.p4_midpoint_scoring import score_exported_campaign as replay_r74
from rocell.application.product_ghost_export_review import _read
from rocell.application.supported_recovery_installation import review_recovery_startup
from rocell.application.wizard_diagnostic_coordinator import decode_diagnostic_json
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


R74_SUMMARY = "wizard-20260924T194534566569Z-9bccccf548084617b78cd5290a1482ef"
R74_BOOT = "05b842d721c1ec3519d8a7bc7909b061"


def preflight(root, startup_export):
    root = Path(root).resolve()
    review_release(root)
    binding = review_recovery_startup(root, startup_export, revision=75)
    exports = root / "runs/wizard-exports"
    summary, _ = _read(exports, R74_SUMMARY, "attachment-r74-p4-midpoint-summary.json")
    replay = replay_r74(exports, summary["source_exports"], boot=R74_BOOT)
    if canonical(replay) != canonical(summary):
        raise ValueError("Retained r74 source replay differs")
    last, _ = _read(exports, summary["source_exports"][-1],
                    "attachment-p4-midpoint-assessment.json")
    if (last["final_positions"] != [2047, 2225, 1890, 2716, 1979, 2041, 2047]
            or last["final_goals"] != [2047, 2217, 1897, 2711, 1980, 2040, 2047]):
        raise ValueError("Retained P4 source differs")
    claim = exports / f'r75-air-typing-{binding["expected_boot"]}.json'
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
        print(json.dumps(dict(status="R75_AIR_TYPING_BINDING_VERIFIED",
                              boot=binding["expected_boot"], hardware_access=False)))
        return
    reader = HoldHTTPReader(binding["address"])
    status = decode_diagnostic_json(reader(STATUS, maximum_bytes=512, timeout_seconds=3), maximum=512)
    if (status.get("instance_id") != binding["expected_boot"] or status.get("state") != "IDLE"
            or status.get("storage_fault") is not False):
        raise ValueError("Reviewed r75 startup no longer idle live boot")
    key = load_reviewed_key(root)
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    with claim.open("x", encoding="utf-8") as stream:
        json.dump(dict(boot=binding["expected_boot"], startup_export=args.startup_export,
                       source_export=R74_SUMMARY, scope="one-fixed-17-leg-noncontact-AIR17",
                       retry_allowed=False), stream)
        stream.flush()
        os.fsync(stream.fileno())
    client = CharacterizationHTTP(binding["address"], key=key, boot=binding["expected_boot"])
    result = AirTypingHost(client, boot=binding["expected_boot"], export_root=exports,
                           source_kind="controller_feedback").run_once()
    source_ids = [Path(path).name for path in result["exports"]]
    score = score_exported_campaign(exports, source_ids, boot=binding["expected_boot"])
    saved = exporter.export({"mode": "r75-air-typing-physical-summary"}, [], attachments={
        "r75-air-typing-summary.json": canonical(score)})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("Physical summary export failed")
    print(json.dumps(dict(status=result["status"], summary_export=saved["path"], score=score)))


if __name__ == "__main__":
    main()
