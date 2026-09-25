"""Derive a private app-slot recovery artifact from the verified backup; no I/O to hardware."""
import hashlib
import json
import os
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    private = root / 'private-backups/controller-20260918-session1'
    a = (private / 'flash-pair-a.bin').read_bytes()
    b = (private / 'flash-pair-b.bin').read_bytes()
    expected = 'd9e3de5cf3738b18144697095534ec9a33e531a6cd5062f68b85b5a29f6df2b9'
    if len(a) != 4194304 or a != b or hashlib.sha256(a).hexdigest() != expected:
        raise ValueError('Backup pair changed')
    region = a[0x10000:0x150000]
    digest = hashlib.sha256(region).hexdigest()
    destination = private / 'original-app0-slot.bin'
    with destination.open('xb') as output:
        output.write(region)
        output.flush()
        os.fsync(output.fileno())
    if destination.read_bytes() != region:
        raise ValueError('Recovery artifact verification failed')
    print(json.dumps({'file': destination.name, 'offset': '0x10000',
                      'bytes': len(region), 'sha256': digest,
                      'restoration_exercised': False, 'hardware_access': False}))


if __name__ == '__main__':
    main()
