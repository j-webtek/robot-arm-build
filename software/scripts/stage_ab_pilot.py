"""Freeze one fixed A/B variant from verified r38. Offline only; never upload."""
import argparse
import hashlib
from pathlib import Path
from rocell.application.product_ghost_export_review import _read
from rocell.application.first_motion_contract import canonical
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export

VARIANTS = {'control': (39, 'ABControl'), 'compensated': (40, 'ABCandidate')}
HEADERS = ('characterization_prepare.h', 'characterization_controller.h',
           'shoulder_characterization_owner.h')
PREDECESSOR = 'wizard-20260920T171839175122Z-d0ed0e8ab5634672a1f7913cba0137f4'


def stage(root, variant):
    revision, selector = VARIANTS[variant]
    exports = root/'runs/wizard-exports'
    prefix = '.firmware-tools/configured-diagnostic-candidate-r38/RoArm-M3_example/'
    report, receipt = _read(exports, PREDECESSOR, 'attachment-compile-review.json')
    expected = {Path(p).name: h for p, h in report['source_hashes'].items()
                if p.replace('\\', '/').startswith(prefix)}
    files = {p.name: p.read_bytes() for p in (root/prefix).iterdir() if p.is_file()}
    sha = lambda raw: hashlib.sha256(raw).hexdigest()
    if (report['status'] != 'COMPILED' or not expected or set(expected) != set(files)
            or any(sha(raw) != expected[n] for n, raw in files.items())):
        raise ValueError('Pinned r38 source differs')
    before = {n: sha(raw) for n, raw in files.items()}
    for name in HEADERS:
        files[name] = (root/'firmware/diagnostics'/name).read_bytes()
    board = 'characterization_smoke_board.h'
    old = b'CharacterizationPattern::Repeatability'
    if files[board].count(old) != 1:
        raise ValueError('Expected exactly one trusted selector')
    files[board] = files[board].replace(old, ('CharacterizationPattern::'+selector).encode())
    changes = {n: dict(before=before[n], after=sha(raw)) for n, raw in files.items()
               if before[n] != sha(raw)}
    if set(changes) != set(HEADERS) | {board}:
        raise ValueError('Unexpected change set')
    # Check export availability before freezing a non-overwritable candidate.
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    target = root/f'.firmware-tools/configured-diagnostic-candidate-r{revision}/RoArm-M3_example'
    target.mkdir(parents=True, exist_ok=False)
    for name, raw in files.items():
        with (target/name).open('xb') as stream:
            stream.write(raw)
        if (target/name).read_bytes() != raw:
            raise ValueError('Stage readback differs')
    saved = exporter.export({'mode': 'ab-pilot-stage'}, [], attachments={
        'ab-stage.json': canonical(dict(revision=revision, variant=variant,
            selector=selector, predecessor_compile_receipt=receipt,
            changed_files=changes, maximum_legs=3,
            goals=[[2377,1737],[2389,1725],
                   [2387,1727] if variant=='control' else [2378,1736]],
            hardware_access=False, uploaded=False, settings_changed=False,
            deployable=False))})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Stage export failed')
    return saved['path']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--variant', required=True, choices=VARIANTS)
    args = parser.parse_args()
    print(stage(Path(__file__).resolve().parents[1], args.variant))
