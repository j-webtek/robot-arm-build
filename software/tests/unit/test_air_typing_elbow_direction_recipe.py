from rocell.application.air_typing_elbow_direction_recipe import (
    A,HIGH,LOW,TARGETS,validate_recipe,
)


def test_isolates_elbow_with_thirty_count_legs():
    assert validate_recipe() is True
    assert TARGETS==(LOW,A,HIGH,A,LOW,A,HIGH,A)
    prior=A
    for target in TARGETS:
        assert abs(target[3]-prior[3])==30
        assert all(target[i]==A[i] for i in (0,1,2,4,5,6))
        prior=target
