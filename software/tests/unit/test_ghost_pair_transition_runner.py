import pytest

from rocell.application.ghost_pair_transition_campaign import plan_ghost_pair_transition_campaign
from rocell.application.ghost_pair_transition_runner import GhostPairTransitionRunner


def test_runner_binds_exact_route_and_fresh_start(tmp_path,monkeypatch):
    import rocell.application.local_pair_mapping_runner as module
    plan=plan_ghost_pair_transition_campaign()
    runner=GhostPairTransitionRunner(None,tmp_path,key=b'k'*32,boot='11'*16)
    challenge={'reference':'22'*32,'campaign':'33'*32,
               'manifest':{'goals':plan['manifest']['goals']}}
    joints=[{'goal':2047,'position':2047} for _ in range(7)]
    joints[1].update(goal=2389,position=2391)
    joints[2].update(goal=1725,position=1724)
    monkeypatch.setattr(module,'decode_reference',lambda *a,**k:{'poses':[{'joints':joints}]})
    result=runner.review(b'reference',challenge)
    assert runner.targets==plan['manifest']['goals']
    assert result['mapping_plan_sha256']==plan['plan_sha256']
    challenge['manifest']['goals'][2]=[2387,1727]
    with pytest.raises(ValueError):runner.review(b'reference',challenge)
