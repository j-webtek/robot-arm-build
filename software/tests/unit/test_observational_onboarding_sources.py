"""Correlate modeled onboarding records; no OS/device observations occur here."""
import hashlib

import pytest

from rocell.application.first_motion_contract import canonical
from rocell.application.observational_onboarding_sources import sources_from_onboarding
from test_wizard_native_arm_integration import setup
from test_wizard_native_arm_integration import action
from test_wizard_passive_arm_setup import ready


@pytest.mark.parametrize('fault', [None, 'history', 'binary', 'unit', 'metadata', 'session'])
def test_metadata_and_operator_history_keep_separate_evidence_basis(setup, fault):
    service, runner, _, _ = ready(setup)
    calls = list(runner.calls)
    native = service._native_arm_report
    raw = canonical(native)
    unit = dict(schema='rocell.observational_received_unit.v1', session_id=service.session_id,
        source_sha256=service.source_sha256, native_report_sha256=hashlib.sha256(raw).hexdigest(),
        operator_id='synthetic', model='RoArm-M3-Pro', firmware_unchanged_since_delivery=True,
        basis='OPERATOR_REPORTED', installed_binary_verified=False)
    if fault == 'history': unit['firmware_unchanged_since_delivery'] = False
    if fault == 'binary': unit['installed_binary_verified'] = True
    if fault == 'unit': unit['native_report_sha256'] = 'f'*64
    if fault == 'session': unit['session_id'] = 'wizard-'+'f'*32
    if fault == 'metadata': raw = canonical(dict(native, status='HELD'))
    def build():
        return sources_from_onboarding(native_original=raw,
            generic_review=service._device_selection.reviewed_candidate('SERIAL'),
            received_unit_original=canonical(unit), protocol_original=b'{"synthetic":"reviewed protocol fixture"}',
            session_id=service.session_id, source_sha256=service.source_sha256)
    if fault:
        with pytest.raises(ValueError): build()
    else:
        binding, originals, summary = build()
        assert summary['installed_binary_verified'] is False
        assert summary['firmware_basis'] == 'OPERATOR_REPORTED_HISTORY'
        assert summary['motion_authorized'] is False
        assert binding.installed_firmware_evidence_sha256 == hashlib.sha256(originals['received_unit']).hexdigest()
        assert binding.identity.port_name == native['reviewed_generic_candidate']['ephemeral_locator_observation']
    assert runner.calls == calls


def test_intake_setup_run_rejects_synthetic_usb_before_key_or_device_access(setup, monkeypatch):
    from rocell.application import wizard_observational_coordinator as coordinator
    from rocell.providers.windows import bench_review_key
    from rocell.safety.observational_review_authority import CHECKS
    service, runner, _, _ = ready(setup)
    calls = list(runner.calls)
    monkeypatch.setattr(service, '_powered_setup_context', lambda: {'synthetic':True})
    def forbidden(*args, **kwargs):
        pytest.fail('Synthetic inventory reached key lookup or native dispatch')
    monkeypatch.setattr(bench_review_key, 'load_host_observational_review_authority', forbidden)
    monkeypatch.setattr(coordinator, 'run_reviewed_observational', forbidden)
    imported = action(service, 'use_current_arm_for_observational_test',
        operator_id='synthetic', confirm_model=True, firmware_unchanged=True)
    assert imported['status'] == 'SUCCEEDED'
    source = imported['result']['steps'][0]['report']['receipt']['source_id']
    staged = action(service, 'setup_observational_movement', source_id=source, direction='-1')
    assert staged['status'] == 'SUCCEEDED', staged
    attempted = action(service, 'run_observational_movement',
        operator_id='synthetic', **dict.fromkeys(CHECKS, True))
    # The full production final-click compiler refuses fffe:0002/SYNTHETIC-ARM-A.
    assert attempted['status'] == 'FAILED'
    assert service._observational_confirmation is not None
    assert service._observational_request is None and service._observational_outcome is None
    exported = action(service, 'export_logs')
    assert exported['status'] == 'SUCCEEDED', exported
    assert runner.calls == calls


@pytest.mark.parametrize('corrupt_export', [False, True])
def test_public_intake_populates_setup_without_device_access(setup, corrupt_export):
    service, runner, _, _ = ready(setup)
    calls = list(runner.calls)
    operation = action(service, 'use_current_arm_for_observational_test',
        operator_id='synthetic', confirm_model=True, firmware_unchanged=True)
    assert operation['status'] == 'SUCCEEDED', operation
    report = operation['result']['steps'][0]['report']
    source_id = report['receipt']['source_id']
    assert source_id in service._observational_sources
    view = next(item for item in service.view()['actions'] if item['action_id'] == 'setup_observational_movement')
    assert any(item['value'] == source_id for item in view['fields'][0]['options'])
    assert report['summary']['installed_binary_verified'] is False
    assert service._observational_configuration is None
    assert service._observational_request is None
    if corrupt_export:
        (service._log.root/(operation['operation_id']+'-observational-onboarding-received_unit.json')).write_bytes(b'{}')
    exported = action(service, 'export_logs')
    assert exported['status'] == ('FAILED' if corrupt_export else 'SUCCEEDED'), exported
    if not corrupt_export:
        import base64
        import json
        from pathlib import Path
        from rocell.application.wizard_diagnostic_export import verify_export
        folder = Path(exported['result']['receipt']['path'])
        assert verify_export(folder)['valid']
        bundle = json.loads((folder/'attachment-observational-source-originals.json').read_bytes())
        association = bundle['associations'][0]
        assert association['source_id'] == source_id
        assert set(association['originals']) == {'controller', 'protocol', 'onboarding_native_identity',
            'onboarding_generic_review', 'onboarding_received_unit', 'onboarding_protocol',
            'onboarding_serial_profile', 'onboarding_boot_policy'}
        for digest, original in bundle['originals'].items():
            raw = b''.join(base64.b64decode(chunk, validate=True) for chunk in original['base64_chunks'])
            assert hashlib.sha256(raw).hexdigest() == digest
            assert len(raw) == original['bytes']
    assert runner.calls == calls
