// Separate asynchronous startup owner. Not exposed by the installed firmware.
// Local policy, no-write converter, exclusive bus ownership and external fault
// predicate are required. Normal authenticated owner and tracking stay unchanged.
#pragma once
#include "startup_plan_structure.h"
#include "startup_precommand_evidence.h"
#include "start_envelope.h"
#include "received_session.h"
namespace rocell_diag {
enum class StartupOwnerState { Idle, Preparing, Sampling, Captured, Fault };
template<class Library,class Clock,class Sink,class Converter,class Crypto,
         class Parser=StartupPlanStructure,class Envelope=StartEnvelopeGate>
class StartupAuthenticatedOwner {
 public:
  StartupAuthenticatedOwner(Library& library,Clock& clock,Sink& sink,Converter& converter,Crypto& crypto,
      const uint8_t (&key)[32],const uint8_t (&boot)[16],const uint8_t (&nonce)[32],
      uint64_t issued,uint64_t expires,const char* conversion,const char* policy_id,
      const StartupPositionPolicy& startup,uint8_t mode,const WholeArmBaselinePolicy& normal,
      bool (*fault)(void*),void* context)
      :library_(library),clock_(clock),sink_(sink),converter_(converter),crypto_(crypto),
       envelope_(key,boot,nonce,issued,expires),evidence_(library,clock,sink,startup,mode),
       startup_(startup),normal_(normal),mode_(mode),issued_(issued),expires_(expires),fault_(fault),context_(context){
    static const char hex[]="0123456789abcdef";
    for(size_t i=0;i<16;++i){boot_[2*i]=hex[boot[i]>>4];boot_[2*i+1]=hex[boot[i]&15];}
    if(valid_identity(conversion)&&valid_identity(policy_id)){
      memcpy(conversion_,conversion,strlen(conversion)+1);memcpy(policy_id_,policy_id,strlen(policy_id)+1);
    }else fail("STARTUP_IDENTITY_INVALID");
  }
  bool start(const uint8_t* token,size_t length){
    if(attempted_||state_!=StartupOwnerState::Idle)return false;attempted_=true;
    const uint64_t now=clock_.now_us();AuthenticatedPlanView view;
    if(!healthy(now))return fail("STARTUP_OWNER_NOT_READY");
    if(!envelope_.consume(token,length,now,crypto_,view))return fail("STARTUP_AUTHENTICATION_REJECTED");
    if(!parser_.parse(reinterpret_cast<const char*>(view.bytes),view.length,boot_,conversion_,policy_id_,startup_,mode_,normal_)||
       !parser_.bind_payload(crypto_,converter_)||!parser_.copy_bound_request(request_)||request_.samples>6||!request_.samples)
      return fail("STARTUP_PLAN_REJECTED");
    // 1 authorization + 3 startup records + receipt + 4 write records + samples.
    if(!sink_.reserve(9+request_.samples))return fail("STARTUP_EVIDENCE_FAILURE");
    uint8_t digest[32]={};char hash[65]={};static const char hex[]="0123456789abcdef";
    if(!crypto_.sha256(view.bytes,view.length,digest))return fail("STARTUP_HASH_FAILURE");
    for(size_t i=0;i<32;++i){hash[2*i]=hex[digest[i]>>4];hash[2*i+1]=hex[digest[i]&15];}
    const int n=snprintf(record_,sizeof(record_),
      "{\"schema\":\"rocell.startup_authorization.v1\",\"boot_id\":\"%s\",\"command_id\":\"%s\","
      "\"startup_plan_sha256\":\"%s\",\"policy_id\":\"%s\",\"authentication_verified\":true,\"received_us\":%llu}",
      boot_,request_.command,hash,policy_id_,static_cast<unsigned long long>(now));
    if(n<0||static_cast<size_t>(n)>=sizeof(record_)||!sink_.publish("startup_auth",record_)||
       !evidence_.begin(request_.boot,request_.command,request_.wire_count,request_.maximum_delta))
      return fail("STARTUP_EVIDENCE_FAILURE");
    state_=StartupOwnerState::Preparing;return true;
  }
  void poll(){
    if(state_!=StartupOwnerState::Preparing&&state_!=StartupOwnerState::Sampling)return;
    if(!healthy(clock_.now_us())){fail("STARTUP_OWNER_NOT_READY");return;}
    if(state_==StartupOwnerState::Preparing){
      evidence_.poll();
      if(evidence_.state()==StartupEvidenceState::Fault){fail(evidence_.reason());return;}
      if(evidence_.state()!=StartupEvidenceState::Bound)return;
      if(!session_.start(library_,clock_,sink_,*this,request_.boot,request_.command,
          request_.payload,request_.payload_length,request_.samples,request_.pair_us,request_.interval_us,
          WriteBoundaryGuard{&StartupAuthenticatedOwner::boundary,this})){
        fail(session_.reason());return;
      }
      state_=StartupOwnerState::Sampling;return;
    }
    session_.sample(library_,clock_,sink_);
    if(session_.state()==SessionState::Fault)fail(session_.reason());
    else if(session_.state()==SessionState::Captured)state_=StartupOwnerState::Captured;
  }
  bool admit_and_convert(double rad,uint16_t speed,uint8_t acc,uint16_t& target){
    return state_==StartupOwnerState::Preparing && healthy(clock_.now_us()) &&
      converter_.admit_and_convert(rad,speed,acc,target)&&target==request_.wire_count&&
      evidence_.boundary(target,clock_.now_us());
  }
  void interference(){fail("STARTUP_INTERFERENCE");}
  void export_failed(){fail("STARTUP_EVIDENCE_FAILURE");}
  StartupOwnerState state()const{return state_;}
  const char* reason()const{return reason_;}
 private:
  bool healthy(uint64_t now){
    if(now<last_time_||now<issued_||now>=expires_||!fault_||fault_(context_)||sink_.faulted()||!library_.Level)return false;
    last_time_=now;return true;
  }
  static bool boundary(void* context,uint64_t now){
    auto& self=*static_cast<StartupAuthenticatedOwner*>(context);
    return self.healthy(now)&&self.evidence_.boundary(self.request_.wire_count,now);
  }
  bool fail(const char* reason){if(state_!=StartupOwnerState::Fault)reason_=reason;state_=StartupOwnerState::Fault;return false;}
  Library& library_;Clock& clock_;Sink& sink_;Converter& converter_;Crypto& crypto_;
  Envelope envelope_;Parser parser_;StartupPrecommandEvidence<Library,Clock,Sink> evidence_;
  StartupPositionPolicy startup_;WholeArmBaselinePolicy normal_;uint8_t mode_;
  uint64_t issued_,expires_,last_time_=0;bool (*fault_)(void*);void* context_;
  BoundStartRequest request_;ReceivedSession session_;
  char boot_[33]={},conversion_[129]={},policy_id_[129]={},record_[1024]={};
  bool attempted_=false;StartupOwnerState state_=StartupOwnerState::Idle;const char* reason_="NONE";
};
}
