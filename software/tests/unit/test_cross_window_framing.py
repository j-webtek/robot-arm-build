"""Every split position is checked without a serial connection or command."""
import hashlib
import json
import pytest
from rocell.arm.cross_window_framing import partition_cross_command_frame, analyze_cross_command_post

FRAME=(json.dumps(dict(T=1051,x=1,y=2,z=3,tit=0,b=0,s=0,e=1,t=0,r=.02,g=3,tR=0),
                  separators=(',',':'))+'\r\n').encode()


def windows(raw, start):
    return [[i,min(i+128,len(raw)),start+j*1_000_000,start+(j+1)*1_000_000]
            for j,i in enumerate(range(0,len(raw),128))]


def fixture(split, extra=b''):
    before=FRAME+FRAME[:split]
    after=FRAME[split:]+extra+FRAME+FRAME
    bw=windows(before,1_000_000)
    write=bw[-1][3]+1_000_000
    pw=windows(after,write+1_000_000)
    binding=dict(baseline_sha256=hashlib.sha256(before).hexdigest(),
                 post_sha256=hashlib.sha256(after).hexdigest(),
                 write_started_ns=write,write_finished_ns=write)
    return before,bw,after,pw,binding


@pytest.mark.parametrize('split',range(1,len(FRAME)))
def test_every_interior_split_excludes_crossing_frame(split):
    before,bw,after,pw,binding=fixture(split)
    selected,shifted,proof=partition_cross_command_frame(before,bw,after,pw,**binding)
    assert selected==FRAME+FRAME
    assert proof['post_excluded_range']==[0,len(FRAME)-split]
    assert proof['joined_frame_sha256']==hashlib.sha256(FRAME).hexdigest()
    assert proof['byte_continuity_consistent'] and not proof['transport_continuity_verified']
    assert not proof['crossing_frame_counted_as_post'] and not proof['motion_authorized']
    assert shifted[0][0]==0 and shifted[-1][1]==len(selected)


@pytest.mark.parametrize('fault',['digest','missing_byte','bad_prefix','gap','overlap','coverage','overlong'])
def test_unprovable_boundary_rejected(fault):
    before,bw,after,pw,binding=fixture(len(FRAME)-4)
    if fault=='digest':binding['post_sha256']='0'*64
    if fault in ('missing_byte','bad_prefix','overlong'):
        after=after[1:] if fault=='missing_byte' else b'!'+after if fault=='bad_prefix' else b'x'*4097+b'\n'
        pw=windows(after,binding['write_finished_ns']+1_000_000)
        binding['post_sha256']=hashlib.sha256(after).hexdigest()
    if fault=='gap':
        pw=[[a,b,c+300_000_000,d+300_000_000] for a,b,c,d in pw]
    if fault=='overlap':binding['write_started_ns']=bw[-1][3]-1
    if fault=='coverage':pw[0][0]=1
    with pytest.raises(ValueError):partition_cross_command_frame(before,bw,after,pw,**binding)


@pytest.mark.parametrize('extra',[b'bad\n',b'"r":0}\n',b'0}\r\n'])
def test_second_bad_line_cannot_be_discarded(extra):
    before,bw,after,pw,binding=fixture(len(FRAME)-4,extra)
    _,issues,_=analyze_cross_command_post(before,bw,after,pw,
        post_started_ns=pw[0][2],post_finished_ns=pw[-1][3],**binding)
    assert issues


def test_aligned_boundary_preserves_all_bytes():
    before,bw,after,pw,binding=fixture(len(FRAME))
    selected,_,proof=partition_cross_command_frame(before,bw,after,pw,**binding)
    assert selected==after and proof['status']=='ALIGNED_NO_PARTITION'


def test_valid_partition_produces_only_later_complete_poses():
    before,bw,after,pw,binding=fixture(len(FRAME)-4)
    rows,issues,proof=analyze_cross_command_post(before,bw,after,pw,
        post_started_ns=pw[0][2],post_finished_ns=pw[-1][3],**binding)
    assert len(rows)==2 and not issues
    assert proof['remaining_capture_framing']['analysis_range'][0]==0


def test_slow_crossing_fragment_rejected_even_with_short_write_gap():
    before,bw,after,pw,binding=fixture(len(FRAME)-4)
    # Extend the baseline tail's first read without changing the write gap.
    bw=[[a,b,c+300_000_000,d+300_000_000] for a,b,c,d in bw]
    bw[0][2]=1_000_000
    binding['write_started_ns']+=300_000_000
    binding['write_finished_ns']+=300_000_000
    pw=[[a,b,c+300_000_000,d+300_000_000] for a,b,c,d in pw]
    with pytest.raises(ValueError,match='CROSSING_FRAME_ACQUISITION_GAP'):
        partition_cross_command_frame(before,bw,after,pw,**binding)


def test_version_gate_preserves_old_bad_suffix_verdict():
    from rocell.arm.campaign_stream_sync import campaign_post_window
    before,bw,after,pw,binding=fixture(len(FRAME)-4)
    results=[]
    for version in (20,21):
        results.append(campaign_post_window(
            dict(schema=f'rocell.attended_positional_intent.v{version}',
                 limits=dict(maximum_raw_bytes_per_leg=540672)),
            after,pw,pw[0][2],pw[-1][3],baseline_raw=before,baseline_windows=bw,
            write_started_ns=binding['write_started_ns'],write_finished_ns=binding['write_finished_ns']))
    assert results[0][1]  # v20 rejects the orphan 0} suffix as before.
    assert not results[1][1]
    assert results[1][2]['post_excluded_range']==[0,4]
