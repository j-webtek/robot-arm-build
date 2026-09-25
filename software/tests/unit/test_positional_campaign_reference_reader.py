import hashlib

import pytest

from rocell.application.first_motion_contract import canonical
from rocell.application.physical_onboarding_durability import PhysicalOnboardingDurabilityError
from rocell.application import positional_campaign_reference_reader as module
from rocell.safety.positional_campaign_authority import PositionalCampaignIntent
from test_positional_campaign_authority import body


def prepared(tmp_path, monkeypatch):
    value = body()
    directory = tmp_path / (value['campaign_id'] + '-positional-native-child')
    directory.mkdir()
    originals = {}
    for name, filename in module.ORIGINAL_FILES.items():
        raw = canonical({'fixture_only': name})
        (directory / filename).write_bytes(raw)
        originals[name] = raw
        value['references'][name] = hashlib.sha256(raw).hexdigest()
    monkeypatch.setattr(module, 'source_fingerprint', lambda workspace: value['references']['source_sha256'])
    request = PositionalCampaignIntent(canonical(value))
    reader = module.PositionalCampaignReferenceReader(request, workspace=tmp_path, root=tmp_path)
    return reader, directory, originals


def test_all_reviewed_references_reconstructed_and_frozen(tmp_path, monkeypatch):
    reader, directory, originals = prepared(tmp_path, monkeypatch)
    assert dict(reader()) == reader._request.to_dict()['references']
    frozen = module.FrozenPositionalCampaignReferences(reader)
    assert frozen() == reader()
    assert all(frozen.original(name) == raw for name, raw in originals.items())
    # Freezing is explicitly a historical startup snapshot, not live validation.
    (directory / 'workcell.original.json').write_bytes(b'{}')
    assert frozen.original('workcell_sha256') == originals['workcell_sha256']
    with pytest.raises(ValueError): reader()


@pytest.mark.parametrize('name', list(module.ORIGINAL_FILES))
def test_changed_original_cannot_be_admitted_as_reviewed(tmp_path, monkeypatch, name):
    reader, directory, _ = prepared(tmp_path, monkeypatch)
    (directory / module.ORIGINAL_FILES[name]).write_bytes(canonical({'changed': True}))
    with pytest.raises(ValueError, match='changed'): reader()


def test_changed_source_and_missing_original_rejected(tmp_path, monkeypatch):
    reader, directory, _ = prepared(tmp_path, monkeypatch)
    monkeypatch.setattr(module, 'source_fingerprint', lambda workspace: 'f'*64)
    with pytest.raises(ValueError, match='source/reference'): reader()
    (directory / 'runtime.original.json').unlink()
    with pytest.raises(PhysicalOnboardingDurabilityError): reader.original('runtime_sha256')


def test_unknown_path_and_invalid_reader_rejected(tmp_path, monkeypatch):
    reader, _, _ = prepared(tmp_path, monkeypatch)
    with pytest.raises(ValueError): reader.original('../outside.json')
    with pytest.raises(ValueError): module.FrozenPositionalCampaignReferences(lambda: reader())


def test_mid_freeze_reference_change_rejected(tmp_path, monkeypatch):
    reader, directory, _ = prepared(tmp_path, monkeypatch)
    original = reader.original
    calls = [0]
    def changing(name):
        calls[0] += 1
        raw = original(name)
        if calls[0] == 8:
            (directory / 'runtime.original.json').write_bytes(b'{"changed":true}')
        return raw
    monkeypatch.setattr(reader, 'original', changing)
    with pytest.raises(ValueError): module.FrozenPositionalCampaignReferences(reader)


@pytest.mark.parametrize('acknowledged', [True, False])
def test_v2_original_requires_bounded_completion_risk_not_emergency_stop(tmp_path, monkeypatch, acknowledged):
    reader, directory, _ = prepared(tmp_path, monkeypatch)
    value = reader._request.to_dict()
    value['schema'] = 'rocell.attended_positional_intent.v2'
    value['references'].pop('stop_qualification_sha256')
    raw = canonical(dict(schema='rocell.attended_bounded_motion_risk.v1',
        operator_present=True, entire_accepted_motion_clear=True, no_contact=True,
        no_added_payload=True, accepted_goal_may_finish=acknowledged,
        software_cancel_is_not_physical_stop=True))
    value['references']['bounded_motion_risk_sha256'] = hashlib.sha256(raw).hexdigest()
    (directory/'bounded-motion-risk.original.json').write_bytes(raw)
    (directory/'stop-qualification.original.json').unlink()
    current = module.PositionalCampaignReferenceReader(PositionalCampaignIntent(canonical(value)),
        workspace=tmp_path, root=tmp_path)
    if acknowledged:
        frozen = module.FrozenPositionalCampaignReferences(current)
        assert frozen.original('bounded_motion_risk_sha256') == raw
        assert 'stop_qualification_sha256' not in dict(frozen())
    else:
        with pytest.raises(ValueError, match='completion-risk'): current()
