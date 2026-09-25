// Fixed P4-relative, noncontact A-B-A recipe. No arbitrary target input.
#pragma once
#include "shoulder_characterization_policy.h"
#include <cstdlib>
namespace rocell_diag {
struct AirTypingPolicy {
  static constexpr unsigned legs=17;
  static constexpr uint16_t targets[legs][7]={
    {2047,2176,1938,2686,2046,2040,2047},
    {2047,2139,1975,2658,2110,2040,2047},
    {2047,2105,2009,2630,2173,2040,2047},
    {2047,2075,2039,2600,2233,2040,2047},
    {2047,2093,2021,2618,2197,2040,2047},
    {2047,2105,2009,2630,2173,2040,2047},
    {2047,2075,2039,2600,2233,2040,2047},
    {1994,2076,2038,2598,2234,2040,2047},
    {1941,2080,2034,2591,2236,2040,2047},
    {1941,2098,2016,2609,2201,2040,2047},
    {1941,2111,2003,2621,2176,2040,2047},
    {1941,2080,2034,2591,2236,2040,2047},
    {1994,2076,2038,2598,2234,2040,2047},
    {2047,2075,2039,2600,2233,2040,2047},
    {2047,2093,2021,2618,2197,2040,2047},
    {2047,2105,2009,2630,2173,2040,2047},
    {2047,2075,2039,2600,2233,2040,2047}
  };
  uint16_t source_goals[7]={2047,2217,1897,2711,1980,2040,2047};
  uint16_t source_positions[7]={2047,2225,1890,2716,1979,2041,2047};
  uint16_t target_goals[7]={2047,2176,1938,2686,2046,2040,2047};
  unsigned source_tolerance=3;
  void advance(const ShoulderPreloadPose& final,unsigned next){
    for(int i=0;i<7;++i){source_goals[i]=final.goal[i];source_positions[i]=final.position[i];
      target_goals[i]=targets[next][i];}
    source_tolerance=1;
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
    for(int i=0;i<7;++i)if(samples[2].goal[i]!=source_goals[i]||
       std::abs(int(samples[2].position[i])-int(source_positions[i]))>int(source_tolerance))return false;
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
    for(int i=0;i<7;++i)if(selected(i)){
      const int command=int(target_goals[i])-int(before[2].goal[i]);
      const int travel=int(after[2].position[i])-int(before[2].position[i]);
      if((std::abs(command)>=4&&travel*(command>0?1:-1)<2)||
         std::abs(int(after[2].position[i])-int(target_goals[i]))>12)return false;
    }
    return true;
  }
};
}
