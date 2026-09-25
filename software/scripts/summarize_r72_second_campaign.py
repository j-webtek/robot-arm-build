"""Offline replay and comparison of the second physical r72 wrist campaign."""
import json
from pathlib import Path
from statistics import mean

from rocell.application.first_motion_contract import canonical
from rocell.application.p4_repeat_campaign import assess_leg
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export

BOOT='62d0bf638a2d7763a452fa8eb7c19198'
SOURCES=(
 'wizard-20260924T185209342095Z-e971ca519e004b439811f12c235c9612',
 'wizard-20260924T185210968634Z-4b28634c61ea482194516b2e54d0229d',
 'wizard-20260924T185212402873Z-ce5d304a13994be1a003cd99fb186479',
 'wizard-20260924T185213847013Z-fb2280d3b0134ea1b64af7a777293c21',
 'wizard-20260924T185215478384Z-feb64ad821b7416c81cbe9c8c411e046',
 'wizard-20260924T185217638896Z-6df22df5955844c2a77b828826eaae8d',
 'wizard-20260924T185219867260Z-bba72cf12b754ee7b63fa3d0dd856dc0',
 'wizard-20260924T185221413295Z-d57700bcf46448aeb31915aeaf31ae38',
 'wizard-20260924T185222961331Z-5fc5908d047c41d89b757572c7b32ec0',
 'wizard-20260924T185224590980Z-a9eda7b4be4a4741951e1875ba54109b',
 'wizard-20260924T185226131326Z-0f8cec7f7f724319825f6cd9bb4239c5',
 'wizard-20260924T185228366510Z-b0da455a91d347afb407d54fb53ed9e0',
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
            'High-goal arrivals repeat here but varied by two counts in the first session',
            'Controller feedback is not external stylus-tip or millimetre accuracy',
            'No shoulder/elbow reverse validation or general compensation claim'])
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({'mode':'r72-physical-campaign-offline-summary'},[],attachments={
        'r72-campaign-summary.json':canonical(summary)})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Summary export invalid')
    return dict(export=saved['path'],**summary)


if __name__=='__main__':print(json.dumps(summarize(Path(__file__).resolve().parents[1])))
