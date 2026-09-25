"""Offline endpoint prediction from independently verified campaign exports.

No serial imports, inverse commands, runtime registration or motion authority.
One endpoint is one observation; hundreds of frames are not extra trials.
"""
import math
from statistics import mean

from .positional_campaign_native_export import verify_native_retained_export


def compare_exports(entries):
    """Fit zero-target biases on named campaigns; score disjoint campaigns.

    Splits are retrospective unless their manifest predates collection. A
    matching hash establishes integrity, not physical accuracy or freshness.
    """
    if not isinstance(entries, list) or not 2 <= len(entries) <= 32:
        raise ValueError('Two through 32 explicitly selected exports required')
    seen, provenance, rows, excluded = set(), [], [], []
    context = None
    for entry in entries:
        if set(entry) != {'directory','report_name','report_sha256','split'} or entry['split'] not in ('train','validation'):
            raise ValueError('Exact export selection and split required')
        checked = verify_native_retained_export(entry['directory'], entry['report_name'])
        digest = checked['report_sha256']
        if digest != entry['report_sha256'] or digest in seen:
            raise ValueError('Changed or duplicate campaign; split leakage prohibited')
        if not checked['valid'] or not checked['reconstruction_consistent']:
            raise ValueError('Fully reconstructable original endpoint records required')
        seen.add(digest)
        refs = checked['configuration_references']
        # Baselines and target configurations legitimately differ. Hardware,
        # tool, workcell and reviewed protocol must retain the same context.
        current = {k: refs[k] for k in ('native_controller_review_sha256',
            'tool_payload_sha256','workcell_sha256','protocol_review_sha256')}
        if context is not None and current != context:
            raise ValueError('Incompatible experiment contexts')
        context = current
        provenance.append(dict(entry, configuration_references=refs))
        for endpoint in checked['endpoint_diagnostics']:
            if endpoint['final_rad'] is None or endpoint['target_rad'] != 0:
                excluded.append(dict(report_sha256=digest, leg_id=endpoint['leg_id'],
                    reason='NOT_EXECUTED' if endpoint['final_rad'] is None else 'NONZERO_TARGET'))
                continue
            if endpoint['command'] != dict(T=101,joint=4,rad=0.,spd=20,acc=1):
                raise ValueError('Matched nominal target, speed and acceleration required')
            direction = endpoint['direction']
            error = endpoint['signed_error_rad']
            if direction not in ('INCREASING','DECREASING') or type(error) not in (int,float) or not math.isfinite(error):
                raise ValueError('Finite directional endpoint required')
            rows.append(dict(report_sha256=digest,leg_id=endpoint['leg_id'],
                split=entry['split'],direction=direction,error_deg=math.degrees(error),
                reported_pass=endpoint['reported_endpoint_verified']))
    training = [r for r in rows if r['split']=='train']
    validation = [r for r in rows if r['split']=='validation']
    if not validation or {r['direction'] for r in training} != {'INCREASING','DECREASING'}:
        raise ValueError('Both training directions and disjoint validation required')
    biases = {d:mean(r['error_deg'] for r in training if r['direction']==d)
              for d in ('INCREASING','DECREASING')}
    constant = mean(r['error_deg'] for r in training)
    models = {}
    for name in ('nominal','constant_bias','direction_bias'):
        predictions = []
        for row in validation:
            predicted = 0. if name=='nominal' else constant if name=='constant_bias' else biases[row['direction']]
            predictions.append(dict(row,predicted_error_deg=predicted,
                prediction_residual_deg=row['error_deg']-predicted))
        residuals = [p['prediction_residual_deg'] for p in predictions]
        models[name] = dict(mae_deg=mean(abs(v) for v in residuals),
            rmse_deg=math.sqrt(mean(v*v for v in residuals)),
            maximum_absolute_residual_deg=max(abs(v) for v in residuals),predictions=predictions)
    return dict(schema='rocell.offline_wrist_endpoint_models.v1',
        basis='RETROSPECTIVE_CAMPAIGN_DISJOINT_ZERO_TARGET_COMPARISON',
        physical_accuracy_verified=False, device_freshness_verified=False,
        motion_authorized=False, compensation_enabled=False,
        prediction_domain=dict(target_deg=0,spd=20,acc=1),
        training_count=len(training),validation_count=len(validation),
        training_counts_by_direction={d:sum(r['direction']==d for r in training) for d in biases},
        constant_bias_deg=constant,direction_bias_deg=biases,models=models,
        observations=rows,excluded_endpoints=excluded,provenance=provenance,
        limitations=['Retrospective split: outcomes were already inspected.',
            'Zero-only fit cannot establish generalization to new targets.',
            'Quantized controller reports are not independent physical measurements.',
            'Prediction error reduction is not measured improvement from compensation.'])
