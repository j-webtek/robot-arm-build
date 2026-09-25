// Native read-only building block for staged hold initialization, not deployed.
// The outer owner must exclude every other bus user across the entire capture.
// Unlike movement admission, capture preserves torque=0 and nonzero goals.
#pragma once
#include "baseline_only_scan.h"
#include "servo_control_state_read.h"

namespace rocell_diag {
struct HoldJointState {
  uint16_t position=0,goal=0;
  uint8_t mode=0,torque=0,moving=0;
};
class HoldStateSnapshot {
 public:
  template<class Library,class Clock>
  bool capture(Library& library,Clock& clock,uint64_t maximum_pair_us,
               uint64_t maximum_scan_us) {
    if(used_)return false;
    used_=true;
    if(!maximum_scan_us||maximum_scan_us>1000000){reason_="INVALID_HOLD_SCAN_LIMIT";return false;}
    if(!positions_.run(library,clock,maximum_pair_us,maximum_scan_us)){
      reason_=positions_.reason();return false;
    }
    if(!controls_.acquire(library,clock)){reason_=controls_.reason();return false;}
    started_=positions_.pair(0)->target.started_us;
    finished_=controls_.read(13)->finished_us;
    // The control scan is called synchronously after the position scan.
    if(controls_.read(0)->started_us<positions_.pair(6)->feedback.finished_us||
       finished_<started_||finished_-started_>maximum_scan_us){
      reason_="HOLD_SCAN_TIMING_INVALID";return false;
    }
    for(size_t i=0;i<7;++i){
      const auto* p=positions_.pair(i);
      auto& j=joints_[i];
      j.goal=p->target.bytes[0]|(uint16_t(p->target.bytes[1])<<8);
      j.position=p->feedback.bytes[0]|(uint16_t(p->feedback.bytes[1])<<8);
      j.moving=p->feedback.bytes[10];
      j.mode=controls_.read(2*i)->bytes[0];
      j.torque=controls_.read(2*i+1)->bytes[0];
      if(j.position>4095||j.goal>4095||j.moving>1||j.torque>1){
        reason_="HOLD_REGISTER_RANGE_INVALID";return false;
      }
    }
    complete_=true;reason_="HOLD_STATE_CAPTURED";return true;
  }
  bool fresh(uint64_t now,uint64_t maximum_age_us){
    if(!complete_||faulted_)return false;
    if(!maximum_age_us||maximum_age_us>1000000||now>INT64_MAX||
       now<finished_||now<last_check_||now-started_>maximum_age_us){
      faulted_=true;reason_="HOLD_STATE_STALE";return false;
    }
    last_check_=now;return true;
  }
  const HoldJointState* joint(size_t i)const{return complete_&&i<7?&joints_[i]:nullptr;}
  const BaselineOnlyScan& positions()const{return positions_;}
  const ServoControlStateRead& controls()const{return controls_;}
  uint64_t started_us()const{return started_;}
  uint64_t finished_us()const{return finished_;}
  const char* reason()const{return reason_;}
  bool complete()const{return complete_;}
 private:
  BaselineOnlyScan positions_;
  ServoControlStateRead controls_;
  HoldJointState joints_[7];
  uint64_t started_=0,finished_=0,last_check_=0;
  bool used_=false,complete_=false,faulted_=false;
  const char* reason_="NOT_STARTED";
};
}
