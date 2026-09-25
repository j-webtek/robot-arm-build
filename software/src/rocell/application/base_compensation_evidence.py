"""Read the finite frozen base experiment inputs without opening any device.

Summary files select original training exports only. The proposer rebuilds every
measurement and the model; it never accepts summary endpoint values as evidence.
Prospective prediction hashes are pinned independently of those summaries.
"""
import re

from .physical_onboarding_durability import safe_root, contained_path, read_bounded_regular_file
from .wizard_diagnostic_coordinator import decode_diagnostic_json


HELD_OUT = (
    ('BASE_HELD_OUT_PREDICTION_20260915.json',
     'f67277d71bd7115e0c805820f0bd38c0df627d7220117e2605a6841a70f57908',
     'campaign-5f6f0189cac1462a842f65edc94f2753',
     '1973d6fbc2df1a495858c45c57f312f816704acdff58a06a2306fcc952a53bb6'),
    ('BASE_NEGATIVE_MIDPOINT_PREDICTION_20260915.json',
     '2590a2c2c8e87437a28315c825fc9b305691bb58c08964e8c24e2910bbd017cc',
     'campaign-aee93c474a594f8a8a8987d8baec9e71',
     '03b5a8c4f7684e1d062e958c8965de8cdeef851d1084a7f5bdb052a12640e67d'),
    ('BASE_POSITIVE_MIDPOINT_PREDICTION_20260915.json',
     '071163cc4bd8c85435ddf09773f625285b021f4aec04e3d59a7f741304604b07',
     'campaign-9a7f7c335aaa48668db239ad54c49acf',
     '0a77d6b4f3274c4894ce33e1cd773c0192167bbcb021c287a684c9ee04dbd189'),
)


def load_fixed_base_compensation_evidence(workspace):
    """Return inputs for the rebuilding proposer, not a validated motion permit."""
    root=safe_root(workspace / 'software' / 'runs')
    def read(name):
        return read_bounded_regular_file(contained_path(root,name,label='base experiment evidence'),maximum_bytes=65536)
    def selection(name,digest):
        if (type(name) is not str or not re.fullmatch('campaign-[a-f0-9]{32}',name)
                or type(digest) is not str or not re.fullmatch('[a-f0-9]{64}',digest)):
            raise ValueError('Exact base campaign reference required')
        return dict(directory=str(root/'wizard-exports'/name),
            report_name=name+'-parent-report.json',report_sha256=digest)
    training=[]
    for filename in ('BASE_REPEATABILITY_20260915.json','BASE_FIXED_TARGET_REPETITIONS_20260915.json'):
        summary=decode_diagnostic_json(read(filename),maximum=65536)
        if type(summary) is not dict or type(summary.get('rows')) is not list or len(summary['rows'])!=4:
            raise ValueError('Four original training selections per group required')
        training.extend(selection(r['campaign_id'],r['report_sha256']) for r in summary['rows'])
    held=[dict(export=selection(campaign,digest),prediction_raw=read(filename),prediction_sha256=prediction_hash)
        for filename,prediction_hash,campaign,digest in HELD_OUT]
    return dict(model_raw=read('BASE_LOCAL_MODEL_20260915.json'),
        expected_model_sha256='fa8158f348758829ec29452525ccd97b77c34da97778b4073a031a3677884cb5',
        training_exports=training,held_out=held)
