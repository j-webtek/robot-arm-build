"""Native publisher records parsed independently in Python; no hardware."""
import json
import copy
from pathlib import Path
import shutil
import subprocess
import pytest
from rocell.application.hold_record_replay import (
    assess_simulated_hold, export_simulated_hold, replay_simulated_hold_export,
    review_simulated_hold_endpoints,
)
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter
from rocell.application.first_motion_contract import canonical


def test_native_hold_records_and_publication_failures(tmp_path):
    compiler = shutil.which('clang++')
    if not compiler:
        pytest.skip('Host compiler required')
    root = Path(__file__).resolve().parents[2]
    exe = tmp_path / 'hold-publisher.exe'
    result = subprocess.run([
        compiler, '-std=c++17', '-I', str(root / '.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root / 'firmware/diagnostics/test_hold_evidence_publisher.cpp'), '-o', str(exe),
    ], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    rows = [json.loads(line) for line in result.stdout.splitlines()]
    powered=subprocess.run([str(exe),'--already-enabled'],capture_output=True,text=True,timeout=10,check=True)
    powered_rows=[json.loads(line) for line in powered.stdout.splitlines()]
    endpoint=review_simulated_hold_endpoints(powered_rows,allow_enable=True)['endpoint']
    assert endpoint['previous_goal']==2724
    assert endpoint['requested_hold_target']==endpoint['encoded_command_target']==2723
    assert endpoint['first_goal_readback']==endpoint['settled_goal_readback']==2723
    assert endpoint['torque_before']==endpoint['torque_settled']==1
    assert endpoint['explicit_enable_used'] is False
    saved=export_simulated_hold(tmp_path/'powered-exports',powered_rows,allow_enable=True)
    assert replay_simulated_hold_export(saved['path'])['category']=='SIMULATED_HOLD_VERIFIED'
    for scenario, expected in (('--fast-powered', 'SIMULATED_HOLD_VERIFIED'),
                               ('--fast-busy', 'INCONCLUSIVE')):
        fast = subprocess.run([str(exe), scenario], capture_output=True,
                              text=True, timeout=10, check=True)
        fast_rows = [json.loads(line) for line in fast.stdout.splitlines()]
        actions = [r for r in fast_rows if r['schema'] == 'rocell.hold_action.v1']
        assert len(actions) == 1
        assessment = assess_simulated_hold(fast_rows, allow_enable=True)
        assert assessment['category'] == expected
        exported = export_simulated_hold(tmp_path / scenario[2:], fast_rows, allow_enable=True)
        assert replay_simulated_hold_export(exported['path']) == assessment
    assert len(rows) == 19
    for row in rows:
        assert row['boot_id'] == 'test-boot' and row['command_id'] == 'test-hold'
    for records in (rows[:7], rows[7:17]):
        scans = [r for r in records if r['schema'] == 'rocell.hold_snapshot.v1']
        actions = [r for r in records if r['schema'] == 'rocell.hold_action.v1']
        assert [r['snapshot_index'] for r in scans] == list(range(len(scans)))
        assert [r['action_index'] for r in actions] == list(range(len(actions)))
        for scan in scans:
            assert scan['complete'] and len(scan['reads']) == 28
            for servo, address, width, read in scan['reads']:
                assert 11 <= servo <= 17 and address in (42, 56, 33, 40)
                seq, start, end, returned, error, success, raw = read
                assert start <= end and returned == width and error == 0 and success
                assert len(bytes.fromhex(raw)) == width
        assert actions[0]['payload_hex'] == '01a30a00001400'
        assert all(a['dispatch_status'] == 'SUCCEEDED' for a in actions)
        assert scans[0]['reads'][0][3][-1] == '0000'
        assert scans[-1]['reads'][6][3][-1] == 'a30a'
    failed = rows[-2]
    assert failed['complete'] is False
    assert failed['reads'][-1][3][-2:] == [False, None]
    for records, enable in ((rows[:7], False), (rows[7:17], True), (rows[17:], False)):
        assessment = assess_simulated_hold(records, allow_enable=enable)
        assert assessment['category'] == ('INCONCLUSIVE' if len(records) == 2 else 'SIMULATED_HOLD_VERIFIED')
        if len(records) != 2:
            endpoint = review_simulated_hold_endpoints(records, allow_enable=enable)['endpoint']
            assert endpoint['requested_hold_target'] == endpoint['encoded_command_target'] == 2723
            assert endpoint['previous_goal'] == 0
            assert endpoint['first_goal_readback'] == endpoint['settled_goal_readback'] == 2723
            assert endpoint['start_position'] == endpoint['settled_position'] == 2723
            assert endpoint['settled_error_counts'] == endpoint['position_change_counts'] == 0
            assert endpoint['torque_before'] == 0 and endpoint['torque_settled'] == 1
            assert endpoint['explicit_enable_used'] is enable
            assert endpoint['command_duration_us'] >= 0
            assert endpoint['final_observation_after_command_us'] >= 100000
            assert [j['servo_id'] for j in endpoint['other_joint_changes']] == [11, 12, 13, 15, 16, 17]
            assert all(j['position_change_counts'] == 0 and not j['goal_changed'] and not j['torque_changed']
                       for j in endpoint['other_joint_changes'])
            assert endpoint['wire_observation_verified'] is False
            assert endpoint['physical_tip_accuracy_verified'] is False
        else:
            assert 'endpoint' not in assessment
        exported = export_simulated_hold(tmp_path / 'exports', records, allow_enable=enable)
        assert replay_simulated_hold_export(exported['path']) == assessment
        # Old exports have no endpoint attachment and must still replay.
        legacy_exporter = WizardDiagnosticExporter(tmp_path / 'legacy-exports')
        legacy_exporter.prepare(create=True)
        legacy = legacy_exporter.export({'mode': 'simulated-hold-review'}, [], attachments={
            'hold-records.json': canonical(records), 'hold-assessment.json': canonical(assessment),
            'hold-replay-policy.json': canonical(dict(origin='SIMULATION', allow_enable=enable,
                                                     policy='hold-model-default-v1'))})
        assert replay_simulated_hold_export(legacy['path']) == assessment
    assert assess_simulated_hold(rows[7:17])['category'] == 'INCONCLUSIVE'
    # A within-policy measured offset must not be rounded away in review.
    shifted = copy.deepcopy(rows[:7])
    final_scan = next(r for r in reversed(shifted) if r['schema'] == 'rocell.hold_snapshot.v1')
    raw = final_scan['reads'][7][3][6]
    final_scan['reads'][7][3][6] = 'a40a' + raw[4:]
    shifted_review = review_simulated_hold_endpoints(shifted)
    assert shifted_review['category'] == 'SIMULATED_HOLD_VERIFIED'
    assert shifted_review['endpoint']['settled_position'] == 2724
    assert shifted_review['endpoint']['settled_error_counts'] == 1
    assert shifted_review['endpoint']['position_change_counts'] == 1
    for mutate in (
        lambda r: r.pop(),
        lambda r: r[0].update(boot_id='wrong-boot'),
        lambda r: next(x for x in r if x['schema']=='rocell.hold_action.v1').update(payload_hex='01a40a00001400'),
        lambda r: next(x for x in r if x['schema']=='rocell.hold_action.v1').update(library_return=0),
        lambda r: r[-2]['reads'][6][3].__setitem__(6, '0000'),
        lambda r: r[-1].update(snapshot_count=1),
        lambda r: r[-1].update(state='FAULT'),
        lambda r: r[0]['reads'][0][3].__setitem__(5, False),
        lambda r: r[0].update(snapshot_index=1),
    ):
        damaged = copy.deepcopy(rows[:7])
        mutate(damaged)
        assert assess_simulated_hold(damaged)['category'] == 'INCONCLUSIVE'
