"""Stage an offline, public-source-only six-count recovery delta from verified r17."""
import hashlib
from pathlib import Path
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def main():
    root = Path(__file__).resolve().parents[1]
    exports = root / 'runs/wizard-exports'
    source = root / '.firmware-tools/configured-diagnostic-candidate-r17/RoArm-M3_example'
    target = root / '.firmware-tools/configured-diagnostic-candidate-r18/RoArm-M3_example'
    report, receipt_hash = _read(exports,
        'wizard-20260919T124030530895Z-4b08188d6ec14f308e9c7923fd5be8e3',
        'attachment-compile-review.json')
    if report['status'] != 'COMPILED' or report['target'] != 'configured-diagnostic-candidate-r17':
        raise ValueError('Verified predecessor required')
    files, changes = {}, {}
    digest = lambda raw: hashlib.sha256(raw).hexdigest()
    expected = {Path(name).name: value for name, value in report['source_hashes'].items()
                if name.replace('\\', '/').startswith('.firmware-tools/configured-diagnostic-candidate-r17/RoArm-M3_example/')}
    for path in source.iterdir():
        if path.is_symlink() or not path.is_file() or path.suffix not in ('.h', '.ino'):
            raise ValueError('Unexpected source entry')
        raw = path.read_bytes()
        if expected.get(path.name) != digest(raw):
            raise ValueError('Immutable predecessor changed')
        files[path.name] = raw
    if set(files) != set(expected):
        raise ValueError('Predecessor inventory changed')
    for name in ('hold_initialization_owner.h', 'hold_plan_admission.h',
                 'hold_authenticated_runtime.h', 'verified_hold_handoff.h',
                 'allocated_hold_runtime.h', 'configured_hold_runtime.h',
                 'configured_recovery_board_routes.h', 'configured_native_owner.h'):
        previous = files.get(name)
        source_name = 'configured_recovery_board_owner.h' if name == 'configured_native_owner.h' else name
        raw = (root / 'firmware/diagnostics' / source_name).read_bytes()
        if name == 'configured_native_owner.h':
            raw = b'#define ROCELL_SIX_COUNT_RECOVERY 1\n' + raw
        changes[name] = dict(before_sha256=digest(previous) if previous is not None else None,
                             after_sha256=digest(raw))
        files[name] = raw
    # Preserve the immutable predecessor and all files outside the reviewed delta.
    target.mkdir(parents=True, exist_ok=False)
    for name, raw in files.items():
        with (target / name).open('xb') as stream:
            stream.write(raw)
        if (target / name).read_bytes() != raw:
            raise ValueError('Staging readback differs')
    review = dict(schema='rocell.six_count_stage.v1', revision=18,
                  predecessor_compile_sha256=receipt_hash, changed_files=changes,
                  unchanged_files=len(files)-len(changes), hardware_access=False,
                  firmware_uploaded=False, provisioning_performed=False)
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved = exporter.export({'mode': 'r18-six-count-stage'}, [],
                            attachments={'six-count-stage.json': canonical(review)})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Stage export failed')
    print(canonical(dict(export_path=saved['path'], **review)).decode())


if __name__ == '__main__':
    main()
