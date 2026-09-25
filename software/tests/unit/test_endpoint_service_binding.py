"""Service-owned review selection and host wiring with incapable assembly."""

import pytest
from rocell.application.endpoint_trial_draft import EndpointTrialDraft
from rocell.application.endpoint_reference_reader import ORIGINAL_REFERENCES
from rocell.application.endpoint_engineering_review import ENGINEERING_DRAFT_CHECKS
from rocell.application import endpoint_binding_assembly as assembly
from rocell.application.wizard_endpoint_coordinator import EndpointWizardBinding
from rocell.application.wizard_actions import WizardError
from test_arrival_wizard_service import make_service, _run
from test_endpoint_trial_contract import request


def prepared(make_service,monkeypatch,decision='APPROVED'):
    service,runner,_ = make_service(mode='physical')
    draft = EndpointTrialDraft.from_request(request())
    ids = []
    for check in sorted(ENGINEERING_DRAFT_CHECKS):
        completed = _run(service,'record_endpoint_engineering_review',{
            'draft_json':draft.canonical_bytes.decode(),'reviewer_id':'synthetic-reviewer',
            'check':check,'decision':decision,'detail':'Synthetic test only; not hardware evidence.'})
        assert completed['status'] == 'SUCCEEDED'
        ids.append(completed['operation_id'])
    calls = []
    originals = tuple((name,b'{"synthetic":true}') for name in sorted(ORIGINAL_REFERENCES))
    def incapable(**kwargs):
        kwargs['check_current']()
        calls.append(kwargs)
        return EndpointWizardBinding(draft,originals,lambda r:{},lambda r:{},lambda r:lambda:None)
    monkeypatch.setattr(assembly,'assemble_endpoint_binding',incapable)
    return service,runner,draft,tuple(ids),originals,calls


def test_installs_from_own_receipts_without_enumeration_or_motion(make_service,monkeypatch):
    service,runner,draft,ids,originals,calls = prepared(make_service,monkeypatch)
    result = service.configure_endpoint_trial(draft=draft,reference_originals=originals,review_operation_ids=ids)
    assert result['status'] == 'HOST_BOUND_NOT_AUTHORIZED' and result['motion_authorized'] is False
    assert len(calls) == 1 and not runner.calls
    assert calls[0]['review_root'] == service._log.root
    for op,digest in calls[0]['review_selections']:
        assert digest == service._operations[op]['result']['steps'][0]['report']['review_sha256']
    action = next(a for a in service.view()['actions'] if a['action_id']=='run_endpoint_trial')
    assert action['endpoint_draft_sha256'] == draft.draft_sha256
    assert not action['enabled']  # Actual powered/current hardware setup is absent.
    with pytest.raises(WizardError):
        service.configure_endpoint_trial(draft=draft,reference_originals=originals,review_operation_ids=ids)


@pytest.mark.parametrize('decision',['DENIED','UNKNOWN'])
def test_recorded_nonapproval_does_not_assemble(make_service,monkeypatch,decision):
    service,_,draft,ids,originals,calls = prepared(make_service,monkeypatch,decision)
    with pytest.raises(WizardError):
        service.configure_endpoint_trial(draft=draft,reference_originals=originals,review_operation_ids=ids)
    assert not calls and service._endpoint_binding is None


@pytest.mark.parametrize('fault',['duplicate','missing','unknown','attempted','busy'])
def test_bad_selection_or_lifecycle_never_assembles(make_service,monkeypatch,fault):
    service,_,draft,ids,originals,calls = prepared(make_service,monkeypatch)
    if fault == 'duplicate': ids = ids[:-1]+ids[:1]
    if fault == 'missing': ids = ids[:-1]
    if fault == 'unknown': ids = ('operation-'+'f'*32,)+ids[1:]
    if fault == 'attempted': service._endpoint_attempt_id = 'operation-'+'e'*32
    if fault == 'busy': service._running = 'operation-'+'e'*32
    with pytest.raises(WizardError):
        service.configure_endpoint_trial(draft=draft,reference_originals=originals,review_operation_ids=ids)
    assert not calls


def test_post_snapshot_state_guard_is_cheap_and_rejects_replacement(make_service,monkeypatch):
    service,_,draft,ids,originals,calls = prepared(make_service,monkeypatch)
    service.configure_endpoint_trial(draft=draft,reference_originals=originals,review_operation_ids=ids)
    monkeypatch.setattr(service,'_recheck_source',lambda _:pytest.fail('No disk source scan inside snapshot-age window'))
    assert calls[0]['check_current']() is None
    service._endpoint_binding = None
    with pytest.raises(WizardError): calls[0]['check_current']()


def test_public_records_through_real_assembly_remain_non_actuating(make_service,tmp_path,monkeypatch):
    from test_endpoint_worker_preparation import setup as original_fixture
    workspace,req,_ = original_fixture(tmp_path,monkeypatch)
    # Real current source/build hashes, but deliberately synthetic reference
    # meanings and controller fixture. Do not interpret as physical approval.
    _,_,source = make_service()
    source['hash'] = req.to_dict()['references']['source_sha256']
    service,runner,_ = make_service(mode='physical')
    draft = EndpointTrialDraft.from_request(req)
    ids = []
    for check in sorted(ENGINEERING_DRAFT_CHECKS):
        completed = _run(service,'record_endpoint_engineering_review',{
            'draft_json':draft.canonical_bytes.decode(),'reviewer_id':'synthetic-reviewer',
            'check':check,'decision':'APPROVED','detail':'Synthetic integration fixture only.'})
        assert completed['status'] == 'SUCCEEDED'
        ids.append(completed['operation_id'])
    originals = tuple((name,(tmp_path/(req.to_dict()['attempt_id']+'-'+name+'.original.json')).read_bytes())
                     for name in sorted(ORIGINAL_REFERENCES))
    result = service.configure_endpoint_trial(draft=draft,reference_originals=originals,
        review_operation_ids=tuple(ids))
    assert result['motion_authorized'] is False
    assert service._endpoint_binding.draft.canonical_bytes == draft.canonical_bytes
    assert not runner.calls
    assert service._endpoint_attempt_id is None
    assert not next(a for a in service.view()['actions'] if a['action_id']=='run_endpoint_trial')['enabled']
