// Offline candidate only: no route, startup, enable, disable or retry.
// Evidence callback must persist before returning; never wired to live firmware.
#pragma once
#include "shoulder_preload_candidate.h"
namespace rocell_diag {
class MixedShoulderCandidate {
 public:
  template<class Bus,class Clock,class Evidence,class Admission>
  bool run(Bus& bus,Clock& clock,Evidence& evidence,Admission& admitted){
    if(used_)return false;used_=true;
    ShoulderPreloadPose initial,current;
    if(bus.End!=0||!admitted()){reason_="NOT_ADMITTED";return false;}
    auto sample=[&](ShoulderPreloadPose& pose){return ShoulderPreloadCandidate::sample(bus,clock,pose,admitted);};
    auto emit=[&](const char* event,const ShoulderPreloadPose& pose,int sid,int result){
      if(!evidence(event,pose,sid,result)){reason_="EXPORT_FAILED";return false;}return true;
    };
    auto fail=[&](const char* reason){
      reason_=reason;if(!evidence("STATE_MISMATCH",current,0,0))reason_="EXPORT_FAILED";return false;
    };
    if(!sample(initial)){reason_="BASELINE_INVALID";return false;}
    current=initial;
    if(!emit("BASELINE",initial,0,0))return false;
    if(initial.torque[1]+initial.torque[2]!=1)return fail("NOT_MIXED");
    for(int i=0;i<7;++i)if(moving(initial,i)||
        (initial.torque[i]&&std::abs(int(initial.position[i])-int(initial.goal[i]))>2))
      return fail("BASELINE_NOT_TRACKING");
    const int index=initial.torque[1]?2:1;
    if(!sample(current)){reason_="FEEDBACK_INVALID";return false;}
    if(!same(initial,current,-1,0))return fail("PRE_INTENT_STATE_CHANGED");
    const auto before=current;const uint16_t target=current.position[index];
    current.requested_target=target;
    if(!emit("PRELOAD_INTENT",current,index+11,0))return false;
    // Re-read after export. Do not silently change the exported target.
    if(!sample(current)){reason_="FEEDBACK_INVALID";return false;}
    if(!same(before,current,-1,0)||current.position[index]!=target)
      return fail("PREWRITE_STATE_CHANGED");
    if(!admitted()){reason_="ADMISSION_LOST";return false;}
    current.requested_target=target;current.action_started_us=clock.now_us();
    ++writes_;const int result=bus.WritePosEx(index+11,target,20,1);
    current.action_device_error=bus.Error;current.action_finished_us=clock.now_us();
    const uint64_t sent=current.action_finished_us;
    if(!emit("PRELOAD_RESULT",current,index+11,result))return false;
    if(result!=1||current.action_device_error){reason_="DELIVERY_UNCERTAIN";return false;}
    int observed_torque=-1;
    for(int n=0;n<3;++n){
      if(!sample(current)){reason_="FEEDBACK_INVALID";return false;}
      if(current.started_us<=sent||current.finished_us-sent>2000000)
        return fail("POSTWRITE_DEADLINE");
      if(!same(before,current,index,target))return fail("POSTWRITE_STATE_CHANGED");
      if(observed_torque!=-1&&current.torque[index]!=observed_torque)return fail("TORQUE_UNSTABLE");
      observed_torque=current.torque[index];
      if(!emit("PRELOAD_VERIFIED",current,index+11,1))return false;
    }
    reason_=observed_torque?"TARGET_OBSERVED_ENABLED":"TARGET_OBSERVED_PASSIVE";
    return true;
  }
  const char* reason()const{return reason_;}
  unsigned writes()const{return writes_;}
 private:
  static bool moving(const ShoulderPreloadPose& p,int i){
    return p.feedback[i][2]||p.feedback[i][3]||p.feedback[i][10];
  }
  static bool same(const ShoulderPreloadPose& a,const ShoulderPreloadPose& b,int selected,uint16_t target){
    for(int i=0;i<7;++i){
      if(moving(b,i)||std::abs(int(a.position[i])-int(b.position[i]))>2)return false;
      if(i==selected){if(b.goal[i]!=target)return false;}
      else if(a.goal[i]!=b.goal[i]||a.torque[i]!=b.torque[i])return false;
      if(i!=selected&&b.torque[i]&&std::abs(int(b.position[i])-int(b.goal[i]))>2)return false;
    }
    return true;
  }
  bool used_=false;unsigned writes_=0;const char* reason_="NOT_STARTED";
};
}
