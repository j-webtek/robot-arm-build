"""Integrated offline provisioning: real LittleFS/parser/DPAPI, fake controller."""
import json
from pathlib import Path

import pytest
from test_diagnostic_provisioning_image import library, image
from test_startup_provisioning_image import validator
from test_hold_provisioning_image import hold_validator
from test_held_pair_settings import pair_validator
from rocell.application import hold_provisioning_execution as hold_core
from rocell.application import pair_settings_provisioning as pair_core
from rocell.application.hold_provisioning_run import run_hold_provisioning, run_hold_policy_replacement
from rocell.application import startup_provisioning_execution as core
from rocell.application import startup_provisioning_run as run
from rocell.application.diagnostic_provisioning_image import stage_startup_image, stage_hold_image
from rocell.application.first_motion_contract import canonical
from rocell.providers.windows.diagnostic_image_store import save_image, load_image


@pytest.mark.parametrize('fault', [None, 'storage', 'write', 'result-export'])
@pytest.mark.parametrize('profile', ['startup', 'hold', 'hold-replacement', 'pair-settings'])
@pytest.mark.parametrize('startup_authorized', [False, True])
def test_integrated_offline_run(tmp_path, monkeypatch, library, validator, hold_validator, fault, profile, startup_authorized, request):
    hold = profile != 'startup'
    prefix = 'hold-r7-supported-replacement' if profile == 'hold-replacement' else 'hold-r7' if hold else 'startup-r6'
    selected_core = hold_core if hold else core
    selected_run = run_hold_policy_replacement if profile == 'hold-replacement' else run_hold_provisioning if hold else run.run_provisioning
    selected_stage = stage_hold_image if hold else stage_startup_image
    validator = hold_validator if hold else validator
    source = image(library)
    policy = canonical(json.loads((Path(__file__).resolve().parents[2] /
        ('docs/hold-r7-policy-draft.json' if hold else 'docs/startup-r6-policy-draft.json')).read_bytes()))
    key = b'Q' * 32  # Synthetic only; never used on a controller.
    candidate, report = selected_stage(source, core.digest(source), policy, key,
        littlefs=library, validate_policy=validator)
    previous_policy = policy
    if profile == 'hold-replacement':
        from rocell.application.diagnostic_provisioning_image import replace_hold_policy_image
        source = candidate
        policy = canonical(json.loads((Path(__file__).resolve().parents[2] /
            'docs/hold-r7-supported-pose-draft.json').read_bytes()))
        candidate, report = replace_hold_policy_image(source, core.digest(source), previous_policy,
            policy, littlefs=library, validate_policy=validator)
    if profile == 'pair-settings':
        from rocell.application.diagnostic_provisioning_image import stage_pair_settings_image
        from rocell.application.held_pair_settings import encode_pair_settings
        source=candidate
        settings=encode_pair_settings(forward_command_id='forward',return_command_id='return')
        settings_validator=request.getfixturevalue('pair_validator')
        candidate,report=stage_pair_settings_image(source,core.digest(source),settings,policy,
            littlefs=library,validate_settings=settings_validator,validate_hold_policy=validator)
        prefix='pair-r10-settings'
        selected_core=pair_core
        selected_run=pair_core.run_pair_settings_provisioning
    memory = bytearray(core.FLASH_SIZE)
    memory[core.FS_START:core.FS_END] = source
    monkeypatch.setattr(selected_core, 'APP_SHA256', core.digest(memory[core.APP_START:core.APP_START+selected_core.APP_SIZE]))
    monkeypatch.setattr(core, 'PARTITION_SHA256', core.digest(memory[0x8000:0x8c00]))
    private = tmp_path / 'private'
    private.mkdir()

    class Device:
        writes = starts = reads = 0
        closed = False
        def identity(self):
            assert (private / (prefix+'-provisioning-events.jsonl')).exists()
            return dict(mac=core.MAC, flash_id=0x164020, secure_boot=False,
                flash_encryption=False, secure_download_mode=False)
        def read_flash(self, offset, length):
            self.reads += 1
            return bytes(memory[offset:offset+length])
        def write_flash_once(self, offset, data):
            assert load_image(private / (prefix+'-prewrite-source.dpapi')) == source
            self.writes += 1
            memory[offset:offset+len(data)] = data
            if fault == 'write': raise OSError('Synthetic uncertain write')
            return True
        def startup_once(self):
            # Reset cannot precede the verified result export.
            assert list((tmp_path / 'exports').glob('*/attachment-provisioning-result.json'))
            self.starts += 1
        def close(self): self.closed = True

    device = Device()
    def save(root, filename, data):
        if fault == 'storage': raise OSError('Synthetic private storage failure')
        return save_image(root, filename, data)
    if fault == 'result-export':
        original = run.WizardDiagnosticExporter.export
        def failing_export(self, *args, **kwargs):
            if 'provisioning-result.json' in kwargs.get('attachments', {}):
                raise OSError('Synthetic export failure')
            return original(self, *args, **kwargs)
        monkeypatch.setattr(run.WizardDiagnosticExporter, 'export', failing_export)
    args = dict(source=source, source_sha256=core.digest(source), candidate=candidate,
        candidate_sha256=core.digest(candidate), policy=policy, key=key, littlefs=library,
        validate_policy=validator, private_root=private, export_root=tmp_path / 'exports',
        device=device, save_private_image=save, startup_authorized=startup_authorized)
    if profile == 'hold-replacement':
        args.pop('key')
        args['previous_policy'] = previous_policy
    if profile == 'pair-settings':
        args.pop('policy');args.pop('key');args.pop('validate_policy')
        args.update(settings=settings,expected_hold_policy=policy,
            validate_settings=settings_validator,validate_hold_policy=validator)
    if fault:
        with pytest.raises(OSError): selected_run(**args)
        assert device.starts == 0
        assert device.writes == (0 if fault == 'storage' else 1)
    else:
        result = selected_run(**args)
        assert result['status'] == 'FLASH_READBACK_VERIFIED'
        assert device.starts == int(startup_authorized) and device.writes == 1 and device.reads == 2
        assert result['startup_attempted'] is startup_authorized
        assert load_image(private / (prefix+'-candidate.dpapi')) == candidate
        expected_mode='pair-settings' if profile=='pair-settings' else 'hold' if hold else 'startup'
        assert result['schema'] == f'rocell.{expected_mode}_provisioning_result.v1'
        assert not result['application_health_verified'] and not result['motion_authorized']
    assert device.closed
    with pytest.raises(ValueError, match='Existing provisioning attempt'):
        selected_run(**args)
    for file in (tmp_path / 'exports').rglob('*'):
        if file.is_file(): assert key not in file.read_bytes()
