"""Offline r15 staging; preserves every predecessor artifact and private file."""
import hashlib
import argparse
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', type=int, choices=(15, 16), default=16)
    revision = parser.parse_args().revision
    root = Path(__file__).resolve().parents[1]
    source = root / '.firmware-tools/configured-diagnostic-candidate-r14/RoArm-M3_example'
    target = root / f'.firmware-tools/configured-diagnostic-candidate-r{revision}/RoArm-M3_example'
    exports = root / 'runs/wizard-exports'
    predecessor, receipt_hash = _read(exports,
        'wizard-20260919T041541114321Z-30322c77b1374066ae0eb93579c5ed96', 'attachment-compile-review.json')
    if predecessor['status'] != 'COMPILED':
        raise ValueError('Predecessor build not verified')
    same_name = ('hold_initialization_owner.h', 'hold_plan_admission.h', 'hold_authenticated_runtime.h',
        'verified_hold_handoff.h', 'allocated_hold_runtime.h', 'configured_hold_runtime.h',
        'configured_hold_routes.h', 'configured_held_pair_routes.h', 'configured_pair_board_routes.h')
    mappings = {name: name for name in same_name}
    mappings['configured_native_owner.h'] = 'configured_recovery_board_owner.h'
    mappings['diagnostic_boot.h'] = 'diagnostic_recovery_boot.h'
    mappings['diagnostic_http.h'] = 'configured_hold_routes.h'
    additions = ('configured_recovery_routes.h', 'configured_recovery_board_routes.h',
                 'supported_recovery_board_policy.h')
    files, changes = {}, {}
    for path in source.iterdir():
        if path.is_symlink() or not path.is_file() or path.suffix not in ('.h', '.ino'):
            raise ValueError('Unexpected source entry')
        original = path.read_bytes()
        old_hash = hashlib.sha256(original).hexdigest()
        if predecessor['source_hashes'][str(path.relative_to(root))] != old_hash:
            raise ValueError('Immutable r14 source changed')
        raw = original
        if path.name in mappings:
            raw = (root / 'firmware/diagnostics' / mappings[path.name]).read_bytes()
            if path.name == 'diagnostic_http.h':
                before = b'void registerDiagnosticRoutes()'
                if raw.count(before) != 1:
                    raise ValueError('Hold registration mapping changed')
                raw = raw.replace(before, b'void registerHoldDiagnosticRoutes()')
                raw += b'\n#include "configured_pair_board_routes.h"\n'
            changes[path.name] = dict(before_sha256=old_hash,
                after_sha256=hashlib.sha256(raw).hexdigest(), source=mappings[path.name])
        files[path.name] = raw
    if set(changes) != set(mappings):
        raise ValueError('Missing source mapping')
    for name in additions:
        if name in files: raise ValueError('Addition collides')
        raw = (root / 'firmware/diagnostics' / name).read_bytes()
        files[name] = raw
        changes[name] = dict(before_sha256=None, after_sha256=hashlib.sha256(raw).hexdigest(), source=name)
    target.mkdir(parents=True, exist_ok=False)
    for name, raw in files.items():
        (target / name).write_bytes(raw)
    for name, raw in files.items():
        if (target / name).read_bytes() != raw: raise ValueError('Staging changed bytes')
    review = dict(schema='rocell.recovery_stage.v1', revision=revision, source_compile_sha256=receipt_hash,
        changed_files=changes, unchanged_files=len(files)-len(changes),
        hardware_access=False, firmware_uploaded=False, provisioning_performed=False)
    exporter = WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved = exporter.export({'mode': f'r{revision}-recovery-stage'}, [],
        attachments={'recovery-stage.json': canonical(review)})
    if not verify_export(Path(saved['path']))['valid']: raise ValueError('Stage export failed')
    print(canonical(dict(export_path=saved['path'], **review)).decode())


if __name__ == '__main__': main()
