// Uninstalled native candidate. No route, enable, reset or retry operation.
// The caller owns admission, bus exclusion and durable per-event export.
#pragma once
#include <cstdint>
#include <cstdlib>
namespace rocell_diag {
struct ShoulderPreloadPose {
  uint16_t position[7]={},goal[7]={};uint8_t torque[7]={};
  // Raw reference bytes: no unverified conversion to torque/current units.
  uint8_t feedback[7][15]={};
  uint64_t started_us=0,finished_us=0;
  uint16_t requested_target=0;
  uint16_t requested_pair[2]={};
  uint64_t action_started_us=0,action_finished_us=0;
  int action_device_error=0;
};
class ShoulderPreloadCandidate {
  friend class ShoulderHoldCandidate;
  friend class MixedShoulderCandidate;
  friend class ShoulderFaultSettlingCapture;
  template<class Digest,class Verifier> friend class ShoulderPreloadSession;
  template<class Crypto> friend class LocalShoulderStepSession;
  template<class Crypto> friend class CompensatedShoulderStepSession;
  friend class ShoulderCharacterizationOwner;
  friend class CharacterizationCapture;
  friend struct FixedPairReanchorAcquisition;
 public:
  // evidence(event, pose, servo_id, result) must persist before returning true.
  // Failure after a write leaves that partial state intact; never auto-undo.
  template<class Bus,class Clock,class Evidence,class Admission>
  bool run(Bus& bus,Clock& clock,Evidence& evidence,Admission& admitted){
    if(used_)return false;
    used_=true;
    if(bus.End!=0||!admitted()){reason_="NOT_ADMITTED";return false;}
    ShoulderPreloadPose initial,current;
    if(!sample(bus,clock,initial,admitted)){reason_="BASELINE_INVALID";return false;}
    if(initial.torque[1]||initial.torque[2]){reason_="SHOULDERS_NOT_PASSIVE";return false;}
    for(int i=0;i<7;++i){
      if(initial.torque[i]&&std::abs(int(initial.position[i])-int(initial.goal[i]))>2){
        reason_="ENABLED_JOINT_NOT_TRACKING";return false;
      }
    }
    if(!evidence("BASELINE",initial,0,0)){reason_="EXPORT_FAILED";return false;}
    for(int index=1;index<=2;++index){
      if(!sample(bus,clock,current,admitted)||!consistent(initial,current,index-1)){
        reason_="PREWRITE_STATE_CHANGED";return false;
      }
      current.requested_target=initial.position[index];
      if(!evidence("PRELOAD_INTENT",current,index+11,0)||!admitted()){
        reason_="INTENT_OR_ADMISSION_FAILED";return false;
      }
      // Export may be slow. Reacquire immediately before transmission.
      if(!sample(bus,clock,current,admitted)||!consistent(initial,current,index-1)){
        reason_="POST_EXPORT_STATE_CHANGED";return false;
      }
      ++writes_;
      current.requested_target=initial.position[index];
      current.action_started_us=clock.now_us();
      const int result=bus.WritePosEx(index+11,initial.position[index],20,1);
      const int error=bus.Error;
      current.action_finished_us=clock.now_us();current.action_device_error=error;
      if(!evidence("PRELOAD_RESULT",current,index+11,result)){
        reason_="EXPORT_FAILED";return false;
      }
      if(result!=1||error!=0){reason_="PRELOAD_DELIVERY_UNCERTAIN";return false;}
      if(!sample(bus,clock,current,admitted)||!consistent(initial,current,index)){
        reason_="READBACK_MISMATCH";return false;
      }
      if(!evidence("PRELOAD_VERIFIED",current,index+11,result)){
        reason_="EXPORT_FAILED";return false;
      }
    }
    baseline_=initial;reason_="PASSIVE_TARGETS_PRELOADED";return true;
  }
  const char* reason()const{return reason_;}
  unsigned writes()const{return writes_;}
 private:
  ShoulderPreloadPose baseline_;
  bool used_=false;unsigned writes_=0;const char* reason_="NOT_STARTED";
  static bool consistent(const ShoulderPreloadPose& first,const ShoulderPreloadPose& now,int completed){
    for(int i=0;i<7;++i){
      const auto goal=(i>=1&&i<=completed)?first.position[i]:first.goal[i];
      if(std::abs(int(now.position[i])-int(first.position[i]))>2||
         now.torque[i]!=first.torque[i]||now.goal[i]!=goal)return false;
    }
    return true;
  }
  template<class Bus,class Clock,class Admission>
  static bool sample(Bus& bus,Clock& clock,ShoulderPreloadPose& pose,Admission& admitted){
    const auto begin=clock.now_us();if(!begin)return false;
    pose.started_us=begin;
    uint64_t previous=begin;
    for(int i=0;i<7;++i){
      uint8_t mode=0,torque=0,goal[2]={};auto* position=pose.feedback[i];
      uint8_t* bytes[]={&mode,&torque,goal,position};
      const uint8_t address[]={33,40,42,56},width[]={1,1,2,15};
      for(int field=0;field<4;++field){
        if(!admitted())return false;
        const auto start=clock.now_us();
        if(start<previous||start-begin>300000)return false;
        const int count=bus.Read(i+11,address[field],bytes[field],width[field]);
        const auto end=clock.now_us();
        if(count!=width[field]||bus.Error||end<start||end-start>50000||end-begin>300000)return false;
        previous=end;
      }
      pose.position[i]=position[0]|(uint16_t(position[1])<<8);
      pose.goal[i]=goal[0]|(uint16_t(goal[1])<<8);pose.torque[i]=torque;
      if(mode!=0||torque>1||pose.position[i]>4095||pose.goal[i]>4095)return false;
    }
    pose.finished_us=previous;return admitted();
  }
};
}
