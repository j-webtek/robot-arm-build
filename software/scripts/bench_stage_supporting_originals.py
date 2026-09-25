"""Extract hash-checked originals from one retained zero-write attempt.

This prepares human-review material, not the eight approved endpoint references.
It cannot convert feedback-only evidence into a motion review or renew presence.
No hardware imports or device access are used.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path

NAMES = frozenset(('firmware_compatibility_review_sha256', 'generic_review_original',
    'native_identity_original_sha256', 'powered_startup_original_sha256',
    'protocol_review_sha256', 'runtime_sha256', 'serial_profile_sha256'))


def unpack(raw):
    if type(raw) is not bytes or len(raw)>512*1024:
        raise ValueError('Bounded prepared-attempt bytes required')
    value = json.loads(raw)
    if value.get('stage') != 'prepared' or value.get('physical_authority') is not False:
        raise ValueError('Unprivileged prepared attempt required')
    body = value['body']
    intent = body['intent']
    if intent['purpose'] != 'POWERED_UNSOLICITED_TELEMETRY_ZERO_WRITE':
        raise ValueError('Only the retained zero-write evidence format is supported')
    originals = body['originals_base64']
    if set(originals) != NAMES:
        raise ValueError('Exact supporting original set required')
    decoded = {}
    for name in sorted(NAMES):
        data = base64.b64decode(originals[name], validate=True)
        if not data or len(data)>128*1024:
            raise ValueError('Supporting original size out of bounds')
        if name != 'generic_review_original':
            if hashlib.sha256(data).hexdigest()!=intent['references'][name]:
                raise ValueError('Retained original digest mismatch')
        decoded[name] = data
    native = json.loads(decoded['native_identity_original_sha256'])
    expected_generic = native['binding']['generic_review_sha256']
    if hashlib.sha256(decoded['generic_review_original']).hexdigest()!=expected_generic:
        raise ValueError('Generic review does not match the retained native association')
    return decoded


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared', type=Path, required=True)
    parser.add_argument('--expected-sha256', required=True)
    parser.add_argument('--output-directory', type=Path, required=True)
    args = parser.parse_args()
    with args.prepared.open('rb') as stream:
        raw = stream.read(512*1024+1)
    digest = hashlib.sha256(raw).hexdigest()
    if digest != args.expected_sha256:
        raise ValueError('Prepared attempt does not match the explicitly selected hash')
    decoded = unpack(raw)
    args.output_directory.mkdir(exist_ok=False)
    rows = []
    for name, data in decoded.items():
        filename = name+'.original.bin'
        with (args.output_directory/filename).open('xb') as stream:
            stream.write(data)
        rows.append({'name': filename, 'bytes': len(data),
                     'sha256': hashlib.sha256(data).hexdigest()})
    index = {'schema': 'rocell.bench_supporting_originals.v1',
             'prepared_attempt_sha256': digest, 'files': rows,
             'physical_authority': False, 'motion_authorized': False,
             'status': 'SUPPORTING_EVIDENCE_ONLY_NOT_ENDPOINT_APPROVALS',
             'limitations': ['Historical timestamps unchanged',
                 'Feedback-only reviews are not motion compatibility approvals',
                 'Hashes establish byte integrity, not physical truth or authorship',
                 'No endpoint controller binding or operator approval was created']}
    with (args.output_directory/'index.json').open('x', encoding='utf-8') as stream:
        json.dump(index, stream, indent=2)
    print(json.dumps(index))


if __name__ == '__main__':
    main()
