"""Build a host validator bound to reviewed app source. No device access."""
import hashlib
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from rocell.application.first_motion_contract import canonical
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


APP_SHA = '5d1e081a1b33ddf9eb85a248112c6d18484e04417a1b87042f805875414ba481'
BUILD_EXPORT = 'wizard-20260918T121159084880Z-c4061a611eba4557a6732828f0dbaf2e'
R6_APP_SHA = '71447b72f1488954ece0f6e9d95ca6ec3fc14b45982a10d65a96d3caa3691526'
R6_BUILD_EXPORT = 'wizard-20260918T151815541742Z-e59178a1371b488fbfca4dd48490450d'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_sources(root, report, revision=2):
    if revision not in (2,6):raise ValueError('Unreviewed validator revision')
    expected=APP_SHA if revision==2 else R6_APP_SHA
    if (report.get('status') != 'COMPILED' or
            report.get('artifact_hashes', {}).get('RoArm-M3_example.ino.bin') != expected):
        raise ValueError('Wrong application build evidence')
    sketch = root / f'.firmware-tools/configured-diagnostic-candidate-r{revision}/RoArm-M3_example'
    sources = report['source_hashes']
    checked = {}
    if revision==6:
        recorded={Path(name).name for name in sources if Path(name).parent==sketch.relative_to(root)
                  and Path(name).suffix=='.h'}
        if recorded!={path.name for path in sketch.glob('*.h')}:
            raise ValueError('Candidate header inventory differs from reviewed build')
        for candidate in sorted(sketch.glob('*.h')):
            if sources.get(str(candidate.relative_to(root)))!=digest(candidate):
                raise ValueError('Candidate differs from reviewed startup build')
            checked[candidate.name]=digest(candidate)
        if 'controller_startup_config.h' not in checked:raise ValueError('Startup parser missing')
        return checked
    # Only the approved build's header set belongs to this validator. New,
    # uninstalled feature headers must neither expand nor invalidate that set.
    recorded_headers = [Path(name).name for name in sources
                        if Path(name).parent == Path('firmware/diagnostics')
                        and Path(name).suffix == '.h']
    for name in sorted(recorded_headers):
        header = root / 'firmware/diagnostics' / name
        candidate = sketch / header.name
        for path in (header, candidate):
            name = str(path.relative_to(root))
            if sources.get(name) != digest(path):
                raise ValueError('Diagnostic source differs from approved build: ' + header.name)
        if digest(header) != digest(candidate):
            raise ValueError('Host and installed parser source differ')
        checked[header.name] = digest(header)
    if 'controller_diagnostic_config.h' not in checked:
        raise ValueError('Policy parser source missing')
    return checked


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision',type=int,choices=(2,6),default=2)
    revision=parser.parse_args().revision
    app_sha=APP_SHA if revision==2 else R6_APP_SHA
    build_export=BUILD_EXPORT if revision==2 else R6_BUILD_EXPORT
    root = Path(__file__).resolve().parents[1]
    evidence = root / 'runs/wizard-exports' / build_export
    if not verify_export(evidence)['valid']:
        raise ValueError('Build export integrity failure')
    report = json.loads((evidence / 'attachment-compile-review.json').read_bytes())
    checked = verify_sources(root, report, revision)
    compiler = shutil.which('clang++')
    if not compiler:
        raise ValueError('Host compiler required')
    # Unique directory preserves all older reviewed executables and manifests.
    directory = Path(tempfile.mkdtemp(prefix='bound-policy-validator-',
                                      dir=root / '.firmware-tools'))
    executable = directory / 'validate.exe'
    wrapper = root / 'firmware/diagnostics' / ('validate_provisioning_policy.cpp' if revision==2 else 'validate_startup_provisioning_policy.cpp')
    includes = root / '.firmware-tools/user/libraries/ArduinoJson/src'
    dependencies = {str(p.relative_to(includes)): digest(p)
                    for p in sorted(includes.rglob('*')) if p.is_file()}
    wrapper_hash = digest(wrapper)
    command = [compiler, '-std=c++14', '-Wall', '-Wextra', '-Werror',
               '-I' + str(includes), str(wrapper), '-o', str(executable)]
    if revision==6:
        command.insert(1,'-I'+str(root/'.firmware-tools/configured-diagnostic-candidate-r6/RoArm-M3_example'))
    subprocess.run(command, check=True, capture_output=True, timeout=60)
    if verify_sources(root, report, revision) != checked or digest(wrapper) != wrapper_hash:
        raise ValueError('Source changed during compilation')
    if dependencies != {str(p.relative_to(includes)): digest(p)
                        for p in sorted(includes.rglob('*')) if p.is_file()}:
        raise ValueError('Library changed during compilation')
    result = dict(schema='rocell.bound_policy_validator.v1', app_sha256=app_sha,
        executable=str(executable), executable_sha256=digest(executable),
        wrapper_sha256=wrapper_hash, source_hashes=checked,
        arduinojson_current_hashes=dependencies,
        library_historical_hash_binding=False,
        limitation='Original build recorded ArduinoJson version, not per-file hashes.',
        compiler_sha256=digest(Path(compiler)), build_export=build_export,
        hardware_access=False, provisioning_authority=False)
    exporter = WizardDiagnosticExporter(root / 'runs/wizard-exports')
    exporter.prepare(create=True)
    receipt = exporter.export({'mode': 'host-validator-build'}, [],
                              attachments={'validator-build.json': canonical(result)})
    if not verify_export(Path(receipt['path']))['valid']:
        raise ValueError('Validator build export failure')
    print(json.dumps({'executable': str(executable), 'sha256': digest(executable),
                      'export': receipt['path'], 'source_binding_verified': True,
                      'historical_library_hash_binding': False}))


if __name__ == '__main__':
    main()
