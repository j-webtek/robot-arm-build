// Acquisition only. Caller must own the bus and prevent concurrent operations.
// No pose acceptance, target changes, torque writes, fault clearing or retries.
#pragma once
#include "hold_state_snapshot.h"
namespace rocell_diag {
class PoseObservationSequence {
 public:
  enum class State { Idle, Sampling, Captured, Fault };
  bool begin(uint64_t now){
    if(state_!=State::Idle)return false;
    started_=last_poll_=next_=now;state_=State::Sampling;return true;
  }
  template<class ReadOnlyBus,class Clock>
  void poll(ReadOnlyBus& bus,Clock& clock){
    if(state_!=State::Sampling)return;
    const uint64_t now=clock.now_us();
    if(now<last_poll_||now-started_>1000000){fail("OBSERVATION_TIMING_INVALID");return;}
    last_poll_=now;if(now<next_)return;
    auto& snapshot=scans_[count_++];
    if(!snapshot.capture(bus,clock,10000,100000)){fail(snapshot.reason());return;}
    const uint64_t end=clock.now_us();
    if(end<now||end-started_>1000000){fail("OBSERVATION_TIMING_INVALID");return;}
    if(count_==3){state_=State::Captured;reason_="OBSERVATIONS_CAPTURED";return;}
    next_=end+100000;last_poll_=end;
  }
  State state()const{return state_;}
  const char* reason()const{return reason_;}
  size_t size()const{return count_;}
  const HoldStateSnapshot* snapshot(size_t i)const{return i<count_?&scans_[i]:nullptr;}
 private:
  void fail(const char* reason){reason_=reason;state_=State::Fault;}
  HoldStateSnapshot scans_[3];size_t count_=0;
  uint64_t started_=0,last_poll_=0,next_=0;
  State state_=State::Idle;const char* reason_="NOT_STARTED";
};
}
