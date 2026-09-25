// The pytest harness injects exact hash-verified reference function bodies.
#define _USE_MATH_DEFINES
#include <cmath>
#include <cstdint>
#include <cassert>
#include <algorithm>
#include <cstdio>
using byte=uint8_t;using u16=uint16_t;using u8=uint8_t;using s16=int16_t;
const int ARM_SERVO_POS_RANGE=4096,ELBOW_SERVO_ID=14;
int goalPos[7]={};
template<class A,class B,class C> int constrain(A n,B low,C high){return std::min<int>(high,std::max<int>(low,n));}
struct Bus {
  int writes=0,last_target=0,Level=1,End=0,Error=0;
  int WritePosEx(int,int target,int,int){++writes;last_target=target;return 1;}
} st;
#include "pinned_elbow_functions.h"
#include "reference_elbow_admission.h"
#include "received_session.h"
#include "evidence_store.h"
struct Clock{uint64_t now_us(){return ++t;}uint64_t t=1000;};
int main(){
  rocell_diag::ReferenceElbowAdmission admission({1.6,1.9,40,1});
  uint16_t target=0;goalPos[3]=2222;
  for(double rad:{1.6,1.7,1.8,1.9}){
    const int expected=RoArmM3_elbowJointCtrlRad(0,rad,20,1);goalPos[3]=2222;
    assert(admission.admit_and_convert(rad,20,1,target));
    assert(target==expected && goalPos[3]==2222 && st.writes==0);
  }
  for(double rad:{1.59,1.91,static_cast<double>(INFINITY),static_cast<double>(NAN)}){
    assert(!admission.admit_and_convert(rad,20,1,target));
    assert(goalPos[3]==2222 && st.writes==0);
  }
  assert(!admission.admit_and_convert(1.7,41,1,target));
  assert(!admission.admit_and_convert(1.7,20,2,target));
  rocell_diag::ReferenceElbowAdmission bad({1.9,1.6,40,1});
  assert(!bad.admit_and_convert(1.7,20,1,target));
  assert(st.writes==0 && goalPos[3]==2222);
  rocell_diag::ReceivedSession session;rocell_diag::EvidenceStore<8> store;Clock clock;
  const char* payload="{\"T\":101,\"joint\":3,\"rad\":1.7,\"spd\":20,\"acc\":1}";
  assert(session.start(st,clock,store,admission,"boot","native-conversion",payload,strlen(payload),1,100));
  assert(st.writes==1 && st.last_target==2132 && goalPos[3]==2222);
  puts(store.get(1)->json);puts(store.get(3)->json);
}
