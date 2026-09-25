"""Stage public r22 sources only; never connect, restart, provision or upload."""
import hashlib
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def main():
    root = Path(__file__).resolve().parents[1]
    exports = root / 'runs/wizard-exports'
    source = root / '.firmware-tools/configured-diagnostic-candidate-r21/RoArm-M3_example'
    target = root / '.firmware-tools/configured-diagnostic-candidate-r22/RoArm-M3_example'
    report, receipt = _read(exports,
        'wizard-20260919T142823450037Z-4bfd7a6265a24e2fac964fbd26d3bce8',
        'attachment-compile-review.json')
    if report['status'] != 'COMPILED' or report['target'] != 'configured-diagnostic-candidate-r21':
        raise ValueError('Verified r21 predecessor required')
    sha = lambda raw: hashlib.sha256(raw).hexdigest()
    prefix = '.firmware-tools/configured-diagnostic-candidate-r21/RoArm-M3_example/'
    expected = {Path(name).name: digest for name, digest in report['source_hashes'].items()
                if name.replace('\\', '/').startswith(prefix)}
    files = {}
    for path in source.iterdir():
        if path.is_symlink() or not path.is_file() or path.suffix not in ('.h', '.ino'):
            raise ValueError('Unexpected predecessor entry')
        raw = path.read_bytes()
        if expected.get(path.name) != sha(raw):
            raise ValueError('Predecessor source changed')
        files[path.name] = raw
    if set(files) != set(expected):
        raise ValueError('Predecessor inventory changed')
    original = dict(files)
    for name in ('shoulder_configuration_snapshot.h', 'shoulder_configuration_json.h',
                 'shoulder_configuration_routes.h'):
        if name in files:
            raise ValueError('Unexpected preexisting shoulder capture')
        files[name] = (root / 'firmware/diagnostics' / name).read_bytes()
    # Reuse the existing inactive-bus policy, including the pose reservation.
    # Registration itself performs no reads. No enable-packet candidate is copied.
    name = 'configured_pair_board_routes.h'
    raw = files[name]
    marker = b'void registerDiagnosticRoutes(){'
    if raw.count(marker) != 1:
        raise ValueError('Unexpected route registration structure')
    declaration = (
        b'#include "shoulder_configuration_routes.h"\n'
        b'rocell_diag::ShoulderConfigurationRoutes<decltype(st),decltype(rocellConfiguredClock),WebServer>\n'
        b'    rocellShoulderConfigurationRoutes(st,rocellConfiguredClock,server,rocellDiagnosticInstance,rocellConfigurationBusInactive);\n'
    )
    files[name] = raw.replace(marker, declaration + marker +
                             b'\n  rocellShoulderConfigurationRoutes.register_routes();', 1)
    changes = {name: dict(before_sha256=sha(original[name]) if name in original else None,
                         after_sha256=sha(raw))
               for name, raw in files.items() if original.get(name) != raw}
    if len(changes) != 4:
        raise ValueError('Unexpected change scope')
    target.mkdir(parents=True, exist_ok=False)
    for name, raw in files.items():
        with (target / name).open('xb') as stream:
            stream.write(raw)
        if (target / name).read_bytes() != raw:
            raise ValueError('Stage readback mismatch')
    review = dict(schema='rocell.shoulder_capture_candidate_stage.v1', revision=22,
                  predecessor_compile_sha256=receipt, changed_files=changes,
                  unchanged_files=len(files)-len(changes), hardware_access=False,
                  firmware_uploaded=False, provisioning_performed=False,
                  new_motion_routes=False)
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved = exporter.export({'mode': 'r22-public-source-stage'}, [], attachments={
        'shoulder-capture-stage.json': canonical(review)})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Stage export failed')
    print(canonical(dict(export_path=saved['path'], **review)).decode())


if __name__ == '__main__':
    main()
