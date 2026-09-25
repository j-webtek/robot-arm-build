// Finite read-only acquisition primitive; not a motion admission or bus owner.
// Outer integration MUST hold sole bus ownership for its entire lifetime.
#pragma once
#include <stddef.h>
#include "reference_read_adapter.h"
namespace rocell_diag {
class BaselineOnlyScan {
 public:
  template<class Library, class Clock>
  bool run(Library& library, Clock& clock, uint64_t maximum_pair_us,
           uint64_t maximum_scan_us) {
    if (used_) return false;
    used_=true;
    if (library.End!=0 || !maximum_pair_us || maximum_pair_us>1000000 ||
        !maximum_scan_us || maximum_scan_us>7000000) {
      reason_="INVALID_SCAN_CONFIGURATION"; return false;
    }
    ReferenceReadAdapter<Library> adapter(library);
    for(size_t index=0;index<7;++index) {
      auto& pair=pairs_[index];
      const bool valid=recorder_.acquire(static_cast<uint8_t>(11+index),adapter,clock,pair);
      count_=index+1; // Preserve both outcomes, including a failed pair.
      if(!valid){reason_="BASELINE_READ_FAILED";return false;}
      if(pair.feedback.finished_us>INT64_MAX ||
         pair.feedback.finished_us-pair.target.started_us>maximum_pair_us ||
         pair.feedback.finished_us-pairs_[0].target.started_us>maximum_scan_us) {
        reason_="BASELINE_TIMING_INVALID";return false;
      }
    }
    complete_=true;reason_="BASELINE_CAPTURED";return true;
  }
  bool complete() const{return complete_;}
  const char* reason() const{return reason_;}
  size_t count() const{return count_;}
  const PairEvidence* pair(size_t index) const{return index<count_?&pairs_[index]:nullptr;}
 private:
  bool used_=false,complete_=false;
  const char* reason_="NOT_STARTED";
  size_t count_=0;
  PairRecorder recorder_;
  PairEvidence pairs_[7]={};
};
}
