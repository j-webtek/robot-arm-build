// One owner, one attempt. No network registration, key provisioning, or direct
// servo access. Native adapters must supply reviewed admission and session start.
#pragma once
#include "start_envelope.h"
#include "start_plan_structure.h"
namespace rocell_diag {
class AuthorizedStart {
 public:
  AuthorizedStart(const uint8_t (&key)[32],const uint8_t (&boot)[16],const uint8_t (&nonce)[32],
      uint64_t issued,uint64_t expires,const char* conversion,const WholeArmBaselinePolicy* approved=nullptr)
      :gate_(key,boot,nonce,issued,expires),expires_(expires) {
    static const char hex[]="0123456789abcdef";
    for(size_t i=0;i<16;++i){boot_[2*i]=hex[boot[i]>>4];boot_[2*i+1]=hex[boot[i]&15];}
    if(valid_identity(conversion))memcpy(conversion_,conversion,strlen(conversion)+1);
    if(approved){whole_policy_=*approved;has_whole_policy_=true;}
  }
  template<class Clock,class Crypto,class Converter,class Sink,class Admission,class Starter>
  bool start(const uint8_t* token,size_t length,Clock& clock,Crypto& crypto,Converter& converter,
             Sink& sink,Admission& admission,Starter& starter) {
    if(attempted_)return false;attempted_=true;
    const uint64_t begin=clock.now_us();AuthenticatedPlanView view;
    if(!gate_.consume(token,length,begin,crypto,view))return fail("AUTHENTICATION_REJECTED");
    if(!parser_.parse(reinterpret_cast<const char*>(view.bytes),view.length,boot_,conversion_,has_whole_policy_?&whole_policy_:nullptr) ||
       !parser_.bind_payload(crypto,converter)||!parser_.copy_bound_request(request_))return fail("PLAN_REJECTED");
    // Seven records: authorization plus receipt/baseline/conversion/hook/write/
    // dispatch. Limit pairs to nine in the current 16-slot store.
    const size_t boundary_records=request_.has_whole_arm?8:7;
    if(request_.samples>16-boundary_records || !sink.reserve(request_.samples+boundary_records))return fail("EVIDENCE_FAILURE");
    uint8_t digest[32]={};char hash[65]={};static const char hex[]="0123456789abcdef";
    if(!crypto.sha256(view.bytes,view.length,digest))return fail("HASH_FAILURE");
    for(size_t i=0;i<32;++i){hash[2*i]=hex[digest[i]>>4];hash[2*i+1]=hex[digest[i]&15];}
    const int n=snprintf(record_,sizeof(record_),
        "{\"schema\":\"rocell.start_authorization.v1\",\"boot_id\":\"%s\",\"command_id\":\"%s\","
        "\"session_plan_sha256\":\"%s\",\"received_us\":%llu,\"expires_us\":%llu,"
        "\"authentication_verified\":true,\"phase\":\"BEFORE_ADMISSION\",\"dispatch_attempted\":false}",
        boot_,request_.command,hash,(unsigned long long)begin,(unsigned long long)expires_);
    if(n<0 || static_cast<size_t>(n)>=sizeof(record_) || !sink.publish("authorization",record_))return fail("EVIDENCE_FAILURE");
    // Must check fresh whole-arm state plus controller-owned workspace bounds;
    // request limits and an HMAC are not clearance. Admission must not dispatch.
    if(!admission.check(request_))return fail("ADMISSION_REJECTED");
    const uint64_t now=clock.now_us();
    if(now<begin || now>=expires_)return fail("EXPIRED_BEFORE_START");
    if(!starter.start(request_))return fail("START_NOT_VERIFIED");
    reason_="STARTED";return true;
  }
  const char* reason() const{return reason_;}
 private:
  bool fail(const char* reason){reason_=reason;return false;}
  StartEnvelopeGate gate_;uint64_t expires_;bool attempted_=false;
  const char* reason_="NOT_STARTED";char boot_[33]={},conversion_[129]={},record_[768]={};
  StartPlanStructure parser_;BoundStartRequest request_;
  bool has_whole_policy_=false;WholeArmBaselinePolicy whole_policy_={};
};
}
