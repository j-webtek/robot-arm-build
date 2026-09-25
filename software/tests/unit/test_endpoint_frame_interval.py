"""Boundary fragments remain explicit; complete interior corruption is fatal."""

from copy import deepcopy
import hashlib

import pytest

from rocell.arm.telemetry_coverage import complete_frame_interval
from rocell.arm.movement_analysis import analyze_endpoint_trial
from rocell.motion.characterization_plan import freeze_campaign
from test_characterization_plan import candidate
from test_endpoint_movement_analysis import endpoints


def fragmented(prefix=b'"tR":24}\r\n',suffix=b'{"T":1051,"x":'):
    raw,windows,kw=endpoints()
    modified=deepcopy(windows)
    for row in modified:
        row[0]+=len(prefix)
        row[1]+=len(prefix)
    modified[0][0]=0
    modified[-1][1]+=len(suffix)
    return prefix+raw+suffix,modified,kw,raw,windows


def test_fragments_preserve_original_offsets_hashes_and_host_times():
    original,windows,kw,expected,expected_windows=fragmented()
    raw,view,frame=complete_frame_interval(original,windows)
    assert raw==expected and view==expected_windows
    assert frame['original_sha256']==hashlib.sha256(original).hexdigest()
    a,b=frame['analysis_range']
    assert original[a:b]==raw
    assert a+(b-a)+(len(original)-b)==len(original)
    result=analyze_endpoint_trial(freeze_campaign(candidate()),'out',original,windows,**kw)
    assert result['status']=='OBSERVED_ENDPOINT_DWELL'
    assert result['raw_sha256']==frame['original_sha256']
    assert result['frame_interval']==frame
    assert result['physical_stop_verified'] is False


def test_attachment_inside_numeric_token_is_retained_outside_analysis():
    original,windows,kw,expected,expected_windows=fragmented(b'06135923,"r":-0.003,"tR":24}\r\n')
    raw,view,framing=complete_frame_interval(original,windows)
    assert raw==expected and view==expected_windows
    assert framing['unobserved_prefix_range'] is not None
    assert analyze_endpoint_trial(freeze_campaign(candidate()),'out',original,windows,**kw)['status']=='OBSERVED_ENDPOINT_DWELL'


@pytest.mark.parametrize('prefix,suffix',[(b'{bad}\n',b''),(b'broken\n',b''),(b'',b'garbage'),
                                        (b'"'+b'x'*2048+b'}\n',b'')])
def test_nonboundary_corruption_is_not_rescued(prefix,suffix):
    raw,windows,kw,_,_=fragmented(prefix,suffix)
    # Very large prefix deliberately exceeds per-read limits, also refused.
    if len(prefix)>256:
        with pytest.raises(ValueError): complete_frame_interval(raw,windows)
    else:
        result=analyze_endpoint_trial(freeze_campaign(candidate()),'out',raw,windows,**kw)
        assert result['status']=='INSUFFICIENT_ENDPOINT_EVIDENCE'


def test_removed_fragment_does_not_hide_out_of_window_read():
    raw,windows,kw,_,_=fragmented()
    # Move just the final fragment to another read after the observation ends.
    end=raw.rfind(b'\n')+1
    windows[-1][1]=end
    windows.append([end,len(raw),kw['observation_end_ns']+1,kw['observation_end_ns']+2])
    with pytest.raises(ValueError,match='beyond observation'):
        analyze_endpoint_trial(freeze_campaign(candidate()),'out',raw,windows,**kw)


@pytest.mark.parametrize('delimiter', [b'\n', b'\r\n'])
def test_attachment_at_prior_frame_delimiter_is_accounted_not_erased(delimiter):
    original, windows, kw, expected, expected_windows = fragmented(delimiter)
    raw, view, framing = complete_frame_interval(original, windows)
    assert raw == expected and view == expected_windows
    assert framing['unobserved_prefix_range'] == [0, len(delimiter)]
    assert framing['original_sha256'] == hashlib.sha256(original).hexdigest()
    assert original[:len(delimiter)] == delimiter
    assert analyze_endpoint_trial(freeze_campaign(candidate()), 'out', original, windows, **kw)['status'] == 'OBSERVED_ENDPOINT_DWELL'


@pytest.mark.parametrize('prefix', [b'\n\n', b'\r\n\r\n', b' \n', b'\t\n'])
def test_multiple_or_whitespace_records_are_not_hidden_as_delimiter(prefix):
    raw, windows, kw, _, _ = fragmented(prefix)
    result = analyze_endpoint_trial(freeze_campaign(candidate()), 'out', raw, windows, **kw)
    assert result['status'] == 'INSUFFICIENT_ENDPOINT_EVIDENCE'
