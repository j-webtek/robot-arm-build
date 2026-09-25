// Adapts a pre-initialized allocated hold runtime to the existing one-shot HTTP
// listener. Sampling includes all exclusive prewrite and postwrite acquisition.
#pragma once
#include "allocated_hold_runtime.h"
#include "diagnostic_session.h"
namespace rocell_diag {
template<class Allocated>
class HoldListenerOwner {
 public:
  explicit HoldListenerOwner(Allocated& runtime):runtime_(runtime){}
  bool start(const uint8_t* bytes,size_t length){
    if(used_||fault_)return false;
    used_=true;
    if(!runtime_.start(bytes,length)){fault_=true;return false;}
    return true;
  }
  bool sample(){if(!fault_)runtime_.poll();return state()!=SessionState::Fault;}
  bool owned()const{return used_||fault_;}
  SessionState state()const{
    if(fault_)return SessionState::Fault;
    if(!used_)return SessionState::Idle;
    const auto* owner=runtime_.owner();
    if(!owner)return SessionState::Fault;
    if(owner->phase()==HoldPhase::Fault)return SessionState::Fault;
    if(owner->phase()==HoldPhase::Captured)return SessionState::Captured;
    return SessionState::Sampling;
  }
  const char* reason()const{return runtime_.reason();}
  void interference(){fault_=true;runtime_.interference();}
  void export_failed(){interference();}
 private:
  Allocated& runtime_;bool used_=false,fault_=false;
};
}
