#include "p4_wrist_policy.h"
#include <cassert>
using namespace rocell_diag;
static ShoulderPreloadPose pose(int n,bool after){
  ShoulderPreloadPose p;
  p.started_us=(after?2000000:1000000)+n*150000;
  p.finished_us=p.started_us+50000;
  for(int i=0;i<7;++i){
    p.goal[i]=after?P4WristPolicy::target_goals[i]:P4WristPolicy::source_goals[i];
    p.position[i]=P4WristPolicy::source_positions[i];p.torque[i]=1;
  }
  if(after)p.position[4]=1977;
  for(int i=0;i<7;++i){p.feedback[i][0]=uint8_t(p.position[i]);p.feedback[i][1]=uint8_t(p.position[i]>>8);}
  return p;
}
static void position(ShoulderPreloadPose& p,int i,int value){
  p.position[i]=value;p.feedback[i][0]=uint8_t(value);p.feedback[i][1]=uint8_t(value>>8);
}
int main(){
  ShoulderPreloadPose before[3]={pose(0,false),pose(1,false),pose(2,false)};
  ShoulderPreloadPose after[3]={pose(0,true),pose(1,true),pose(2,true)};
  assert(P4WristPolicy::source(before,1400000));
  assert(P4WristPolicy::endpoint(before,after,1500000,2400000));
  auto bad=after[2];position(bad,1,bad.position[1]+3);
  assert(!P4WristPolicy::bounded_endpoint_sample(before[2],bad));
  bad=after[2];position(bad,4,1910);
  assert(!P4WristPolicy::bounded_endpoint_sample(before[2],bad));
  bad=after[2];position(bad,4,1993);
  assert(!P4WristPolicy::bounded_endpoint_sample(before[2],bad));
  bad=after[2];bad.goal[4]++;
  assert(!P4WristPolicy::bounded_endpoint_sample(before[2],bad));
  for(auto& p:after)position(p,4,1940);
  assert(!P4WristPolicy::endpoint(before,after,1500000,2400000));
  position(before[2],4,1916);
  assert(!P4WristPolicy::source(before,1400000));
}
