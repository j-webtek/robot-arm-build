// Offline only: no bus, signing, routes or actuator API. Not part of installed r31.
#pragma once
#include <algorithm>
#include "local_shoulder_step_contract.h"
namespace rocell_diag {
struct CompensatedShoulderContract {
  ShoulderPreloadPose reference;
  int desired[2]={},command_goals[2]={},predicted[2]={};
  bool valid=false;
  static bool fresh(const ShoulderPreloadPose& p,uint64_t now,uint64_t age){
    if(!p.started_us||p.finished_us<p.started_us||p.finished_us-p.started_us>300000||
       now<p.finished_us||now-p.finished_us>age)return false;
    for(int i=0;i<7;++i)if(p.torque[i]!=1||p.position[i]>4095||p.goal[i]>4095)return false;
    return true;
  }
  bool prepare(const ShoulderPreloadPose& p,uint64_t now){
    valid=false;
    const int positions[7]={2047,2414,1702,2904,1591,2041,2047};
    const int goals[7]={2047,2405,1709,2907,1589,2040,2047};
    if(!fresh(p,now,2000000)||!LocalShoulderStepContract::stationary(p))return false;
    for(int i=0;i<7;++i)if(p.goal[i]!=goals[i]||std::abs(int(p.position[i])-positions[i])>2)return false;
    if(std::abs(int(p.position[1])-2415)>2||std::abs(int(p.position[2])-1702)>2)return false;
    desired[0]=p.position[1]-14;desired[1]=p.position[2]+14;
    int bestMax=999,bestSquare=999,bestTravel=999;
    // Same bounded integer projection as the host, independent implementation.
    for(int a=2387;a<=2451;++a){
      int b=4114-a,x=a+10,y=b-7;
      if(!(0<int(p.goal[1])-a&&int(p.goal[1])-a<=24&&0<b-int(p.goal[2])&&b-int(p.goal[2])<=24))continue;
      if(std::abs(a-int(p.position[1]))>32||std::abs(b-int(p.position[2]))>32)continue;
      int e=x-desired[0],f=y-desired[1],m=std::max(std::abs(e),std::abs(f)),sq=e*e+f*f,t=std::abs(a-int(p.goal[1]));
      if(m<bestMax||(m==bestMax&&(sq<bestSquare||(sq==bestSquare&&t<bestTravel)))){
        bestMax=m;bestSquare=sq;bestTravel=t;command_goals[0]=a;command_goals[1]=b;predicted[0]=x;predicted[1]=y;
      }
    }
    if(bestMax>2)return false;
    reference=p;valid=true;return true;
  }
  bool prewrite(const ShoulderPreloadPose& p,uint64_t now)const{
    if(!valid||!fresh(p,now,1000000)||!LocalShoulderStepContract::stationary(p)||
        p.started_us<=reference.finished_us||now<reference.finished_us||now-reference.finished_us>30000000)return false;
    for(int i=0;i<7;++i)if(p.goal[i]!=reference.goal[i]||std::abs(int(p.position[i])-int(reference.position[i]))>1)return false;
    return 0<int(p.position[1])-command_goals[0]&&int(p.position[1])-command_goals[0]<=32&&
      0<command_goals[1]-int(p.position[2])&&command_goals[1]-int(p.position[2])<=32;
  }
  // -1 fault, 0 valid but not arrived, 1 stationary at desired measured endpoint.
  int observe(const ShoulderPreloadPose& p,uint64_t now,uint64_t sent)const{
    if(!valid||!fresh(p,now,1000000)||sent<=reference.finished_us||p.started_us<=sent||p.finished_us-sent>5000000)return -1;
    bool arrived=true;
    for(int i=0;i<7;++i){
      bool selected=i==1||i==2,moving=p.feedback[i][2]||p.feedback[i][3]||p.feedback[i][10];
      int goal=selected?command_goals[i-1]:reference.goal[i];
      int dest=selected?desired[i-1]:reference.position[i];
      int low=std::min(dest,int(reference.position[i]))-2,high=std::max(dest,int(reference.position[i]))+2;
      if(p.goal[i]!=goal||p.position[i]<low||p.position[i]>high||(!selected&&moving))return -1;
      if(moving||(selected&&std::abs(int(p.position[i])-dest)>2))arrived=false;
    }
    return arrived?1:0;
  }
};
}
