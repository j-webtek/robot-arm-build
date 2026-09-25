// Single native count-space leg, offline only. No network route or reset/rearm.
// Outer integration must authenticate the frozen target, reserve evidence space,
// enforce exclusive ownership, and export before admitting a separate return leg.
#pragma once
#include "hold_initialization_owner.h"

namespace rocell_diag {
enum class HeldLegPhase { New, Baseline, Dispatch, Sampling, Arrived, NotArrived, Fault };
class HeldElbowLegOwner {
 public:
  HeldElbowLegOwner(const HoldInitializationPolicy& policy,uint16_t target,
      uint16_t tolerance,bool (*healthy)(void*),void* context=nullptr)
      :p_(policy),target_(target),tolerance_(tolerance),healthy_(healthy),context_(context){}
  // Bind a preceding verified endpoint before any acquisition. Copy only the
  // state needed across legs, not the large raw-scan history. This is continuity
  // checking, not authentication or a substitute for fresh reads on this leg.
  bool bind_start(const HoldStateSnapshot& prior){
    if(bound_||phase_!=HeldLegPhase::New||count_||!prior.complete()){
      fail("LEG_START_BINDING_INVALID");return false;
    }
    for(size_t i=0;i<7;++i){
      const auto* j=prior.joint(i);
      if(!j||j->mode!=0||j->moving||j->position>4095||j->goal>4095||j->torque>1){
        fail("LEG_START_BINDING_INVALID");return false;
      }
      expected_[i]={j->position,j->goal,j->torque};
    }
    bound_=true;return true;
  }
  template<class Bus,class Clock> void poll(Bus& bus,Clock& clock){
    if(terminal())return;
    const uint64_t now=clock.now_us();
    if(now>INT64_MAX||(last_poll_&&now<last_poll_)){fail("LEG_CLOCK_INVALID");return;}
    last_poll_=now;
    if(!healthy_||!healthy_(context_)||bus.End!=0||bus.Level!=1){fail("LEG_BOUNDARY_INVALID");return;}
    if(phase_==HeldLegPhase::New){
      if(!HoldInitializationOwner::policy_valid(p_)||tolerance_>2||
         target_<p_.minimum[3]||target_>p_.maximum[3]){fail("LEG_POLICY_INVALID");return;}
      started_=now;
      if(!capture(bus,clock,false))return;
      anchor_=last()->joint(3)->position;
      if(distance(anchor_,target_)<=2*tolerance_||distance(anchor_,target_)>16){fail("LEG_DELTA_INVALID");return;}
      phase_=HeldLegPhase::Baseline;return;
    }
    if(now<last()->finished_us()||now-last()->finished_us()>p_.maximum_gap_us){fail("LEG_OBSERVATION_GAP");return;}
    if(!written_&&now-started_>p_.deadline_us){fail("LEG_PREWRITE_DEADLINE");return;}
    if(phase_==HeldLegPhase::Baseline){
      if(now-last()->finished_us()<p_.baseline_gap_us)return;
      if(capture(bus,clock,false))phase_=HeldLegPhase::Dispatch;
      return;
    }
    if(phase_==HeldLegPhase::Dispatch){
      if(!capture(bus,clock,false))return;
      const uint64_t at=clock.now_us();
      if(!healthy_(context_)||!last()->fresh(at,p_.age_us)||at-started_>p_.deadline_us||
         bus.End!=0||bus.Level!=1){fail("LEG_WRITE_BOUNDARY_INVALID");return;}
      written_=true; // Reserve before dispatch, including lost acknowledgment.
      action_.started_us=at;action_.address=41;action_.width=7;
      action_.bytes[0]=p_.acceleration;action_.bytes[1]=target_&255;action_.bytes[2]=target_>>8;
      action_.bytes[5]=p_.speed&255;action_.bytes[6]=p_.speed>>8;
      int result=bus.WritePosEx(14,target_,p_.speed,p_.acceleration);
      action_.finished_us=clock.now_us();
      action_.ack=record_dispatch(14,result,result==1?bus.Error:-1,AckPolicy::Enabled);
      if(action_.finished_us<at||action_.finished_us>INT64_MAX||
         action_.finished_us-at>p_.age_us||action_.ack.status!=DispatchStatus::Succeeded){
        fail("LEG_DISPATCH_UNCERTAIN");return;
      }
      phase_=HeldLegPhase::Sampling;return;
    }
    if(now-last()->finished_us()<p_.settle_us)return;
    if(now<action_.finished_us||now-action_.finished_us>p_.deadline_us+p_.maximum_gap_us){
      fail("LEG_ENDPOINT_TIMING_INVALID");return;
    }
    if(!capture(bus,clock,true))return;
    const auto& j=*last()->joint(3);
    const bool in_band=distance(j.position,target_)<=tolerance_&&j.moving==0;
    const uint64_t elapsed=last()->finished_us()-action_.finished_us;
    if(in_band&&previous_in_band_&&elapsed<=p_.deadline_us){
      phase_=HeldLegPhase::Arrived;reason_="LEG_ARRIVED";return;
    }
    previous_in_band_=in_band;
    if(elapsed>=p_.deadline_us){
      if(!in_band){phase_=HeldLegPhase::NotArrived;reason_="LEG_NOT_ARRIVED";}
      else fail("LEG_SETTLING_INCOMPLETE");
    }
  }
  HeldLegPhase phase()const{return phase_;}
  const char* reason()const{return reason_;}
  bool terminal()const{return phase_==HeldLegPhase::Arrived||phase_==HeldLegPhase::NotArrived||phase_==HeldLegPhase::Fault;}
  size_t scan_count()const{return count_;}
  const HoldStateSnapshot* scan(size_t i)const{return i<count_?&scans_[i]:nullptr;}
  const HoldActionEvidence* action()const{return written_?&action_:nullptr;}
  uint16_t anchor()const{return anchor_;}
  void export_failed(){fail("LEG_EXPORT_FAILED");}
  void interference(){fail("LEG_INTERFERENCE");}
 private:
  static unsigned distance(unsigned a,unsigned b){return a>b?a-b:b-a;}
  void fail(const char* why){phase_=HeldLegPhase::Fault;reason_=why;}
  HoldStateSnapshot* last(){return count_?&scans_[count_-1]:nullptr;}
  template<class Bus,class Clock> bool capture(Bus& bus,Clock& clock,bool after){
    if(count_==32){fail("LEG_STORAGE_FULL");return false;}
    const uint64_t previous=count_?last()->finished_us():0;
    auto& s=scans_[count_++];
    if(!s.capture(bus,clock,p_.pair_us,p_.scan_us)||!s.fresh(clock.now_us(),p_.age_us)||
       s.started_us()<=previous||(after&&s.started_us()<=action_.finished_us)){
      fail("LEG_INVALID_ACQUISITION");return false;
    }
    for(size_t i=0;i<7;++i){
      const auto& j=*s.joint(i);const auto& initial=*scans_[0].joint(i);
      // A new local baseline must not silently absorb between-leg changes.
      // The elbow may move only after this leg's dispatch; neighbors never may.
      if(bound_&&(i!=3||!after)&&
         (distance(j.position,expected_[i].position)>(i==3?tolerance_:p_.drift)||
          j.goal!=expected_[i].goal||j.torque!=expected_[i].torque)){
        fail("LEG_BOUND_START_CHANGED");return false;
      }
      if(j.mode!=0||j.position<p_.minimum[i]||j.position>p_.maximum[i]){
        fail("LEG_POSE_OR_MODE_INVALID");return false;
      }
      if(i!=3){
        if(j.moving||distance(j.position,initial.position)>p_.drift||j.goal!=initial.goal||j.torque!=initial.torque){
          fail("LEG_NEIGHBOR_CHANGED");return false;
        }
      }else if(j.torque!=1||(!after&&(j.moving||distance(j.position,j.goal)>tolerance_||
               distance(j.position,initial.position)>p_.drift||j.goal!=initial.goal))||
               (after&&j.goal!=target_)){
        fail("LEG_CONTROL_OR_GOAL_MISMATCH");return false;
      }
      if(i==3&&after){
        const int low=(anchor_<target_?anchor_:target_)-int(tolerance_);
        const int high=(anchor_>target_?anchor_:target_)+int(tolerance_);
        if(int(j.position)<low||int(j.position)>high){fail("LEG_UNEXPECTED_DIRECTION_OR_OVERSHOOT");return false;}
      }
    }
    return true;
  }
  HoldInitializationPolicy p_;uint16_t target_,tolerance_,anchor_=0;
  struct ExpectedState { unsigned position,goal,torque; };
  ExpectedState expected_[7]={};bool bound_=false;
  bool (*healthy_)(void*);void* context_;
  HoldStateSnapshot scans_[32];HoldActionEvidence action_;
  size_t count_=0;uint64_t started_=0,last_poll_=0;
  bool written_=false,previous_in_band_=false;
  HeldLegPhase phase_=HeldLegPhase::New;const char* reason_="NOT_STARTED";
};
}
