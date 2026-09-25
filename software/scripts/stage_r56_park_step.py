"""Stage an r56 settling/fault-record candidate from pinned r55, offline only."""

import hashlib
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


R55_COMPILE = 'wizard-20260921T224655422019Z-a0d634b9151d406aa3dd750cfa179dc7'
OVERLAY = ('park_step_policy.h', 'park_step_owner.h')


def stage(root):
    root = Path(root).resolve()
    report, receipt = _read(root/'runs/wizard-exports', R55_COMPILE,
                            'attachment-compile-review.json')
    prefix = '.firmware-tools/configured-diagnostic-candidate-r55/RoArm-M3_example/'
    source = root/prefix
    files = {path.name: path.read_bytes() for path in source.iterdir() if path.is_file()}
    expected = {Path(path).name: digest for path, digest in report['source_hashes'].items()
                if path.replace('\\', '/').startswith(prefix)}
    sha = lambda raw: hashlib.sha256(raw).hexdigest()
    if (report['status'] != 'COMPILED' or
            report['target'] != 'configured-diagnostic-candidate-r55' or
            set(files) != set(expected) or
            any(sha(raw) != expected[name] for name, raw in files.items())):
        raise ValueError('Pinned r55 source differs')
    changed = {}
    for name in OVERLAY:
        old = files[name]
        new = (root/'firmware/diagnostics'/name).read_bytes()
        if sha(old) == sha(new):
            raise ValueError('No reviewed change for '+name)
        files[name] = new
        changed[name] = {'before': sha(old), 'after': sha(new)}
    target = root/'.firmware-tools/configured-diagnostic-candidate-r56/RoArm-M3_example'
    target.mkdir(parents=True, exist_ok=False)
    for name, raw in files.items():
        with (target/name).open('xb') as stream:
            stream.write(raw)
        if target.joinpath(name).read_bytes() != raw:
            raise ValueError('Staged source readback differs')
    exporter = WizardDiagnosticExporter(root/'runs/wizard-exports')
    exporter.prepare(create=True)
    saved = exporter.export({'mode': 'r56-park-step-stage'}, [], attachments={
        'r56-park-step-stage.json': canonical(dict(
            revision=56, predecessor_revision=55, predecessor_compile_receipt=receipt,
            changed_files=changed, hardware_access=False, uploaded=False,
            settings_changed=False, deployable=False))})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Stage export invalid')
    return saved['path']


if __name__ == '__main__':
    print(stage(Path(__file__).resolve().parents[1]))
