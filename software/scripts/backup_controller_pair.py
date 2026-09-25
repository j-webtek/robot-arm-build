"""Authorized backup only: two flash reads on one esptool 4.6 connection.

No write_flash, erase, application-start or servo API is used. Output belongs in
the pre-created private backup directory, never in general wizard exports.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys


def read_pair(esp, directory, size, progress=None):
    """Reserve both host files before I/O; stop on any failure, never retry."""
    paths = [directory / 'flash-pair-a.bin', directory / 'flash-pair-b.bin']
    handles = []
    records = []
    try:
        for path in paths:
            handles.append(path.open('xb'))
        for index, (path, handle) in enumerate(zip(paths, handles), 1):
            callback = (lambda done, total: progress(index, done, total)) if progress else None
            # Vendor stub reader checks stream length and device-provided digest.
            data = esp.read_flash(0, size, callback)
            if len(data) != size:
                raise ValueError('Incomplete flash read')
            digest = hashlib.sha256(data).hexdigest()
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
            handle.close()
            stored = path.read_bytes()
            if len(stored) != size or hashlib.sha256(stored).hexdigest() != digest:
                raise ValueError('Host backup verification failed')
            records.append({'file': path.name, 'bytes': size, 'sha256': digest})
        return {'schema': 'rocell.private_backup_pair.v1', 'copies': records,
                'matching': records[0]['sha256'] == records[1]['sha256'],
                'firmware_deployed': False}
    finally:
        for handle in handles:
            handle.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--authorized-backup', action='store_true', required=True)
    parser.add_argument('--port', required=True)
    parser.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    directory = args.directory.resolve(strict=True)
    private = (root / 'private-backups').resolve(strict=True)
    if not directory.is_dir() or not directory.is_relative_to(private):
        parser.error('Use an existing restricted directory under private-backups')
    if any((directory / name).exists() for name in ('flash-pair-a.bin', 'flash-pair-b.bin', 'pair-report.json')):
        parser.error('Backup output already exists; preserve it')
    sys.path.insert(0, str(root / '.firmware-tools/esptool-api-4.6'))
    import esptool
    import serial
    if esptool.__version__ != '4.6':
        raise ValueError('Unexpected esptool version')
    # Configure line state BEFORE opening; OS/driver transitions remain a risk.
    port = serial.Serial(port=None, baudrate=115200, timeout=3, write_timeout=10)
    port.dtr = False
    port.rts = False
    port.port = args.port
    try:
        port.open()
        esp = esptool.ESP32ROM(port, baud=115200)
        esp.connect('default_reset', attempts=2)
        if esp.secure_download_mode or esp.stub_is_disabled:
            raise ValueError('Controller does not permit this reviewed RAM-helper path')
        mac = ':'.join(f'{value:02x}' for value in esp.read_mac())
        if mac != 'fc:e8:c0:f8:d5:38':
            raise ValueError('Controller MAC mismatch')
        stub = esp.run_stub()
        if stub.flash_id() != 0x164020:
            raise ValueError('Unexpected flash identity')
        print(json.dumps({'event': 'backup_started', 'mac': mac, 'bytes_per_copy': 4194304}), flush=True)
        last = {1: -1, 2: -1}

        def progress(copy, done, total):
            bucket = done // (256 * 1024)
            if bucket != last[copy]:
                last[copy] = bucket
                print(json.dumps({'copy': copy, 'bytes_read': done, 'total': total}), flush=True)

        report = read_pair(stub, directory, 4194304, progress)
        with (directory / 'pair-report.json').open('x', encoding='utf-8') as output:
            json.dump(report, output, indent=2)
            output.flush()
            os.fsync(output.fileno())
        print(json.dumps(report), flush=True)
        if not report['matching']:
            raise ValueError('Independent flash reads differ')
    finally:
        # Do not deliberately reset or run the application on success OR failure.
        # Closing the Windows handle does not prove pin levels/runtime state.
        port.close()


if __name__ == '__main__':
    main()
