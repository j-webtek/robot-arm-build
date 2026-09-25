// Actual read/admission/session composition. Instantiate in owner/static storage,
// not a small HTTP callback stack. No route, provisioning or startup side effects.
#pragma once
#include "start_plan_structure.h"
#include "whole_arm_baseline_json.h"
#include "fresh_elbow_baseline.h"
#include "received_session.h"
namespace rocell_diag {
inline bool same_whole_arm_policy(const WholeArmBaselinePolicy& a,const WholeArmBaselinePolicy& b) {
  if(a.tracking_tolerance!=b.tracking_tolerance || a.maximum_pair_us!=b.maximum_pair_us ||
     a.maximum_scan_us!=b.maximum_scan_us || a.maximum_age_us!=b.maximum_age_us)return false;
  for(size_t i=0;i<7;++i)if(a.joints[i].minimum!=b.joints[i].minimum || a.joints[i].maximum!=b.joints[i].maximum)return false;
  return true;
}
template<class Library,class Clock,class Sink,class Converter>
class AdmittedSession {
 public:
  AdmittedSession(Library& library,Clock& clock,Sink& sink,Converter& converter,
      const WholeArmBaselinePolicy& policy,uint64_t expires,bool (*faulted)(void*),void* context)
      :library_(library),clock_(clock),sink_(sink),converter_(converter),whole_(policy),
       expires_(expires),faulted_(faulted),context_(context) {}
  bool check(const BoundStartRequest& request) {
    if(checked_)return false;checked_=true;
    if(!request.has_whole_arm || !same_whole_arm_policy(request.whole_arm,whole_.policy()) ||
       !faulted_ || faulted_(context_) || !request.samples || request.samples>8 ||
       !valid_identity(request.boot)||!valid_identity(request.command)||!request.payload_length||request.payload_length>256 ||
       !sink_.reserve(request.samples+7))return false;
    request_=request;
    const bool ok=whole_.check(library_,clock_);
    if(!whole_arm_baseline_json(whole_,request_.boot,request_.command,record_,sizeof(record_)) ||
       !sink_.publish("whole_arm",record_))return false;
    admitted_=ok && !faulted_(context_) && whole_.fresh(clock_.now_us());
    return admitted_;
  }
  bool start(const BoundStartRequest& request) {
    if(started_)return false;started_=true;
    if(!admitted_ || !same_request(request) || !ready(clock_.now_us()))return false;
    return session_.start(library_,clock_,sink_,*this,request_.boot,request_.command,
        request_.payload,request_.payload_length,request_.samples,request_.pair_us,request_.interval_us,
        WriteBoundaryGuard{&AdmittedSession::boundary,this});
  }
  bool admit_and_convert(double rad,uint16_t speed,uint8_t acceleration,uint16_t& target) {
    if(!started_ || !admitted_ || !ready(clock_.now_us()) ||
       !converter_.admit_and_convert(rad,speed,acceleration,target)||target!=request_.wire_count)return false;
    const bool ok=elbow_.check(library_,clock_,target,request_.maximum_delta,request_.settled_tolerance,
        request_.baseline_pair_us,request_.baseline_age_us);
    if(!elbow_.encode(request_.boot,request_.command,pair_,sizeof(pair_)))return false;
    const int n=snprintf(record_,sizeof(record_),
        "{\"schema\":\"rocell.elbow_baseline.v1\",\"accepted\":%s,\"reason\":\"%s\","
        "\"maximum_delta_counts\":%u,\"settled_tolerance_counts\":%u,"
        "\"maximum_pair_us\":%llu,\"maximum_age_us\":%llu,\"acquisition\":%s}",
        ok?"true":"false",elbow_.reason(),request_.maximum_delta,request_.settled_tolerance,
        (unsigned long long)request_.baseline_pair_us,(unsigned long long)request_.baseline_age_us,pair_);
    if(n<0 || static_cast<size_t>(n)>=sizeof(record_) || !sink_.publish("baseline",record_))return false;
    elbow_ready_=ok;return ok && ready(clock_.now_us());
  }
  bool sample(){
    if(!faulted_ || faulted_(context_)){session_.interference();return false;}
    return session_.sample(library_,clock_,sink_);
  }
  SessionState state() const{return session_.state();}
  const char* reason() const{return session_.reason();}
 private:
  bool same_request(const BoundStartRequest& r) const {
    return r.has_whole_arm && same_whole_arm_policy(r.whole_arm,request_.whole_arm) &&
      r.payload_length==request_.payload_length && !memcmp(r.payload,request_.payload,request_.payload_length) &&
      !strcmp(r.boot,request_.boot)&&!strcmp(r.command,request_.command)&&r.wire_count==request_.wire_count&&
      r.desired_count==request_.desired_count&&r.samples==request_.samples&&r.interval_us==request_.interval_us&&
      r.pair_us==request_.pair_us&&r.baseline_pair_us==request_.baseline_pair_us&&
      r.baseline_age_us==request_.baseline_age_us&&r.maximum_delta==request_.maximum_delta&&
      r.settled_tolerance==request_.settled_tolerance;
  }
  bool ready(uint64_t now){return faulted_ && !faulted_(context_) && now<expires_ && whole_.fresh(now);}
  static bool boundary(void* context,uint64_t now){
    auto& self=*static_cast<AdmittedSession*>(context);
    return self.elbow_ready_ && self.ready(now) && now>=self.elbow_.finished_us() &&
        now-self.elbow_.finished_us()<=self.request_.baseline_age_us;
  }
  Library& library_;Clock& clock_;Sink& sink_;Converter& converter_;
  WholeArmBaseline whole_;FreshElbowBaseline elbow_;ReceivedSession session_;BoundStartRequest request_;
  uint64_t expires_;bool (*faulted_)(void*);void* context_;
  bool checked_=false,admitted_=false,started_=false,elbow_ready_=false;
  char pair_[1536]={},record_[2048]={};
};
}
