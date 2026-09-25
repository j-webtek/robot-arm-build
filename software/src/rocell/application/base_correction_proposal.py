"""Evidence-bound inverse proposal for one local base experiment, offline only.

Rebuild training and held-out observations from portable originals. Never load
coefficients from summary claims alone. Desired endpoint and transmitted target
remain separate. This module has no serial, signing or native admission API.
"""
import hashlib
import math
from dataclasses import dataclass
from .first_motion_contract import canonical
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .base_endpoint_dataset import build_base_dataset,fit_local_base_lines,predict_unseen_base_target
from rocell.arm.joint_endpoint_verification import verify_reported_joint


@dataclass(frozen=True)
class BaseCorrectionProposal:
    original: bytes

    def to_dict(self):
        return decode_diagnostic_json(self.original,maximum=32768)

    @property
    def sha256(self):
        return hashlib.sha256(self.original).hexdigest()


def propose_base_correction(model_raw, *, expected_model_sha256, training_exports,
        held_out, start_joints_rad):
    """Only +1 degree desired feedback, increasing approach, no extrapolation."""
    return _propose_directional_base_correction(model_raw,expected_model_sha256=expected_model_sha256,
        training_exports=training_exports,held_out=held_out,start_joints_rad=start_joints_rad,
        direction='INCREASING')


def propose_decreasing_base_correction(model_raw, *, expected_model_sha256, training_exports,
        held_out, start_joints_rad):
    """Offline-only +0.4-degree desired endpoint using the decreasing branch.

    Distinct proposal schema prevents admission through the positive v10/v11
    profiles. This prepares an experiment; it does not release native motion.
    """
    return _propose_directional_base_correction(model_raw,expected_model_sha256=expected_model_sha256,
        training_exports=training_exports,held_out=held_out,start_joints_rad=start_joints_rad,
        direction='DECREASING')


def _propose_directional_base_correction(model_raw, *, expected_model_sha256,
        training_exports, held_out, start_joints_rad, direction):
    if type(model_raw) is not bytes or len(model_raw)>65536 or hashlib.sha256(model_raw).hexdigest()!=expected_model_sha256:
        raise ValueError('Exact frozen model original required')
    model=decode_diagnostic_json(model_raw,maximum=65536)
    training=build_base_dataset(training_exports)
    rebuilt=fit_local_base_lines(training)
    if canonical(model)!=canonical(rebuilt):raise ValueError('Model differs from verified training reconstruction')
    if type(held_out) is not list or not 3<=len(held_out)<=16:
        raise ValueError('Three through sixteen held-out originals required')
    trained={r['campaign_id'] for r in training['rows']};seen=set();targets=set();checks=[]
    for item in held_out:
        if type(item) is not dict or set(item)!={'export','prediction_raw','prediction_sha256'}:
            raise ValueError('Exact original prediction/export pair required')
        raw=item['prediction_raw']
        if type(raw) is not bytes or len(raw)>32768 or hashlib.sha256(raw).hexdigest()!=item['prediction_sha256']:
            raise ValueError('Frozen prediction original changed')
        p=decode_diagnostic_json(raw,maximum=32768)
        r=build_base_dataset([item['export']])['rows'][0]
        key=(r['direction'],r['target_rad'])
        if r['campaign_id'] in trained|seen or key in targets:
            raise ValueError('Held-out targets overlap training or duplicate validation')
        seen.add(r['campaign_id']);targets.add(key)
        expected=predict_unseen_base_target(model,target_rad=r['command_rad'],start_joints_rad=r['start_joints_rad'])
        if (p.get('schema')!='rocell.base_held_out_prediction.v1'
                or any(p.get(k)!=expected[k] for k in ('model_sha256','direction','target_rad','start_joints_rad','predicted_final_rad','prediction_tolerance_deg'))
                or r['context']!=model['context'] or p.get('model_file_sha256')!=expected_model_sha256):
            raise ValueError('Prediction, model, pose or context association differs')
        error=abs(r['final_joints_rad'][0]-expected['predicted_final_rad'])
        if error>math.radians(.25):raise ValueError('Held-out linear prediction failed screen')
        comparative=p.get('comparison_predeclared') is True
        nearest_error=None
        if comparative:
            if any(p.get(k)!=expected[k] for k in ('nearest_anchor_final_rad','nearest_anchor_command_rad','nearest_anchor_tie_rule')):
                raise ValueError('Predeclared comparator differs')
            nearest_error=abs(r['final_joints_rad'][0]-expected['nearest_anchor_final_rad'])
        checks.append(dict(campaign_id=r['campaign_id'],report_sha256=r['report_sha256'],
            prediction_sha256=item['prediction_sha256'],direction=r['direction'],
            target_rad=r['target_rad'],linear_error_rad=error,nearest_error_rad=nearest_error))
    if sum(c['direction']=='INCREASING' for c in checks)<2 or not any(c['direction']=='DECREASING' for c in checks):
        raise ValueError('Both approaches and two increasing holdouts required')
    comparisons=[c for c in checks if c['nearest_error_rad'] is not None]
    if (len(comparisons)<2 or {c['direction'] for c in comparisons}!={'INCREASING','DECREASING'}
            or sum(c['linear_error_rad'] for c in comparisons)>=sum(c['nearest_error_rad'] for c in comparisons)):
        raise ValueError('Predeclared directional comparison does not favor linear hypothesis')
    if (type(start_joints_rad) is not list or len(start_joints_rad)!=6
            or any(type(v) not in (int,float) or not math.isfinite(v) for v in start_joints_rad)):
        raise ValueError('Finite six-joint planned start required')
    m=next(m for m in model['models'] if m['direction']==direction)
    if direction=='DECREASING' and start_joints_rad[0]<=math.radians(.9):
        raise ValueError('Decreasing nominal move requires a start above +0.9 degree')
    desired=math.radians(1 if direction=='INCREASING' else .4)
    command=(desired-m['intercept_rad'])/m['slope']
    prediction=predict_unseen_base_target(model,target_rad=command,start_joints_rad=start_joints_rad)
    if prediction['direction']!=direction or not math.isclose(prediction['predicted_final_rad'],desired,rel_tol=0,abs_tol=1e-12):
        raise ValueError('Inverse proposal changed branch or prediction')
    for target in (desired,command):
        signed_delta=(target-start_joints_rad[0])*(1 if direction=='INCREASING' else -1)
        if not math.radians(.5)<signed_delta<=math.radians(2.5) or abs(target)>math.radians(5):
            raise ValueError('Nominal or motor target exceeds local experiment bounds')
    return BaseCorrectionProposal(canonical(dict(schema='rocell.offline_base_correction_proposal.v1' if direction=='INCREASING' else 'rocell.offline_base_correction_proposal.v2',
        nominal_target_rad=desired,proposed_command_target_rad=command,
        predicted_final_rad=prediction['predicted_final_rad'],direction=direction,
        expected_start_joints_rad=list(start_joints_rad),start_is_historical_only=True,
        start_domain_rad=m['observed_start_range_rad'],command_domain_rad=[a['command_rad'] for a in m['anchors']],
        model_file_sha256=expected_model_sha256,model_sha256=prediction['model_sha256'],
        training_dataset_sha256=model['dataset_sha256'],held_out_checks=checks,
        context_references=model['context'],maximum_commands=1,spd=20,acc=1,
        maximum_delta_deg=2.5,observation_s=5,arrival_tolerance_deg=.5,
        experiment_error_screen_deg=.25,automatic_retry=False,motion_authorized=False,
        compensation_enabled=False,physical_accuracy_verified=False,fresh_baseline_required=True,
        native_integration_status='IMPLEMENTED_V10_V11_LOCAL_EXPERIMENT_ONLY' if direction=='INCREASING' else 'IMPLEMENTED_V12_V13_LOCAL_EXPERIMENT_ONLY')))


def score_synthetic_base_correction(proposal, rows):
    """Exercise desired-endpoint verification separately from the motor target."""
    if type(proposal) is not BaseCorrectionProposal or type(rows) is not list or not 20<=len(rows)<=512:
        raise ValueError('Typed proposal and bounded synthetic rows required')
    p=proposal.to_dict();issues=[]
    if not 4_800_000_000<=rows[-1][0]-rows[0][1]<=5_250_000_000:
        issues.append('INCOMPLETE_WINDOW')
    if any(b[0]-a[1]>100_000_000 for a,b in zip(rows,rows[1:])):issues.append('READ_GAP')
    nominal=verify_reported_joint(rows,joint='b',start=p['expected_start_joints_rad'],target=p['nominal_target_rad'],capture_issues=issues)
    motor=verify_reported_joint(rows,joint='b',start=p['expected_start_joints_rad'],target=p['proposed_command_target_rad'],capture_issues=issues)
    passed=bool(nominal['endpoint_verified'] and not motor['joint_excursion'] and abs(nominal['final_error_rad'])<=math.radians(.25))
    return dict(schema='rocell.synthetic_base_correction_score.v1',nominal_endpoint=nominal,
        motor_endpoint_diagnostic=motor,experiment_screen_passed=passed,
        motion_authorized=False,physical_accuracy_verified=False)
