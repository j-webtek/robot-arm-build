"""Run the real quality display branch in a DOM-free Node harness; no I/O."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest


def render(endpoints):
    node = shutil.which('node')
    if node is None:
        pytest.skip('Node unavailable')
    source = (Path(__file__).resolve().parents[2] / 'src/rocell/ui/static/app.js').read_text(encoding='utf-8')
    start = source.index('  function appendMovementCampaignResult(')
    end = source.index('    if (operation.action_id === "positional_campaign_boundary_tests")', start)
    branch = source[start:end] + '\n}'
    harness = '''
const rows = [];
function card(...args) { rows.push(args); return {append: (...items) => rows.push(items)}; }
function element(...args) { return args; }
function facts(value) { return value; }
const box = {append: () => {}};
'''
    result = subprocess.run([node, '-e', harness + branch + '\nappendMovementCampaignResult(box, ' +
        json.dumps(dict(action_id='run_positional_campaign', result=dict(steps=[dict(report=dict(endpoint_diagnostics=endpoints))]))) +
        '); console.log(JSON.stringify(rows));'], capture_output=True, text=True, timeout=5, check=True)
    return result.stdout


def test_displays_independent_outcomes_and_no_physical_claim():
    text = render([dict(leg_id='roll', quality_assessment=dict(schema='rocell.endpoint_quality.v1',
        motion_authorized=False, arrival_status='PASSED_EXISTING_CRITERIA',
        persistence_status='REPORTED_ENDPOINT_PERSISTENT', precision_status='OUTSIDE_DIAGNOSTIC_SCREEN',
        absolute_error_deg=.473, precision_screen_deg=.1, repeatability_status='NOT_ASSESSED_FROM_SINGLE_TRIAL',
        next_start_status='REPORTED_MISMATCH'))])
    for value in ('PASSED_EXISTING_CRITERIA', 'OUTSIDE_DIAGNOSTIC_SCREEN', 'REPORTED_MISMATCH',
                  'not external tool-tip measurements', 'Fresh feedback is required'):
        assert value in text


@pytest.mark.parametrize('endpoints', [None, [], [{}], [dict(quality_assessment=dict(schema='rocell.endpoint_quality.v1', motion_authorized=True))]])
def test_missing_or_authorizing_projection_never_infers_precision(endpoints):
    text = render(endpoints)
    assert 'unavailable' in text or 'No reconstructed endpoint quality' in text
    assert 'WITHIN_DIAGNOSTIC_SCREEN' not in text
