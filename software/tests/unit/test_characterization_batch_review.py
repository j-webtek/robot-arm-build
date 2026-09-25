from copy import deepcopy
from pathlib import Path

import pytest

from rocell.application.characterization_batch_review import review_export, summarize_campaign
from rocell.application.shoulder_characterization_sim import run_characterization_sim
from rocell.application.wizard_diagnostic_export import verify_export


@pytest.fixture
def campaign(tmp_path):
    return run_characterization_sim(tmp_path / 'source')


def test_grouped_repeats_retain_offset_not_false_accuracy(campaign):
    summary = summarize_campaign(campaign['report'])
    rows = summary['grouped_endpoints']
    assert len(rows) == 6
    assert sum(row['samples'] for row in rows) == 24
    assert {row['mean_error_counts'] for row in rows} == {9, -7}
    assert all(row['endpoint_range_counts'] == 0 for row in rows)
    assert summary['compensation_applied'] is False
    assert summary['movement_authorized'] is False


def test_export_roundtrip(campaign, tmp_path):
    result = review_export(Path(campaign['export_path']), tmp_path / 'review')
    assert verify_export(Path(result['export_path']))['valid']
    assert result['summary']['source_manifest_sha256']
    text = (Path(result['export_path']) / 'attachment-batch-review.md').read_text()
    assert 'Synthetic simulation only' in text
    assert '9.000' in text and '-7.000' in text


def test_tampering_rejected_before_output(campaign, tmp_path):
    source = Path(campaign['export_path'])
    (source / 'attachment-campaign-result.json').write_text('{}')
    with pytest.raises(ValueError, match='integrity'):
        review_export(source, tmp_path / 'review')
    assert not (tmp_path / 'review').exists()


def test_forged_pass_cannot_hide_bad_raw_position(campaign):
    report = deepcopy(campaign['report'])
    sample = report['legs'][0]['samples'][-1]
    sample['positions'] = list(sample['positions'])
    sample['positions'][1] += 100
    with pytest.raises(ValueError, match='reassessment'):
        summarize_campaign(report)


@pytest.mark.parametrize('field,value', [('basis', 'LIVE'), ('physical_packets', 12)])
def test_live_evidence_not_mislabelled_as_simulation(campaign, field, value):
    report = deepcopy(campaign['report'])
    report[field] = value
    with pytest.raises(ValueError, match='synthetic'):
        summarize_campaign(report)


def test_fault_retained_and_not_used_for_statistics(tmp_path):
    report = run_characterization_sim(tmp_path, fault='DELIVERY')['report']
    summary = summarize_campaign(report)
    assert summary['campaign_state'] == 'STOPPED'
    assert summary['excluded_legs'] == [{'leg_id': 4, 'reason': 'INCOMPLETE_OR_STOPPED'}]
    assert sum(row['samples'] for row in summary['grouped_endpoints']) == 6


def test_matched_campaign_uses_existing_simulator_and_review(tmp_path):
    report = run_characterization_sim(tmp_path, pattern='matched')['report']
    assert report['state'] == 'COMPLETED' and report['physical_packets'] == 0
    summary = summarize_campaign(report)
    matched = [row for row in summary['grouped_endpoints']
               if row['servo_id'] == 12 and row['target_counts'] == 2397]
    assert len(matched) == 2
    assert {row['approach_direction'] for row in matched} == {-1, 1}
    assert all(row['samples'] == 3 for row in matched)
