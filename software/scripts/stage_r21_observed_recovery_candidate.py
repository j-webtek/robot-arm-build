"""Public-source staging only: r20 plus exact observed-pose recovery support."""
import hashlib
from pathlib import Path
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def main():
    root = Path(__file__).resolve().parents[1]; exports = root/'runs/wizard-exports'
    source = root/'.firmware-tools/configured-diagnostic-candidate-r20/RoArm-M3_example'
    target = root/'.firmware-tools/configured-diagnostic-candidate-r21/RoArm-M3_example'
    report, receipt = _read(exports, 'wizard-20260919T135231068472Z-4ae0d39f68234b01abf2c114d5bf0a4c',
                            'attachment-compile-review.json')
    if report['status'] != 'COMPILED' or report['target'] != 'configured-diagnostic-candidate-r20':
        raise ValueError('Verified predecessor build required')
    sha = lambda b: hashlib.sha256(b).hexdigest()
    expected = {Path(p).name: h for p,h in report['source_hashes'].items()
        if p.replace('\\','/').startswith('.firmware-tools/configured-diagnostic-candidate-r20/RoArm-M3_example/')}
    files = {}
    for path in source.iterdir():
        if path.is_symlink() or not path.is_file() or path.suffix not in ('.h','.ino'):
            raise ValueError('Unexpected predecessor entry')
        raw = path.read_bytes()
        if expected.get(path.name) != sha(raw): raise ValueError('Predecessor changed')
        files[path.name] = raw
    if set(files) != set(expected): raise ValueError('Predecessor inventory changed')
    original = dict(files)
    for name in ('supported_recovery_board_policy.h','configured_recovery_board_routes.h'):
        files[name] = (root/'firmware/diagnostics'/name).read_bytes()
    owner = files['configured_native_owner.h']
    if b'#define ROCELL_SIX_COUNT_RECOVERY 1' not in owner:
        raise ValueError('Expected six-count runtime missing')
    files['configured_native_owner.h'] = b'#define ROCELL_OBSERVED_POSE_RECOVERY 1\n'+owner
    changes = {n: dict(before_sha256=sha(original[n]), after_sha256=sha(raw))
               for n,raw in files.items() if raw != original[n]}
    if len(changes) != 3: raise ValueError('Unexpected change scope')
    target.mkdir(parents=True, exist_ok=False)
    for name, raw in files.items():
        with (target/name).open('xb') as stream: stream.write(raw)
        if (target/name).read_bytes() != raw: raise ValueError('Stage readback mismatch')
    review = dict(schema='rocell.observed_recovery_candidate_stage.v1', revision=21,
        predecessor_compile_sha256=receipt, changed_files=changes,
        unchanged_files=len(files)-len(changes), hardware_access=False,
        firmware_uploaded=False, provisioning_performed=False)
    exporter = WizardDiagnosticExporter(exports); exporter.prepare(create=True)
    saved = exporter.export({'mode':'r21-public-source-stage'}, [], attachments={
        'observed-recovery-stage.json': canonical(review)})
    if not verify_export(Path(saved['path']))['valid']: raise ValueError('Stage export failed')
    print(canonical(dict(export_path=saved['path'], **review)).decode())


if __name__ == '__main__': main()
