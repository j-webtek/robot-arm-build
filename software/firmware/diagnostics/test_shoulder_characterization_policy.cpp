#include "shoulder_characterization_policy.h"
#include <iostream>
void read_pose(rocell_diag::ShoulderPreloadPose& p){
  std::cin>>p.started_us>>p.finished_us;
  for(int i=0;i<7;++i){unsigned torque,moving;
    std::cin>>p.position[i]>>p.goal[i]>>torque>>moving;
    p.torque[i]=torque;p.feedback[i][2]=moving;
  }
}
int main(){
  rocell_diag::ShoulderPreloadPose before,samples[64];uint16_t goals[2],bounds[7][2];
  read_pose(before);std::cin>>goals[0]>>goals[1];
  for(auto& b:bounds)std::cin>>b[0]>>b[1];
  unsigned count,delivery,exported;std::cin>>count>>delivery>>exported;
  if(count>64)return 2;
  for(unsigned i=0;i<count;++i)read_pose(samples[i]);
  if(!std::cin)return 3;
  auto r=rocell_diag::ShoulderCharacterizationPolicy::assess(before,goals,samples,count,bounds,delivery,exported);
  const char* status=r.outcome==rocell_diag::CharacterizationOutcome::Stop?"STOP":
    r.outcome==rocell_diag::CharacterizationOutcome::SettledAccurate?"SETTLED_ACCURATE":"SETTLED_MISS";
  std::cout<<status<<" "<<r.reason<<" "<<r.continuation_eligible()<<"\n";
}
