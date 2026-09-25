"""Explicit private review-key setup; no serial, reviews, permits or motion."""

from rocell.providers.windows.bench_review_key import (
    FILENAME, provision_bench_review_key, load_bench_review_authority, host_key_root,
)


def run_key_setup(workspace, values):
    if set(values)!={'operation','acknowledge'} or values['acknowledge'] is not True:
        raise ValueError('Explicit key setup acknowledgement required')
    if values['operation'] not in {'CHECK','PROVISION'}:
        raise ValueError('Unknown key setup operation')
    root = host_key_root(workspace,create=values['operation']=='PROVISION')
    if root is None: return _report('KEY_NOT_CONFIGURED')
    if not (root/FILENAME).exists():
        if values['operation']=='CHECK': return _report('KEY_NOT_CONFIGURED')
        provision_bench_review_key(root)
    # Existing files are only loaded, never replaced. Failure requires review.
    load_bench_review_authority(root)
    return _report('KEY_AVAILABLE_NO_MOTION_APPROVAL')


def _report(status):
    return {'schema':'rocell.bench_key_setup.v1','status':status,
            'authority_id':'local-bench-review-v1','storage':'CURRENT_USER_PRIVATE_APPDATA',
            'physical_authority':False,'connected':False,'motion_approved':False,
            'note':'Key availability authenticates future reviews, not physical readiness.'}
