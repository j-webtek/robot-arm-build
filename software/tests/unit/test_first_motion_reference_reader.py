"""Actual bounded reference reads, with synthetic supporting originals."""
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from rocell.application import endpoint_reference_reader as shared
from rocell.application.first_motion_reference_reader import FirstMotionReferenceReader, ORIGINAL_REFERENCES
from rocell.application.first_motion_contract import FirstMotionRequest, canonical
from rocell.application.physical_onboarding_durability import PhysicalOnboardingDurabilityError
from test_first_motion_measurement_binding import setup


def prepare(tmp_path, source, build):
    _, request = setup(tmp_path)
    data = request.to_dict()
    data['references']['source_sha256'] = source
    data['references']['build_snapshot_sha256'] = build
    for name in ORIGINAL_REFERENCES:
        raw = canonical({'schema':'synthetic.original.v1','name':name})
        data['references'][name] = hashlib.sha256(raw).hexdigest()
        (tmp_path/(data['attempt_id']+'-'+name+'.original.json')).write_bytes(raw)
    return FirstMotionRequest(canonical(data))


@pytest.mark.parametrize('fault',[None,'source','build','original','missing','oversized'])
def test_current_originals_reconstructed_or_refused(tmp_path,monkeypatch,fault):
    request = prepare(tmp_path,'a'*64,'b'*64)
    monkeypatch.setattr(shared,'source_fingerprint',lambda _: 'f'*64 if fault=='source' else 'a'*64)
    monkeypatch.setattr(shared,'import_build_snapshot',lambda _:SimpleNamespace(snapshot_hash='f'*64 if fault=='build' else 'b'*64))
    path = tmp_path/(request.to_dict()['attempt_id']+'-swept_clearance_review_sha256.original.json')
    if fault=='original': path.write_bytes(b'{"changed":true}')
    if fault=='missing': path.unlink()
    if fault=='oversized': path.write_bytes(b'x'*(128*1024+1))
    reader = FirstMotionReferenceReader(request,workspace=tmp_path,reference_root=tmp_path)
    if fault:
        with pytest.raises((ValueError,OSError,PhysicalOnboardingDurabilityError)): reader()
    else:
        assert reader()==tuple(sorted(request.to_dict()['references'].items()))
    with pytest.raises(ValueError): shared.EndpointReferenceReader(request,workspace=tmp_path,reference_root=tmp_path)


def test_real_workspace_source_and_build_reconstruction(tmp_path):
    workspace = Path(__file__).resolve().parents[3]
    source = shared.source_fingerprint(workspace)
    build = shared.import_build_snapshot(workspace).snapshot_hash
    request = prepare(tmp_path,source,build)
    observed = dict(FirstMotionReferenceReader(request,workspace=workspace,reference_root=tmp_path)())
    assert observed['source_sha256']==source and observed['build_snapshot_sha256']==build
