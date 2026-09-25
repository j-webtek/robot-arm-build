import json
import shutil

import pytest

from rocell.application.first_motion_contract import canonical
from rocell.application.positional_campaign_native_retention import publish_native_campaign_result
from rocell.application.positional_campaign_native_export import verify_native_retained_export
from test_positional_campaign_native_retention import prepared


def bundle(tmp_path, monkeypatch, **kwargs):
    reader, raw, receipt = prepared(tmp_path, monkeypatch, **kwargs)
    path, report = publish_native_campaign_result(tmp_path, reader, request_original=raw, receipt=receipt)
    portable = tmp_path / 'portable-export'
    portable.mkdir()
    for name in [path.name] + [item['file'] for item in report['originals'].values()]:
        shutil.copy2(tmp_path / name, portable / name)
    return portable, path.name, report


@pytest.mark.parametrize('case', ['complete', 'miss', 'cancelled'])
def test_copied_bundle_reproduces_without_live_reader_or_source_records(tmp_path, monkeypatch, case):
    options = dict(missed_leg=1) if case == 'miss' else dict(cancel_after_write=True) if case == 'cancelled' else {}
    portable, name, _ = bundle(tmp_path, monkeypatch, **options)
    import rocell.application.positional_campaign_native_export as module
    real_read = module.read_bounded_regular_file
    def portable_only(path, **kwargs):
        assert path.parent == portable
        return real_read(path, **kwargs)
    monkeypatch.setattr(module, 'read_bounded_regular_file', portable_only)
    result = verify_native_retained_export(portable, name)
    assert result['valid']
    assert result['endpoint_completion_consistent'] is (case == 'complete')
    assert result['reconstruction_consistent'] is (case != 'cancelled')
    assert not result['process_receipt_authenticated']
    assert not result['motion_authorized'] and not result['physical_accuracy_verified']
    diagnostics = result['endpoint_diagnostics']
    if case == 'cancelled':
        assert diagnostics == []  # No fabricated endpoint for partial capture.
    else:
        assert len(diagnostics) == 2
        first = diagnostics[0]
        assert first['final_rad'] - first['target_rad'] == pytest.approx(first['signed_error_rad'])
        assert first['post_sample_count'] >= 20
        assert first['direction'] == 'INCREASING'
        assert first['command']['rad'] == first['target_rad']
        quality = first['quality_assessment']
        assert quality['schema'] == 'rocell.endpoint_quality.v1'
        assert quality['historical_endpoint_verified'] == first['reported_endpoint_verified']
        assert quality['absolute_error_deg'] >= 0
        assert quality['motion_authorized'] is False
        if case == 'complete':
            assert all(row['reported_endpoint_verified'] for row in diagnostics)
            assert diagnostics[1]['direction'] == 'DECREASING'
            assert first['quiet_entry_after_write_bounds_ns'] is not None
        else:
            assert not first['reported_endpoint_verified']
            assert diagnostics[1]['status'] == 'NOT_EXECUTED'
            assert diagnostics[1]['final_rad'] is None


@pytest.mark.parametrize('fault', ['claim', 'trial', 'completion', 'path', 'missing'])
def test_changed_export_cannot_reproduce_success(tmp_path, monkeypatch, fault):
    portable, name, report = bundle(tmp_path, monkeypatch)
    if fault in ('claim', 'trial'):
        kind = 'claimed' if fault == 'claim' else 'trial'
        path = portable / report['originals'][kind]['file']
        wrapper = json.loads(path.read_bytes())
        wrapper['base64'] = 'e30='
        path.write_bytes(canonical(wrapper))
    elif fault == 'missing':
        (portable / report['originals']['launch']['file']).unlink()
    else:
        if fault == 'completion': report['endpoint_reported_complete'] = False
        if fault == 'path': report['originals']['trial']['file'] = '../outside.json'
        (portable / name).write_bytes(canonical(report))
    with pytest.raises((ValueError, OSError, RuntimeError)):
        verify_native_retained_export(portable, name)
