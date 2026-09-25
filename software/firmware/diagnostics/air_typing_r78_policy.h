// Four fixed noncontact A-side legs from the post-r77 stable measured pose.
// Installed as air_typing_policy.h only in a separate reviewed r78 candidate.
#pragma once
#include "shoulder_characterization_policy.h"
#include "air_typing_r76_endpoint_rule.h"
#include "air_typing_r78_source_rule.h"
#include <cstdlib>
namespace rocell_diag {
struct AirTypingPolicy {
  static constexpr unsigned legs=4;
  static constexpr uint16_t targets[legs][7]={
    {2047,2075,2039,2600,2233,2040,2047},
    {2047,2093,2021,2618,2197,2040,2047},
    {2047,2105,2009,2630,2173,2040,2047},
    {2047,2075,2039,2600,2233,2040,2047}
  };
  uint16_t source_goals[7]={1994,2076,2038,2598,2234,2040,2047};
  uint16_t source_positions[7]={1987,2082,2031,2600,2235,2041,2047};
  uint16_t target_goals[7]={2047,2075,2039,2600,2233,2040,2047};
  void advance(const ShoulderPreloadPose& final,unsigned next){
    for(int i=0;i<7;++i){source_goals[i]=final.goal[i];source_positions[i]=final.position[i];
      target_goals[i]=targets[next][i];}
  }
  bool selected(int i)const{return target_goals[i]!=source_goals[i];}
  bool stable(const ShoulderPreloadPose (&samples)[3],uint64_t now,uint64_t after_us=0)const{
    if(!now||samples[0].started_us<=after_us||samples[2].finished_us>now||
       now-samples[2].finished_us>1000000||
       samples[2].finished_us-samples[0].started_us<200000||
       samples[2].finished_us-samples[0].started_us>1500000)return false;
    for(int n=0;n<3;++n){
      const auto& s=samples[n];
      if(!ShoulderCharacterizationPolicy::valid(s))return false;
      if(n&&(s.started_us<=samples[n-1].finished_us||
             s.started_us-samples[n-1].finished_us<100000))return false;
      for(int i=0;i<7;++i){
        if(ShoulderCharacterizationPolicy::moving(s,i)||s.goal[i]!=samples[0].goal[i]||
           std::abs(int(s.position[i])-int(samples[0].position[i]))>1||
           (s.feedback[i][0]|uint16_t(s.feedback[i][1])<<8)!=s.position[i])return false;
      }
    }
    return true;
  }
  bool source(const ShoulderPreloadPose (&samples)[3],uint64_t now)const{
    if(!stable(samples,now))return false;
    for(int i=0;i<7;++i)if(!air_typing_r78_source_joint_verified(
        source_positions[i],source_goals[i],samples[2].position[i],samples[2].goal[i]))return false;
    return true;
  }
  bool unchanged_source(const ShoulderPreloadPose& current,const ShoulderPreloadPose& prior)const{
    for(int i=0;i<7;++i)if(current.goal[i]!=prior.goal[i]||current.torque[i]!=prior.torque[i]||
       ShoulderCharacterizationPolicy::moving(current,i)||
       std::abs(int(current.position[i])-int(prior.position[i]))>1||
       (current.feedback[i][0]|uint16_t(current.feedback[i][1])<<8)!=current.position[i])return false;
    return true;
  }
  bool bounded_endpoint_sample(const ShoulderPreloadPose& initial,
                               const ShoulderPreloadPose& sample)const{
    if(!ShoulderCharacterizationPolicy::valid(sample))return false;
    for(int i=0;i<7;++i){
      if((sample.feedback[i][0]|uint16_t(sample.feedback[i][1])<<8)!=sample.position[i]||
         sample.goal[i]!=target_goals[i])return false;
      const int travel=int(sample.position[i])-int(initial.position[i]);
      if(selected(i)){
        const int command=int(target_goals[i])-int(initial.goal[i]);
        if(!command||std::abs(command)>80||travel*(command>0?1:-1)<-1||
           std::abs(travel)>92)return false;
      }else if(std::abs(travel)>2||ShoulderCharacterizationPolicy::moving(sample,i))return false;
    }
    return true;
  }
  bool endpoint(const ShoulderPreloadPose (&before)[3],
                const ShoulderPreloadPose (&after)[3],uint64_t sent_us,uint64_t now)const{
    if(!source(before,sent_us)||!stable(after,now,sent_us))return false;
    for(const auto& s:after)if(!bounded_endpoint_sample(before[2],s))return false;
    for(int i=0;i<7;++i)if(selected(i)&&
       !air_typing_r76_endpoint_joint_verified(before[2].goal[i],before[2].position[i],
                                               target_goals[i],after[2].position[i]))return false;
    return true;
  }
};
}
