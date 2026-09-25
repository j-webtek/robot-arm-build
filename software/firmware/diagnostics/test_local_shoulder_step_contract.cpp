#include "local_shoulder_step_contract.h"
#include <cassert>
#include <iostream>
int main(int argc,char** argv){
  rocell_diag::ShoulderPreloadPose pose;
  int positions[7]={2047,2429,1688,2904,1591,2041,2047};
  int goals[7]={2047,2419,1695,2907,1589,2040,2047};
  for(int i=0;i<7;++i){pose.position[i]=positions[i];pose.goal[i]=goals[i];pose.torque[i]=1;}
  pose.started_us=1;pose.finished_us=1000;
  rocell_diag::LocalShoulderStepContract plan;
  assert(plan.prepare(pose,24,1001)&&plan.targets[0]==2405&&plan.targets[1]==1709);
  auto fresh=pose;fresh.started_us=2000;fresh.finished_us=3000;
  assert(plan.prewrite(fresh,3001));
  assert(!plan.prewrite(fresh,1003001));
  assert(!plan.prewrite(fresh,31000000));
  for(int i=0;i<7;++i){
    auto changed=fresh;changed.position[i]+=2;assert(!plan.prewrite(changed,3001));
    changed=fresh;changed.goal[i]++;assert(!plan.prewrite(changed,3001));
    changed=fresh;changed.torque[i]=0;assert(!plan.prewrite(changed,3001));
    changed=fresh;changed.feedback[i][2]=1;assert(!plan.prewrite(changed,3001));
  }
  assert(!plan.prepare(pose,25,1001));assert(!plan.valid);
  assert(!plan.prepare(pose,24,2001001));
  if(argc==4){
    pose.position[1]=std::atoi(argv[1]);pose.position[2]=std::atoi(argv[2]);
    bool ok=plan.prepare(pose,std::atoi(argv[3]),1001);
    std::cout<<(ok?1:0)<<" "<<plan.targets[0]<<" "<<plan.targets[1]<<"\n";
  }
}
