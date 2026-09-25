import importlib.util
from pathlib import Path
import pytest


@pytest.fixture
def reader():
    scripts=Path(__file__).resolve().parents[2]/'scripts'
    spec=importlib.util.spec_from_file_location('ab_comparison_test',scripts/'compare_ab_pilot.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('fault',[None,'variant','usable','source','endpoint','model','conditioning'])
def test_retained_control_provenance(reader,monkeypatch,fault):
    exports=Path(__file__).resolve().parents[2]/'runs/wizard-exports'
    original=reader._read
    def altered(root,ident,name):
        value,digest=original(root,ident,name)
        if name=='attachment-ab-terminal-review.json':
            if fault=='variant':value['variant']='compensated'
            if fault=='usable':value['terminal_measurement_usable']=False
            if fault=='source':value['source_result']=value['source_run']
            if fault=='endpoint':value['actual'][0]+=1
        if name=='attachment-ab-predictions.json' and fault=='model':
            value['campaign']='different'
        if name=='attachment-smoke-run.json' and fault=='conditioning':
            value['legs'][0]['assessment']['continuation_eligible']=False
        return value,digest
    monkeypatch.setattr(reader,'_read',altered)
    args=(exports,'wizard-20260920T183801352365Z-150c883b704449b581992fc4a59618c2','control')
    if fault:
        with pytest.raises((ValueError,FileNotFoundError)):reader.load_trial(*args)
    else:
        audit,_,_=reader.load_trial(*args)
        assert audit['actual']==[2391,1724] and audit['signed_error']==[3,-5]
