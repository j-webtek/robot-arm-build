"""Compare explicit retained exports offline; prints JSON and opens no device."""
import argparse
import json
import re
from pathlib import Path

from rocell.application.wrist_endpoint_models import compare_exports


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest',type=Path)
    args=parser.parse_args()
    raw=args.manifest.read_bytes()
    if len(raw)>65536:
        raise ValueError('Manifest exceeds 64 KiB')
    manifest=json.loads(raw)
    if (set(manifest)!={'schema','split_kind','exports'}
            or manifest['schema']!='rocell.offline_endpoint_model_selection.v1'
            or manifest['split_kind']!='RETROSPECTIVE_CAMPAIGN_DISJOINT'
            or type(manifest['exports']) is not list or not 2<=len(manifest['exports'])<=32):
        raise ValueError('Exact bounded retrospective selection required')
    workspace=Path(__file__).resolve().parents[2]
    entries=[]
    for selection in manifest['exports']:
        if set(selection)!={'campaign_id','report_sha256','split'}:
            raise ValueError('Exact campaign selection required')
        cid=selection['campaign_id']
        if not re.fullmatch('campaign-[a-f0-9]{32}',cid):
            raise ValueError('Exact campaign identifier required')
        entries.append(dict(directory=str(workspace/'software/runs/wizard-exports'/cid),
            report_name=cid+'-parent-report.json',report_sha256=selection['report_sha256'],split=selection['split']))
    print(json.dumps(compare_exports(entries),indent=2))


if __name__=='__main__':
    main()
