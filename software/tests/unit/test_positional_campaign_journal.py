import json
import base64
import hashlib
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
import pytest

from rocell.application import positional_campaign_journal as module
from rocell.application.positional_campaign_journal import (
    PositionalCampaignJournal, inspect_campaign_journal, export_campaign_journal,
    verify_campaign_journal_export,
)
from rocell.application.positional_campaign_rehearsal import simulate_positional_campaign, verify_rehearsal_report
from rocell.motion.positional_campaign import compile_wrist_campaign


@pytest.mark.parametrize('count',[2,4,8])
def test_each_commit_precedes_next_reservation(tmp_path,count):
    plan = compile_wrist_campaign(leg_count=count)
    journal = PositionalCampaignJournal(tmp_path,plan)
    report = simulate_positional_campaign(plan,journal=journal)
    assert verify_rehearsal_report(report)['valid']
    for leg in report['legs']:
        saved = json.loads((tmp_path/(leg['leg_id']+'-result.json')).read_bytes())
        assert saved == {k:v for k,v in leg.items() if k != 'record_sha256'}
    assert len(inspect_campaign_journal(tmp_path)['committed_file_legs']) == count
    assert not inspect_campaign_journal(tmp_path)['replay_allowed']
    bundle = export_campaign_journal(tmp_path,report)['bundle']
    assert verify_campaign_journal_export(bundle,report)['valid']
    with pytest.raises(ValueError): PositionalCampaignJournal(tmp_path,plan)
    with pytest.raises(ValueError): simulate_positional_campaign(plan,journal=journal)


def test_endpoint_failure_leaves_uncertain_reservation_and_no_later_command(tmp_path):
    plan = compile_wrist_campaign(leg_count=4)
    journal = PositionalCampaignJournal(tmp_path,plan)
    report = simulate_positional_campaign(plan,journal=journal,fault='NO_RESPONSE',fault_leg=2)
    assert report['simulated_write_count'] == 2
    assert inspect_campaign_journal(tmp_path)['unresolved_reservations'] == ['leg-02']
    assert not (tmp_path/'leg-03-reserved.json').exists()
    with pytest.raises(ValueError): journal.reserve('leg-03',{},plan.sha256)


@pytest.mark.parametrize('name',['leg-01-reserved.json','leg-01-result.json'])
@pytest.mark.parametrize('after_publication',[False,True])
def test_interrupted_publication_never_allows_next_leg(tmp_path,monkeypatch,name,after_publication):
    plan = compile_wrist_campaign()
    journal = PositionalCampaignJournal(tmp_path,plan)
    method = 'publish_bytes' if name.endswith('-result.json') else 'publish_reservation_bytes'
    original = getattr(module,method)
    def interrupt(root,relative,raw,**kwargs):
        if relative == name:
            # Model process failure after exclusive publication reached disk.
            if after_publication:
                original(root,relative,raw,**kwargs)
            raise OSError('injected publication failure')
        return original(root,relative,raw,**kwargs)
    monkeypatch.setattr(module,method,interrupt)
    with pytest.raises(OSError): simulate_positional_campaign(plan,journal=journal)
    assert not (tmp_path/'leg-02-reserved.json').exists()
    with pytest.raises(ValueError): simulate_positional_campaign(plan,journal=journal)
    with pytest.raises(ValueError): PositionalCampaignJournal(tmp_path,plan)


def test_concurrent_duplicate_reservation_has_one_winner(tmp_path):
    plan = compile_wrist_campaign()
    journal = PositionalCampaignJournal(tmp_path,plan)
    def reserve():
        try:
            journal.reserve('leg-01',{},plan.sha256)
            return True
        except ValueError:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(lambda _:reserve(),range(2))) == 1


def test_other_process_cannot_continue_existing_object(tmp_path,monkeypatch):
    plan = compile_wrist_campaign()
    journal = PositionalCampaignJournal(tmp_path,plan)
    monkeypatch.setattr(module.os,'getpid',lambda: journal._pid+1)
    with pytest.raises(ValueError): journal.reserve('leg-01',{},plan.sha256)
    assert not (tmp_path/'leg-01-reserved.json').exists()


def test_changed_committed_predecessor_prevents_next_reservation(tmp_path):
    plan = compile_wrist_campaign()
    report = simulate_positional_campaign(plan)
    first = {k:v for k,v in report['legs'][0].items() if k != 'record_sha256'}
    journal = PositionalCampaignJournal(tmp_path,plan)
    journal.reserve('leg-01',first['baseline'],plan.sha256)
    journal.commit(first)
    (tmp_path/'leg-01-result.json').write_bytes(b'{}')
    with pytest.raises(ValueError):
        journal.reserve('leg-02',report['legs'][1]['baseline'],report['legs'][0]['record_sha256'])
    assert not (tmp_path/'leg-02-reserved.json').exists()


def test_real_process_exit_after_reservation_is_read_only_on_recovery(tmp_path):
    script = '''
import os,sys
from pathlib import Path
from rocell.motion.positional_campaign import compile_wrist_campaign
from rocell.application.positional_campaign_journal import PositionalCampaignJournal
p=compile_wrist_campaign()
j=PositionalCampaignJournal(Path(sys.argv[1]),p)
j.reserve('leg-01',{},p.sha256)
os._exit(17)
'''
    result = subprocess.run([sys.executable,'-c',script,str(tmp_path)],capture_output=True,timeout=10)
    assert result.returncode == 17, result.stderr
    assert inspect_campaign_journal(tmp_path)['unresolved_reservations'] == ['leg-01']
    with pytest.raises(ValueError): PositionalCampaignJournal(tmp_path,compile_wrist_campaign())
    assert not (tmp_path/'leg-02-reserved.json').exists()


@pytest.mark.parametrize('mutation',['reservation','result','header','missing','duplicate'])
def test_export_checks_originals_not_just_hashes(tmp_path,mutation):
    plan = compile_wrist_campaign()
    report = simulate_positional_campaign(plan,journal=PositionalCampaignJournal(tmp_path,plan))
    bundle = export_campaign_journal(tmp_path,report)['bundle']
    if mutation == 'missing': bundle['files'].pop()
    elif mutation == 'duplicate': bundle['files'].append(bundle['files'][0])
    else:
        name = {'reservation':'leg-01-reserved.json','result':'leg-01-result.json','header':'campaign.json'}[mutation]
        item = next(item for item in bundle['files'] if item['name'] == name)
        body = json.loads(base64.b64decode(item['raw_base64']))
        body['physical_authority'] = True
        raw = module.canonical(body)
        item['raw_base64'] = base64.b64encode(raw).decode()
        item['sha256'] = hashlib.sha256(raw).hexdigest()
    with pytest.raises(ValueError): verify_campaign_journal_export(bundle,report)
