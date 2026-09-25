import shutil
import subprocess
from pathlib import Path

import pytest

from rocell.application.air_typing_r78_source_rule import source_joint_verified


ROOT=Path(__file__).resolve().parents[2]


def test_post_reset_pose_requires_small_window():
    assert source_joint_verified(previous_position=1985,expected_goal=1994,
                                 current_position=1987,current_goal=1994)
    assert not source_joint_verified(previous_position=1985,expected_goal=1994,
                                     current_position=1989,current_goal=1994)


@pytest.mark.parametrize("delta",range(-3,4))
def test_three_count_boundary(delta):
    assert source_joint_verified(previous_position=2000,expected_goal=2000,
                                 current_position=2000+delta,current_goal=2000)


def test_wrong_goal_and_too_far_from_goal():
    assert not source_joint_verified(previous_position=1985,expected_goal=1994,
                                     current_position=1987,current_goal=1995)
    assert not source_joint_verified(previous_position=1985,expected_goal=2000,
                                     current_position=1987,current_goal=2000)


def test_native_candidate_rule(tmp_path):
    compiler=shutil.which("clang++")
    if not compiler:pytest.skip("Native compiler unavailable")
    source=ROOT/"firmware/diagnostics/test_air_typing_r78_source_rule.cpp"
    target=tmp_path/"source_rule.exe"
    build=subprocess.run([compiler,"-std=c++17","-O2",str(source),"-o",str(target)],
                         capture_output=True,text=True)
    assert build.returncode==0,build.stderr
    result=subprocess.run([str(target)],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
