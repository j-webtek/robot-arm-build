"""Stage corrected policy-bound adapter as r60, preserving failed r59."""

import hashlib
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


R58_COMPILE = 'wizard-20260922T194627054855Z-9bc643483a50464ea3b3e127600ae487'
FAILED_R59_COMPILE = 'wizard-20260922T202808438722Z-86271b878fd84537b1bf5eb339bf3f0c'


def stage(root):
    root = Path(root).resolve(); exports = root / 'runs/wizard-exports'
    report, receipt = _read(exports, R58_COMPILE, 'attachment-compile-review.json')
    failed, failed_receipt = _read(exports, FAILED_R59_COMPILE,
                                   'attachment-compile-review.json')
    if failed['status'] != 'FAILED' or failed['artifact_hashes']:
        raise ValueError('Pinned r59 compile failure differs')
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
    name = 'characterization_board_services.h'; previous = files[name]
    replacement = (root / 'firmware/diagnostics' / name).read_bytes()
    section = replacement.split(b'bool park_return_write', 1)[1].split(
        b'bool park_return_evidence', 1)[0]
    if (b'#include "park_reanchor_policy.h"' not in replacement or
            b'ParkReanchorPolicy::target12' not in section or
            b'ParkReanchorPolicy::target13' not in section or
            b'a!=2389||b!=1725' in section):
        raise ValueError('Corrected adapter source differs')
    files[name] = replacement
    target = root / '.firmware-tools/configured-diagnostic-candidate-r60/RoArm-M3_example'
    target.mkdir(parents=True, exist_ok=False)
    for filename, raw in files.items():
        with (target / filename).open('xb') as stream: stream.write(raw)
        if (target / filename).read_bytes() != raw:
            raise ValueError('Staged source readback differs')
    exporter = WizardDiagnosticExporter(exports); exporter.prepare(create=True)
    saved = exporter.export({'mode': 'r60-policy-bound-adapter-stage'}, [], attachments={
        'r60-policy-bound-adapter-stage.json': canonical({
            'revision': 60, 'predecessor_revision': 58,
            'predecessor_compile_receipt': receipt,
            'failed_r59_compile_receipt': failed_receipt,
            'changed_files': {name: {'before': sha(previous), 'after': sha(replacement)}},
            'hardware_access': False, 'uploaded': False,
            'settings_changed': False, 'deployable': False,
            'fault_resolved': 'R58_BOARD_ADAPTER_STALE_FIXED_TARGET',
            'compile_order_fix': 'EXPLICIT_POLICY_INCLUDE',
            'fixed_target_goals': [2413, 1701],
            'adapter_uses_policy_constants': True,
            'automatic_retry': False, 'automatic_return': False,
        })})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('r60 stage export invalid')
    return saved['path']


if __name__ == '__main__':
    print(stage(Path(__file__).resolve().parents[1]))
