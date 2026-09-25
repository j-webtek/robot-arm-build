"""Cross-language hashes of actual native publisher output; synthetic bus only."""
import json
import hashlib
import copy
from pathlib import Path
import shutil
import subprocess
import sys
import pytest
from rocell.application.held_evidence_digest import held_evidence_digest
from rocell.application.first_motion_contract import canonical
from rocell.application.held_leg_raw_export import export_raw_simulated_held_leg, replay_raw_simulated_held_leg
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter


@pytest.mark.parametrize('rows', [[], [('bad', b'{}')], [('held_leg_scan', '{}')],
    [('held_leg_scan', b'')], [('held_leg_scan', b'x'*4096)],
    [('held_leg_scan', b'a\0b')], [('held_leg_scan', b'{}')]*35])
def test_digest_rejects_invalid(rows):
    with pytest.raises(ValueError):
        held_evidence_digest(rows)


def test_native_and_host_digest_agree(tmp_path):
    compiler = shutil.which('clang++')
    if sys.platform != 'win32' or not compiler:
        pytest.skip('Windows crypto and native compiler required')
    root = Path(__file__).resolve().parents[2]
    def build(name, crypto=False):
        exe = tmp_path / (name+'.exe')
        args = [compiler, '-std=c++17',
                '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
                str(root/'firmware/diagnostics'/('test_'+name+'.cpp')), '-o', str(exe)]
        if crypto:
            args.append('-lbcrypt')
        result = subprocess.run(args, capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stderr
        return exe
    publisher = build('held_leg_evidence_publisher')
    native = build('held_evidence_digest', True)
    result = subprocess.run([str(publisher)], capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr
    sessions, rows = [], []
    kinds = {'rocell.held_leg_snapshot.v1': 'held_leg_scan',
             'rocell.hold_action.v1': 'held_leg_action',
             'rocell.held_leg_terminal.v1': 'held_leg_end'}
    for raw in result.stdout.splitlines():
        kind = kinds[json.loads(raw)['schema']]
        rows.append((kind, raw))
        if kind == 'held_leg_end':
            sessions.append(rows)
            rows = []
    assert not rows and len(sessions) == 3
    policy = json.loads((root/'docs/hold-r7-supported-pose-draft.json').read_bytes())['hold_policy']
    policy['joints'] = [[p-16,p+16] for p in (2047,2395,1722,2902,2035,2045,2047)]
    plan = dict(schema='rocell.held_leg_plan.v1', boot_id='test-boot', command_id='test-leg',
                target_count=2908, tolerance_counts=2,
                policy_sha256=hashlib.sha256(canonical(policy)).hexdigest())
    for i, rows in enumerate(sessions):
        source = tmp_path / f'records-{i}.txt'
        source.write_bytes(b''.join(k.encode()+b'\t'+raw+b'\n' for k, raw in rows))
        result = subprocess.run([str(native), str(source)], capture_output=True,
                                text=True, timeout=20)
        assert result.returncode == 0, result.stderr
        expected = held_evidence_digest(rows)
        assert result.stdout.strip() == expected
        assert held_evidence_digest(rows[::-1]) != expected
        assert held_evidence_digest(rows[:-1]) != expected
        changed = [(rows[0][0], rows[0][1]+b' ')] + rows[1:]
        assert held_evidence_digest(changed) != expected
        saved = export_raw_simulated_held_leg(tmp_path/'exports', rows, plan=plan, policy=policy)
        assert saved['evidence_sha256'] == expected and saved['replay_verified']
        assert saved['origin'] == 'SIMULATION' and not saved['progression_authority']
        assert saved['assessment']['category'] == ['VERIFIED_ARRIVAL', 'VERIFIED_NON_ARRIVAL', 'INCONCLUSIVE'][i]
        assert replay_raw_simulated_held_leg(tmp_path/'exports', Path(saved['export_path']).name)['export_sha256'] == saved['export_sha256']
        # Exact raw whitespace survives export instead of being reserialized.
        changed_saved = export_raw_simulated_held_leg(tmp_path/'exports', changed, plan=plan, policy=policy)
        assert changed_saved['evidence_sha256'] != expected
        assert changed_saved['assessment'] == saved['assessment']
        attachment = Path(saved['export_path'])/'attachment-raw-held-leg.json'
        if i == 0:
            original = json.loads(attachment.read_bytes())
            exporter = WizardDiagnosticExporter(tmp_path/'exports')
            exporter.prepare(create=True)
            mutations = [lambda b: b.update(origin='DEVICE_CAPTURE'),
                         lambda b: b.update(progression_authority=True),
                         lambda b: b.update(evidence_sha256='0'*64),
                         lambda b: b['assessment'].update(category='VERIFIED_NON_ARRIVAL'),
                         lambda b: b['records'][0].update(raw_base64='%%%'),
                         lambda b: b['records'][0].update(kind='held_leg_action')]
            for mutate in mutations:
                altered = copy.deepcopy(original)
                mutate(altered)
                forged = exporter.export({'mode': 'test'}, [],
                    attachments={'raw-held-leg.json': canonical(altered)})
                # A valid manifest cannot bless mismatched semantics or origin.
                with pytest.raises(ValueError):
                    replay_raw_simulated_held_leg(tmp_path/'exports', Path(forged['path']).name)
        attachment.write_bytes(attachment.read_bytes()+b' ')
        with pytest.raises(ValueError):
            replay_raw_simulated_held_leg(tmp_path/'exports', Path(saved['export_path']).name)
