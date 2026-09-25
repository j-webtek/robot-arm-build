"""Planning bounds must check the actual outbound path, never clip a target."""
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('observed_paths',
    Path(__file__).resolve().parents[2] / 'scripts/review_observed_elbow_paths.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_current_anchor_keeps_requested_targets():
    paths = module.candidate_paths(2899)
    assert [p['targets'] for p in paths] == [[2893, 2899], [2905, 2899],
                                            [2909, 2899], [2911, 2899]]
    assert [p['fits_encoder_envelope'] for p in paths] == [True, True, True, False]


@pytest.mark.parametrize('anchor', [True, 2899.0, 2892, 2910])
def test_invalid_anchor_rejected(anchor):
    with pytest.raises(ValueError):
        module.candidate_paths(anchor)
