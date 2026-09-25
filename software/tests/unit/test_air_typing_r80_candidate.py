"""Native eight-leg owner and fault-stop checks for staged approach comparison."""
from pathlib import Path
import shutil
import subprocess

import pytest

from rocell.application.air_typing_approach_recipe import TARGETS


ROOT=Path(__file__).resolve().parents[2]
STAGE=ROOT/".firmware-tools/configured-diagnostic-candidate-r80/RoArm-M3_example"


@pytest.fixture(scope="module")
def native(tmp_path_factory):
    compiler=shutil.which("clang++")
    if not compiler:pytest.skip("Native compiler unavailable")
    source=(ROOT/"firmware/diagnostics/test_air_typing_owner.cpp").read_text()
    changes={
        '#include "air_typing_owner.h"':'#include <air_typing_owner.h>',
        '{2047,2225,1890,2716,1979,2041,2047}':'{2041,2082,2033,2609,2233,2041,2047}',
        '{2047,2217,1897,2711,1980,2040,2047}':'{2047,2075,2039,2600,2233,2040,2047}',
        '{0,8,-7,5,-1,1,0}':'{0,1,-1,1,2,1,0}',
        'for(int i=0;i<7;++i){goals[i]=target[i];pos[i]=uint16_t(int(target[i])+residual[i]);}':
            'for(int i=0;i<7;++i){if(goals[i]!=target[i])pos[i]=uint16_t(int(target[i])+residual[i]);goals[i]=target[i];}',
    }
    for old,new in changes.items():
        assert source.count(old)==1
        source=source.replace(old,new)
    target=tmp_path_factory.mktemp("r80-native")/"owner.exe"
    result=subprocess.run([compiler,"-std=c++17","-O2","-x","c++","-",
        "-I"+str(STAGE),"-I"+str(ROOT/"firmware/diagnostics"),"-o",str(target)],
        input=source,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    return target


def test_exact_eight_records(native):
    result=subprocess.run([str(native),"success"],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
    lines=result.stdout.splitlines()
    assert len(lines)==8
    for leg,line in enumerate(lines,1):
        raw=bytes.fromhex(line)
        assert len(raw)==1130 and raw[:10]==b"RCAIRAB601" and raw[26]==leg
        assert int.from_bytes(raw[27:29],"big")==TARGETS[leg-1][4]


@pytest.mark.parametrize("mode",["delivery","wrong_endpoint","evidence","source",
                                  "prewrite","stale","timeout","expired"])
@pytest.mark.parametrize("leg",range(1,9))
def test_fault_stops_on_any_leg(native,mode,leg):
    result=subprocess.run([str(native),mode,str(leg)],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,(mode,leg,result.returncode,result.stderr)
