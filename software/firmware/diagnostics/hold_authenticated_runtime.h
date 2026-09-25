// Integrated finite runtime, not an installed route or physical bus mutex.
// Outer firmware must exclusively route the bus and supply a fail-closed healthy
// predicate covering physical admission/interference. No resetting or resending.
#pragma once
#include "hold_plan_admission.h"
#include "hold_evidence_publisher.h"
#include "verified_hold_handoff.h"
namespace rocell_diag {
template<class Library,class Clock,class Sink,class Crypto,bool Recovery=false,uint8_t RecoveryLimit=5>
class HoldAuthenticatedRuntime {
  static_assert(RecoveryLimit==5||(Recovery&&RecoveryLimit==6),"Unreviewed recovery profile");
 public:
  HoldAuthenticatedRuntime(Library& bus,Clock& clock,Sink& sink,Crypto& crypto,
      const uint8_t (&key)[32],const uint8_t (&boot)[16],const uint8_t (&nonce)[32],
      uint64_t issued,uint64_t expires,const HoldInitializationPolicy& policy,
      const char* command,bool (*healthy)(void*),void* context)
      :bus_(bus),clock_(clock),sink_(sink),crypto_(crypto),admission_(key,boot,nonce,issued,expires),
       owner_(make_owner(policy,this)),policy_(policy),
       issued_(issued),expires_(expires),healthy_(healthy),context_(context),linked_(*this){
    const char* hex="0123456789abcdef";
    for(size_t i=0;i<16;++i){boot_[2*i]=hex[boot[i]>>4];boot_[2*i+1]=hex[boot[i]&15];}
    if(valid_identity(command))memcpy(command_,command,strlen(command)+1);
  }
  bool start(const uint8_t* token,size_t length){
    if(attempted_)return false;attempted_=true;
    if(!healthy_now()||!admission_.consume(token,length,clock_.now_us(),crypto_,policy_,command_,Recovery,RecoveryLimit)){
      stopped_=true;reason_="HOLD_ADMISSION_REJECTED";return false;
    }
    // Authorisation + maximum 11 publisher records, with hash envelope overhead.
    if(!sink_.reserve(12)||!publisher_.begin(linked_,boot_,command_))return stop("HOLD_RESERVATION_FAILED");
    JsonDocument doc;doc["schema"]="rocell.hold_authorization.v1";
    doc["boot_id"]=boot_;doc["command_id"]=command_;doc["authentication_verified"]=true;
    doc["received_us"]=last_time_;
    if(!(Recovery?recovery_policy_json(policy_,buffer_,sizeof(buffer_),RecoveryLimit):
                  hold_policy_json(policy_,buffer_,sizeof(buffer_))))return stop("HOLD_POLICY_ENCODING_FAILED");
    JsonDocument p;if(deserializeJson(p,buffer_))return stop("HOLD_POLICY_ENCODING_FAILED");
    doc["policy"].set(p.as<JsonVariantConst>());
    if(!hold_json_finish(doc,buffer_,sizeof(buffer_))||!linked_.publish("hold_auth",buffer_))
      return stop("HOLD_AUTH_EXPORT_FAILED");
    active_=true;reason_="HOLD_ADMITTED";return true;
  }
  void poll(){
    if(!active_||stopped_)return;
    if(!healthy_now())owner_.interference();
    publisher_.poll(owner_,bus_,clock_,linked_);
    if(publisher_.faulted())stop("HOLD_EXPORT_FAILED");
    else if(owner_.phase()==HoldPhase::Fault||owner_.phase()==HoldPhase::Captured){
      active_=false;stopped_=true;reason_=owner_.reason();
    }
  }
  const char* reason()const{return reason_;}
  void interference(){
    if(stopped_)return;
    owner_.interference();active_=false;stopped_=true;reason_="HOLD_EXTERNAL_INTERFERENCE";
  }
  const HoldInitializationOwner& owner()const{return owner_;}
  bool take_handoff(VerifiedHoldHandoff& out){
    // Recovery is not ordinary pair admission. Host review/export must precede
    // a separately admitted experiment; do not hand off automatically.
    if(Recovery)return false;
    if(handoff_attempted_)return false;handoff_attempted_=true;
    if(owner_.phase()!=HoldPhase::Captured||publisher_.faulted()||sink_.faulted()||
       !admission_.accepted()||!healthy_||!healthy_(context_))return false;
    return out.seal(*owner_.scan(owner_.scan_count()-1),boot_,admission_.plan_hash(),admission_.policy_hash());
  }
 private:
  static HoldInitializationOwner make_owner(const HoldInitializationPolicy& p,void* context){
    if constexpr(Recovery&&RecoveryLimit==6)
      return HoldInitializationOwner(p,SixCountRecoveryAdmission{},&boundary,context);
    return Recovery?HoldInitializationOwner(p,SupportedRecoveryAdmission{},&boundary,context):
                    HoldInitializationOwner(p,&boundary,context);
  }
  struct LinkedSink {
    explicit LinkedSink(HoldAuthenticatedRuntime& runtime):runtime(runtime){}
    HoldAuthenticatedRuntime& runtime;
    bool reserve(size_t count){return count==11;}
    bool faulted()const{return runtime.sink_.faulted();}
    bool publish(const char* kind,const char* json){
      JsonDocument doc;if(deserializeJson(doc,json))return false;
      if(Recovery){
        const char* schema=doc["schema"];
        if(!schema)return false;
        if(!strcmp(schema,"rocell.hold_authorization.v1"))doc["schema"]="rocell.supported_recovery_authorization.v1";
        else if(!strcmp(schema,"rocell.hold_snapshot.v1"))doc["schema"]="rocell.supported_recovery_snapshot.v1";
        else if(!strcmp(schema,"rocell.hold_action.v1"))doc["schema"]="rocell.supported_recovery_action.v1";
        else if(!strcmp(schema,"rocell.hold_terminal.v1"))doc["schema"]="rocell.supported_recovery_terminal.v1";
        else return false;
        if constexpr(RecoveryLimit==6){
          const char* translated=doc["schema"];
          if(!strcmp(translated,"rocell.supported_recovery_authorization.v1"))doc["schema"]="rocell.six_count_recovery_authorization.v1";
          else if(!strcmp(translated,"rocell.supported_recovery_snapshot.v1"))doc["schema"]="rocell.six_count_recovery_snapshot.v1";
          else if(!strcmp(translated,"rocell.supported_recovery_action.v1"))doc["schema"]="rocell.six_count_recovery_action.v1";
          else doc["schema"]="rocell.six_count_recovery_terminal.v1";
        }
      }
      doc["plan_sha256"]=runtime.admission_.plan_hash();
      doc["policy_sha256"]=runtime.admission_.policy_hash();
      if(!hold_json_finish(doc,runtime.linked_buffer_,sizeof(runtime.linked_buffer_)))return false;
      return runtime.sink_.publish(kind,runtime.linked_buffer_);
    }
  };
  bool healthy_now(){
    const uint64_t now=clock_.now_us();
    if(now<issued_||now>=expires_||now<last_time_||!healthy_||!healthy_(context_)||sink_.faulted())return false;
    last_time_=now;return true;
  }
  static bool boundary(void* self){return static_cast<HoldAuthenticatedRuntime*>(self)->healthy_now();}
  bool stop(const char* reason){stopped_=true;active_=false;reason_=reason;owner_.export_failed();return false;}
  Library& bus_;Clock& clock_;Sink& sink_;Crypto& crypto_;
  HoldPlanAdmission admission_;HoldInitializationOwner owner_;HoldInitializationPolicy policy_;
  uint64_t issued_,expires_,last_time_=0;bool (*healthy_)(void*);void* context_;
  LinkedSink linked_;HoldEvidencePublisher publisher_;
  bool attempted_=false,active_=false,stopped_=false,handoff_attempted_=false;
  char boot_[33]={},command_[129]={},buffer_[2048]={},linked_buffer_[4608]={};
  const char* reason_="NOT_STARTED";
};
}
