"""One explicitly requested saved-result GET; no POST, startup or servo writes."""
import argparse
import json
from pathlib import Path
from rocell.application.elbow_gain_retention import prepare_retained_gain, retrieve_retained_gain


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-export',required=True)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preflight-only',action='store_true')
    mode.add_argument('--authorized-one-retained-get',action='store_true')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]/'runs/wizard-exports'
    if args.preflight_only:
        report, _, digest=prepare_retained_gain(root,args.source_export)
        print(json.dumps(dict(status='LOCAL_RETENTION_PREFLIGHT_VERIFIED',
            source_sha256=digest,subject=report['subject'],hardware_access=False)))
        return
    print(json.dumps(retrieve_retained_gain(root,args.source_export,authorized=True)))


if __name__=='__main__':main()
