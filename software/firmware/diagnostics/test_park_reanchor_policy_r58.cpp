#include "park_reanchor_policy_r58.h"
using namespace rocell_diag;

static ShoulderPreloadPose sample(int n,bool after){
  ShoulderPreloadPose p{};
  p.started_us=(after?2000000:1000000)+uint64_t(n)*150000;
  p.finished_us=p.started_us+50000;
  for(int i=0;i<7;++i){
    p.goal[i]=ParkReanchorPolicy::source_goals[i];
    p.position[i]=ParkReanchorPolicy::source_positions[i];
    p.torque[i]=1;
  }
  if(after){
    p.goal[1]=ParkReanchorPolicy::target12;
    p.goal[2]=ParkReanchorPolicy::target13;
    p.position[1]=ParkReanchorPolicy::expected12;
    p.position[2]=ParkReanchorPolicy::expected13;
  }
  for(int i=0;i<7;++i){
    p.feedback[i][0]=uint8_t(p.position[i]);
    p.feedback[i][1]=uint8_t(p.position[i]>>8);
  }
  return p;
}

int main(){
  ShoulderPreloadPose before[3]={sample(0,false),sample(1,false),sample(2,false)};
  ShoulderPreloadPose after[3]={sample(0,true),sample(1,true),sample(2,true)};
  if(!ParkReanchorPolicy::start(before,1351000)||
     !ParkReanchorPolicy::endpoint(before,after,1351000,2351000))return 1;
  after[2].position[1]=2420;
  after[2].feedback[1][0]=uint8_t(after[2].position[1]);
  after[2].feedback[1][1]=uint8_t(after[2].position[1]>>8);
  if(ParkReanchorPolicy::bounded_sample(before[2],after[2]))return 2;
  before[2]=sample(2,false);before[2].goal[2]=1724;
  if(ParkReanchorPolicy::start(before,1351000))return 3;
  return 0;
}
