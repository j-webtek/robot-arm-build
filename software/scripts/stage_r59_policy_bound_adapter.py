"""Stage r59 from r58 with the adapter bound to policy constants, offline."""

import hashlib
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


R58_COMPILE = 'wizard-20260922T194627054855Z-9bc643483a50464ea3b3e127600ae487'


def stage(root):
    root = Path(root).resolve(); exports = root / 'runs/wizard-exports'
    report, receipt = _read(exports, R58_COMPILE, 'attachment-compile-review.json')
    prefix = '.firmware-tools/configured-diagnostic-candidate-r58/RoArm-M3_example/'
    source = root / prefix
    files = {p.name: p.read_bytes() for p in source.iterdir() if p.is_file()}
    expected = {Path(path).name: digest for path, digest in report['source_hashes'].items()
                if path.replace('\\', '/').startswith(prefix)}
    sha = lambda raw: hashlib.sha256(raw).hexdigest()
    if (report['status'] != 'COMPILED' or
            report['target'] != 'configured-diagnostic-candidate-r58' or
            set(files) != set(expected) or
            any(sha(raw) != expected[name] for name, raw in files.items())):
        raise ValueError('Pinned r58 source differs')
    name = 'characterization_board_services.h'
    previous = files[name]
    replacement = (root / 'firmware/diagnostics' / name).read_bytes()
    if previous == replacement:
        raise ValueError('r59 adapter did not change')
    return_adapter = replacement.split(b'bool park_return_write', 1)[1].split(
        b'bool park_return_evidence', 1)[0]
    if (b'ParkReanchorPolicy::target12' not in return_adapter or
            b'ParkReanchorPolicy::target13' not in return_adapter or
            b'a!=2389||b!=1725' in return_adapter):
        raise ValueError('Policy-bound adapter source differs')
    files[name] = replacement
    target = root / '.firmware-tools/configured-diagnostic-candidate-r59/RoArm-M3_example'
    target.mkdir(parents=True, exist_ok=False)
    for filename, raw in files.items():
        with (target / filename).open('xb') as stream: stream.write(raw)
        if (target / filename).read_bytes() != raw:
            raise ValueError('Staged source readback differs')
    exporter = WizardDiagnosticExporter(exports); exporter.prepare(create=True)
    saved = exporter.export({'mode': 'r59-policy-bound-adapter-stage'}, [], attachments={
        'r59-policy-bound-adapter-stage.json': canonical({
            'revision': 59, 'predecessor_revision': 58,
            'predecessor_compile_receipt': receipt,
            'changed_files': {name: {'before': sha(previous), 'after': sha(replacement)}},
            'hardware_access': False, 'uploaded': False,
            'settings_changed': False, 'deployable': False,
            'fault_resolved': 'R58_BOARD_ADAPTER_STALE_FIXED_TARGET',
            'fixed_target_goals': [2413, 1701],
            'adapter_uses_policy_constants': True,
            'automatic_retry': False, 'automatic_return': False,
        })})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('r59 stage export invalid')
    return saved['path']


if __name__ == '__main__':
    print(stage(Path(__file__).resolve().parents[1]))
