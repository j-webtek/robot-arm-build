// One-use, read-only baseline gate for the pinned elbow profile. A moving flag
// of zero is evidence, not proof of clearance or full-arm stationarity.
#pragma once
#include "reference_read_adapter.h"
#include "servo_evidence_json.h"
namespace rocell_diag {
class FreshElbowBaseline {
 public:
  FreshElbowBaseline():used_(false),captured_(false),accepted_(false),reason_("NOT_STARTED"),pair_{} {}
  template<class Library,class Clock>
  bool check(Library& library,Clock& clock,uint16_t target,uint16_t maximum_delta,
             uint16_t settled_tolerance,uint64_t maximum_pair_us,uint64_t maximum_age_us) {
    if(used_)return false;used_=true;
    reason_="INVALID_BASELINE_POLICY";
    if(library.End!=0 || target<1024 || target>3071 || !maximum_delta || maximum_delta>64 ||
       settled_tolerance>16 || !maximum_pair_us || maximum_pair_us>1000000 ||
       !maximum_age_us || maximum_age_us>1000000)return false;
    ReferenceReadAdapter<Library> adapter(library);
    const bool valid=recorder_.acquire(14,adapter,clock,pair_);captured_=true;
    reason_="INVALID_BASELINE_READ";if(!valid)return false;
    const uint64_t now=clock.now_us();
    reason_="STALE_BASELINE";
    if(now<pair_.feedback.finished_us || now>INT64_MAX ||
       now-pair_.feedback.finished_us>maximum_age_us ||
       pair_.feedback.finished_us-pair_.target.started_us>maximum_pair_us)return false;
    const unsigned position=pair_.feedback.bytes[0]|(static_cast<unsigned>(pair_.feedback.bytes[1])<<8);
    const unsigned goal=pair_.target.bytes[0]|(static_cast<unsigned>(pair_.target.bytes[1])<<8);
    reason_="BASELINE_OUTSIDE_PROFILE";
    if(position<1024 || position>3071 || goal<1024 || goal>3071)return false;
    reason_="BASELINE_NOT_SETTLED";
    const unsigned tracking=position>goal?position-goal:goal-position;
    if(pair_.feedback.bytes[10]!=0 || tracking>settled_tolerance)return false;
    reason_="BASELINE_DELTA_EXCEEDED";
    const unsigned delta=position>target?position-target:target-position;
    if(delta>maximum_delta)return false;
    accepted_=true;reason_="BASELINE_ACCEPTED";return true;
  }
  bool encode(const char* boot,const char* command,char* output,size_t capacity) const {
    if(output && capacity)output[0]=0;
    return captured_ && pair_json(pair_,boot,command,"little",output,capacity);
  }
  bool accepted() const{return accepted_;}
  const char* reason() const{return reason_;}
  uint64_t finished_us() const{return pair_.feedback.finished_us;}
 private:
  bool used_,captured_,accepted_;const char* reason_;
  PairEvidence pair_;PairRecorder recorder_;
};
}
