"""Stage an exclusive offline r33 build from the hash-checked r31 baseline.

No settings, private filesystem image, device connection or upload is accessed.
"""
import hashlib
import re
from pathlib import Path
from rocell.application.product_ghost_export_review import _read
from rocell.application.first_motion_contract import canonical
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def main():
    root=Path(__file__).resolve().parents[1]
    exports=root/'runs/wizard-exports'
    prefix='.firmware-tools/configured-diagnostic-candidate-r31/RoArm-M3_example/'
    report,receipt=_read(exports,'wizard-20260920T141911297986Z-959068ada58d4e37bedcec4e80dc9e5a',
                         'attachment-compile-review.json')
    expected={Path(p).name:h for p,h in report['source_hashes'].items()
              if p.replace('\\','/').startswith(prefix)}
    files={p.name:p.read_bytes() for p in (root/prefix).iterdir() if p.is_file()}
    sha=lambda raw:hashlib.sha256(raw).hexdigest()
    if report['status']!='COMPILED' or set(expected)!=set(files) or any(sha(raw)!=expected[n] for n,raw in files.items()):
        raise ValueError('Pinned baseline differs')
    changes={}
    diagnostics=root/'firmware/diagnostics'
    pending=['shoulder_board_session.h','characterization_smoke_board.h']
    seen=set()
    while pending:
        name=pending.pop()
        if name in seen:continue
        seen.add(name)
        raw=(diagnostics/name).read_bytes()
        # Only follow the campaign dependency tree, not inactive historic owners.
        if name!='shoulder_board_session.h':
            pending.extend(n for n in re.findall(r'#include "([\w.-]+)"',raw.decode())
                           if (diagnostics/n).is_file())
        if name=='shoulder_board_session.h':raw=b'#define ROCELL_CHARACTERIZATION_SMOKE 1\n'+raw
        changes[name]=dict(before=sha(files[name]) if name in files else None,after=sha(raw))
        files[name]=raw
    name='configured_pair_board_routes.h'
    before=files[name]
    old=b'  registerShoulderSessionRoutes();'
    anchor=b'  registerHoldDiagnosticRoutes();'
    if before.count(old)!=1 or before.count(anchor)!=1:
        raise ValueError('Unexpected registration ordering')
    files[name]=before.replace(old,b'').replace(anchor,anchor+b'\n  registerShoulderSessionRoutes(); // Shared boot ID must exist before smoke authentication.')
    changes[name]=dict(before=sha(before),after=sha(files[name]))
    target=root/'.firmware-tools/configured-diagnostic-candidate-r33/RoArm-M3_example'
    target.mkdir(parents=True,exist_ok=False)
    for name,raw in files.items():
        with (target/name).open('xb') as stream:stream.write(raw)
        if (target/name).read_bytes()!=raw:raise ValueError('Stage readback failed')
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({'mode':'r33-smoke-stage'},[],attachments={'smoke-stage.json':canonical(dict(
        predecessor_compile_receipt=receipt,changed_files=changes,maximum_legs=1,
        hardware_access=False,uploaded=False,physical_release=False,
        limitation='Encoder limits are not reviewed physical clearance bounds'))})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Stage export failed')
    print(saved['path'])


if __name__=='__main__':main()
