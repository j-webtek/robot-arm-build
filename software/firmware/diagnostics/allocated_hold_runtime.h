// One bounded allocation for the entire hold object graph. No network or reset.
// A mode-selecting caller must not also instantiate the old startup runtime.
// Destruction frees RAM only; it must never release holding torque.
#pragma once
#include <new>
#include "hold_authenticated_runtime.h"
#include "evidence_store.h"
namespace rocell_diag {
template<class Library,class Clock,class Crypto,bool Recovery=false,uint8_t RecoveryLimit=5>
class AllocatedHoldRuntime {
 public:
  using Store=EvidenceStore<12,4096>;
  using Runtime=HoldAuthenticatedRuntime<Library,Clock,Store,Crypto,Recovery,RecoveryLimit>;
 private:
  struct Inner {
    Store store;Runtime runtime;
    Inner(Library& bus,Clock& clock,Crypto& crypto,const uint8_t (&key)[32],
          const uint8_t (&boot)[16],const uint8_t (&nonce)[32],uint64_t issued,uint64_t expires,
          const HoldInitializationPolicy& policy,const char* command,bool (*healthy)(void*),void* context)
      :runtime(bus,clock,store,crypto,key,boot,nonce,issued,expires,policy,command,healthy,context){}
  };
 public:
  AllocatedHoldRuntime()=default;
  AllocatedHoldRuntime(const AllocatedHoldRuntime&)=delete;
  AllocatedHoldRuntime& operator=(const AllocatedHoldRuntime&)=delete;
  ~AllocatedHoldRuntime(){delete inner_;}
  static constexpr size_t allocation_bytes(){return sizeof(Inner);}
  bool initialize(Library& bus,Clock& clock,Crypto& crypto,const uint8_t (&key)[32],
      const uint8_t (&boot)[16],const uint8_t (&nonce)[32],uint64_t issued,uint64_t expires,
      const HoldInitializationPolicy& policy,const char* command,bool (*healthy)(void*),void* context){
    if(used_)return false;used_=true;
    if(Recovery&&(policy.drift!=2||policy.speed!=20||policy.permit_explicit_enable))
      return fail("RECOVERY_POLICY_REJECTED");
    uint8_t nonzero=0;for(uint8_t byte:key)nonzero|=byte;
    if(!nonzero||!valid_identity(command)||!HoldInitializationOwner::policy_valid(policy)||
       issued>INT64_MAX||expires>INT64_MAX||expires<=issued||expires-issued>30000000||
       bus.End!=0||bus.Level!=1||!healthy||!healthy(context))return fail("HOLD_SETUP_REJECTED");
    const uint64_t now=clock.now_us();
    if(now<issued||now>=expires)return fail("HOLD_SETUP_EXPIRED");
    inner_=new(std::nothrow) Inner(bus,clock,crypto,key,boot,nonce,issued,expires,policy,command,healthy,context);
    if(!inner_)return fail("HOLD_MEMORY_UNAVAILABLE");
    return true;
  }
  bool start(const uint8_t* bytes,size_t length){return inner_&&!failure_&&inner_->runtime.start(bytes,length);}
  void poll(){if(inner_&&!failure_)inner_->runtime.poll();}
  void interference(){used_=true;if(inner_)inner_->runtime.interference();else fail("HOLD_EXTERNAL_INTERFERENCE");}
  const char* reason()const{return failure_?failure_:inner_?inner_->runtime.reason():"NOT_INITIALIZED";}
  size_t size()const{return inner_?inner_->store.size():0;}
  const typename Store::Record* get(size_t index)const{return inner_?inner_->store.get(index):nullptr;}
  bool storage_faulted()const{return inner_&&inner_->store.faulted();}
  const HoldInitializationOwner* owner()const{return inner_?&inner_->runtime.owner():nullptr;}
  bool take_handoff(VerifiedHoldHandoff& out){return inner_&&!failure_&&inner_->runtime.take_handoff(out);}
 private:
  bool fail(const char* reason){failure_=reason;return false;}
  bool used_=false;const char* failure_=nullptr;Inner* inner_=nullptr;
};
}
