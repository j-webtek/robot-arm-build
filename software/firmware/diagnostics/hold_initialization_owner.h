// Offline-tested staged elbow initializer. Not wired to any installed route.
// Outer integration must authenticate/bind boot+operation, reserve durable record
// capacity and grant exclusive bus ownership BEFORE polling this object.
// This core does not constitute authorization or independently acquire a lock.
#pragma once
#include "hold_state_snapshot.h"

namespace rocell_diag {
struct HoldInitializationPolicy {
  uint16_t minimum[7]={},maximum[7]={};
  uint16_t drift=2,speed=20;
  uint8_t acceleration=1;
  bool permit_explicit_enable=false;
  uint64_t baseline_gap_us=100000,settle_us=100000,maximum_gap_us=500000;
  uint64_t pair_us=10000,scan_us=100000,age_us=250000,deadline_us=2000000;
};
struct HoldActionEvidence {
  uint8_t servo_id=14,address=0,width=0,bytes[7]={};
  uint64_t started_us=0,finished_us=0;
  DispatchEvidence ack={};
};
enum class HoldPhase { New, BaselineWait, Hold, ReadHold, Enable, ReadEnable,
                       Settling, Captured, Fault };
// Explicit construction only: existing settings/routes cannot enable recovery.
// Outer integration must separately bind one-use recovery authorization.
struct SupportedRecoveryAdmission {};
// Separate offline profile for the recorded six-count failed return. No installed
// route selects this tag; authenticated policy/export integration is required.
struct SixCountRecoveryAdmission {};
class HoldInitializationOwner {
 public:
  explicit HoldInitializationOwner(const HoldInitializationPolicy& p,
      bool (*boundary)(void*)=nullptr,void* context=nullptr)
      :policy_(p),boundary_(boundary),context_(context){}
  HoldInitializationOwner(const HoldInitializationPolicy& p,
      SupportedRecoveryAdmission, bool (*boundary)(void*)=nullptr,void* context=nullptr)
      :policy_(p),recovery_(true),boundary_(boundary),context_(context){}
  HoldInitializationOwner(const HoldInitializationPolicy& p,
      SixCountRecoveryAdmission, bool (*boundary)(void*)=nullptr,void* context=nullptr)
      :policy_(p),recovery_(true),initial_residual_limit_(6),boundary_(boundary),context_(context){}
  template<class Library,class Clock>
  void poll(Library& bus,Clock& clock){
    if(phase_==HoldPhase::Fault||phase_==HoldPhase::Captured)return;
    const uint64_t now=clock.now_us();
    if(now>INT64_MAX||(last_poll_&&now<last_poll_)){fail("HOLD_CLOCK_INVALID");return;}
    last_poll_=now;
    if(phase_==HoldPhase::New){
      if(!policy_valid(policy_)||bus.End!=0||bus.Level!=1){fail("HOLD_POLICY_OR_ACK_INVALID");return;}
      if(recovery_&&(policy_.drift!=2||policy_.speed!=20||
                     policy_.permit_explicit_enable)){
        fail("RECOVERY_POLICY_INVALID");return;
      }
      started_=now;
      if(!capture(bus,clock))return;
      // A controller-only restart leaves powered servos holding their last goal.
      // Accept that state only when already tracking within the hold tolerance;
      // never release torque just to satisfy an initialization assumption.
      const auto& elbow=*last()->joint(3);
      if(elbow.torque==1&&delta(elbow.position,elbow.goal)>(recovery_?initial_residual_limit_:policy_.drift)){
        fail("HOLD_ENABLED_ELBOW_NOT_TRACKING");return;
      }
      phase_=HoldPhase::BaselineWait;return;
    }
    if(now-started_>policy_.deadline_us){fail("HOLD_DEADLINE");return;}
    if(now<last()->finished_us()){fail("HOLD_CLOCK_INVALID");return;}
    if(now-last()->finished_us()>policy_.maximum_gap_us){fail("HOLD_OBSERVATION_GAP");return;}
    if(phase_==HoldPhase::BaselineWait){
      if(now-last()->finished_us()<policy_.baseline_gap_us)return;
      if(!capture(bus,clock)||!unchanged_elbow())return;
      phase_=HoldPhase::Hold;return;
    }
    if(phase_==HoldPhase::Hold||phase_==HoldPhase::Enable){
      const bool enable=phase_==HoldPhase::Enable;
      if(!capture(bus,clock))return;
      const auto& elbow=*last()->joint(3);
      if(!enable){
        if(!unchanged_elbow())return;
        target_=elbow.position;
      }else if(!policy_.permit_explicit_enable||elbow.torque!=0||elbow.goal!=target_||
               delta(elbow.position,target_)>policy_.drift){fail("HOLD_ENABLE_STATE_INVALID");return;}
      dispatch(bus,clock,enable);return;
    }
    // Give a just-acknowledged write the configured dwell before requiring a
    // stationary scan. This schedules the first observation, not a retry; a
    // moving flag in that observation still faults and no write is repeated.
    if(phase_==HoldPhase::ReadHold||phase_==HoldPhase::ReadEnable){
      const auto finished=actions_[action_count_-1].finished_us;
      if(now<finished){fail("HOLD_CLOCK_INVALID");return;}
      if(now-finished<policy_.settle_us)return;
    }
    if(phase_==HoldPhase::Settling&&now-last()->finished_us()<policy_.settle_us)return;
    if(!capture(bus,clock))return;
    const auto& elbow=*last()->joint(3);
    if(last()->started_us()<=actions_[action_count_-1].finished_us||
       elbow.goal!=target_||delta(elbow.position,target_)>policy_.drift){
      fail("HOLD_READBACK_MISMATCH");return;
    }
    if(elbow.torque==0){
      if(phase_==HoldPhase::ReadHold&&policy_.permit_explicit_enable&&
         scans_[0].joint(3)->torque==0){phase_=HoldPhase::Enable;return;}
      fail("HOLD_TORQUE_NOT_ENABLED");return;
    }
    if(phase_==HoldPhase::Settling){phase_=HoldPhase::Captured;reason_="ELBOW_HOLD_CAPTURED";return;}
    phase_=HoldPhase::Settling;
  }
  HoldPhase phase()const{return phase_;}
  const char* reason()const{return reason_;}
  size_t scan_count()const{return scan_count_;}
  size_t action_count()const{return action_count_;}
  bool supported_recovery()const{return recovery_;}
  void export_failed(){fail("HOLD_EXPORT_FAILED");}
  void interference(){fail("HOLD_EXTERNAL_INTERFERENCE");}
  const HoldStateSnapshot* scan(size_t i)const{return i<scan_count_?&scans_[i]:nullptr;}
  const HoldActionEvidence* action(size_t i)const{return i<action_count_?&actions_[i]:nullptr;}
  // Captured means evidence ready to export, NOT host-verified or all-arm ready.
 private:
  static unsigned delta(unsigned a,unsigned b){return a>b?a-b:b-a;}
 public:
  static bool policy_valid(const HoldInitializationPolicy& policy_){
    if(policy_.drift>8||!policy_.speed||policy_.speed>40||policy_.acceleration!=1||
       !policy_.baseline_gap_us||!policy_.settle_us||!policy_.maximum_gap_us||
       policy_.baseline_gap_us>policy_.maximum_gap_us||policy_.settle_us>policy_.maximum_gap_us||
       policy_.maximum_gap_us>1000000||!policy_.pair_us||policy_.pair_us>100000||
       !policy_.scan_us||policy_.scan_us>1000000||!policy_.age_us||policy_.age_us>1000000||
       !policy_.deadline_us||policy_.deadline_us>10000000)return false;
    for(size_t i=0;i<7;++i)if(policy_.minimum[i]>policy_.maximum[i]||policy_.maximum[i]>4095)return false;
    return true;
  }
 private:
  HoldStateSnapshot* last(){return scan_count_?&scans_[scan_count_-1]:nullptr;}
  void fail(const char* reason){if(phase_!=HoldPhase::Fault){phase_=HoldPhase::Fault;reason_=reason;}}
  bool unchanged_elbow(){
    const auto& a=*scans_[0].joint(3);const auto& b=*last()->joint(3);
    if(a.goal!=b.goal||a.torque!=b.torque){fail("HOLD_ELBOW_CHANGED");return false;}
    return true;
  }
  template<class Library,class Clock>
  bool capture(Library& bus,Clock& clock){
    if(scan_count_==8){fail("HOLD_STORAGE_FULL");return false;}
    const uint64_t previous=last()?last()->finished_us():0;
    auto& s=scans_[scan_count_++];
    if(!s.capture(bus,clock,policy_.pair_us,policy_.scan_us)){fail(s.reason());return false;}
    const uint64_t boundary=clock.now_us();
    if(!s.fresh(boundary,policy_.age_us)||s.started_us()<=previous||boundary<started_||
       boundary-started_>policy_.deadline_us){fail("HOLD_CAPTURE_TIMING_INVALID");return false;}
    for(size_t i=0;i<7;++i){
      const auto& j=*s.joint(i);
      if(recovery_&&i==3&&(j.torque!=1||
         (action_count_==0&&(delta(j.position,j.goal)>initial_residual_limit_||
          j.goal<policy_.minimum[i]||j.goal>policy_.maximum[i])))){
        fail("RECOVERY_INITIAL_STATE_INVALID");return false;
      }
      if(j.mode!=0||j.moving!=0||j.position<policy_.minimum[i]||j.position>policy_.maximum[i]){
        fail("HOLD_POSE_OR_CONTROL_INVALID");return false;
      }
      if(scan_count_>1){const auto& original=*scans_[0].joint(i);
        if(delta(j.position,original.position)>policy_.drift||
           (i!=3&&(j.goal!=original.goal||j.torque!=original.torque))){
          fail("HOLD_NEIGHBOR_OR_DRIFT_CHANGED");return false;
        }
      }
    }
    return true;
  }
  template<class Library,class Clock>
  void dispatch(Library& bus,Clock& clock,bool enable){
    if(boundary_&&!boundary_(context_)){fail("HOLD_EXTERNAL_BOUNDARY_REJECTED");return;}
    const uint64_t boundary=clock.now_us();
    if(action_count_>=2||bus.End!=0||bus.Level!=1||!last()->fresh(boundary,policy_.age_us)||
       boundary<started_||boundary-started_>policy_.deadline_us){fail("HOLD_WRITE_BOUNDARY_INVALID");return;}
    auto& a=actions_[action_count_++]; // Reserve before calling the library, never retry.
    a.started_us=boundary;a.address=enable?40:41;a.width=enable?1:7;
    a.bytes[0]=enable?1:policy_.acceleration;
    if(!enable){a.bytes[1]=target_&255;a.bytes[2]=target_>>8;
      a.bytes[5]=policy_.speed&255;a.bytes[6]=policy_.speed>>8;}
    const int result=enable?bus.EnableTorque(14,1):bus.WritePosEx(14,target_,policy_.speed,policy_.acceleration);
    a.finished_us=clock.now_us();
    a.ack=record_dispatch(14,result,result==1?bus.Error:-1,AckPolicy::Enabled);
    if(a.finished_us<a.started_us||a.finished_us>INT64_MAX||
       a.finished_us-started_>policy_.deadline_us||a.ack.status!=DispatchStatus::Succeeded){
      fail("HOLD_ACK_UNCERTAIN_OR_FAILED");return;
    }
    phase_=enable?HoldPhase::ReadEnable:HoldPhase::ReadHold;
  }
  HoldInitializationPolicy policy_;
  bool recovery_=false;
  uint16_t initial_residual_limit_=5;
  HoldStateSnapshot scans_[8];HoldActionEvidence actions_[2];
  size_t scan_count_=0,action_count_=0;
  uint64_t started_=0,last_poll_=0;uint16_t target_=0;
  HoldPhase phase_=HoldPhase::New;const char* reason_="NOT_STARTED";
  bool (*boundary_)(void*);void* context_;
};
}
