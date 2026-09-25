import pytest

from rocell.application import shoulder_configuration_capture as capture
from rocell.application.first_motion_contract import canonical
from rocell.application.shoulder_configuration_review import REGISTERS
from rocell.application.servo_register_reference import PROFILE_ID
from rocell.application.physical_onboarding_durability import PhysicalOnboardingDurabilityError

BOOT = 'ab' * 16


def response(boot=BOOT):
    reads = []
    for sid in (12, 13):
        for address, width in REGISTERS:
            seq = len(reads)
            reads.append([sid, address, width,
                          [seq, 100+seq*20, 110+seq*20, width, 0, True, '00'*width]])
    return canonical(dict(schema='rocell.shoulder_configuration.v1', boot_id=boot,
        capture_id='shoulder-config-1', profile_id=PROFILE_ID, byte_order='little',
        complete=True, reason='SHOULDER_CONFIG_CAPTURED', reads=reads))


def run(root, exchange, **kwargs):
    return capture.capture_shoulders(root, address='192.168.0.225', expected_boot=BOOT,
        authorized=True, origin='SIMULATION', exchange=exchange, **kwargs)


def test_capture_and_retained_export(tmp_path):
    calls = []
    def exchange(address, method):
        calls.append(method)
        # Intent is durably exported before POST, response before GET.
        assert list(tmp_path.glob('wizard-*/attachment-shoulder-transport.json'))
        return response()
    result = run(tmp_path, exchange)
    assert calls == ['POST', 'GET']
    assert result['report']['category'] == 'SIMULATED_CONFIGURATION'
    assert not result['report']['motion_authorized']
    with pytest.raises((ValueError, FileExistsError, PhysicalOnboardingDurabilityError)):
        run(tmp_path, exchange)
    assert calls == ['POST', 'GET']


@pytest.mark.parametrize('failure', ['timeout', 'wrong_boot', 'malformed', 'oversize', 'changed_get'])
def test_failure_never_retries(tmp_path, failure):
    calls = []
    def exchange(address, method):
        calls.append(method)
        if failure == 'timeout': raise TimeoutError('lost response')
        if failure == 'wrong_boot': return response('cd'*16)
        if failure == 'malformed': return b'not json'
        if failure == 'oversize': return b'x'*8193
        return response() if method == 'POST' else response()+b' '
    result = run(tmp_path, exchange)
    assert result['report']['category'] == 'INCONCLUSIVE'
    assert calls == (['POST', 'GET'] if failure == 'changed_get' else ['POST'])


@pytest.mark.parametrize('fail_save', [1, 2])
def test_export_failure_prevents_next_request(tmp_path, monkeypatch, fail_save):
    original = capture.WizardDiagnosticExporter.export
    saves = []
    calls = []
    def export(self, *args, **kwargs):
        saves.append(1)
        if len(saves) == fail_save: raise OSError('disk unavailable')
        return original(self, *args, **kwargs)
    monkeypatch.setattr(capture.WizardDiagnosticExporter, 'export', export)
    def exchange(address, method):
        calls.append(method)
        return response()
    with pytest.raises(OSError): run(tmp_path, exchange)
    assert calls == ([] if fail_save == 1 else ['POST'])


def test_authority_and_simulation_do_not_open_network(tmp_path):
    with pytest.raises(ValueError, match='approval'):
        capture.capture_shoulders(tmp_path, address='192.168.0.225', expected_boot=BOOT)
    with pytest.raises(ValueError, match='Simulation'):
        capture.capture_shoulders(tmp_path, address='192.168.0.225', expected_boot=BOOT,
                                  authorized=True, origin='SIMULATION')


@pytest.mark.parametrize('case', ['large_valid', 'oversize', 'truncated', 'redirect'])
def test_fixed_http_routes_and_response_limits(monkeypatch, case):
    body = b'x'*5000
    length = 8193 if case == 'oversize' else len(body)
    status = '302 Found' if case == 'redirect' else '200 OK'
    wire = (f'HTTP/1.1 {status}\r\nContent-Length: {length}\r\n'
            'Content-Type: application/json\r\n\r\n').encode()+body
    if case == 'truncated': wire = wire[:-1]
    class Socket:
        def __init__(self): self.pending=bytearray(wire);self.sent=[]
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def settimeout(self, value): assert 0 < value <= 3
        def connect(self, target): assert target == ('192.168.0.225', 80)
        def sendall(self, raw): self.sent.append(raw)
        def recv(self, count):
            raw=bytes(self.pending[:count]);del self.pending[:count];return raw
    connection=Socket()
    monkeypatch.setattr(capture.socket, 'socket', lambda *args: connection)
    if case == 'large_valid':
        assert capture.shoulder_exchange('192.168.0.225', 'POST') == body
    else:
        with pytest.raises(ValueError): capture.shoulder_exchange('192.168.0.225', 'POST')
    assert len(connection.sent) == 1
    assert connection.sent[0].startswith(b'POST /rocell/shoulder-configuration/capture HTTP/1.1')
