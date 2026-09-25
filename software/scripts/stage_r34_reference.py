"""Freeze r33 plus three reference-export headers, offline only."""
import hashlib
from pathlib import Path
from rocell.application.product_ghost_export_review import _read
from rocell.application.first_motion_contract import canonical
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def main():
    root=Path(__file__).resolve().parents[1];exports=root/'runs/wizard-exports'
    prefix='.firmware-tools/configured-diagnostic-candidate-r33/RoArm-M3_example/'
    report,receipt=_read(exports,'wizard-20260920T142852905258Z-681d77e3d508428ea251f2e14b071d31',
                         'attachment-compile-review.json')
    expected={Path(p).name:h for p,h in report['source_hashes'].items() if p.replace('\\','/').startswith(prefix)}
    files={p.name:p.read_bytes() for p in (root/prefix).iterdir() if p.is_file()}
    sha=lambda raw:hashlib.sha256(raw).hexdigest()
    if report['status']!='COMPILED' or set(expected)!=set(files) or any(sha(raw)!=expected[n] for n,raw in files.items()):
        raise ValueError('Pinned r33 source differs')
    changes={}
    for name in ('characterization_prepare.h','characterization_controller.h','characterization_prepare_routes.h'):
        raw=(root/'firmware/diagnostics'/name).read_bytes()
        changes[name]=dict(before=sha(files[name]),after=sha(raw));files[name]=raw
    target=root/'.firmware-tools/configured-diagnostic-candidate-r34/RoArm-M3_example'
    target.mkdir(parents=True,exist_ok=False)
    for name,raw in files.items():
        with (target/name).open('xb') as stream:stream.write(raw)
        if (target/name).read_bytes()!=raw:raise ValueError('Stage readback differs')
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({'mode':'r34-reference-stage'},[],attachments={'reference-stage.json':canonical(dict(
        predecessor_compile_receipt=receipt,changed_files=changes,maximum_legs=1,
        new_route='/rocell/characterization/reference',hardware_access=False,uploaded=False,
        startup_changed=False,settings_changed=False,movement_policy_changed=False))})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Stage export failed')
    print(saved['path'])


if __name__=='__main__':main()
