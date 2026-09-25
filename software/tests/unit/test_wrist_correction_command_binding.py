import math
from threading import Event
import pytest
from test_wrist_correction_current_context import fixture
from rocell.arm.protocol import encode_line
from rocell.application.wrist_correction_command_binding import WristCorrectionCommandBinding
from rocell.application.physical_onboarding_durability import PhysicalOnboardingDurabilityError


def selected(tmp_path):
    reader,clock,*_=fixture(tmp_path)
    cancel=Event()
    binding=WristCorrectionCommandBinding(reader=reader,root=tmp_path,cancellation=cancel)
    binding.claim_open();binding.validate_open_claim()
    joints=reader._originals[0][0].to_dict()['draft']['expected_start_joints_rad']
    raw=b'';windows=[]
    for i in range(10):
        line=encode_line(dict(T=1051,x=1,y=2,z=3,tit=0,**joints))
        stamp=2_000_000_000+i*50_000_000
        windows.append([len(raw),len(raw)+len(line),stamp,stamp]);raw+=line
    clock[0]=2_500_000_000
    binding.bind_baseline(raw,windows,started_ns=2_000_000_000,finished_ns=2_500_000_000)
    return binding,reader,clock,cancel


def test_one_open_one_bound_command_without_native_io(tmp_path):
    binding,reader,_,cancel=selected(tmp_path)
    payload=binding.consume_command()
    assert b'"joint":4' in payload and b'"rad":-' in payload
    for call in (binding.claim_open,binding.consume_command,binding.validate_open_claim):
        with pytest.raises(ValueError): call()
    with pytest.raises(PhysicalOnboardingDurabilityError):
        WristCorrectionCommandBinding(reader=reader,root=tmp_path,cancellation=cancel)


@pytest.mark.parametrize('fault',['cancel','stale','revoke','clock','review'])
def test_changed_state_never_dispatches(tmp_path,fault):
    binding,_,clock,cancel=selected(tmp_path)
    if fault=='cancel': cancel.set()
    if fault=='stale': clock[0]+=101_000_000
    if fault=='revoke': binding.revoke()
    if fault=='clock': clock[0]-=1
    if fault=='review': next(tmp_path.glob('*plan-review.json')).write_bytes(b'{}')
    with pytest.raises(ValueError): binding.consume_command()
    with pytest.raises(ValueError): binding.consume_command()


def test_no_binding_before_open_claim(tmp_path):
    reader,*_=fixture(tmp_path)
    binding=WristCorrectionCommandBinding(reader=reader,root=tmp_path,cancellation=Event())
    with pytest.raises(ValueError): binding.bind_baseline(b'',[],started_ns=1,finished_ns=2)


def test_concurrent_dispatch_consumption_returns_only_one_payload(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    binding,*_=selected(tmp_path)
    def take(_):
        try: return binding.consume_command()
        except ValueError: return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(take,range(2)))
    assert sum(type(r) is bytes for r in results)==1
