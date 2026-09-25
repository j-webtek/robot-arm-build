"""Stage an offline, public-source-only gain diagnostic delta from verified r16."""
import hashlib
from pathlib import Path
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def main():
    root = Path(__file__).resolve().parents[1]
    exports = root / 'runs/wizard-exports'
    source = root / '.firmware-tools/configured-diagnostic-candidate-r16/RoArm-M3_example'
    target = root / '.firmware-tools/configured-diagnostic-candidate-r17/RoArm-M3_example'
    report, receipt_hash = _read(exports,
        'wizard-20260919T113420406745Z-1e5770617ccf427094e4960eacaf93df',
        'attachment-compile-review.json')
    if report['status'] != 'COMPILED' or report['target'] != 'configured-diagnostic-candidate-r16':
        raise ValueError('Verified predecessor required')
    files, changes = {}, {}
    digest = lambda raw: hashlib.sha256(raw).hexdigest()
    expected = {Path(name).name: value for name, value in report['source_hashes'].items()
                if name.replace('\\', '/').startswith('.firmware-tools/configured-diagnostic-candidate-r16/RoArm-M3_example/')}
    for path in source.iterdir():
        if path.is_symlink() or not path.is_file() or path.suffix not in ('.h', '.ino'):
            raise ValueError('Unexpected source entry')
        raw = path.read_bytes()
        if expected.get(path.name) != digest(raw):
            raise ValueError('Immutable predecessor changed')
        files[path.name] = raw
    if set(files) != set(expected):
        raise ValueError('Predecessor inventory changed')
    for name in ('configured_pair_board_routes.h', 'elbow_gain_snapshot.h',
                 'elbow_gain_json.h', 'elbow_gain_routes.h'):
        previous = files.get(name)
        raw = (root / 'firmware/diagnostics' / name).read_bytes()
        changes[name] = dict(before_sha256=digest(previous) if previous is not None else None,
                             after_sha256=digest(raw))
        files[name] = raw
    # Preserve all predecessor motion, recovery, startup and configuration code.
    target.mkdir(parents=True, exist_ok=False)
    for name, raw in files.items():
        with (target / name).open('xb') as stream:
            stream.write(raw)
        if (target / name).read_bytes() != raw:
            raise ValueError('Staging readback differs')
    review = dict(schema='rocell.gain_stage.v1', revision=17,
                  predecessor_compile_sha256=receipt_hash, changed_files=changes,
                  unchanged_files=len(files)-len(changes), hardware_access=False,
                  firmware_uploaded=False, provisioning_performed=False)
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved = exporter.export({'mode': 'r17-gain-stage'}, [],
                            attachments={'gain-stage.json': canonical(review)})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Stage export failed')
    print(canonical(dict(export_path=saved['path'], **review)).decode())


if __name__ == '__main__':
    main()
