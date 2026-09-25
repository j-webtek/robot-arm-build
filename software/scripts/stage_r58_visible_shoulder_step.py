"""Stage the r58 fixed visible shoulder step from reviewed r57, offline only."""

import hashlib
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


R57_COMPILE = 'wizard-20260922T003055181870Z-087edefca56649f3a79cc1b33ea83d05'


def stage(root):
    root = Path(root).resolve()
    report, receipt = _read(root / 'runs/wizard-exports', R57_COMPILE,
                            'attachment-compile-review.json')
    prefix = '.firmware-tools/configured-diagnostic-candidate-r57/RoArm-M3_example/'
    source = root / prefix
    files = {path.name: path.read_bytes() for path in source.iterdir()
             if path.is_file()}
    expected = {Path(path).name: digest
                for path, digest in report['source_hashes'].items()
                if path.replace('\\', '/').startswith(prefix)}
    sha = lambda raw: hashlib.sha256(raw).hexdigest()
    if (report['status'] != 'COMPILED' or
            report['target'] != 'configured-diagnostic-candidate-r57' or
            set(files) != set(expected) or
            any(sha(raw) != expected[name] for name, raw in files.items())):
        raise ValueError('Pinned r57 source differs')
    previous = files['park_reanchor_policy.h']
    replacement = (root / 'firmware/diagnostics/park_reanchor_policy_r58.h').read_bytes()
    if previous == replacement:
        raise ValueError('r58 policy did not change')
    files['park_reanchor_policy.h'] = replacement
    changed = {'park_reanchor_policy.h': {
        'before': sha(previous), 'after': sha(replacement)}}
    target = root / '.firmware-tools/configured-diagnostic-candidate-r58/RoArm-M3_example'
    target.mkdir(parents=True, exist_ok=False)
    for name, raw in files.items():
        with (target / name).open('xb') as stream:
            stream.write(raw)
        if (target / name).read_bytes() != raw:
            raise ValueError('Staged source readback differs')
    exporter = WizardDiagnosticExporter(root / 'runs/wizard-exports')
    exporter.prepare(create=True)
    saved = exporter.export({'mode': 'r58-visible-shoulder-step-stage'}, [],
                            attachments={'r58-visible-step-stage.json': canonical({
        'revision': 58, 'predecessor_revision': 57,
        'predecessor_compile_receipt': receipt,
        'changed_files': changed,
        'hardware_access': False, 'uploaded': False,
        'settings_changed': False, 'deployable': False,
        'source_goals': [2389, 1725],
        'source_positions': [2391, 1724],
        'fixed_target_goals': [2413, 1701],
        'expected_encoder_positions': [2415, 1700],
        'maximum_excursion_counts': 28,
        'route': '/rocell/park-return',
        'automatic_retry': False, 'automatic_return': False,
    })})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Stage export invalid')
    return saved['path']


if __name__ == '__main__':
    print(stage(Path(__file__).resolve().parents[1]))
