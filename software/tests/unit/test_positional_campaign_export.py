"""Actual immutable publication and portable reconstruction; incapable IO only."""
import json
import shutil
from pathlib import Path

import pytest

from rocell.application.first_motion_contract import canonical
from rocell.application.positional_campaign_export import (
    publish_owned_campaign_export, verify_owned_campaign_export,
)
from test_positional_campaign_reconstruction import experiment


@pytest.mark.parametrize('fault', [None, 'no_response', 'short_write', 'write_error',
    'malformed', 'cancel_before', 'cancel_after', 'close_error', 'clock_error'])
def test_export_preserves_complete_and_interrupted_campaigns(tmp_path, fault):
    request, result = experiment(tmp_path, fault)
    receipt = publish_owned_campaign_export(tmp_path, request, result)
    folder = Path(receipt['path'])
    assert (folder / 'result.json').read_bytes() == canonical(result)
    assert (folder / 'intent.json').read_bytes() == request.canonical_bytes
    complete = fault in (None, 'no_response', 'short_write', 'write_error')
    assert receipt['disposition'] == ('RECONSTRUCTED' if complete else 'DIAGNOSTIC_ONLY')
    assert receipt['valid'] and not receipt['motion_authorized']
    assert not receipt['physical_stop_verified'] and not receipt['replay_allowed']
    if complete:
        assert receipt['reconstruction']['reconstructed_status'] == result['status']
    else:
        assert receipt['reconstruction'] is None
    portable = tmp_path / 'portable-copy'
    shutil.copytree(folder, portable)
    assert verify_owned_campaign_export(portable)['manifest_sha256'] == receipt['manifest_sha256']
    with pytest.raises(FileExistsError):
        publish_owned_campaign_export(tmp_path, request, result)


@pytest.mark.parametrize('changed', ['result', 'manifest', 'missing'])
def test_changed_or_incomplete_export_rejected(tmp_path, changed):
    request, result = experiment(tmp_path)
    folder = Path(publish_owned_campaign_export(tmp_path, request, result)['path'])
    if changed == 'missing':
        (folder / 'manifest.json').unlink()
    elif changed == 'result':
        result['legs'][0]['verification']['endpoint']['final_error_rad'] = 1
        (folder / 'result.json').write_bytes(canonical(result))
    else:
        manifest = json.loads((folder / 'manifest.json').read_bytes())
        manifest['motion_authorized'] = True
        (folder / 'manifest.json').write_bytes(canonical(manifest))
    with pytest.raises(ValueError):
        verify_owned_campaign_export(folder)


def test_unreconstructable_success_label_saved_only_as_diagnostic(tmp_path):
    request, result = experiment(tmp_path)
    result['legs'][0]['verification']['endpoint']['final_error_rad'] = 1
    receipt = publish_owned_campaign_export(tmp_path, request, result)
    assert receipt['disposition'] == 'DIAGNOSTIC_ONLY'
    assert receipt['reconstruction'] is None


def test_native_claim_not_accepted_by_synthetic_exporter(tmp_path):
    request, result = experiment(tmp_path)
    result['basis'] = 'RETAINED_PHYSICAL_CAPTURE'
    with pytest.raises(ValueError):
        publish_owned_campaign_export(tmp_path, request, result)
    assert not list(tmp_path.glob('*-owned-export'))
