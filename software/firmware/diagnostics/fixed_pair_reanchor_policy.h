// Offline r54 candidate policy. This file has no bus write or HTTP route.
// The eventual one-use owner must call start() immediately before its sole
// paired write and endpoint() only on fresh post-write observations.
#pragma once
#include "shoulder_characterization_policy.h"
#include <cstdlib>
namespace rocell_diag {
struct FixedPairReanchorPolicy {
  static constexpr uint16_t source_goals[2]={2386,1728};
  static constexpr uint16_t source_positions[2]={2390,1725};
  static constexpr uint16_t target_goals[2]={2389,1725};
  static constexpr uint16_t target_positions[2]={2391,1724};

  static bool start(const ShoulderPreloadPose (&poses)[3],uint64_t now){
    if(!stable(poses,now,0))return false;
    const auto& last=poses[2];
    for(int j=0;j<2;++j){
      const int i=j+1;
      if(last.goal[i]!=source_goals[j]||
         std::abs(int(last.position[i])-int(source_positions[j]))>1)return false;
    }
    return true;
  }

  static bool endpoint(const ShoulderPreloadPose (&before)[3],
      const ShoulderPreloadPose (&after)[3],uint64_t sent_us,uint64_t now){
    if(!start(before,sent_us)||!stable(after,now,sent_us))return false;
    const auto& initial=before[2];
    for(const auto& sample:after)for(int i=0;i<7;++i){
      if(i==1||i==2){
        const int j=i-1;
        if(sample.goal[i]!=target_goals[j]||
           std::abs(int(sample.position[i])-int(initial.position[i]))>3)return false;
      }else if(sample.goal[i]!=initial.goal[i]||
               std::abs(int(sample.position[i])-int(initial.position[i]))>2)return false;
    }
    const auto& final=after[2];
    for(int j=0;j<2;++j)
      if(std::abs(int(final.position[j+1])-int(target_positions[j]))>1)return false;
    return true;
  }

 private:
  static bool stable(const ShoulderPreloadPose (&poses)[3],uint64_t now,uint64_t after_us){
    if(!now||poses[0].started_us<=after_us||poses[2].finished_us>now||
       now-poses[2].finished_us>1000000||
       poses[2].finished_us-poses[0].started_us>1500000)return false;
    for(int n=0;n<3;++n){
      const auto& pose=poses[n];
      if(!ShoulderCharacterizationPolicy::valid(pose))return false;
      if(n&&(pose.started_us<=poses[n-1].finished_us||
             pose.started_us-poses[n-1].finished_us<100000))return false;
      for(int i=0;i<7;++i){
        if(ShoulderCharacterizationPolicy::moving(pose,i)||
           pose.goal[i]!=poses[0].goal[i]||
           std::abs(int(pose.position[i])-int(poses[0].position[i]))>1||
           (pose.feedback[i][0]|uint16_t(pose.feedback[i][1])<<8)!=pose.position[i])
          return false;
      }
    }
    return poses[2].finished_us-poses[0].started_us>=200000;
  }
};
}
