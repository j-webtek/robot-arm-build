"""Real host HMAC checked by native Windows crypto; no controller access."""
import hashlib
import copy
import hmac
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import pytest
from test_arrival_wizard_service import make_service, _run
from test_movement_campaign_ui import render
from rocell.application.first_motion_contract import canonical
from rocell.application.servo_start_authorization import DOMAIN
from rocell.application.hold_command_contract import freeze_hold_plan, sign_hold
from rocell.application.hold_prepared_start import send_prepared_hold
from rocell.application.hold_started_review import review_prepared_hold_simulation, replay_started_hold_simulation
from rocell.application.hold_collected_review import collect_prepared_hold_simulation, replay_collected_hold_simulation
from rocell.application.servo_transport_snapshot import STATUS, RECORD
from rocell.application.hold_bound_replay import (
    assess_bound_simulation, export_bound_simulation, replay_bound_simulation_export,
)


def test_native_hold_authenticated_plan(tmp_path, make_service, monkeypatch):
    compiler = shutil.which('clang++')
    if sys.platform != 'win32' or not compiler:
        pytest.skip('Windows native crypto/compiler required')
    root = Path(__file__).resolve().parents[2]
    exe = tmp_path / 'hold-admission.exe'
    built = subprocess.run([compiler, '-std=c++17',
        '-I' + str(root / '.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root / 'firmware/diagnostics/test_hold_plan_admission.cpp'), '-lbcrypt', '-o', str(exe)],
        capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stderr
    policy = dict(acceleration=1, age_us=250000, baseline_gap_us=100000,
        deadline_us=2000000, drift=2, joints=[[p-8,p+8] for p in (2048,2390,1727,2723,2041,2042,2051)],
        maximum_gap_us=500000, pair_us=10000, permit_explicit_enable=0, scan_us=100000,
        schema='rocell.hold_policy.v1', servo_id=14, settle_us=100000, speed=20)
    plan = dict(boot_id='11'*16, command_id='reviewed-hold', origin='DEVICE_CAPTURE',
        policy_sha256=hashlib.sha256(canonical(policy)).hexdigest(), schema='rocell.hold_plan.v1')
    valid = canonical(plan)
    frozen = freeze_hold_plan(policy, boot_id=plan['boot_id'], command_id=plan['command_id'])
    assert frozen.encoded == valid
    for index, (payload, corrupt, expected) in enumerate([
        (valid, False, True), (valid, True, False),
        (canonical(dict(plan, command_id='another')), False, False),
        (canonical(dict(plan, policy_sha256='00'*32)), False, False),
        (canonical(dict(plan, origin='SIMULATION')), False, False),
        (json.dumps(plan).encode(), False, False),
    ]):
        body = DOMAIN + bytes.fromhex('11'*16) + bytes.fromhex('22'*32) + struct.pack('>QQH',1000,10001000,len(payload)) + payload
        signature = hmac.digest(b'k'*32, body, 'sha256')
        if expected:
            signed = sign_hold(frozen, dict(schema='rocell.start_challenge.v1',
                boot_id='11'*16, nonce='22'*32, issued_us=1000, expires_us=10001000),
                b'k'*32, approved_policy=policy)
            assert signed == body + signature
        if corrupt:
            signature = bytes([signature[0]^1]) + signature[1:]
        # Test-only binary fixture in pytest's private temporary directory.
        path = tmp_path / f'token-{index}.bin'
        path.write_bytes(body + signature)
        result = subprocess.run([str(exe), str(path), '1' if expected else '0'], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, result.stderr
        if expected:
            records = [json.loads(line) for line in result.stdout.splitlines()]
            assert len(records) == 8
            for record in records:
                assert record['plan_sha256'] == hashlib.sha256(valid).hexdigest()
                assert record['policy_sha256'] == plan['policy_sha256']
                assert record['boot_id'] == plan['boot_id']
                assert record['command_id'] == plan['command_id']
            assert records[0]['schema'] == 'rocell.hold_authorization.v1'
            assert records[0]['authentication_verified'] is True
            assert records[0]['policy'] == policy
            assert records[-1]['schema'] == 'rocell.hold_terminal.v1'
            assert records[-1]['state'] == 'CAPTURED'
            assessed = assess_bound_simulation(records, expected_plan=plan, expected_policy=policy)
            assert assessed['category'] == 'SIMULATED_HOLD_VERIFIED'
            exported = export_bound_simulation(tmp_path / 'bound-exports', records,
                                               expected_plan=plan, expected_policy=policy)
            assert replay_bound_simulation_export(exported['path']) == assessed
            endpoint_path = Path(exported['path']) / 'attachment-hold-endpoints.json'
            endpoint_report = json.loads(endpoint_path.read_bytes())
            assert endpoint_report['schema'] == 'rocell.bound_hold_endpoint_review.v1'
            assert endpoint_report['origin'] == 'SIMULATION'
            assert endpoint_report['endpoint']['encoded_command_target'] == assessed['target_count']
            assert endpoint_report['endpoint']['settled_error_counts'] == 0
            assert endpoint_report['progression_authority'] is False
            class AcceptedSender:
                calls = 0
                def send(self, *args):
                    self.calls += 1
                    body = canonical(dict(accepted=True, retry_allowed=False))
                    return dict(schema='rocell.host_hold_delivery.v1', connection_attempted=True,
                        transmission_attempted=True, retry_allowed=False, progression_authority=False,
                        endpoint_verified=False, result='CONTROLLER_REPORTED_ACCEPTANCE',
                        hold_plan_sha256=hashlib.sha256(valid).hexdigest(), policy_sha256=plan['policy_sha256'],
                        boot_id=plan['boot_id'], command_id=plan['command_id'],
                        response_body=body.decode(), response_sha256=hashlib.sha256(body).hexdigest())
            sender = AcceptedSender()
            service, runner, _ = make_service(mode='physical')
            linked_root = service.export_directory
            challenge = dict(schema='rocell.start_challenge.v1', boot_id='11'*16,
                             nonce='22'*32, issued_us=1000, expires_us=10001000)
            prepared = send_prepared_hold(linked_root, sender, frozen, challenge, b'k'*32,
                                         approved_policy=policy)
            prepared_id = Path(prepared['export_path']).name
            linked = review_prepared_hold_simulation(linked_root, prepared_id, records)
            reviewed = replay_started_hold_simulation(linked_root, Path(linked['path']).name)
            assert reviewed['assessment']['category'] == 'SIMULATED_HOLD_VERIFIED'
            assert reviewed['delivery']['endpoint_verified'] is False and sender.calls == 1
            calls = []
            status = dict(schema='rocell.hold_transport.v1', instance_id=plan['boot_id'],
                state='CAPTURED', reason='ELBOW_HOLD_CAPTURED', records=8, record_bytes=4096,
                storage_fault=False, durable_export_verified=False)
            kinds = {'rocell.hold_authorization.v1':'hold_auth', 'rocell.hold_snapshot.v1':'hold_scan',
                     'rocell.hold_action.v1':'hold_action', 'rocell.hold_terminal.v1':'hold_terminal'}
            def get(path, **kwargs):
                calls.append(path)
                if path == STATUS:
                    return canonical(status)
                index = int(path.removeprefix(RECORD))
                return canonical(dict(schema='rocell.hold_record.v1', instance_id=plan['boot_id'],
                    index=index, kind=kinds[records[index]['schema']], record=records[index]))
            collected = collect_prepared_hold_simulation(linked_root, prepared_id, get)
            assert len(calls) == 10 and sender.calls == 1
            assert collected['assessment']['category'] == 'SIMULATED_HOLD_VERIFIED'
            assert replay_collected_hold_simulation(linked_root, Path(collected['export_path']).name)['matches']
            # Exercise the real observation collector with synthetic HTTP bytes.
            # This verifies software plumbing, not a live hardware trial.
            from rocell.application.hold_observed_review import (
                collect_prepared_hold_observation, replay_hold_observation)
            from rocell.application.hold_transport_snapshot import HoldHTTPReader
            with monkeypatch.context() as patch:
                patch.setattr(HoldHTTPReader, '_get', lambda self, path, **kw: get(path, **kw))
                calls.clear()
                observed = collect_prepared_hold_observation(linked_root, prepared_id,
                                                            address='192.168.0.225')
                assert len(calls) == 10 and sender.calls == 1
                assert observed['assessment']['category'] == 'CONTROLLER_REPORTED_HOLD_VERIFIED'
                assert observed['assessment']['origin'] == 'HOST_HTTP_OBSERVATION'
                assert observed['assessment']['provenance_verified'] is False
                assert observed['assessment']['physical_tip_accuracy_verified'] is False
                assert observed['assessment']['endpoint']['settled_error_counts'] == 0
                patch.setattr(HoldHTTPReader, '_get', lambda *a, **kw: pytest.fail('Replay accessed hardware'))
                assert replay_hold_observation(linked_root, Path(observed['export_path']).name)['matches']
                from rocell.application.held_pair_preparation import prepare_held_pair, replay_held_pair_preparation
                paired = prepare_held_pair(linked_root, Path(observed['export_path']).name,
                    forward_command_id='pair-forward', return_command_id='pair-return')
                prepared_pair = paired['preparation']
                assert paired['replay_verified'] and not paired['progression_authority']
                assert prepared_pair['historical_anchor'] == 2723
                assert prepared_pair['illustrative_targets'] == [2729,2723]
                assert prepared_pair['pair_plan']['hold_plan_sha256'] == hashlib.sha256(frozen.encoded).hexdigest()
                assert prepared_pair['pair_plan']['boot_id'] == plan['boot_id']
                assert replay_held_pair_preparation(linked_root, Path(paired['export_path']).name)['preparation'] == prepared_pair
                from rocell.application.held_pair_prepared_authorization import authorize_prepared_held_pair
                from rocell.application.physical_onboarding_durability import PhysicalOnboardingDurabilityError
                pair_challenge=dict(schema='rocell.start_challenge.v1',boot_id=plan['boot_id'],
                    nonce='66'*32,issued_us=1000,expires_us=10001000)
                authorization=authorize_prepared_held_pair(linked_root,Path(paired['export_path']).name,
                                                           pair_challenge,b'k'*32)
                assert authorization.session_sha256 == prepared_pair['pair_plan_sha256']
                assert 'token=' not in repr(authorization)
                assert authorization.token.endswith(hmac.digest(b'k'*32,authorization.token[:-32],'sha256'))
                claim=json.loads((linked_root/authorization.claim_file).read_bytes())
                assert claim['state']=='CONSUMED_BEFORE_TOKEN_RELEASE'
                from rocell.application.held_pair_prepared_authorization import replay_initial_pair_authorization
                replayed_auth = replay_initial_pair_authorization(linked_root, authorization.context_export_id)
                assert replayed_auth['preparation'] == prepared_pair
                assert replayed_auth['replay_verified'] and not replayed_auth['delivery_verified']
                with monkeypatch.context() as changed_claim:
                    from rocell.application import held_pair_prepared_authorization as auth_module
                    changed_claim.setattr(auth_module, 'read_bounded_regular_file', lambda *a, **kw: b'{}')
                    with pytest.raises(ValueError, match='nonce claim'):
                        replay_initial_pair_authorization(linked_root, authorization.context_export_id)
                with pytest.raises(PhysicalOnboardingDurabilityError):
                    authorize_prepared_held_pair(linked_root,Path(paired['export_path']).name,pair_challenge,b'k'*32)
                with pytest.raises(ValueError):
                    authorize_prepared_held_pair(linked_root,Path(paired['export_path']).name,
                                                dict(pair_challenge,boot_id='33'*16),b'k'*32)
                context_path=linked_root/authorization.context_export_id/'attachment-held-pair-signing-context.json'
                assert authorization.token not in context_path.read_bytes()
                from rocell.application import held_pair_prepared_authorization as pair_auth
                def claim_path(challenge):
                    identity=canonical(dict(boot_id=challenge['boot_id'],nonce=challenge['nonce']))
                    return linked_root/('diagnostic-start-'+hashlib.sha256(identity).hexdigest()+'.json')
                def fail_storage(*args,**kwargs):
                    raise OSError('synthetic storage failure')
                before_export=dict(pair_challenge,nonce='77'*32)
                with monkeypatch.context() as failures:
                    failures.setattr(pair_auth.WizardDiagnosticExporter,'export',fail_storage)
                    with pytest.raises(OSError):
                        authorize_prepared_held_pair(linked_root,Path(paired['export_path']).name,before_export,b'k'*32)
                assert not claim_path(before_export).exists()
                after_claim=dict(pair_challenge,nonce='88'*32)
                with monkeypatch.context() as failures:
                    failures.setattr(pair_auth,'read_bounded_regular_file',fail_storage)
                    with pytest.raises(OSError):
                        authorize_prepared_held_pair(linked_root,Path(paired['export_path']).name,after_claim,b'k'*32)
                assert claim_path(after_claim).exists()
                with pytest.raises(PhysicalOnboardingDurabilityError):
                    authorize_prepared_held_pair(linked_root,Path(paired['export_path']).name,after_claim,b'k'*32)
                # The hold workflow already consumed nonce 22: pair cannot reuse it.
                collision=dict(pair_challenge,nonce='22'*32)
                retained_claim=claim_path(collision).read_bytes()
                with pytest.raises(PhysicalOnboardingDurabilityError):
                    authorize_prepared_held_pair(linked_root,Path(paired['export_path']).name,collision,b'k'*32)
                assert claim_path(collision).read_bytes()==retained_claim
                from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter
                pair_exporter = WizardDiagnosticExporter(linked_root)
                pair_exporter.prepare(create=True)
                for mutate in (
                    lambda r: r.update(hold_observation_sha256='0'*64),
                    lambda r: r.update(historical_anchor=2724),
                    lambda r: r.update(progression_authority=True),
                    lambda r: r.update(fresh_same_boot_handoff_required=False),
                    lambda r: r['pair_plan'].update(boot_id='33'*16),
                ):
                    altered = copy.deepcopy(prepared_pair); mutate(altered)
                    forged = pair_exporter.export({'mode':'test'},[],
                        attachments={'held-pair-preparation.json':canonical(altered)})
                    with pytest.raises(ValueError):
                        replay_held_pair_preparation(linked_root,Path(forged['path']).name)
                with pytest.raises(ValueError):
                    prepare_held_pair(linked_root, Path(observed['export_path']).name,
                        forward_command_id='same', return_command_id='same')
                observed_operation = _run(service, 'review_observed_hold',
                    {'export_id': Path(observed['export_path']).name})
                assert observed_operation['status'] == 'SUCCEEDED', observed_operation
                observed_page = render(observed_operation)
                assert 'HOST_HTTP_OBSERVATION' in observed_page
                assert 'CONTROLLER_REPORTED_HOLD_VERIFIED' in observed_page
                assert '2723' in observed_page and 'NOT QUALIFIED' in observed_page
                assert 'does not authenticate' in observed_page
                assert 'ELBOW_HOLD_CAPTURED' in observed_page
                assert not runner.calls and service.view()['arm']['status'] == 'NOT_CONNECTED'
                with pytest.raises(Exception):
                    collect_prepared_hold_observation(linked_root, 'wizard-missing',
                                                      address='192.168.0.225')
                patch.setattr(HoldHTTPReader, '_get', lambda self, path, **kw: get(path, **kw))
                original_hash = records[2]['plan_sha256']
                records[2]['plan_sha256'] = '00' * 32
                try:
                    invalid = collect_prepared_hold_observation(linked_root, prepared_id,
                                                               address='192.168.0.225')
                    assert invalid['assessment']['category'] == 'INCONCLUSIVE'
                    assert invalid['assessment']['reason'] == 'INVALID_BOUND_HOLD_EVIDENCE'
                finally:
                    records[2]['plan_sha256'] = original_hash
            operation = _run(service, 'review_collected_hold',
                             {'export_id': Path(collected['export_path']).name})
            assert operation['status'] == 'SUCCEEDED', operation
            page = render(operation)
            assert 'SIMULATION' in page and 'NOT QUALIFIED' in page
            assert 'encoded command target' in page and '2723' in page
            assert 'Not independently measured' in page and 'Not measured' in page
            assert not runner.calls and service.view()['arm']['status'] == 'NOT_CONNECTED'
            assert sender.calls == 1
            calls.clear()
            def interrupted(path, **kwargs):
                if len(calls) == 3:
                    calls.append(path)
                    raise OSError('simulated interruption')
                return get(path, **kwargs)
            failed_capture = collect_prepared_hold_simulation(linked_root, prepared_id, interrupted)
            assert len(calls) == 4 and sender.calls == 1
            assert failed_capture['assessment']['category'] == 'INCONCLUSIVE'
            with monkeypatch.context() as patch:
                calls.clear()
                patch.setattr(HoldHTTPReader, '_get', lambda self, path, **kw: interrupted(path, **kw))
                observed_failure = collect_prepared_hold_observation(linked_root, prepared_id,
                                                                    address='192.168.0.225')
                assert len(calls) == 4 and sender.calls == 1
                assert observed_failure['assessment']['category'] == 'INCONCLUSIVE'
                assert observed_failure['replay_verified'] is True
                failure_replay = replay_hold_observation(linked_root, Path(observed_failure['export_path']).name)
                assert failure_replay['stable_status_observed'] is False
                failed_observation = _run(service, 'review_observed_hold',
                    {'export_id': Path(observed_failure['export_path']).name})
                assert failed_observation['status'] == 'SUCCEEDED', failed_observation
                assert 'Inconclusive' in render(failed_observation)
                assert not runner.calls and sender.calls == 1
            assert replay_collected_hold_simulation(linked_root,
                Path(failed_capture['export_path']).name)['matches']
            failed_operation = _run(service, 'review_collected_hold',
                                   {'export_id': Path(failed_capture['export_path']).name})
            assert failed_operation['status'] == 'SUCCEEDED', failed_operation
            assert 'Inconclusive' in render(failed_operation)
            assert not runner.calls and sender.calls == 1
            missing = _run(service, 'review_collected_hold', {'export_id': 'wizard-missing'})
            assert missing['status'] != 'SUCCEEDED' and not runner.calls
            outside = copy.deepcopy(records)
            outside[0]['received_us'] = 999
            with pytest.raises(ValueError, match='challenge window'):
                review_prepared_hold_simulation(linked_root, prepared_id, outside)
            (linked_root / prepared['claim_file']).unlink()
            with pytest.raises(Exception):
                replay_started_hold_simulation(linked_root, Path(linked['path']).name)
            assert sender.calls == 1
            for mutate in (
                lambda r: r[2].update(plan_sha256='00'*32),
                lambda r: r[0].update(authentication_verified=False),
                lambda r: r[0]['policy'].update(speed=21),
                lambda r: r[-1].update(policy_sha256='00'*32),
                lambda r: r.pop(),
                lambda r: r[0].update(received_us=10000000),
            ):
                damaged = copy.deepcopy(records)
                mutate(damaged)
                assert assess_bound_simulation(damaged, expected_plan=plan,
                    expected_policy=policy)['category'] == 'INCONCLUSIVE'
            # Consistent hashes do not excuse policy violations. Rebind test data
            # to several policies and require assessment of their actual limits.
            for edit, expected_category in (
                ({'settle_us': 50000}, 'SIMULATED_HOLD_VERIFIED'),
                ({'settle_us': 200000}, 'INCONCLUSIVE'),
                ({'speed': 21}, 'INCONCLUSIVE'),
                ({'joints': [[0, 1]] * 7}, 'INCONCLUSIVE'),
            ):
                changed_policy = dict(policy, **edit)
                changed_plan = dict(plan, policy_sha256=hashlib.sha256(canonical(changed_policy)).hexdigest())
                changed_records = copy.deepcopy(records)
                for record in changed_records:
                    record['policy_sha256'] = changed_plan['policy_sha256']
                    record['plan_sha256'] = hashlib.sha256(canonical(changed_plan)).hexdigest()
                changed_records[0]['policy'] = changed_policy
                assert assess_bound_simulation(changed_records, expected_plan=changed_plan,
                    expected_policy=changed_policy)['category'] == expected_category
