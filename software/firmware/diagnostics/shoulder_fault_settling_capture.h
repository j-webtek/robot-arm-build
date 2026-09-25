// Offline candidate: not wired to a board route or installed firmware.
// Owns observations only; it cannot resume or clear the parent motion fault.
#pragma once
#include "shoulder_preload_candidate.h"
namespace rocell_diag {
enum class SettlingState { Idle, Reading, WaitingExport, Settled, Exhausted, Failed };
class ShoulderFaultSettlingCapture {
 public:
  // The caller must first preserve/export the original failure and retain its
  // boot/command identity. This separate sequence never overwrites that record.
  bool begin(uint64_t now,bool fault_latched,bool original_exported){
    if(state_!=SettlingState::Idle)return false;
    if(!now||!fault_latched||!original_exported){fail("FAULT_EVIDENCE_REQUIRED");return false;}
    began_=last_clock_=now;state_=SettlingState::Reading;return true;
  }
  template<class Bus,class Clock,class Admission>
  void advance(Bus& bus,Clock& clock,Admission& admitted){
    if(state_!=SettlingState::Reading&&state_!=SettlingState::WaitingExport)return;
    const auto now=clock.now_us();
    if(now<last_clock_||now-began_>8000000){fail("CAPTURE_DEADLINE");return;}
    last_clock_=now;
    if(bus.End!=0||!admitted()){fail("CAPTURE_ADMISSION_LOST");return;}
    if(state_==SettlingState::WaitingExport)return; // No reads before durable export.
    if(count_&&now-last_finished_<500000)return;
    ShoulderPreloadPose pose;
    if(!ShoulderPreloadCandidate::sample(bus,clock,pose,admitted)){
      fail("CAPTURE_FEEDBACK_INVALID");return;
    }
    if(pose.started_us<last_clock_||pose.finished_us<pose.started_us||
       pose.finished_us-began_>8000000){fail("CAPTURE_SCAN_TIMING");return;}
    last_clock_=last_finished_=pose.finished_us;
    bool still=true,unchanged=true;
    for(int i=0;i<7;++i){
      if(pose.feedback[i][2]||pose.feedback[i][3]||pose.feedback[i][10])still=false;
      if(count_&&(pose.goal[i]!=reference_.goal[i]||pose.torque[i]!=reference_.torque[i]))unchanged=false;
    }
    // Preserve a valid but surprising scan for failure export too.
    retained_=pose;++count_;
    if(!unchanged){fail("CAPTURE_TARGET_OR_TORQUE_CHANGED");return;}
    bool close=stable_count_>0;
    for(int i=0;i<7;++i)if(std::abs(int(pose.position[i])-int(anchor_.position[i]))>1)close=false;
    if(!still)stable_count_=0;
    else if(close)++stable_count_;
    else {anchor_=pose;stable_count_=1;}
    if(count_==1)reference_=pose;
    state_=SettlingState::WaitingExport;
  }
  // Only the authenticated host/export adapter may call this after validating
  // an identity-bound receipt. A duplicate/wrong receipt terminates observation.
  bool exported(unsigned sequence,bool verified,uint64_t now){
    if(now<last_clock_||now-began_>8000000){fail("CAPTURE_DEADLINE");return false;}
    last_clock_=now;
    if(state_!=SettlingState::WaitingExport||sequence!=count_-1||!verified){
      fail("CAPTURE_EXPORT_FAILED");return false;
    }
    if(stable_count_>=3&&last_finished_-began_>=2000000){
      state_=SettlingState::Settled;reason_="STABLE_SAMPLED_POSE";
    }else if(count_>=12){state_=SettlingState::Exhausted;reason_="SAMPLE_LIMIT";}
    else state_=SettlingState::Reading;
    return true;
  }
  SettlingState state()const{return state_;}
  const char* reason()const{return reason_;}
  unsigned count()const{return count_;}
  const ShoulderPreloadPose& record()const{return retained_;}
 private:
  void fail(const char* why){state_=SettlingState::Failed;reason_=why;}
  SettlingState state_=SettlingState::Idle;
  const char* reason_="NOT_COMPLETE";
  uint64_t began_=0,last_clock_=0,last_finished_=0;
  unsigned count_=0,stable_count_=0;
  ShoulderPreloadPose retained_,reference_,anchor_;
};
}
