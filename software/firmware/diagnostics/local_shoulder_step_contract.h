// Offline typed contract. No bus or actuator API. Not admitted by r29/r30.
#pragma once
#include "shoulder_preload_candidate.h"
namespace rocell_diag {
struct LocalShoulderStepContract {
  ShoulderPreloadPose reference;
  uint16_t targets[2]={};
  bool valid=false;
  static bool stationary(const ShoulderPreloadPose& p){
    for(int i=0;i<7;++i)if(p.torque[i]!=1||p.position[i]>4095||p.goal[i]>4095||
        p.feedback[i][2]||p.feedback[i][3]||p.feedback[i][10])return false;
    return true;
  }
  bool prepare(const ShoulderPreloadPose& p,unsigned step,uint64_t now){
    valid=false;
    if(!stationary(p)||step<12||step>24||!p.started_us||p.finished_us<p.started_us||
       p.finished_us-p.started_us>300000||now<p.finished_us||now-p.finished_us>2000000)return false;
    const int positions[7]={2047,2429,1688,2904,1591,2041,2047};
    const int goals[7]={2047,2419,1695,2907,1589,2040,2047};
    for(int i=0;i<7;++i)if(std::abs(int(p.position[i])-positions[i])>2||p.goal[i]!=goals[i])return false;
    const int a=int(p.position[1])-int(step),b=int(p.goal[1])+int(p.goal[2])-a;
    if(a<0||b>4095||a>=p.goal[1]||b<=p.goal[2]||b<=p.position[2]||b-p.position[2]>32)return false;
    reference=p;targets[0]=a;targets[1]=b;valid=true;return true;
  }
  bool prewrite(const ShoulderPreloadPose& fresh,uint64_t now)const{
    if(!valid||!stationary(fresh)||fresh.started_us<=reference.finished_us||
       fresh.finished_us<fresh.started_us||fresh.finished_us-fresh.started_us>300000||
       now<fresh.finished_us||now-fresh.finished_us>1000000||
       now<reference.finished_us||now-reference.finished_us>30000000)return false;
    for(int i=0;i<7;++i)if(fresh.goal[i]!=reference.goal[i]||
        std::abs(int(fresh.position[i])-int(reference.position[i]))>1)return false;
    // Both directions and travel bounds must still hold immediately before send.
    return targets[0]<fresh.position[1]&&fresh.position[1]-targets[0]<=32&&
           targets[1]>fresh.position[2]&&targets[1]-fresh.position[2]<=32;
  }
};
}
