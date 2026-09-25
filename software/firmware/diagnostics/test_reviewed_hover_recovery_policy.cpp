#include "reviewed_hover_recovery_policy.h"
#include <cassert>
#include <cstring>
using namespace rocell_diag;

static void sample(ShoulderPreloadPose& pose,uint64_t started,uint64_t finished,
                   const uint16_t (&goals)[7],const uint16_t (&positions)[7]){
  pose={};pose.started_us=started;pose.finished_us=finished;
  for(unsigned i=0;i<7;++i){
    pose.goal[i]=goals[i];pose.position[i]=positions[i];pose.torque[i]=1;
    pose.feedback[i][0]=uint8_t(positions[i]);
    pose.feedback[i][1]=uint8_t(positions[i]>>8);
  }
}

int main(){
  ReviewedHoverRecoveryPolicy policy;
  constexpr uint8_t ids[5]={0,1,2,1,0};
  uint8_t wrong[5]={0,1,2,1,1};
  assert(!policy.configure(wrong,5));
  assert(!policy.configure(ids,4));
  assert(policy.configure(ids,5)&&!policy.configure(ids,5));
  const uint16_t source[7]={2047,2093,2021,2618,2197,2040,2047};
  const uint16_t positions[7]={2041,2094,2020,2620,2199,2041,2047};
  const uint16_t clear[7]={2047,2075,2039,2600,2233,2040,2047};
  for(unsigned i=0;i<7;++i){
    assert(policy.source_goals[i]==source[i]);
    assert(policy.target_goals[i]==clear[i]);
  }
  ShoulderPreloadPose reads[3];
  sample(reads[0],850000,900000,source,positions);
  sample(reads[1],1050000,1100000,source,positions);
  sample(reads[2],1250000,1300000,source,positions);
  assert(policy.source(reads,1350000));
  reads[2].goal[4]++;assert(!policy.source(reads,1350000));
  reads[2].goal[4]--;reads[2].torque[2]=0;
  assert(!policy.source(reads,1350000));reads[2].torque[2]=1;
  reads[2].feedback[1][2]=1;assert(!policy.source(reads,1350000));
  reads[2].feedback[1][2]=0;reads[2].position[4]+=7;
  reads[2].feedback[4][0]=uint8_t(reads[2].position[4]);
  assert(!policy.source(reads,1350000));
  reads[2].position[4]-=7;
  reads[2].feedback[4][0]=uint8_t(reads[2].position[4]);
  assert(policy.source(reads,1350000));
  ShoulderPreloadPose final{};
  sample(final,1400000,1450000,clear,clear);
  assert(!policy.advance(final,2));
  final.goal[4]++;assert(!policy.advance(final,1));final.goal[4]--;
  assert(policy.advance(final,1));
  for(unsigned i=0;i<7;++i){
    assert(policy.source_goals[i]==clear[i]);
    assert(policy.target_goals[i]==source[i]);
  }
  assert(policy.source_tolerance==1);
  assert(!policy.advance(final,1)&&!policy.advance(final,5));
  return 0;
}
