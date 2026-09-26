"""Replay six archived scene conditions against ten synthetic H-I probes."""
import argparse
import json
from pathlib import Path
import sys

AI_DIR = Path(__file__).resolve().parent
sys.path[:0] = [str(AI_DIR), str(AI_DIR.parent / 'src')]
from run_keyboard_route_coverage import proposals
from rocell_ai.localization_stress import probe
from rocell_ai.scene_observation import canonical_hash


def study(workspace: Path):
    source = json.loads((workspace / 'software/ai/eval/gemma3_4b_scene_stress_v0.json').read_text())
    if source['report_sha256'] != canonical_hash({k:v for k,v in source.items() if k!='report_sha256'}):
        raise ValueError('Archived stress report hash mismatch')
    catalog = {p['target_id']:p for p in proposals(workspace)}
    sequence = [catalog['H'], catalog['I']]
    cases=[]
    for row in source['rows']:
        for dx,dy,confidence in [(0,0,1.0),(6,0,1.0),(-6,0,1.0),(0,6,1.0),(0,-6,1.0),
                                 (8,0,1.0),(-8,0,1.0),(0,8,1.0),(0,-8,1.0),(0,0,0.5)]:
            result=probe(row, sequence, workspace=workspace, dx=dx, dy=dy, confidence=confidence)
            cases.append(result)
            print(row['case'],dx,dy,confidence,result['status'],flush=True)
    counts={status:sum(c['status']==status for c in cases) for status in sorted({c['status'] for c in cases})}
    core={'schema':'rocell.ai_localization_scene_stress.v0', 'source_scene_study_sha256':source['report_sha256'],
          'synthetic_base_proposals':sequence,'cases':cases,'counts':counts,'physical_execution_authorized':False,
          'hardware_writes':0,'limitations':[
              'Archived scene decisions replayed from a previous Gemma run; no new images or inference',
              'Scene quality is a synthetic condition for unrelated nominal coordinates, not calibrated image grounding',
              'This harness is not the live vision-fusion gate and does not check current-frame freshness',
              'Offsets and confidence are injected labels, not learned localization error estimates',
              'Passing offset probes do not define a physical precision tolerance or demonstrate key registration',
              'One H-I sequence and one correlated source photograph; no deployment-camera qualification']}
    return {**core,'study_sha256':canonical_hash(core)}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=study(AI_DIR.parents[1])
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_bytes((json.dumps(result,indent=2,sort_keys=True)+'\n').encode())
