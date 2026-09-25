// Offline policy only. No bus, dispatcher, signed admission or live route.
#pragma once
#include "shoulder_preload_candidate.h"
#include <cstddef>
namespace rocell_diag {
enum class CharacterizationOutcome { Stop, SettledAccurate, SettledMiss, SettledSmall };
struct CharacterizationResult {
  CharacterizationOutcome outcome=CharacterizationOutcome::Stop;
  const char* reason="INVALID_OR_UNSAFE_EVIDENCE";
  int actual_delta[2]={},goal_delta[2]={},endpoint_error[2]={};
  bool continuation_eligible()const{return outcome!=CharacterizationOutcome::Stop;}
};
struct ShoulderCharacterizationPolicy {
  static bool moving(const ShoulderPreloadPose& p,int i){
    return p.feedback[i][2]||p.feedback[i][3]||p.feedback[i][10];
  }
  static bool valid(const ShoulderPreloadPose& p){
    if(!p.started_us||p.finished_us<p.started_us||p.finished_us-p.started_us>300000)return false;
    for(int i=0;i<7;++i)if(p.position[i]>4095||p.goal[i]>4095||p.torque[i]!=1)return false;
    return true;
  }
  static CharacterizationResult assess(const ShoulderPreloadPose& before,const uint16_t (&goals)[2],
      const ShoulderPreloadPose* samples,size_t count,const uint16_t (&bounds)[7][2],
      bool delivery_confirmed,bool export_verified){
    CharacterizationResult result;
    if(!delivery_confirmed){result.reason="DELIVERY_UNCERTAIN";return result;}
    if(!export_verified){result.reason="EXPORT_UNVERIFIED";return result;}
    if(!samples||count<3||count>64||!valid(before)||goals[0]>4095||goals[1]>4095||
       int(goals[0])+goals[1]!=4114||int(before.goal[1])+before.goal[2]!=4114)return result;
    for(int i=0;i<7;++i){
      if(moving(before,i)||bounds[i][0]>bounds[i][1]||bounds[i][1]>4095||
         before.position[i]<bounds[i][0]||before.position[i]>bounds[i][1])return result;
    }
    for(int i=0;i<2;++i){
      if(goals[i]<bounds[i+1][0]||goals[i]>bounds[i+1][1]||std::abs(int(goals[i])-int(before.position[i+1]))>32)return result;
      result.goal_delta[i]=int(goals[i])-int(before.goal[i+1]);
    }
    if(!result.goal_delta[0]||result.goal_delta[0]!=-result.goal_delta[1]||std::abs(result.goal_delta[0])>24)return result;
    uint64_t last=before.finished_us;
    for(size_t n=0;n<count;++n){
      const auto& p=samples[n];
      if(!valid(p)||p.started_us<=last||p.started_us-last>1000000||
         p.finished_us-before.finished_us>8000000)return result;
      last=p.finished_us;
      for(int i=0;i<7;++i){
        bool selected=i==1||i==2;
        int expected=selected?goals[i-1]:before.goal[i];
        if(p.goal[i]!=expected||p.position[i]<bounds[i][0]||p.position[i]>bounds[i][1])return result;
        int delta=int(p.position[i])-int(before.position[i]);
        if(selected){if(std::abs(delta)>32||delta*(result.goal_delta[i-1]>0?1:-1)<-1)return result;}
        else if(std::abs(delta)>2||moving(p,i))return result;
      }
    }
    const auto& anchor=samples[count-3];const auto& final=samples[count-1];
    result.reason="NOT_SETTLED";
    if(final.finished_us-anchor.finished_us<200000)return result;
    for(size_t n=count-3;n<count;++n)for(int i=0;i<7;++i)
      if(moving(samples[n],i)||std::abs(int(samples[n].position[i])-int(anchor.position[i]))>1)return result;
    for(int i=0;i<2;++i){
      result.actual_delta[i]=int(final.position[i+1])-int(before.position[i+1]);
      result.endpoint_error[i]=int(final.position[i+1])-int(goals[i]);
    }
    result.reason="NO_CLEAR_RESPONSE";
    if(std::abs(result.actual_delta[0])<2||std::abs(result.actual_delta[1])<2)return result;
    result.reason="RESIDUAL_ENVELOPE_EXCEEDED";
    if(std::abs(result.endpoint_error[0])>12||std::abs(result.endpoint_error[1])>12)return result;
    result.reason="MEASUREMENT_RETAINED";
    result.outcome=(std::abs(result.endpoint_error[0])<=2&&std::abs(result.endpoint_error[1])<=2)?
      CharacterizationOutcome::SettledAccurate:CharacterizationOutcome::SettledMiss;
    return result;
  }
};
}
