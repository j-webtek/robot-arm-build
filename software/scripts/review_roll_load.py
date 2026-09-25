"""Offline raw-field comparison; never connects to hardware or fits a model."""
import argparse
import base64
import hashlib
import json
import math
from pathlib import Path

from review_wifi_roll_export import review


def summarize_samples(samples):
    """Hash-check original successful bodies; missing fields stay missing.

    tR is retained as a raw field, with no assumed engineering units. Failed
    requests are counted separately, never filled from the preceding sample.
    """
    values = []
    successful = 0
    for sample in samples:
        if sample.get('status') != 'SUCCEEDED':
            continue
        raw = base64.b64decode(sample['response_base64'], validate=True)
        if hashlib.sha256(raw).hexdigest() != sample['response_sha256']:
            raise ValueError('Original response hash mismatch')
        body = json.loads(raw)
        successful += 1
        if 'tR' in body:
            value = body['tR']
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError('Invalid raw tR field')
            values.append(value)
    return dict(successful_samples=successful, failed_samples=len(samples)-successful,
                field_samples=len(values), missing_field_samples=successful-len(values),
                raw_tR_min=min(values) if values else None,
                raw_tR_max=max(values) if values else None,
                raw_tR_mean=sum(values)/len(values) if values else None)


def analyze(path):
    """Replay endpoint/hold evidence first, including incomplete-hold status."""
    path = Path(path).resolve()
    result = review(path)
    reports = []
    for item in json.loads((path/'manifest.json').read_bytes())['files']:
        name = item['name']
        if name.startswith('attachment-result-') and name.endswith('.json'):
            reports.extend(step['report'] for step in
                           json.loads((path/name).read_bytes()).get('steps', [])
                           if 'report' in step)
    movement = next(r for r in reports if 'outcome' in r)
    hold = next(r for r in reports if 'samples' in r)
    return dict(export_id=result['export_id'],
                manifest_sha256=result['manifest_file_sha256'],
                command_deg=math.degrees(result['command']['rad']),
                final_deg=result.get('final_deg'),
                full_validation_success=result['full_validation_success'],
                endpoint=summarize_samples(movement['outcome']['feedback_originals']),
                hold=summarize_samples(hold['samples']),
                units_verified=False, model_fitted=False, motion_authorized=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('exports', nargs='+', type=Path)
    args = parser.parse_args()
    print(json.dumps([analyze(path) for path in args.exports], indent=2))
