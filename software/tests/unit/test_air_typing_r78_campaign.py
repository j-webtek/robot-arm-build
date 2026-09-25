from pathlib import Path
import hashlib
import json
import shutil
import subprocess

import pytest

from rocell.application.air_typing_r78_campaign import (
    AirTypingASideHost,TARGETS,assess_leg,assess_source_fault,
)
from rocell.application.wizard_diagnostic_export import verify_export


ROOT=Path(__file__).resolve().parents[2]
STAGE=ROOT/".firmware-tools/configured-diagnostic-candidate-r78/RoArm-M3_example"


def specialized(source):
    changes={
        '#include "air_typing_owner.h"':'#include <air_typing_owner.h>',
        '{2047,2225,1890,2716,1979,2041,2047}':'{1987,2082,2031,2600,2235,2041,2047}',
        '{2047,2217,1897,2711,1980,2040,2047}':'{1994,2076,2038,2598,2234,2040,2047}',
        '{0,8,-7,5,-1,1,0}':'{0,8,-7,5,-1,1,0}',
    }
    for old,new in changes.items():
        assert old in source
        if old!=new:source=source.replace(old,new)
    return source


@pytest.fixture(scope="module")
def native(tmp_path_factory):
    compiler=shutil.which("clang++")
    if not compiler:pytest.skip("Native compiler unavailable")
    source=specialized((ROOT/"firmware/diagnostics/test_air_typing_owner.cpp").read_text())
    target=tmp_path_factory.mktemp("r78-native")/"owner.exe"
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
@pytest.mark.parametrize("leg",range(1,5))
def test_native_fault_stops(native,mode,leg):
    result=subprocess.run([str(native),mode,str(leg)],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,(mode,leg,result.returncode,result.stderr)


def test_all_records_replay_independently(records):
    assert len(records)==len(TARGETS)==4
    previous=None
    for leg,raw in enumerate(records,1):
        previous=assess_leg(raw,boot="ab"*16,leg=leg,previous=previous)
        assert previous["status"]=="A_SIDE_LEG_ENDPOINT_VERIFIED"
        assert previous["target_goals"]==list(TARGETS[leg-1])
    with pytest.raises(ValueError):assess_leg(records[0],boot="cd"*16,leg=1)
    with pytest.raises(ValueError):assess_leg(records[0],boot="ab"*16,leg=2)


def test_four_leg_export_gated_host(records,tmp_path):
    class Transport:
        def __init__(self):self.leg=1;self.receipts=[]
        def __call__(self,method,path,body=b""):
            suffix=path.rsplit("/",1)[-1]
            if suffix=="start":
                assert method=="POST" and body==b"AIR4"
                return b"CAPTURING_START"
            if suffix=="status":return f"AWAITING_EXPORT|{self.leg}".encode()
            if suffix=="record":return records[self.leg-1].hex().encode()
            if suffix=="receipt":
                assert body==f'{self.leg}:{hashlib.sha256(records[self.leg-1]).hexdigest()}'.encode()
                self.receipts.append(self.leg);self.leg+=1
                return b"COMPLETE" if self.leg==5 else f"READY|{self.leg}".encode()
            if suffix=="next":
                assert body==str(self.leg).encode()
                return b"CAPTURING_START"
            raise AssertionError(path)
    transport=Transport()
    host=AirTypingASideHost(transport,boot="ab"*16,export_root=tmp_path,
                            source_kind="simulation")
    result=host.run_once()
    assert result["status"]=="A_SIDE_COMPLETE"
    assert transport.receipts==[1,2,3,4]
    assert all(verify_export(Path(p))["valid"] for p in result["exports"])
    with pytest.raises(ValueError,match="consumed"):host.run_once()


def test_rejected_source_is_exported_without_write(tmp_path):
    source=dict(schema="rocell.air_source_fault.v1",leg=1,samples=[dict(
        started_us=100+i*200,finished_us=150+i*200,
        positions=[1987,2082,2031,2600,2235,2041,2047],
        goals=[1994,2076,2038,2598,2234,2040,2047],torque=[1]*7)
        for i in range(3)])
    raw=json.dumps(source).encode()
    assert assess_source_fault(raw,leg=1)==source
    class Transport:
        def __init__(self):self.calls=[]
        def __call__(self,method,path,body=b""):
            self.calls.append((method,path))
            suffix=path.rsplit("/",1)[-1]
            if suffix=="start":return b"CAPTURING_START"
            if suffix=="status":return b"SOURCE_POSE_REJECTED|1"
            if suffix=="source-fault":return raw
            raise AssertionError(path)
    transport=Transport()
    with pytest.raises(ValueError,match="stopped"):
        AirTypingASideHost(transport,boot="ab"*16,export_root=tmp_path,
                           source_kind="simulation").run_once()
    fault_files=list(tmp_path.glob("wizard-*/attachment-air-typing-last-fault.json"))
    assert len(fault_files)==1
    report=json.loads(fault_files[0].read_text())
    assert report["source_fault"]==source and report["completed_legs"]==0
    assert all(method=="GET" for method,_ in transport.calls[1:])


def test_native_route_and_source_fault(tmp_path):
    compiler=shutil.which("clang++")
    if not compiler:pytest.skip("Native compiler unavailable")
    source=(ROOT/"firmware/diagnostics/test_air_typing_routes.cpp").read_text()
    changes={
        '#include "air_typing_routes.h"':'#include <air_typing_routes.h>',
        '{2047,2225,1890,2716,1979,2041,2047}':'{1987,2082,2031,2600,2235,2041,2047}',
        '{2047,2217,1897,2711,1980,2040,2047}':'{1994,2076,2038,2598,2234,2040,2047}',
        '/rocell/air-type/':'/rocell/air-type-last/',
        'AIR17':'AIR4',
        'web.routes.size()==5':'web.routes.size()==6',
    }
    for old,new in changes.items():
        assert old in source
        source=source.replace(old,new)
    old='  routes.poll();assert(services.writes==AirTypingPolicy::legs);\n}'
    new='''  routes.poll();assert(services.writes==AirTypingPolicy::legs);
  Services rejected{clock};rejected.goals[0]++;
  Web web2;AirTypingRoutes<Crypto,Services,Clock,Web> failed(crypto,rejected,clock,web2,boot);
  failed.register_routes();web2.body="AIR4";web2.routes["/rocell/air-type-last/start"]();
  assert(web2.status==202);
  web2.body="";
  for(unsigned i=0;i<3;++i){clock.now+=150000;failed.poll();}
  web2.routes["/rocell/air-type-last/status"]();
  assert(web2.response=="SOURCE_POSE_REJECTED|1"&&rejected.writes==0);
  web2.routes["/rocell/air-type-last/source-fault"]();
  assert(web2.status==200&&web2.response.find("rocell.air_source_fault.v1")!=std::string::npos);
  assert(web2.response.find("\\"positions\\"")!=std::string::npos);
}'''
    assert old in source
    source=source.replace(old,new)
    target=tmp_path/"routes.exe"
    result=subprocess.run([compiler,"-std=c++17","-O2","-x","c++","-",
        "-I"+str(STAGE),"-I"+str(ROOT/"firmware/diagnostics"),"-o",str(target)],
        input=source,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    result=subprocess.run([str(target)],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,(result.returncode,result.stderr)
