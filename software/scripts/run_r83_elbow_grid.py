"""One signed, finite 16-leg noncontact elbow grid with per-leg exports."""
import argparse
import json
import os
from pathlib import Path

from observe_r33_campaign import load_reviewed_key
from rocell.application.air_typing_elbow_grid_recipe import review_source
from rocell.application.air_typing_r83_campaign import AirTypingElbowGridHost
from rocell.application.air_typing_r83_release import review_release
from rocell.application.characterization_http import CharacterizationHTTP
from rocell.application.hold_transport_snapshot import HoldHTTPReader,STATUS
from rocell.application.supported_recovery_installation import review_recovery_startup
from rocell.application.wizard_diagnostic_coordinator import decode_diagnostic_json


def preflight(root,startup_export):
    root=Path(root).resolve();review_release(root)
    binding=review_recovery_startup(root,startup_export,revision=83)
    exports=root/"runs/wizard-exports"
    source_digest=review_source(exports)
    claim=exports/f'r83-elbow-grid-{binding["expected_boot"]}.json'
    if claim.exists() or (exports/f'pose-observation-{binding["expected_boot"]}.json').exists():
        raise ValueError("Boot already claimed")
    return binding,exports,claim,source_digest


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--startup-export",required=True)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight-only",action="store_true")
    mode.add_argument("--authorized-once",action="store_true")
    args=parser.parse_args(argv)
    root=Path(__file__).resolve().parents[1]
    binding,exports,claim,source_digest=preflight(root,args.startup_export)
    if args.preflight_only:
        print(json.dumps(dict(status="R83_ELBOW_GRID_BINDING_VERIFIED",
                              boot=binding["expected_boot"],hardware_access=False)))
        return
    status=decode_diagnostic_json(HoldHTTPReader(binding["address"])(
        STATUS,maximum_bytes=512,timeout_seconds=3),maximum=512)
    if (status.get("instance_id")!=binding["expected_boot"] or status.get("state")!="IDLE"
            or status.get("storage_fault") is not False):
        raise ValueError("Reviewed r83 startup no longer idle live boot")
    key=load_reviewed_key(root)
    with claim.open("x",encoding="utf-8") as stream:
        json.dump(dict(boot=binding["expected_boot"],startup_export=args.startup_export,
                       source_assessment_digest=source_digest,
                       scope="one-fixed-16-leg-noncontact-AIRG16",retry_allowed=False),stream)
        stream.flush();os.fsync(stream.fileno())
    client=CharacterizationHTTP(binding["address"],key=key,boot=binding["expected_boot"])
    result=AirTypingElbowGridHost(client,boot=binding["expected_boot"],
        export_root=exports,source_kind="controller_feedback").run_once()
    print(json.dumps(result))


if __name__=="__main__":main()
