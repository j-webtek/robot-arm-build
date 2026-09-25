// Offline r54 one-use state machine. No route, key, hardware adapter or startup
// action. The caller must exclusively own the servo bus and persist evidence.
#pragma once
#include "fixed_pair_reanchor_policy.h"
#include <cstddef>
namespace rocell_diag {
class FixedPairReanchorOwner {
 public:
  enum class State { New, CapturingStart, Prewrite, CapturingEndpoint,
                     AwaitExport, Complete, Fault };

  template<class Reserve,class Clock>
  bool begin(Reserve& reserve,Clock& clock){
    if(state_!=State::New)return false;
    state_=State::Fault;reason_="RESERVATION_FAILED";
    if(!reserve())return false;
    started_us_=clock.now_us();
    if(!started_us_)return false;
    state_=State::CapturingStart;reason_="CAPTURING_START";
    return true;
  }

  template<class Acquire,class Write,class Clock,class Evidence,class Admission>
  void poll(Acquire& acquire,Write& write,Clock& clock,Evidence& evidence,
            Admission& admitted){
    if(state_==State::New||state_==State::Complete||state_==State::Fault||
       state_==State::AwaitExport)return;
    const auto now=clock.now_us();
    if(now<started_us_||now-started_us_>8000000||!admitted()){
      fail("DEADLINE_OR_ADMISSION_LOST");return;
    }
    if(last_finished_us_&&now<last_finished_us_){fail("CLOCK_REVERSED");return;}
    if(last_finished_us_&&now-last_finished_us_<100000)return;
    ShoulderPreloadPose pose;
    if(!acquire(pose)||!ShoulderCharacterizationPolicy::valid(pose)||
       pose.started_us<=last_finished_us_||pose.finished_us>clock.now_us()||
       clock.now_us()-pose.finished_us>100000){
      fail("FRESH_FEEDBACK_FAILED");return;
    }
    last_finished_us_=pose.finished_us;
    if(state_==State::CapturingStart){
      before_[count_++]=pose;
      if(!evidence("START_SAMPLE",pose)){fail("EVIDENCE_FAILED");return;}
      if(count_<3)return;
      if(!FixedPairReanchorPolicy::start(before_,clock.now_us())){
        fail("START_GATE_FAILED");return;
      }
      if(!evidence("FIXED_INTENT",pose)){fail("EVIDENCE_FAILED");return;}
      state_=State::Prewrite;reason_="PREWRITE";return;
    }
    if(state_==State::Prewrite){
      if(!same_start(pose,before_[2])||
         !FixedPairReanchorPolicy::start(before_,clock.now_us())){
        fail("PREWRITE_CHANGED");return;
      }
      if(!evidence("PREWRITE",pose)||!admitted()){
        fail("EVIDENCE_OR_ADMISSION_FAILED");return;
      }
      prewrite_=pose;
      sent_us_=clock.now_us();
      if(sent_us_<pose.finished_us||sent_us_-pose.finished_us>100000){
        fail("PREWRITE_EXPIRED");return;
      }
      ++writes_; // Counts an attempt even if delivery is uncertain.
      if(!write(uint8_t(12),uint8_t(13),uint16_t(2389),uint16_t(1725),
                uint16_t(20),uint8_t(1))){
        fail("WRITE_DELIVERY_UNCERTAIN");return;
      }
      if(!evidence("WRITE_ATTEMPTED",pose)){
        fail("EVIDENCE_FAILED_AFTER_WRITE");return;
      }
      count_=0;state_=State::CapturingEndpoint;
      reason_="CAPTURING_ENDPOINT";return;
    }
    after_[count_++]=pose;
    if(!evidence("ENDPOINT_SAMPLE",pose)){
      fail("EVIDENCE_FAILED_AFTER_WRITE");return;
    }
    if(count_<3)return;
    if(!FixedPairReanchorPolicy::endpoint(before_,after_,sent_us_,clock.now_us())){
      fail("ENDPOINT_GATE_FAILED");return;
    }
    state_=State::AwaitExport;reason_="AWAITING_DURABLE_EXPORT";
  }

  // Trusted owner-task seam only. Do not bind directly to an unauthenticated
  // route: the future adapter must verify exact retained bytes and host export.
  bool mark_export_verified(bool exact_retained_export_verified){
    if(state_!=State::AwaitExport||exact_retained_export_verified!=true)return false;
    state_=State::Complete;reason_="REANCHOR_VERIFIED";return true;
  }
  State state()const{return state_;}
  const char* reason()const{return reason_;}
  unsigned writes()const{return writes_;}
  uint64_t sent_us()const{return sent_us_;}
  const ShoulderPreloadPose (&before()const)[3]{return before_;}
  const ShoulderPreloadPose& prewrite()const{return prewrite_;}
  const ShoulderPreloadPose (&after()const)[3]{return after_;}

  // Fixed-width, big-endian, padding-free evidence. The authenticated board
  // adapter must bind this to its real 16-byte boot identity and retain/export
  // all bytes before accepting completion. A fault has no success record.
  size_t copy_result(const uint8_t (&boot)[16],uint8_t* out,size_t capacity)const{
    constexpr size_t required=10+16+8+1+7*(16+7*20);
    if(state_!=State::AwaitExport||writes_!=1||!out||capacity<required)return 0;
    size_t size=0;
    auto put=[&](uint64_t value,unsigned width){
      for(int n=int(width)-1;n>=0;--n)out[size++]=uint8_t(value>>(n*8));
    };
    const char domain[]="RCRANCH001";
    for(size_t i=0;i<sizeof(domain)-1;++i)put(uint8_t(domain[i]),1);
    for(auto byte:boot)put(byte,1);
    put(sent_us_,8);put(writes_,1);
    auto pose=[&](const ShoulderPreloadPose& p){
      put(p.started_us,8);put(p.finished_us,8);
      for(int i=0;i<7;++i){
        put(p.position[i],2);put(p.goal[i],2);put(p.torque[i],1);
        for(auto byte:p.feedback[i])put(byte,1);
      }
    };
    for(const auto& p:before_)pose(p);
    pose(prewrite_);
    for(const auto& p:after_)pose(p);
    return size==required?size:0;
  }

 private:
  static bool same_start(const ShoulderPreloadPose& current,
                         const ShoulderPreloadPose& baseline){
    for(int i=0;i<7;++i)
      if(current.goal[i]!=baseline.goal[i]||current.torque[i]!=baseline.torque[i]||
         ShoulderCharacterizationPolicy::moving(current,i)||
         std::abs(int(current.position[i])-int(baseline.position[i]))>1||
         (current.feedback[i][0]|uint16_t(current.feedback[i][1])<<8)!=current.position[i])
        return false;
    return true;
  }
  void fail(const char* reason){state_=State::Fault;reason_=reason;}
  State state_=State::New;const char* reason_="NEW";
  uint64_t started_us_=0,last_finished_us_=0,sent_us_=0;
  unsigned count_=0,writes_=0;
  ShoulderPreloadPose before_[3],prewrite_,after_[3];
};
}
