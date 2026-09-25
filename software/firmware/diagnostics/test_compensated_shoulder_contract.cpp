#include "compensated_shoulder_contract.h"
#include <cassert>
#include <iostream>
int main(int argc,char** argv){
  rocell_diag::ShoulderPreloadPose p;
  int positions[7]={2047,2414,1702,2904,1591,2041,2047};
  int goals[7]={2047,2405,1709,2907,1589,2040,2047};
  for(int i=0;i<7;++i){p.position[i]=positions[i];p.goal[i]=goals[i];p.torque[i]=1;}
  p.started_us=1;p.finished_us=1000;
  rocell_diag::CompensatedShoulderContract c;
  assert(c.prepare(p,1001));assert(c.command_goals[0]==2391&&c.command_goals[1]==1723);
  auto fresh=p;fresh.started_us=2000;fresh.finished_us=3000;
  assert(c.prewrite(fresh,3001));assert(!c.prewrite(fresh,31000000));
  for(int i=0;i<7;++i){
    auto changed=fresh;changed.position[i]+=2;assert(!c.prewrite(changed,3001));
    changed=fresh;changed.goal[i]++;assert(!c.prewrite(changed,3001));
    changed=fresh;changed.torque[i]=0;assert(!c.prewrite(changed,3001));
  }
  if(argc==3){
    p.position[1]=std::atoi(argv[1]);p.position[2]=std::atoi(argv[2]);
    bool ok=c.prepare(p,1001);
    std::cout<<ok<<" "<<c.command_goals[0]<<" "<<c.command_goals[1]<<"\n";
  }else if(argc==2){
    std::string mode=argv[1];fresh.position[1]=c.desired[0];fresh.position[2]=c.desired[1];
    fresh.goal[1]=c.command_goals[0];fresh.goal[2]=c.command_goals[1];
    fresh.started_us=4000;fresh.finished_us=5000;
    if(mode=="short")fresh.position[1]+=5;
    if(mode=="overshoot")fresh.position[1]-=3;
    if(mode=="goal")fresh.goal[1]=c.desired[0];
    if(mode=="neighbor")fresh.position[4]+=3;
    if(mode=="moving")fresh.feedback[1][2]=1;
    if(mode=="oldgoal")fresh.position[1]=c.command_goals[0];
    if(mode=="disabled")fresh.torque[1]=0;
    if(mode=="stale"){fresh.started_us=6000000;fresh.finished_us=6001000;}
    std::cout<<c.observe(fresh,fresh.finished_us+1,3500)<<"\n";
  }
}
