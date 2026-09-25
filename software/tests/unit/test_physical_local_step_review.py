import json
from pathlib import Path

import pytest

from rocell.application.physical_local_step_review import import_local_step, review_physical_export
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def bundle(root, report):
    exporter = WizardDiagnosticExporter(root)
    exporter.prepare(create=True)
    return Path(exporter.export({'mode': 'importer-test'}, [], attachments={
        'local-step-run.json': json.dumps(report).encode()})['path'])


@pytest.mark.parametrize('origin,schema', [('SIMULATION', 'rocell.local_step_run.v1'),
                                        ('DEVICE_CAPTURE', 'unknown')])
def test_reject_other_evidence_types(tmp_path, origin, schema):
    source = bundle(tmp_path, dict(schema=schema, origin=origin, state='STOPPED'))
    with pytest.raises(ValueError, match='Unsupported'):
        import_local_step(source)


def test_corrupt_bundle_cannot_publish(tmp_path):
    source = bundle(tmp_path / 'input', {})
    (source / 'attachment-local-step-run.json').write_text('changed')
    with pytest.raises(ValueError, match='Invalid source'):
        review_physical_export(source, tmp_path / 'output')
    assert not (tmp_path / 'output').exists()


def test_missing_records_are_not_success(tmp_path):
    source = bundle(tmp_path, dict(schema='rocell.local_step_run.v1', origin='DEVICE_CAPTURE',
                                  state='LOCAL_STEP_OBSERVED', records=[]))
    with pytest.raises(ValueError, match='movement evidence'):
        import_local_step(source)


def test_external_reference_rejected(tmp_path):
    source = bundle(tmp_path, dict(schema='rocell.local_step_run.v1', origin='DEVICE_CAPTURE',
                                  state='STOPPED', boot_id='11'*16, command_id='local-step-1',
                                  records=[str(tmp_path.parent / 'outside')]*6))
    with pytest.raises(ValueError, match='sibling'):
        import_local_step(source)


def test_saved_r31_trial_roundtrip(tmp_path):
    # Optional local evidence regression; generic validation tests run everywhere.
    source = Path(__file__).resolve().parents[2] / 'runs/wizard-exports' / (
        'wizard-20260919T234006065057Z-53ea59edfe2d4b20bfc7d3eaae25253e')
    if not source.exists():
        pytest.skip('Historical private hardware evidence not distributed')
    result = import_local_step(source)
    assert result['accepted_records'] == 20
    assert result['original_state'] == 'STOPPED'
    assert [r['endpoint_error_counts'] for r in result['endpoints']] == [10, -7]
    assert [r['measured_change_counts'] for r in result['endpoints']] == [-14, 14]
    assert result['settling']['endpoint_error_counts'] == [9, -7]
    assert result['settling']['validated_records'] == 5
    assert result['settling']['movement_outcome_unchanged'] is True
    exported = Path(review_physical_export(source, tmp_path))
    assert verify_export(exported)['valid']
    assert 'not the later post-fault' in (exported / 'attachment-physical-review.md').read_text()
