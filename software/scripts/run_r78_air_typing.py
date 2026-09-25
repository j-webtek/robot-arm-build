"""One signed, finite four-leg noncontact A-side continuation on reviewed r78 boot."""
import argparse
import json
import os
from pathlib import Path

from observe_r33_campaign import load_reviewed_key
from rocell.application.air_typing_r78_campaign import AirTypingASideHost
from rocell.application.air_typing_r78_release import review_release
from rocell.application.characterization_http import CharacterizationHTTP
from rocell.application.hold_transport_snapshot import HoldHTTPReader, STATUS
from rocell.application.product_ghost_export_review import _read
from rocell.application.supported_recovery_installation import review_recovery_startup
from rocell.application.wizard_diagnostic_coordinator import decode_diagnostic_json


R77_LEG3="wizard-20260924T231012251808Z-1613945c126b4a16bd1950ddf6b51bcc"
POSE="wizard-20260924T232712748224Z-e462f96c2c1b4561895acf10ba434231"


def preflight(root, startup_export):
    root=Path(root).resolve();review_release(root)
    binding=review_recovery_startup(root,startup_export,revision=78)
    exports=root/"runs/wizard-exports"
    leg,_=_read(exports,R77_LEG3,"attachment-air-typing-final-assessment.json")
    if (leg.get("status")!="FINALE_LEG_ENDPOINT_VERIFIED"
            or leg.get("leg")!=3
            or leg.get("final_goals")!=[1994,2076,2038,2598,2234,2040,2047]
            or leg.get("final_positions")!=[1985,2082,2031,2600,2235,2041,2047]):
        raise ValueError("Retained r77 leg-three source differs")
    pose,_=_read(exports,POSE,"attachment-pose-assessment.json")
    if (pose.get("category")!="STABLE_SAMPLED_POSE"
            or [joint["last_goal"] for joint in pose.get("joints",[])]!=leg["final_goals"]
            or [joint["last_position"] for joint in pose.get("joints",[])]!=
                [1987,2082,2031,2600,2235,2041,2047]
            or any(joint.get("torque")!=1 or joint.get("position_span")!=0
                   for joint in pose["joints"])):
        raise ValueError("Retained settled pose differs")
    claim=exports/f'r78-air-typing-{binding["expected_boot"]}.json'
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
        print(json.dumps(dict(status="R78_A_SIDE_BINDING_VERIFIED",
                              boot=binding["expected_boot"],hardware_access=False)))
        return
    status=decode_diagnostic_json(HoldHTTPReader(binding["address"])(
        STATUS,maximum_bytes=512,timeout_seconds=3),maximum=512)
    if (status.get("instance_id")!=binding["expected_boot"] or status.get("state")!="IDLE"
            or status.get("storage_fault") is not False):
        raise ValueError("Reviewed r78 startup no longer idle live boot")
    key=load_reviewed_key(root)
    with claim.open("x",encoding="utf-8") as stream:
        json.dump(dict(boot=binding["expected_boot"],startup_export=args.startup_export,
                       source_exports=[R77_LEG3,POSE],scope="one-fixed-4-leg-noncontact-AIR4",
                       retry_allowed=False),stream)
        stream.flush();os.fsync(stream.fileno())
    client=CharacterizationHTTP(binding["address"],key=key,boot=binding["expected_boot"])
    result=AirTypingASideHost(client,boot=binding["expected_boot"],export_root=exports,
                              source_kind="controller_feedback").run_once()
    print(json.dumps(result))


if __name__=="__main__":main()
