from pathlib import Path
import hashlib
import json
import shutil
import subprocess

import pytest

from rocell.application.air_typing_r77_campaign import AirTypingFinaleHost, TARGETS, assess_leg
from rocell.application.wizard_diagnostic_export import verify_export


ROOT=Path(__file__).resolve().parents[2]
STAGE=ROOT/".firmware-tools/configured-diagnostic-candidate-r77/RoArm-M3_example"


@pytest.fixture(scope="module")
def native(tmp_path_factory):
    compiler=shutil.which("clang++")
    if not compiler:pytest.skip("Native compiler unavailable")
    source=(ROOT/"firmware/diagnostics/test_air_typing_owner.cpp").read_text()
    changes={
        '#include "air_typing_owner.h"':'#include <air_typing_owner.h>',
        '{2047,2225,1890,2716,1979,2041,2047}':'{1949,2099,2015,2610,2203,2041,2047}',
        '{2047,2217,1897,2711,1980,2040,2047}':'{1941,2098,2016,2609,2201,2040,2047}',
        '{0,8,-7,5,-1,1,0}':'{8,1,-1,1,2,1,0}',
    }
    for old,new in changes.items():
        assert old in source
        source=source.replace(old,new)
    target=tmp_path_factory.mktemp("r77-native")/"owner.exe"
    result=subprocess.run([compiler,"-std=c++17","-O2","-x","c++","-",
        "-I"+str(STAGE),"-I"+str(ROOT/"firmware/diagnostics"),"-o",str(target)],
        input=source,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    return target


@pytest.fixture(scope="module")
def records(native):
    result=subprocess.run([str(native),"success"],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
    return [bytes.fromhex(line) for line in result.stdout.splitlines()]


@pytest.mark.parametrize("mode",["delivery","wrong_endpoint","evidence","source",
                                    "prewrite","stale","timeout","expired"])
@pytest.mark.parametrize("leg",range(1,8))
def test_native_fault_stops(native,mode,leg):
    result=subprocess.run([str(native),mode,str(leg)],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,(mode,leg,result.returncode,result.stderr)


def test_all_records_replay_independently(records):
    assert len(records)==len(TARGETS)==7
    previous=None
    for leg,raw in enumerate(records,1):
        previous=assess_leg(raw,boot="ab"*16,leg=leg,previous=previous)
        assert previous["status"]=="FINALE_LEG_ENDPOINT_VERIFIED"
        assert previous["target_goals"]==list(TARGETS[leg-1])
    with pytest.raises(ValueError):assess_leg(records[0],boot="cd"*16,leg=1)
    with pytest.raises(ValueError):assess_leg(records[0],boot="ab"*16,leg=2)


def test_finite_export_gated_host(records,tmp_path):
    class Transport:
        def __init__(self):self.leg=1;self.receipts=[]
        def __call__(self,method,path,body=b""):
            suffix=path.rsplit("/",1)[-1]
            if suffix=="start":
                assert method=="POST" and body==b"AIR7"
                return b"CAPTURING_START"
            if suffix=="status":return f"AWAITING_EXPORT|{self.leg}".encode()
            if suffix=="record":return records[self.leg-1].hex().encode()
            if suffix=="receipt":
                assert body==f'{self.leg}:{hashlib.sha256(records[self.leg-1]).hexdigest()}'.encode()
                self.receipts.append(self.leg);self.leg+=1
                return b"COMPLETE" if self.leg==8 else f"READY|{self.leg}".encode()
            if suffix=="next":
                assert body==str(self.leg).encode()
                return b"CAPTURING_START"
            raise AssertionError(path)
    transport=Transport()
    host=AirTypingFinaleHost(transport,boot="ab"*16,export_root=tmp_path,source_kind="simulation")
    result=host.run_once()
    assert result["status"]=="FINALE_COMPLETE"
    assert transport.receipts==list(range(1,8))
    assert all(verify_export(Path(p))["valid"] for p in result["exports"])
    with pytest.raises(ValueError,match="consumed"):host.run_once()


def test_fault_export_retains_controller_reason(records,tmp_path):
    class Transport:
        def __init__(self):self.leg=1
        def __call__(self,method,path,body=b""):
            suffix=path.rsplit("/",1)[-1]
            if suffix in ("start","next"):return b"CAPTURING_START"
            if suffix=="status":
                return b"SOURCE_POSE_REJECTED|4" if self.leg==4 else f"AWAITING_EXPORT|{self.leg}".encode()
            if suffix=="record":return records[self.leg-1].hex().encode()
            if suffix=="receipt":
                self.leg+=1
                return f"READY|{self.leg}".encode()
            raise AssertionError(path)
    host=AirTypingFinaleHost(Transport(),boot="ab"*16,export_root=tmp_path,
                             source_kind="simulation")
    with pytest.raises(ValueError,match="Finale stopped"):
        host.run_once()
    faults=list(tmp_path.glob("wizard-*/attachment-air-typing-final-fault.json"))
    assert len(faults)==1
    report=json.loads(faults[0].read_text())
    assert report["leg"]==4 and report["completed_legs"]==3
    assert report["last_controller_status"]=="SOURCE_POSE_REJECTED|4"


def test_native_route_uses_exact_selector_and_one_use(tmp_path):
    compiler=shutil.which("clang++")
    if not compiler:pytest.skip("Native compiler unavailable")
    source=(ROOT/"firmware/diagnostics/test_air_typing_routes.cpp").read_text()
    changes={
        '#include "air_typing_routes.h"':'#include <air_typing_routes.h>',
        '{2047,2225,1890,2716,1979,2041,2047}':'{1949,2099,2015,2610,2203,2041,2047}',
        '{2047,2217,1897,2711,1980,2040,2047}':'{1941,2098,2016,2609,2201,2040,2047}',
        '{0,8,-7,5,-1,1,0}':'{8,1,-1,1,2,1,0}',
        '/rocell/air-type/':'/rocell/air-type-final/',
        'AIR17':'AIR7',
    }
    for old,new in changes.items():
        assert old in source
        source=source.replace(old,new)
    target=tmp_path/"routes.exe"
    result=subprocess.run([compiler,"-std=c++17","-O2","-x","c++","-",
        "-I"+str(STAGE),"-I"+str(ROOT/"firmware/diagnostics"),"-o",str(target)],
        input=source,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    result=subprocess.run([str(target)],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,(result.returncode,result.stderr)
