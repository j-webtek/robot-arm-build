"""One signed, finite seven-leg noncontact B-A sequence on reviewed r77 boot."""
import argparse
import json
import os
from pathlib import Path

from observe_r33_campaign import load_reviewed_key
from rocell.application.air_typing_r77_campaign import AirTypingFinaleHost
from rocell.application.air_typing_r77_release import review_release
from rocell.application.characterization_http import CharacterizationHTTP
from rocell.application.hold_transport_snapshot import HoldHTTPReader,STATUS
from rocell.application.product_ghost_export_review import _read
from rocell.application.supported_recovery_installation import review_recovery_startup
from rocell.application.wizard_diagnostic_coordinator import decode_diagnostic_json


R76_RESULT="wizard-20260924T225254423367Z-ad13c5528ce84c49a196d58651ccc6be"


def preflight(root,startup_export):
    root=Path(root).resolve();review_release(root)
    binding=review_recovery_startup(root,startup_export,revision=77)
    exports=root/"runs/wizard-exports"
    source,_=_read(exports,R76_RESULT,"attachment-b-hover-assessment.json")
    if (source["status"]!="B_HOVER_JOINT_ENDPOINT_VERIFIED"
            or source["source_kind"]!="controller_feedback"
            or source["final_goals"]!=[1941,2098,2016,2609,2201,2040,2047]
            or source["final_positions"]!=[1949,2099,2015,2610,2203,2041,2047]
            or source["boot"]!="c788314e681f90d7021042d1bcef8f76"):
        raise ValueError("Retained r76 B-hover source differs")
    claim=exports/f'r77-air-typing-{binding["expected_boot"]}.json'
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
        print(json.dumps(dict(status="R77_FINALE_BINDING_VERIFIED",
                              boot=binding["expected_boot"],hardware_access=False)))
        return
    status=decode_diagnostic_json(HoldHTTPReader(binding["address"])(
        STATUS,maximum_bytes=512,timeout_seconds=3),maximum=512)
    if (status.get("instance_id")!=binding["expected_boot"] or status.get("state")!="IDLE"
            or status.get("storage_fault") is not False):
        raise ValueError("Reviewed r77 startup no longer idle live boot")
    key=load_reviewed_key(root)
    with claim.open("x",encoding="utf-8") as stream:
        json.dump(dict(boot=binding["expected_boot"],startup_export=args.startup_export,
                       source_export=R76_RESULT,scope="one-fixed-7-leg-noncontact-AIR7",
                       retry_allowed=False),stream)
        stream.flush();os.fsync(stream.fileno())
    client=CharacterizationHTTP(binding["address"],key=key,boot=binding["expected_boot"])
    result=AirTypingFinaleHost(client,boot=binding["expected_boot"],export_root=exports,
                               source_kind="controller_feedback").run_once()
    print(json.dumps(result))


if __name__=="__main__":main()
