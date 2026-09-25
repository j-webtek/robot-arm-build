import copy
from pathlib import Path
import pytest
from rocell.application.hold_transport_export import capture_hold_transport, replay_hold_transport_bundle
from rocell.application.product_ghost_export_review import _read


def test_invalid_json_is_retained_and_replayed_and_mutations_rejected(tmp_path):
    calls = []
    def get(path, **kwargs):
        calls.append(path)
        return b'{broken'
    receipt = capture_hold_transport(tmp_path / 'exports', get, expected_boot='11'*16)
    assert len(calls) == 1 and receipt['summary']['category'] == 'INCONCLUSIVE'
    folder = Path(receipt['export_path'])
    bundle, _ = _read(folder.parent, folder.name, 'attachment-hold-transport.json')
    assert replay_hold_transport_bundle(bundle)['matches']
    for mutate in (
        lambda b: b['responses'][0].update(sha256='00'*32),
        lambda b: b['responses'][0].update(path='/js'),
        lambda b: b['responses'].append(b['responses'][0]),
        lambda b: b['responses'].clear(),
        lambda b: b['summary'].update(category='TRANSPORT_CAPTURED'),
    ):
        changed = copy.deepcopy(bundle);mutate(changed)
        with pytest.raises(ValueError):
            replay_hold_transport_bundle(changed)
