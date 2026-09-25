import copy
import hmac
import struct

import pytest

from rocell.application.first_motion_contract import canonical
from rocell.application.servo_diagnostic_simulation import simulate_trace
from rocell.application.servo_session_plan import SessionPlan, freeze_session_plan
from rocell.application.servo_start_authorization import (
    DOMAIN, StartAuthorizationGate, issue_challenge, sign_start,
)

KEY = bytes(range(32))  # Public deterministic fixture, never a deployment key.
BOOT = '0123456789abcdef0123456789abcdef'


def fixture():
    trace=simulate_trace('paired_arrival')
    trace['command'].update(boot_id=BOOT,servo_id=14)
    plan=freeze_session_plan(trace['command'],trace['policy'],canonical(trace['command']['payload']),
        dict(sample_count=3,sample_interval_us=1000000,maximum_lateness_us=1000000,maximum_pair_us=1000),
        origin='SIMULATION',baseline_policy=dict(maximum_delta_counts=16,settled_tolerance_counts=2,
            maximum_pair_us=1000,maximum_age_us=1000))
    challenge=issue_challenge(BOOT,1000,lease_us=10000)
    return plan,challenge


def gate(challenge):
    return StartAuthorizationGate(challenge,KEY,expected_origin='SIMULATION')


def test_valid_request_is_exact_plan_bound_and_one_use():
    plan,challenge=fixture();token=sign_start(plan,challenge,KEY)
    unsigned=token[:-32]
    # Independently lay out wire bytes for the future native verifier.
    expected=(DOMAIN+bytes.fromhex(BOOT)+bytes.fromhex(challenge['nonce'])
        +struct.pack('>QQH',1000,11000,len(plan.encoded))+plan.encoded)
    assert unsigned==expected
    assert token[-32:]==hmac.digest(KEY,expected,'sha256')
    verifier=gate(challenge);result=verifier.consume(token,now_us=1001)
    assert result['session_plan_sha256']==plan.sha256 and result['authenticated_request']
    assert not result['progression_authority'] and not result['write_attempted']
    assert not result['clearance_verified']
    with pytest.raises(ValueError,match='consumed'):verifier.consume(token,now_us=1002)


@pytest.mark.parametrize('fault',['domain','boot','nonce','time','length','plan','signature',
                                 'truncated','extra','wrong_key','expired','rewound','bool_time'])
def test_faults_consume_attempt_without_retry(fault):
    plan,challenge=fixture();token=sign_start(plan,challenge,KEY);now=1001
    if fault in ('domain','boot','nonce','time','length','plan','signature'):
        offsets={'domain':0,'boot':len(DOMAIN),'nonce':len(DOMAIN)+16,
            'time':len(DOMAIN)+48,'length':len(DOMAIN)+64,'plan':len(DOMAIN)+66,'signature':-1}
        changed=bytearray(token);changed[offsets[fault]]^=1;token=bytes(changed)
    if fault=='truncated':token=token[:-1]
    if fault=='extra':token+=b'!'
    if fault=='wrong_key':token=sign_start(plan,challenge,b'x'*32)
    if fault=='expired':now=11000
    if fault=='rewound':now=999
    if fault=='bool_time':now=True
    verifier=gate(challenge)
    with pytest.raises(ValueError):verifier.consume(token,now_us=now)
    with pytest.raises(ValueError,match='consumed'):
        verifier.consume(sign_start(plan,challenge,KEY),now_us=1001)


def test_other_challenge_and_default_live_gate_reject_simulation():
    plan,challenge=fixture();token=sign_start(plan,challenge,KEY)
    other=issue_challenge(BOOT,1000,lease_us=10000)
    assert challenge['nonce']!=other['nonce']
    with pytest.raises(ValueError,match='challenge mismatch'):gate(other).consume(token,now_us=1001)
    with pytest.raises(ValueError,match='origin mismatch'):
        StartAuthorizationGate(challenge,KEY).consume(token,now_us=1001)


def test_challenge_is_copied_and_wrong_boot_plan_rejected():
    plan,challenge=fixture();verifier=gate(challenge);token=sign_start(plan,challenge,KEY)
    challenge['expires_us']=1001
    assert verifier.consume(token,now_us=1002)['consumed']
    document=plan.to_dict();document['command']['boot_id']='f'*32
    with pytest.raises(ValueError,match='wrong-boot'):
        sign_start(SessionPlan(canonical(document)),challenge,KEY)


def test_even_authenticated_malformed_plan_is_rejected():
    plan,challenge=fixture();token=sign_start(plan,challenge,KEY)
    prefix=token[:len(DOMAIN)+64]
    malformed=b'{}'
    unsigned=prefix+struct.pack('>H',len(malformed))+malformed
    forged=unsigned+hmac.digest(KEY,unsigned,'sha256')
    with pytest.raises(ValueError,match='baseline-bound'):
        gate(challenge).consume(forged,now_us=1001)


@pytest.mark.parametrize('key',[b'',b'short',bytes(32),'not-bytes'])
def test_invalid_keys_rejected(key):
    plan,challenge=fixture()
    with pytest.raises(ValueError):sign_start(plan,challenge,key)


def test_invalid_challenge_and_noncanonical_plan():
    plan,challenge=fixture()
    invalid=copy.deepcopy(challenge);invalid['expires_us']+=30000000
    with pytest.raises(ValueError):gate(invalid)
    with pytest.raises(ValueError,match='Noncanonical'):
        sign_start(SessionPlan(plan.encoded+b' '),challenge,KEY)
