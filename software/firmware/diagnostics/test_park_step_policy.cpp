#include "park_step_policy.h"
#include <cstdio>
#include <string>
using namespace rocell_diag;

static ShoulderPreloadPose pose(int index,bool endpoint){
  ShoulderPreloadPose sample;
  sample.started_us=(endpoint?2000000:1000000)+index*150000;
  sample.finished_us=sample.started_us+50000;
  for(int i=0;i<7;++i){
    sample.goal[i]=ParkStepPolicy::reference_goals[i];
    sample.position[i]=ParkStepPolicy::reference_positions[i];
    sample.torque[i]=1;
  }
  if(endpoint){
    sample.goal[1]=2377;sample.goal[2]=1737;
    sample.position[1]=2378;sample.position[2]=1736;
  }
  for(int i=0;i<7;++i){
    sample.feedback[i][0]=uint8_t(sample.position[i]);
    sample.feedback[i][1]=uint8_t(sample.position[i]>>8);
  }
  return sample;
}

int main(int argc,char** argv){
  if(argc!=2)return 2;
  const std::string mode=argv[1];
  ShoulderPreloadPose before[3],after[3];
  for(int i=0;i<3;++i){before[i]=pose(i,false);after[i]=pose(i,true);}
  if(mode=="neighbor_drift")after[2].position[3]+=3;
  if(mode=="wrong_goal")after[2].goal[1]=2378;
  if(mode=="wrong_direction")after[2].position[1]=2394;
  if(mode=="no_response")after[2].position[1]=2390;
  if(mode=="disabled")before[2].torque[2]=0;
  if(mode=="stale")before[2].started_us=0;
  if(mode=="excess_target"){
    if(ParkStepPolicy::start(before,1451000,2365,1749))return 1;
    return 0;
  }
  if(mode=="success"){
    if(!ParkStepPolicy::start(before,1451000,2377,1737)||
       !ParkStepPolicy::endpoint(before,after,1451000,2451000,2377,1737))return 1;
    return 0;
  }
  if(mode=="disabled"||mode=="stale"){
    return ParkStepPolicy::start(before,1451000,2377,1737)?1:0;
  }
  return ParkStepPolicy::endpoint(before,after,1451000,2451000,2377,1737)?1:0;
}
