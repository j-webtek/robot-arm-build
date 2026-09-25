// One exact synchronized measured T1 -> P1 relief. One boot permits one write attempt;
// there is no retry, return, or continuation to another pose.
#pragma once
#include "large_pose_relief_policy.h"
#include <cstddef>
#include <cstdint>
#include <cstring>
namespace rocell_diag {
class LargePoseReliefOwner {
 public:
  enum class State { New, CapturingStart, Prewrite, CapturingEndpoint,
                     AwaitExport, Complete, Fault };
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
       state_==State::AwaitExport)return;
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
      if(!LargePoseReliefPolicy::source(before_,clock.now_us())){
        fail("SOURCE_POSE_REJECTED");return;
      }
      if(!evidence("LARGE_POSE_P1_INTENT",pose)){fail("EVIDENCE_FAILED");return;}
      state_=State::Prewrite;reason_="PREWRITE";return;
    }
    if(state_==State::Prewrite){
      if(!LargePoseReliefPolicy::unchanged_source(pose,before_[2])||
         !LargePoseReliefPolicy::source(before_,clock.now_us())){
        fail("PREWRITE_CHANGED");return;
      }
      if(!evidence("PREWRITE",pose)||!admitted()){
        fail("EVIDENCE_OR_ADMISSION_FAILED");return;
      }
      prewrite_=pose;sent_us_=clock.now_us();
      if(sent_us_<pose.finished_us||sent_us_-pose.finished_us>100000){
        fail("PREWRITE_EXPIRED");return;
      }
      ++writes_;
      if(!write(uint8_t(14),uint8_t(15),uint16_t(2842),
                uint16_t(1719),uint16_t(20),uint8_t(1))){
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
    if(!LargePoseReliefPolicy::bounded_endpoint_sample(before_[2],pose)){
      fail("ENDPOINT_OUT_OF_BOUNDS");return;
    }
    if(count_<3)after_[count_++]=pose;
    else {after_[0]=after_[1];after_[1]=after_[2];after_[2]=pose;}
    if(count_<3||!LargePoseReliefPolicy::endpoint(before_,after_,sent_us_,clock.now_us()))return;
    state_=State::AwaitExport;reason_="AWAITING_DURABLE_EXPORT";
  }
  bool mark_export_verified(bool verified){
    if(state_!=State::AwaitExport||!verified)return false;
    state_=State::Complete;reason_="LARGE_POSE_P1_RECORDED";return true;
  }
  State state()const{return state_;}const char* reason()const{return reason_;}
  unsigned writes()const{return writes_;}
  size_t copy_result(const uint8_t (&boot)[16],uint8_t* out,size_t capacity)const{
    constexpr size_t required=10+16+4+8+1+7*(16+7*20);
    if(state_!=State::AwaitExport||writes_!=1||!out||capacity<required)return 0;
    size_t size=0;auto put=[&](uint64_t value,unsigned width){
      for(int n=int(width)-1;n>=0;--n)out[size++]=uint8_t(value>>(n*8));};
    const char domain[]="RCRELIEF01";
    for(size_t i=0;i<sizeof(domain)-1;++i)put(uint8_t(domain[i]),1);
    for(auto byte:boot)put(byte,1);
    put(2842,2);put(1719,2);put(sent_us_,8);put(writes_,1);
    auto retained=[&](const ShoulderPreloadPose& sample){
      put(sample.started_us,8);put(sample.finished_us,8);
      for(int i=0;i<7;++i){put(sample.position[i],2);put(sample.goal[i],2);
        put(sample.torque[i],1);for(auto byte:sample.feedback[i])put(byte,1);}};
    for(const auto& sample:before_)retained(sample);retained(prewrite_);
    for(const auto& sample:after_)retained(sample);
    return size==required?size:0;
  }
 private:
  void fail(const char* reason){state_=State::Fault;reason_=reason;}
  State state_=State::New;const char* reason_="NEW";
  uint64_t started_us_=0,last_finished_us_=0,sent_us_=0;
  unsigned count_=0,writes_=0;
  ShoulderPreloadPose before_[3],prewrite_,after_[3];
};
}

