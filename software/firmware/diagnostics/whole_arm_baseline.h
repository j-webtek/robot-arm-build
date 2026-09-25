// Fresh joint-state evidence only, NOT collision/clearance or physical accuracy.
// Use after installed servo-profile review, through the sole native bus owner.
#pragma once
#include "reference_read_adapter.h"
namespace rocell_diag {
struct JointCountWindow {uint16_t minimum,maximum;};
struct WholeArmBaselinePolicy {
  JointCountWindow joints[7]; // IDs 11..17, including BOTH shoulder servos.
  uint16_t tracking_tolerance;
  uint64_t maximum_pair_us,maximum_scan_us,maximum_age_us;
};
class WholeArmBaseline {
 public:
  explicit WholeArmBaseline(const WholeArmBaselinePolicy& policy):policy_(policy) {}
  template<class Library,class Clock>
  bool check(Library& library,Clock& clock) {
    if(used_)return false;used_=true;
    reason_="INVALID_WHOLE_ARM_POLICY";
    if(library.End!=0 || policy_.tracking_tolerance>16 ||
       !policy_.maximum_pair_us || policy_.maximum_pair_us>1000000 ||
       !policy_.maximum_scan_us || policy_.maximum_scan_us>7000000 ||
       !policy_.maximum_age_us || policy_.maximum_age_us>1000000)return false;
    for(const auto& bounds:policy_.joints)
      if(bounds.minimum>bounds.maximum || bounds.maximum>4095)return false;
    ReferenceReadAdapter<Library> adapter(library);
    for(size_t index=0;index<7;++index) {
      PairEvidence& pair=pairs_[index];
      const bool read_ok=recorder_.acquire(static_cast<uint8_t>(11+index),adapter,clock,pair);
      count_=index+1; // Retain failure evidence, but do not read later joints.
      reason_="WHOLE_ARM_READ_FAILED";if(!read_ok)return false;
      reason_="WHOLE_ARM_TIMING_INVALID";
      if(pair.feedback.finished_us>INT64_MAX ||
         pair.feedback.finished_us-pair.target.started_us>policy_.maximum_pair_us ||
         pair.feedback.finished_us-pairs_[0].target.started_us>policy_.maximum_scan_us)return false;
      reason_="WHOLE_ARM_STALE";
      if(pair.feedback.finished_us-pairs_[0].target.started_us>policy_.maximum_age_us)return false;
      const unsigned position=pair.feedback.bytes[0]|(static_cast<unsigned>(pair.feedback.bytes[1])<<8);
      const unsigned target=pair.target.bytes[0]|(static_cast<unsigned>(pair.target.bytes[1])<<8);
      const auto& bounds=policy_.joints[index];
      reason_="WHOLE_ARM_OUTSIDE_WINDOW";
      if(position<bounds.minimum || position>bounds.maximum || target<bounds.minimum || target>bounds.maximum)return false;
      reason_="WHOLE_ARM_NOT_SETTLED";
      const unsigned error=position>target?position-target:target-position;
      if(pair.feedback.bytes[10]!=0 || error>policy_.tracking_tolerance)return false;
    }
    accepted_=true;
    if(!fresh(clock.now_us())){accepted_=false;reason_="WHOLE_ARM_STALE";return false;}
    reason_="WHOLE_ARM_BASELINE_ACCEPTED";return true;
  }
  // Must be checked again immediately before dispatch; all seven reads age from
  // the FIRST read start, not just the newest sample. Sequential, not simultaneous.
  bool fresh(uint64_t now) {
    if(!accepted_)return false;
    if(count_!=7 || now>INT64_MAX || now<last_checked_us_ ||
        now<pairs_[6].feedback.finished_us ||
        now-pairs_[0].target.started_us>policy_.maximum_age_us) {
      accepted_=false;reason_="WHOLE_ARM_STALE";return false;
    }
    last_checked_us_=now;return true;
  }
  const PairEvidence* pair(size_t index) const{return index<count_?&pairs_[index]:nullptr;}
  size_t count() const{return count_;}
  const char* reason() const{return reason_;}
  bool accepted() const{return accepted_;}
  uint64_t checked_us() const{return last_checked_us_;}
  const WholeArmBaselinePolicy& policy() const{return policy_;}
 private:
  const WholeArmBaselinePolicy policy_;PairRecorder recorder_;PairEvidence pairs_[7]={};
  size_t count_=0;bool used_=false,accepted_=false;const char* reason_="NOT_STARTED";
  uint64_t last_checked_us_=0;
};
}
