"""Frozen snapshot integrity, not physical pin/approval qualification."""

import json
from pathlib import Path
import pytest
from rocell.application import endpoint_evidence_snapshot as module
from rocell.application.arm_bench_qualification_contract import _canonical
from rocell.application.endpoint_reference_reader import source_fingerprint
from test_endpoint_reference_reader import prepare


def setup(tmp_path):
    workspace = Path(__file__).resolve().parents[3]
    req = prepare(tmp_path,source_fingerprint(workspace),module.import_build_snapshot(workspace).snapshot_hash)
    output = tmp_path/'snapshot'
    output.mkdir()
    path = module.prepare_snapshot(workspace,req,reference_root=tmp_path,directory=output)
    return req,path


def test_actual_workspace_snapshot_roundtrip_and_no_overwrite(tmp_path):
    req,path = setup(tmp_path)
    raw = path.read_bytes()
    originals = module.decode_snapshot(raw,req)
    assert set(originals)==module.ORIGINAL_REFERENCES
    assert all(type(v) is bytes for v in originals.values())
    workspace = Path(__file__).resolve().parents[3]
    with pytest.raises(Exception): module.prepare_snapshot(workspace,req,reference_root=tmp_path,directory=path.parent)
    assert path.read_bytes()==raw


def test_frozen_reference_reader_needs_no_filesystem_after_validation(tmp_path,monkeypatch):
    req,path = setup(tmp_path)
    reader = module.FrozenEndpointReferences(path.read_bytes(),req)
    monkeypatch.setattr(module,'read_bounded_regular_file',lambda *a,**k:pytest.fail('No frozen-reader disk access'))
    assert reader()==tuple(sorted(req.to_dict()['references'].items()))
    assert type(reader.original('geometry_sha256')) is bytes


@pytest.mark.parametrize('field',['request','build','original','missing','authority'])
def test_changed_snapshot_refused(tmp_path,field):
    req,path = setup(tmp_path)
    value = json.loads(path.read_bytes())
    if field=='request': value['request_sha256']='f'*64
    if field=='build': value['build_snapshot']['contact_enabled']=True
    if field=='original': value['originals']['geometry_sha256']='e30='
    if field=='missing': value['originals'].pop('geometry_sha256')
    if field=='authority': value['physical_authority']=True
    with pytest.raises(ValueError): module.decode_snapshot(_canonical(value),req)
