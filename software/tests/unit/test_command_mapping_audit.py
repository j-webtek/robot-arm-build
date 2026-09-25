import hashlib
from rocell.application.first_motion_contract import canonical
from rocell.application.coordinated_trace_review import audit_command_mapping
from rocell.application.local_tip_press import RETRACT_START,RETRACT_GOAL
from rocell.kinematics.firmware_reference import forward,inverse


def report():
    pose=forward(*RETRACT_GOAL)
    command=dict(T=104,**dict(zip(('x','y','z','t'),pose)),r=RETRACT_START[4],g=RETRACT_START[5],spd=.05)
    final=[.001533981,.033747577,1.67357304,-.052155347,.018407769,3.138524692]
    return dict(receipt=dict(payload_sha256=hashlib.sha256(canonical(command)).hexdigest()),
        run=dict(move_request=dict(command=command.copy()),transaction=dict(command=command,
        baseline_joints=RETRACT_START,expected_joints=[*inverse(*pose),*RETRACT_START[4:]],
        rows=[[1,2,list(forward(*final[:4])),final]])))


def test_audit_distinguishes_host_binding_from_actuator_evidence():
    a=audit_command_mapping(report())
    assert a['transport_payload_hash_matches'] and a['reserved_command_matches']
    assert a['inverse_expected_max_error_rad']==0
    assert a['opposite_reported_count_direction']==['e']
    assert a['reference_count_comparison'][2]['count_error']==10
    assert not a['quantization_only_explanation_supported']
    assert not a['servo_bus_writes_observed'] and not a['physical_cause_identified']


def test_audit_exposes_changed_command_or_hash():
    r=report();r['receipt']['payload_sha256']='wrong'
    r['run']['move_request']['command']['z']+=1
    a=audit_command_mapping(r)
    assert not a['transport_payload_hash_matches'] and not a['reserved_command_matches']
