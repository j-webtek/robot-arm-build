"""Host assembly from synthetic retained records; no native enumeration/open."""

from dataclasses import replace
import pytest
from rocell.application.endpoint_binding_assembly import assemble_endpoint_binding
from rocell.application.endpoint_trial_draft import EndpointTrialDraft
from rocell.application.endpoint_reference_reader import ORIGINAL_REFERENCES
from rocell.application.wizard_engineering_review_intake import record_decision
from rocell.application.endpoint_engineering_review import ENGINEERING_DRAFT_CHECKS
from test_endpoint_worker_preparation import setup
from test_endpoint_current_context import fixture


def assembly(tmp_path,monkeypatch):
    workspace,req,_ = setup(tmp_path,monkeypatch)
    draft = EndpointTrialDraft.from_request(req)
    body = req.to_dict()
    originals = tuple((name,(tmp_path/(body['attempt_id']+'-'+name+'.original.json')).read_bytes())
                     for name in sorted(ORIGINAL_REFERENCES))
    receipts = []
    for i,check in enumerate(sorted(ENGINEERING_DRAFT_CHECKS)):
        op = 'operation-'+format(i,'032x')
        report = record_decision({'draft_json':draft.canonical_bytes.decode(),
            'reviewer_id':'synthetic-reviewer','check':check,'decision':'APPROVED',
            'detail':'Synthetic fixture only; no hardware approval.'},root=tmp_path,
            operation_id=op,source_sha256=body['references']['source_sha256'],now_ns=500_000_000)
        receipts.append((op,report['review_sha256']))
    calls = []
    _,samples,_,_ = fixture()
    def metadata_factory(request):
        calls.append('factory')
        def metadata():
            calls.append('metadata')
            return replace(samples[0],finished_monotonic_ns=1_000_000_000)
        return metadata
    kwargs = dict(workspace=workspace,draft=draft,reference_originals=originals,
        review_root=tmp_path,review_selections=tuple(receipts),check_current=lambda:None,
        clock_ns=lambda:1_000_000_000,metadata_factory=metadata_factory)
    return req,kwargs,calls


def test_assembly_is_inert_then_uses_existing_current_context(tmp_path,monkeypatch):
    req,kwargs,calls = assembly(tmp_path,monkeypatch)
    binding = assemble_endpoint_binding(**kwargs)
    assert not calls
    with pytest.raises(ValueError,match='final operator'): binding.operator_reader(req)
    assert set(binding.engineering_reader(req)) == ENGINEERING_DRAFT_CHECKS
    context = binding.context_factory(req)
    assert calls == ['factory']
    result = context()
    assert calls == ['factory','metadata']
    assert result.connection_id == req.to_dict()['attempt_id']
    assert result.references == tuple(sorted(req.to_dict()['references'].items()))


@pytest.mark.parametrize('fault',['missing','hash','build','context','receipts','metadata'])
def test_incomplete_or_changed_assembly_never_acquires_metadata(tmp_path,monkeypatch,fault):
    from rocell.application import endpoint_binding_assembly as module
    from types import SimpleNamespace
    _,kwargs,calls = assembly(tmp_path,monkeypatch)
    if fault == 'missing': kwargs['reference_originals'] = kwargs['reference_originals'][:-1]
    if fault == 'hash':
        rows = kwargs['reference_originals']
        kwargs['reference_originals'] = ((rows[0][0],b'{"changed":true}'),)+rows[1:]
    if fault == 'build': monkeypatch.setattr(module,'import_build_snapshot',lambda _:SimpleNamespace(snapshot_hash='f'*64))
    if fault == 'context': kwargs['check_current'] = lambda:'cancelled'
    if fault == 'receipts': kwargs['review_selections'] = kwargs['review_selections'][:-1]
    if fault == 'metadata': kwargs['metadata_factory'] = None
    with pytest.raises(ValueError): assemble_endpoint_binding(**kwargs)
    assert not calls


def test_later_reference_mutation_is_not_hidden_by_assembly(tmp_path,monkeypatch):
    req,kwargs,calls = assembly(tmp_path,monkeypatch)
    binding = assemble_endpoint_binding(**kwargs)
    path = tmp_path/(req.to_dict()['attempt_id']+'-geometry_sha256.original.json')
    path.write_bytes(b'{"changed":true}')
    with pytest.raises(ValueError): binding.context_factory(req)()
    assert calls == ['factory']
