"""Stage the exact r53 direct-observation-window change from reviewed r52.

Offline only: this never connects to or resets the controller.
"""
import hashlib
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


R52_COMPILE='wizard-20260921T094941126648Z-acc5e720a663431f8c0758f2212de354'
OWNER='shoulder_characterization_owner.h'


def stage(root):
    root=Path(root).resolve()
    exports=root/'runs/wizard-exports'
    report,receipt=_read(exports,R52_COMPILE,'attachment-compile-review.json')
    prefix='.firmware-tools/configured-diagnostic-candidate-r52/RoArm-M3_example/'
    source=root/prefix
    files={path.name:path.read_bytes() for path in source.iterdir() if path.is_file()}
    expected={Path(path).name:digest for path,digest in report['source_hashes'].items()
              if path.replace('\\','/').startswith(prefix)}
    sha=lambda raw:hashlib.sha256(raw).hexdigest()
    if (report['status']!='COMPILED' or report['target']!='configured-diagnostic-candidate-r52'
            or set(files)!=set(expected) or
            any(sha(raw)!=expected[name] for name,raw in files.items())):
        raise ValueError('Pinned r52 source differs')
    old=files[OWNER]
    new=(root/'firmware/diagnostics'/OWNER).read_bytes()
    if old==new or b'ghost_pair_transition_' not in new or b'2000000)return;' not in new:
        raise ValueError('Reviewed direct-window change missing')
    files[OWNER]=new
    target=root/'.firmware-tools/configured-diagnostic-candidate-r53/RoArm-M3_example'
    target.mkdir(parents=True,exist_ok=False)
    for name,raw in files.items():
        with (target/name).open('xb') as stream:
            stream.write(raw)
        if target.joinpath(name).read_bytes()!=raw:
            raise ValueError('Staged source readback differs')
    exporter=WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved=exporter.export({'mode':'r53-direct-window-stage'},[],attachments={
        'r53-direct-window-stage.json':canonical(dict(
            revision=53,predecessor_revision=52,predecessor_compile_receipt=receipt,
            changed_files={OWNER:dict(before=sha(old),after=sha(new))},
            hardware_access=False,uploaded=False,settings_changed=False,deployable=False))})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Stage export invalid')
    return saved['path']


if __name__=='__main__':
    print(stage(Path(__file__).resolve().parents[1]))
