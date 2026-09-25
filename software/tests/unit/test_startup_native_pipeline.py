"""Real signed host bytes through native admission; no device access."""
import base64
import copy
import hashlib
import hmac
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys

import pytest

from rocell.application.first_motion_contract import canonical
from rocell.application.servo_session_plan import SessionPlan
from rocell.application.servo_start_authorization import DOMAIN
from rocell.application.startup_command_contract import freeze_startup_plan, sign_startup
from rocell.application.startup_session_assessment import assess_startup_session
from rocell.application.startup_planned_run import collect_startup_run, replay_startup_run
from rocell.application.startup_prepared_start import send_prepared_startup
from rocell.application.startup_started_run import collect_started_startup, replay_started_startup
from rocell.application.servo_goal_ledger import load_startup_ledger, assess_mixed_goal_scan
from test_servo_goal_ledger import check_two_scan_observation
from rocell.application.servo_transport_snapshot import collect_snapshot, STATUS, RECORD
from test_startup_command_contract import fixture, KEY


def test_real_native_startup_pipeline(tmp_path):
    compiler = shutil.which('clang++')
    if sys.platform != 'win32' or not compiler:
        pytest.skip('Windows crypto and host compiler required')
    root = Path(__file__).resolve().parents[2]
    tools = root / '.firmware-tools'
    reference = tools / 'reference/RoArm-M3_example/RoArm-M3_module.h'
    raw = reference.read_bytes()
    manifest = json.loads((tools / 'reference-build-inputs.json').read_text())
    assert hashlib.sha256(raw).hexdigest() == manifest['files'][str(reference.relative_to(tools))]
    text = raw.decode('utf-8-sig').replace('\r\r\n', '\n').replace('\r\n', '\n')
    bodies = []
    for signature in ('double calculatePosByRad(', 'int RoArmM3_elbowJointCtrlRad('):
        start = text.index(signature)
        bodies.append(text[start:text.index('\n}', start) + 2])
    (tmp_path / 'pinned_elbow_functions.h').write_text('\n'.join(bodies))
    exe = tmp_path / 'startup-pipeline.exe'
    build = subprocess.run([compiler, '-std=c++14', '-Wall', '-Wextra', '-Werror',
        '-I' + str(tmp_path), '-I' + str(tools / 'user/libraries/ArduinoJson/src'),
        str(root / 'firmware/diagnostics/test_startup_native_pipeline.cpp'),
        '-lbcrypt', '-o', str(exe)], capture_output=True, text=True, timeout=60)
    assert build.returncode == 0, build.stderr

    normal, policy, _ = fixture()
    doc = normal.to_dict()
    # DEVICE_CAPTURE exercises native admission, not a claim of actual hardware.
    doc['origin'] = 'DEVICE_CAPTURE'
    doc['command'].update(boot_id='11' * 16, wire_count=2132, desired_count=2132,
        conversion_version='roarm-m3-example20260115-elbow-v1')
    challenge = dict(schema='rocell.start_challenge.v1', boot_id='11' * 16,
        nonce='22' * 32, issued_us=1000, expires_us=10001000)
    plan = freeze_startup_plan(SessionPlan(canonical(doc)), policy)
    valid = sign_startup(plan, challenge, KEY, policy)
    config = dict(schema='rocell.controller_startup.v1', startup_policy=policy,
        controller_policy=dict(schema='rocell.controller_diagnostics.v1', policy_id=policy['policy_id'],
            conversion_version=doc['command']['conversion_version'], start_port=8081,
            challenge_lifetime_us=10000000, elbow_bounds=dict(minimum_rad=1.6, maximum_rad=1.9,
                maximum_speed=40, maximum_acceleration=1), whole_arm_policy=doc['whole_arm_policy']))
    config_path = tmp_path / 'startup-config.json'
    config_path.write_bytes(canonical(config))

    def sign_unchecked(wrapper):
        # Deliberately authenticated invalid plans must still fail native parsing.
        encoded = canonical(wrapper)
        prefix = valid[:len(DOMAIN) + 64]
        unsigned = prefix + struct.pack('>H', len(encoded)) + encoded
        return unsigned + hmac.digest(KEY, unsigned, 'sha256')

    cases = [('success', valid, 1), ('target-mismatch', valid, 2), ('no-motion', valid, 3),
             ('bad-signature', valid[:-1] + bytes([valid[-1] ^ 1]), 0)]
    for field, value in [('wire_count', 2133), ('payload_sha256', '0' * 64),
                         ('boot_id', '33' * 16), ('conversion_version', 'wrong')]:
        changed = json.loads(json.dumps(doc))
        changed['command'][field] = value
        wrapper = json.loads(plan.encoded)
        wrapper['session_plan_base64'] = base64.b64encode(canonical(changed)).decode()
        cases.append((field, sign_unchecked(wrapper), 0))
    wrapper = json.loads(plan.encoded)
    wrapper['startup_policy']['reviewed_mode'] = 1
    cases.append(('wrong-local-policy', sign_unchecked(wrapper), 0))
    for field, value in [('origin', 'SIMULATION'), ('sent_base64', base64.b64encode(
            b'{"T":101,"acc":1,"joint":3,"rad":1.8,"spd":20}').decode())]:
        changed = json.loads(json.dumps(doc))
        changed[field] = value
        wrapper = json.loads(plan.encoded)
        wrapper['session_plan_base64'] = base64.b64encode(canonical(changed)).decode()
        cases.append((field, sign_unchecked(wrapper), 0))
    for name, token, expected in cases:
        path = tmp_path / (name + '.bin')
        path.write_bytes(token)
        run = subprocess.run([str(exe), str(path), str(expected), str(config_path)],
            capture_output=True, text=True, timeout=10)
        assert run.returncode == 0, (name, run.stderr)
        records = [(kind, json.loads(body)) for kind, body in
                   (line.split('\t', 1) for line in run.stdout.splitlines())]
        if expected:
            assert [kind for kind, _ in records] == [
                'startup_auth', 'startup_first', 'startup_second', 'startup_control',
                'receipt', 'converted', 'hook', 'dispatch', 'write'] + ['pair'] * (1 if expected == 2 else 3)
            assert records[0][1]['startup_plan_sha256'] == hashlib.sha256(plan.encoded).hexdigest()
            assert records[5][1]['wire_count'] == records[7][1]['wire_count'] == 2132
            snapshot = dict(status=dict(state='FAULT' if expected == 2 else 'CAPTURED',
                storage_fault=False), records=[dict(kind=kind, record=body) for kind, body in records])
            review = assess_startup_session(snapshot, plan, boot_id='11' * 16, approved_policy=policy)
            assert review['startup_evidence_verified'] and not review['progression_authority']
            assert review['initial_elbow_position'] == 2128 and review['command_delta_counts'] == 4
            status = dict(schema='rocell.diagnostic_transport.v3', instance_id='11' * 16,
                state=snapshot['status']['state'], reason='NONE', records=len(records),
                storage_fault=False, start_supported=True, durable_export_verified=False)
            responses = {STATUS: canonical(status)}
            responses.update({RECORD + str(i): canonical(dict(schema='rocell.diagnostic_record.v2',
                instance_id='11' * 16, index=i, kind=kind, record=body))
                for i, (kind, body) in enumerate(records)})
            calls = []
            def get_bytes(path, **limits):
                calls.append(path)
                assert len(responses[path]) <= limits['maximum_bytes']
                return responses[path]
            with pytest.raises(ValueError): collect_snapshot(get_bytes)
            calls.clear()
            exported = collect_startup_run(tmp_path / name, get_bytes, plan,
                boot_id='11' * 16, approved_policy=policy)
            assert calls == [STATUS, *[RECORD + str(i) for i in range(len(records))], STATUS]
            assert exported['export_verified'] and exported['replay_verified']
            assert exported['outcome']['assessment'] == review
            assert replay_startup_run(tmp_path / name, Path(exported['export_path']).name)['matches']
            if expected == 1:
                partial_status = dict(status, state='FAULT', reason='STARTUP_EVIDENCE_FAILURE', records=3)
                responses[STATUS] = canonical(partial_status)
                partial = collect_startup_run(tmp_path / 'partial-startup', get_bytes, plan,
                    boot_id='11' * 16, approved_policy=policy)
                assert partial['outcome'] == dict(status='INCONCLUSIVE', assessment=None)
                assert partial['export_verified'] and partial['replay_verified']
                responses[STATUS] = canonical(status)
                class SimulatedDelivery:
                    def send(self, sent_plan, sent_challenge, key):
                        assert sent_plan.encoded == plan.encoded and sent_challenge == challenge and key == KEY
                        body = canonical(dict(accepted=True,retry_allowed=False))
                        return dict(schema='rocell.host_startup_delivery.v1',connection_attempted=True,
                            transmission_attempted=True,retry_allowed=False,progression_authority=False,
                            endpoint_verified=False,result='CONTROLLER_REPORTED_ACCEPTANCE',
                            startup_plan_sha256=hashlib.sha256(plan.encoded).hexdigest(),
                            boot_id=challenge['boot_id'],command_id=doc['command']['command_id'],
                            response_body=body.decode(),response_sha256=hashlib.sha256(body).hexdigest())
                linked_root=tmp_path/'linked-native-startup'
                prepared=send_prepared_startup(linked_root,SimulatedDelivery(),plan,challenge,KEY,approved_policy=policy)
                linked=collect_started_startup(linked_root,Path(prepared['export_path']).name,get_bytes)
                replay=replay_started_startup(linked_root,Path(linked['export_path']).name)
                assert replay['outcome']['assessment']['category']=='DIAGNOSTIC_ENDPOINT_CRITERIA_MET'
                assert replay['delivery']['endpoint_verified'] is False and replay['matches']
                linked_id = Path(linked['export_path']).name
                ledger = json.loads(load_startup_ledger(linked_root, linked_id).encoded)
                assert [j['goal'] for j in ledger['joints']] == [0, 0, 0, 2132, 0, 0, 0]
                assert [j['position'] for j in ledger['joints']] == [2128, 2128, 2128, 2132, 2128, 2128, 2128]
                assert [j['commanded'] for j in ledger['joints']] == [False, False, False, True, False, False, False]
                scan = copy.deepcopy(records[2][1])
                scan['scan_id'] = 'continuation-observation-1'
                for index, row in enumerate(scan['reads']):
                    for offset, read in enumerate(row):
                        read[1] = ledger['finished_us'] + 100 + (index * 2 + offset) * 10
                        read[2] = read[1] + 1
                scan['reads'][3][0][6] = (2132).to_bytes(2, 'little').hex()
                scan['reads'][3][1][6] = (2132).to_bytes(2, 'little').hex() + scan['reads'][3][1][6][4:]
                boundary = scan['reads'][-1][1][2] + 1
                def check(observation, at=boundary):
                    return assess_mixed_goal_scan(linked_root, linked_id, observation,
                        scan_id=scan['scan_id'], boundary_us=at)
                observation = check(scan)
                assert observation['status'] == 'OBSERVATION_MATCHES_LEDGER'
                assert not any(observation[k] for k in ('progression_authority',
                    'control_state_verified', 'two_scan_stability_verified', 'physical_accuracy_verified'))
                for fault in ('goal', 'untouched-goal', 'drift', 'moving', 'boot', 'identity', 'old', 'incomplete'):
                    bad_scan = copy.deepcopy(scan)
                    if fault == 'goal': bad_scan['reads'][3][0][6] = '0000'
                    if fault == 'untouched-goal': bad_scan['reads'][0][0][6] = '0100'
                    if fault == 'drift': bad_scan['reads'][0][1][6] = '0009' + bad_scan['reads'][0][1][6][4:]
                    if fault == 'moving':
                        raw = bytearray.fromhex(bad_scan['reads'][3][1][6]); raw[10] = 1
                        bad_scan['reads'][3][1][6] = raw.hex()
                    if fault == 'boot': bad_scan['boot_id'] = '33' * 16
                    if fault == 'identity': bad_scan['scan_id'] = 'other-observation'
                    if fault == 'old': bad_scan['reads'][0][0][1] = ledger['finished_us']
                    if fault == 'incomplete': bad_scan['complete'] = False
                    with pytest.raises(ValueError): check(bad_scan)
                with pytest.raises(ValueError): check(scan, boundary + policy['maximum_age_us'])
                with pytest.raises(ValueError): check(scan, boundary - 2)
                check_two_scan_observation(linked_root, linked_id, scan, records[3][1], policy)
            if expected == 2:
                assert review['category'] == 'SESSION_FAULT'
            elif expected == 3:
                assert review['category'] == 'FRESH_POSITION_NOT_SETTLED_AT_DESIRED_TARGET'
            else:
                assert review['category'] == 'DIAGNOSTIC_ENDPOINT_CRITERIA_MET'
                for fault in ('hash', 'order', 'torque', 'drift', 'stale', 'schedule', 'missing'):
                    bad = copy.deepcopy(snapshot)
                    rows = bad['records']
                    if fault == 'hash': rows[0]['record']['startup_plan_sha256'] = '0' * 64
                    if fault == 'order': rows[1], rows[2] = rows[2], rows[1]
                    if fault == 'torque': rows[3]['record']['reads'][1][2][6] = '00'
                    if fault == 'drift':
                        raw = rows[2]['record']['reads'][3][1][6]
                        rows[2]['record']['reads'][3][1][6] = '5308' + raw[4:]
                    if fault == 'stale':
                        # Corrupt acquisition time; stale/invalid evidence cannot pass.
                        rows[2]['record']['reads'][0][0][1] = 0
                    if fault == 'schedule': rows[5]['record']['sample_count'] = 2
                    if fault == 'missing': rows.pop(3)
                    with pytest.raises(ValueError):
                        assess_startup_session(bad, plan, boot_id='11' * 16, approved_policy=policy)
        else:
            assert not records
