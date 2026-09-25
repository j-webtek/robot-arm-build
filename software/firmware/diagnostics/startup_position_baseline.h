// Separate zero-goal startup observation. Does NOT replace normal target tracking.
// Caller must hold exclusive bus ownership. No commands, torque writes or retries.
#pragma once
#include "baseline_only_scan.h"
#include "whole_arm_baseline.h"
namespace rocell_diag {
struct StartupPositionPolicy {
  JointCountWindow joints[7];
  uint16_t drift_tolerance;
  uint64_t minimum_separation_us,maximum_wait_us,maximum_pair_us,maximum_scan_us,maximum_age_us;
};
enum class StartupPositionState { New, Waiting, Observed, Fault };
class StartupPositionBaseline {
 public:
  explicit StartupPositionBaseline(const StartupPositionPolicy& policy):policy_(policy){}
  template<class Library,class Clock>
  void poll(Library& library,Clock& clock) {
    if(state_==StartupPositionState::Fault||state_==StartupPositionState::Observed)return;
    const uint64_t now=clock.now_us();
    if(now>INT64_MAX || (last_poll_ && now<last_poll_)){fail("STARTUP_CLOCK_INVALID");return;}
    last_poll_=now;
    if(state_==StartupPositionState::New){
      if(!valid_policy()){fail("STARTUP_POLICY_INVALID");return;}
      if(!capture(0,library,clock))return;
      first_finished_=scans_[0].pair(6)->feedback.finished_us;
      state_=StartupPositionState::Waiting;return;
    }
    if(now<first_finished_){fail("STARTUP_CLOCK_INVALID");return;}
    if(now-first_finished_>policy_.maximum_wait_us){fail("STARTUP_WAIT_EXPIRED");return;}
    if(now-first_finished_<policy_.minimum_separation_us)return;
    if(!capture(1,library,clock))return;
    for(size_t i=0;i<7;++i){
      const unsigned a=position(0,i),b=position(1,i);
      if((a>b?a-b:b-a)>policy_.drift_tolerance){fail("STARTUP_POSITION_DRIFT");return;}
    }
    state_=StartupPositionState::Observed;reason_="STARTUP_STABLE_ZERO_GOALS";
  }
  bool fresh(uint64_t now) {
    if(state_!=StartupPositionState::Observed)return false;
    const uint64_t oldest=scans_[1].pair(0)->target.started_us;
    const uint64_t finished=scans_[1].pair(6)->feedback.finished_us;
    if(now<finished || now<last_fresh_ || now>INT64_MAX || now-oldest>policy_.maximum_age_us){
      fail("STARTUP_OBSERVATION_STALE");return false;
    }
    last_fresh_=now;return true;
  }
  StartupPositionState state()const{return state_;}
  const char* reason()const{return reason_;}
  const BaselineOnlyScan* scan(size_t index)const{return index<captured_?&scans_[index]:nullptr;}
  // One-shot target binding only, not write authorization. Control-state evidence,
  // command identity, conversion and the write-boundary guard remain mandatory.
  bool bind_elbow_target(uint16_t target,uint16_t maximum_delta,uint64_t now){
    if(bound_attempted_)return false;bound_attempted_=true;
    if(!fresh(now))return false;
    const auto& bounds=policy_.joints[3];
    if(!maximum_delta||maximum_delta>64||target<1024||target>3071||
       target<bounds.minimum||target>bounds.maximum){fail("STARTUP_TARGET_OUTSIDE_BOUNDS");return false;}
    const unsigned current=position(1,3);
    if((current>target?current-target:target-current)>maximum_delta){fail("STARTUP_DELTA_EXCEEDED");return false;}
    bound_target_=target;return true;
  }
  uint16_t bound_target()const{return bound_target_;}
 private:
  bool valid_policy()const{
    if(policy_.drift_tolerance>16 || !policy_.minimum_separation_us ||
       policy_.minimum_separation_us>policy_.maximum_wait_us || policy_.maximum_wait_us>5000000 ||
       !policy_.maximum_pair_us || policy_.maximum_pair_us>1000000 ||
       !policy_.maximum_scan_us || policy_.maximum_scan_us>7000000 ||
       !policy_.maximum_age_us || policy_.maximum_age_us>1000000)return false;
    for(const auto& joint:policy_.joints)if(joint.minimum>joint.maximum||joint.maximum>4095)return false;
    return true;
  }
  template<class Library,class Clock>
  bool capture(size_t index,Library& library,Clock& clock){
    captured_=index+1;
    if(!scans_[index].run(library,clock,policy_.maximum_pair_us,policy_.maximum_scan_us)){
      fail("STARTUP_READ_INVALID");return false;
    }
    for(size_t i=0;i<7;++i){
      const auto* pair=scans_[index].pair(i);const auto& bounds=policy_.joints[i];
      if(pair->target.bytes[0]||pair->target.bytes[1]){fail("STARTUP_GOAL_NOT_ZERO");return false;}
      if(position(index,i)<bounds.minimum||position(index,i)>bounds.maximum){fail("STARTUP_OUTSIDE_WINDOW");return false;}
      if(pair->feedback.bytes[10]){fail("STARTUP_MOVING");return false;}
    }
    return true;
  }
  unsigned position(size_t sample,size_t index)const{
    const auto* pair=scans_[sample].pair(index);
    return pair->feedback.bytes[0]|(static_cast<unsigned>(pair->feedback.bytes[1])<<8);
  }
  void fail(const char* reason){state_=StartupPositionState::Fault;reason_=reason;}
  StartupPositionPolicy policy_;BaselineOnlyScan scans_[2];size_t captured_=0;
  StartupPositionState state_=StartupPositionState::New;
  const char* reason_="NOT_STARTED";
  uint64_t first_finished_=0,last_poll_=0,last_fresh_=0;
  bool bound_attempted_=false;uint16_t bound_target_=0;
};
}
