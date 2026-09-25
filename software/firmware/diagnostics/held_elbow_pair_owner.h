// Finite mechanical scheduler, offline only. The outer authenticated runtime
// owns bus exclusion, initial authorization and durable evidence storage.
// Continuation.consume(anchor, forward) must verify the one-use signed return
// and the exported forward evidence. A boolean supplied over HTTP is NOT such
// an implementation. No transport route instantiates this scheduler yet.
#pragma once
#include <new>
#include "held_elbow_leg_owner.h"

namespace rocell_diag {
enum class HeldPairPhase { New, Forward, AwaitingExport, Return, Complete, Stopped };
class HeldElbowPairOwner {
 public:
  HeldElbowPairOwner(const HoldInitializationPolicy& policy,int offset,uint16_t tolerance,
      bool (*healthy)(void*),void* context=nullptr)
      :policy_(policy),offset_(offset),tolerance_(tolerance),healthy_(healthy),context_(context){}
  HeldElbowPairOwner(const HeldElbowPairOwner&)=delete;
  HeldElbowPairOwner& operator=(const HeldElbowPairOwner&)=delete;
  ~HeldElbowPairOwner(){if(leg_)leg_->~HeldElbowLegOwner();}

  // The caller supplies a verified hold endpoint. All actual dispatches still
  // require the leg's fresh scans; the retained endpoint is continuity evidence.
  bool start(const HoldStateSnapshot& held){
    if(phase_!=HeldPairPhase::New)return false;
    const auto* joint=held.joint(3);
    if(!healthy_||!healthy_(context_)||!joint||joint->torque!=1||joint->moving||
       !HoldInitializationOwner::policy_valid(policy_)||tolerance_>2||
       offset_ < -16||offset_ > 16||
       (offset_>=-int(2*tolerance_)&&offset_<=int(2*tolerance_)))
      return stop("PAIR_INITIAL_STATE_INVALID");
    original_anchor_=joint->position;
    const int target=int(original_anchor_)+offset_;
    if(original_anchor_<policy_.minimum[3]||original_anchor_>policy_.maximum[3]||
       target<policy_.minimum[3]||target>policy_.maximum[3])
      return stop("PAIR_TARGET_OUTSIDE_ENVELOPE");
    leg_=new(storage_) HeldElbowLegOwner(policy_,uint16_t(target),tolerance_,healthy_,context_);
    if(!leg_->bind_start(held))return stop("PAIR_INITIAL_BINDING_FAILED");
    phase_=HeldPairPhase::Forward;reason_="PAIR_FORWARD";return true;
  }

  // Driver.poll(leg) must perform acquisition AND publication before returning;
  // any publication error must fault the leg (HeldLegEvidencePublisher does).
  template<class Driver> void poll(Driver& driver){
    if(phase_!=HeldPairPhase::Forward&&phase_!=HeldPairPhase::Return)return;
    if(!healthy_||!healthy_(context_)){stop("PAIR_BOUNDARY_INVALID");return;}
    driver.poll(*leg_);
    if(!leg_->terminal())return;
    if(leg_->phase()!=HeldLegPhase::Arrived){stop(leg_->reason());return;}
    if(phase_==HeldPairPhase::Forward){
      phase_=HeldPairPhase::AwaitingExport;reason_="PAIR_AWAITING_FORWARD_EXPORT";
    }else{phase_=HeldPairPhase::Complete;reason_="PAIR_COMPLETE";}
  }

  // Consume before releasing forward raw evidence. A failed or duplicate
  // attempt cannot restart either leg. Driver/sink rollover happens outside
  // this object only after success, before the next poll.
  template<class Continuation> bool admit_return(Continuation& continuation){
    if(return_attempted_||phase_!=HeldPairPhase::AwaitingExport)return false;
    return_attempted_=true;
    if(!healthy_||!healthy_(context_)||
       !continuation.consume(original_anchor_,*leg_))return stop("PAIR_RETURN_REJECTED");
    endpoint_=*leg_->scan(leg_->scan_count()-1);
    // Reuse one scan-history allocation; never retain two 32-scan owners.
    leg_->~HeldElbowLegOwner();
    leg_=new(storage_) HeldElbowLegOwner(policy_,original_anchor_,tolerance_,healthy_,context_);
    if(!leg_->bind_start(endpoint_))return stop("PAIR_RETURN_BINDING_FAILED");
    phase_=HeldPairPhase::Return;reason_="PAIR_RETURN";return true;
  }
  void export_failed(){stop("PAIR_EXPORT_FAILED");}
  HeldPairPhase phase()const{return phase_;}
  const char* reason()const{return reason_;}
  uint16_t original_anchor()const{return original_anchor_;}
  const HeldElbowLegOwner* leg()const{return leg_;}
 private:
  bool stop(const char* reason){phase_=HeldPairPhase::Stopped;reason_=reason;return false;}
  HoldInitializationPolicy policy_;int offset_;uint16_t tolerance_,original_anchor_=0;
  bool (*healthy_)(void*);void* context_;bool return_attempted_=false;
  alignas(HeldElbowLegOwner) unsigned char storage_[sizeof(HeldElbowLegOwner)];
  HeldElbowLegOwner* leg_=nullptr;HoldStateSnapshot endpoint_;
  HeldPairPhase phase_=HeldPairPhase::New;const char* reason_="NOT_STARTED";
};
}
