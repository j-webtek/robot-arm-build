// Explicit hold-to-pair composition for firmware entry points. No filesystem,
// auto challenge, default motion, torque release, reset, retry or configuration.
#pragma once
#include "held_pair_authenticated_runtime.h"
#include "held_pair_network_lifecycle.h"
#include "held_pair_transport_json.h"
namespace rocell_diag {
template<class Bus,class Clock,class Crypto,class Entropy,class Server,class Client,class Socket>
class ConfiguredHeldPairRuntime {
  using Runtime=HeldPairAuthenticatedRuntime<Bus,Clock,Crypto>;
  using Lifecycle=HeldPairNetworkLifecycle<Runtime,Clock,Entropy,Server,Client,Socket>;
 public:
  ConfiguredHeldPairRuntime()=default;
  ConfiguredHeldPairRuntime(const ConfiguredHeldPairRuntime&)=delete;
  ConfiguredHeldPairRuntime& operator=(const ConfiguredHeldPairRuntime&)=delete;
  template<class Hold>
  bool initialize_from_hold(Hold& hold,Bus& bus,Clock& clock,Crypto& crypto,Entropy& entropy,
      const HoldInitializationPolicy& policy,const uint8_t (&key)[32],const uint8_t (&boot)[16],
      uint16_t port,const char* forward,const char* reverse,int offset,uint8_t tolerance,
      bool (*healthy)(void*),void* context){
    if(attempted_)return false;attempted_=true;
    uint8_t nonzero=0;for(uint8_t b:key)nonzero|=b;
    if(!nonzero||port<1024||!HoldInitializationOwner::policy_valid(policy)||
       !valid_identity(forward)||!valid_identity(reverse)||!strcmp(forward,reverse)||
       tolerance>2||offset<-16||offset>16||(offset>=-int(2*tolerance)&&offset<=int(2*tolerance))||
       bus.End!=0||bus.Level!=1)return fail("PAIR_CONFIGURATION_REJECTED");
    if(!healthy||!healthy(context))return fail("PAIR_HEALTH_REJECTED");
    // Retire the large old graph BEFORE allocating the new one. A failure after
    // this point is terminal, with torque unchanged and no automatic recovery.
    if(!hold.retire_to_pair(handoff_))return fail("PAIR_HOLD_HANDOFF_REJECTED");
    char boot_text[33]={};const char* hex="0123456789abcdef";
    for(size_t i=0;i<16;++i){boot_text[2*i]=hex[boot[i]>>4];boot_text[2*i+1]=hex[boot[i]&15];}
    runtime_.reset(new(std::nothrow) Runtime(bus,clock,crypto,policy,boot_text,
        handoff_.plan_hash(),forward,reverse,offset,tolerance,healthy,context));
    if(!runtime_)return fail("PAIR_RUNTIME_MEMORY_UNAVAILABLE");
    lifecycle_.reset(new(std::nothrow) Lifecycle(*runtime_,handoff_,clock,entropy,port,key,boot));
    if(!lifecycle_)return fail("PAIR_LIFECYCLE_MEMORY_UNAVAILABLE");
    return true;
  }
  bool issue_initial(char* out,size_t capacity){
    if(out&&capacity)out[0]=0;
    if(!lifecycle_||failure_)return false;
    return lifecycle_->issue_initial(out,capacity);
  }
  bool issue_return(char* out,size_t capacity){
    if(out&&capacity)out[0]=0;
    if(!lifecycle_||failure_)return false;
    return lifecycle_->issue_return(out,capacity);
  }
  void poll(){if(lifecycle_&&!failure_)lifecycle_->poll();}
  // The web owner must not serve other handlers while a POST/motion is active.
  bool exclusive_work()const{
    return lifecycle_&&(lifecycle_->phase()==PairNetworkPhase::Initial||
                        lifecycle_->phase()==PairNetworkPhase::Returning);
  }
  void interference(){fail("PAIR_EXTERNAL_INTERFERENCE");}
  void export_failed(){fail("PAIR_EXPORT_FAILED");}
  bool status_json(char* out,size_t capacity)const{
    return runtime_&&held_pair_status_json(*runtime_,out,capacity);
  }
  bool record_json(size_t index,char* out,size_t capacity)const{
    return runtime_&&held_pair_record_json(*runtime_,index,out,capacity);
  }
  size_t record_count()const{return runtime_?runtime_->evidence().size():0;}
  const char* reason()const{return failure_?failure_:runtime_?runtime_->reason():"PAIR_NOT_CONFIGURED";}
  PairNetworkPhase phase()const{return failure_?PairNetworkPhase::Fault:
      lifecycle_?lifecycle_->phase():PairNetworkPhase::New;}
 private:
  bool fail(const char* reason){
    if(!failure_)failure_=reason;
    lifecycle_.reset();if(runtime_)runtime_->interference();return false;
  }
  bool attempted_=false;const char* failure_=nullptr;
  // Reverse destruction order preserves all borrowed references.
  VerifiedHoldHandoff handoff_;
  std::unique_ptr<Runtime> runtime_;
  std::unique_ptr<Lifecycle> lifecycle_;
};
}
