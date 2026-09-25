import json
import pytest
from rocell.application import held_pair_installation_evidence as evidence
from rocell.application.first_motion_contract import canonical


def rows():
    return [dict(stage='RESERVED',app_sha256=evidence.R10_APP_SHA256,offset=65536,bytes=evidence.APP_BYTES),
        dict(stage='IDENTITY_AND_PREWRITE_VERIFIED',mac='fc:e8:c0:f8:d5:38'),
        dict(stage='WRITE_ATTEMPT_STARTED'),
        dict(stage='FLASH_VERIFIED',app_sha256=evidence.R10_APP_SHA256,protected_regions_unchanged=True),
        dict(stage='ONE_STARTUP_ATTEMPT'),dict(stage='STARTUP_RESET_SENT',application_health_verified=False)]


def encoded(items):return b'\n'.join(canonical(row) for row in items)+b'\n'


@pytest.mark.parametrize('selected_revision',[11,12,13,14,16,23,26,27,28,29,31,33,34,37,38,39,40,41,42,43,44,45,46,47,48,49,50,61])
def test_new_journal_cannot_be_confused_with_r10(selected_revision):
    items=rows();app_hash,app_bytes,_,_=evidence._profile(selected_revision)
    items[0].update(app_sha256=app_hash,bytes=app_bytes)
    items[3]['app_sha256']=app_hash
    assert evidence._decode_journal(encoded(items),revision=selected_revision)==items
    with pytest.raises(ValueError):evidence._decode_journal(encoded(items))
    with pytest.raises(ValueError):evidence._decode_journal(encoded(rows()),revision=selected_revision)
    for other in {10,11,12,13,14,16}-{selected_revision}:
        with pytest.raises(ValueError):evidence._decode_journal(encoded(items),revision=other)
    for revision in (True,9,15,'11'):
        with pytest.raises(ValueError):evidence._profile(revision)


@pytest.mark.parametrize('fault',['missing','stopped','repeat','hash','offset','mac','boolean','duplicate'])
def test_rejects_incomplete_or_conflicting_journal(fault):
    items=rows()
    if fault=='missing':items.pop()
    if fault=='stopped':items.append(dict(stage='STOPPED'))
    if fault=='repeat':items+=rows()
    if fault=='hash':items[3]['app_sha256']='0'*64
    if fault=='offset':items[0]['offset']=0
    if fault=='mac':items[1]['mac']='00:00:00:00:00:00'
    if fault=='boolean':items[3]['protected_regions_unchanged']=1
    raw=encoded(items)
    if fault=='duplicate':raw=raw.replace(b'"stage":"RESERVED"',b'"stage":"RESERVED","stage":"RESERVED"')
    with pytest.raises(ValueError):evidence._decode_journal(raw)


@pytest.mark.parametrize('revision',[10,11,12,13,14,16,26,27,31,33,34,48,49,50])
def test_exact_journal_is_not_live_health(tmp_path,monkeypatch,revision):
    app_hash,app_bytes,journal_name,review_id=evidence._profile(revision)
    items=rows()
    items[0].update(app_sha256=app_hash,bytes=app_bytes)
    items[3]['app_sha256']=app_hash
    private=tmp_path/'private-backups/controller-20260918-session1';private.mkdir(parents=True)
    (private/journal_name).write_bytes(encoded(items))
    review=dict(target=f'configured-diagnostic-candidate-r{revision}',app_offset=65536,app_slot_bytes=0x140000,
        artifacts={'RoArm-M3_example.ino.bin':dict(sha256=app_hash,bytes=app_bytes)},
        original_backups_match=True,original_recovery_matches_backup=True,retained_r7_artifact_verified=True)
    def read(root,ident,name):
        assert ident==review_id and name=='attachment-pair-candidate-review.json'
        return review,'a'*64
    monkeypatch.setattr(evidence,'_read',read)
    report=evidence.review_pair_installation(tmp_path,revision=revision)
    assert report['host_reported_flash_readback_verified'] is True
    assert report['application_health_verified'] is False
    assert report['current_device_bytes_verified'] is False
    assert report['pair_configuration_verified'] is False
    assert report['motion_authorized'] is False
    review['artifacts']['RoArm-M3_example.ino.bin']['sha256']='0'*64
    with pytest.raises(ValueError):evidence.review_pair_installation(tmp_path,revision=revision)


def test_missing_installation_never_falls_back_to_r7(tmp_path):
    private=tmp_path/'private-backups/controller-20260918-session1';private.mkdir(parents=True)
    (private/'app-r7-deployment-events.jsonl').write_bytes(encoded(rows()))
    with pytest.raises(Exception):evidence.review_pair_installation(tmp_path)


def test_r61_installation_binds_exact_visible_interval_review(tmp_path, monkeypatch):
    revision=61
    app_hash,app_bytes,journal_name,review_id=evidence._profile(revision)
    items=rows();items[0].update(app_sha256=app_hash,bytes=app_bytes);items[3]['app_sha256']=app_hash
    private=tmp_path/'private-backups/controller-20260918-session1';private.mkdir(parents=True)
    (private/journal_name).write_bytes(encoded(items))
    review=dict(schema='rocell.r61_visible_interval_review.v1',
        target='configured-diagnostic-candidate-r61',app_sha256=app_hash,app_bytes=app_bytes,
        app_offset=65536,app_slot_bytes=0x140000,
        predecessor_sha256='6f98f372b5a927b016ae81f0673df1ee8ddd0f0b78bc714d181746e575df7211',
        goals=[[2401,1713],[2389,1725],[2401,1713],[2413,1701]],maximum_writes=4,
        one_write_per_leg=True,retry_allowed=False,settings_preserved_by_design=True,
        hardware_access=False,firmware_uploaded=False)
    def read(root,ident,name):
        assert ident==review_id and name=='attachment-r61-visible-interval-review.json'
        return review,'a'*64
    monkeypatch.setattr(evidence,'_read',read)
    assert evidence.review_pair_installation(tmp_path,revision=revision)['app_sha256']==app_hash
    review['maximum_writes']=5
    with pytest.raises(ValueError):evidence.review_pair_installation(tmp_path,revision=revision)
