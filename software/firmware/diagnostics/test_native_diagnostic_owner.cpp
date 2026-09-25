#define _USE_MATH_DEFINES
#include <cmath>
#include <cstdint>
#include <cstring>
#include <cstdlib>
#include <cassert>
int goalPos[7]={};
struct FakeLibrary {
  int Level=1,End=0,Error=0,writes=0,reads=0;
  bool moving=false,bad=false;
  int WritePosEx(uint8_t id,int16_t target,uint16_t speed,uint8_t acc){
    assert(id==14 && target==2132 && speed==20 && acc==1);++writes;return 1;
  }
  int Read(uint8_t,uint8_t,uint8_t* data,uint8_t width){++reads;data[0]=0x54;data[1]=0x08;if(width==15)data[10]=moving?1:0;return bad?0:width;}
} st;
int RoArmM3_elbowJointCtrlRad(uint8_t write,double,uint16_t,uint8_t){assert(!write);goalPos[3]=2132;return 2132;}
bool owner_fault=false;
bool rocellOwnerFault(){return owner_fault;}
int64_t clock_value=1000;
int64_t esp_timer_get_time(){return ++clock_value;}
#include "native_diagnostic_owner.h"
int main(int argc,char** argv){
  assert(argc==2);int scenario=atoi(argv[1]);
  if(scenario!=0)memcpy(rocellDiagnosticInstance,"0123456789abcdef0123456789abcdef",33);
  if(scenario==1)owner_fault=true;
  if(scenario==5)st.moving=true;
  if(scenario==6)st.bad=true;
  const char* payload="{\"T\":101,\"joint\":3,\"rad\":1.7,\"spd\":20,\"acc\":1}";
  const bool started=startReceivedDiagnostic("command",payload,strlen(payload),
      {scenario==4?1.8:1.6,1.9,40,1},2,100,1000000,{16,2,100,100});
  if(scenario<2){assert(!started && !rocellDiagnosticOwned && st.writes==0);return 0;}
  if(scenario==4){assert(!started && rocellDiagnosticOwned && st.writes==0);return 0;}
  if(scenario>=5){
    assert(!started && st.writes==0 && st.reads==2);assert(rocellDiagnosticEvidence.size()==2);
    for(size_t i=0;i<rocellDiagnosticEvidence.size();++i)puts(rocellDiagnosticEvidence.get(i)->json);
    return 0;
  }
  assert(started && rocellDiagnosticOwned && st.writes==1);
  assert(rocellDiagnosticEvidence.size()==6);
  assert(strcmp(rocellDiagnosticEvidence.get(1)->kind,"baseline")==0);
  pollReceivedDiagnostic();assert(st.reads==2);
  clock_value+=1000000;pollReceivedDiagnostic();assert(st.reads==4);
  if(scenario==2)assert(rocellRejectDiagnosticInterference());
  else owner_fault=true;
  clock_value+=1000000;pollReceivedDiagnostic();
  assert(st.reads==4 && st.writes==1 && rocellDiagnosticSession.state()==rocell_diag::SessionState::Fault);
  assert(!startReceivedDiagnostic("again",payload,strlen(payload),{1.6,1.9,40,1},2,100,1000000,{16,2,100,100}));
  assert(st.writes==1);
  for(size_t i=0;i<rocellDiagnosticEvidence.size();++i)puts(rocellDiagnosticEvidence.get(i)->json);
}
