// One bounded park-step owner. Offline until a reviewed authenticated route is
// wired to it. Each boot permits one transmission attempt, including uncertain
// delivery; receipt of exported evidence cannot start another step.
#pragma once
#include "park_step_policy.h"
#include <cstddef>
#include <cstdint>
#include <cstring>
namespace rocell_diag {
class ParkStepOwner {
 public:
  enum class State { New, CapturingStart, Prewrite, CapturingEndpoint,
                     AwaitExport, Complete, Fault };

  template<class Reserve,class Clock>
  bool begin(uint16_t target12,uint16_t target13,Reserve& reserve,Clock& clock){
    if(state_!=State::New)return false;
    state_=State::Fault;reason_="RESERVATION_FAILED";
    // Bounds are checked again against fresh readings before the write.
    if(target12>4095||target13>4095||!reserve())return false;
    started_us_=clock.now_us();
    if(!started_us_)return false;
    target12_=target12;target13_=target13;
    state_=State::CapturingStart;reason_="CAPTURING_START";return true;
  }

  template<class Acquire,class Write,class Clock,class Evidence,class Admission>
  void poll(Acquire& acquire,Write& write,Clock& clock,Evidence& evidence,
            Admission& admitted){
    if(state_==State::New||state_==State::Complete||state_==State::Fault||
       state_==State::AwaitExport)return;
    const auto now=clock.now_us();
    if(now<started_us_||!admitted()){fail("CLOCK_OR_ADMISSION_LOST");return;}
    if(now-started_us_>8000000){
      fail(state_==State::CapturingEndpoint&&count_==3?
           "ENDPOINT_TIMEOUT":"DEADLINE_EXPIRED");return;
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
      if(!ParkStepPolicy::start(before_,clock.now_us(),target12_,target13_)){
        fail("START_GATE_FAILED");return;
      }
      if(!evidence("PARK_STEP_INTENT",pose)){fail("EVIDENCE_FAILED");return;}
      state_=State::Prewrite;reason_="PREWRITE";return;
    }
    if(state_==State::Prewrite){
      if(!same_start(pose,before_[2])||
         !ParkStepPolicy::start(before_,clock.now_us(),target12_,target13_)){
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
      ++writes_;
      if(!write(uint8_t(12),uint8_t(13),target12_,target13_,
                uint16_t(20),uint8_t(1))){
        fail("WRITE_DELIVERY_UNCERTAIN");return;
      }
      if(!evidence("WRITE_ATTEMPTED",pose)){
        fail("EVIDENCE_FAILED_AFTER_WRITE");return;
      }
      count_=0;state_=State::CapturingEndpoint;
      reason_="CAPTURING_ENDPOINT";return;
    }
    if(!evidence("ENDPOINT_SAMPLE",pose)){
      fail("EVIDENCE_FAILED_AFTER_WRITE");return;
    }
    if(!ParkStepPolicy::bounded_endpoint_sample(before_[2],pose,target12_,target13_)){
      fail("ENDPOINT_OUT_OF_BOUNDS");return;
    }
    // Retain only the most recent three observations. Motion is allowed to
    // settle, but never beyond the fixed eight-second owner deadline.
    if(count_<3)after_[count_++]=pose;
    else {after_[0]=after_[1];after_[1]=after_[2];after_[2]=pose;}
    if(count_<3||!ParkStepPolicy::endpoint(before_,after_,sent_us_,clock.now_us(),
                                          target12_,target13_))return;
    state_=State::AwaitExport;reason_="AWAITING_DURABLE_EXPORT";
  }

  bool mark_export_verified(bool exact_retained_export_verified){
    if(state_!=State::AwaitExport||!exact_retained_export_verified)return false;
    state_=State::Complete;reason_="PARK_STEP_RECORDED";return true;
  }
  State state()const{return state_;}
  const char* reason()const{return reason_;}
  unsigned writes()const{return writes_;}
  uint16_t target12()const{return target12_;}
  uint16_t target13()const{return target13_;}

  // 10-byte domain, 16-byte boot, two 16-bit targets, 64-bit send time,
  // one write count, and seven complete seven-servo raw-feedback poses.
  size_t copy_result(const uint8_t (&boot)[16],uint8_t* out,size_t capacity)const{
    constexpr size_t required=10+16+4+8+1+7*(16+7*20);
    const bool settled=state_==State::AwaitExport;
    const bool timed_out=state_==State::Fault&&
                         strcmp(reason_,"ENDPOINT_TIMEOUT")==0&&count_==3;
    if((!settled&&!timed_out)||writes_!=1||!out||capacity<required)return 0;
    size_t size=0;
    auto put=[&](uint64_t value,unsigned width){
      for(int n=int(width)-1;n>=0;--n)out[size++]=uint8_t(value>>(n*8));
    };
    const char domain[]="RCPARK0001";
    for(size_t i=0;i<sizeof(domain)-1;++i)put(uint8_t(domain[i]),1);
    for(auto byte:boot)put(byte,1);
    put(target12_,2);put(target13_,2);put(sent_us_,8);put(writes_,1);
    auto retained_pose=[&](const ShoulderPreloadPose& sample){
      put(sample.started_us,8);put(sample.finished_us,8);
      for(int i=0;i<7;++i){
        put(sample.position[i],2);put(sample.goal[i],2);put(sample.torque[i],1);
        for(auto byte:sample.feedback[i])put(byte,1);
      }
    };
    for(const auto& sample:before_)retained_pose(sample);
    retained_pose(prewrite_);
    for(const auto& sample:after_)retained_pose(sample);
    return size==required?size:0;
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
  void fail(const char* reason){state_=State::Fault;reason_=reason;}
  State state_=State::New;const char* reason_="NEW";
  uint64_t started_us_=0,last_finished_us_=0,sent_us_=0;
  uint16_t target12_=0,target13_=0;
  unsigned count_=0,writes_=0;
  ShoulderPreloadPose before_[3],prewrite_,after_[3];
};
}
