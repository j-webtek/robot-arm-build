"""Known field-name attachment tails, without accepting malformed whole frames."""
import pytest
from rocell.arm.telemetry_coverage import complete_frame_interval


@pytest.mark.parametrize('prefix', [b'R":20}', b'tS":9,"tE":65,"tT":0,"tR":20}',
    b',"tE":65,"tT":-13,"tR":20}', b',"t":0.010737866}'])
def test_known_numeric_key_tail_is_retained_as_unobserved_prefix(prefix):
    raw = prefix+b'\r\n'+b'{"T":1051}\n'
    offset = len(prefix)+2
    selected, windows, framing = complete_frame_interval(raw, [[0,len(raw),10,20]])
    assert selected == b'{"T":1051}\n'
    assert framing['unobserved_prefix_range'] == [0,offset]
    assert framing['original_bytes'] == len(raw)
    assert windows == [[0,len(selected),10,20]]


@pytest.mark.parametrize('prefix', [b'garbageR":20}', b'R":"bad"}', b'R":20,"unknown":2}', b'{"tR":bad}',
    b',"unknown":2}', b',"t":true}', b',"t":"bad"}', b',"t":NaN}',
    b',"t":1e999}', b',"t":1,"t":2}', b',"t":{}}', b',}', b',,"t":1}'])
def test_unknown_or_malformed_prefix_is_not_discarded(prefix):
    raw = prefix+b'\n'+b'{"T":1051}\n'
    selected, _, framing = complete_frame_interval(raw, [[0,len(raw),10,20]])
    assert selected == raw and framing['unobserved_prefix_range'] is None


def test_key_tail_interior_remains_a_rejected_record():
    raw = b'{"T":1051}\nR":20}\n{"T":1051}\n'
    selected, _, framing = complete_frame_interval(raw, [[0,len(raw),10,20]])
    assert selected == raw and framing['unobserved_prefix_range'] is None


def test_comma_tail_interior_is_not_discarded():
    raw = b'{"T":1051}\n,"tE":65,"tT":-13,"tR":20}\n{"T":1051}\n'
    selected, _, framing = complete_frame_interval(raw, [[0,len(raw),10,20]])
    assert selected == raw and framing['unobserved_prefix_range'] is None


@pytest.mark.parametrize('prefix', [b':1.593806039,"t":-0.007669904,"r":-0.001533981,"g":3.149262558,"tB":-21,"tS":9,"tE":65,"tT":-21,"tR":20}', b':20}'])
def test_colon_attachment_boundary_is_unobserved_not_a_sample(prefix):
    raw = prefix+b'\r\n{"T":1051}\n'
    selected, _, framing = complete_frame_interval(raw, [[0,len(raw),10,20]])
    assert selected == b'{"T":1051}\n'
    assert framing['unobserved_prefix_range'] == [0,len(prefix)+2]


@pytest.mark.parametrize('prefix', [b':true}', b':NaN}', b':1e999}',
    b':"bad"}', b':1,"unknown":2}', b':1,"t":2,"t":3}', b':{}}'])
def test_malformed_colon_prefix_is_not_discarded(prefix):
    raw = prefix+b'\n{"T":1051}\n'
    selected, _, framing = complete_frame_interval(raw, [[0,len(raw),10,20]])
    assert selected == raw and framing['unobserved_prefix_range'] is None


def test_colon_interior_is_never_discarded():
    raw = b'{"T":1051}\n:1.593806039,"t":0}\n'
    selected, _, framing = complete_frame_interval(raw, [[0,len(raw),10,20]])
    assert selected == raw and framing['unobserved_prefix_range'] is None
