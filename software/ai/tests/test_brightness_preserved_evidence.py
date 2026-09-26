import hashlib
import json
from pathlib import Path
import numpy as np

AI = Path(__file__).resolve().parents[1]
ROOT = AI.parents[1]


def test_frozen_provenance_and_matched_budget():
    path = AI / 'train/brightness_preserved_v0_plan.json'
    plan = json.loads(path.read_text())
    report = json.loads((AI / 'eval/brightness_preserved_v0_scorecard.json').read_text())
    assert hashlib.sha256(path.read_bytes()).hexdigest() == report['plan_sha256']
    for name, digest in plan['file_sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
    control, candidate = report['results']
    assert control['training_images'] == candidate['training_images'] == 7200
    assert control['development_images'] == candidate['development_images'] == 800
    assert control['development_pixels_sha256'] == candidate['development_pixels_sha256']
    assert control['training_pixels_sha256'] == candidate['training_pixels_sha256']
    for result in report['results']:
        assert len(result['history']) == 12
        assert result['selected_epoch'] == min(result['history'], key=lambda r: r['development_mse'])['epoch']
        assert result['hardware_writes'] == result['physical_movements'] == 0
        assert result['qualification_installed'] is False


def test_per_condition_metrics_from_cases():
    report = json.loads((AI / 'eval/brightness_preserved_v0_scorecard.json').read_text())
    for result in report['results']:
        assert len(result['cases']) == 800
        for condition, summary in result['by_condition'].items():
            rows = [r for r in result['cases'] if r['condition'] == condition]
            assert [r['seed'] for r in rows] == list(range(15000000, 15000200))
            assert abs(np.mean([r['mean_mm'] for r in rows]) - summary['mean_mm']) < 1e-12
            assert sum(r['maximum_mm'] > 3 for r in rows) == summary['above_3mm_images']
            assert abs(np.percentile([r['yaw_degrees'] for r in rows], 95) - summary['yaw_p95_degrees']) < 1e-12
    assert report['development_rule_passed'] == all(all(c.values()) for c in list(report['development_checks'].values()) + list(report['reference_checks'].values()))


def test_preservation_loss_masks_dark_samples_and_detached_teacher():
    import sys
    import torch
    sys.path[:0] = [str(AI), str(AI.parent / 'src')]
    from vision.train_brightness_preserved import preservation_loss
    prediction = torch.tensor([[1., 0., 0.], [100., 100., 100.]], requires_grad=True)
    teacher = torch.zeros_like(prediction).detach()
    loss = preservation_loss(prediction, teacher, torch.tensor([1., 0.]))
    assert abs(loss.item() - 4/9) < 1e-7
    loss.backward()
    assert prediction.grad[1].abs().sum().item() == 0
    assert prediction.grad[0, 0].item() > 0
    assert teacher.grad is None
    assert preservation_loss(prediction, teacher, torch.zeros(2)).item() == 0


def test_identical_teacher_and_independent_reference_gates():
    report = json.loads((AI / 'eval/brightness_preserved_v0_scorecard.json').read_text())
    reference = json.loads((AI / 'eval/brightness_reduced_v0_scorecard.json').read_text())['results'][0]
    control, candidate = report['results']
    assert control['teacher_predictions_sha256'] == candidate['teacher_predictions_sha256']
    assert control['original_training_images'] == candidate['original_training_images'] == 5400
    assert [control['preservation_weight'], candidate['preservation_weight']] == [0, 4]
    passed = True
    for baseline, key in [(control, 'development_checks'), (reference, 'reference_checks')]:
        for condition, checks in report[key].items():
            a, b = baseline['by_condition'][condition], candidate['by_condition'][condition]
            mean_ok = b['mean_mm'] < a['mean_mm'] if condition == 'darkened_standard' else b['mean_mm'] / a['mean_mm'] <= 1.05
            tail_ok = b['above_3mm_images'] < a['above_3mm_images'] if condition == 'darkened_standard' else b['above_3mm_images'] <= a['above_3mm_images']
            yaw_ok = b['yaw_p95_degrees'] / a['yaw_p95_degrees'] <= 1.10
            assert checks == dict(mean_error=mean_ok, tail=tail_ok, yaw=yaw_ok)
            passed = passed and mean_ok and tail_ok and yaw_ok
    assert report['development_rule_passed'] == passed
