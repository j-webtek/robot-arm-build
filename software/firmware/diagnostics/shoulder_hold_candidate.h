// Offline composed candidate, not installed or exposed by any network route.
// Completion proves only sampled torque/target/position agreement, NOT load
// sharing, mechanical clearance, physical stability or permission to lift.
#pragma once
#include "shoulder_preload_candidate.h"
#include "shoulder_enable_packet_candidate.h"
namespace rocell_diag {
class ShoulderHoldCandidate {
 public:
  template<class Bus,class Clock,class Evidence,class Admission>
  bool run(Bus& bus,Clock& clock,Evidence& evidence,Admission& admitted){
    if(used_)return false;
    used_=true;
    if(!preload_.run(bus,clock,evidence,admitted)){reason_=preload_.reason();return false;}
    ShoulderPreloadPose current;
    const auto& baseline=preload_.baseline_;
    if(!ShoulderPreloadCandidate::sample(bus,clock,current,admitted)||
       !ShoulderPreloadCandidate::consistent(baseline,current,2)){
      reason_="PRE_ENABLE_STATE_CHANGED";return false;
    }
    if(!evidence("PAIR_ENABLE_INTENT",current,0,0)){
      reason_="EXPORT_FAILED";return false;
    }
    // Re-read after potentially slow durable export; never reuse earlier goals.
    if(!ShoulderPreloadCandidate::sample(bus,clock,current,admitted)||
       !ShoulderPreloadCandidate::consistent(baseline,current,2)){
      reason_="POST_EXPORT_STATE_CHANGED";return false;
    }
    delivery_=enable_.emit_once(bus);
    if(!evidence("PAIR_ENABLE_SENT_UNACKNOWLEDGED",current,0,0)){
      reason_="EXPORT_FAILED";return false;
    }
    // Broadcast transmission is not an ACK. Read both shoulders and neighbors;
    // no further actuator write follows, including after partial enable.
    auto expected=baseline;expected.torque[1]=expected.torque[2]=1;
    for(int sample=0;sample<3;++sample){
      if(!ShoulderPreloadCandidate::sample(bus,clock,current,admitted)){
        reason_="ENABLE_FEEDBACK_INVALID";return false;
      }
      const bool matches=ShoulderPreloadCandidate::consistent(expected,current,2);
      if(!evidence("PAIR_ENABLE_READBACK",current,0,matches?1:0)){
        reason_="EXPORT_FAILED";return false;
      }
      if(!matches){reason_="ENABLE_READBACK_MISMATCH";return false;}
    }
    expected_=expected;last_=current.finished_us;began_=last_;
    observing_=true;reason_="OBSERVING_PAIR_HOLD";return true;
  }
  // Nonblocking scheduler entry: no actuator writes. These provisional timing
  // values are bounded observation parameters, not mechanical safety limits.
  template<class Bus,class Clock,class Evidence,class Admission>
  void poll(Bus& bus,Clock& clock,Evidence& evidence,Admission& admitted){
    if(!observing_)return;
    auto stop=[&](const char* reason){reason_=reason;observing_=false;};
    const auto now=clock.now_us();
    if(now<last_||now-last_>500000||now-began_>3000000){stop("HOLD_OBSERVATION_GAP");return;}
    if(!admitted()){stop("HOLD_ADMISSION_LOST");return;}
    if(now-last_<100000)return;
    ShoulderPreloadPose current;
    if(!ShoulderPreloadCandidate::sample(bus,clock,current,admitted)){
      stop("HOLD_FEEDBACK_INVALID");return;
    }
    bool stationary=true;
    for(int i=0;i<7;++i){
      // Zero has the same representation irrespective of speed sign convention.
      if(current.feedback[i][2]||current.feedback[i][3]||current.feedback[i][10])stationary=false;
    }
    const bool matches=stationary&&ShoulderPreloadCandidate::consistent(expected_,current,2);
    if(!evidence("TIMED_HOLD_SAMPLE",current,0,matches?1:0)){stop("EXPORT_FAILED");return;}
    if(!matches){stop("HOLD_STATE_CHANGED");return;}
    last_=current.finished_us;++samples_;
    const auto after=clock.now_us();
    if(after<last_||after-last_>500000||after-began_>3000000){stop("HOLD_EXPORT_GAP");return;}
    if(last_-began_>=2000000&&samples_>=5){
      observed_=true;stop("TIMED_PAIR_HOLD_OBSERVED");
    }
  }
  bool observation_complete()const{return observed_;}
  const char* reason()const{return reason_;}
  ShoulderEnableDelivery delivery()const{return delivery_;}
 private:
  bool used_=false;const char* reason_="NOT_STARTED";
  bool observing_=false,observed_=false;uint64_t began_=0,last_=0;unsigned samples_=0;
  ShoulderPreloadPose expected_;
  ShoulderPreloadCandidate preload_;ShoulderEnablePacketCandidate enable_;
  ShoulderEnableDelivery delivery_=ShoulderEnableDelivery::NotAttempted;
};
}
