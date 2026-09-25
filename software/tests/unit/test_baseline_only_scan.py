from pathlib import Path
import shutil
import subprocess
import json
import copy

import pytest


def test_native_read_only_scan(tmp_path):
    compiler = shutil.which('clang++')
    if not compiler:
        pytest.skip('Host compiler required')
    root = Path(__file__).resolve().parents[2]
    executable = tmp_path / 'baseline-only.exe'
    build = subprocess.run([compiler, '-std=c++14', '-Wall', '-Wextra', '-Werror',
        '-I' + str(root / '.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root / 'firmware/diagnostics/test_baseline_only_scan.cpp'),
        '-o', str(executable)], capture_output=True, text=True, timeout=60)
    assert build.returncode == 0, build.stderr
    run = subprocess.run([str(executable)], capture_output=True, text=True, timeout=10)
    assert run.returncode == 0, run.stderr
    from rocell.application.baseline_only_review import assess_baseline_only
    from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export
    normal, failed = map(json.loads, run.stdout.splitlines())
    def assess(record):
        return assess_baseline_only(record, boot_id='boot', scan_id='scan')
    result = assess(normal)
    assert result['status'] == 'BASELINE_CAPTURED' and len(result['joints']) == 7
    assert all(joint['moving'] == 1 for joint in result['joints'])
    assert not result['progression_authority'] and not result['freshness_at_use_verified']
    assert assess(failed)['status'] == 'INCONCLUSIVE'
    altered = copy.deepcopy(normal); altered['reads'][1][0][1] = 1
    assert assess(altered)['status'] == 'INCONCLUSIVE'
    altered = copy.deepcopy(normal); altered['boot_id'] = 'wrong'
    with pytest.raises(ValueError): assess(altered)
    exporter = WizardDiagnosticExporter(tmp_path / 'exports'); exporter.prepare(create=True)
    saved = exporter.export({'mode': 'simulated-baseline-only', 'assessment': result}, [],
        attachments={'baseline.json': run.stdout.splitlines()[0].encode(),
                     'failed-baseline.json': run.stdout.splitlines()[1].encode()})
    assert verify_export(Path(saved['path']))['valid']
    assert assess(json.loads((Path(saved['path']) / 'attachment-baseline.json').read_bytes())) == result
