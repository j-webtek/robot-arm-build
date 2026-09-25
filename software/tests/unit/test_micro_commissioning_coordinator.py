"""Coordinator ordering with explicit fake providers; never invokes native I/O."""
from contextlib import contextmanager
import math
import pytest
from rocell.application import micro_commissioning_coordinator as module


def setup(tmp_path,monkeypatch,*,angle=1.40625,fault=None):
    events=[];exports=[];active=[False]
    (tmp_path/'manifest.json').write_text('{}')
    @contextmanager
    def lease():
        if fault=='lease':raise RuntimeError()
        active[0]=True;events.append('acquire')
        try:yield
        finally:
            active[0]=False;events.append('release')
    class Session:
        def __init__(self,*,lease_factory,clock_ns):self.lease=lease_factory
        def scope(self):return self.lease()
        def predecessor_intent(self):events.append('intent')
        def bind(self,admission):events.append('bind')
    def review(*a,**k):
        events.append('review')
        if fault=='evidence':raise ValueError()
        return dict(pose=[0,0,0,0,math.radians(angle),0])
    def previous(**kwargs):
        assert active[0];events.append('predecessor')
        return dict(status='FAILED' if fault=='predecessor' else 'SUCCEEDED')
    def hold(**kwargs):events.append('hold');return dict(status='SUCCEEDED')
    def save_previous(*args):
        events.append('save_predecessor')
        if fault=='predecessor_export':raise OSError()
        return tmp_path
    def baseline(**kwargs):
        assert active[0];events.append('baseline');return {}
    def admission(**kwargs):
        events.append('admission')
        if fault=='admission':raise ValueError()
        return object()
    def transport(*args):events.append('transport');return object()
    def transaction(*args,export,**kwargs):
        assert active[0];events.append('micro')
        r=dict(status='STOPPED' if fault=='micro' else 'EXPERIMENT_VERIFIED',reason='TEST')
        export(r);return r
    def final(report):
        events.append('save_final');exports.append(report)
        if fault=='final_export':raise OSError()
        return dict(saved=True)
    monkeypatch.setattr(module,'MicroControlSession',Session)
    monkeypatch.setattr(module,'predecessor',review)
    monkeypatch.setattr(module,'MicroCommandAdmission',admission)
    monkeypatch.setattr(module,'run_micro_transaction',transaction)
    args=dict(root=tmp_path,lease_factory=lease,clock_ns=lambda:1,wait=lambda s:None,
              run_predecessor=previous,observe_hold=hold,save_predecessor=save_previous,
              read_baseline=baseline,transport_factory=transport,save_micro=lambda r:dict(saved=True),
              save_outcome=final,exclusive_controller_declared=fault!='declaration',
              cancelled=lambda:fault=='cancel')
    coordinator=module.MicroCommissioningCoordinator()
    return coordinator,args,events,exports


def test_one_predecessor_one_optional_micro_under_same_scope(tmp_path,monkeypatch):
    coordinator,args,events,exports=setup(tmp_path,monkeypatch)
    result=coordinator.run(**args)
    assert result['status']=='EXPERIMENT_VERIFIED'
    assert events==['acquire','intent','predecessor','hold','save_predecessor','review',
                    'baseline','admission','bind','transport','micro','save_final','release']
    assert result['micro_export']==dict(saved=True)
    with pytest.raises(ValueError):coordinator.run(**args)
    assert events.count('micro')==events.count('predecessor')==1


def test_in_band_does_not_search_for_an_error_to_correct(tmp_path,monkeypatch):
    coordinator,args,events,exports=setup(tmp_path,monkeypatch,angle=1.230468748)
    result=coordinator.run(**args)
    assert result['status']=='NO_CORRECTION_NEEDED'
    assert events.count('predecessor')==1
    assert 'baseline' not in events and 'micro' not in events
    assert exports[-1]['summary']==result['summary']
    assert result['summary']['status']=='NO_CORRECTION_NEEDED'
    assert result['summary']['legs'][0]['observed_deg'] is None  # Stub has no rows.


def test_outside_start_range_stops_without_other_positioning(tmp_path,monkeypatch):
    coordinator,args,events,_=setup(tmp_path,monkeypatch,angle=1.6)
    assert coordinator.run(**args)['reason']=='PREDECESSOR_OUTSIDE_MICRO_START_RANGE'
    assert 'micro' not in events


@pytest.mark.parametrize('fault',['lease','predecessor','predecessor_export','evidence',
                                 'admission','micro','final_export','declaration','cancel'])
def test_failure_keeps_diagnostics_without_retry(tmp_path,monkeypatch,fault):
    coordinator,args,events,exports=setup(tmp_path,monkeypatch,fault=fault)
    result=coordinator.run(**args)
    assert result['status']=='STOPPED' and exports
    assert events.count('predecessor')<=1 and events.count('micro')<=1
    if fault not in ('micro','final_export'):assert 'micro' not in events
    if fault=='predecessor':assert 'hold' not in events and 'save_predecessor' in events
    if fault=='final_export':assert not result['final_export_succeeded']
