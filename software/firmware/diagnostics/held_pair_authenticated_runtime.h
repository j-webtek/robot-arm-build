// Owns a finite authenticated pair and its evidence. Not installed or routed.
// Outer firmware supplies exclusive bus ownership, a same-boot verified hold,
// fresh challenges, reviewed local configuration, and its health predicate.
// Allocate the entire runtime off the control-task stack, with checked memory.
#pragma once
#include <memory>
#include "held_elbow_pair_owner.h"
#include "held_pair_plan_admission.h"
#include "held_pair_return_bridge.h"
#include "evidence_store.h"
#include "held_compact_evidence_store.h"
#include "verified_hold_handoff.h"
namespace rocell_diag {
template<class Bus,class Clock,class Crypto>
class HeldPairAuthenticatedRuntime {
 public:
  using Store=HeldCompactEvidenceStore<Crypto>;
  HeldPairAuthenticatedRuntime(Bus& bus,Clock& clock,Crypto& crypto,
      const HoldInitializationPolicy& policy,const char* boot,const char* hold_hash,
      const char* forward,const char* reverse,int offset,uint16_t tolerance,
      bool (*healthy)(void*),void* context=nullptr)
      :bus_(bus),clock_(clock),crypto_(crypto),policy_(policy),offset_(offset),tolerance_(tolerance),
       pair_(policy,offset,tolerance,healthy,context),healthy_(healthy),context_(context){
    configured_=copy(boot_,boot)&&copy(hold_hash_,hold_hash)&&
                copy(forward_,forward)&&copy(reverse_,reverse);
  }
  HeldPairAuthenticatedRuntime(const HeldPairAuthenticatedRuntime&)=delete;
  HeldPairAuthenticatedRuntime& operator=(const HeldPairAuthenticatedRuntime&)=delete;

  bool start(HeldPairPlanAdmission& gate,const uint8_t* token,size_t length,
             VerifiedHoldHandoff& held){
    if(attempted_)return false;attempted_=true;
    if(!configured_||!healthy_||!healthy_(context_)||strcmp(gate.boot_id(),boot_)||
       !gate.consume(token,length,clock_.now_us(),crypto_,policy_,hold_hash_,
                     forward_,reverse_,offset_,tolerance_))return stop("PAIR_START_REJECTED");
    const auto* endpoint=held.consume(boot_,hold_hash_,gate.policy_hash());
    if(!endpoint||!pair_.start(*endpoint))return stop("PAIR_HOLD_HANDOFF_FAILED");
    copy(session_hash_,gate.session_hash());copy(policy_hash_,gate.policy_hash());
    if(!derive_leg_plan(forward_,int(pair_.original_anchor())+offset_,forward_plan_,forward_hash_)||
       !store_.bind(*pair_.leg(),crypto_,boot_,forward_)||
       !publisher_.begin(store_,boot_,forward_))return stop("PAIR_FORWARD_PREPARATION_FAILED");
    started_=true;return true;
  }
  void poll(){
    if(!started_||stopped_)return;
    Driver driver{*this};pair_.poll(driver);
  }
  bool admit_return(HeldReturnAdmission& gate,const uint8_t* token,size_t length){
    if(!started_||stopped_||pair_.phase()!=HeldPairPhase::AwaitingExport)return false;
    using Bridge=HeldPairReturnBridge<Store,Crypto,Clock>;
    std::unique_ptr<Bridge> bridge(new(std::nothrow) Bridge(gate,token,length,crypto_,clock_,
        store_,boot_,forward_,session_hash_,forward_hash_));
    if(!bridge||!pair_.admit_return(*bridge))return stop("PAIR_RETURN_ADMISSION_FAILED");
    bridge.reset();
    returning_=true;
    // Forward bytes survive every rejection. Only an accepted continuation
    // releases them, after the host has asserted its verified durable export.
    publisher_.~HeldLegEvidencePublisher();new(&publisher_) HeldLegEvidencePublisher();
    store_.~Store();new(&store_) Store();
    if(!derive_leg_plan(reverse_,pair_.original_anchor(),return_plan_,return_hash_)||
       !store_.bind(*pair_.leg(),crypto_,boot_,reverse_)||
       !publisher_.begin(store_,boot_,reverse_))return stop("PAIR_RETURN_PREPARATION_FAILED");
    return true;
  }
  const Store& evidence()const{return store_;}
  void interference(){stop("PAIR_EXTERNAL_INTERFERENCE");}
  HeldPairPhase phase()const{return pair_.phase();}
  const char* reason()const{return stopped_?reason_:pair_.reason();}
  const char* session_hash()const{return started_?session_hash_:nullptr;}
  const char* forward_plan()const{return started_?forward_plan_:nullptr;}
  const char* forward_hash()const{return started_?forward_hash_:nullptr;}
  const char* return_plan()const{return return_plan_[0]?return_plan_:nullptr;}
  const char* boot_id()const{return boot_;}
  const char* active_leg()const{return returning_?"return":"forward";}
  const char* active_plan_hash()const{return returning_?return_hash_:forward_hash_;}
 private:
  struct Driver{
    HeldPairAuthenticatedRuntime& self;
    void poll(HeldElbowLegOwner& owner){
      self.publisher_.poll(owner,self.bus_,self.clock_,self.store_);
    }
  };
  bool derive_leg_plan(const char* command,int target,char* plan,char* hash){
    if(target<policy_.minimum[3]||target>policy_.maximum[3])return false;
    JsonDocument doc;doc["boot_id"]=boot_;doc["command_id"]=command;
    doc["policy_sha256"]=policy_hash_;doc["schema"]="rocell.held_leg_plan.v1";
    doc["target_count"]=target;doc["tolerance_counts"]=tolerance_;
    uint8_t digest[32];
    if(!hold_json_finish(doc,plan,512)||
       !crypto_.sha256(reinterpret_cast<const uint8_t*>(plan),strlen(plan),digest))return false;
    const char* hex="0123456789abcdef";
    for(size_t i=0;i<32;++i){hash[2*i]=hex[digest[i]>>4];hash[2*i+1]=hex[digest[i]&15];}
    hash[64]=0;return true;
  }
  template<size_t N> static bool copy(char (&out)[N],const char* value){
    if(!value)return false;size_t n=0;while(n<N&&value[n])++n;
    if(!n||n==N)return false;memcpy(out,value,n+1);return true;
  }
  bool stop(const char* reason){
    // Listener cleanup can follow a leg's terminal failure. Preserve that first
    // cause and its evidence; repeated cleanup must not relabel non-arrival.
    if(stopped_||pair_.phase()==HeldPairPhase::Stopped)return false;
    stopped_=true;reason_=reason;pair_.export_failed();return false;
  }
  Bus& bus_;Clock& clock_;Crypto& crypto_;HoldInitializationPolicy policy_;
  int offset_;uint16_t tolerance_;HeldElbowPairOwner pair_;Store store_;HeldLegEvidencePublisher publisher_;
  bool (*healthy_)(void*);void* context_;
  bool configured_=false,attempted_=false,started_=false,stopped_=false,returning_=false;
  const char* reason_="NOT_STARTED";
  char boot_[33]={},hold_hash_[65]={},forward_[129]={},reverse_[129]={};
  char session_hash_[65]={},policy_hash_[65]={},forward_hash_[65]={},return_hash_[65]={};
  char forward_plan_[512]={},return_plan_[512]={};
};
}
