"""Freeze a matrix candidate from verified r36; never upload or access hardware."""
import hashlib
from pathlib import Path
from rocell.application.product_ghost_export_review import _read
from rocell.application.first_motion_contract import canonical
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export

CHANGED_HEADERS = ('characterization_prepare.h', 'characterization_controller.h',
                   'shoulder_characterization_policy.h', 'shoulder_characterization_owner.h')


def main():
    root = Path(__file__).resolve().parents[1]
    exports = root/'runs/wizard-exports'
    prefix = '.firmware-tools/configured-diagnostic-candidate-r36/RoArm-M3_example/'
    report, receipt = _read(exports,
        'wizard-20260920T162104226298Z-6457ab96d6274648bdfeb735db1e2b74',
        'attachment-compile-review.json')
    expected = {Path(p).name: h for p, h in report['source_hashes'].items()
                if p.replace('\\', '/').startswith(prefix)}
    files = {p.name: p.read_bytes() for p in (root/prefix).iterdir() if p.is_file()}
    sha = lambda raw: hashlib.sha256(raw).hexdigest()
    if (report['status'] != 'COMPILED' or set(expected) != set(files) or
            any(sha(raw) != expected[n] for n, raw in files.items())):
        raise ValueError('Pinned r36 source differs')
    before = {n: sha(raw) for n, raw in files.items()}
    for name in CHANGED_HEADERS:
        files[name] = (root/'firmware/diagnostics'/name).read_bytes()
    board = 'characterization_smoke_board.h'
    old = b'CharacterizationPattern::Matched'
    if files[board].count(old) != 1:
        raise ValueError('Expected exactly one trusted pattern selection')
    files[board] = files[board].replace(old, b'CharacterizationPattern::Matrix')
    changes = {n: dict(before=before[n], after=sha(raw)) for n, raw in files.items()
               if before[n] != sha(raw)}
    if set(changes) != set(CHANGED_HEADERS) | {board}:
        raise ValueError('Unexpected change set')
    target = root/'.firmware-tools/configured-diagnostic-candidate-r37/RoArm-M3_example'
    target.mkdir(parents=True, exist_ok=False)
    for name, raw in files.items():
        with (target/name).open('xb') as stream:
            stream.write(raw)
        if (target/name).read_bytes() != raw:
            raise ValueError('Stage readback differs')
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved = exporter.export({'mode': 'r37-matrix-stage'}, [], attachments={
        'matrix-stage.json': canonical(dict(predecessor_compile_receipt=receipt,
            changed_files=changes, maximum_legs=12, offsets=[-4,0,-8,0,-12,0]*2,
            total_selected_excursion_counts=32, total_neighbour_excursion_counts=2,
            small_response_outcome=4, maximum_consecutive_small=1,
            observation_window_basis='first_post_write_sample',
            small_response_observation_us=2000000, hardware_access=False,
            uploaded=False, startup_changed=False, settings_changed=False,
            movement_policy_changed=True, deployable=False))})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Stage export failed')
    print(saved['path'])


if __name__ == '__main__':
    main()
