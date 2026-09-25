import importlib.util
from pathlib import Path
import pytest


@pytest.fixture
def summarize(monkeypatch):
    scripts=Path(__file__).resolve().parents[2]/'scripts'
    monkeypatch.syspath_prepend(str(scripts))
    spec=importlib.util.spec_from_file_location('comparison_under_test',scripts/'compare_elbow_forward_trials.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.summarize


@pytest.mark.parametrize('positions,start', [([1,2,2,2],200),([2,1,2],300),([2,2,2],100)])
def test_plateau_is_final_contiguous_run(summarize,positions,start):
    samples=[dict(after_ack_us=(i+1)*100,position_counts=p,load_library_units=-45,
                  speed_library_units=0,voltage_raw=121,moving_raw=0)
             for i,p in enumerate(positions)]
    trace=dict(source_export='test',source_sha256='a'*64,assessment={},action={},samples=samples)
    result=summarize(trace)
    assert result['observed_final_plateau_start_us']==start
    assert result['postcommand_samples']==len(positions)
    assert result['position_range']==[min(positions),max(positions)]


def test_precommand_samples_cannot_establish_plateau(summarize):
    with pytest.raises(ValueError):
        summarize(dict(samples=[dict(after_ack_us=-1)]))
