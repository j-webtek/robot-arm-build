"""Offline app/partition/stack-frame review; never communicates with hardware."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('revision', type=int, choices=(5, 6))
    parser.add_argument('compile_export_id')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    exports = root / 'runs/wizard-exports'
    compile_report, _ = _read(exports, args.compile_export_id, 'attachment-compile-review.json')
    target = f'configured-diagnostic-candidate-r{args.revision}'
    if (compile_report['status'] != 'COMPILED' or compile_report['target'] != target or
            compile_report['build_profile'] != 'default-4mb-no-psram'):
        raise ValueError('Matching successful compile evidence required')
    tools = root / '.firmware-tools'
    build = tools / ('build-' + target + '--default-4mb-no-psram')
    artifacts = {}
    for name, expected in compile_report['artifact_hashes'].items():
        if Path(name).name != name: raise ValueError('Invalid artifact name')
        raw = (build / name).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != expected: raise ValueError('Build artifact changed')
        artifacts[name] = dict(sha256=digest, bytes=len(raw))
    sketch = tools / target / 'RoArm-M3_example'
    for path in sketch.iterdir():
        if path.suffix not in ('.h', '.ino'): continue
        expected = compile_report['source_hashes'][str(path.relative_to(root))]
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Candidate source changed after compile')
    prefix = 'RoArm-M3_example.ino'
    if artifacts[prefix + '.partitions.bin']['sha256'] != '148b959cbff1c38aa8e1d5c0ba9d612c54997b945e56a63f41223eef650653a1':
        raise ValueError('Partition compatibility mismatch')
    if artifacts[prefix + '.bootloader.bin']['sha256'] != 'b22f373e6194a62505034bbcd2828ab5eaa0fba62f3e4198fb7ae677c1d2f6f7':
        raise ValueError('Bootloader profile mismatch')
    length = artifacts[prefix + '.bin']['bytes']
    if not 0 < length <= 0x140000: raise ValueError('App does not fit installed app0 slot')
    elf = build / (prefix + '.elf')
    objdump = tools / 'data/packages/esp32/tools/esp-x32/2302/bin/xtensa-esp32-elf-objdump.exe'
    output = subprocess.run([str(objdump), '-d', '-C', str(elf)],
        capture_output=True, text=True, check=True, timeout=60).stdout
    wanted = ('ControllerStartupConfigParser::parse(', 'StartupPlanStructure::parse(',
              'rocellPrepareChallenge()', 'ConfiguredStartupRuntime<')
    frames = []
    current = None
    for line in output.splitlines():
        symbol = re.match(r'^[0-9a-f]+ <(.+)>:$', line)
        if symbol: current = symbol.group(1)
        entry = re.search(r'\bentry\s+a1,\s*(0x[0-9a-f]+|[0-9]+)', line)
        if entry and current and any(name in current for name in wanted):
            frames.append(dict(symbol=current, frame_bytes=int(entry.group(1), 0)))
            current = None
    if not any('ControllerStartupConfigParser::parse(' in frame['symbol'] for frame in frames):
        raise ValueError('Startup parser stack-frame evidence missing')
    report = dict(schema='rocell.startup_candidate_review.v1', target=target,
        compile_export_id=args.compile_export_id, artifacts=artifacts,
        app_offset=0x10000, app_slot_bytes=0x140000,
        erase_end_exclusive=0x10000 + ((length + 4095)//4096)*4096,
        partition_profile_matches=True, elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),
        objdump_sha256=hashlib.sha256(objdump.read_bytes()).hexdigest(), stack_frames=frames,
        complete_stack_bound_proved=False, live_heap_headroom_verified=False,
        device_modified=False, deployment_authorized=False,
        limitations=['Individual frames are not worst-case call-chain stack use.',
                    'Compile success does not verify live heap, network or servo behavior.',
                    'Installed image identity must be rechecked before any approved write.'])
    exporter = WizardDiagnosticExporter(exports); exporter.prepare(create=True)
    saved = exporter.export({'mode': 'startup-candidate-offline-review'}, [],
        attachments={'startup-candidate-review.json': canonical(report)})
    if not verify_export(Path(saved['path']))['valid']: raise ValueError('Review export failed')
    print(json.dumps(dict(export=saved['path'], stack_frames=frames,
        app_bytes=length, erase_end_exclusive=report['erase_end_exclusive'], verified=True)))


if __name__ == '__main__': main()
