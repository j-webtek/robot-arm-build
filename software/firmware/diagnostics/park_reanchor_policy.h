// Offline return-from-offset predicates. This header has no route or bus write.
// A later one-use owner must recheck start against fresh prewrite feedback.
#pragma once
#include "park_step_policy.h"

namespace rocell_diag {
struct ParkReanchorPolicy {
  static constexpr uint16_t source_goals[7]={2047,2377,1737,2907,1589,2040,2047};
  static constexpr uint16_t source_positions[7]={2047,2385,1730,2904,1591,2041,2047};
  static constexpr uint16_t target12=2389,target13=1725;
  static constexpr uint16_t expected12=2390,expected13=1724;
  static constexpr int maximum_travel=8;

  static bool start(const ShoulderPreloadPose (&before)[3],uint64_t now){
    if(!ParkStepPolicy::stable(before,now))return false;
    const auto& last=before[2];
    for(int i=0;i<7;++i){
      const int tolerance=i==1||i==2?1:2;
      if(last.goal[i]!=source_goals[i]||last.torque[i]!=1||
         std::abs(int(last.position[i])-int(source_positions[i]))>tolerance)
        return false;
    }
    return true;
  }

  static bool bounded_sample(const ShoulderPreloadPose& initial,
                             const ShoulderPreloadPose& sample){
    if(!ShoulderCharacterizationPolicy::valid(sample))return false;
    for(int i=0;i<7;++i){
      if((sample.feedback[i][0]|uint16_t(sample.feedback[i][1])<<8)!=
         sample.position[i]||sample.torque[i]!=initial.torque[i])return false;
      if(i==1||i==2){
        const int travel=(i==1?1:-1)*
            (int(sample.position[i])-int(initial.position[i]));
        if(sample.goal[i]!=(i==1?target12:target13)||
           travel< -1||travel>maximum_travel)return false;
      }else if(sample.goal[i]!=initial.goal[i]||
               std::abs(int(sample.position[i])-int(initial.position[i]))>2||
               ShoulderCharacterizationPolicy::moving(sample,i))return false;
    }
    return true;
  }

  static bool endpoint(const ShoulderPreloadPose (&before)[3],
                       const ShoulderPreloadPose (&after)[3],
                       uint64_t sent_us,uint64_t now){
    if(!start(before,sent_us)||!ParkStepPolicy::stable(after,now,sent_us))
      return false;
    for(const auto& sample:after)
      if(!bounded_sample(before[2],sample))return false;
    const auto& last=after[2];
    return std::abs(int(last.position[1])-2390)<=2&&
           std::abs(int(last.position[2])-1724)<=2&&
           std::abs(int(last.position[1])-target12)<=2&&
           std::abs(int(last.position[2])-target13)<=2;
  }
};
}
