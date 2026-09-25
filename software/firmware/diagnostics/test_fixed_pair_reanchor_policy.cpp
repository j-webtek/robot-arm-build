#include "fixed_pair_reanchor_policy.h"
#include <cstring>
#include <string>
using namespace rocell_diag;

static void fill(ShoulderPreloadPose (&poses)[3],bool endpoint=false){
  for(int n=0;n<3;++n){
    auto& p=poses[n];
    p.started_us=(endpoint?2000000:1000000)+uint64_t(n)*150000;
    p.finished_us=p.started_us+50000;
    for(int i=0;i<7;++i){
      p.goal[i]=2000;p.position[i]=2000;p.torque[i]=1;
    }
    p.goal[1]=endpoint?2389:2386;
    p.goal[2]=endpoint?1725:1728;
    p.position[1]=endpoint?2391:2390;
    p.position[2]=endpoint?1724:1725;
    for(int i=0;i<7;++i){
      p.feedback[i][0]=uint8_t(p.position[i]);
      p.feedback[i][1]=uint8_t(p.position[i]>>8);
    }
  }
}
int main(int argc,char** argv){
  if(argc!=2)return 2;
  ShoulderPreloadPose before[3],after[3];fill(before);fill(after,true);
  std::string mode=argv[1];
  if(mode=="start_goal")before[2].goal[1]=2385;
  if(mode=="start_position")before[2].position[1]=2387;
  if(mode=="start_moving")before[1].feedback[1][2]=1;
  if(mode=="start_stale")before[2].finished_us=1000000;
  if(mode=="endpoint_goal")after[2].goal[1]=2388;
  if(mode=="endpoint_position")after[2].position[1]=2394;
  if(mode=="transient_excursion"){
    after[0].position[1]=2394;
    after[0].feedback[1][0]=uint8_t(2394);
    after[0].feedback[1][1]=uint8_t(2394>>8);
  }
  if(mode=="neighbor")after[2].goal[4]=2001;
  if(mode=="transient_neighbor"){
    after[0].position[4]=2003;
    after[0].feedback[4][0]=uint8_t(2003);
    after[0].feedback[4][1]=uint8_t(2003>>8);
  }
  if(mode=="postwrite_time")after[0].started_us=1400000;
  if(mode=="readback")after[2].feedback[1][0]=0;
  bool accepted=FixedPairReanchorPolicy::start(before,1400000)&&
      FixedPairReanchorPolicy::endpoint(before,after,1500000,2400000);
  return accepted==(mode=="success")?0:1;
}
