// Offline one-use return owner. No route or hardware adapter is wired here.
#pragma once
#ifdef ROCELL_PARK_REANCHOR_POLICY_HEADER
#include ROCELL_PARK_REANCHOR_POLICY_HEADER
#else
#include "park_reanchor_policy.h"
#endif
#include <cstddef>
#include <cstdint>
#include <cstring>

namespace rocell_diag {
class ParkReanchorOwner {
 public:
  enum class State { New, CapturingStart, Prewrite, CapturingEndpoint,
                     AwaitExport, Complete, Fault };
  enum class RecordOutcome : uint8_t { Settled=1, Timeout=2, OutOfBounds=3,
    FeedbackFailed=4, EvidenceFailed=5, AdmissionLost=6, ClockFailed=7,
    WriteUncertain=8 };
  static constexpr size_t record_size=10+16+1+1+8+1+7*(16+7*20);

  template<class Reserve,class Clock>
  bool begin(Reserve& reserve,Clock& clock){
    if(state_!=State::New)return false;
    state_=State::Fault;reason_="RESERVATION_FAILED";
    if(!reserve())return false;
    started_us_=clock.now_us();
    if(!started_us_)return false;
    state_=State::CapturingStart;reason_="CAPTURING_START";return true;
  }

  template<class Acquire,class Write,class Clock,class Evidence,class Admission>
  void poll(Acquire& acquire,Write& write,Clock& clock,Evidence& evidence,
            Admission& admitted){
    if(state_==State::New||state_==State::Complete||state_==State::Fault||
       state_==State::AwaitExport)return;
    const uint64_t now=clock.now_us();
    if(now<started_us_||
       (last_finished_us_&&now<last_finished_us_)){
      fail("CLOCK_REVERSED",RecordOutcome::ClockFailed);return;
    }
    if(!admitted()){
      fail("ADMISSION_LOST",RecordOutcome::AdmissionLost);return;
    }
    if(now-started_us_>8000000){
      fail(state_==State::CapturingEndpoint?"ENDPOINT_TIMEOUT":"DEADLINE_EXPIRED",
           RecordOutcome::Timeout);return;
    }
    if(last_finished_us_&&now-last_finished_us_<100000)return;
    ShoulderPreloadPose pose{};
    if(!acquire(pose)||!ShoulderCharacterizationPolicy::valid(pose)||
       pose.started_us<=last_finished_us_||pose.finished_us>clock.now_us()||
       clock.now_us()-pose.finished_us>100000){
      fail("FRESH_FEEDBACK_FAILED",RecordOutcome::FeedbackFailed);return;
    }
    last_finished_us_=pose.finished_us;
    if(state_==State::CapturingStart){
      before_[count_++]=pose;
      if(!evidence("START_SAMPLE",pose)){
        fail("EVIDENCE_FAILED",RecordOutcome::EvidenceFailed);return;
      }
      if(count_<3)return;
      if(!ParkReanchorPolicy::start(before_,clock.now_us())){
        fail("START_GATE_FAILED",RecordOutcome::OutOfBounds);return;
      }
      if(!evidence("RETURN_INTENT",pose)){
        fail("EVIDENCE_FAILED",RecordOutcome::EvidenceFailed);return;
      }
      state_=State::Prewrite;reason_="PREWRITE";return;
    }
    if(state_==State::Prewrite){
      if(!same_start(pose,before_[2])||
         !ParkReanchorPolicy::start(before_,clock.now_us())){
        fail("PREWRITE_CHANGED",RecordOutcome::OutOfBounds);return;
      }
      if(!evidence("PREWRITE",pose)||!admitted()){
        fail("EVIDENCE_OR_ADMISSION_FAILED",RecordOutcome::EvidenceFailed);return;
      }
      prewrite_=pose;sent_us_=clock.now_us();
      if(sent_us_<pose.finished_us||sent_us_-pose.finished_us>100000){
        fail("PREWRITE_EXPIRED",RecordOutcome::ClockFailed);return;
      }
      count_=0;
      ++writes_; // An uncertain transmission still consumes the only attempt.
      if(!write(uint8_t(12),uint8_t(13),ParkReanchorPolicy::target12,
                ParkReanchorPolicy::target13,uint16_t(20),uint8_t(1))){
        fail("WRITE_DELIVERY_UNCERTAIN",RecordOutcome::WriteUncertain);return;
      }
      if(!evidence("WRITE_ATTEMPTED",pose)){
        fail("EVIDENCE_FAILED_AFTER_WRITE",RecordOutcome::EvidenceFailed);return;
      }
      state_=State::CapturingEndpoint;
      reason_="CAPTURING_ENDPOINT";return;
    }
    // Retain the latest three postwrite observations, including a rejected
    // sample. No retry or inverse command is issued on any fault.
    if(count_<3)after_[count_++]=pose;
    else {after_[0]=after_[1];after_[1]=after_[2];after_[2]=pose;}
    if(!evidence("ENDPOINT_SAMPLE",pose)){
      fail("EVIDENCE_FAILED_AFTER_WRITE",RecordOutcome::EvidenceFailed);return;
    }
    if(!ParkReanchorPolicy::bounded_sample(before_[2],pose)){
      fail("ENDPOINT_OUT_OF_BOUNDS",RecordOutcome::OutOfBounds);return;
    }
    if(count_<3||!ParkReanchorPolicy::endpoint(before_,after_,sent_us_,clock.now_us()))return;
    outcome_=RecordOutcome::Settled;
    state_=State::AwaitExport;reason_="AWAITING_DURABLE_EXPORT";
  }

  bool mark_export_verified(bool exact_retained_export_verified){
    if(state_!=State::AwaitExport||!exact_retained_export_verified)return false;
    state_=State::Complete;reason_="RETURN_RECORDED";return true;
  }
  State state()const{return state_;}
  const char* reason()const{return reason_;}
  unsigned writes()const{return writes_;}
  unsigned postwrite_samples()const{return count_;}

  // Domain, boot identity, outcome, postwrite sample count, send timestamp,
  // attempted writes, and seven complete raw poses. Unfilled slots are zero.
  // A fault record is evidence only and can never receive a success receipt.
  size_t copy_result(const uint8_t (&boot)[16],uint8_t* out,size_t capacity)const{
    if(writes_!=1||!(state_==State::AwaitExport||state_==State::Fault)||
       !out||capacity<record_size)return 0;
    size_t size=0;
    auto put=[&](uint64_t value,unsigned width){
      for(int n=int(width)-1;n>=0;--n)out[size++]=uint8_t(value>>(n*8));
    };
    const char domain[]="RCRTN00001";
    for(size_t i=0;i<10;++i)put(uint8_t(domain[i]),1);
    for(auto byte:boot)put(byte,1);
    put(uint8_t(outcome_),1);put(count_,1);put(sent_us_,8);put(writes_,1);
    auto retained=[&](const ShoulderPreloadPose& p){
      put(p.started_us,8);put(p.finished_us,8);
      for(int i=0;i<7;++i){
        put(p.position[i],2);put(p.goal[i],2);put(p.torque[i],1);
        for(auto byte:p.feedback[i])put(byte,1);
      }
    };
    for(const auto& p:before_)retained(p);
    retained(prewrite_);
    for(const auto& p:after_)retained(p);
    return size==record_size?size:0;
  }

 private:
  static bool same_start(const ShoulderPreloadPose& current,
                         const ShoulderPreloadPose& baseline){
    for(int i=0;i<7;++i)
      if(current.goal[i]!=baseline.goal[i]||current.torque[i]!=baseline.torque[i]||
         ShoulderCharacterizationPolicy::moving(current,i)||
         std::abs(int(current.position[i])-int(baseline.position[i]))>1||
         (current.feedback[i][0]|uint16_t(current.feedback[i][1])<<8)!=
             current.position[i])return false;
    return true;
  }
  void fail(const char* reason,RecordOutcome outcome){
    state_=State::Fault;reason_=reason;outcome_=outcome;
  }
  State state_=State::New;
  const char* reason_="NEW";
  RecordOutcome outcome_=RecordOutcome::FeedbackFailed;
  uint64_t started_us_=0,last_finished_us_=0,sent_us_=0;
  unsigned count_=0,writes_=0;
  ShoulderPreloadPose before_[3]{},prewrite_{},after_[3]{};
};
}
