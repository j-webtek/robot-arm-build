from rocell.application.local_interval_campaign import plan_local_interval_campaign
from rocell.application.local_interval_runner import LocalIntervalRunner


def test_runner_binds_exact_r51_route_and_start_gate(tmp_path):
    runner=LocalIntervalRunner(None,tmp_path,key=b'k'*32,boot='11'*16)
    plan=plan_local_interval_campaign()
    challenge={'reference':'22'*32,'campaign':'33'*32,
               'manifest':{'goals':plan['manifest']['goals']}}
    joints=[{'goal':2047,'position':2047} for _ in range(7)]
    joints[1].update(goal=2389,position=2391);joints[2].update(goal=1725,position=1724)
    import rocell.application.local_pair_mapping_runner as module
    original=module.decode_reference
    module.decode_reference=lambda *a,**k:{'poses':[{'joints':joints}]}
    try:review=runner.review(b'reference',challenge)
    finally:module.decode_reference=original
    assert review['mapping_plan_sha256']==plan['plan_sha256']
    assert runner.targets==plan['manifest']['goals']
