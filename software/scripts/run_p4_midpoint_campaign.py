"""One authenticated fixed 16-leg wrist comparison on reviewed r74 startup."""
import argparse
import json
import os
from pathlib import Path

from observe_r33_campaign import load_reviewed_key
from rocell.application.characterization_http import CharacterizationHTTP
from rocell.application.first_motion_contract import canonical
from rocell.application.hold_transport_snapshot import HoldHTTPReader, STATUS
from rocell.application.p4_midpoint_campaign import P4MidpointHost
from rocell.application.p4_midpoint_scoring import score_exported_campaign
from rocell.application.product_ghost_export_review import _read
from rocell.application.p4_correction_scoring import score_exported_campaign as score_r73_exports
from rocell.application.supported_recovery_installation import review_recovery_startup
from rocell.application.wizard_diagnostic_coordinator import decode_diagnostic_json
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export

R73_SUMMARY='wizard-20260924T193000463098Z-0dd40c9e0c784847bda008593634ad38'
R73_BOOT='3b61679887bee5e72bc70ca6ffdf7344'


def preflight(root, startup_export):
    root=Path(root).resolve();exports=root/'runs/wizard-exports'
    binding=review_recovery_startup(root,startup_export,revision=74)
    summary,_=_read(exports,R73_SUMMARY,'attachment-r73-p4-correction-summary.json')
    score_r73_exports(exports,summary['source_exports'],boot=R73_BOOT)
    last,_=_read(exports,summary['source_exports'][-1],'attachment-p4-correction-assessment.json')
    if (last['final_positions']!=[2047,2225,1890,2716,1978,2041,2047] or
        last['final_goals']!=[2047,2217,1897,2711,1980,2040,2047]):
        raise ValueError('Retained source pose differs')
    boot=binding['expected_boot']
    claim=exports/f'r74-p4-midpoint-{boot}.json'
    if claim.exists() or (exports/f'pose-observation-{boot}.json').exists():
        raise ValueError('Boot already claimed')
    return binding,exports,claim


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--startup-export',required=True)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preflight-only',action='store_true')
    mode.add_argument('--authorized-once',action='store_true')
    args=parser.parse_args(argv)
    root=Path(__file__).resolve().parents[1]
    binding,exports,claim=preflight(root,args.startup_export)
    if args.preflight_only:
        print(json.dumps(dict(status='R74_P4_BINDING_VERIFIED',
            boot=binding['expected_boot'],source_export=R73_SUMMARY,hardware_access=False)))
        return
    reader=HoldHTTPReader(binding['address'])
    raw=reader(STATUS,maximum_bytes=512,timeout_seconds=3)
    status=decode_diagnostic_json(raw,maximum=512)
    if (status.get('instance_id')!=binding['expected_boot'] or
        status.get('state')!='IDLE' or status.get('storage_fault') is not False):
        raise ValueError('Reviewed r74 startup is no longer idle live boot')
    key=load_reviewed_key(root)
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    with claim.open('x',encoding='utf-8') as stream:
        json.dump(dict(boot=binding['expected_boot'],startup_export=args.startup_export,
            source_export=R73_SUMMARY,scope='one-fixed-16-leg-P4M16-comparison',retry_allowed=False),stream)
        stream.flush();os.fsync(stream.fileno())
    client=CharacterizationHTTP(binding['address'],key=key,boot=binding['expected_boot'])
    result=P4MidpointHost(client,export_root=exports,
        boot=binding['expected_boot'],source_kind='controller_feedback').run_once()
    source_ids=[Path(path).name for path in result['exports']]
    score=score_exported_campaign(exports,source_ids,boot=binding['expected_boot'])
    saved=exporter.export({'mode':'r74-p4-midpoint-physical-summary'},[],attachments={
        'r74-p4-midpoint-summary.json':canonical(score)})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Summary export failed; no validated comparison')
    print(json.dumps(dict(status=result['status'],summary_export=saved['path'],score=score)))


if __name__=='__main__':main()
