"""Offline replay and comparison of the first physical r72 wrist campaign."""
import json
from pathlib import Path
from statistics import mean

from rocell.application.first_motion_contract import canonical
from rocell.application.p4_repeat_campaign import assess_leg
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export

BOOT='bc34f3be743dad1a774e82cfac95280e'
SOURCES=(
 'wizard-20260924T184809085534Z-0f2f1de8868040d8907b9bac40cd6590',
 'wizard-20260924T184810728920Z-ccc99b6447b8440f9002ebbfe3c2b321',
 'wizard-20260924T184812388522Z-e7cc49c3f739445e921d5aaf7f84914f',
 'wizard-20260924T184813906327Z-1fd46d60f9064a1ab64c51afada7b7b9',
 'wizard-20260924T184815537241Z-7aa02ab88b1b4c6ea85ebce15ee5479d',
 'wizard-20260924T184817995507Z-426ae11ed9ac4582b92cea6fa8371e59',
 'wizard-20260924T184820279187Z-6e04384147014a33a5ef62ebb896a5d5',
 'wizard-20260924T184821906580Z-e3b1820cfca14afdb5d362b5402b136a',
 'wizard-20260924T184823527120Z-e523b8f6da1646409b523f93ed642f74',
 'wizard-20260924T184825079175Z-d91a7bea40904743a5a78e809d8d43ff',
 'wizard-20260924T184826598096Z-165c3ccf78164d2aac2d49ee1b0ebc3b',
 'wizard-20260924T184828853128Z-3b158e1a3d1b4dde88ab51efacd18f37',
)


def summarize(root):
    exports=Path(root).resolve()/'runs/wizard-exports'
    rows=[]
    for leg,source in enumerate(SOURCES,1):
        saved,_=_read(exports,source,'attachment-p4-repeat-assessment.json')
        if not verify_export(exports/source)['valid']:raise ValueError('Invalid source export')
        raw=bytes.fromhex((exports/source/'attachment-p4-repeat-record.hex.txt').read_text('ascii'))
        row=assess_leg(raw,boot=BOOT,leg=leg,previous=rows[-1] if rows else None)
        row['source_kind']='controller_feedback'
        if canonical(row)!=canonical(saved):raise ValueError('Stored result differs from raw replay')
        rows.append(row)
    groups=[]
    for goal,direction in sorted({(r['target'],r['direction']) for r in rows}):
        chosen=[r for r in rows if (r['target'],r['direction'])==(goal,direction)]
        positions=[r['final_positions'][4] for r in chosen]
        groups.append(dict(goal=goal,direction=direction,arrivals=len(chosen),
            positions=positions,errors=[r['endpoint_error_counts'] for r in chosen],
            mean_error_counts=mean(r['endpoint_error_counts'] for r in chosen),
            endpoint_spread_counts=max(positions)-min(positions)))
    mid={g['direction']:g for g in groups if g['goal']==1947}
    errors=[abs(r['endpoint_error_counts']) for r in rows]
    summary=dict(schema='rocell.r72_physical_campaign_summary.v1',boot=BOOT,source_exports=list(SOURCES),
        verified_legs=len(rows),groups=groups,maximum_absolute_error_counts=max(errors),
        mean_absolute_error_counts=mean(errors),
        midpoint_reverse_minus_forward_counts=mid[-1]['mean_error_counts']-mid[1]['mean_error_counts'],
        final_positions=rows[-1]['final_positions'],final_goals=rows[-1]['final_goals'],
        hardware_access=False,compensation_applied=False,continuation_authorized=False,
        limitations=['One boot and two cycles; limited wrist interval and fixed speed/load',
            'Direction-dependent midpoint offset observed; mechanical cause not established',
            'High-goal arrivals differ by two counts between cycles despite same direction',
            'Controller feedback is not external stylus-tip or millimetre accuracy',
            'No shoulder/elbow reverse validation or general compensation claim'])
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({'mode':'r72-physical-campaign-offline-summary'},[],attachments={
        'r72-campaign-summary.json':canonical(summary)})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Summary export invalid')
    return dict(export=saved['path'],**summary)


if __name__=='__main__':print(json.dumps(summarize(Path(__file__).resolve().parents[1])))
