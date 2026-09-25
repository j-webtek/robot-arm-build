"""Freeze r35 plus bounded matched composition; offline only, never upload."""
import hashlib
from pathlib import Path
from rocell.application.product_ghost_export_review import _read
from rocell.application.first_motion_contract import canonical
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def main():
    root=Path(__file__).resolve().parents[1];exports=root/'runs/wizard-exports'
    prefix='.firmware-tools/configured-diagnostic-candidate-r35/RoArm-M3_example/'
    report,receipt=_read(exports,'wizard-20260920T155503166485Z-6860d55adcb74a55af2e93c63e8398ea',
                         'attachment-compile-review.json')
    expected={Path(p).name:h for p,h in report['source_hashes'].items() if p.replace('\\','/').startswith(prefix)}
    files={p.name:p.read_bytes() for p in (root/prefix).iterdir() if p.is_file()}
    sha=lambda raw:hashlib.sha256(raw).hexdigest()
    if report['status']!='COMPILED' or set(expected)!=set(files) or any(sha(raw)!=expected[n] for n,raw in files.items()):
        raise ValueError('Pinned r35 source differs')
    before={n:sha(raw) for n,raw in files.items()}
    for name in ('shoulder_characterization_owner.h','characterization_session.h'):
        files[name]=(root/'firmware/diagnostics'/name).read_bytes()
    changes={n:dict(before=before[n],after=sha(raw)) for n,raw in files.items() if before[n]!=sha(raw)}
    if set(changes)!={'shoulder_characterization_owner.h','characterization_session.h'}:
        raise ValueError('Unexpected change set')
    target=root/'.firmware-tools/configured-diagnostic-candidate-r36/RoArm-M3_example'
    target.mkdir(parents=True,exist_ok=False)
    for n,raw in files.items():
        with (target/n).open('xb') as stream:stream.write(raw)
        if (target/n).read_bytes()!=raw:raise ValueError('Stage readback differs')
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({'mode':'r36-matched-stage'},[],attachments={'matched-stage.json':canonical(dict(
        predecessor_compile_receipt=receipt,changed_files=changes,maximum_legs=12,
        total_selected_excursion_counts=32,total_neighbour_excursion_counts=2,
        hardware_access=False,uploaded=False,startup_changed=False,settings_changed=False,
        movement_policy_changed=True,small_response_observation_us=2000000,failed_result_outcome=3,deployable=False))})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Stage export failed')
    print(saved['path'])


if __name__=='__main__':main()
