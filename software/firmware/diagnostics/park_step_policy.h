// Offline bounded shoulder-rise policy. No transport, route, or bus write.
// Encoder direction alone cannot prove that the gripper rose in space.
#pragma once
#include "shoulder_characterization_policy.h"
#include <cstdlib>
namespace rocell_diag {
struct ParkStepPolicy {
  static constexpr uint16_t reference_goals[7]={2047,2389,1725,2907,1589,2040,2047};
  static constexpr uint16_t reference_positions[7]={2047,2390,1724,2904,1591,2041,2047};
  static constexpr int step_counts=12;
  static constexpr int total_counts=48;

  static bool stable(const ShoulderPreloadPose (&samples)[3],uint64_t now,
                     uint64_t after_us=0){
    if(!now||samples[0].started_us<=after_us||samples[2].finished_us>now||
       now-samples[2].finished_us>1000000||
       samples[2].finished_us-samples[0].started_us<200000||
       samples[2].finished_us-samples[0].started_us>1500000)return false;
    for(int n=0;n<3;++n){
      const auto& sample=samples[n];
      if(!ShoulderCharacterizationPolicy::valid(sample))return false;
      if(n&&(sample.started_us<=samples[n-1].finished_us||
             sample.started_us-samples[n-1].finished_us<100000))return false;
      for(int i=0;i<7;++i){
        if(ShoulderCharacterizationPolicy::moving(sample,i)||
           sample.goal[i]!=samples[0].goal[i]||
           std::abs(int(sample.position[i])-int(samples[0].position[i]))>1||
           (sample.feedback[i][0]|uint16_t(sample.feedback[i][1])<<8)!=
               sample.position[i])return false;
      }
    }
    return true;
  }

  static bool start(const ShoulderPreloadPose (&samples)[3],uint64_t now,
                    uint16_t target12,uint16_t target13){
    if(!stable(samples,now))return false;
    const auto& current=samples[2];
    for(int i=0;i<7;++i){
      if(i==1||i==2)continue;
      if(current.goal[i]!=reference_goals[i]||
         std::abs(int(current.position[i])-int(reference_positions[i]))>2)
        return false;
    }
    const int progress12=int(reference_goals[1])-int(current.goal[1]);
    const int progress13=int(current.goal[2])-int(reference_goals[2]);
    if(progress12<0||progress12>total_counts-step_counts||
       progress13!=progress12||progress12%step_counts!=0||
       std::abs(int(current.position[1])-int(current.goal[1]))>2||
       std::abs(int(current.position[2])-int(current.goal[2]))>2||
       target12!=current.goal[1]-step_counts||
       target13!=current.goal[2]+step_counts||
       target12+target13!=reference_goals[1]+reference_goals[2])return false;
    return true;
  }

  static bool endpoint(const ShoulderPreloadPose (&before)[3],
                       const ShoulderPreloadPose (&after)[3],uint64_t sent_us,
                       uint64_t now,uint16_t target12,uint16_t target13){
    if(!start(before,sent_us,target12,target13)||
       !stable(after,now,sent_us))return false;
    const auto& initial=before[2];
    for(const auto& sample:after)for(int i=0;i<7;++i){
      if(i==1||i==2){
        const int target=i==1?target12:target13;
        const int sign=i==1?-1:1;
        const int travel=sign*(int(sample.position[i])-int(initial.position[i]));
        if(sample.goal[i]!=target||travel< -1||travel>step_counts+2)return false;
      }else if(sample.goal[i]!=initial.goal[i]||
               std::abs(int(sample.position[i])-int(initial.position[i]))>2)
        return false;
    }
    const auto& final=after[2];
    // A partial but correctly directed response is evidence, not authority
    // for another step. The host separately classifies goal error.
    return int(initial.position[1])-int(final.position[1])>=2&&
           int(final.position[2])-int(initial.position[2])>=2;
  }

  // A transient sample may still be moving, but it must not leave the
  // bounded joint envelope or change any unrelated goal. Settling is judged
  // separately from a sliding three-sample window.
  static bool bounded_endpoint_sample(const ShoulderPreloadPose& initial,
                                      const ShoulderPreloadPose& sample,
                                      uint16_t target12,uint16_t target13){
    if(!ShoulderCharacterizationPolicy::valid(sample))return false;
    for(int i=0;i<7;++i){
      if((sample.feedback[i][0]|uint16_t(sample.feedback[i][1])<<8)!=sample.position[i])
        return false;
      if(i==1||i==2){
        const int target=i==1?target12:target13;
        const int sign=i==1?-1:1;
        const int travel=sign*(int(sample.position[i])-int(initial.position[i]));
        if(sample.goal[i]!=target||travel< -1||travel>step_counts+2)return false;
      }else if(sample.goal[i]!=initial.goal[i]||
               std::abs(int(sample.position[i])-int(initial.position[i]))>2||
               ShoulderCharacterizationPolicy::moving(sample,i))return false;
    }
    return true;
  }
};
}
