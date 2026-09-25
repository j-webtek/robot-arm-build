"""One signed, finite six-leg noncontact A-repeat campaign on reviewed r79 boot."""
import argparse
import json
import os
from pathlib import Path

from observe_r33_campaign import load_reviewed_key
from rocell.application.air_typing_r79_campaign import AirTypingRepeatHost
from rocell.application.air_typing_r79_release import review_release
from rocell.application.characterization_http import CharacterizationHTTP
from rocell.application.hold_transport_snapshot import HoldHTTPReader,STATUS
from rocell.application.product_ghost_export_review import _read
from rocell.application.supported_recovery_installation import review_recovery_startup
from rocell.application.wizard_diagnostic_coordinator import decode_diagnostic_json


SOURCE="wizard-20260924T234900259937Z-5d6c8c652fe24e2abb137b9046dc7811"


def preflight(root,startup_export):
    root=Path(root).resolve();review_release(root)
    binding=review_recovery_startup(root,startup_export,revision=79)
    exports=root/"runs/wizard-exports"
    source,_=_read(exports,SOURCE,"attachment-air-typing-last-assessment.json")
    if (source.get("status")!="A_SIDE_LEG_ENDPOINT_VERIFIED"
            or source.get("source_kind")!="controller_feedback"
            or source.get("leg")!=4
            or source.get("final_goals")!=[2047,2075,2039,2600,2233,2040,2047]
            or source.get("final_positions")!=[2041,2081,2033,2609,2233,2041,2047]):
        raise ValueError("Retained r78 A-retract source differs")
    claim=exports/f'r79-air-typing-repeat-{binding["expected_boot"]}.json'
    if claim.exists() or (exports/f'pose-observation-{binding["expected_boot"]}.json').exists():
        raise ValueError("Boot already claimed")
    return binding,exports,claim


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--startup-export",required=True)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight-only",action="store_true")
    mode.add_argument("--authorized-once",action="store_true")
    args=parser.parse_args(argv)
    root=Path(__file__).resolve().parents[1]
    binding,exports,claim=preflight(root,args.startup_export)
    if args.preflight_only:
        print(json.dumps(dict(status="R79_A_REPEAT_BINDING_VERIFIED",
                              boot=binding["expected_boot"],hardware_access=False)))
        return
    status=decode_diagnostic_json(HoldHTTPReader(binding["address"])(
        STATUS,maximum_bytes=512,timeout_seconds=3),maximum=512)
    if (status.get("instance_id")!=binding["expected_boot"] or status.get("state")!="IDLE"
            or status.get("storage_fault") is not False):
        raise ValueError("Reviewed r79 startup no longer idle live boot")
    key=load_reviewed_key(root)
    with claim.open("x",encoding="utf-8") as stream:
        json.dump(dict(boot=binding["expected_boot"],startup_export=args.startup_export,
                       source_export=SOURCE,scope="one-fixed-6-leg-noncontact-AIR6",
                       retry_allowed=False),stream)
        stream.flush();os.fsync(stream.fileno())
    client=CharacterizationHTTP(binding["address"],key=key,boot=binding["expected_boot"])
    result=AirTypingRepeatHost(client,boot=binding["expected_boot"],export_root=exports,
                               source_kind="controller_feedback").run_once()
    print(json.dumps(result))


if __name__=="__main__":main()
