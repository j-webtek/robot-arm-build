"""Offline receipt faults must not become permission to use a stale boot."""
import base64
import hashlib
import pytest
from rocell.application import r10_provisioned_evidence as evidence
from rocell.application.first_motion_contract import canonical


@pytest.fixture
def receipts(monkeypatch):
    plan=dict(schema='rocell.pair-settings_provisioning_review.v1',
        source_sha256=evidence.SOURCE,candidate_sha256=evidence.CANDIDATE,
        policy_sha256=evidence.SETTINGS,settings_sha256=evidence.SETTINGS,
        hold_policy_sha256=evidence.POLICY,existing_entries_preserved=6,
        remount_verified=True,startup_authorized=True,motion_authorized=False,
        existing_key_preserved=True,device_path='/rocell-pair.json',key_generated=False)
    write=dict(schema='rocell.pair-settings_provisioning_result.v1',status='FLASH_READBACK_VERIFIED',
        candidate_sha256=evidence.CANDIDATE,source_sha256=evidence.SOURCE,
        protected_regions_unchanged=True,recovery_preserved=True,retry_allowed=False,
        startup_attempted=False,configuration_loaded=False,motion_authorized=False,plan_export_id=evidence.PLAN)
    run=dict(write,startup_attempted=True,application_health_verified=False,verified_write_export_id=evidence.WRITE)
    status=dict(schema='rocell.hold_transport.v1',instance_id=evidence.BOOT,
        state='IDLE',reason='NOT_CONFIGURED',records=0,storage_fault=False)
    capabilities=dict(schema='rocell.held_pair_capabilities.v1',boot_id=evidence.BOOT,
        protocol='hold-first-pair-v1',servo_id=14,max_offset_counts=16,
        free_internal_heap_bytes=228228,minimum_free_internal_heap_bytes=224376,
        largest_internal_block_bytes=110580,stack_measured=False,physical_accuracy_verified=False)
    def response(path, value):
        raw=canonical(value)
        return dict(path=path,raw_base64=base64.b64encode(raw).decode(),sha256=hashlib.sha256(raw).hexdigest())
    health=dict(schema='rocell.r10_startup_observation.v1',address=evidence.ADDRESS,
        status='IDLE_AND_PAIR_PROTOCOL_OBSERVED',challenge_requested=False,servo_commands_sent=False,
        provisioning_performed=False,reset_performed=False,retry_allowed=False,hold_status=status,
        responses=[response('/rocell/diagnostics/status',status),
            response('/rocell/held-pair/capabilities',capabilities),response('/rocell/diagnostics/status',status)])
    docs={evidence.PLAN:plan,evidence.WRITE:write,evidence.RUN:run,evidence.HEALTH:health}
    monkeypatch.setattr(evidence,'review_pair_installation',lambda root:{'hardware_access':False})
    monkeypatch.setattr(evidence,'_read',lambda root,identity,name:(docs[identity],hashlib.sha256(canonical(docs[identity])).hexdigest()))
    return docs


def test_exact_receipts_are_retained_evidence_not_live_permission(receipts,tmp_path):
    result=evidence.review_provisioned_r10(tmp_path)
    assert result['expected_boot']==evidence.BOOT
    assert result['hardware_access'] is False
    assert result['current_boot_verified'] is False
    assert result['motion_authorized'] is False


@pytest.mark.parametrize('fault',['candidate','preservation','key','source','write_startup',
    'run_link','run_extra','status_boot','raw_hash','response_count','response_path','servo_command'])
def test_rejects_inconsistent_evidence(receipts,tmp_path,fault):
    plan,write,run,health=[receipts[key] for key in (evidence.PLAN,evidence.WRITE,evidence.RUN,evidence.HEALTH)]
    if fault=='candidate':plan['candidate_sha256']='0'*64
    if fault=='preservation':plan['existing_entries_preserved']=5
    if fault=='key':plan['existing_key_preserved']=1
    if fault=='source':write['source_sha256']='0'*64
    if fault=='write_startup':write['startup_attempted']=True
    if fault=='run_link':run['verified_write_export_id']='wrong'
    if fault=='run_extra':run['automatic_retry']=True
    if fault=='status_boot':health['hold_status']['instance_id']='0'*32
    if fault=='raw_hash':health['responses'][0]['sha256']='0'*64
    if fault=='response_count':health['responses'].pop()
    if fault=='response_path':health['responses'][1]['path']='/wrong'
    if fault=='servo_command':health['servo_commands_sent']=True
    with pytest.raises(ValueError):evidence.review_provisioned_r10(tmp_path)
