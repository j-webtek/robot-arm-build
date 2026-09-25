"""Production host/native contracts exercised through localhost, never hardware."""
import json
from pathlib import Path
import pytest
from test_characterization_composition import binary
from test_characterization_socket_campaign import NativeHTTPRelay, KEY, BOOT, PREFIX
from rocell.application.characterization_http import CharacterizationHTTP
from rocell.application.characterization_matrix_runner import MatrixRunner


@pytest.mark.parametrize('hypothesis', ['constant10', 'frozen_reverse', 'frozen_all'])
def test_matrix_real_contracts(binary, tmp_path, hypothesis):
    relay = NativeHTTPRelay(binary, 'matrix', hypothesis=hypothesis)
    try:
        client = CharacterizationHTTP('127.0.0.1', relay.server.server_port, key=KEY, boot=BOOT)
        report = MatrixRunner(client, tmp_path, key=KEY, boot=BOOT,
                              sleep=lambda _: None).run(motion_admitted=True)['report']
        complete = hypothesis == 'constant10'
        expected = 12 if complete else 6 if hypothesis == 'frozen_reverse' else 1
        assert report['status'] == ('COMPLETE' if complete else 'INCONCLUSIVE'), report
        assert len(report['legs']) == expected
        assert relay.calls.count(PREFIX+'receipt') == expected
        records = [json.loads(p.read_text()) for p in
                   tmp_path.rglob('attachment-characterization-result.json')]
        assert len(records) == expected + (hypothesis == 'frozen_all')
        small = [r for r in records if r['outcome'] == 'SETTLED_SMALL_RESPONSE']
        if not complete:
            assert small
            assert all(r['observations'][-1]['finished_us']-
                       r['observations'][0]['started_us'] >= 2000000 for r in small)
            fault = json.loads((Path(report['fault_export']['export_path'])/
                                'attachment-characterization-fault.json').read_text())
            assert fault['reason'] == ('NO_CLEAR_RESPONSE' if hypothesis == 'frozen_all'
                                       else 'DIRECTION_OR_TRAVEL')
            assert relay.rpc('TICK 100') == str(expected+1)
        else:
            assert not small
        if hypothesis == 'frozen_all':
            # Independently challenge the host with a forged eligible outcome
            # for the second small leg. Native stopping is not our only gate.
            from rocell.application.characterization_result_codec import decode_result
            from rocell.application.characterization_host_session import CharacterizationHostSession
            blobs = [bytes.fromhex(p.read_text()) for p in
                     tmp_path.rglob('attachment-characterization-result.hex.txt')]
            blobs.sort(key=lambda raw: decode_result(raw)['leg'])
            first = decode_result(blobs[0])
            manifest = {k: first[k] for k in ('goals', 'bounds', 'maximum_us')}
            host = CharacterizationHostSession(tmp_path/'independent', manifest,
                key=KEY, boot=BOOT, campaign='33'*32, reference='44'*32)
            host.export_and_sign(blobs[0], source_boot=BOOT, source_campaign='33'*32)
            forged = bytearray(blobs[1])
            forged[len(b'RCCRESULT01\0')+2+8+12*4+7*4] = 4
            with pytest.raises(ValueError, match='assessment rejected'):
                host.export_and_sign(bytes(forged), source_boot=BOOT, source_campaign='33'*32)
    finally:
        relay.close()


@pytest.mark.parametrize('hypothesis', ['directional', 'transient_reverse', 'delayed_reverse'])
def test_matrix_response_variants(binary, tmp_path, hypothesis):
    relay = NativeHTTPRelay(binary, 'matrix', hypothesis=hypothesis)
    try:
        client = CharacterizationHTTP('127.0.0.1', relay.server.server_port, key=KEY, boot=BOOT)
        report = MatrixRunner(client, tmp_path, key=KEY, boot=BOOT,
                              sleep=lambda _: None).run(motion_admitted=True)['report']
        complete = hypothesis == 'delayed_reverse'
        expected = 12 if complete else 7 if hypothesis == 'directional' else 6
        assert report['status'] == ('COMPLETE' if complete else 'INCONCLUSIVE'), report
        assert len(report['legs']) == relay.calls.count(PREFIX+'receipt') == expected
        if not complete:
            fault = json.loads((Path(report['fault_export']['export_path'])/
                                'attachment-characterization-fault.json').read_text())
            # Directional residuals can consume a small step on both successive
            # legs; transient/frozen reverse eventually demands opposite travel.
            assert fault['reason'] == ('NO_CLEAR_RESPONSE' if hypothesis == 'directional'
                                       else 'DIRECTION_OR_TRAVEL')
            assert relay.rpc('TICK 100') == str(expected+1)
        records = sorted((json.loads(p.read_text()) for p in
                          tmp_path.rglob('attachment-characterization-result.json')),
                         key=lambda r: r['leg'])
        if hypothesis == 'transient_reverse':
            assert records[1]['outcome'] == 'SETTLED_SMALL_RESPONSE'
            assert [j['sampled_peak_absolute_counts'] for j in
                    records[1]['motion_summary']['joints']] == [4, 4]
            assert [j['final_net_counts'] for j in
                    records[1]['motion_summary']['joints']] == [0, -2]
        if hypothesis == 'delayed_reverse':
            assert records[1]['outcome'] == 'SETTLED_MISS'
    finally:
        relay.close()


def test_matrix_export_failure_withholds_receipt(binary, tmp_path, monkeypatch):
    from rocell.application import characterization_host_session as host
    def fail_export(*args):
        raise ValueError('Injected export failure')
    monkeypatch.setattr(host, 'export_result', fail_export)
    relay = NativeHTTPRelay(binary, 'matrix')
    try:
        client = CharacterizationHTTP('127.0.0.1', relay.server.server_port, key=KEY, boot=BOOT)
        report = MatrixRunner(client, tmp_path, key=KEY, boot=BOOT,
                              sleep=lambda _: None).run(motion_admitted=True)['report']
        assert report['status'] == 'INCONCLUSIVE'
        assert relay.calls.count(PREFIX+'receipt') == 0
        assert relay.rpc('TICK 100') == '1'
    finally:
        relay.close()


def test_matrix_lost_receipt_ack_does_not_retry(binary, tmp_path):
    from rocell.application.characterization_recovery_http import CharacterizationRecoveryHTTP
    relay = NativeHTTPRelay(binary, 'matrix', drop_receipt=True)
    try:
        client = CharacterizationHTTP('127.0.0.1', relay.server.server_port, key=KEY, boot=BOOT)
        def recovery(campaign):
            return CharacterizationRecoveryHTTP('127.0.0.1', relay.server.server_port,
                                                key=KEY, boot=BOOT, campaign=campaign)
        report = MatrixRunner(client, tmp_path, key=KEY, boot=BOOT,
            sleep=lambda _: None, recovery_factory=recovery).run(motion_admitted=True)['report']
        assert report['status'] == 'INCONCLUSIVE'
        assert relay.calls.count(PREFIX+'receipt') == 1
        assert relay.writes_after_lost_ack == 2
        assert report['reconciliation']['state'] == 'RECEIPT_ACCEPTED_NEXT_LEG_POSSIBLE'
        assert not report['reconciliation']['resume_allowed']
        assert not report['controller_stop_confirmed']
    finally:
        relay.close()
