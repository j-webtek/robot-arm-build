// Reuse the one-connection start listener for one authenticated operation.
// Initial and return operations need distinct fresh challenges and lifetimes.
// Same bounded POST parser; plan schemas/nonce/gates distinguish operations.
#pragma once
#include "held_pair_authenticated_runtime.h"
#include "diagnostic_session.h"
namespace rocell_diag {
template<class Runtime> struct HeldPairInitialOperation {
  Runtime& runtime;HeldPairPlanAdmission& gate;VerifiedHoldHandoff& held;
  bool start(const uint8_t* bytes,size_t length){return runtime.start(gate,bytes,length,held);}
};
template<class Runtime> struct HeldPairReturnOperation {
  Runtime& runtime;HeldReturnAdmission& gate;
  bool start(const uint8_t* bytes,size_t length){return runtime.admit_return(gate,bytes,length);}
};
template<class Runtime,class Operation> class HeldPairListenerOwner {
 public:
  HeldPairListenerOwner(Runtime& runtime,Operation& operation,bool returning)
      :runtime_(runtime),operation_(operation),returning_(returning){}
  bool start(const uint8_t* bytes,size_t length){
    if(used_||fault_)return false;used_=true;
    const auto expected=returning_?HeldPairPhase::AwaitingExport:HeldPairPhase::New;
    if(runtime_.phase()!=expected||!operation_.start(bytes,length)){interference();return false;}
    return true;
  }
  bool sample(){if(used_&&!fault_)runtime_.poll();return state()!=SessionState::Fault;}
  bool owned()const{return used_||fault_;}
  SessionState state()const{
    if(fault_||runtime_.phase()==HeldPairPhase::Stopped)return SessionState::Fault;
    if(!used_)return SessionState::Idle;
    const auto completed=returning_?HeldPairPhase::Complete:HeldPairPhase::AwaitingExport;
    return runtime_.phase()==completed?SessionState::Captured:SessionState::Sampling;
  }
  const char* reason()const{return runtime_.reason();}
  void interference(){fault_=true;runtime_.interference();}
  void export_failed(){interference();}
 private:
  Runtime& runtime_;Operation& operation_;bool returning_,used_=false,fault_=false;
};
}
