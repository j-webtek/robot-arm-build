"""One authenticated fixed 16-leg wrist comparison on reviewed r73 startup."""
import argparse
import json
import os
from pathlib import Path

from observe_r33_campaign import load_reviewed_key
from rocell.application.characterization_http import CharacterizationHTTP
from rocell.application.first_motion_contract import canonical
from rocell.application.hold_transport_snapshot import HoldHTTPReader, STATUS
from rocell.application.p4_correction_campaign import P4CorrectionHost
from rocell.application.p4_correction_scoring import score_exported_campaign
from rocell.application.p4_endpoint_prediction import TEST, load_session
from rocell.application.supported_recovery_installation import review_recovery_startup
from rocell.application.wizard_diagnostic_coordinator import decode_diagnostic_json
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def preflight(root, startup_export):
    root=Path(root).resolve();exports=root/'runs/wizard-exports'
    binding=review_recovery_startup(root,startup_export,revision=73)
    last=load_session(exports,TEST)[-1]
    if (last['final_positions']!=[2047,2225,1890,2716,1977,2041,2047] or
        last['final_goals']!=[2047,2217,1897,2711,1980,2040,2047]):
        raise ValueError('Retained source pose differs')
    boot=binding['expected_boot']
    claim=exports/f'r73-p4-correction-{boot}.json'
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
        print(json.dumps(dict(status='R73_P4_BINDING_VERIFIED',
            boot=binding['expected_boot'],source_export=TEST,hardware_access=False)))
        return
    reader=HoldHTTPReader(binding['address'])
    raw=reader(STATUS,maximum_bytes=512,timeout_seconds=3)
    status=decode_diagnostic_json(raw,maximum=512)
    if (status.get('instance_id')!=binding['expected_boot'] or
        status.get('state')!='IDLE' or status.get('storage_fault') is not False):
        raise ValueError('Reviewed r73 startup is no longer idle live boot')
    key=load_reviewed_key(root)
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    with claim.open('x',encoding='utf-8') as stream:
        json.dump(dict(boot=binding['expected_boot'],startup_export=args.startup_export,
            source_export=TEST,scope='one-fixed-16-leg-P4C16-comparison',retry_allowed=False),stream)
        stream.flush();os.fsync(stream.fileno())
    client=CharacterizationHTTP(binding['address'],key=key,boot=binding['expected_boot'])
    result=P4CorrectionHost(client,export_root=exports,
        boot=binding['expected_boot'],source_kind='controller_feedback').run_once()
    source_ids=[Path(path).name for path in result['exports']]
    score=score_exported_campaign(exports,source_ids,boot=binding['expected_boot'])
    saved=exporter.export({'mode':'r73-p4-correction-physical-summary'},[],attachments={
        'r73-p4-correction-summary.json':canonical(score)})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Summary export failed; no validated comparison')
    print(json.dumps(dict(status=result['status'],summary_export=saved['path'],score=score)))


if __name__=='__main__':main()
