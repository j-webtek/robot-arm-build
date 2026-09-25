// Exact measured T1 -> P1 elbow-relief policy. Encoder-domain checks complement, but do not
// replace, the reviewed swept-geometry plan in LARGE_POSE_LADDER_PLAN.md.
#pragma once
#include "shoulder_characterization_policy.h"
#include <cstdlib>
namespace rocell_diag {
struct LargePoseReliefPolicy {
  static constexpr uint16_t source_goals[7]={2047,2348,1766,2907,1654,2040,2047};
  static constexpr uint16_t source_positions[7]={2047,2357,1759,2904,1652,2041,2047};
  static constexpr uint16_t target_goals[7]={2047,2348,1766,2842,1719,2040,2047};
  static constexpr int selected[2]={3,4};

  static bool is_selected(int joint){return joint==3||joint==4;}
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
  static bool source(const ShoulderPreloadPose (&samples)[3],uint64_t now){
    if(!stable(samples,now))return false;
    const auto& current=samples[2];
    for(int i=0;i<7;++i)
      if(current.goal[i]!=source_goals[i]||
         std::abs(int(current.position[i])-int(source_positions[i]))>3)return false;
    return true;
  }
  static bool unchanged_source(const ShoulderPreloadPose& current,
                               const ShoulderPreloadPose& baseline){
    for(int i=0;i<7;++i)
      if(current.goal[i]!=baseline.goal[i]||current.torque[i]!=baseline.torque[i]||
         ShoulderCharacterizationPolicy::moving(current,i)||
         std::abs(int(current.position[i])-int(baseline.position[i]))>1||
         (current.feedback[i][0]|uint16_t(current.feedback[i][1])<<8)!=
           current.position[i])return false;
    return true;
  }
  static bool bounded_endpoint_sample(const ShoulderPreloadPose& initial,
                                      const ShoulderPreloadPose& sample){
    if(!ShoulderCharacterizationPolicy::valid(sample))return false;
    for(int i=0;i<7;++i){
      if((sample.feedback[i][0]|uint16_t(sample.feedback[i][1])<<8)!=sample.position[i])
        return false;
      if(is_selected(i)){
        const int command=int(target_goals[i])-int(initial.goal[i]);
        const int travel=int(sample.position[i])-int(initial.position[i]);
        if(sample.goal[i]!=target_goals[i]||travel*(command>0?1:-1)<-1||
           std::abs(travel)>80)return false;
      }else if(sample.goal[i]!=initial.goal[i]||
               std::abs(int(sample.position[i])-int(initial.position[i]))>2||
               ShoulderCharacterizationPolicy::moving(sample,i))return false;
    }
    return true;
  }
  static bool endpoint(const ShoulderPreloadPose (&before)[3],
                       const ShoulderPreloadPose (&after)[3],uint64_t sent_us,
                       uint64_t now){
    if(!source(before,sent_us)||!stable(after,now,sent_us))return false;
    for(const auto& sample:after)
      if(!bounded_endpoint_sample(before[2],sample))return false;
    const auto& final=after[2];
    for(int i=0;i<7;++i)if(is_selected(i)){
      const int command=int(target_goals[i])-int(before[2].goal[i]);
      const int travel=int(final.position[i])-int(before[2].position[i]);
      if(travel*(command>0?1:-1)<2||
         std::abs(int(final.position[i])-int(target_goals[i]))>12)return false;
    }
    return true;
  }
};
}

