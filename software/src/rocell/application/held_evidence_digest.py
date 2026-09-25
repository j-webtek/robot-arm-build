"""Identity of raw controller records, without reserializing their JSON.

This is not an arrival assessment, a signature or proof of hardware provenance.
The host must retain these exact bytes and separately replay the parsed records.
"""
import hashlib

DOMAIN = b'rocell.held-evidence-chain.v1\0'
KINDS = frozenset(('held_leg_scan', 'held_leg_action', 'held_leg_end'))


def held_evidence_digest(records):
    """Hash ordered (storage-kind, raw-JSON-bytes) pairs, matching native code."""
    if not isinstance(records, (list, tuple)) or not 1 <= len(records) <= 34:
        raise ValueError('Expected 1..34 raw evidence records')
    digest = hashlib.sha256(DOMAIN).digest()
    for index, record in enumerate(records):
        if not isinstance(record, (list, tuple)) or len(record) != 2:
            raise ValueError('Expected kind and raw bytes')
        kind, raw = record
        if not isinstance(kind, str) or kind not in KINDS:
            raise ValueError('Unknown storage kind')
        if not isinstance(raw, bytes) or not 1 <= len(raw) < 4096 or b'\0' in raw:
            raise ValueError('Expected bounded NUL-free raw bytes')
        encoded = kind.encode('ascii')
        digest = hashlib.sha256(digest + index.to_bytes(2, 'big') +
                                bytes([len(encoded)]) + encoded +
                                len(raw).to_bytes(2, 'big') + raw).digest()
    return digest.hex()
