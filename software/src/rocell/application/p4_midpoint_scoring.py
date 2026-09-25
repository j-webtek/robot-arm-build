"""Scientific screening of independently verified comparison records."""
from statistics import mean
from pathlib import Path
from .p4_midpoint_campaign import assess_leg
from .first_motion_contract import canonical
from .product_ghost_export_review import _read
from .wizard_diagnostic_export import verify_export


def score_records(records, *, boot):
    if len(records)!=16:
        raise ValueError('Incomplete comparison is inconclusive')
    rows=[]
    for leg,raw in enumerate(records,1):
        rows.append(assess_leg(raw,boot=boot,leg=leg,previous=rows[-1] if rows else None))
    metrics={}
    for condition in ('baseline','candidate'):
        selected=[r for r in rows if r['role']=='comparison' and r['condition']==condition]
        errors=[r['desired_error_counts'] for r in selected]
        metrics[condition]=dict(errors_counts=errors,mae_counts=mean(abs(e) for e in errors),
            max_absolute_error_counts=max(abs(e) for e in errors),spread_counts=max(errors)-min(errors),
            anchor_positions=[r['anchor_position'] for r in selected])
    a,b=metrics['baseline'],metrics['candidate']
    improvement=a['mae_counts']-b['mae_counts']
    passed=(b['max_absolute_error_counts']<=1 and b['mae_counts']<=0.5 and
            b['spread_counts']<=1)
    balanced=sorted(a['anchor_positions'])==sorted(b['anchor_positions'])
    common=sorted(set(a['anchor_positions']) & set(b['anchor_positions']))
    by_anchor=[]
    for anchor in common:
        baseline_errors=[abs(error) for error,position in zip(
            a['errors_counts'],a['anchor_positions']) if position==anchor]
        candidate_errors=[abs(error) for error,position in zip(
            b['errors_counts'],b['anchor_positions']) if position==anchor]
        by_anchor.append(dict(anchor_position=anchor,baseline_count=len(baseline_errors),
            candidate_count=len(candidate_errors),baseline_mae_counts=mean(baseline_errors),
            candidate_mae_counts=mean(candidate_errors)))
    return dict(schema='rocell.p4_midpoint_score.v1',metrics=metrics,
        mae_improvement_counts=improvement,screening_criteria_met=passed,
        anchor_distribution_balanced=balanced,
        comparative_claim_supported=bool(common),matched_anchor_metrics=by_anchor,
        result='LOCAL_SCREEN_PASS' if passed else 'REVIEW_REQUIRED',
        verified_legs=16,physical_accuracy_verified=False,
        limitation='Raw record scoring alone does not establish evidence provenance or stylus accuracy')


def score_exported_campaign(export_root, export_ids, *, boot, source_kind='controller_feedback'):
    """Replay immutable per-leg exports before any physical campaign score."""
    if (len(export_ids)!=16 or len(set(export_ids))!=16 or
            any(type(item) is not str or '/' in item or '\\' in item or item.startswith('.')
                for item in export_ids)):
        raise ValueError('Sixteen distinct export identifiers required')
    root=Path(export_root).resolve()
    raw_records=[];prior=None
    for leg,source in enumerate(export_ids,1):
        directory=(root/source).resolve()
        if directory.parent!=root or not verify_export(directory)['valid']:
            raise ValueError('Leg export invalid')
        saved,_=_read(root,source,'attachment-p4-midpoint-assessment.json')
        raw=bytes.fromhex((directory/'attachment-p4-midpoint-record.hex.txt').read_text('ascii'))
        row=assess_leg(raw,boot=boot,leg=leg,previous=prior)
        row['source_kind']=source_kind
        if canonical(row)!=canonical(saved):
            raise ValueError('Saved assessment differs from raw replay')
        raw_records.append(raw);prior=row
    result=score_records(raw_records,boot=boot)
    result['source_kind']=source_kind
    result['source_exports']=list(export_ids)
    result['physical_accuracy_verified']=False
    result['limitation']='Controller joint readback does not establish physical stylus accuracy'
    return result
