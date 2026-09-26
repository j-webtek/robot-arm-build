"""Emit or abstain at the shared AI batch boundary using saved frame evidence.

No localization qualifications are trusted by this CLI until a qualification
registry is commissioned. Model output files cannot supply their own trust.
"""
import argparse
import json
from pathlib import Path
import sys
AI_DIR=Path(__file__).resolve().parent
sys.path[:0]=[str(AI_DIR),str(AI_DIR.parent/'src')]
from rocell.typing import compile_development_text
from rocell_ai.batch_emitter import emit
from rocell_ai.grounded import propose
from rocell_ai.motion_assurance import load
from rocell_ai.scene_observation import FrameEvidence

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('request','request-id','batch-id','frame-id','captured-at-utc','evaluated-at-utc'):
        p.add_argument('--'+name,required=True)
    for name in ('image','scene','precision','output'):
        p.add_argument('--'+name,type=Path,required=True)
    args=p.parse_args()
    frame=FrameEvidence(args.frame_id,args.captured_at_utc,args.image.read_bytes())
    task=propose(request_id=args.request_id,request=args.request,
                 observation={'ref':args.frame_id,'fresh':True,'phone_state':'UNKNOWN'})
    if task['decision']!='type_text':
        raise ValueError('Intent did not compile: '+task['reason'])
    result=emit(plan=compile_development_text(task['device'],task['text']),request_id=args.request_id,
        batch_id=args.batch_id,workspace=AI_DIR.parents[1],frame=frame,scene_observation=load(args.scene),
        precision_observation=load(args.precision),evaluated_at_utc=args.evaluated_at_utc)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_bytes((json.dumps(result,indent=2,sort_keys=True)+'\n').encode())
    print(result['status'], result['fusion']['reasons'])
