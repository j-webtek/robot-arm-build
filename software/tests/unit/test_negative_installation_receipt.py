import copy
import json
import pytest
from rocell.application import negative_pair_provisioning as module
from rocell.application import product_ghost_export_review as reads
from rocell.application import physical_onboarding_durability as durability
from rocell.application.r10_provisioned_evidence import CANDIDATE,POLICY


@pytest.mark.parametrize('fault',[None,'incomplete','candidate','settings','write','journal_link','extra'])
def test_completed_direction_receipt_required(tmp_path,monkeypatch,fault):
    candidate='d1c041bcb4e90082685babc16698bcef3c639d87464932d6534d8056b71ce3aa'
    final=dict(schema='rocell.negative-pair_provisioning_result.v1',status='FLASH_READBACK_VERIFIED',
        candidate_sha256=candidate,source_sha256=CANDIDATE,protected_regions_unchanged=True,
        recovery_preserved=True,retry_allowed=False,startup_attempted=True,configuration_loaded=False,
        motion_authorized=False,application_health_verified=False,plan_export_id='plan',verified_write_export_id='write')
    written=copy.deepcopy(final)
    written.pop('verified_write_export_id');written.pop('application_health_verified');written['startup_attempted']=False
    plan=dict(schema='rocell.negative-pair_provisioning_review.v1',
        settings_sha256='471898fe914f0843bdd88556b98aa1277c29d672c628df5892bd5bd849a8f314',
        hold_policy_sha256=POLICY,candidate_sha256=candidate,source_sha256=CANDIDATE,
        remount_verified=True,existing_key_preserved=True)
    rows=[dict(stage=s) for s in ['RESERVED','PREWRITE_VERIFIED','WRITE_ATTEMPT_STARTED',
        'FLASH_READBACK_VERIFIED','RESULT_EXPORTED','ONE_STARTUP_ATTEMPT','STARTUP_RESET_SENT']]
    rows[0].update(app_sha256=module.APP_SHA256,candidate_sha256=candidate,plan_export_id='plan')
    rows[4]['export_id']='write'
    if fault=='incomplete':rows.pop()
    if fault=='candidate':final['candidate_sha256']='0'*64
    if fault=='settings':plan['settings_sha256']='0'*64
    if fault=='write':written['protected_regions_unchanged']=False
    if fault=='journal_link':rows[4]['export_id']='other'
    if fault=='extra':rows.append(dict(stage='ONE_STARTUP_ATTEMPT'))
    docs={'final':final,'plan':plan,'write':written}
    monkeypatch.setattr(reads,'_read',lambda root,ident,name:(docs[ident],'a'*64))
    monkeypatch.setattr(durability,'read_bounded_regular_file',lambda *a,**k:
        b'\n'.join(json.dumps(row).encode() for row in rows))
    if fault:
        with pytest.raises(ValueError):module.review_negative_installation(tmp_path,'final')
    else:assert module.review_negative_installation(tmp_path,'final')['offset_counts']==-6
