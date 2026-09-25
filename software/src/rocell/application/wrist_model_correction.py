"""Offline-only bounded correction design; incompatible with native intents.

Revalidate prospective exports before using the frozen model. No transport,
signing, admission or automatic retry is exposed. A prediction is not a test.
"""
from dataclasses import dataclass
import hashlib
import json
import math

from .first_motion_contract import canonical
from .positional_campaign_native_export import verify_native_retained_export
from .wrist_accuracy_analysis import reference_wrist_goal
from rocell.arm.wrist_endpoint_verification import verify_reported_wrist


@dataclass(frozen=True)
class OfflineCorrectionProposal:
    """Immutable serialized experiment description, never a motion permit."""
    original: bytes

    def to_dict(self):
        return json.loads(self.original)

    @property
    def sha256(self):
        return hashlib.sha256(self.original).hexdigest()


def propose_model_correction(model_raw, *, expected_model_sha256, exports,
                             start_joints_rad, nominal_target_deg=2):
    if (type(model_raw) is not bytes or len(model_raw)>65536
            or hashlib.sha256(model_raw).hexdigest()!=expected_model_sha256):
        raise ValueError('Frozen model bytes changed')
    model=json.loads(model_raw)
    if (model['schema']!='rocell.offline_wrist_endpoint_models.v1'
            or model['compensation_enabled'] is not False
            or model['motion_authorized'] is not False):
        raise ValueError('Offline frozen model required')
    bias=model['direction_bias_deg']
    if (set(bias)!={'INCREASING','DECREASING'} or
            any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>1 for v in bias.values())):
        raise ValueError('Directional bias exceeds one-degree experiment bound')
    if type(exports) is not list or not 6<=len(exports)<=16:
        raise ValueError('Six through sixteen prospective exports required')
    groups={d:[] for d in bias}
    refs=[];seen=set();context=None
    for selection in exports:
        if set(selection)!={'directory','report_name','report_sha256'}:
            raise ValueError('Exact export reference required')
        result=verify_native_retained_export(selection['directory'],selection['report_name'])
        digest=result['report_sha256']
        if (digest!=selection['report_sha256'] or digest in seen
                or not result['valid'] or not result['reconstruction_consistent']):
            raise ValueError('Changed, duplicate or incomplete prospective export')
        seen.add(digest)
        current={k:result['configuration_references'][k] for k in (
            'native_controller_review_sha256','tool_payload_sha256','workcell_sha256','protocol_review_sha256')}
        if context is not None and context!=current:
            raise ValueError('Prospective context differs')
        context=current
        matches=[e for e in result['endpoint_diagnostics'] if e['target_rad']==math.radians(2) and e['final_rad'] is not None]
        if len(matches)!=1:
            raise ValueError('One executed prospective +2 endpoint per campaign required')
        e=matches[0];direction=e['direction']
        if direction not in groups or e['command']!=dict(T=101,joint=4,rad=math.radians(2),spd=20,acc=1):
            raise ValueError('Prospective command or direction differs')
        error=math.degrees(e['signed_error_rad'])
        if not math.isfinite(error) or abs(error-bias[direction])>.25:
            raise ValueError('Prospective prediction screen failed')
        groups[direction].append(dict(start_rad=e['start_rad'],error_deg=error))
        refs.append(dict(selection,leg_id=e['leg_id']))
    if any(len(g)<3 for g in groups.values()):
        raise ValueError('At least three independent trials per direction required')
    errors=[(d,r['error_deg']) for d,g in groups.items() for r in g]
    directional=sum(abs(e-bias[d]) for d,e in errors)
    if directional>=min(sum(abs(e) for _,e in errors),
            sum(abs(e-model['constant_bias_deg']) for _,e in errors)):
        raise ValueError('Direction model does not improve frozen baseline predictions')
    for original in model['provenance']:
        if any(original['configuration_references'][k]!=v for k,v in context.items()):
            raise ValueError('Model training context differs from prospective context')
        if original['report_sha256'] in seen:
            raise ValueError('Prospective data overlap model data')
    if (type(nominal_target_deg) not in (int,float) or nominal_target_deg!=2
            or type(start_joints_rad) not in (list,tuple) or len(start_joints_rad)!=6
            or any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>2*math.pi for v in start_joints_rad)):
        raise ValueError('Finite six-joint start and validated +2 target required')
    start=math.degrees(start_joints_rad[3]);target=float(nominal_target_deg)
    direction='INCREASING' if target>start else 'DECREASING'
    command=target-bias[direction]
    # Use the raw corrected radian request, not the decoded reference feedback
    # angle. The device performs its own rounding; the model already includes
    # the observed command-to-feedback offset. Do not apply it a second time.
    if (max(abs(start),abs(target),abs(command))>10
            or not .5<abs(target-start)<=5 or not .5<abs(command-start)<=5
            or (command-start)*(target-start)<=0):
        raise ValueError('Correction reverses direction or exceeds movement envelope')
    starts=[math.degrees(r['start_rad']) for r in groups[direction]]
    if not min(starts)-.5<=start<=max(starts)+.5:
        raise ValueError('Starting wrist is outside demonstrated approach context')
    goal=reference_wrist_goal(math.radians(command))
    if goal['clamped']:
        raise ValueError('Reference firmware would clamp command')
    proposal=dict(schema='rocell.offline_model_correction_proposal.v1',
        nominal_target_deg=target, proposed_command_target_deg=command,
        proposed_command_target_rad=math.radians(command),direction=direction,
        bias_deg=bias[direction],model_predicted_final_deg=command+bias[direction],
        uncorrected_mean_absolute_error_deg=sum(abs(r['error_deg']) for r in groups[direction])/len(groups[direction]),
        correction_screen_maximum_error_deg=.25,
        prediction_is_algebraic_not_measurement=True,reference_goal=goal,
        expected_start_joints_rad=list(start_joints_rad),start_is_historical_only=True,
        frozen_model_sha256=expected_model_sha256,prospective_exports=refs,
        context_references=context,spd=20,acc=1,maximum_commands=1,
        arrival_tolerance_deg=.5,observation_s=5,maximum_delta_deg=5,
        motion_authorized=False,compensation_enabled=False,automatic_retry=False,
        physical_accuracy_verified=False,fresh_baseline_required=True,
        native_integration_status='NOT_IMPLEMENTED_FOR_THIS_SCHEMA')
    return OfflineCorrectionProposal(canonical(proposal))


def score_synthetic_correction(proposal, rows, *, transport_clean=True, capture_issues=()):
    """Exercise nominal scoring only; cannot turn input rows into live evidence.

    Conservatively preserve the existing nominal-target excursion rule as well
    as the proposed-command corridor. Real capture validation remains required
    in a future explicitly integrated native path.
    """
    if type(proposal) is not OfflineCorrectionProposal:
        raise ValueError('Exact offline proposal required')
    p=proposal.to_dict()
    if type(rows) is not list or not 20<=len(rows)<=512:
        raise ValueError('Bounded synthetic endpoint rows required')
    capture_issues=list(capture_issues)
    if not 4_800_000_000<=rows[-1][0]-rows[0][1]<=5_250_000_000:
        capture_issues.append('INCOMPLETE_SYNTHETIC_WINDOW')
    if any(b[0]-a[1]>100_000_000 for a,b in zip(rows,rows[1:])):
        capture_issues.append('SYNTHETIC_READ_GAP')
    nominal=verify_reported_wrist(rows,start=p['expected_start_joints_rad'],
        target=math.radians(p['nominal_target_deg']),capture_issues=capture_issues,transport_clean=transport_clean)
    commanded=verify_reported_wrist(rows,start=p['expected_start_joints_rad'],
        target=p['proposed_command_target_rad'],capture_issues=capture_issues,transport_clean=transport_clean)
    nominal_pass=nominal['endpoint_verified'] and not commanded['wrist_excursion']
    correction_pass=(nominal_pass and abs(nominal['final_error_rad'])<=math.radians(.25)
        and abs(nominal['final_error_rad'])<math.radians(p['uncorrected_mean_absolute_error_deg']))
    return dict(schema='rocell.synthetic_model_correction_score.v1',proposal_sha256=proposal.sha256,
        basis='SYNTHETIC_ONLY',nominal_endpoint=nominal,command_endpoint_diagnostic=commanded,
        simulation_passed=nominal_pass,correction_screen_passed=correction_pass,
        motion_authorized=False,automatic_next_command_allowed=False)
