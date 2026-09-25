import json
from pathlib import Path
import pytest
from test_characterization_composition import binary
from test_characterization_socket_campaign import NativeHTTPRelay,KEY,BOOT,PREFIX
from test_shoulder_repeatability_plan import frozen
from rocell.application.characterization_http import CharacterizationHTTP
from rocell.application.next_validation_runner import NextValidationRunner


@pytest.mark.parametrize('variant,expected',[('forward_repeat',[-1,1]),
    ('reverse_candidate',[-1,-1]),('reverse_control',[0,-2]),
    ('heldout_candidate',[0,0]),('heldout_control',[1,-1]),
    ('second_heldout_candidate',[0,1]),('second_heldout_control',[1,-2])])
def test_fixed_campaign_completes_and_exports(binary,tmp_path,variant,expected):
    relay=NativeHTTPRelay(binary,variant)
    try:
        client=CharacterizationHTTP('127.0.0.1',relay.server.server_port,key=KEY,boot=BOOT)
        result=NextValidationRunner(client,tmp_path,key=KEY,boot=BOOT,frozen_models=frozen(),
            variant=variant,sleep=lambda _:None).run(motion_admitted=True)
        assert result['report']['status']=='COMPLETE'
        expected_writes=(4 if variant in ('forward_repeat','second_heldout_control') else
                         2 if variant.startswith('heldout_') else 3)
        assert relay.calls.count(PREFIX+'receipt')==expected_writes
        audit=json.loads((Path(result['trial_audit_export'])/
            'attachment-next-validation-terminal-review.json').read_text())
        assert audit['terminal_measurement_usable'] and audit['signed_error']==expected
        assert not audit['general_compensation_validated']
    finally:relay.close()


def test_native_reverse_gate_survives_host_gate_omission(binary,tmp_path,monkeypatch):
    monkeypatch.setattr(NextValidationRunner,'check_result',lambda *args:None)
    relay=NativeHTTPRelay(binary,'reverse_candidate',hypothesis='bad_lower')
    try:
        client=CharacterizationHTTP('127.0.0.1',relay.server.server_port,key=KEY,boot=BOOT)
        result=NextValidationRunner(client,tmp_path,key=KEY,boot=BOOT,frozen_models=frozen(),
            variant='reverse_candidate',sleep=lambda _:None).run(motion_admitted=True)
        assert result['report']['status']=='INCONCLUSIVE'
        assert result['report']['fault_export']['reason']=='BASELINE_ADMISSION'
        assert relay.calls.count(PREFIX+'receipt')==2
    finally:relay.close()
