"""Native owner and route regression for isolated-elbow eight-leg candidate."""
from pathlib import Path
import hashlib
import shutil
import subprocess

import pytest

from rocell.application.air_typing_elbow_direction_recipe import TARGETS
from rocell.application.air_typing_r81_campaign import AirTypingElbowDirectionHost, assess_leg
from rocell.application.wizard_diagnostic_export import verify_export


ROOT=Path(__file__).resolve().parents[2]
STAGE=ROOT/".firmware-tools/configured-diagnostic-candidate-r81/RoArm-M3_example"


def specialized_owner():
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
    return source


@pytest.fixture(scope="module")
def native(tmp_path_factory):
    compiler=shutil.which("clang++")
    if not compiler:pytest.skip("Native compiler unavailable")
    target=tmp_path_factory.mktemp("r81-native")/"owner.exe"
    result=subprocess.run([compiler,"-std=c++17","-O2","-x","c++","-",
        "-I"+str(STAGE),"-I"+str(ROOT/"firmware/diagnostics"),"-o",str(target)],
        input=specialized_owner(),capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    return target


def test_exact_eight_records(native):
    result=subprocess.run([str(native),"success"],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
    lines=result.stdout.splitlines()
    assert len(lines)==8
    for leg,line in enumerate(lines,1):
        raw=bytes.fromhex(line)
        assert len(raw)==1130 and raw[:10]==b"RCAIRAB701" and raw[26]==leg
        assert int.from_bytes(raw[27:29],"big")==TARGETS[leg-1][4]


def test_host_verifies_and_exports_every_native_record(native,tmp_path):
    result=subprocess.run([str(native),"success"],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
    records=[bytes.fromhex(line) for line in result.stdout.splitlines()]
    prior=None
    for leg,raw in enumerate(records,1):
        prior=assess_leg(raw,boot="ab"*16,leg=leg,previous=prior)
        assert prior["target_goals"]==list(TARGETS[leg-1])
        assert prior["selected_joints"]==[3]
    class Transport:
        def __init__(self):self.leg=1;self.receipts=[]
        def __call__(self,method,path,body=b""):
            suffix=path.rsplit("/",1)[-1]
            assert path.startswith("/rocell/air-elbow-direction/")
            if suffix=="start":
                assert method=="POST" and body==b"AIRE8"
                return b"CAPTURING_START"
            if suffix=="status":return f"AWAITING_EXPORT|{self.leg}".encode()
            if suffix=="record":return records[self.leg-1].hex().encode()
            if suffix=="receipt":
                assert body==f'{self.leg}:{hashlib.sha256(records[self.leg-1]).hexdigest()}'.encode()
                self.receipts.append(self.leg);self.leg+=1
                return b"COMPLETE" if self.leg==9 else f"READY|{self.leg}".encode()
            if suffix=="next":
                assert body==str(self.leg).encode()
                return b"CAPTURING_START"
            raise AssertionError(path)
    transport=Transport()
    host=AirTypingElbowDirectionHost(transport,boot="ab"*16,export_root=tmp_path,
                                     source_kind="simulation")
    result=host.run_once()
    assert result["status"]=="ELBOW_DIRECTION_COMPLETE"
    assert transport.receipts==list(range(1,9))
    assert all(verify_export(Path(p))["valid"] for p in result["exports"])
    with pytest.raises(ValueError,match="consumed"):host.run_once()


@pytest.mark.parametrize("mode",["delivery","wrong_endpoint","evidence","source",
                                  "prewrite","stale","timeout","expired"])
@pytest.mark.parametrize("leg",range(1,9))
def test_native_fault_stops_without_retry(native,mode,leg):
    result=subprocess.run([str(native),mode,str(leg)],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,(mode,leg,result.returncode,result.stderr)


def test_native_route_fixed_selector_and_read_only_fault(tmp_path):
    compiler=shutil.which("clang++")
    if not compiler:pytest.skip("Native compiler unavailable")
    source=(ROOT/"firmware/diagnostics/test_air_typing_routes.cpp").read_text()
    changes={
        '#include "air_typing_routes.h"':'#include <air_typing_routes.h>',
        '{2047,2225,1890,2716,1979,2041,2047}':'{2041,2082,2033,2609,2233,2041,2047}',
        '{2047,2217,1897,2711,1980,2040,2047}':'{2047,2075,2039,2600,2233,2040,2047}',
        '{0,8,-7,5,-1,1,0}':'{0,1,-1,1,2,1,0}',
        'goals[i]=target[i];pos[i]=uint16_t(int(target[i])+residual[i]);':
            'if(goals[i]!=target[i])pos[i]=uint16_t(int(target[i])+residual[i]);goals[i]=target[i];',
        'web.routes.size()==5':'web.routes.size()==6',
        '/rocell/air-type/':'/rocell/air-elbow-direction/',
        'AIR17':'AIRE8',
    }
    for old,new in changes.items():
        assert old in source
        source=source.replace(old,new)
    original='  routes.poll();assert(services.writes==AirTypingPolicy::legs);\n}'
    replacement='''  routes.poll();assert(services.writes==AirTypingPolicy::legs);
  Services rejected{clock};rejected.goals[0]++;
  Web web2;AirTypingRoutes<Crypto,Services,Clock,Web> failed(crypto,rejected,clock,web2,boot);
  failed.register_routes();web2.body="AIRE8";web2.routes["/rocell/air-elbow-direction/start"]();
  assert(web2.status==202);web2.body="";
  for(unsigned i=0;i<3;++i){clock.now+=150000;failed.poll();}
  web2.routes["/rocell/air-elbow-direction/status"]();
  assert(web2.response=="SOURCE_POSE_REJECTED|1"&&rejected.writes==0);
  web2.routes["/rocell/air-elbow-direction/source-fault"]();
  assert(web2.status==200&&web2.response.find("rocell.air_source_fault.v1")!=std::string::npos);
}'''
    assert original in source
    source=source.replace(original,replacement)
    target=tmp_path/"routes.exe"
    result=subprocess.run([compiler,"-std=c++17","-O2","-x","c++","-",
        "-I"+str(STAGE),"-I"+str(ROOT/"firmware/diagnostics"),"-o",str(target)],
        input=source,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    result=subprocess.run([str(target)],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,(result.returncode,result.stderr)
