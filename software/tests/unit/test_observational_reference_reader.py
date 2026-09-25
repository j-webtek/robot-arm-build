from pathlib import Path

import pytest

from rocell.application.first_motion_contract import canonical
from rocell.application.observational_reference_reader import ObservationalReferenceReader
from rocell.application.wizard_diagnostic_coordinator import source_fingerprint
from rocell.safety.observational_review_authority import ObservationalIntent
from test_observational_native_registration import registration


@pytest.mark.parametrize('fault', [None, 'source', 'original'])
def test_source_and_original_reconstruction(tmp_path, fault):
    reg, _, request = registration(tmp_path)
    workspace = Path(__file__).resolve().parents[3]
    body = request.to_dict()
    body['references']['source_sha256'] = source_fingerprint(workspace)
    if fault == 'source': body['references']['source_sha256'] = 'f'*64
    request = ObservationalIntent(canonical(body))
    if fault == 'original': reg.package_files[3].path.write_bytes(b'{"changed":true}')
    reader = ObservationalReferenceReader(request, workspace=workspace, root=tmp_path)
    if fault:
        with pytest.raises(ValueError): reader()
    else:
        assert dict(reader()) == body['references']
