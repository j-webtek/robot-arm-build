import importlib.util
from pathlib import Path


def test_read_only_observer_contains_exact_r50_gate(monkeypatch):
    scripts=Path(__file__).resolve().parents[2]/'scripts'
    monkeypatch.syspath_prepend(str(scripts))
    spec=importlib.util.spec_from_file_location(
        'observe_campaign_revision_test',scripts/'observe_r33_campaign.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    source=(scripts/'observe_r33_campaign.py').read_text(encoding='utf-8')
    assert 'choices=(33,34,48,49,50,51)' in source
    assert 'expected_goals=[2387,1727];expected_positions=[2389,1726]' in source
    assert 'plan_fine_lookup_validation()' in source
    assert 'expected_goals=[2389,1725];expected_positions=[2391,1724]' in source
    assert 'plan_local_interval_campaign()' in source
