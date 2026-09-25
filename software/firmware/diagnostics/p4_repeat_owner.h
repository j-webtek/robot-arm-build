// Fixed finite campaign core. Integration with authenticated routes is still required.
#pragma once
#include "p4_repeat_policy.h"
#include <cstddef>
#include <cstdint>
#include <cstring>
namespace rocell_diag {
class P4RepeatOwner {
 public:
  enum class State { New, CapturingStart, Prewrite, CapturingEndpoint,
                     AwaitExport, ReadyNext, Complete, Fault };
  template<class Reserve,class Clock> bool begin(Reserve& reserve,Clock& clock){
    if(state_!=State::New)return false;
    state_=State::Fault;reason_="RESERVATION_FAILED";
    if(!reserve())return false;
    started_us_=clock.now_us();if(!started_us_)return false;
    state_=State::CapturingStart;reason_="CAPTURING_START";return true;
  }
  template<class Acquire,class Write,class Clock,class Evidence,class Admission>
  void poll(Acquire& acquire,Write& write,Clock& clock,Evidence& evidence,
            Admission& admitted){
    if(state_==State::New||state_==State::Complete||state_==State::Fault||
       state_==State::AwaitExport||state_==State::ReadyNext)return;
    const auto now=clock.now_us();
    if(now<started_us_||!admitted()){fail("CLOCK_OR_ADMISSION_LOST");return;}
    if(now-started_us_>10000000){fail("DEADLINE_EXPIRED");return;}
    if(last_finished_us_&&now<last_finished_us_){fail("CLOCK_REVERSED");return;}
    if(last_finished_us_&&now-last_finished_us_<100000)return;
    ShoulderPreloadPose pose;
    if(!acquire(pose)||!ShoulderCharacterizationPolicy::valid(pose)||
       pose.started_us<=last_finished_us_||pose.finished_us>clock.now_us()||
       clock.now_us()-pose.finished_us>100000){fail("FRESH_FEEDBACK_FAILED");return;}
    last_finished_us_=pose.finished_us;
    if(state_==State::CapturingStart){
      before_[count_++]=pose;
      if(!evidence("START_SAMPLE",pose)){fail("EVIDENCE_FAILED");return;}
      if(count_<3)return;
      if(!policy_.source(before_,clock.now_us())){
        fail("SOURCE_POSE_REJECTED");return;
      }
      if(!evidence("P4_REPEAT_LEG_INTENT",pose)){fail("EVIDENCE_FAILED");return;}
      state_=State::Prewrite;reason_="PREWRITE";return;
    }
    if(state_==State::Prewrite){
      if(!policy_.unchanged_source(pose,before_[2])||
         !policy_.source(before_,clock.now_us())){
        fail("PREWRITE_CHANGED");return;
      }
      if(!evidence("PREWRITE",pose)||!admitted()){
        fail("EVIDENCE_OR_ADMISSION_FAILED");return;
      }
      prewrite_=pose;sent_us_=clock.now_us();
      if(sent_us_<pose.finished_us||sent_us_-pose.finished_us>100000){
        fail("PREWRITE_EXPIRED");return;
      }
      ++writes_;++total_writes_;
      if(!write(uint8_t(15),uint16_t(policy_.target_goals[4]),uint16_t(20),uint8_t(1))){
        fail("WRITE_DELIVERY_UNCERTAIN");return;
      }
      if(!evidence("WRITE_ATTEMPTED",pose)){
        fail("EVIDENCE_FAILED_AFTER_WRITE");return;
      }
      count_=0;state_=State::CapturingEndpoint;reason_="CAPTURING_ENDPOINT";return;
    }
    if(!evidence("ENDPOINT_SAMPLE",pose)){
      fail("EVIDENCE_FAILED_AFTER_WRITE");return;
    }
    if(!policy_.bounded_endpoint_sample(before_[2],pose)){
      fail("ENDPOINT_OUT_OF_BOUNDS");return;
    }
    if(count_<3)after_[count_++]=pose;
    else {after_[0]=after_[1];after_[1]=after_[2];after_[2]=pose;}
    if(count_<3||!policy_.endpoint(before_,after_,sent_us_,clock.now_us()))return;
    state_=State::AwaitExport;reason_="AWAITING_DURABLE_EXPORT";
  }
  template<class Clock>
  bool acknowledge(unsigned leg,const uint8_t* digest,Clock& clock){
    if(state_!=State::AwaitExport||!sealed_||!digest||leg!=leg_+1||
       std::memcmp(digest,record_digest_,32)!=0)return false;
    const auto now=clock.now_us();
    if(now<last_finished_us_||now-last_finished_us_>30000000){
      fail("EXPORT_RECEIPT_EXPIRED");return false;
    }
    if(leg_==11){state_=State::Complete;reason_="P4_REPEAT_COMPLETE";return true;}
    ++leg_;policy_.advance(after_[2],leg_);
    count_=0;writes_=0;sealed_=false;started_us_=now;
    state_=State::ReadyNext;reason_="READY_NEXT";return true;
  }
  template<class Clock> bool begin_next(unsigned leg,Clock& clock){
    if(state_!=State::ReadyNext||leg!=leg_+1)return false;
    const auto now=clock.now_us();
    if(now<started_us_||now-started_us_>30000000){fail("NEXT_ADMISSION_EXPIRED");return false;}
    started_us_=now;state_=State::CapturingStart;reason_="CAPTURING_START";return true;
  }
  template<class Hash>
  size_t seal_record(const uint8_t (&boot)[16],uint8_t* out,size_t capacity,Hash& hash){
    const size_t size=copy_result(boot,out,capacity);
    if(!size)return 0;
    uint8_t digest[32];
    if(!hash(out,size,digest)){fail("RECORD_HASH_FAILED");return 0;}
    if(sealed_&&std::memcmp(digest,record_digest_,32)!=0){fail("RECORD_CHANGED");return 0;}
    std::memcpy(record_digest_,digest,32);sealed_=true;return size;
  }
  unsigned leg()const{return leg_+1;}
  unsigned total_writes()const{return total_writes_;}
  State state()const{return state_;}const char* reason()const{return reason_;}
  unsigned writes()const{return writes_;}
  size_t copy_result(const uint8_t (&boot)[16],uint8_t* out,size_t capacity)const{
    constexpr size_t required=10+16+1+2+8+1+7*(16+7*20);
    if(state_!=State::AwaitExport||writes_!=1||!out||capacity<required)return 0;
    size_t size=0;auto put=[&](uint64_t value,unsigned width){
      for(int n=int(width)-1;n>=0;--n)out[size++]=uint8_t(value>>(n*8));};
    const char domain[]="RCWRREP001";
    for(size_t i=0;i<sizeof(domain)-1;++i)put(uint8_t(domain[i]),1);
    for(auto byte:boot)put(byte,1);
    put(leg_+1,1);put(policy_.target_goals[4],2);put(sent_us_,8);put(writes_,1);
    auto retained=[&](const ShoulderPreloadPose& sample){
      put(sample.started_us,8);put(sample.finished_us,8);
      for(int i=0;i<7;++i){put(sample.position[i],2);put(sample.goal[i],2);
        put(sample.torque[i],1);for(auto byte:sample.feedback[i])put(byte,1);}};
    for(const auto& sample:before_)retained(sample);retained(prewrite_);
    for(const auto& sample:after_)retained(sample);
    return size==required?size:0;
  }
 private:
  P4RepeatPolicy policy_;
  unsigned leg_=0,total_writes_=0;
  bool sealed_=false;uint8_t record_digest_[32]={};
  void fail(const char* reason){state_=State::Fault;reason_=reason;}
  State state_=State::New;const char* reason_="NEW";
  uint64_t started_us_=0,last_finished_us_=0,sent_us_=0;
  unsigned count_=0,writes_=0;
  ShoulderPreloadPose before_[3],prewrite_,after_[3];
};
}
