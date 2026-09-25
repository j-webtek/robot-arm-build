import base64
import json
import pytest
from test_wrist_correction_process_finalization import inputs
from rocell.application.wrist_correction_process_finalization import finalize_correction_process
from rocell.application.wrist_correction_export import export_correction_run
from rocell.application.wrist_correction_parent_retention import retain_correction_parent_result
from rocell.application.first_motion_contract import canonical
from rocell.providers.windows.wrist_correction_native_protocol import digest
from rocell.application.wrist_correction_export_validation import validate_correction_export


def test_export_retains_originals_and_can_reconstruct_request(tmp_path,monkeypatch):
    request,process,args,kernel=inputs(tmp_path,monkeypatch)
    finalized=finalize_correction_process(request,process,**args)
    destination=tmp_path/'exports';destination.mkdir()
    before={p.name:p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    path,report=export_correction_run(request,process,export_root=destination)
    assert base64.b64decode(report['request']['base64'])==request
    assert not report['replay_allowed']
    assert report['schema']=='rocell.wrist_correction_export.v2'
    for suffix in ('final-capture-claim','final-capture.original','final-reservation','final-consumed'):
        assert any(row['source_relative'].endswith('-'+suffix+'.json') and row['status']=='RETAINED' for row in report['artifacts'])
    assert any(row['source_relative']==finalized['verdict_retention']['file'] and row['status']=='RETAINED' for row in report['artifacts'])
    for row in report['artifacts']:
        if row['status']=='RETAINED':
            raw=(path.parent/row['file']).read_bytes()
            assert digest(raw)==row['sha256'] and len(raw)==row['bytes']
    assert before=={p.name:p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    assert len(kernel.writes)==1
    assert validate_correction_export(path.parent)['integrity_valid']
    with pytest.raises(FileExistsError): export_correction_run(request,process,export_root=destination)


def test_missing_artifacts_are_visible_not_invented(tmp_path):
    from test_wrist_correction_parent_retention import inputs as failed_inputs
    wire,process=failed_inputs(tmp_path)
    destination=tmp_path/'exports';destination.mkdir()
    path,report=export_correction_run(canonical(wire),process,export_root=destination)
    assert not report['artifact_roster_complete']
    assert all(item['status']=='MISSING' for item in report['artifacts'])
    assert json.loads(path.read_bytes())['process']['primary_error']=='TIMED_OUT'
    integrity=validate_correction_export(path.parent)
    assert integrity['integrity_valid'] and not integrity['artifact_roster_complete']
    assert not integrity['endpoint_verified'] and not integrity['replay_allowed']


def portable_fixture(tmp_path):
    from test_wrist_correction_parent_retention import inputs as failed_inputs
    wire,process=failed_inputs(tmp_path)
    (tmp_path/(wire['attempt_id']+'-wrist-correction-plan-review.json')).write_bytes(b'{}')
    destination=tmp_path/'exports';destination.mkdir()
    return export_correction_run(canonical(wire),process,export_root=destination)


def test_portable_validation_reads_only_copied_bundle(tmp_path,monkeypatch):
    import shutil
    from rocell.application import wrist_correction_export_validation as validator
    path,_=portable_fixture(tmp_path)
    copied=tmp_path/'copied';shutil.copytree(path.parent,copied)
    before={p.name:p.read_bytes() for p in copied.iterdir()}
    read=validator.read_bounded_regular_file
    def local_only(path,**kwargs):
        assert path.parent==copied
        return read(path,**kwargs)
    monkeypatch.setattr(validator,'read_bounded_regular_file',local_only)
    report=validator.validate_correction_export(copied)
    assert report['integrity_valid'] and not report['physical_provenance_verified']
    assert before=={p.name:p.read_bytes() for p in copied.iterdir()}


@pytest.mark.parametrize('fault',['artifact','path','roster','total','completeness','stream','authority'])
def test_portable_validation_rejects_changed_bundle(tmp_path,fault):
    path,body=portable_fixture(tmp_path)
    retained=next(row for row in body['artifacts'] if row['status']=='RETAINED')
    if fault=='artifact': (path.parent/retained['file']).write_bytes(b'changed')
    elif fault=='path': retained['file']='../outside.json'
    elif fault=='roster': body['artifacts'].pop()
    elif fault=='total': body['total_artifact_bytes']+=1
    elif fault=='completeness': body['artifact_roster_complete']=True
    elif fault=='stream': body['stdout']['retained_sha256']='0'*64
    else: body['replay_allowed']=True
    path.write_bytes(canonical(body))
    with pytest.raises((ValueError,OSError)):
        validate_correction_export(path.parent)


def test_truncated_stream_is_integrity_checked_but_not_complete(tmp_path):
    from dataclasses import replace
    from test_wrist_correction_parent_retention import inputs as failed_inputs
    wire,process=failed_inputs(tmp_path)
    destination=tmp_path/'exports';destination.mkdir()
    path,body=export_correction_run(canonical(wire),replace(process,stdout=b'x'*(300*1024)),export_root=destination)
    report=validate_correction_export(path.parent)
    assert report['integrity_valid'] and not report['streams_complete']
    del body['stdout']['retained_sha256']
    path.write_bytes(canonical(body))
    with pytest.raises(ValueError,match='Legacy truncated'):
        validate_correction_export(path.parent)


def test_validation_cli_reports_integrity_not_endpoint_success(tmp_path,capsys):
    from rocell.application.wrist_correction_export_validation import main
    path,_=portable_fixture(tmp_path)
    assert main([str(path.parent)])==0
    assert json.loads(capsys.readouterr().out)['endpoint_verified'] is False
    path.write_bytes(b'{}')
    assert main([str(path.parent)])==1
    assert json.loads(capsys.readouterr().out)['integrity_valid'] is False


def test_legacy_v1_roster_remains_portably_valid(tmp_path):
    from rocell.application.wrist_correction_export import correction_artifact_roster
    from rocell.providers.windows.wrist_correction_native_protocol import decode_request
    path,body=portable_fixture(tmp_path)
    # A prior incomplete export uses the unchanged v1 roster. Copies must be
    # renamed in roster order; no paths from the embedded request are followed.
    wire=decode_request(base64.b64decode(body['request']['base64']))
    body['schema']='rocell.wrist_correction_export.v1'
    body['artifacts']=[dict(source_relative=name,status='MISSING') for name,_ in correction_artifact_roster(wire)]
    body['total_artifact_bytes']=0
    path.write_bytes(canonical(body))
    assert validate_correction_export(path.parent)['integrity_valid']
