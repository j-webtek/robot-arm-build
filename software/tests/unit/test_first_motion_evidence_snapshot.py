"""Frozen commissioning originals, not independent hardware measurements."""
import json
from pathlib import Path

import pytest

from rocell.application import first_motion_evidence_snapshot as module
from rocell.application.first_motion_contract import canonical
from rocell.application.endpoint_reference_reader import source_fingerprint
from rocell.application.endpoint_evidence_snapshot import decode_snapshot as endpoint_decode
from test_first_motion_reference_reader import prepare


def setup(tmp_path):
    workspace=Path(__file__).resolve().parents[3]
    request=prepare(tmp_path,source_fingerprint(workspace),module.import_build_snapshot(workspace).snapshot_hash)
    output=tmp_path/'snapshot'; output.mkdir()
    path=module.prepare_snapshot(workspace,request,reference_root=tmp_path,directory=output)
    return request,path


def test_roundtrip_actual_workspace_with_synthetic_originals(tmp_path):
    request,path=setup(tmp_path)
    raw=path.read_bytes()
    assert set(module.decode_snapshot(raw,request))==module.ORIGINAL_REFERENCES
    with pytest.raises(ValueError): endpoint_decode(raw,request)
    with pytest.raises(Exception):
        module.prepare_snapshot(Path(__file__).resolve().parents[3],request,reference_root=tmp_path,directory=path.parent)
    assert path.read_bytes()==raw


def test_frozen_bytes_do_not_reread_disk(tmp_path,monkeypatch):
    request,path=setup(tmp_path)
    reader=module.FrozenFirstMotionReferences(path.read_bytes(),request)
    monkeypatch.setattr(module,'read_bounded_regular_file',lambda *a,**kw:pytest.fail('Frozen reader accessed disk'))
    assert reader()==tuple(sorted(request.to_dict()['references'].items()))
    assert type(reader.original('independent_posture_review_sha256')) is bytes


@pytest.mark.parametrize('fault',['request','build','original','missing','authority'])
def test_changed_snapshot_refused(tmp_path,fault):
    request,path=setup(tmp_path)
    value=json.loads(path.read_bytes())
    if fault=='request': value['request_sha256']='f'*64
    if fault=='build': value['build_snapshot']['contact_enabled']=True
    if fault=='original': value['originals']['independent_posture_review_sha256']='e30='
    if fault=='missing': value['originals'].pop('independent_posture_review_sha256')
    if fault=='authority': value['physical_authority']=True
    with pytest.raises(ValueError): module.decode_snapshot(canonical(value),request)
